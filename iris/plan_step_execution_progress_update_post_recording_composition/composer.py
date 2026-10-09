"""Compose exact WP052 Step C decisions with canonical WP022 update synthesis."""

from __future__ import annotations

from datetime import datetime

from iris.context import ContextBudget, ContextCandidate, ContextUncertainty
from iris.execution.models import ExecutionInput
from iris.orchestrator import HandlerAvailability
from iris.plan_runs import PlanRun, StepProgressUpdate
from iris.plan_step_execution_progress_update_post_recording_composition.errors import (
    PlanStepExecutionProgressUpdatePostRecordingCompositionInvariantError,
)
from iris.plan_step_execution_progress_update_post_recording_composition.models import (
    PlanStepExecutionProgressUpdatePostRecordingCompositionResult,
    _validate_update,
)
from iris.plan_step_execution_transition_decision_post_recording_composition import (
    PlanStepExecutionTransitionDecisionPostRecordingComposer,
    PlanStepExecutionTransitionDecisionPostRecordingCompositionResult,
)
from iris.planning import Plan
from iris.step_progress_transition import StepProgressTransitionAction
from iris.step_progress_update_synthesis import StepProgressUpdateSynthesizer


class PlanStepExecutionProgressUpdatePostRecordingComposer:
    """Append at most one inert WP022 update to one exact WP052 result."""

    def __init__(
        self,
        *,
        transition_decision_composer: (
            PlanStepExecutionTransitionDecisionPostRecordingComposer
        ),
        progress_update_synthesizer: StepProgressUpdateSynthesizer | None = None,
    ) -> None:
        if not isinstance(
            transition_decision_composer,
            PlanStepExecutionTransitionDecisionPostRecordingComposer,
        ):
            raise TypeError(
                "transition_decision_composer must be a "
                "PlanStepExecutionTransitionDecisionPostRecordingComposer"
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
        post_recording_candidates: tuple[ContextCandidate, ...],
        post_recording_budget: ContextBudget,
        post_recording_uncertainties: tuple[ContextUncertainty, ...] = (),
        post_recording_created_at: datetime,
        post_recording_availability: HandlerAvailability,
        post_recording_execution_input: ExecutionInput | None = None,
    ) -> PlanStepExecutionProgressUpdatePostRecordingCompositionResult:
        """Delegate once, optionally synthesize one Step C update, then stop."""

        # Delegation precedes validation to retain WP052's lazy input semantics.
        upstream = self._transition_decision_composer.compose(
            plan,
            run,
            step_id,
            candidates=candidates,
            budget=budget,
            uncertainties=uncertainties,
            created_at=created_at,
            availability=availability,
            execution_input=execution_input,
            post_recording_candidates=post_recording_candidates,
            post_recording_budget=post_recording_budget,
            post_recording_uncertainties=post_recording_uncertainties,
            post_recording_created_at=post_recording_created_at,
            post_recording_availability=post_recording_availability,
            post_recording_execution_input=post_recording_execution_input,
        )
        self._validate_upstream(
            plan,
            run,
            step_id,
            post_recording_budget,
            post_recording_created_at,
            post_recording_execution_input,
            upstream,
        )
        decision = upstream.post_recording_execution_transition_decision
        if (
            decision is None
            or decision.action is StepProgressTransitionAction.NO_TRANSITION
        ):
            return self._result(upstream, None)

        recording = upstream.post_recording_execution_recording_result
        assessment = upstream.post_recording_execution_assessment
        if recording is None or assessment is None:  # guarded above
            raise PlanStepExecutionProgressUpdatePostRecordingCompositionInvariantError(
                "TRANSITION requires exact Step C recording and assessment"
            )
        update = self._progress_update_synthesizer.synthesize(
            plan, recording.recorded_run, assessment, decision
        )
        _validate_update(recording, assessment, decision, update)
        return self._result(upstream, update)

    @staticmethod
    def _validate_upstream(
        plan: Plan,
        source_run: PlanRun,
        processed_step_id: str,
        post_recording_budget: ContextBudget,
        post_recording_created_at: datetime,
        post_recording_execution_input: ExecutionInput | None,
        result: PlanStepExecutionTransitionDecisionPostRecordingCompositionResult,
    ) -> None:
        invariant = (
            PlanStepExecutionProgressUpdatePostRecordingCompositionInvariantError
        )
        if not isinstance(
            result, PlanStepExecutionTransitionDecisionPostRecordingCompositionResult
        ):
            raise invariant("WP052 must return its canonical composition result")
        try:
            PlanStepExecutionTransitionDecisionPostRecordingComposer._validate_evidence_composition(
                plan,
                source_run,
                processed_step_id,
                post_recording_budget,
                post_recording_created_at,
                post_recording_execution_input,
                result,
            )
            PlanStepExecutionTransitionDecisionPostRecordingCompositionResult.__post_init__(
                result
            )
            recording = result.post_recording_execution_recording_result
            assessment = result.post_recording_execution_assessment
            decision = result.post_recording_execution_transition_decision
            if (
                recording is not None
                and assessment is not None
                and decision is not None
            ):
                PlanStepExecutionTransitionDecisionPostRecordingComposer._validate_decision(
                    plan, recording, assessment, decision
                )
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise invariant("WP052 returned contradictory cumulative lineage") from exc

    @staticmethod
    def _result(
        upstream: PlanStepExecutionTransitionDecisionPostRecordingCompositionResult,
        update: StepProgressUpdate | None,
    ) -> PlanStepExecutionProgressUpdatePostRecordingCompositionResult:
        return PlanStepExecutionProgressUpdatePostRecordingCompositionResult(
            assessment=upstream.assessment,
            transition_decision=upstream.transition_decision,
            progress_update=upstream.progress_update,
            advancement_result=upstream.advancement_result,
            handling_preparation=upstream.handling_preparation,
            work_subject=upstream.work_subject,
            context_snapshot=upstream.context_snapshot,
            orchestration_decision=upstream.orchestration_decision,
            execution_request=upstream.execution_request,
            execution_binding=upstream.execution_binding,
            execution_start_result=upstream.execution_start_result,
            execution_recording_result=upstream.execution_recording_result,
            post_recording_assessment=upstream.post_recording_assessment,
            post_recording_transition_decision=upstream.post_recording_transition_decision,
            post_recording_progress_update=upstream.post_recording_progress_update,
            post_recording_advancement_result=upstream.post_recording_advancement_result,
            post_recording_handling_preparation=upstream.post_recording_handling_preparation,
            post_recording_work_subject=upstream.post_recording_work_subject,
            post_recording_context_snapshot=upstream.post_recording_context_snapshot,
            post_recording_orchestration_decision=upstream.post_recording_orchestration_decision,
            post_recording_execution_request=upstream.post_recording_execution_request,
            post_recording_execution_binding=upstream.post_recording_execution_binding,
            post_recording_execution_start_result=upstream.post_recording_execution_start_result,
            post_recording_execution_recording_result=upstream.post_recording_execution_recording_result,
            post_recording_execution_assessment=upstream.post_recording_execution_assessment,
            post_recording_execution_transition_decision=upstream.post_recording_execution_transition_decision,
            post_recording_execution_progress_update=update,
        )
