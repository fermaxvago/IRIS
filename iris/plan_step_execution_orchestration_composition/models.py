"""Immutable output of bounded post-recording PlanStep orchestration."""

from dataclasses import dataclass

from iris.context import ContextSnapshot
from iris.orchestrator import (
    HandlingNeed,
    OrchestrationDecision,
    validate_orchestration_decision_current,
)
from iris.plan_handling import StepHandlingPreparationStatus
from iris.plan_step_execution_context_materialization_composition import (
    PlanStepExecutionContextMaterializationCompositionResult,
)
from iris.plan_step_execution_orchestration_composition.errors import (
    PlanStepExecutionOrchestrationCompositionInvariantError,
)
from iris.work_identity import WorkSubject


@dataclass(frozen=True, slots=True)
class PlanStepExecutionOrchestrationCompositionResult(
    PlanStepExecutionContextMaterializationCompositionResult
):
    """Preserve WP045 artifacts and append the optional exact WP017 decision."""

    post_recording_orchestration_decision: OrchestrationDecision | None

    def __post_init__(self) -> None:
        PlanStepExecutionContextMaterializationCompositionResult.__post_init__(self)
        decision = self.post_recording_orchestration_decision
        if decision is not None and not isinstance(decision, OrchestrationDecision):
            raise TypeError(
                "post_recording_orchestration_decision must be an "
                "OrchestrationDecision or None"
            )

        subject = self.post_recording_work_subject
        context = self.post_recording_context_snapshot
        preparation = self.post_recording_handling_preparation
        if subject is None:
            if decision is not None:
                raise PlanStepExecutionOrchestrationCompositionInvariantError(
                    "post-recording orchestration requires exact selected work"
                )
            return

        if context is None or preparation is None:
            raise PlanStepExecutionOrchestrationCompositionInvariantError(
                "selected post-recording work requires Context and preparation"
            )
        prepared = preparation.status is StepHandlingPreparationStatus.PREPARED
        if prepared != (decision is not None):
            raise PlanStepExecutionOrchestrationCompositionInvariantError(
                "post-recording orchestration decision must exist if and only if "
                "the exact Step C handling preparation is PREPARED"
            )
        if not prepared:
            return

        need = preparation.handling_need
        if not isinstance(need, HandlingNeed) or need.blockers:
            raise PlanStepExecutionOrchestrationCompositionInvariantError(
                "PREPARED Step C handling must preserve its canonical unmodified need"
            )
        assert decision is not None
        self._validate_orchestration_decision(decision, subject, context, need)

    @staticmethod
    def _validate_orchestration_decision(
        decision: OrchestrationDecision,
        subject: WorkSubject,
        context: ContextSnapshot,
        need: HandlingNeed,
    ) -> None:
        try:
            validate_orchestration_decision_current(decision, subject, context)
        except (TypeError, ValueError) as exc:
            raise PlanStepExecutionOrchestrationCompositionInvariantError(
                "post-recording decision is not current for exact Step C artifacts"
            ) from exc
        if decision.created_at < context.created_at:
            raise PlanStepExecutionOrchestrationCompositionInvariantError(
                "post-recording decision cannot predate its exact ContextSnapshot"
            )
        if decision.need_ids != (need.need_id,):
            raise PlanStepExecutionOrchestrationCompositionInvariantError(
                "post-recording decision must account for the exact prepared need"
            )
        if decision.requirement is not None and decision.requirement is not need:
            raise PlanStepExecutionOrchestrationCompositionInvariantError(
                "post-recording decision selected a foreign handling requirement"
            )
        if any(
            reference not in need.blockers for reference in decision.context_references
        ):
            raise PlanStepExecutionOrchestrationCompositionInvariantError(
                "post-recording decision referenced an unsupplied Context blocker"
            )

    def to_data(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible representation."""

        data = PlanStepExecutionContextMaterializationCompositionResult.to_data(self)
        data["post_recording_orchestration_decision"] = (
            None
            if self.post_recording_orchestration_decision is None
            else self.post_recording_orchestration_decision.to_trace()
        )
        return data
