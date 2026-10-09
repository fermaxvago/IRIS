"""Immutable WP053 lineage plus one optional exact Step C advancement."""

from dataclasses import dataclass

from iris.plan_run_advancement import PlanRunProgressAdvanceResult
from iris.plan_step_execution_progress_advancement_post_recording_composition.errors import (
    PlanStepExecutionProgressAdvancementPostRecordingCompositionInvariantError,
)
from iris.plan_step_execution_progress_advancement_post_recording_composition.validation import (
    validate_advancement,
)
from iris.plan_step_execution_progress_update_post_recording_composition import (
    PlanStepExecutionProgressUpdatePostRecordingCompositionResult,
)


@dataclass(frozen=True, slots=True)
class PlanStepExecutionProgressAdvancementPostRecordingCompositionResult(
    PlanStepExecutionProgressUpdatePostRecordingCompositionResult
):
    """Preserve WP053 and append the optional exact WP023 artifact."""

    post_recording_execution_advancement_result: PlanRunProgressAdvanceResult | None

    def __post_init__(self) -> None:
        PlanStepExecutionProgressUpdatePostRecordingCompositionResult.__post_init__(
            self
        )
        advancement = self.post_recording_execution_advancement_result
        update = self.post_recording_execution_progress_update
        if advancement is not None and not isinstance(
            advancement, PlanRunProgressAdvanceResult
        ):
            raise TypeError(
                "post_recording_execution_advancement_result must be a "
                "PlanRunProgressAdvanceResult or None"
            )
        if (update is None) != (advancement is None):
            raise PlanStepExecutionProgressAdvancementPostRecordingCompositionInvariantError(
                "Step C update and advancement must either both exist or both be absent"
            )
        if update is not None and advancement is not None:
            recording = self.post_recording_execution_recording_result
            if recording is None:
                raise PlanStepExecutionProgressAdvancementPostRecordingCompositionInvariantError(
                    "Step C advancement requires its exact recording"
                )
            validate_advancement(
                recording.recorded_run.plan_id,
                recording.recorded_run,
                update,
                advancement,
            )

    def to_data(self) -> dict[str, object]:
        """Append the canonical WP023 representation to inherited WP053 data."""

        data = PlanStepExecutionProgressUpdatePostRecordingCompositionResult.to_data(
            self
        )
        data["post_recording_execution_advancement_result"] = (
            None
            if self.post_recording_execution_advancement_result is None
            else self.post_recording_execution_advancement_result.to_data()
        )
        return data
