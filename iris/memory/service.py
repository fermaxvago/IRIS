"""Memory-domain operations; callers explicitly decide what to persist."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from iris.memory.contracts import MemoryStore
from iris.memory.errors import MemoryConflictError, MemoryNotFoundError
from iris.memory.models import (
    CurrentStatus,
    LifecycleStatus,
    MemoryCandidate,
    MemoryQuery,
    MemoryRecord,
    MemoryRelation,
    MemoryResult,
    MemoryScope,
    utc_time,
)


class MemoryService:
    """Persist evidence and preserve explicit lifecycle and history."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def store(self, candidate: MemoryCandidate) -> MemoryRecord:
        if not isinstance(candidate, MemoryCandidate):
            raise TypeError("candidate must be a MemoryCandidate")
        record = MemoryRecord(uuid4().hex, candidate, datetime.now(UTC))
        self._store.insert(record)
        return record

    def get(
        self, memory_id: str, *, include_history: bool = False
    ) -> MemoryRecord | None:
        """Direct lookup; historic/forgotten records require explicit opt-in."""
        record = self._store.get(memory_id)
        if record is not None and (
            include_history or record.lifecycle is LifecycleStatus.ACTIVE
        ):
            return record
        return None

    def query(self, filters: MemoryQuery) -> tuple[MemoryRecord, ...]:
        """Query exact filters; default query returns active records only."""
        return self._store.query(filters)

    def supersede(self, old_id: str, candidate: MemoryCandidate) -> MemoryRecord:
        if not isinstance(candidate, MemoryCandidate):
            raise TypeError("candidate must be a MemoryCandidate")
        record = MemoryRecord(uuid4().hex, candidate, datetime.now(UTC))
        return self._store.supersede(old_id, record)

    def retract(self, memory_id: str) -> MemoryRecord:
        return self._store.transition(memory_id, LifecycleStatus.RETRACTED)

    def forget(self, memory_id: str) -> MemoryRecord:
        """Hide a record from normal recall while retaining its evidence."""
        return self._store.transition(memory_id, LifecycleStatus.FORGOTTEN)

    def expire(self, memory_id: str, *, as_of: datetime) -> MemoryRecord:
        """Explicit expiration; retention alone never schedules deletion."""
        instant = utc_time(as_of, "as_of")
        record = self._store.get(memory_id)
        if record is None:
            raise MemoryNotFoundError(memory_id)
        if (
            record.candidate.valid_until is None
            or record.candidate.valid_until > instant
        ):
            raise MemoryConflictError("memory validity has not ended")
        return self._store.transition(memory_id, LifecycleStatus.EXPIRED)

    def relate(self, source_id: str, target_id: str, kind: str) -> MemoryRelation:
        relation = MemoryRelation(source_id, target_id, kind)
        self._store.add_relation(relation)
        return relation

    def current(
        self,
        *,
        subject: str,
        kind: str,
        scope: MemoryScope,
        as_of: datetime,
    ) -> MemoryResult:
        """Resolve current stored evidence from validity/observation time.

        The result is a view of recorded evidence, not proof of external truth.
        Unknown event time or conflicting records at the latest time are
        ambiguous. Recorded insertion time never decides current state.
        """
        instant = utc_time(as_of, "as_of")
        records = self.query(MemoryQuery(subject=subject, kind=kind, scope=scope))
        applicable = tuple(
            record
            for record in records
            if (
                record.candidate.valid_from is None
                or record.candidate.valid_from <= instant
            )
            and (
                record.candidate.valid_until is None
                or instant < record.candidate.valid_until
            )
            and (
                record.candidate.observed_at is None
                or record.candidate.observed_at <= instant
            )
        )
        if not applicable:
            return MemoryResult(CurrentStatus.NONE)

        def event_time(record: MemoryRecord) -> datetime | None:
            return record.candidate.valid_from or record.candidate.observed_at

        unknown = tuple(record for record in applicable if event_time(record) is None)
        if unknown:
            return MemoryResult(CurrentStatus.AMBIGUOUS, candidates=applicable)
        times = tuple(
            time for record in applicable if (time := event_time(record)) is not None
        )
        latest = max(times)
        winners = tuple(record for record in applicable if event_time(record) == latest)
        if len(winners) != 1:
            return MemoryResult(CurrentStatus.AMBIGUOUS, candidates=winners)
        return MemoryResult(CurrentStatus.FOUND, record=winners[0], candidates=winners)
