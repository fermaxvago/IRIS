"""Compose one WP030 result with optional exact WP014 preparation."""

from __future__ import annotations

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
from iris.plan_run_advancement import PlanRunProgressAdvanceResult
from iris.plan_runs import PlanRun, PlanRunError, StepProgressUpdate
from iris.plan_step_handling_preparation.errors import (
    PlanStepHandlingPreparationInvariantError,
)
from iris.plan_step_handling_preparation.models import (
    PlanStepHandlingPreparationResult,
)
from iris.plan_step_progress_advancement import (
    PlanStepProgressAdvancementComposer,
    PlanStepProgressAdvancementResult,
)
from iris.planning import Plan
from iris.step_progress_transition import StepProgressTransitionDecision


class PlanStepHandlingPreparationComposer:
    """Advance reaction once, optionally prepare fresh selected handling, stop."""

    def __init__(
        self,
        *,
        progress_advancement_composer: PlanStepProgressAdvancementComposer
        | None = None,
        handling_preparer: PlanStepHandlingPreparer | None = None,
    ) -> None:
        if progress_advancement_composer is not None and not isinstance(
            progress_advancement_composer, PlanStepProgressAdvancementComposer
        ):
            raise TypeError(
                "progress_advancement_composer must be a "
                "PlanStepProgressAdvancementComposer"
            )
        if handling_preparer is not None and not isinstance(
            handling_preparer, PlanStepHandlingPreparer
        ):
            raise TypeError("handling_preparer must be a PlanStepHandlingPreparer")
        self._progress_advancement_composer = (
            PlanStepProgressAdvancementComposer()
            if progress_advancement_composer is None
            else progress_advancement_composer
        )
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
    ) -> PlanStepHandlingPreparationResult:
        """Return WP030 artifacts and zero or one exact WP014 preparation."""

        self._validate_input_types(plan, run, step_id)
        progress = self._progress_advancement_composer.compose(plan, run, step_id)
        self._validate_progress_result(plan, run, step_id, progress)

        advancement = progress.advancement_result
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
            advancement,
            preparation,
        )
        return self._result(progress, preparation)

    @staticmethod
    def _validate_input_types(plan: Plan, run: PlanRun, step_id: str) -> None:
        if not isinstance(plan, Plan):
            raise TypeError("plan must be a Plan")
        if not isinstance(run, PlanRun):
            raise TypeError("run must be a PlanRun")
        if not isinstance(step_id, str):
            raise TypeError("step_id must be a string")

    @classmethod
    def _validate_progress_result(
        cls,
        plan: Plan,
        run: PlanRun,
        step_id: str,
        result: PlanStepProgressAdvancementResult,
    ) -> None:
        if not isinstance(result, PlanStepProgressAdvancementResult):
            raise PlanStepHandlingPreparationInvariantError(
                "WP030 composer must return a PlanStepProgressAdvancementResult"
            )
        assessment = result.assessment
        decision = result.transition_decision
        update = result.progress_update
        advancement = result.advancement_result
        if not isinstance(assessment, StepOutcomeAssessment) or not isinstance(
            decision, StepProgressTransitionDecision
        ):
            raise PlanStepHandlingPreparationInvariantError(
                "WP030 result must contain canonical assessment and decision types"
            )
        if update is not None and not isinstance(update, StepProgressUpdate):
            raise PlanStepHandlingPreparationInvariantError(
                "WP030 progress_update must be a StepProgressUpdate or None"
            )
        if advancement is not None and not isinstance(
            advancement, PlanRunProgressAdvanceResult
        ):
            raise PlanStepHandlingPreparationInvariantError(
                "WP030 advancement_result must be a PlanRunProgressAdvanceResult or None"
            )
        if (
            assessment.plan_id != plan.plan_id
            or assessment.run_id != run.run_id
            or assessment.run_revision != run.revision
            or assessment.step_id != step_id
            or decision.plan_id != plan.plan_id
            or decision.run_id != run.run_id
            or decision.observed_revision != run.revision
            or decision.step_id != step_id
            or decision.assessment_id != assessment.assessment_id
        ):
            raise PlanStepHandlingPreparationInvariantError(
                "WP030 result does not match the supplied Plan, Run revision, and step"
            )
        if (update is None) != (advancement is None):
            raise PlanStepHandlingPreparationInvariantError(
                "WP030 progress update and advancement must both exist or be absent"
            )
        if update is None:
            return
        assert advancement is not None
        if (
            update.run_id != run.run_id
            or update.expected_revision != run.revision
            or update.step_id != step_id
            or advancement.source_update_id != update.update_id
            or advancement.source_revision != run.revision
            or advancement.source_revision != update.expected_revision
        ):
            raise PlanStepHandlingPreparationInvariantError(
                "WP030 update and advancement do not match the source operation"
            )
        cls._validate_fresh_advancement(plan, run, advancement)

    @staticmethod
    def _validate_fresh_advancement(
        plan: Plan,
        run: PlanRun,
        advancement: PlanRunProgressAdvanceResult,
    ) -> None:
        updated_run = advancement.updated_run
        control = advancement.control_decision
        if not isinstance(updated_run, PlanRun):
            raise PlanStepHandlingPreparationInvariantError(
                "WP030 advancement must contain a canonical PlanRun"
            )
        if not isinstance(control, ControlDecision):
            raise PlanStepHandlingPreparationInvariantError(
                "WP030 advancement must contain a canonical ControlDecision"
            )
        if (
            updated_run.plan_id != plan.plan_id
            or updated_run.run_id != run.run_id
            or updated_run.goal_id != run.goal_id
            or updated_run.revision != run.revision + 1
            or control.plan_id != plan.plan_id
            or control.run_id != updated_run.run_id
            or control.observed_revision != updated_run.revision
        ):
            raise PlanStepHandlingPreparationInvariantError(
                "WP030 successor Run and fresh control lineage do not match"
            )
        try:
            validate_control_decision_current(plan, updated_run, control)
        except (PlanControlError, PlanRunError) as exc:
            raise PlanStepHandlingPreparationInvariantError(
                "WP030 fresh control is not current for its successor Run"
            ) from exc

    @staticmethod
    def _validate_handling_result(
        plan: Plan,
        advancement: PlanRunProgressAdvanceResult,
        preparation: StepHandlingPreparationResult,
    ) -> None:
        if not isinstance(preparation, StepHandlingPreparationResult):
            raise PlanStepHandlingPreparationInvariantError(
                "WP014 preparer must return a StepHandlingPreparationResult"
            )
        updated_run = advancement.updated_run
        control = advancement.control_decision
        if (
            preparation.plan_id != plan.plan_id
            or preparation.run_id != updated_run.run_id
            or preparation.observed_revision != updated_run.revision
            or preparation.step_id != control.selected_step_id
        ):
            raise PlanStepHandlingPreparationInvariantError(
                "WP014 result does not match the exact successor selection"
            )
        try:
            validate_step_handling_preparation_current(
                plan,
                updated_run,
                preparation,
            )
        except (PlanHandlingError, PlanControlError, PlanRunError) as exc:
            raise PlanStepHandlingPreparationInvariantError(
                "WP014 result is not current for the exact successor selection"
            ) from exc

    @staticmethod
    def _result(
        progress: PlanStepProgressAdvancementResult,
        preparation: StepHandlingPreparationResult | None,
    ) -> PlanStepHandlingPreparationResult:
        return PlanStepHandlingPreparationResult(
            assessment=progress.assessment,
            transition_decision=progress.transition_decision,
            progress_update=progress.progress_update,
            advancement_result=progress.advancement_result,
            handling_preparation=preparation,
        )
