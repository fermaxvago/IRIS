"""Immutable output of one selected PlanStep Context materialization pass."""

from dataclasses import dataclass

from iris.context import ContextSnapshot
from iris.outcome_assessment import StepOutcomeAssessment
from iris.plan_control import ControlDecision, ControlDecisionKind
from iris.plan_handling import StepHandlingPreparationResult
from iris.plan_run_advancement import PlanRunProgressAdvanceResult
from iris.plan_runs import StepProgressUpdate
from iris.plan_step_context_materialization.errors import (
    PlanStepContextMaterializationInvariantError,
)
from iris.step_progress_transition import StepProgressTransitionDecision
from iris.work_identity import PlanStepWorkReference, WorkSubject, WorkSubjectKind


@dataclass(frozen=True, slots=True)
class PlanStepContextMaterializationResult:
    """Preserve WP032 artifacts and the optional exact WP016 snapshot."""

    assessment: StepOutcomeAssessment
    transition_decision: StepProgressTransitionDecision
    progress_update: StepProgressUpdate | None
    advancement_result: PlanRunProgressAdvanceResult | None
    handling_preparation: StepHandlingPreparationResult | None
    work_subject: WorkSubject | None
    context_snapshot: ContextSnapshot | None

    def __post_init__(self) -> None:
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

        self._validate_common_lineage()
        self._validate_optional_shape()

    def _validate_common_lineage(self) -> None:
        decision = self.transition_decision
        if (
            self.assessment.plan_id != decision.plan_id
            or self.assessment.run_id != decision.run_id
            or self.assessment.run_revision != decision.observed_revision
            or self.assessment.step_id != decision.step_id
            or self.assessment.assessment_id != decision.assessment_id
        ):
            raise PlanStepContextMaterializationInvariantError(
                "assessment and transition decision lineage must match exactly"
            )

        update = self.progress_update
        advancement = self.advancement_result
        if (update is None) != (advancement is None):
            raise PlanStepContextMaterializationInvariantError(
                "progress update and advancement result must both exist or be absent"
            )
        if update is not None and advancement is not None:
            if (
                update.run_id != decision.run_id
                or update.expected_revision != decision.observed_revision
                or update.step_id != decision.step_id
                or advancement.source_update_id != update.update_id
                or advancement.source_revision != update.expected_revision
            ):
                raise PlanStepContextMaterializationInvariantError(
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
            raise PlanStepContextMaterializationInvariantError(
                "handling preparation must exist if and only if fresh control "
                "selected a step"
            )
        if selected != (self.work_subject is not None):
            raise PlanStepContextMaterializationInvariantError(
                "work subject must exist if and only if fresh control selected a step"
            )
        if (self.work_subject is None) != (self.context_snapshot is None):
            raise PlanStepContextMaterializationInvariantError(
                "context snapshot must exist if and only if work subject exists"
            )
        if not selected:
            return

        assert advancement is not None
        assert control is not None
        assert self.handling_preparation is not None
        assert self.work_subject is not None
        assert self.context_snapshot is not None
        selected_step_id = control.selected_step_id
        if selected_step_id is None:
            raise PlanStepContextMaterializationInvariantError(
                "selected control must identify one PlanStep"
            )
        if (
            self.handling_preparation.plan_id != self.assessment.plan_id
            or self.handling_preparation.run_id != advancement.updated_run.run_id
            or self.handling_preparation.observed_revision
            != advancement.updated_run.revision
            or self.handling_preparation.step_id != selected_step_id
        ):
            raise PlanStepContextMaterializationInvariantError(
                "handling preparation must match the exact fresh selection"
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
            raise PlanStepContextMaterializationInvariantError(
                "work subject must identify the exact selected PlanStep without origin"
            )
        if (
            self.context_snapshot.subject is not subject
            or self.context_snapshot.subject_id != subject.subject_id
        ):
            raise PlanStepContextMaterializationInvariantError(
                "context snapshot must preserve the exact WorkSubject owner"
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
        }
