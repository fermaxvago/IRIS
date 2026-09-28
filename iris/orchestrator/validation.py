"""Pure currentness validation for subject-scoped orchestration decisions."""

from iris.context import ContextSnapshot
from iris.orchestrator.errors import (
    StaleOrchestrationDecisionError,
    SubjectContextMismatchError,
)
from iris.orchestrator.models import OrchestrationDecision
from iris.work_identity.models import WorkSubject


def validate_orchestration_decision_current(
    decision: OrchestrationDecision,
    subject: WorkSubject,
    context: ContextSnapshot,
) -> None:
    """Require one decision to match this subject and exact snapshot identity.

    This is structural validation only. It says nothing about current handler
    availability, authorization, safety, evidence truth, or external state.
    """

    if not isinstance(decision, OrchestrationDecision):
        raise TypeError("decision must be an OrchestrationDecision")
    if not isinstance(subject, WorkSubject):
        raise TypeError("subject must be a WorkSubject")
    if not isinstance(context, ContextSnapshot):
        raise TypeError("context must be a ContextSnapshot")
    if subject.subject_id != context.subject_id:
        raise SubjectContextMismatchError(
            "subject and context snapshot identities do not match"
        )
    if decision.subject_id != subject.subject_id:
        raise StaleOrchestrationDecisionError(
            "orchestration decision belongs to a different WorkSubject"
        )
    if decision.context_snapshot_id != context.snapshot_id:
        raise StaleOrchestrationDecisionError(
            "orchestration decision belongs to a different ContextSnapshot"
        )
