"""Compose one bounded WP042 result with the existing WP014 boundary."""

from __future__ import annotations

from datetime import datetime

from iris.context import ContextBudget, ContextCandidate, ContextUncertainty
from iris.execution.models import ExecutionInput
from iris.orchestrator import HandlerAvailability
from iris.outcome_assessment import StepOutcomeAssessment
from iris.plan_control import (
    ControlDecision,
    ControlDecisionKind,
    PlanControlError,
    validate_control_decision_current,
)
from iris.plan_handling import (
    PlanHandlingError,
    PlanStepHandlingPreparer,
    StepHandlingPreparationResult,
    validate_step_handling_preparation_current,
)
from iris.plan_runs import PlanRun, PlanRunError
from iris.plan_step_execution_handling_preparation_composition.errors import (
    PlanStepExecutionHandlingPreparationCompositionInvariantError,
)
from iris.plan_step_execution_handling_preparation_composition.models import (
    PlanStepExecutionHandlingPreparationCompositionResult,
)
from iris.plan_step_execution_progress_advancement_composition import (
    PlanStepExecutionProgressAdvancementComposer,
    PlanStepExecutionProgressAdvancementCompositionResult,
)
from iris.planning import Plan
from iris.step_progress_transition import StepProgressTransitionDecision


class PlanStepExecutionHandlingPreparationComposer:
    """Append at most one exact WP014 result to one WP042 reaction."""

    def __init__(
        self,
        *,
        progress_advancement_composer: PlanStepExecutionProgressAdvancementComposer,
        handling_preparer: PlanStepHandlingPreparer | None = None,
    ) -> None:
        if not isinstance(
            progress_advancement_composer,
            PlanStepExecutionProgressAdvancementComposer,
        ):
            raise TypeError(
                "progress_advancement_composer must be a "
                "PlanStepExecutionProgressAdvancementComposer"
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
    ) -> PlanStepExecutionHandlingPreparationCompositionResult:
        """Invoke WP042 once, optionally prepare fresh handling, then stop."""

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
        progress = self._progress_advancement_composer.compose(
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
        self._validate_progress_result(plan, run, step_id, progress)

        advancement = progress.post_recording_advancement_result
        if advancement is None:
            return self._result(progress, None)

        control = advancement.control_decision
        if control.kind is not ControlDecisionKind.STEP_SELECTED:
            return self._result(progress, None)

        preparation = self._handling_preparer.prepare(
            plan,
            advancement.updated_run,
            control,
        )
        self._validate_handling_result(
            plan,
            advancement.updated_run,
            control,
            preparation,
        )
        return self._result(progress, preparation)

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
    def _validate_progress_result(
        plan: Plan,
        source_run: PlanRun,
        processed_step_id: str,
        result: PlanStepExecutionProgressAdvancementCompositionResult,
    ) -> None:
        invariant = PlanStepExecutionHandlingPreparationCompositionInvariantError
        if not isinstance(
            result, PlanStepExecutionProgressAdvancementCompositionResult
        ):
            raise invariant(
                "WP042 must return a "
                "PlanStepExecutionProgressAdvancementCompositionResult"
            )
        try:
            result.__post_init__()
        except (RuntimeError, TypeError, ValueError) as exc:
            raise invariant("WP042 result violates its canonical contract") from exc

        assessment = result.assessment
        decision = result.transition_decision
        if not isinstance(assessment, StepOutcomeAssessment) or not isinstance(
            decision, StepProgressTransitionDecision
        ):
            raise invariant(
                "WP042 result must preserve canonical inherited decision artifacts"
            )
        if (
            assessment.plan_id != plan.plan_id
            or assessment.run_id != source_run.run_id
            or assessment.run_revision != source_run.revision
            or assessment.step_id != processed_step_id
            or decision.plan_id != plan.plan_id
            or decision.run_id != source_run.run_id
            or decision.observed_revision != source_run.revision
            or decision.step_id != processed_step_id
            or decision.assessment_id != assessment.assessment_id
        ):
            raise invariant(
                "WP042 result does not match the supplied Plan, source Run, and step"
            )

        advancement = result.post_recording_advancement_result
        if advancement is None:
            return
        successor = advancement.updated_run
        control = advancement.control_decision
        if not isinstance(successor, PlanRun) or not isinstance(
            control, ControlDecision
        ):
            raise invariant("WP042 advancement contains noncanonical artifacts")
        if (
            successor.plan_id != plan.plan_id
            or successor.run_id != source_run.run_id
            or successor.goal_id != source_run.goal_id
            or control.plan_id != plan.plan_id
            or control.run_id != successor.run_id
            or control.observed_revision != successor.revision
        ):
            raise invariant(
                "WP042 successor Run and fresh control contradict the operation"
            )
        try:
            validate_control_decision_current(plan, successor, control)
        except (PlanControlError, PlanRunError, TypeError) as exc:
            raise invariant(
                "WP042 fresh control is not current for its exact successor Run"
            ) from exc

    @staticmethod
    def _validate_handling_result(
        plan: Plan,
        successor: PlanRun,
        control: ControlDecision,
        preparation: StepHandlingPreparationResult,
    ) -> None:
        invariant = PlanStepExecutionHandlingPreparationCompositionInvariantError
        if not isinstance(preparation, StepHandlingPreparationResult):
            raise invariant("WP014 must return a StepHandlingPreparationResult")
        try:
            preparation.__post_init__()
        except (PlanHandlingError, TypeError, ValueError) as exc:
            raise invariant("WP014 result violates its canonical contract") from exc
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
            raise invariant(
                "WP014 result does not match the exact post-recording selection"
            )
        try:
            validate_step_handling_preparation_current(
                plan,
                successor,
                preparation,
            )
        except (PlanHandlingError, PlanControlError, PlanRunError, TypeError) as exc:
            raise invariant(
                "WP014 result is not current for the exact post-recording selection"
            ) from exc

    @staticmethod
    def _result(
        progress: PlanStepExecutionProgressAdvancementCompositionResult,
        preparation: StepHandlingPreparationResult | None,
    ) -> PlanStepExecutionHandlingPreparationCompositionResult:
        return PlanStepExecutionHandlingPreparationCompositionResult(
            assessment=progress.assessment,
            transition_decision=progress.transition_decision,
            progress_update=progress.progress_update,
            advancement_result=progress.advancement_result,
            handling_preparation=progress.handling_preparation,
            work_subject=progress.work_subject,
            context_snapshot=progress.context_snapshot,
            orchestration_decision=progress.orchestration_decision,
            execution_request=progress.execution_request,
            execution_binding=progress.execution_binding,
            execution_start_result=progress.execution_start_result,
            execution_recording_result=progress.execution_recording_result,
            post_recording_assessment=progress.post_recording_assessment,
            post_recording_transition_decision=(
                progress.post_recording_transition_decision
            ),
            post_recording_progress_update=(progress.post_recording_progress_update),
            post_recording_advancement_result=(
                progress.post_recording_advancement_result
            ),
            post_recording_handling_preparation=preparation,
        )
