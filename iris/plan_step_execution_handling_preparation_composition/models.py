"""Immutable output of one bounded post-recording handling preparation."""

from dataclasses import dataclass

from iris.plan_control import ControlDecisionKind
from iris.plan_handling import StepHandlingPreparationResult
from iris.plan_step_execution_handling_preparation_composition.errors import (
    PlanStepExecutionHandlingPreparationCompositionInvariantError,
)
from iris.plan_step_execution_progress_advancement_composition import (
    PlanStepExecutionProgressAdvancementCompositionResult,
)


@dataclass(frozen=True, slots=True)
class PlanStepExecutionHandlingPreparationCompositionResult(
    PlanStepExecutionProgressAdvancementCompositionResult
):
    """Preserve WP042 artifacts and append the optional exact WP014 result."""

    post_recording_handling_preparation: StepHandlingPreparationResult | None

    def __post_init__(self) -> None:
        PlanStepExecutionProgressAdvancementCompositionResult.__post_init__(self)
        preparation = self.post_recording_handling_preparation
        if preparation is not None and not isinstance(
            preparation, StepHandlingPreparationResult
        ):
            raise TypeError(
                "post_recording_handling_preparation must be a "
                "StepHandlingPreparationResult or None"
            )

        advancement = self.post_recording_advancement_result
        selected = (
            advancement is not None
            and advancement.control_decision.kind is ControlDecisionKind.STEP_SELECTED
        )
        if selected != (preparation is not None):
            raise PlanStepExecutionHandlingPreparationCompositionInvariantError(
                "post-recording handling preparation must exist if and only if "
                "fresh post-recording control selected a step"
            )
        if preparation is None:
            return
        if preparation is self.handling_preparation:
            raise PlanStepExecutionHandlingPreparationCompositionInvariantError(
                "inherited and post-recording handling preparations must remain "
                "distinct artifacts"
            )

        assert advancement is not None
        successor = advancement.updated_run
        control = advancement.control_decision
        if (
            preparation.plan_id != successor.plan_id
            or preparation.plan_id != control.plan_id
            or preparation.run_id != successor.run_id
            or preparation.run_id != control.run_id
            or preparation.observed_revision != successor.revision
            or preparation.observed_revision != control.observed_revision
            or preparation.step_id != control.selected_step_id
        ):
            raise PlanStepExecutionHandlingPreparationCompositionInvariantError(
                "post-recording handling preparation contradicts the exact fresh "
                "selection"
            )

    def to_data(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible representation."""

        data = PlanStepExecutionProgressAdvancementCompositionResult.to_data(self)
        data["post_recording_handling_preparation"] = (
            None
            if self.post_recording_handling_preparation is None
            else self.post_recording_handling_preparation.to_data()
        )
        return data
