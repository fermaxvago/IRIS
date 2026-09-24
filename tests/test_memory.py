"""Persistent evidence, temporal state, lifecycle, and schema regression tests."""

from __future__ import annotations

import sqlite3
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from iris.memory import (
    SCHEMA_VERSION,
    AcquisitionMode,
    CurrentStatus,
    EpistemicStatus,
    LifecycleStatus,
    MemoryCandidate,
    MemoryClass,
    MemoryConflictError,
    MemoryDataError,
    MemoryKind,
    MemoryNotFoundError,
    MemoryProvenance,
    MemoryQuery,
    MemorySchemaError,
    MemoryScope,
    MemoryService,
    MemoryStore,
    RelationKind,
    Retention,
    ScopeKind,
    SourceType,
    SQLiteMemoryStore,
)

MON = datetime(2026, 9, 21, 12, tzinfo=UTC)
TUE = MON + timedelta(days=1)
WED = TUE + timedelta(days=1)
GLOBAL = MemoryScope(ScopeKind.GLOBAL)
PROJECT = MemoryScope(ScopeKind.PROJECT, "iris")


def candidate(
    content: str = "85",
    *,
    kind: str = MemoryKind.FACT,
    subject: str = "fer.weight",
    observed_at: datetime | None = TUE,
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
    scope: MemoryScope = GLOBAL,
    epistemic: EpistemicStatus = EpistemicStatus.DIRECT,
    provenance: MemoryProvenance | None = None,
    acquisition: AcquisitionMode = AcquisitionMode.EXPLICIT,
) -> MemoryCandidate:
    return MemoryCandidate(
        memory_class=MemoryClass.SEMANTIC,
        kind=kind,
        subject=subject,
        content=content,
        provenance=provenance
        or MemoryProvenance(SourceType.USER_STATEMENT, "chat-1", "fer"),
        epistemic=epistemic,
        acquisition=acquisition,
        scope=scope,
        retention=Retention.LONG,
        observed_at=observed_at,
        valid_from=valid_from,
        valid_until=valid_until,
        source_reference="source-1",
        artifact_reference="artifact-1",
    )


def service(path: Path) -> tuple[SQLiteMemoryStore, MemoryService]:
    store = SQLiteMemoryStore(path)
    assert isinstance(store, MemoryStore)
    return store, MemoryService(store)


def test_persistence_survives_close_and_reopen_with_semantic_fields(
    tmp_path: Path,
) -> None:
    path = tmp_path / "memory.sqlite"
    db, api = service(path)
    original = api.store(candidate("the recorded value", scope=PROJECT))
    db.close()

    with SQLiteMemoryStore(path) as reopened:
        assert reopened.get(original.id) == original
        assert reopened.query(MemoryQuery(scope=PROJECT)) == (original,)
        assert reopened.query(MemoryQuery(scope=GLOBAL)) == ()
        assert (
            reopened._connection.execute("PRAGMA user_version").fetchone()[0]
            == SCHEMA_VERSION
        )


def test_current_and_history_with_atomic_supersession(tmp_path: Path) -> None:
    with SQLiteMemoryStore(tmp_path / "memory.sqlite") as db:
        api = MemoryService(db)
        old = api.store(candidate("93", observed_at=MON))
        new = api.supersede(old.id, candidate("85", observed_at=TUE))
        assert (
            api.current(
                subject="fer.weight", kind=MemoryKind.FACT, scope=GLOBAL, as_of=WED
            ).record
            == new
        )
        assert api.get(old.id) is None
        assert (
            api.get(old.id, include_history=True).lifecycle
            is LifecycleStatus.SUPERSEDED
        )  # type: ignore[union-attr]
        assert api.query(MemoryQuery(statuses=None)) == (
            replace(old, lifecycle=LifecycleStatus.SUPERSEDED),
            new,
        )
        assert new.relations[0].kind == RelationKind.SUPERSEDES
        assert new.relations[0].target_id == old.id

    with SQLiteMemoryStore(tmp_path / "memory.sqlite") as db:
        assert db.get(new.id) == new
        assert db.get(old.id) is not None


def test_late_recording_uses_observation_not_insert_time(tmp_path: Path) -> None:
    with SQLiteMemoryStore(tmp_path / "memory.sqlite") as db:
        api = MemoryService(db)
        recent = api.store(candidate("85", observed_at=TUE))
        late = api.store(candidate("86", observed_at=MON))
        assert late.recorded_at >= recent.recorded_at
        result = api.current(
            subject="fer.weight", kind=MemoryKind.FACT, scope=GLOBAL, as_of=WED
        )
        assert result.status is CurrentStatus.FOUND
        assert result.record == recent
        assert len(api.query(MemoryQuery(statuses=None))) == 2


