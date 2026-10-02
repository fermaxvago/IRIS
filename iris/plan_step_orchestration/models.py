"""Immutable output of one bounded post-Context PlanStep orchestration pass."""

from dataclasses import dataclass

from iris.context import ContextSnapshot
from iris.orchestrator import (
    HandlingNeed,
    OrchestrationDecision,
    validate_orchestration_decision_current,
)
from iris.outcome_assessment import StepOutcomeAssessment
from iris.plan_control import ControlDecision, ControlDecisionKind
from iris.plan_handling import (
    StepHandlingPreparationResult,
    StepHandlingPreparationStatus,
)
from iris.plan_run_advancement import PlanRunProgressAdvanceResult
from iris.plan_runs import StepProgressUpdate
from iris.plan_step_orchestration.errors import PlanStepOrchestrationInvariantError
from iris.step_progress_transition import StepProgressTransitionDecision
from iris.work_identity import PlanStepWorkReference, WorkSubject, WorkSubjectKind


@dataclass(frozen=True, slots=True)
class PlanStepOrchestrationResult:
    """Preserve WP033 artifacts and the optional exact WP017 decision."""

    assessment: StepOutcomeAssessment
    transition_decision: StepProgressTransitionDecision
    progress_update: StepProgressUpdate | None
    advancement_result: PlanRunProgressAdvanceResult | None
    handling_preparation: StepHandlingPreparationResult | None
    work_subject: WorkSubject | None
    context_snapshot: ContextSnapshot | None
    orchestration_decision: OrchestrationDecision | None

    def __post_init__(self) -> None:
        self._validate_types()
        self._validate_common_lineage()
        self._validate_optional_shape()

    def _validate_types(self) -> None:
        if not isinstance(self.assessment, StepOutcomeAssessment):
            raise TypeError("assessment must be a StepOutcomeAssessment")
        if not isinstance(self.transition_decision, StepProgressTransitionDecision):
            raise TypeError(
                "transition_decision must be a StepProgressTransitionDecision"
            )
        if self.progress_update is not None and not isinstance(
            self.progress_update, StepProgressUpdate
        ):
            raise TypeError("progress_update must be a StepProgressUpdate or None")
        if self.advancement_result is not None and not isinstance(
            self.advancement_result, PlanRunProgressAdvanceResult
        ):
            raise TypeError(
                "advancement_result must be a PlanRunProgressAdvanceResult or None"
            )
        if self.handling_preparation is not None and not isinstance(
            self.handling_preparation, StepHandlingPreparationResult
        ):
            raise TypeError(
                "handling_preparation must be a StepHandlingPreparationResult or None"
            )
        if self.work_subject is not None and not isinstance(
            self.work_subject, WorkSubject
        ):
            raise TypeError("work_subject must be a WorkSubject or None")
        if self.context_snapshot is not None and not isinstance(
            self.context_snapshot, ContextSnapshot
        ):
            raise TypeError("context_snapshot must be a ContextSnapshot or None")
        if self.orchestration_decision is not None and not isinstance(
            self.orchestration_decision, OrchestrationDecision
        ):
            raise TypeError(
                "orchestration_decision must be an OrchestrationDecision or None"
            )

    def _validate_common_lineage(self) -> None:
        decision = self.transition_decision
        if (
            self.assessment.plan_id != decision.plan_id
            or self.assessment.run_id != decision.run_id
            or self.assessment.run_revision != decision.observed_revision
            or self.assessment.step_id != decision.step_id
            or self.assessment.assessment_id != decision.assessment_id
        ):
            raise PlanStepOrchestrationInvariantError(
                "assessment and transition decision lineage must match exactly"
            )

        update = self.progress_update
        advancement = self.advancement_result
        if (update is None) != (advancement is None):
            raise PlanStepOrchestrationInvariantError(
                "progress update and advancement result must both exist or be absent"
            )
        if (
            update is not None
            and advancement is not None
            and (
                update.run_id != decision.run_id
                or update.expected_revision != decision.observed_revision
                or update.step_id != decision.step_id
                or advancement.source_update_id != update.update_id
                or advancement.source_revision != update.expected_revision
            )
        ):
            raise PlanStepOrchestrationInvariantError(
                "progress update and advancement lineage must match exactly"
            )

    def _validate_optional_shape(self) -> None:
        advancement = self.advancement_result
        selected = False
        control: ControlDecision | None = None
        if advancement is not None:
            control = advancement.control_decision
            if not isinstance(control, ControlDecision):
                raise TypeError(
                    "advancement control_decision must be a ControlDecision"
                )
            selected = control.kind is ControlDecisionKind.STEP_SELECTED

        if selected != (self.handling_preparation is not None):
            raise PlanStepOrchestrationInvariantError(
                "handling preparation must exist if and only if fresh control "
                "selected a step"
            )
        if selected != (self.work_subject is not None):
            raise PlanStepOrchestrationInvariantError(
                "work subject must exist if and only if fresh control selected a step"
            )
        if selected != (self.context_snapshot is not None):
            raise PlanStepOrchestrationInvariantError(
                "context snapshot must exist if and only if fresh control selected a step"
            )
        if not selected:
            if self.orchestration_decision is not None:
                raise PlanStepOrchestrationInvariantError(
                    "orchestration decision cannot exist without selected work"
                )
            return

        assert advancement is not None
        assert control is not None
        assert self.handling_preparation is not None
        assert self.work_subject is not None
        assert self.context_snapshot is not None
        selected_step_id = control.selected_step_id
        if selected_step_id is None:
            raise PlanStepOrchestrationInvariantError(
                "selected control must identify one PlanStep"
            )
        if (
            self.handling_preparation.plan_id != self.assessment.plan_id
            or self.handling_preparation.run_id != advancement.updated_run.run_id
            or self.handling_preparation.observed_revision
            != advancement.updated_run.revision
            or self.handling_preparation.step_id != selected_step_id
        ):
            raise PlanStepOrchestrationInvariantError(
                "handling preparation must match the exact fresh selection"
            )
        if not isinstance(
            self.handling_preparation.status,
            StepHandlingPreparationStatus,
        ):
            raise TypeError(
                "handling preparation status must be a StepHandlingPreparationStatus"
            )
        subject = self.work_subject
        if (
            subject.kind is not WorkSubjectKind.PLAN_STEP
            or not isinstance(subject.reference, PlanStepWorkReference)
            or subject.reference.plan_id != self.assessment.plan_id
            or subject.reference.run_id != advancement.updated_run.run_id
            or subject.reference.step_id != selected_step_id
            or subject.origin is not None
        ):
            raise PlanStepOrchestrationInvariantError(
                "work subject must identify the exact selected PlanStep without origin"
            )
        context = self.context_snapshot
        if context.subject is not subject or context.subject_id != subject.subject_id:
            raise PlanStepOrchestrationInvariantError(
                "context snapshot must preserve the exact WorkSubject owner"
            )

        prepared = (
            self.handling_preparation.status is StepHandlingPreparationStatus.PREPARED
        )
        if prepared != (self.orchestration_decision is not None):
            raise PlanStepOrchestrationInvariantError(
                "orchestration decision must exist if and only if selected handling "
                "is PREPARED"
            )
        if not prepared:
            return

        need = self.handling_preparation.handling_need
        if not isinstance(need, HandlingNeed) or need.blockers:
            raise PlanStepOrchestrationInvariantError(
                "PREPARED PlanStep handling must contain its canonical unmodified need"
            )
        assert self.orchestration_decision is not None
        self._validate_orchestration_decision(
            self.orchestration_decision,
            subject,
            context,
            need,
        )

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
            raise PlanStepOrchestrationInvariantError(
                "orchestration decision is not current for the exact subject/context"
            ) from exc
        if decision.need_ids != (need.need_id,):
            raise PlanStepOrchestrationInvariantError(
                "orchestration decision must account for the exact prepared need"
            )
        if decision.requirement is not None and decision.requirement != need:
            raise PlanStepOrchestrationInvariantError(
                "orchestration decision selected a requirement outside the input"
            )
        if any(
            reference not in need.blockers for reference in decision.context_references
        ):
            raise PlanStepOrchestrationInvariantError(
                "orchestration decision referenced an unsupplied Context blocker"
            )

    def to_data(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible representation."""

        return {
            "assessment": self.assessment.to_data(),
            "transition_decision": self.transition_decision.to_data(),
            "progress_update": (
                None if self.progress_update is None else self.progress_update.to_data()
            ),
            "advancement_result": (
                None
                if self.advancement_result is None
                else self.advancement_result.to_data()
            ),
            "handling_preparation": (
                None
                if self.handling_preparation is None
                else self.handling_preparation.to_data()
            ),
            "work_subject": (
                None if self.work_subject is None else self.work_subject.to_data()
            ),
            "context_snapshot": (
                None
                if self.context_snapshot is None
                else self.context_snapshot.to_data()
            ),
            "orchestration_decision": (
                None
                if self.orchestration_decision is None
                else self.orchestration_decision.to_trace()
            ),
        }
