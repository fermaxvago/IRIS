"""Compose one WP049 result with WP026 recording and stop."""

from __future__ import annotations

from datetime import datetime

from iris.context import ContextBudget, ContextCandidate, ContextUncertainty
from iris.execution.models import ExecutionInput
from iris.orchestrator import HandlerAvailability
from iris.plan_runs import PlanRun, validate_plan_run
from iris.plan_step_execution_result_recording import (
    PlanStepExecutionResultRecorder,
    PlanStepExecutionResultRecordingResult,
)
from iris.plan_step_execution_result_recording_post_recording_composition.errors import (
    PlanStepExecutionResultRecordingPostRecordingCompositionInvariantError,
)
from iris.plan_step_execution_result_recording_post_recording_composition.models import (
    PlanStepExecutionResultRecordingPostRecordingCompositionResult,
    _validate_recording,
)
from iris.plan_step_execution_start_post_recording_composition import (
    PlanStepExecutionStartPostRecordingComposer,
    PlanStepExecutionStartPostRecordingCompositionResult,
)
from iris.planning import Plan


class PlanStepExecutionResultRecordingPostRecordingComposer:
    """Record one exact Step C start fact; no assessment or continuation."""

    def __init__(
        self,
        *,
        start_composer: PlanStepExecutionStartPostRecordingComposer,
        result_recorder: PlanStepExecutionResultRecorder | None = None,
    ) -> None:
        if not isinstance(start_composer, PlanStepExecutionStartPostRecordingComposer):
            raise TypeError(
                "start_composer must be a PlanStepExecutionStartPostRecordingComposer"
            )
        if result_recorder is not None and not isinstance(
            result_recorder, PlanStepExecutionResultRecorder
        ):
            raise TypeError("result_recorder must be a PlanStepExecutionResultRecorder")
        self._start_composer = start_composer
        self._result_recorder = (
            PlanStepExecutionResultRecorder()
            if result_recorder is None
            else result_recorder
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
    ) -> PlanStepExecutionResultRecordingPostRecordingCompositionResult:
        """WP049 once, validate before recording, WP026 zero or one times, stop."""

        # Reuse the exact upstream validation contract, not an alternate pipeline.
        PlanStepExecutionStartPostRecordingComposer._validate_input_types(
            plan,
            run,
            step_id,
            candidates,
            budget,
            uncertainties,
            created_at,
            availability,
            execution_input,
            post_recording_candidates,
            post_recording_budget,
            post_recording_uncertainties,
            post_recording_created_at,
            post_recording_availability,
        )
        upstream = self._start_composer.compose(
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
        invariant = (
            PlanStepExecutionResultRecordingPostRecordingCompositionInvariantError
        )
        if not isinstance(
            upstream, PlanStepExecutionStartPostRecordingCompositionResult
        ):
            raise invariant(
                "WP049 must return a PlanStepExecutionStartPostRecordingCompositionResult"
            )
        # WP049 may already have caused effects. This protects recording only.
        try:
            PlanStepExecutionStartPostRecordingComposer._validate_binding_result(
                plan,
                run,
                step_id,
                post_recording_budget,
                post_recording_created_at,
                post_recording_execution_input,
                upstream,
            )
            PlanStepExecutionStartPostRecordingCompositionResult.__post_init__(upstream)
            start = upstream.post_recording_execution_start_result
            if start is not None and start.active_run is not None:
                validate_plan_run(plan, start.active_run)
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise invariant("WP049 returned contradictory cumulative lineage") from exc

        if start is None:
            return self._result(upstream, None)
        advancement = upstream.post_recording_advancement_result
        assert advancement is not None
        recording_base = (
            start.active_run
            if start.active_run is not None
            else advancement.updated_run
        )
        # Operational failures stay outside validation wrappers; never retry.
        recording = self._result_recorder.record(plan, recording_base, start)
        try:
            _validate_recording(recording_base, start, recording)
            validate_plan_run(plan, recording.recorded_run)
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise invariant("WP026 returned contradictory Step C recording") from exc
        return self._result(upstream, recording)

    @staticmethod
    def _result(
        start_composition: PlanStepExecutionStartPostRecordingCompositionResult,
        recording: PlanStepExecutionResultRecordingResult | None,
    ) -> PlanStepExecutionResultRecordingPostRecordingCompositionResult:
        return PlanStepExecutionResultRecordingPostRecordingCompositionResult(
            assessment=start_composition.assessment,
            transition_decision=start_composition.transition_decision,
            progress_update=start_composition.progress_update,
            advancement_result=start_composition.advancement_result,
            handling_preparation=start_composition.handling_preparation,
            work_subject=start_composition.work_subject,
            context_snapshot=start_composition.context_snapshot,
            orchestration_decision=start_composition.orchestration_decision,
            execution_request=start_composition.execution_request,
            execution_binding=start_composition.execution_binding,
            execution_start_result=start_composition.execution_start_result,
            execution_recording_result=start_composition.execution_recording_result,
            post_recording_assessment=start_composition.post_recording_assessment,
            post_recording_transition_decision=(
                start_composition.post_recording_transition_decision
            ),
            post_recording_progress_update=(
                start_composition.post_recording_progress_update
            ),
            post_recording_advancement_result=(
                start_composition.post_recording_advancement_result
            ),
            post_recording_handling_preparation=(
                start_composition.post_recording_handling_preparation
            ),
            post_recording_work_subject=start_composition.post_recording_work_subject,
            post_recording_context_snapshot=(
                start_composition.post_recording_context_snapshot
            ),
            post_recording_orchestration_decision=(
                start_composition.post_recording_orchestration_decision
            ),
            post_recording_execution_request=start_composition.post_recording_execution_request,
            post_recording_execution_binding=start_composition.post_recording_execution_binding,
            post_recording_execution_start_result=start_composition.post_recording_execution_start_result,
            post_recording_execution_recording_result=recording,
        )
