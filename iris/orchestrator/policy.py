"""Deterministic single-step orchestration policy."""

from iris.orchestrator.models import (
    ContextBlocker,
    ContextBlockerKind,
    HandlingKind,
    OrchestrationInput,
    OrchestrationReason,
    OrchestrationSelection,
    OrchestrationTarget,
)

_BLOCKER_ORDER = {
    ContextBlockerKind.CONFLICTED: 0,
    ContextBlockerKind.AMBIGUOUS: 1,
    ContextBlockerKind.MISSING: 2,
}


def _blocker_key(item: ContextBlocker) -> tuple[object, ...]:
    return (
        _BLOCKER_ORDER[item.issue],
        item.scope.kind.value,
        item.scope.identifier or "",
        item.kind,
        item.key,
        item.candidate_ids,
    )


_TARGET_REASON = {
    HandlingKind.SYSTEM: (
        OrchestrationTarget.SYSTEM,
        OrchestrationReason.DETERMINISTIC_SYSTEM_REQUEST,
    ),
    HandlingKind.MEMORY: (
        OrchestrationTarget.MEMORY,
        OrchestrationReason.EXPLICIT_MEMORY_OPERATION,
    ),
    HandlingKind.CAPABILITY: (
        OrchestrationTarget.CAPABILITY,
        OrchestrationReason.EXPLICIT_CAPABILITY_REQUEST,
    ),
    HandlingKind.INTELLIGENCE: (
        OrchestrationTarget.INTELLIGENCE,
        OrchestrationReason.INTELLIGENCE_REQUIRED,
    ),
}


class DeterministicOrchestrationPolicy:
    """Choose one handler class from explicit needs and availability.

    Relevant context blockers take precedence. More than one need is a
    composite request that this single-step loop deliberately cannot execute.
    """

    def select(self, orchestration_input: OrchestrationInput) -> OrchestrationSelection:
        if not isinstance(orchestration_input, OrchestrationInput):
            raise TypeError("orchestration_input must be an OrchestrationInput")
        needs = tuple(sorted(orchestration_input.needs, key=lambda item: item.need_id))
        need_ids = tuple(item.need_id for item in needs)
        blockers = tuple(
            sorted(
                {blocker for need in needs for blocker in need.blockers},
                key=_blocker_key,
            )
        )
        if blockers:
            lead = blockers[0]
            reason = {
                ContextBlockerKind.CONFLICTED: OrchestrationReason.CONTEXT_CONFLICTED,
                ContextBlockerKind.AMBIGUOUS: OrchestrationReason.CONTEXT_AMBIGUOUS,
                ContextBlockerKind.MISSING: (
                    OrchestrationReason.MISSING_REQUIRED_INFORMATION
                ),
            }[lead.issue]
            return OrchestrationSelection(
                target=OrchestrationTarget.CLARIFY,
                reason=reason,
                need_ids=need_ids,
                requirement=needs[0] if len(needs) == 1 else None,
                context_references=blockers,
            )
        if len(needs) > 1:
            return OrchestrationSelection(
                target=OrchestrationTarget.UNSATISFIED,
                reason=OrchestrationReason.COMPOSITE_HANDLING_REQUIRED,
                need_ids=need_ids,
            )
        if not needs:
            return OrchestrationSelection(
                target=OrchestrationTarget.UNSATISFIED,
                reason=OrchestrationReason.NO_ADMISSIBLE_HANDLER,
                need_ids=(),
            )

        need = needs[0]
        if need.kind is HandlingKind.CLARIFICATION:
            raise ValueError("clarification need must include a validated blocker")
        if not orchestration_input.availability.supports(need):
            return OrchestrationSelection(
                target=OrchestrationTarget.UNSATISFIED,
                reason=OrchestrationReason.NO_ADMISSIBLE_HANDLER,
                need_ids=need_ids,
                requirement=need,
            )
        target, reason = _TARGET_REASON[need.kind]
        return OrchestrationSelection(
            target=target,
            reason=reason,
            need_ids=need_ids,
            requirement=need,
        )
