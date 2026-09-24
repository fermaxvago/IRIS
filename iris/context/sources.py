"""Explicit, read-only conversion from selected memory evidence to candidates."""

from __future__ import annotations

from typing import Protocol

from iris.context.models import (
    ContextCandidate,
    ContextEvidence,
    EvidenceSource,
    Freshness,
    Relevance,
)
from iris.memory.models import (
    LifecycleStatus,
    MemoryQuery,
    MemoryRecord,
    vocabulary,
)


class _MemoryReader(Protocol):
    def query(self, filters: MemoryQuery) -> tuple[MemoryRecord, ...]: ...


class MemoryContextSource:
    """Turn an exact caller-supplied memory query into lightweight evidence.

    This adapter does not discover queries, rank memory or write to storage.
    Historic records require an explicit opt-in at both query and source.
    """

    def __init__(self, memory: _MemoryReader) -> None:
        self._memory = memory

    def candidates(
        self,
        query: MemoryQuery,
        *,
        kind: str,
        key: str,
        relevance: Relevance,
        freshness: Freshness,
        include_content: bool = False,
        include_history: bool = False,
    ) -> tuple[ContextCandidate, ...]:
        if not isinstance(query, MemoryQuery):
            raise TypeError("query must be MemoryQuery")
        if query.subject is None or query.kind is None or query.scope is None:
            raise ValueError("memory context requires exact subject, kind and scope")
        vocabulary(kind, "context kind")
        vocabulary(key, "context key")
        if not isinstance(relevance, Relevance) or not isinstance(freshness, Freshness):
            raise TypeError("relevance and freshness must be domain categories")
        if not isinstance(include_content, bool) or not isinstance(
            include_history, bool
        ):
            raise TypeError("include_content and include_history must be bool")
        active_only = frozenset({LifecycleStatus.ACTIVE})
        if not include_history and query.statuses != active_only:
            raise ValueError(
                "historical memory retrieval requires include_history=True"
            )
        records = self._memory.query(query)
        if not isinstance(records, tuple) or any(
            not isinstance(record, MemoryRecord) for record in records
        ):
            raise TypeError("memory source must return a tuple of MemoryRecord")
        for record in records:
            if (
                record.candidate.subject != query.subject
                or record.candidate.kind != query.kind
                or record.candidate.scope != query.scope
            ):
                raise ValueError(
                    "memory source returned a record outside the exact query"
                )
        if not include_history:
            records = tuple(
                record
                for record in records
                if record.lifecycle is LifecycleStatus.ACTIVE
            )
        if not include_content and len(records) > 1:
            raise ValueError(
                "reference-only memory context requires a single matching record; "
                "refine the query or explicitly include content"
            )
        return tuple(
            ContextCandidate(
                candidate_id=f"memory:{record.id}:{kind}:{key}",
                kind=kind,
                key=key,
                value=record.candidate.content if include_content else record.id,
                evidence=ContextEvidence(
                    source=EvidenceSource.MEMORY,
                    reference=record.id,
                    epistemic=record.candidate.epistemic,
                ),
                scope=record.candidate.scope,
                relevance=relevance,
                freshness=freshness,
                observed_at=record.candidate.observed_at,
            )
            for record in records
        )
