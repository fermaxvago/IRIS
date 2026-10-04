"""Compose one bounded WP040 reaction with the existing WP022 boundary."""

from __future__ import annotations

from datetime import datetime

from iris.context import ContextBudget, ContextCandidate, ContextUncertainty
from iris.execution.models import ExecutionInput
from iris.orchestrator import HandlerAvailability
from iris.outcome_assessment import StepOutcomeAssessment
from iris.plan_runs import PlanRun, StepProgressUpdate
from iris.plan_step_execution_progress_update_composition.errors import (
    PlanStepExecutionProgressUpdateCompositionInvariantError,
)
from iris.plan_step_execution_progress_update_composition.models import (
    PlanStepExecutionProgressUpdateCompositionResult,
)
from iris.plan_step_execution_result_recording import (
    PlanStepExecutionResultRecordingResult,
)
from iris.plan_step_execution_transition_decision_composition import (
    PlanStepExecutionTransitionDecisionComposer,
    PlanStepExecutionTransitionDecisionCompositionResult,
)
from iris.planning import Plan
from iris.step_progress_transition import (
    StepProgressTransitionAction,
    StepProgressTransitionDecision,
    StepProgressTransitionError,
    validate_step_progress_transition_decision_current,
)
from iris.step_progress_update_synthesis import StepProgressUpdateSynthesizer


