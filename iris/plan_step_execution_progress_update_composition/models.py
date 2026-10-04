"""Immutable output of one bounded post-decision update composition."""

from dataclasses import dataclass

from iris.plan_runs import StepProgressUpdate
from iris.plan_step_execution_progress_update_composition.errors import (
    PlanStepExecutionProgressUpdateCompositionInvariantError,
)
from iris.plan_step_execution_transition_decision_composition import (
    PlanStepExecutionTransitionDecisionCompositionResult,
)
from iris.step_progress_transition import StepProgressTransitionAction


@dataclass(frozen=True, slots=True)
class PlanStepExecutionProgressUpdateCompositionResult(
    PlanStepExecutionTransitionDecisionCompositionResult
):
    """Preserve WP040 artifacts and append the optional exact WP022 update."""

    post_recording_progress_update: StepProgressUpdate | None

    def __post_init__(self) -> None:
        PlanStepExecutionTransitionDecisionCompositionResult.__post_init__(self)
        update = self.post_recording_progress_update
        if update is not None and not isinstance(update, StepProgressUpdate):
            raise TypeError(
                "post_recording_progress_update must be a StepProgressUpdate or None"
            )

        decision = self.post_recording_transition_decision
        transition_requested = (
            decision is not None
            and decision.action is StepProgressTransitionAction.TRANSITION
        )
        if transition_requested != (update is not None):
            raise PlanStepExecutionProgressUpdateCompositionInvariantError(
                "a post-recording progress update must exist if and only if the "
                "post-recording decision requests TRANSITION"
            )
        if update is not None:
            self._validate_update(update)

    def _validate_update(self, update: StepProgressUpdate) -> None:
        assessment = self.post_recording_assessment
        decision = self.post_recording_transition_decision
        recording = self.execution_recording_result
        if assessment is None or decision is None or recording is None:
            raise PlanStepExecutionProgressUpdateCompositionInvariantError(
                "post-recording progress update requires its complete WP040 lineage"
            )
        if (
            update.run_id != decision.run_id
            or update.run_id != assessment.run_id
            or update.run_id != recording.run_id
            or update.run_id != recording.recorded_run.run_id
            or update.expected_revision != decision.observed_revision
            or update.expected_revision != assessment.run_revision
            or update.expected_revision != recording.recorded_run.revision
            or update.step_id != decision.step_id
            or update.step_id != assessment.step_id
            or update.step_id != recording.step_id
            or update.new_state is not decision.target_state
            or update.evidence_ids != assessment.evidence_ids
            or update.provenance.source_type != "step_progress_transition"
            or update.provenance.source_id != decision.decision_id
            or update.provenance.actor is not None
        ):
            raise PlanStepExecutionProgressUpdateCompositionInvariantError(
                "post-recording progress update contradicts its exact WP040 lineage"
            )

    def to_data(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible representation."""

        data = PlanStepExecutionTransitionDecisionCompositionResult.to_data(self)
        data["post_recording_progress_update"] = (
            None
            if self.post_recording_progress_update is None
            else self.post_recording_progress_update.to_data()
        )
        return data
