"""Compose exact WP055 lineage with optional canonical WP015 identity."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from iris.context import ContextBudget, ContextCandidate, ContextUncertainty
from iris.execution.models import ExecutionInput
from iris.orchestrator import HandlerAvailability
from iris.plan_control import ControlDecisionKind
from iris.plan_runs import PlanRun
from iris.plan_step_execution_handling_preparation_post_recording_composition import (
    PlanStepExecutionHandlingPreparationPostRecordingComposer,
    PlanStepExecutionHandlingPreparationPostRecordingCompositionResult,
)
from iris.plan_step_execution_work_subject_materialization_post_recording_composition.errors import (
    PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionInvariantError,
)
from iris.plan_step_execution_work_subject_materialization_post_recording_composition.models import (
    PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionResult,
    validate_successor_subject,
)
from iris.planning import Plan
from iris.work_identity import WorkSubject, work_subject_from_plan_step

WorkSubjectAdapter = Callable[[Plan, PlanRun, str], WorkSubject]


class PlanStepExecutionWorkSubjectMaterializationPostRecordingComposer:
    """Append at most one successor WorkSubject to one exact WP055 result."""

    def __init__(
        self,
        *,
        handling_preparation_composer: (
            PlanStepExecutionHandlingPreparationPostRecordingComposer
        ),
        work_subject_adapter: WorkSubjectAdapter | None = None,
    ) -> None:
        if not isinstance(
            handling_preparation_composer,
            PlanStepExecutionHandlingPreparationPostRecordingComposer,
        ):
            raise TypeError(
                "handling_preparation_composer must be a "
                "PlanStepExecutionHandlingPreparationPostRecordingComposer"
            )
        if work_subject_adapter is not None and not callable(work_subject_adapter):
            raise TypeError("work_subject_adapter must be callable")
        self._handling_preparation_composer = handling_preparation_composer
        self._work_subject_adapter = (
            work_subject_from_plan_step
            if work_subject_adapter is None
            else work_subject_adapter
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
    ) -> PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionResult:
        """Delegate once, optionally materialize selected work, then stop."""

        # Preserve WP055's deferred validation by delegating before local checks.
        upstream = self._handling_preparation_composer.compose(
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
        advancement = upstream.post_recording_execution_advancement_result
        if (
            advancement is None
            or advancement.control_decision.kind
            is not ControlDecisionKind.STEP_SELECTED
        ):
            return self._result(upstream, None)

        successor = advancement.updated_run
        control = advancement.control_decision
        selected_id = control.selected_step_id
        if selected_id is None:  # guarded by canonical control validation
            raise PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionInvariantError(
                "STEP_SELECTED control must identify one PlanStep"
            )
        try:
            subject = self._work_subject_adapter(plan, successor, selected_id)
        except Exception as exc:
            raise PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionInvariantError(
                "WP015 could not materialize exact successor work"
            ) from exc
        validate_successor_subject(
            subject,
            plan_id=plan.plan_id,
            run_id=successor.run_id,
            step_id=selected_id,
        )
        return self._result(upstream, subject)

    @staticmethod
    def _validate_upstream(
        plan: Plan,
        source_run: PlanRun,
        processed_step_id: str,
        post_recording_budget: ContextBudget,
        post_recording_created_at: datetime,
        post_recording_execution_input: ExecutionInput | None,
        result: PlanStepExecutionHandlingPreparationPostRecordingCompositionResult,
    ) -> None:
        invariant = PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionInvariantError
        if not isinstance(
            result, PlanStepExecutionHandlingPreparationPostRecordingCompositionResult
        ):
            raise invariant("WP055 must return its canonical composition result")
        try:
            PlanStepExecutionHandlingPreparationPostRecordingComposer._validate_upstream(
                plan,
                source_run,
                processed_step_id,
                post_recording_budget,
                post_recording_created_at,
                post_recording_execution_input,
                result,
            )
            PlanStepExecutionHandlingPreparationPostRecordingCompositionResult.__post_init__(
                result
            )
            advancement = result.post_recording_execution_advancement_result
            preparation = result.post_recording_execution_handling_preparation
            if advancement is not None and preparation is not None:
                PlanStepExecutionHandlingPreparationPostRecordingComposer._validate_preparation(
                    plan,
                    advancement.updated_run,
                    advancement.control_decision,
                    preparation,
                )
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise invariant("WP055 returned contradictory cumulative lineage") from exc

    @staticmethod
    def _result(
        upstream: PlanStepExecutionHandlingPreparationPostRecordingCompositionResult,
        subject: WorkSubject | None,
    ) -> PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionResult:
        return PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionResult(
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
            post_recording_execution_progress_update=upstream.post_recording_execution_progress_update,
            post_recording_execution_advancement_result=upstream.post_recording_execution_advancement_result,
            post_recording_execution_handling_preparation=upstream.post_recording_execution_handling_preparation,
            post_recording_execution_work_subject=subject,
        )
