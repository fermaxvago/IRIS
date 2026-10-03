"""Compose one bounded WP037 reaction with the existing WP026 boundary."""

from __future__ import annotations

from datetime import datetime

from iris.context import ContextBudget, ContextCandidate, ContextUncertainty
from iris.execution import ExecutionRequest, ExecutionResult, ExecutionStatus
from iris.execution.models import ExecutionInput
from iris.orchestrator import HandlerAvailability
from iris.outcome_assessment import StepOutcomeAssessment
from iris.plan_run_advancement import PlanRunProgressAdvanceResult
from iris.plan_runs import PlanRun, StepProgressState, StepProgressUpdate
from iris.plan_step_execution_binding import (
    PlanStepExecutionBinding,
    PlanStepExecutionBindingError,
    validate_plan_step_execution_binding_current,
)
from iris.plan_step_execution_result_recording import (
    PlanStepExecutionResultRecorder,
    PlanStepExecutionResultRecordingResult,
)
from iris.plan_step_execution_result_recording_composition.errors import (
    PlanStepExecutionResultRecordingCompositionInvariantError,
)
from iris.plan_step_execution_result_recording_composition.models import (
    PlanStepExecutionResultRecordingCompositionResult,
)
from iris.plan_step_execution_start import PlanStepExecutionStartResult
from iris.plan_step_execution_start_composition import (
    PlanStepExecutionStartComposer,
    PlanStepExecutionStartCompositionResult,
)
from iris.planning import Plan
from iris.step_progress_transition import StepProgressTransitionDecision


