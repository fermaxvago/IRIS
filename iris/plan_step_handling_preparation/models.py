"""Immutable output of one post-advancement handling-preparation pass."""

from dataclasses import dataclass

from iris.outcome_assessment import StepOutcomeAssessment
from iris.plan_control import ControlDecision, ControlDecisionKind
from iris.plan_handling import StepHandlingPreparationResult
from iris.plan_run_advancement import PlanRunProgressAdvanceResult
from iris.plan_runs import StepProgressUpdate
from iris.plan_step_handling_preparation.errors import (
    PlanStepHandlingPreparationInvariantError,
)
from iris.step_progress_transition import StepProgressTransitionDecision


@dataclass(frozen=True, slots=True)
class PlanStepHandlingPreparationResult:
    """Preserve WP030 artifacts and the optional exact WP014 result."""

    assessment: StepOutcomeAssessment
    transition_decision: StepProgressTransitionDecision
    progress_update: StepProgressUpdate | None
    advancement_result: PlanRunProgressAdvanceResult | None
    handling_preparation: StepHandlingPreparationResult | None

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
            raise PlanStepHandlingPreparationInvariantError(
                "assessment and transition decision lineage must match exactly"
            )

        update = self.progress_update
        advancement = self.advancement_result
        if (update is None) != (advancement is None):
            raise PlanStepHandlingPreparationInvariantError(
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
                raise PlanStepHandlingPreparationInvariantError(
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
            raise PlanStepHandlingPreparationInvariantError(
                "handling preparation must exist if and only if fresh control "
                "selected a step"
            )
        if self.handling_preparation is None:
            return

        assert advancement is not None
        assert control is not None
        preparation = self.handling_preparation
        if (
            preparation.plan_id != self.assessment.plan_id
            or preparation.run_id != advancement.updated_run.run_id
            or preparation.observed_revision != advancement.updated_run.revision
            or preparation.step_id != control.selected_step_id
        ):
            raise PlanStepHandlingPreparationInvariantError(
                "handling preparation must match the exact fresh selection"
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
        }
