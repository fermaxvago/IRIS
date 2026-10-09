"""Immutable WP050 lineage plus the exact optional Step C assessment."""

from copy import copy
from dataclasses import dataclass, fields

from iris.outcome_assessment import StepOutcomeAssessment
from iris.plan_step_execution_evidence_assessment_post_recording_composition.errors import (
    PlanStepExecutionEvidenceAssessmentPostRecordingCompositionInvariantError,
)
from iris.plan_step_execution_result_recording import (
    PlanStepExecutionResultRecordingResult,
)
from iris.plan_step_execution_result_recording_post_recording_composition import (
    PlanStepExecutionResultRecordingPostRecordingCompositionResult,
)


def _validate_assessment(
    recording: PlanStepExecutionResultRecordingResult,
    assessment: StepOutcomeAssessment,
) -> None:
    """Validate the exact complete Step-scoped WP027 result without repairing it."""

    invariant = (
        PlanStepExecutionEvidenceAssessmentPostRecordingCompositionInvariantError
    )
    if not isinstance(assessment, StepOutcomeAssessment):
        raise invariant("WP027 must return a StepOutcomeAssessment")
    try:
        checked = copy(assessment)
        StepOutcomeAssessment.__post_init__(checked)
        if any(
            type(getattr(assessment, item.name))
            is not type(getattr(checked, item.name))
            or getattr(assessment, item.name) != getattr(checked, item.name)
            for item in fields(StepOutcomeAssessment)
        ):
            raise invariant("WP027 assessment would require normalization/repair")
    except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
        raise invariant("WP027 returned a noncanonical StepOutcomeAssessment") from exc

    recorded_run = recording.recorded_run
    expected_observations = tuple(
        observation
        for observation in recorded_run.observations
        if observation.step_id == recording.step_id
    )
    expected_evidence_ids = tuple(
        observation.observation_id for observation in expected_observations
    )
    if (
        assessment.plan_id != recording.plan_id
        or assessment.run_id != recording.run_id
        or assessment.run_id != recorded_run.run_id
        or assessment.run_revision != recorded_run.revision
        or assessment.step_id != recording.step_id
        or assessment.evidence_ids != expected_evidence_ids
        or assessment.assessed_at < recorded_run.created_at
        or (
            expected_observations
            and assessment.assessed_at
            < max(observation.observed_at for observation in expected_observations)
        )
    ):
        raise invariant(
            "WP027 assessment contradicts the exact complete Step C evidence basis"
        )


@dataclass(frozen=True, slots=True)
class PlanStepExecutionEvidenceAssessmentPostRecordingCompositionResult(
    PlanStepExecutionResultRecordingPostRecordingCompositionResult
):
    """Preserve WP050 and append one optional exact complete-evidence assessment."""

    post_recording_execution_assessment: StepOutcomeAssessment | None

    def __post_init__(self) -> None:
        PlanStepExecutionResultRecordingPostRecordingCompositionResult.__post_init__(
            self
        )
        invariant = (
            PlanStepExecutionEvidenceAssessmentPostRecordingCompositionInvariantError
        )
        recording = self.post_recording_execution_recording_result
        assessment = self.post_recording_execution_assessment
        if (recording is None) != (assessment is None):
            raise invariant("Step C recording and assessment must exist together")
        if recording is None:
            return
        assert assessment is not None
        _validate_assessment(recording, assessment)
        if assessment is self.post_recording_assessment:
            raise invariant(
                "earlier post-recording and Step C assessment artifacts must remain distinct"
            )

    def to_data(self) -> dict[str, object]:
        """Append the exact WP027 representation to inherited WP050 data."""

        data = PlanStepExecutionResultRecordingPostRecordingCompositionResult.to_data(
            self
        )
        data["post_recording_execution_assessment"] = (
            None
            if self.post_recording_execution_assessment is None
            else self.post_recording_execution_assessment.to_data()
        )
        return data