class PlanStepExecutionProgressUpdateComposer:
    """Append at most one exact WP022 update to one WP040 reaction."""

    def __init__(
        self,
        *,
        transition_decision_composer: PlanStepExecutionTransitionDecisionComposer,
        progress_update_synthesizer: StepProgressUpdateSynthesizer | None = None,
    ) -> None:
        if not isinstance(
            transition_decision_composer,
            PlanStepExecutionTransitionDecisionComposer,
        ):
            raise TypeError(
                "transition_decision_composer must be a "
                "PlanStepExecutionTransitionDecisionComposer"
            )
        if progress_update_synthesizer is not None and not isinstance(
            progress_update_synthesizer, StepProgressUpdateSynthesizer
        ):
            raise TypeError(
                "progress_update_synthesizer must be a StepProgressUpdateSynthesizer"
            )
        self._transition_decision_composer = transition_decision_composer
        self._progress_update_synthesizer = (
            StepProgressUpdateSynthesizer()
            if progress_update_synthesizer is None
            else progress_update_synthesizer
        )

    def compose(
        self,
        plan: Plan,
        run: PlanRun,
        step_id: str,
        *,
        candidates: tuple[ContextCandidate, ...],
        budget: ContextBudget,
        uncertainties: tuple[ContextUncertainty, ...] = (),
        created_at: datetime,
        availability: HandlerAvailability,
        execution_input: ExecutionInput | None = None,
    ) -> PlanStepExecutionProgressUpdateCompositionResult:
        """Invoke WP040 once, optionally synthesize one update, then stop."""

        self._validate_input_types(
            plan,
            run,
            step_id,
            candidates,
            budget,
            uncertainties,
            created_at,
            availability,
        )
        transition_composition = self._transition_decision_composer.compose(
            plan,
            run,
            step_id,
            candidates=candidates,
            budget=budget,
            uncertainties=uncertainties,
            created_at=created_at,
            availability=availability,
            execution_input=execution_input,
        )
        self._validate_transition_composition(
            plan,
            run,
            step_id,
            transition_composition,
        )

        decision = transition_composition.post_recording_transition_decision
        if decision is None or (
            decision.action is StepProgressTransitionAction.NO_TRANSITION
        ):
            return self._result(transition_composition, None)

        recording = transition_composition.execution_recording_result
        assessment = transition_composition.post_recording_assessment
        if recording is None or assessment is None:  # guarded above
            raise PlanStepExecutionProgressUpdateCompositionInvariantError(
                "TRANSITION requires the complete post-recording WP040 lineage"
            )
        update = self._progress_update_synthesizer.synthesize(
            plan,
            recording.recorded_run,
            assessment,
            decision,
        )
        self._validate_update(recording, assessment, decision, update)
        return self._result(transition_composition, update)

    @staticmethod
    def _validate_input_types(
        plan: Plan,
        run: PlanRun,
        step_id: str,
        candidates: tuple[ContextCandidate, ...],
        budget: ContextBudget,
        uncertainties: tuple[ContextUncertainty, ...],
        created_at: datetime,
        availability: HandlerAvailability,
    ) -> None:
        if not isinstance(plan, Plan):
            raise TypeError("plan must be a Plan")
        if not isinstance(run, PlanRun):
            raise TypeError("run must be a PlanRun")
        if not isinstance(step_id, str):
            raise TypeError("step_id must be a string")
        if not isinstance(candidates, tuple) or any(
            not isinstance(candidate, ContextCandidate) for candidate in candidates
        ):
            raise TypeError("candidates must be a tuple of ContextCandidate")
        if not isinstance(budget, ContextBudget):
            raise TypeError("budget must be ContextBudget")
        if not isinstance(uncertainties, tuple) or any(
            not isinstance(uncertainty, ContextUncertainty)
            for uncertainty in uncertainties
        ):
            raise TypeError("uncertainties must be a tuple of ContextUncertainty")
        if not isinstance(created_at, datetime):
            raise TypeError("created_at must be a datetime")
        if not isinstance(availability, HandlerAvailability):
            raise TypeError("availability must be a HandlerAvailability")

    @staticmethod
    def _validate_transition_composition(
        plan: Plan,
        source_run: PlanRun,
        processed_step_id: str,
        result: PlanStepExecutionTransitionDecisionCompositionResult,
    ) -> None:
        invariant = PlanStepExecutionProgressUpdateCompositionInvariantError
        if not isinstance(result, PlanStepExecutionTransitionDecisionCompositionResult):
            raise invariant(
                "WP040 must return a "
                "PlanStepExecutionTransitionDecisionCompositionResult"
            )
        try:
            result.__post_init__()
        except (RuntimeError, TypeError, ValueError) as exc:
            raise invariant("WP040 result violates its canonical contract") from exc

        inherited_assessment = result.assessment
        inherited_decision = result.transition_decision
        if not isinstance(
            inherited_assessment, StepOutcomeAssessment
        ) or not isinstance(inherited_decision, StepProgressTransitionDecision):
            raise invariant(
                "WP040 result must preserve canonical inherited decision artifacts"
            )
        if (
            inherited_assessment.plan_id != plan.plan_id
            or inherited_assessment.run_id != source_run.run_id
            or inherited_assessment.run_revision != source_run.revision
            or inherited_assessment.step_id != processed_step_id
            or inherited_decision.plan_id != plan.plan_id
            or inherited_decision.run_id != source_run.run_id
            or inherited_decision.observed_revision != source_run.revision
            or inherited_decision.step_id != processed_step_id
            or inherited_decision.assessment_id != inherited_assessment.assessment_id
        ):
            raise invariant(
                "WP040 result does not match the supplied Plan, source Run, and step"
            )

        decision = result.post_recording_transition_decision
        assessment = result.post_recording_assessment
        recording = result.execution_recording_result
        if decision is None:
            return
        if (
            not isinstance(decision, StepProgressTransitionDecision)
            or not isinstance(assessment, StepOutcomeAssessment)
            or not isinstance(recording, PlanStepExecutionResultRecordingResult)
        ):
            raise invariant("WP040 decision lineage contains noncanonical artifacts")
        try:
            validate_step_progress_transition_decision_current(
                plan,
                recording.recorded_run,
                decision,
            )
        except (StepProgressTransitionError, TypeError, ValueError) as exc:
            raise invariant(
                "WP040 decision is not current for the exact recorded Run"
            ) from exc
        if (
            recording.plan_id != plan.plan_id
            or decision.plan_id != recording.plan_id
            or decision.plan_id != assessment.plan_id
            or decision.run_id != recording.run_id
            or decision.run_id != recording.recorded_run.run_id
            or decision.run_id != assessment.run_id
            or decision.observed_revision != recording.recorded_run.revision
            or decision.observed_revision != assessment.run_revision
            or decision.step_id != recording.step_id
            or decision.step_id != assessment.step_id
            or decision.assessment_id != assessment.assessment_id
        ):
            raise invariant(
                "WP040 decision contradicts its exact post-recording lineage"
            )

    @staticmethod
    def _validate_update(
        recording: PlanStepExecutionResultRecordingResult,
        assessment: StepOutcomeAssessment,
        decision: StepProgressTransitionDecision,
        update: StepProgressUpdate,
    ) -> None:
        invariant = PlanStepExecutionProgressUpdateCompositionInvariantError
        if not isinstance(update, StepProgressUpdate):
            raise invariant("WP022 must return a StepProgressUpdate")
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
            raise invariant(
                "WP022 update contradicts the exact post-recording WP040 lineage"
            )

    @staticmethod
    def _result(
        transition_composition: PlanStepExecutionTransitionDecisionCompositionResult,
        update: StepProgressUpdate | None,
    ) -> PlanStepExecutionProgressUpdateCompositionResult:
        return PlanStepExecutionProgressUpdateCompositionResult(
            assessment=transition_composition.assessment,
            transition_decision=transition_composition.transition_decision,
            progress_update=transition_composition.progress_update,
            advancement_result=transition_composition.advancement_result,
            handling_preparation=transition_composition.handling_preparation,
            work_subject=transition_composition.work_subject,
            context_snapshot=transition_composition.context_snapshot,
            orchestration_decision=transition_composition.orchestration_decision,
            execution_request=transition_composition.execution_request,
            execution_binding=transition_composition.execution_binding,
            execution_start_result=transition_composition.execution_start_result,
            execution_recording_result=(
                transition_composition.execution_recording_result
            ),
            post_recording_assessment=(
                transition_composition.post_recording_assessment
            ),
            post_recording_transition_decision=(
                transition_composition.post_recording_transition_decision
            ),
            post_recording_progress_update=update,
        )
