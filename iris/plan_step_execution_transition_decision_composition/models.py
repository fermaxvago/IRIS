"""Immutable output of one bounded post-assessment transition composition."""

from dataclasses import dataclass

from iris.plan_step_execution_evidence_assessment_composition import (
    PlanStepExecutionEvidenceAssessmentCompositionResult,
)
from iris.plan_step_execution_transition_decision_composition.errors import (
    PlanStepExecutionTransitionDecisionCompositionInvariantError,
)
from iris.step_progress_transition import StepProgressTransitionDecision


@dataclass(frozen=True, slots=True)
class PlanStepExecutionTransitionDecisionCompositionResult(
    PlanStepExecutionEvidenceAssessmentCompositionResult
):
    """Preserve WP039 artifacts and append the optional exact WP021 decision."""

    post_recording_transition_decision: StepProgressTransitionDecision | None

    def __post_init__(self) -> None:
        PlanStepExecutionEvidenceAssessmentCompositionResult.__post_init__(self)
        decision = self.post_recording_transition_decision
        if decision is not None and not isinstance(
            decision, StepProgressTransitionDecision
        ):
            raise TypeError(
                "post_recording_transition_decision must be a "
                "StepProgressTransitionDecision or None"
            )
        if (self.post_recording_assessment is None) != (decision is None):
            raise PlanStepExecutionTransitionDecisionCompositionInvariantError(
                "post-recording assessment and decision must share one presence shape"
            )
        assessment = self.post_recording_assessment
        recording = self.execution_recording_result
        if assessment is None or decision is None:
            return
        if recording is None or (
            decision.plan_id != assessment.plan_id
            or decision.plan_id != recording.plan_id
            or decision.run_id != assessment.run_id
            or decision.run_id != recording.run_id
            or decision.observed_revision != assessment.run_revision
            or decision.observed_revision != recording.recorded_run.revision
            or decision.step_id != assessment.step_id
            or decision.step_id != recording.step_id
            or decision.assessment_id != assessment.assessment_id
        ):
            raise PlanStepExecutionTransitionDecisionCompositionInvariantError(
                "post-recording decision must identify the exact WP039 assessment"
            )

    def to_data(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible representation."""

        data = PlanStepExecutionEvidenceAssessmentCompositionResult.to_data(self)
        data["post_recording_transition_decision"] = (
            None
            if self.post_recording_transition_decision is None
            else self.post_recording_transition_decision.to_data()
        )
        return data
