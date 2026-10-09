"""Immutable WP051 lineage plus the optional exact Step C transition decision."""

from copy import copy
from dataclasses import dataclass, fields

from iris.outcome_assessment import StepOutcomeAssessment
from iris.plan_step_execution_evidence_assessment_post_recording_composition import (
    PlanStepExecutionEvidenceAssessmentPostRecordingCompositionResult,
)
from iris.plan_step_execution_result_recording import (
    PlanStepExecutionResultRecordingResult,
)
from iris.plan_step_execution_transition_decision_post_recording_composition.errors import (
    PlanStepExecutionTransitionDecisionPostRecordingCompositionInvariantError,
)
from iris.step_progress_transition import StepProgressTransitionDecision


def _validate_transition_decision(
    recording: PlanStepExecutionResultRecordingResult,
    assessment: StepOutcomeAssessment,
    decision: StepProgressTransitionDecision,
) -> None:
    """Validate exact Step C decision lineage without repairing policy output."""

    invariant = (
        PlanStepExecutionTransitionDecisionPostRecordingCompositionInvariantError
    )
    if not isinstance(decision, StepProgressTransitionDecision):
        raise invariant("WP021 must return a StepProgressTransitionDecision")
    try:
        checked = copy(decision)
        StepProgressTransitionDecision.__post_init__(checked)
        if any(
            type(getattr(decision, item.name)) is not type(getattr(checked, item.name))
            or getattr(decision, item.name) != getattr(checked, item.name)
            for item in fields(StepProgressTransitionDecision)
        ):
            raise invariant("WP021 decision would require normalization/repair")
    except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
        raise invariant(
            "WP021 returned a noncanonical StepProgressTransitionDecision"
        ) from exc

    recorded_run = recording.recorded_run
    progress = next(
        (
            item
            for item in recorded_run.step_progress
            if item.step_id == recording.step_id
        ),
        None,
    )
    if progress is None:
        raise invariant("Step C recording references missing StepProgress")
    if (
        decision.plan_id != assessment.plan_id
        or decision.plan_id != recording.plan_id
        or decision.run_id != assessment.run_id
        or decision.run_id != recording.run_id
        or decision.run_id != recorded_run.run_id
        or decision.observed_revision != assessment.run_revision
        or decision.observed_revision != recorded_run.revision
        or decision.step_id != assessment.step_id
        or decision.step_id != recording.step_id
        or decision.assessment_id != assessment.assessment_id
        or decision.source_state is not progress.state
        or decision.decided_at < recorded_run.updated_at
        or decision.decided_at < assessment.assessed_at
    ):
        raise invariant(
            "WP021 decision contradicts the exact Step C assessment lineage"
        )


@dataclass(frozen=True, slots=True)
class PlanStepExecutionTransitionDecisionPostRecordingCompositionResult(
    PlanStepExecutionEvidenceAssessmentPostRecordingCompositionResult
):
    """Preserve WP051 and append one optional exact WP021 decision."""

    post_recording_execution_transition_decision: StepProgressTransitionDecision | None

    def __post_init__(self) -> None:
        PlanStepExecutionEvidenceAssessmentPostRecordingCompositionResult.__post_init__(
            self
        )
        invariant = (
            PlanStepExecutionTransitionDecisionPostRecordingCompositionInvariantError
        )
        assessment = self.post_recording_execution_assessment
        decision = self.post_recording_execution_transition_decision
        if (assessment is None) != (decision is None):
            raise invariant("Step C assessment and decision must exist together")
        if assessment is None:
            return
        recording = self.post_recording_execution_recording_result
        if recording is None or decision is None:
            raise invariant("Step C decision requires its exact recording lineage")
        _validate_transition_decision(recording, assessment, decision)
        if decision is self.transition_decision or (
            decision is self.post_recording_transition_decision
        ):
            raise invariant(
                "earlier and Step C transition decisions must remain distinct"
            )

    def to_data(self) -> dict[str, object]:
        """Append the exact WP021 representation to inherited WP051 data."""

        data = (
            PlanStepExecutionEvidenceAssessmentPostRecordingCompositionResult.to_data(
                self
            )
        )
        data["post_recording_execution_transition_decision"] = (
            None
            if self.post_recording_execution_transition_decision is None
            else self.post_recording_execution_transition_decision.to_data()
        )
        return data
