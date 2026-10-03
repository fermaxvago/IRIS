"""Immutable output of one bounded post-start recording composition."""

from dataclasses import dataclass

from iris.plan_step_execution_result_recording import (
    PlanStepExecutionResultRecordingResult,
)
from iris.plan_step_execution_result_recording_composition.errors import (
    PlanStepExecutionResultRecordingCompositionInvariantError,
)
from iris.plan_step_execution_start_composition import (
    PlanStepExecutionStartCompositionResult,
)


@dataclass(frozen=True, slots=True)
class PlanStepExecutionResultRecordingCompositionResult(
    PlanStepExecutionStartCompositionResult
):
    """Preserve WP037 artifacts and append the optional exact WP026 result."""

    execution_recording_result: PlanStepExecutionResultRecordingResult | None

    def __post_init__(self) -> None:
        PlanStepExecutionStartCompositionResult.__post_init__(self)
        if self.execution_recording_result is not None and not isinstance(
            self.execution_recording_result,
            PlanStepExecutionResultRecordingResult,
        ):
            raise TypeError(
                "execution_recording_result must be a "
                "PlanStepExecutionResultRecordingResult or None"
            )
        if (self.execution_start_result is None) != (
            self.execution_recording_result is None
        ):
            raise PlanStepExecutionResultRecordingCompositionInvariantError(
                "execution recording result must exist if and only if start result "
                "exists"
            )
        start = self.execution_start_result
        recording = self.execution_recording_result
        if start is None or recording is None:
            return
        if (
            recording.plan_id != start.plan_id
            or recording.run_id != start.run_id
            or recording.step_id != start.step_id
            or recording.execution_id != start.execution_id
        ):
            raise PlanStepExecutionResultRecordingCompositionInvariantError(
                "execution recording result must identify the exact WP037 start result"
            )

    def to_data(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible representation."""

        data = PlanStepExecutionStartCompositionResult.to_data(self)
        data["execution_recording_result"] = (
            None
            if self.execution_recording_result is None
            else self.execution_recording_result.to_data()
        )
        return data
