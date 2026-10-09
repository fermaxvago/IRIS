"""Immutable WP052 lineage plus one optional inert Step C progress update."""

from copy import copy
from dataclasses import dataclass, fields

from iris.outcome_assessment import StepOutcomeAssessment
from iris.plan_runs import RunProvenance, StepProgressUpdate
from iris.plan_step_execution_progress_update_post_recording_composition.errors import (
    PlanStepExecutionProgressUpdatePostRecordingCompositionInvariantError,
)
from iris.plan_step_execution_result_recording import (
    PlanStepExecutionResultRecordingResult,
)
from iris.plan_step_execution_transition_decision_post_recording_composition import (
    PlanStepExecutionTransitionDecisionPostRecordingCompositionResult,
)
from iris.step_progress_transition import (
    StepProgressTransitionAction,
    StepProgressTransitionDecision,
)


def _validate_update(
    recording: PlanStepExecutionResultRecordingResult,
    assessment: StepOutcomeAssessment,
    decision: StepProgressTransitionDecision,
    update: StepProgressUpdate,
) -> None:
    """Check the exact WP022 artifact without normalizing a forged return."""

    invariant = PlanStepExecutionProgressUpdatePostRecordingCompositionInvariantError
    if not isinstance(update, StepProgressUpdate):
        raise invariant("WP022 must return a StepProgressUpdate")
    try:
        checked = copy(update)
        StepProgressUpdate.__post_init__(checked)
        if (
            any(
                type(getattr(update, item.name))
                is not type(getattr(checked, item.name))
                or getattr(update, item.name) != getattr(checked, item.name)
                for item in fields(StepProgressUpdate)
            )
            or update.updated_at.isoformat() != checked.updated_at.isoformat()
        ):
            raise invariant("WP022 update would require normalization/repair")
        provenance = update.provenance
        if not isinstance(provenance, RunProvenance):
            raise invariant("WP022 update has noncanonical provenance")
        checked_provenance = copy(provenance)
        RunProvenance.__post_init__(checked_provenance)
        if any(
            type(getattr(provenance, item.name))
            is not type(getattr(checked_provenance, item.name))
            or getattr(provenance, item.name) != getattr(checked_provenance, item.name)
            for item in fields(RunProvenance)
        ):
            raise invariant("WP022 provenance would require normalization/repair")
    except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
        raise invariant("WP022 returned a noncanonical StepProgressUpdate") from exc

    recorded_run = recording.recorded_run
    if (
        decision.action is not StepProgressTransitionAction.TRANSITION
        or update.run_id != recorded_run.run_id
        or update.run_id != recording.run_id
        or update.run_id != assessment.run_id
        or update.run_id != decision.run_id
        or update.expected_revision != recorded_run.revision
        or update.expected_revision != assessment.run_revision
        or update.expected_revision != decision.observed_revision
        or update.step_id != recording.step_id
        or update.step_id != assessment.step_id
        or update.step_id != decision.step_id
        or update.new_state is not decision.target_state
        or update.evidence_ids != assessment.evidence_ids
        or update.provenance.source_type != "step_progress_transition"
        or update.provenance.source_id != decision.decision_id
        or update.provenance.actor is not None
        or update.updated_at < recorded_run.updated_at
        or update.updated_at < decision.decided_at
        or update.update_id
        in {
            recorded_run.run_id,
            assessment.assessment_id,
            decision.decision_id,
            decision.step_id,
        }
    ):
        raise invariant("WP022 update contradicts its exact Step C lineage")


@dataclass(frozen=True, slots=True)
class PlanStepExecutionProgressUpdatePostRecordingCompositionResult(
    PlanStepExecutionTransitionDecisionPostRecordingCompositionResult
):
    """Preserve WP052 and append one optional exact WP022 update."""

    post_recording_execution_progress_update: StepProgressUpdate | None

    def __post_init__(self) -> None:
        PlanStepExecutionTransitionDecisionPostRecordingCompositionResult.__post_init__(
            self
        )
        invariant = (
            PlanStepExecutionProgressUpdatePostRecordingCompositionInvariantError
        )
        decision = self.post_recording_execution_transition_decision
        update = self.post_recording_execution_progress_update
        actionable = (
            decision is not None
            and decision.action is StepProgressTransitionAction.TRANSITION
        )
        if actionable != (update is not None):
            raise invariant("Step C update must exist exactly for TRANSITION")
        if update is None:
            return
        recording = self.post_recording_execution_recording_result
        assessment = self.post_recording_execution_assessment
        if recording is None or assessment is None or decision is None:
            raise invariant("Step C update requires its exact decision lineage")
        _validate_update(recording, assessment, decision, update)
        if (
            update is self.progress_update
            or update is self.post_recording_progress_update
        ):
            raise invariant("Step C update must be distinct from earlier updates")

    def to_data(self) -> dict[str, object]:
        """Append the exact WP022 representation to inherited WP052 data."""

        data = (
            PlanStepExecutionTransitionDecisionPostRecordingCompositionResult.to_data(
                self
            )
        )
        data["post_recording_execution_progress_update"] = (
            None
            if self.post_recording_execution_progress_update is None
            else self.post_recording_execution_progress_update.to_data()
        )
        return data
