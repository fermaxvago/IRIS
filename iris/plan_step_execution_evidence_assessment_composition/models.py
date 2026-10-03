"""Immutable output of one bounded post-recording assessment composition."""

from dataclasses import dataclass

from iris.outcome_assessment import StepOutcomeAssessment
from iris.plan_step_execution_evidence_assessment_composition.errors import (
    PlanStepExecutionEvidenceAssessmentCompositionInvariantError,
)
from iris.plan_step_execution_result_recording_composition import (
    PlanStepExecutionResultRecordingCompositionResult,
)


@dataclass(frozen=True, slots=True)
class PlanStepExecutionEvidenceAssessmentCompositionResult(
    PlanStepExecutionResultRecordingCompositionResult
):
    """Preserve WP038 artifacts and append the optional exact WP027 assessment."""

    post_recording_assessment: StepOutcomeAssessment | None

    def __post_init__(self) -> None:
        PlanStepExecutionResultRecordingCompositionResult.__post_init__(self)
        if self.post_recording_assessment is not None and not isinstance(
            self.post_recording_assessment, StepOutcomeAssessment
        ):
            raise TypeError(
                "post_recording_assessment must be a StepOutcomeAssessment or None"
            )
        if (self.execution_recording_result is None) != (
            self.post_recording_assessment is None
        ):
            raise PlanStepExecutionEvidenceAssessmentCompositionInvariantError(
                "post-recording assessment must exist if and only if recording exists"
            )
        recording = self.execution_recording_result
        assessment = self.post_recording_assessment
        if recording is None or assessment is None:
            return
        if (
            assessment.plan_id != recording.plan_id
            or assessment.run_id != recording.run_id
            or assessment.run_revision != recording.recorded_run.revision
            or assessment.step_id != recording.step_id
            or recording.observation_id not in assessment.evidence_ids
        ):
            raise PlanStepExecutionEvidenceAssessmentCompositionInvariantError(
                "post-recording assessment must identify the exact WP038 recording"
            )

    def to_data(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible representation."""

        data = PlanStepExecutionResultRecordingCompositionResult.to_data(self)
        data["post_recording_assessment"] = (
            None
            if self.post_recording_assessment is None
            else self.post_recording_assessment.to_data()
        )
        return data