def test_preference_change_preserves_history(tmp_path: Path) -> None:
    with SQLiteMemoryStore(tmp_path / "memory.sqlite") as db:
        api = MemoryService(db)
        first = api.store(
            candidate(
                "strong",
                kind=MemoryKind.PREFERENCE,
                subject="fer.music",
                observed_at=MON,
            )
        )
        second = api.supersede(
            first.id,
            candidate(
                "weaker",
                kind=MemoryKind.PREFERENCE,
                subject="fer.music",
                observed_at=TUE,
            ),
        )
        assert (
            api.current(
                subject="fer.music", kind=MemoryKind.PREFERENCE, scope=GLOBAL, as_of=WED
            ).record
            == second
        )
        assert (
            len(api.query(MemoryQuery(kind=MemoryKind.PREFERENCE, statuses=None))) == 2
        )


@pytest.mark.parametrize(
    "operation,status",
    [("retract", LifecycleStatus.RETRACTED), ("forget", LifecycleStatus.FORGOTTEN)],
)
def test_lifecycle_hides_normal_recall_without_deleting(
    tmp_path: Path,
    operation: str,
    status: LifecycleStatus,
) -> None:
    with SQLiteMemoryStore(tmp_path / "memory.sqlite") as db:
        api = MemoryService(db)
        record = api.store(candidate())
        getattr(api, operation)(record.id)
        assert api.get(record.id) is None
        assert api.query(MemoryQuery()) == ()
        assert api.get(record.id, include_history=True).lifecycle is status  # type: ignore[union-attr]
        assert api.query(MemoryQuery(statuses=None))[0].lifecycle is status
        assert (
            api.current(
                subject="fer.weight", kind=MemoryKind.FACT, scope=GLOBAL, as_of=WED
            ).status
            is CurrentStatus.NONE
        )


