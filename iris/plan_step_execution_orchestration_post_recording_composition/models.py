"""Immutable WP057 lineage plus one optional exact successor decision."""

from copy import copy
from dataclasses import dataclass, fields

from iris.context import ContextSnapshot
from iris.orchestrator import (
    HandlerAvailability,
    HandlingNeed,
    OrchestrationDecision,
    OrchestrationTarget,
    validate_orchestration_decision_current,
)
from iris.plan_handling import StepHandlingPreparationStatus
from iris.plan_step_execution_context_materialization_post_recording_composition import (
    PlanStepExecutionContextMaterializationPostRecordingCompositionResult,
)
from iris.plan_step_execution_orchestration_post_recording_composition.errors import (
    PlanStepExecutionOrchestrationPostRecordingCompositionInvariantError,
)
from iris.work_identity import WorkSubject


def validate_successor_decision(
    decision: OrchestrationDecision,
    subject: WorkSubject,
    context: ContextSnapshot,
    need: HandlingNeed,
    availability: HandlerAvailability | None = None,
) -> None:
    """Recheck canonical decision shape and exact lineage without repairing it."""

    invariant = PlanStepExecutionOrchestrationPostRecordingCompositionInvariantError
    if not isinstance(decision, OrchestrationDecision):
        raise invariant("WP017 must return a canonical OrchestrationDecision")
    try:
        checked = copy(decision)
        OrchestrationDecision.__post_init__(checked)
        for field in fields(OrchestrationDecision):
            original = getattr(decision, field.name)
            canonical = getattr(checked, field.name)
            if (
                type(original) is not type(canonical)
                or original != canonical
                or (
                    field.name == "created_at"
                    and original.isoformat() != canonical.isoformat()
                )
            ):
                raise ValueError("decision requires canonical normalization")
        validate_orchestration_decision_current(decision, subject, context)
    except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
        raise invariant("WP017 returned a noncanonical or foreign decision") from exc
    if (
        decision.created_at < context.created_at
        or decision.need_ids != (need.need_id,)
        or (decision.requirement is not None and decision.requirement is not need)
        or decision.context_references
        or decision.request_id is not None
    ):
        raise invariant("WP017 decision contradicts the exact prepared successor")
    if decision.target in {
        OrchestrationTarget.SYSTEM,
        OrchestrationTarget.MEMORY,
        OrchestrationTarget.CAPABILITY,
        OrchestrationTarget.INTELLIGENCE,
    }:
        if decision.requirement is not need:
            raise invariant("operational decision must select the exact prepared need")
        if availability is not None and not availability.supports(need):
            raise invariant("WP017 selected an unavailable handler")


@dataclass(frozen=True, slots=True)
class PlanStepExecutionOrchestrationPostRecordingCompositionResult(
    PlanStepExecutionContextMaterializationPostRecordingCompositionResult
):
    """Preserve WP057 and append only the optional WP017 decision."""

    post_recording_execution_orchestration_decision: OrchestrationDecision | None

    def __post_init__(self) -> None:
        PlanStepExecutionContextMaterializationPostRecordingCompositionResult.__post_init__(
            self
        )
        invariant = PlanStepExecutionOrchestrationPostRecordingCompositionInvariantError
        subject = self.post_recording_execution_work_subject
        context = self.post_recording_execution_context_snapshot
        preparation = self.post_recording_execution_handling_preparation
        decision = self.post_recording_execution_orchestration_decision
        prepared = (
            subject is not None
            and preparation is not None
            and preparation.status is StepHandlingPreparationStatus.PREPARED
        )
        if prepared != (decision is not None):
            raise invariant("successor decision must exist exactly for PREPARED work")
        if not prepared:
            return
        assert subject is not None and context is not None and preparation is not None
        assert decision is not None
        need = preparation.handling_need
        if not isinstance(need, HandlingNeed) or need.blockers:
            raise invariant("PREPARED successor must preserve its unblocked need")
        validate_successor_decision(decision, subject, context, need)

    def to_data(self) -> dict[str, object]:
        """Append the canonical WP017 trace to inherited serialization."""

        data = PlanStepExecutionContextMaterializationPostRecordingCompositionResult.to_data(
            self
        )
        data["post_recording_execution_orchestration_decision"] = (
            None
            if self.post_recording_execution_orchestration_decision is None
            else self.post_recording_execution_orchestration_decision.to_trace()
        )
        return data
