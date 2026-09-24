"""Pure, bounded selection of explicit contextual evidence."""

from __future__ import annotations

from dataclasses import dataclass

from iris.context.models import (
    ContextBudget,
    ContextCandidate,
    ContextConflict,
    ContextItem,
    Freshness,
    Relevance,
)

_RELEVANCE = {
    Relevance.REQUIRED: 0,
    Relevance.HIGH: 1,
    Relevance.NORMAL: 2,
    Relevance.LOW: 3,
}
_FRESHNESS = {
    Freshness.CURRENT: 0,
    Freshness.RECENT: 1,
    Freshness.STALE: 2,
    Freshness.UNKNOWN: 3,
}


class DuplicateContextCandidateError(ValueError):
    """The same candidate identifier describes incompatible evidence."""


def _priority(candidate: ContextCandidate) -> tuple[int, int]:
    return _RELEVANCE[candidate.relevance], _FRESHNESS[candidate.freshness]


def _group_key(candidate: ContextCandidate) -> tuple[str, str, str, str]:
    return (
        candidate.scope.kind.value,
        candidate.scope.identifier or "",
        candidate.kind,
        candidate.key,
    )


@dataclass(frozen=True, slots=True)
class ContextSelection:
    """Policy output, distinct from the request-scoped snapshot."""

    items: tuple[ContextItem, ...]
    conflicts: tuple[ContextConflict, ...]
    budget_excluded_ids: tuple[str, ...]


class DeterministicContextSelection:
    """Choose relevance, then freshness, then a stable scoped-key/ID tie.

    Different highest-priority values for one scoped key create a conflict;
    they are not silently resolved by insertion order or observation time.
    Lower-priority alternatives do not override better evidence. No inference,
    authorization or knowledge about provider model windows occurs here.
    """

    def select(
        self,
        candidates: tuple[ContextCandidate, ...],
        budget: ContextBudget,
    ) -> ContextSelection:
        if not isinstance(candidates, tuple) or any(
            not isinstance(candidate, ContextCandidate) for candidate in candidates
        ):
            raise TypeError("candidates must be a tuple of ContextCandidate")
        if not isinstance(budget, ContextBudget):
            raise TypeError("budget must be ContextBudget")

        by_id: dict[str, ContextCandidate] = {}
        for candidate in candidates:
            previous = by_id.get(candidate.candidate_id)
            if previous is not None and previous != candidate:
                raise DuplicateContextCandidateError(
                    f"candidate ID has incompatible evidence: {candidate.candidate_id}"
                )
            by_id[candidate.candidate_id] = candidate

        groups: dict[tuple[str, str, str, str], list[ContextCandidate]] = {}
        for candidate in by_id.values():
            if candidate.eligible:
                groups.setdefault(_group_key(candidate), []).append(candidate)

        contenders: list[ContextCandidate] = []
        conflicts: list[ContextConflict] = []
        for group_key in sorted(groups):
            group = groups[group_key]
            best_priority = min(_priority(candidate) for candidate in group)
            top = sorted(
                (
                    candidate
                    for candidate in group
                    if _priority(candidate) == best_priority
                ),
                key=lambda candidate: candidate.candidate_id,
            )
            canonical = top[0]
            if any(
                type(candidate.value) is not type(canonical.value)
                or candidate.value != canonical.value
                for candidate in top[1:]
            ):
                conflicts.append(
                    ContextConflict(
                        kind=canonical.kind,
                        key=canonical.key,
                        scope=canonical.scope,
                        candidate_ids=tuple(
                            candidate.candidate_id for candidate in top
                        ),
                        evidence=tuple(candidate.evidence for candidate in top),
                    )
                )
            else:
                contenders.append(canonical)

        contenders.sort(
            key=lambda candidate: (
                *_priority(candidate),
                *_group_key(candidate),
                candidate.candidate_id,
            )
        )
        selected = contenders[: budget.max_items]
        excluded = contenders[budget.max_items :]
        return ContextSelection(
            items=tuple(candidate.to_item() for candidate in selected),
            conflicts=tuple(conflicts),
            budget_excluded_ids=tuple(candidate.candidate_id for candidate in excluded),
        )
