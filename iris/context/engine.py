"""Request-scoped context construction from explicit evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from iris.context.contracts import ContextSelectionPolicy
from iris.context.models import (
    ContextBudget,
    ContextCandidate,
    ContextSnapshot,
    ContextUncertainty,
    EvidenceSource,
    Relevance,
    ResolutionStatus,
    UncertaintyReason,
)
from iris.context.selection import (
    ContextSelection,
    DeterministicContextSelection,
    DuplicateContextCandidateError,
)
from iris.memory.models import identifier, utc_time


class ContextPolicyContractError(ValueError):
    """A selection policy produced data outside the supplied evidence/budget."""


class ContextEngine:
    """Build one ephemeral snapshot, without discovering or persisting data."""

    def __init__(self, policy: ContextSelectionPolicy | None = None) -> None:
        self._policy = policy if policy is not None else DeterministicContextSelection()

    def build(
        self,
        *,
        request_id: str,
        candidates: tuple[ContextCandidate, ...],
        budget: ContextBudget,
        uncertainties: tuple[ContextUncertainty, ...] = (),
        created_at: datetime | None = None,
    ) -> ContextSnapshot:
        identifier(request_id, "request_id")
        instant = (
            datetime.now(UTC)
            if created_at is None
            else utc_time(created_at, "created_at")
        )
        if not isinstance(candidates, tuple) or any(
            not isinstance(candidate, ContextCandidate) for candidate in candidates
        ):
            raise TypeError("candidates must be a tuple of ContextCandidate")
        if not isinstance(budget, ContextBudget):
            raise TypeError("budget must be ContextBudget")
        if not isinstance(uncertainties, tuple) or any(
            not isinstance(uncertainty, ContextUncertainty)
            for uncertainty in uncertainties
        ):
            raise TypeError("uncertainties must be a tuple of ContextUncertainty")
        for candidate in candidates:
            if (
                candidate.evidence.source is EvidenceSource.REQUEST
                and candidate.evidence.reference != request_id
            ):
                raise ValueError("request evidence must reference the current request")
            if candidate.observed_at is not None and candidate.observed_at > instant:
                raise ValueError(
                    "context observation cannot postdate snapshot creation"
                )

        by_id: dict[str, ContextCandidate] = {}
        for candidate in candidates:
            previous = by_id.get(candidate.candidate_id)
            if previous is not None and previous != candidate:
                raise DuplicateContextCandidateError(
                    f"candidate ID has incompatible evidence: {candidate.candidate_id}"
                )
            by_id[candidate.candidate_id] = candidate

        for uncertainty in uncertainties:
            if any(
                candidate_id not in by_id for candidate_id in uncertainty.candidate_ids
            ):
                raise ValueError("uncertainty references an unknown candidate")

        selection = self._policy.select(candidates, budget)
        if not isinstance(selection, ContextSelection):
            raise ContextPolicyContractError("policy must return ContextSelection")
        if len(selection.items) > budget.max_items:
            raise ContextPolicyContractError("policy exceeded context budget")
        for item in selection.items:
            matched = by_id.get(item.candidate_id)
            if matched is None or not matched.eligible or item != matched.to_item():
                raise ContextPolicyContractError(
                    "policy selected evidence not supplied or eligible"
                )
        if any(
            candidate_id not in by_id for candidate_id in selection.budget_excluded_ids
        ):
            raise ContextPolicyContractError(
                "policy reported an unknown excluded candidate"
            )
        for conflict in selection.conflicts:
            for candidate_id, evidence in zip(
                conflict.candidate_ids, conflict.evidence, strict=True
            ):
                matched = by_id.get(candidate_id)
                if (
                    matched is None
                    or not matched.eligible
                    or (matched.kind, matched.key, matched.scope)
                    != (conflict.kind, conflict.key, conflict.scope)
                    or matched.evidence != evidence
                ):
                    raise ContextPolicyContractError(
                        "policy reported an invalid conflict participant"
                    )

        known: list[ContextUncertainty] = list(uncertainties)
        for candidate_id in selection.budget_excluded_ids:
            candidate = by_id[candidate_id]
            if candidate.relevance in (Relevance.REQUIRED, Relevance.HIGH):
                known.append(
                    ContextUncertainty(
                        kind=candidate.kind,
                        key=candidate.key,
                        scope=candidate.scope,
                        reason=UncertaintyReason.BUDGET_EXCLUDED,
                        candidate_ids=(candidate_id,),
                    )
                )
        if selection.conflicts:
            status = ResolutionStatus.CONFLICTED
        elif any(item.reason is UncertaintyReason.MULTIPLE_PLAUSIBLE for item in known):
            status = ResolutionStatus.AMBIGUOUS
        elif known:
            status = ResolutionStatus.PARTIAL
        else:
            status = ResolutionStatus.RESOLVED
        return ContextSnapshot(
            snapshot_id=uuid4().hex,
            request_id=request_id,
            created_at=instant,
            budget=budget,
            items=selection.items,
            status=status,
            uncertainties=tuple(known),
            conflicts=selection.conflicts,
            budget_excluded_ids=selection.budget_excluded_ids,
        )
