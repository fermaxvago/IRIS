"""Bounded WP029-to-WP023 conditional progress advancement."""

from __future__ import annotations

from iris.outcome_assessment import StepOutcomeAssessment
from iris.plan_run_advancement import (
    PlanRunProgressAdvancer,
    PlanRunProgressAdvanceResult,
)
from iris.plan_runs import PlanRun, StepProgress, StepProgressUpdate
from iris.plan_step_progress_advancement.errors import (
    PlanStepProgressAdvancementInvariantError,
)
from iris.plan_step_progress_advancement.models import (
    PlanStepProgressAdvancementResult,
)
from iris.plan_step_progress_update_preparation import (
    PlanStepProgressUpdatePreparationResult,
    PlanStepProgressUpdatePreparer,
)
from iris.planning import Plan
from iris.step_progress_transition import StepProgressTransitionDecision


class PlanStepProgressAdvancementComposer:
    """Prepare once, conditionally advance once, preserve control, and stop."""

    def __init__(
        self,
        *,
        progress_update_preparer: PlanStepProgressUpdatePreparer | None = None,
        progress_advancer: PlanRunProgressAdvancer | None = None,
    ) -> None:
        if progress_update_preparer is not None and not isinstance(
            progress_update_preparer, PlanStepProgressUpdatePreparer
        ):
            raise TypeError(
                "progress_update_preparer must be a PlanStepProgressUpdatePreparer"
            )
        if progress_advancer is not None and not isinstance(
            progress_advancer, PlanRunProgressAdvancer
        ):
            raise TypeError("progress_advancer must be a PlanRunProgressAdvancer")
        self._progress_update_preparer = (
            PlanStepProgressUpdatePreparer()
            if progress_update_preparer is None
            else progress_update_preparer
        )
        self._progress_advancer = (
            PlanRunProgressAdvancer()
            if progress_advancer is None
            else progress_advancer
        )

    def compose(
        self,
        plan: Plan,
        run: PlanRun,
        step_id: str,
    ) -> PlanStepProgressAdvancementResult:
        """Return WP029 artifacts and zero or one exact WP023 advancement."""

        self._validate_input_types(plan, run, step_id)
        preparation = self._progress_update_preparer.prepare(plan, run, step_id)
        self._validate_preparation(plan, run, step_id, preparation)

        update = preparation.progress_update
        if update is None:
            return PlanStepProgressAdvancementResult(
                preparation.assessment,
                preparation.transition_decision,
                None,
                None,
            )

        advancement = self._progress_advancer.advance(plan, run, update)
        self._validate_advancement(plan, run, update, advancement)
        return PlanStepProgressAdvancementResult(
            preparation.assessment,
            preparation.transition_decision,
            update,
            advancement,
        )

    @staticmethod
    def _validate_input_types(plan: Plan, run: PlanRun, step_id: str) -> None:
        if not isinstance(plan, Plan):
            raise TypeError("plan must be a Plan")
        if not isinstance(run, PlanRun):
            raise TypeError("run must be a PlanRun")
        if not isinstance(step_id, str):
            raise TypeError("step_id must be a string")

    @staticmethod
    def _validate_preparation(
        plan: Plan,
        run: PlanRun,
        step_id: str,
        preparation: PlanStepProgressUpdatePreparationResult,
    ) -> None:
        if not isinstance(preparation, PlanStepProgressUpdatePreparationResult):
            raise PlanStepProgressAdvancementInvariantError(
                "WP029 preparer must return a PlanStepProgressUpdatePreparationResult"
            )
        assessment = preparation.assessment
        decision = preparation.transition_decision
        update = preparation.progress_update
        if not isinstance(assessment, StepOutcomeAssessment) or not isinstance(
            decision, StepProgressTransitionDecision
        ):
            raise PlanStepProgressAdvancementInvariantError(
                "WP029 result must contain canonical assessment and decision types"
            )
        if update is not None and not isinstance(update, StepProgressUpdate):
            raise PlanStepProgressAdvancementInvariantError(
                "WP029 progress_update must be a StepProgressUpdate or None"
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
            raise PlanStepProgressAdvancementInvariantError(
                "WP029 result does not match the supplied Plan, Run revision, and step"
            )
        if update is not None and (
            update.run_id != run.run_id
            or update.expected_revision != run.revision
            or update.step_id != step_id
            or update.new_state is not decision.target_state
            or update.evidence_ids != assessment.evidence_ids
        ):
            raise PlanStepProgressAdvancementInvariantError(
                "WP029 update does not match the supplied Run and preparation"
            )

    @classmethod
    def _validate_advancement(
        cls,
        plan: Plan,
        run: PlanRun,
        update: StepProgressUpdate,
        advancement: PlanRunProgressAdvanceResult,
    ) -> None:
        if not isinstance(advancement, PlanRunProgressAdvanceResult):
            raise PlanStepProgressAdvancementInvariantError(
                "WP023 advancer must return a PlanRunProgressAdvanceResult"
            )
        updated_run = advancement.updated_run
        control = advancement.control_decision
        if not isinstance(updated_run, PlanRun):
            raise PlanStepProgressAdvancementInvariantError(
                "WP023 result must contain a canonical PlanRun"
            )
        if (
            advancement.source_update_id != update.update_id
            or advancement.source_revision != update.expected_revision
            or advancement.source_revision != run.revision
            or updated_run.plan_id != plan.plan_id
            or updated_run.run_id != run.run_id
            or updated_run.goal_id != run.goal_id
            or updated_run.revision != run.revision + 1
            or updated_run.created_at != run.created_at
            or updated_run.updated_at != update.updated_at
            or control.plan_id != plan.plan_id
            or control.run_id != run.run_id
            or control.observed_revision != updated_run.revision
        ):
            raise PlanStepProgressAdvancementInvariantError(
                "WP023 result does not match the exact update and source Run lineage"
            )
        cls._validate_successor_state(run, update, updated_run)

    @staticmethod
    def _validate_successor_state(
        run: PlanRun,
        update: StepProgressUpdate,
        updated_run: PlanRun,
    ) -> None:
        if (
            updated_run.observations != run.observations
            or updated_run.blockers != run.blockers
        ):
            raise PlanStepProgressAdvancementInvariantError(
                "WP023 progress advancement changed observations or blockers"
            )

        source = {item.step_id: item for item in run.step_progress}
        successor = {item.step_id: item for item in updated_run.step_progress}
        if source.keys() != successor.keys():
            raise PlanStepProgressAdvancementInvariantError(
                "WP023 progress advancement changed the StepProgress identity set"
            )
        target = successor.get(update.step_id)
        if target is None or not isinstance(target, StepProgress):
            raise PlanStepProgressAdvancementInvariantError(
                "WP023 successor Run is missing the updated StepProgress"
            )
        if (
            target.state is not update.new_state
            or target.changed_at != update.updated_at
            or target.evidence_ids != update.evidence_ids
        ):
            raise PlanStepProgressAdvancementInvariantError(
                "WP023 successor StepProgress does not reflect the exact update"
            )
        if any(
            successor[step_id] != progress
            for step_id, progress in source.items()
            if step_id != update.step_id
        ):
            raise PlanStepProgressAdvancementInvariantError(
                "WP023 progress advancement changed an unrelated StepProgress"
            )