def test_provenance_and_epistemic_status_survive_reload(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite"
    with SQLiteMemoryStore(path) as db:
        api = MemoryService(db)
        records = [
            api.store(
                candidate(
                    f"evidence-{status.value}",
                    subject=f"subject.{status.value}",
                    provenance=MemoryProvenance(
                        SourceType.OTHER_PERSON_STATEMENT
                        if status is EpistemicStatus.DIRECT
                        else SourceType.DEVICE_TELEMETRY,
                        "report-1",
                        "mother" if status is EpistemicStatus.DIRECT else "sensor",
                    ),
                    epistemic=status,
                )
            )
            for status in (
                EpistemicStatus.DIRECT,
                EpistemicStatus.OBSERVED,
                EpistemicStatus.DERIVED,
                EpistemicStatus.INFERRED,
            )
        ]
    with SQLiteMemoryStore(path) as db:
        assert [db.get(record.id) for record in records] == records
        assert db.get(records[0].id).candidate.provenance.actor == "mother"  # type: ignore[union-attr]
        assert db.get(records[1].id).candidate.provenance.actor == "sensor"  # type: ignore[union-attr]


def test_temporal_query_is_half_open_and_uses_observed_at(tmp_path: Path) -> None:
    with SQLiteMemoryStore(tmp_path / "memory.sqlite") as db:
        api = MemoryService(db)
        monday = api.store(candidate("monday", observed_at=MON))
        tuesday = api.store(candidate("tuesday", observed_at=TUE))
        api.store(candidate("unknown time", observed_at=None))
        assert api.query(MemoryQuery(observed_from=MON, observed_until=TUE)) == (
            monday,
        )
        assert api.query(MemoryQuery(observed_from=TUE, observed_until=WED)) == (
            tuesday,
        )


def test_relations_persist_and_are_not_artifact_ingestion(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite"
    with SQLiteMemoryStore(path) as db:
        api = MemoryService(db)
        first = api.store(candidate("input", subject="evidence.a"))
        second = api.store(candidate("derived", subject="evidence.b"))
        relation = api.relate(second.id, first.id, RelationKind.DERIVED_FROM)
        assert db.get(second.id).relations == (relation,)  # type: ignore[union-attr]
    with SQLiteMemoryStore(path) as db:
        assert db.get(second.id).relations == (relation,)  # type: ignore[union-attr]
        assert db.get(second.id).candidate.artifact_reference == "artifact-1"  # type: ignore[union-attr]


def test_repeat_queries_order_deterministically(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite"
    with SQLiteMemoryStore(path) as db:
        api = MemoryService(db)
        for value in ("z", "a", "m"):
            api.store(candidate(value))
        first = api.query(MemoryQuery())
        assert first == api.query(MemoryQuery())
        assert [(record.recorded_at, record.id) for record in first] == sorted(
            (record.recorded_at, record.id) for record in first
        )
    with SQLiteMemoryStore(path) as db:
        assert db.query(MemoryQuery()) == first


def test_unknown_future_schema_fails_without_modifying_it(tmp_path: Path) -> None:
    path = tmp_path / "future.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA user_version = 999")
        db.execute("CREATE TABLE future_data (important TEXT)")
        db.execute("INSERT INTO future_data VALUES ('keep')")
    with pytest.raises(MemorySchemaError, match="999"):
        SQLiteMemoryStore(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 999
        assert db.execute("SELECT important FROM future_data").fetchone()[0] == "keep"


def test_nonempty_unversioned_database_is_not_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE existing (item TEXT)")
    with pytest.raises(MemorySchemaError, match="unversioned"):
        SQLiteMemoryStore(path)


def test_malformed_persisted_data_fails_explicitly(tmp_path: Path) -> None:
    with SQLiteMemoryStore(tmp_path / "memory.sqlite") as db:
        api = MemoryService(db)
        record = api.store(candidate())
        db._connection.execute(
            "UPDATE memories SET epistemic = ? WHERE id = ?", ("invalid", record.id)
        )
        with pytest.raises(MemoryDataError, match="malformed"):
            db.get(record.id)


def test_current_state_ambiguous_on_unknown_or_tied_event_time(tmp_path: Path) -> None:
    with SQLiteMemoryStore(tmp_path / "memory.sqlite") as db:
        api = MemoryService(db)
        api.store(candidate("a", observed_at=TUE))
        api.store(candidate("b", observed_at=TUE))
        assert (
            api.current(
                subject="fer.weight", kind=MemoryKind.FACT, scope=GLOBAL, as_of=WED
            ).status
            is CurrentStatus.AMBIGUOUS
        )
        api.store(candidate("unknown", observed_at=None))
        assert (
            api.current(
                subject="fer.weight", kind=MemoryKind.FACT, scope=GLOBAL, as_of=WED
            ).status
            is CurrentStatus.AMBIGUOUS
        )


def test_validity_and_explicit_expiry(tmp_path: Path) -> None:
    with SQLiteMemoryStore(tmp_path / "memory.sqlite") as db:
        api = MemoryService(db)
        record = api.store(
            candidate("valid", observed_at=MON, valid_from=TUE, valid_until=WED)
        )
        assert (
            api.current(
                subject="fer.weight", kind=MemoryKind.FACT, scope=GLOBAL, as_of=MON
            ).status
            is CurrentStatus.NONE
        )
        assert (
            api.current(
                subject="fer.weight", kind=MemoryKind.FACT, scope=GLOBAL, as_of=TUE
            ).record
            == record
        )
        assert (
            api.current(
                subject="fer.weight", kind=MemoryKind.FACT, scope=GLOBAL, as_of=WED
            ).status
            is CurrentStatus.NONE
        )
        with pytest.raises(MemoryConflictError):
            api.expire(record.id, as_of=TUE)
        assert api.expire(record.id, as_of=WED).lifecycle is LifecycleStatus.EXPIRED


def test_supersession_failure_is_atomic_and_preserves_old(tmp_path: Path) -> None:
    with SQLiteMemoryStore(tmp_path / "memory.sqlite") as db:
        api = MemoryService(db)
        old = api.store(candidate())
        with pytest.raises(MemoryConflictError, match="same subject"):
            api.supersede(old.id, candidate(subject="unrelated"))
        assert db.get(old.id) == old
        with pytest.raises(MemoryNotFoundError):
            api.supersede("missing", candidate())
        assert api.query(MemoryQuery(statuses=None)) == (old,)


def test_late_older_evidence_cannot_supersede_newer_observation(tmp_path: Path) -> None:
    with SQLiteMemoryStore(tmp_path / "memory.sqlite") as db:
        api = MemoryService(db)
        tuesday = api.store(candidate("85", observed_at=TUE))
        with pytest.raises(MemoryConflictError, match="backward"):
            api.supersede(tuesday.id, candidate("86", observed_at=MON))
        assert db.get(tuesday.id) == tuesday
        assert api.query(MemoryQuery(statuses=None)) == (tuesday,)


def test_timezone_validation_and_normalization() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        candidate(observed_at=datetime(2026, 9, 21))
    from_zone = timezone(timedelta(hours=-6))
    assert (
        candidate(observed_at=datetime(2026, 9, 21, 6, tzinfo=from_zone)).observed_at
        == MON
    )
    with pytest.raises(FrozenInstanceError):
        candidate().content = "changed"  # type: ignore[misc]


def test_extensible_kind_and_source_vocabulary() -> None:
    custom = candidate(kind="incident", provenance=MemoryProvenance("device_event"))
    assert custom.kind == "incident"
    assert custom.provenance.source_type == "device_event"
    with pytest.raises(ValueError, match="lowercase"):
        candidate(kind="Bad Kind")
