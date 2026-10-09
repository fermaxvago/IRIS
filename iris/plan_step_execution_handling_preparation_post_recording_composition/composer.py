"""Compose one exact WP054 result with optional canonical WP014 preparation."""

from __future__ import annotations

from datetime import datetime

from iris.context import ContextBudget, ContextCandidate, ContextUncertainty
from iris.execution.models import ExecutionInput
from iris.orchestrator import HandlerAvailability
from iris.plan_control import (
    ControlDecision,
    ControlDecisionKind,
    validate_control_decision_current,
)
from iris.plan_handling import (
    PlanStepHandlingPreparer,
    StepHandlingPreparationResult,
    validate_step_handling_preparation_current,
)
from iris.plan_runs import PlanRun
from iris.plan_step_execution_handling_preparation_post_recording_composition.errors import (
    PlanStepExecutionHandlingPreparationPostRecordingCompositionInvariantError,
)
from iris.plan_step_execution_handling_preparation_post_recording_composition.models import (
    PlanStepExecutionHandlingPreparationPostRecordingCompositionResult,
    validate_preparation_artifact,
)
from iris.plan_step_execution_progress_advancement_post_recording_composition import (
    PlanStepExecutionProgressAdvancementPostRecordingComposer,
    PlanStepExecutionProgressAdvancementPostRecordingCompositionResult,
)
from iris.planning import Plan


class PlanStepExecutionHandlingPreparationPostRecordingComposer:
    """Append at most one exact WP014 result to one WP054 composition."""

    def __init__(
        self,
        *,
        progress_advancement_composer: (
            PlanStepExecutionProgressAdvancementPostRecordingComposer
        ),
        handling_preparer: PlanStepHandlingPreparer | None = None,
    ) -> None:
        if not isinstance(
            progress_advancement_composer,
            PlanStepExecutionProgressAdvancementPostRecordingComposer,
        ):
            raise TypeError(
                "progress_advancement_composer must be a "
                "PlanStepExecutionProgressAdvancementPostRecordingComposer"
            )
        if handling_preparer is not None and not isinstance(
            handling_preparer, PlanStepHandlingPreparer
        ):
            raise TypeError("handling_preparer must be a PlanStepHandlingPreparer")
        self._progress_advancement_composer = progress_advancement_composer
        self._handling_preparer = (
            PlanStepHandlingPreparer()
            if handling_preparer is None
            else handling_preparer
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
    ) -> PlanStepExecutionHandlingPreparationPostRecordingCompositionResult:
        """Delegate once, optionally prepare the successor selection, then stop."""

        # Delegation comes first to preserve WP054's deferred validation semantics.
        upstream = self._progress_advancement_composer.compose(
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
        preparation = self._handling_preparer.prepare(plan, successor, control)
        self._validate_preparation(plan, successor, control, preparation)
        return self._result(upstream, preparation)

    @staticmethod
    def _validate_upstream(
        plan: Plan,
        source_run: PlanRun,
        processed_step_id: str,
        post_recording_budget: ContextBudget,
        post_recording_created_at: datetime,
        post_recording_execution_input: ExecutionInput | None,
        result: PlanStepExecutionProgressAdvancementPostRecordingCompositionResult,
    ) -> None:
        invariant = (
            PlanStepExecutionHandlingPreparationPostRecordingCompositionInvariantError
        )
        if not isinstance(
            result,
            PlanStepExecutionProgressAdvancementPostRecordingCompositionResult,
        ):
            raise invariant("WP054 must return its canonical composition result")
        try:
            PlanStepExecutionProgressAdvancementPostRecordingComposer._validate_upstream(
                plan,
                source_run,
                processed_step_id,
                post_recording_budget,
                post_recording_created_at,
                post_recording_execution_input,
                result,
            )
            PlanStepExecutionProgressAdvancementPostRecordingCompositionResult.__post_init__(
                result
            )
            advancement = result.post_recording_execution_advancement_result
            if advancement is not None:
                validate_control_decision_current(
                    plan,
                    advancement.updated_run,
                    advancement.control_decision,
                )
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise invariant("WP054 returned contradictory cumulative lineage") from exc

    @staticmethod
    def _validate_preparation(
        plan: Plan,
        successor: PlanRun,
        control: ControlDecision,
        preparation: StepHandlingPreparationResult,
    ) -> None:
        invariant = (
            PlanStepExecutionHandlingPreparationPostRecordingCompositionInvariantError
        )
        validate_preparation_artifact(preparation)
        if (
            preparation.plan_id != plan.plan_id
            or preparation.plan_id != successor.plan_id
            or preparation.plan_id != control.plan_id
            or preparation.run_id != successor.run_id
            or preparation.run_id != control.run_id
            or preparation.observed_revision != successor.revision
            or preparation.observed_revision != control.observed_revision
            or preparation.step_id != control.selected_step_id
        ):
            raise invariant("WP014 preparation contradicts the successor selection")
        try:
            validate_step_handling_preparation_current(plan, successor, preparation)
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise invariant(
                "WP014 preparation is not current for the successor"
            ) from exc

    @staticmethod
    def _result(
        upstream: PlanStepExecutionProgressAdvancementPostRecordingCompositionResult,
        preparation: StepHandlingPreparationResult | None,
    ) -> PlanStepExecutionHandlingPreparationPostRecordingCompositionResult:
        return PlanStepExecutionHandlingPreparationPostRecordingCompositionResult(
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
            post_recording_execution_handling_preparation=preparation,
        )
