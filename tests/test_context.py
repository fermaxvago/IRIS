"""Deterministic request context; no model, device or network needed."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from iris.context import (
    ContextBudget,
    ContextCandidate,
    ContextEngine,
    ContextEvidence,
    ContextItem,
    ContextKind,
    ContextPolicyContractError,
    ContextSelectionPolicy,
    ContextSnapshot,
    ContextUncertainty,
    DeterministicContextSelection,
    DuplicateContextCandidateError,
    EvidenceSource,
    Freshness,
    MemoryContextSource,
    Relevance,
    ResolutionStatus,
    UncertaintyReason,
)
from iris.context.selection import ContextSelection
from iris.core.request import Request
from iris.memory import (
    AcquisitionMode,
    EpistemicStatus,
    LifecycleStatus,
    MemoryCandidate,
    MemoryClass,
    MemoryKind,
    MemoryProvenance,
    MemoryQuery,
    MemoryScope,
    MemoryService,
    Retention,
    ScopeKind,
    SourceType,
    SQLiteMemoryStore,
)

NOW = datetime(2026, 9, 24, 12, tzinfo=UTC)
GLOBAL = MemoryScope(ScopeKind.GLOBAL)
IRIS = MemoryScope(ScopeKind.PROJECT, "iris")
PHYSICS = MemoryScope(ScopeKind.PROJECT, "physics")


def candidate(
    id: str,
    value: str | int | float | bool,
    *,
    kind: str = ContextKind.TASK,
    key: str = "active_task",
    scope: MemoryScope = GLOBAL,
    relevance: Relevance = Relevance.NORMAL,
    freshness: Freshness = Freshness.RECENT,
    source: EvidenceSource = EvidenceSource.CALLER,
    reference: str | None = None,
    epistemic: EpistemicStatus = EpistemicStatus.UNKNOWN,
    observed_at: datetime | None = None,
    eligible: bool = True,
) -> ContextCandidate:
    return ContextCandidate(
        candidate_id=id,
        kind=kind,
        key=key,
        value=value,
        evidence=ContextEvidence(source, reference or id, epistemic),
        scope=scope,
        relevance=relevance,
        freshness=freshness,
        observed_at=observed_at,
        eligible=eligible,
    )


def build(*items: ContextCandidate, budget: int = 10) -> ContextSnapshot:
    return ContextEngine().build(
        request_id="request-1",
        candidates=items,
        budget=ContextBudget(budget),
        created_at=NOW,
    )


def test_valid_models_are_typed_immutable_and_keep_unknown_time() -> None:
    evidence = ContextEvidence(
        EvidenceSource.CALLER, "event-1", EpistemicStatus.INFERRED
    )
    entry = candidate(
        "one",
        "iris",
        kind=ContextKind.PROJECT,
        key="active_project",
        epistemic=EpistemicStatus.INFERRED,
    )
    assert entry.kind == ContextKind.PROJECT
    assert entry.evidence == replace(evidence, reference="one")
    assert entry.observed_at is None


def test_candidate_item_snapshot_are_immutable_and_traceable() -> None:
    entry = candidate(
        "candidate-1",
        "iris",
        kind=ContextKind.PROJECT,
        key="active_project",
        observed_at=None,
        epistemic=EpistemicStatus.INFERRED,
    )
    item = entry.to_item()
    snapshot = ContextEngine().build(
        request_id="request-1",
        candidates=(entry,),
        budget=ContextBudget(1),
        created_at=NOW,
    )
    assert isinstance(item, ContextItem)
    assert snapshot.items == (item,)
    assert snapshot.items[0].evidence.epistemic is EpistemicStatus.INFERRED
    assert snapshot.items[0].observed_at is None
    assert snapshot.snapshot_id
    assert snapshot.request_id == "request-1"
    assert snapshot.status is ResolutionStatus.RESOLVED
    with pytest.raises(FrozenInstanceError):
        entry.key = "different"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        snapshot.items = ()  # type: ignore[misc]


@pytest.mark.parametrize(
    "bad_value", [None, ["x"], {"x": "y"}, float("nan"), float("inf")]
)
def test_context_value_rejects_non_scalars_and_nonfinite_numbers(
    bad_value: object,
) -> None:
    with pytest.raises((ValueError, TypeError)):
        candidate("invalid", bad_value)  # type: ignore[arg-type]


def test_invalid_vocabulary_and_provenance_reference_rejected() -> None:
    with pytest.raises(ValueError, match="lowercase"):
        candidate("one", "data", kind="Bad Kind")
    with pytest.raises(ValueError, match="lowercase"):
        candidate("one", "data", key="Bad Key")
    with pytest.raises(ValueError, match="reference"):
        ContextEvidence(EvidenceSource.REQUEST, "")
    with pytest.raises(TypeError, match="EvidenceSource"):
        ContextEvidence("request", "request-1")  # type: ignore[arg-type]


def test_temporal_metadata_normalized_to_utc_without_inventing_unknown() -> None:
    offset = timezone(timedelta(hours=-6))
    when = datetime(2026, 9, 24, 6, tzinfo=offset)
    assert candidate("one", "value", observed_at=when).observed_at == NOW
    assert candidate("two", "value").observed_at is None
    with pytest.raises(ValueError, match="timezone-aware"):
        candidate("bad", "value", observed_at=datetime(2026, 9, 24))
    with pytest.raises(ValueError, match="timezone-aware"):
        ContextEngine().build(
            request_id="request-1",
            candidates=(),
            budget=ContextBudget(0),
            created_at=datetime(2026, 9, 24),
        )
    with pytest.raises(ValueError, match="postdate"):
        build(candidate("future", "value", observed_at=NOW + timedelta(seconds=1)))


def test_request_evidence_must_belong_to_current_request() -> None:
    request = Request("¿Qué sigue?", "cli", request_id="request-1")
    matching = candidate(
        "from-request",
        request.content,
        source=EvidenceSource.REQUEST,
        reference=request.request_id,
    )
    assert build(matching).items[0].evidence.reference == request.request_id
    with pytest.raises(ValueError, match="current request"):
        build(
            replace(
                matching,
                evidence=ContextEvidence(EvidenceSource.REQUEST, "other-request"),
            )
        )


def test_categories_freshness_and_relevance_remain_independent() -> None:
    strong_old = candidate(
        "old",
        "calculus",
        relevance=Relevance.HIGH,
        freshness=Freshness.STALE,
        key="old_routine",
    )
    fresh_low = candidate(
        "now",
        "physics",
        relevance=Relevance.LOW,
        freshness=Freshness.CURRENT,
        key="current_activity",
    )
    snapshot = build(fresh_low, strong_old, budget=1)
    assert snapshot.items[0].candidate_id == "old"
    assert snapshot.items[0].freshness is Freshness.STALE
    assert snapshot.items[0].relevance is Relevance.HIGH


def test_relevance_order_and_freshness_tiebreak_are_explicit() -> None:
    examples = (
        candidate("low", "low", relevance=Relevance.LOW, key="low"),
        candidate("normal", "normal", relevance=Relevance.NORMAL, key="normal"),
        candidate("high", "high", relevance=Relevance.HIGH, key="high"),
        candidate("required", "required", relevance=Relevance.REQUIRED, key="required"),
    )
    selected = DeterministicContextSelection().select(examples, ContextBudget(4))
    assert [item.candidate_id for item in selected.items] == [
        "required",
        "high",
        "normal",
        "low",
    ]
    same = tuple(
        candidate(label, label, key=label, freshness=freshness)
        for label, freshness in (
            ("unknown", Freshness.UNKNOWN),
            ("stale", Freshness.STALE),
            ("recent", Freshness.RECENT),
            ("current", Freshness.CURRENT),
        )
    )
    assert [
        item.candidate_id
        for item in DeterministicContextSelection().select(same, ContextBudget(4)).items
    ] == ["current", "recent", "stale", "unknown"]


def test_stable_ties_permutations_and_exact_duplicates() -> None:
    a = candidate("a", "a", key="alpha")
    b = candidate("b", "b", key="beta")
    engine = ContextEngine()
    first = engine.build(
        request_id="request-1",
        candidates=(b, a, a),
        budget=ContextBudget(1),
        created_at=NOW,
    )
    second = engine.build(
        request_id="request-1",
        candidates=(a, a, b),
        budget=ContextBudget(1),
        created_at=NOW,
    )
    assert first.items == second.items
    assert first.items[0].candidate_id == "a"
    assert first.budget_excluded_ids == second.budget_excluded_ids == ("b",)
    assert first.status is second.status is ResolutionStatus.RESOLVED


def test_duplicate_evidence_collapses_and_incompatible_duplicate_id_fails() -> None:
    a = candidate("a", "iris")
    b = candidate("b", "iris", reference="a")
    assert build(a, b).items == (a.to_item(),)
    with pytest.raises(DuplicateContextCandidateError):
        build(a, replace(a, value="other"))


def test_ineligible_candidates_do_not_enter_snapshot_or_force_partial() -> None:
    irrelevant = candidate(
        "unrelated", "secret", relevance=Relevance.REQUIRED, eligible=False
    )
    assert build(irrelevant, budget=0).items == ()
    assert build(irrelevant, budget=0).status is ResolutionStatus.RESOLVED


def test_many_available_unrelated_candidates_stay_out_of_trivial_request() -> None:
    candidates = tuple(
        candidate(f"unrelated-{n}", "memory", key=f"unrelated_{n}", eligible=False)
        for n in range(100)
    )
    snapshot = build(*candidates, budget=2)
    assert snapshot.items == ()
    assert snapshot.status is ResolutionStatus.RESOLVED


def test_invalid_budget_and_budget_exclusion_of_required_information() -> None:
    with pytest.raises(ValueError, match="nonnegative"):
        ContextBudget(-1)
    with pytest.raises(TypeError, match="integer"):
        ContextBudget(True)  # type: ignore[arg-type]
    required = candidate("needed", "iris", relevance=Relevance.REQUIRED, key="project")
    snapshot = build(required, budget=0)
    assert snapshot.items == ()
    assert snapshot.status is ResolutionStatus.PARTIAL
    assert snapshot.uncertainties[0].reason is UncertaintyReason.BUDGET_EXCLUDED
    assert snapshot.uncertainties[0].candidate_ids == ("needed",)


def test_partial_for_explicit_missing_context_and_ambiguity_for_plausible_options() -> (
    None
):
    session = candidate(
        "session",
        "wp008",
        kind=ContextKind.SESSION,
        key="active_project",
        scope=MemoryScope(ScopeKind.SESSION, "one"),
        relevance=Relevance.HIGH,
    )
    task = candidate(
        "task",
        "wp008",
        kind=ContextKind.TASK,
        key="active_task",
        scope=MemoryScope(ScopeKind.TASK, "one"),
        relevance=Relevance.HIGH,
    )
    engine = ContextEngine()
    clean = engine.build(
        request_id="request-1",
        candidates=(session, task),
        budget=ContextBudget(2),
        created_at=NOW,
    )
    assert clean.status is ResolutionStatus.RESOLVED
    missing = ContextUncertainty(
        ContextKind.TASK, "task_detail", GLOBAL, UncertaintyReason.MISSING
    )
    partial = engine.build(
        request_id="request-1",
        candidates=(session,),
        budget=ContextBudget(2),
        uncertainties=(missing,),
        created_at=NOW,
    )
    assert partial.status is ResolutionStatus.PARTIAL
    assert partial.uncertainties == (missing,)
    activity = candidate(
        "activity",
        "physics",
        kind=ContextKind.ACTIVITY,
        key="observed_activity",
        relevance=Relevance.HIGH,
        freshness=Freshness.CURRENT,
    )
    ambiguous = ContextUncertainty(
        ContextKind.TASK,
        "intended_task",
        GLOBAL,
        UncertaintyReason.MULTIPLE_PLAUSIBLE,
        (session.candidate_id, activity.candidate_id),
    )
    result = engine.build(
        request_id="request-1",
        candidates=(session, activity),
        budget=ContextBudget(2),
        uncertainties=(ambiguous,),
        created_at=NOW,
    )
    assert result.status is ResolutionStatus.AMBIGUOUS
    assert result.uncertainties[0].candidate_ids == ("session", "activity")


def test_equal_priority_incompatible_values_make_inspectable_conflict() -> None:
    first = candidate("a", "physics", observed_at=NOW - timedelta(hours=1))
    second = candidate("b", "wp008", observed_at=NOW - timedelta(hours=2))
    first_result = build(first, second)
    second_result = build(second, first)
    assert first_result.status is second_result.status is ResolutionStatus.CONFLICTED
    assert first_result.items == ()
    assert first_result.conflicts == second_result.conflicts
    assert first_result.conflicts[0].candidate_ids == ("a", "b")
    assert tuple(ref.reference for ref in first_result.conflicts[0].evidence) == (
        "a",
        "b",
    )


def test_old_routine_does_not_override_current_evidence() -> None:
    routine = candidate(
        "routine",
        "calculus",
        freshness=Freshness.STALE,
        observed_at=NOW - timedelta(days=30),
    )
    direct = candidate(
        "activity",
        "physics",
        freshness=Freshness.CURRENT,
        observed_at=NOW,
        source=EvidenceSource.SESSION,
        epistemic=EpistemicStatus.OBSERVED,
    )
    snapshot = build(routine, direct)
    assert snapshot.status is ResolutionStatus.RESOLVED
    assert snapshot.items == (direct.to_item(),)


def test_scopes_remain_distinct_without_implicit_inheritance() -> None:
    entries = (
        candidate("iris", "wp008", scope=IRIS),
        candidate("physics", "quiz", scope=PHYSICS),
        candidate(
            "session", "conversation", scope=MemoryScope(ScopeKind.SESSION, "s1")
        ),
        candidate("task", "report", scope=MemoryScope(ScopeKind.TASK, "t1")),
    )
    snapshot = build(*entries)
    assert snapshot.status is ResolutionStatus.RESOLVED
    assert len(snapshot.items) == 4
    assert {item.scope for item in snapshot.items} == {entry.scope for entry in entries}


def test_presence_and_offline_state_do_not_authorize_or_route() -> None:
    presence = candidate(
        "present",
        "nadia",
        kind=ContextKind.ENVIRONMENT,
        key="person_present",
        source=EvidenceSource.SYSTEM,
    )
    offline = candidate(
        "offline",
        "offline",
        kind=ContextKind.RESOURCE,
        key="connectivity",
        source=EvidenceSource.RESOURCE,
    )
    snapshot = build(presence, offline)
    assert {item.key for item in snapshot.items} == {"person_present", "connectivity"}
    assert not hasattr(snapshot, "authorized_actions")
    assert not hasattr(snapshot, "model_id")


def test_context_policy_contract_and_unexpected_errors_remain_visible() -> None:
    assert isinstance(DeterministicContextSelection(), ContextSelectionPolicy)

    class Invented:
        def select(
            self, candidates: tuple[ContextCandidate, ...], budget: ContextBudget
        ) -> ContextSelection:
            return ContextSelection((candidate("invented", "value").to_item(),), (), ())

    class Broken:
        def select(
            self, candidates: tuple[ContextCandidate, ...], budget: ContextBudget
        ) -> ContextSelection:
            raise TypeError("programming defect")

    with pytest.raises(ContextPolicyContractError, match="not supplied"):
        ContextEngine(Invented()).build(
            request_id="request-1",
            candidates=(),
            budget=ContextBudget(1),
            created_at=NOW,
        )
    with pytest.raises(TypeError, match="programming defect"):
        ContextEngine(Broken()).build(
            request_id="request-1",
            candidates=(),
            budget=ContextBudget(1),
            created_at=NOW,
        )


def test_uncertainty_cannot_reference_unprovided_evidence() -> None:
    uncertainty = ContextUncertainty(
        ContextKind.TASK,
        "active_task",
        GLOBAL,
        UncertaintyReason.MULTIPLE_PLAUSIBLE,
        ("unknown", "other"),
    )
    with pytest.raises(ValueError, match="unknown candidate"):
        ContextEngine().build(
            request_id="request-1",
            candidates=(),
            budget=ContextBudget(1),
            uncertainties=(uncertainty,),
            created_at=NOW,
        )


def memory_candidate(
    value: str, *, subject: str = "iris.current_wp"
) -> MemoryCandidate:
    return MemoryCandidate(
        memory_class=MemoryClass.SEMANTIC,
        kind=MemoryKind.PROJECT_STATE,
        subject=subject,
        content=value,
        provenance=MemoryProvenance(
            SourceType.USER_STATEMENT, "conversation-1", "user"
        ),
        epistemic=EpistemicStatus.DIRECT,
        acquisition=AcquisitionMode.EXPLICIT,
        scope=IRIS,
        retention=Retention.LONG,
        observed_at=NOW - timedelta(days=1),
    )


def test_memory_source_is_explicit_read_only_and_keeps_records_hidden(
    tmp_path: Path,
) -> None:
    with SQLiteMemoryStore(tmp_path / "memory.sqlite") as store:
        memory = MemoryService(store)
        live = memory.store(memory_candidate("wp008"))
        forgotten = memory.store(memory_candidate("previous", subject="iris.old"))
        retracted = memory.store(memory_candidate("withdrawn", subject="iris.bad"))
        memory.forget(forgotten.id)
        memory.retract(retracted.id)
        source = MemoryContextSource(memory)
        query = MemoryQuery(
            subject="iris.current_wp", kind=MemoryKind.PROJECT_STATE, scope=IRIS
        )
        before = memory.query(MemoryQuery(scope=IRIS, statuses=None))
        candidates = source.candidates(
            query,
            kind=ContextKind.PROJECT,
            key="active_project",
            relevance=Relevance.NORMAL,
            freshness=Freshness.UNKNOWN,
        )
        assert len(candidates) == 1
        assert candidates[0].value == live.id
        assert candidates[0].evidence.reference == live.id
        assert candidates[0].evidence.epistemic is EpistemicStatus.DIRECT
        snapshot = ContextEngine().build(
            request_id="request-1",
            candidates=candidates,
            budget=ContextBudget(1),
            created_at=NOW,
        )
        assert snapshot.items[0].value == live.id
        assert memory.query(MemoryQuery(scope=IRIS, statuses=None)) == before
        assert all(
            item.lifecycle is not LifecycleStatus.FORGOTTEN
            for item in memory.query(MemoryQuery(scope=IRIS))
        )
        for hidden_subject in ("iris.old", "iris.bad"):
            assert (
                source.candidates(
                    MemoryQuery(
                        subject=hidden_subject,
                        kind=MemoryKind.PROJECT_STATE,
                        scope=IRIS,
                    ),
                    kind=ContextKind.PROJECT,
                    key="active_project",
                    relevance=Relevance.HIGH,
                    freshness=Freshness.UNKNOWN,
                )
                == ()
            )


def test_memory_history_and_content_expansion_require_explicit_opt_in(
    tmp_path: Path,
) -> None:
    with SQLiteMemoryStore(tmp_path / "memory.sqlite") as store:
        memory = MemoryService(store)
        old = memory.store(memory_candidate("wp007"))
        memory.supersede(old.id, memory_candidate("wp008"))
        source = MemoryContextSource(memory)
        historic = MemoryQuery(
            subject="iris.current_wp",
            kind=MemoryKind.PROJECT_STATE,
            scope=IRIS,
            statuses=None,
        )
        with pytest.raises(ValueError, match="include_history"):
            source.candidates(
                historic,
                kind=ContextKind.PROJECT,
                key="project",
                relevance=Relevance.NORMAL,
                freshness=Freshness.UNKNOWN,
            )
        with pytest.raises(ValueError, match="exact"):
            source.candidates(
                MemoryQuery(scope=IRIS),
                kind=ContextKind.PROJECT,
                key="project",
                relevance=Relevance.NORMAL,
                freshness=Freshness.UNKNOWN,
            )
        with pytest.raises(ValueError, match="single matching record"):
            source.candidates(
                historic,
                kind=ContextKind.PROJECT,
                key="project",
                relevance=Relevance.NORMAL,
                freshness=Freshness.UNKNOWN,
                include_history=True,
            )
        active = source.candidates(
            MemoryQuery(
                subject="iris.current_wp", kind=MemoryKind.PROJECT_STATE, scope=IRIS
            ),
            kind=ContextKind.PROJECT,
            key="project",
            relevance=Relevance.NORMAL,
            freshness=Freshness.UNKNOWN,
            include_content=True,
        )
        assert len(active) == 1 and active[0].value == "wp008"
        history = source.candidates(
            historic,
            kind=ContextKind.PROJECT,
            key="project",
            relevance=Relevance.NORMAL,
            freshness=Freshness.UNKNOWN,
            include_history=True,
            include_content=True,
        )
        assert len(history) == 2
        assert {item.evidence.reference for item in history} == {
            record.id for record in memory.query(historic)
        }
