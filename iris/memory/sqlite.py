"""Local SQLite persistence for IRIS memory records (schema version 1)."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from iris.memory.errors import (
    MemoryConflictError,
    MemoryDataError,
    MemoryNotFoundError,
    MemorySchemaError,
)
from iris.memory.models import (
    AcquisitionMode,
    EpistemicStatus,
    LifecycleStatus,
    MemoryCandidate,
    MemoryClass,
    MemoryProvenance,
    MemoryQuery,
    MemoryRecord,
    MemoryRelation,
    MemoryScope,
    Retention,
    ScopeKind,
    utc_time,
)

SCHEMA_VERSION = 1


_CREATE_RECORDS = """
CREATE TABLE memories (
    id TEXT PRIMARY KEY, memory_class TEXT NOT NULL, kind TEXT NOT NULL,
    subject TEXT NOT NULL, content TEXT NOT NULL,
    source_type TEXT NOT NULL, source_id TEXT, actor TEXT,
    epistemic TEXT NOT NULL, acquisition TEXT NOT NULL,
    scope_kind TEXT NOT NULL, scope_id TEXT, retention TEXT NOT NULL,
    observed_at TEXT, recorded_at TEXT NOT NULL,
    valid_from TEXT, valid_until TEXT,
    lifecycle TEXT NOT NULL, source_reference TEXT, artifact_reference TEXT
)
"""

_CREATE_RELATIONS = """
CREATE TABLE relations (
    source_id TEXT NOT NULL REFERENCES memories(id),
    target_id TEXT NOT NULL REFERENCES memories(id), kind TEXT NOT NULL,
    PRIMARY KEY (source_id, target_id, kind),
    CHECK (source_id != target_id)
)
"""

_COLUMNS = (
    "id",
    "memory_class",
    "kind",
    "subject",
    "content",
    "source_type",
    "source_id",
    "actor",
    "epistemic",
    "acquisition",
    "scope_kind",
    "scope_id",
    "retention",
    "observed_at",
    "recorded_at",
    "valid_from",
    "valid_until",
    "lifecycle",
    "source_reference",
    "artifact_reference",
)


def _stamp(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat(timespec="microseconds")


def _read_stamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("timestamp must be text")
    return utc_time(datetime.fromisoformat(value), "stored timestamp")


class SQLiteMemoryStore:
    """Explicit SQLite backend; callers own its lifecycle and database path."""

    def __init__(self, path: str | Path) -> None:
        db_path = Path(path)
        if not db_path.parent.is_dir():
            raise FileNotFoundError(
                f"memory database directory does not exist: {db_path.parent}"
            )
        self._connection = sqlite3.connect(db_path)
        self._connection.row_factory = sqlite3.Row
        try:
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._initialize()
        except (sqlite3.DatabaseError, MemorySchemaError):
            self._connection.close()
            raise

    def __enter__(self) -> SQLiteMemoryStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._connection.close()

    def _initialize(self) -> None:
        version = self._connection.execute("PRAGMA user_version").fetchone()[0]
        if version != 0 and version != SCHEMA_VERSION:
            raise MemorySchemaError(f"unsupported memory schema version: {version}")
        if version == 0:
            existing = self._connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') "
                "AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            if existing:
                raise MemorySchemaError("unversioned nonempty memory database")
            with self._connection:
                self._connection.execute(_CREATE_RECORDS)
                self._connection.execute(_CREATE_RELATIONS)
                self._connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        else:
            tables = {
                row[0]
                for row in self._connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if not {"memories", "relations"}.issubset(tables):
                raise MemorySchemaError("versioned memory database is missing tables")

    def insert(self, record: MemoryRecord) -> None:
        if not isinstance(record, MemoryRecord) or record.relations:
            raise ValueError("insert requires a MemoryRecord without relations")
        with self._connection:
            try:
                self._insert_row(record)
            except sqlite3.IntegrityError as exc:
                raise MemoryConflictError(
                    f"memory already exists: {record.id}"
                ) from exc

    def _insert_row(self, record: MemoryRecord) -> None:
        c = record.candidate
        values = (
            record.id,
            c.memory_class.value,
            c.kind,
            c.subject,
            c.content,
            c.provenance.source_type,
            c.provenance.source_id,
            c.provenance.actor,
            c.epistemic.value,
            c.acquisition.value,
            c.scope.kind.value,
            c.scope.identifier,
            c.retention.value,
            _stamp(c.observed_at),
            _stamp(record.recorded_at),
            _stamp(c.valid_from),
            _stamp(c.valid_until),
            record.lifecycle.value,
            c.source_reference,
            c.artifact_reference,
        )
        placeholders = ",".join("?" for _ in _COLUMNS)
        self._connection.execute(
            f"INSERT INTO memories ({','.join(_COLUMNS)}) VALUES ({placeholders})",
            values,
        )

    def get(self, memory_id: str) -> MemoryRecord | None:
        row = self._connection.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        return None if row is None else self._decode(row)

    def query(self, filters: MemoryQuery) -> tuple[MemoryRecord, ...]:
        if not isinstance(filters, MemoryQuery):
            raise TypeError("filters must be a MemoryQuery")
        conditions: list[str] = []
        params: list[str] = []
        for column, value in (
            ("id", filters.id),
            ("memory_class", filters.memory_class),
            ("kind", filters.kind),
            ("subject", filters.subject),
        ):
            if value is not None:
                conditions.append(f"{column} = ?")
                params.append(str(value))
        if filters.scope is not None:
            conditions.append("scope_kind = ?")
            params.append(filters.scope.kind.value)
            if filters.scope.identifier is None:
                conditions.append("scope_id IS NULL")
            else:
                conditions.append("scope_id = ?")
                params.append(filters.scope.identifier)
        if filters.statuses is not None:
            if not filters.statuses:
                return ()
            conditions.append(
                "lifecycle IN (" + ",".join("?" for _ in filters.statuses) + ")"
            )
            params.extend(sorted(status.value for status in filters.statuses))
        if filters.observed_from is not None:
            conditions.append("observed_at >= ?")
            params.append(_stamp(filters.observed_from) or "")
        if filters.observed_until is not None:
            conditions.append("observed_at < ?")
            params.append(_stamp(filters.observed_until) or "")
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        rows = self._connection.execute(
            "SELECT * FROM memories" + where + " ORDER BY recorded_at ASC, id ASC",
            params,
        ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def transition(self, memory_id: str, lifecycle: LifecycleStatus) -> MemoryRecord:
        if lifecycle not in (
            LifecycleStatus.RETRACTED,
            LifecycleStatus.FORGOTTEN,
            LifecycleStatus.EXPIRED,
        ):
            raise MemoryConflictError("unsupported standalone lifecycle transition")
        with self._connection:
            record = self.get(memory_id)
            if record is None:
                raise MemoryNotFoundError(memory_id)
            if record.lifecycle is not LifecycleStatus.ACTIVE:
                raise MemoryConflictError("only active memories can transition")
            self._connection.execute(
                "UPDATE memories SET lifecycle = ? WHERE id = ?",
                (lifecycle.value, memory_id),
            )
        return replace(record, lifecycle=lifecycle)

    def supersede(self, old_id: str, new_record: MemoryRecord) -> MemoryRecord:
        if (
            not isinstance(new_record, MemoryRecord)
            or new_record.lifecycle is not LifecycleStatus.ACTIVE
            or new_record.relations
        ):
            raise ValueError("supersede requires a new active record without relations")
        with self._connection:
            old = self.get(old_id)
            if old is None:
                raise MemoryNotFoundError(old_id)
            if old.lifecycle is not LifecycleStatus.ACTIVE:
                raise MemoryConflictError("only active memories can be superseded")
            first, second = old.candidate, new_record.candidate
            if (first.subject, first.kind, first.scope) != (
                second.subject,
                second.kind,
                second.scope,
            ):
                raise MemoryConflictError(
                    "supersession requires the same subject, kind, and scope"
                )
            old_time = first.valid_from or first.observed_at
            new_time = second.valid_from or second.observed_at
            if old_time is not None and new_time is not None and new_time < old_time:
                raise MemoryConflictError(
                    "supersession cannot move evidence backward in event time"
                )
            if new_record.id == old_id:
                raise MemoryConflictError("a memory cannot supersede itself")
            try:
                self._insert_row(new_record)
                self._connection.execute(
                    "UPDATE memories SET lifecycle = ? WHERE id = ?",
                    (LifecycleStatus.SUPERSEDED.value, old_id),
                )
                edge = MemoryRelation(new_record.id, old_id, "supersedes")
                self._insert_relation(edge)
            except sqlite3.IntegrityError as exc:
                raise MemoryConflictError("duplicate memory or relation") from exc
        return replace(new_record, relations=(edge,))

    def add_relation(self, relation: MemoryRelation) -> None:
        if not isinstance(relation, MemoryRelation):
            raise TypeError("relation must be a MemoryRelation")
        if relation.kind == "supersedes":
            raise MemoryConflictError("use supersede for lifecycle-linked relations")
        with self._connection:
            for memory_id in (relation.source_id, relation.target_id):
                if self.get(memory_id) is None:
                    raise MemoryNotFoundError(memory_id)
            try:
                self._insert_relation(relation)
            except sqlite3.IntegrityError as exc:
                raise MemoryConflictError("relation already exists") from exc

    def _insert_relation(self, relation: MemoryRelation) -> None:
        self._connection.execute(
            "INSERT INTO relations (source_id,target_id,kind) VALUES (?,?,?)",
            (relation.source_id, relation.target_id, relation.kind),
        )

    def _decode(self, row: sqlite3.Row) -> MemoryRecord:
        try:
            edges = self._connection.execute(
                "SELECT source_id,target_id,kind FROM relations WHERE source_id=? "
                "ORDER BY kind,target_id",
                (row["id"],),
            ).fetchall()
            candidate = MemoryCandidate(
                memory_class=MemoryClass(row["memory_class"]),
                kind=row["kind"],
                subject=row["subject"],
                content=row["content"],
                provenance=MemoryProvenance(
                    row["source_type"], row["source_id"], row["actor"]
                ),
                epistemic=EpistemicStatus(row["epistemic"]),
                acquisition=AcquisitionMode(row["acquisition"]),
                scope=MemoryScope(ScopeKind(row["scope_kind"]), row["scope_id"]),
                retention=Retention(row["retention"]),
                observed_at=_read_stamp(row["observed_at"]),
                valid_from=_read_stamp(row["valid_from"]),
                valid_until=_read_stamp(row["valid_until"]),
                source_reference=row["source_reference"],
                artifact_reference=row["artifact_reference"],
            )
            recorded_at = _read_stamp(row["recorded_at"])
            if recorded_at is None:
                raise ValueError("recorded_at missing")
            return MemoryRecord(
                id=row["id"],
                candidate=candidate,
                recorded_at=recorded_at,
                lifecycle=LifecycleStatus(row["lifecycle"]),
                relations=tuple(MemoryRelation(*edge) for edge in edges),
            )
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            raise MemoryDataError(f"malformed memory record: {row['id']}") from exc