class PlanStepExecutionResultRecordingComposer:
    """Append at most one exact WP026 recording to one WP037 reaction."""

    def __init__(
        self,
        *,
        start_composer: PlanStepExecutionStartComposer,
        result_recorder: PlanStepExecutionResultRecorder | None = None,
    ) -> None:
        if not isinstance(start_composer, PlanStepExecutionStartComposer):
            raise TypeError("start_composer must be a PlanStepExecutionStartComposer")
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
    ) -> PlanStepExecutionResultRecordingCompositionResult:
        """Invoke WP037 once, optionally record its exact result, then stop."""

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
        start_composition = self._start_composer.compose(
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
        self._validate_start_composition(plan, run, step_id, start_composition)

        start_result = start_composition.execution_start_result
        if start_result is None:
            return self._result(start_composition, None)

        advancement = start_composition.advancement_result
        assert advancement is not None
        recording_base = (
            start_result.active_run
            if start_result.active_run is not None
            else advancement.updated_run
        )
        recording = self._result_recorder.record(plan, recording_base, start_result)
        self._validate_recording_result(
            plan,
            recording_base,
            start_result,
            recording,
        )
        return self._result(start_composition, recording)

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
    def _validate_start_composition(
        plan: Plan,
        source_run: PlanRun,
        processed_step_id: str,
        result: PlanStepExecutionStartCompositionResult,
    ) -> None:
        invariant = PlanStepExecutionResultRecordingCompositionInvariantError
        if not isinstance(result, PlanStepExecutionStartCompositionResult):
            raise invariant(
                "WP037 must return a PlanStepExecutionStartCompositionResult"
            )
        assessment = result.assessment
        transition = result.transition_decision
        update = result.progress_update
        advancement = result.advancement_result
        request = result.execution_request
        binding = result.execution_binding
        start = result.execution_start_result
        if not isinstance(assessment, StepOutcomeAssessment) or not isinstance(
            transition, StepProgressTransitionDecision
        ):
            raise invariant(
                "WP037 result must contain canonical assessment and transition types"
            )
        if (
            assessment.plan_id != plan.plan_id
            or assessment.run_id != source_run.run_id
            or assessment.run_revision != source_run.revision
            or assessment.step_id != processed_step_id
            or transition.plan_id != plan.plan_id
            or transition.run_id != source_run.run_id
            or transition.observed_revision != source_run.revision
            or transition.step_id != processed_step_id
            or transition.assessment_id != assessment.assessment_id
        ):
            raise invariant(
                "WP037 result does not match the supplied Plan, source Run, and step"
            )
        if update is not None and not isinstance(update, StepProgressUpdate):
            raise invariant("WP037 progress update must be canonical or None")
        if advancement is not None and not isinstance(
            advancement, PlanRunProgressAdvanceResult
        ):
            raise invariant("WP037 advancement must be canonical or None")
        if request is not None and not isinstance(request, ExecutionRequest):
            raise invariant("WP037 execution request must be canonical or None")
        if binding is not None and not isinstance(binding, PlanStepExecutionBinding):
            raise invariant("WP037 execution binding must be canonical or None")
        if start is not None and not isinstance(start, PlanStepExecutionStartResult):
            raise invariant("WP037 execution start result must be canonical or None")
        if (update is None) != (advancement is None):
            raise invariant(
                "WP037 progress update and advancement must both exist or be absent"
            )
        if (request is None) != (binding is None) or (binding is None) != (
            start is None
        ):
            raise invariant(
                "WP037 request, binding, and start result must share one presence shape"
            )
        if start is None:
            return

        if advancement is None or update is None or request is None or binding is None:
            raise invariant("WP037 start lineage is incomplete")
        pre_activation_run = advancement.updated_run
        if (
            update.run_id != source_run.run_id
            or update.expected_revision != source_run.revision
            or update.step_id != processed_step_id
            or advancement.source_update_id != update.update_id
            or advancement.source_revision != source_run.revision
            or not isinstance(pre_activation_run, PlanRun)
            or pre_activation_run.plan_id != plan.plan_id
            or pre_activation_run.run_id != source_run.run_id
            or pre_activation_run.goal_id != source_run.goal_id
            or pre_activation_run.revision != source_run.revision + 1
        ):
            raise invariant("WP037 advancement does not derive the exact successor Run")
        try:
            validate_plan_step_execution_binding_current(
                plan, pre_activation_run, binding
            )
        except (PlanStepExecutionBindingError, ValueError) as exc:
            raise invariant(
                "WP037 binding is not current for the pre-activation Run"
            ) from exc
        execution_result = start.execution_result
        if not isinstance(execution_result, ExecutionResult):
            raise invariant("WP037 start result must contain an ExecutionResult")
        if (
            start.plan_id != plan.plan_id
            or start.plan_id != binding.plan_id
            or start.run_id != pre_activation_run.run_id
            or start.run_id != binding.run_id
            or start.source_revision != pre_activation_run.revision
            or start.source_revision != binding.observed_revision
            or start.step_id != binding.step_id
            or start.execution_id != binding.execution_id
            or start.execution_id != request.execution_id
            or execution_result.execution_id != request.execution_id
            or execution_result.subject_id != request.subject.subject_id
            or execution_result.decision_id != request.decision.decision_id
            or execution_result.context_snapshot_id != request.context.snapshot_id
            or execution_result.target is not request.decision.target
            or execution_result.decision_reason is not request.decision.reason
        ):
            raise invariant(
                "WP037 start result contradicts its request/binding lineage"
            )

        active_run = start.active_run
        if active_run is None:
            failure = execution_result.failure
            if (
                start.activation_update_id is not None
                or execution_result.status is not ExecutionStatus.REJECTED
                or execution_result.handler_reference is not None
                or failure is None
                or failure.code != "handler_unavailable"
            ):
                raise invariant(
                    "non-activated WP037 result must be canonical handler unavailability"
                )
            return
        if (
            not isinstance(active_run, PlanRun)
            or active_run.plan_id != pre_activation_run.plan_id
            or active_run.run_id != pre_activation_run.run_id
            or active_run.goal_id != pre_activation_run.goal_id
            or active_run.revision != pre_activation_run.revision + 1
            or start.activation_update_id is None
        ):
            raise invariant(
                "WP037 ACTIVE Run must derive exactly from the pre-activation Run"
            )
        progress = next(
            (
                item
                for item in active_run.step_progress
                if item.step_id == start.step_id
            ),
            None,
        )
        if progress is None or progress.state is not StepProgressState.ACTIVE:
            raise invariant("WP037 started PlanStep must be ACTIVE")

    @staticmethod
    def _validate_recording_result(
        plan: Plan,
        recording_base: PlanRun,
        start_result: PlanStepExecutionStartResult,
        recording: PlanStepExecutionResultRecordingResult,
    ) -> None:
        invariant = PlanStepExecutionResultRecordingCompositionInvariantError
        if not isinstance(recording, PlanStepExecutionResultRecordingResult):
            raise invariant(
                "WP026 must return a PlanStepExecutionResultRecordingResult"
            )
        observation = recording.observation
        recorded_run = recording.recorded_run
        if (
            recording.plan_id != plan.plan_id
            or recording.plan_id != start_result.plan_id
            or recording.run_id != recording_base.run_id
            or recording.run_id != start_result.run_id
            or recording.step_id != start_result.step_id
            or recording.execution_id != start_result.execution_id
            or recording.recorded_from_revision != recording_base.revision
            or recorded_run.plan_id != recording_base.plan_id
            or recorded_run.run_id != recording_base.run_id
            or recorded_run.goal_id != recording_base.goal_id
            or recorded_run.revision != recording_base.revision + 1
        ):
            raise invariant("WP026 recording contradicts the exact recording base")
        if (
            observation.observation_id != recording.observation_id
            or observation.run_id != recording_base.run_id
            or observation.step_id != start_result.step_id
            or observation.source != "execution"
            or observation.source_reference != start_result.execution_id
            or observation.kind != "execution_result"
            or observation not in recorded_run.observations
        ):
            raise invariant("WP026 observation contradicts the exact execution lineage")
        if recorded_run.step_progress != recording_base.step_progress:
            raise invariant("WP026 recording must preserve StepProgress exactly")

    @staticmethod
    def _result(
        start_composition: PlanStepExecutionStartCompositionResult,
        recording: PlanStepExecutionResultRecordingResult | None,
    ) -> PlanStepExecutionResultRecordingCompositionResult:
        return PlanStepExecutionResultRecordingCompositionResult(
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
            execution_recording_result=recording,
        )
