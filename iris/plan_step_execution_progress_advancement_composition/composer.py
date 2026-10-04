"""Compose one bounded WP041 reaction with the existing WP023 boundary."""

from __future__ import annotations

from datetime import datetime

from iris.context import ContextBudget, ContextCandidate, ContextUncertainty
from iris.execution.models import ExecutionInput
from iris.orchestrator import HandlerAvailability
from iris.outcome_assessment import StepOutcomeAssessment
from iris.plan_control import ControlDecision
from iris.plan_run_advancement import (
    PlanRunProgressAdvancer,
    PlanRunProgressAdvanceResult,
)
from iris.plan_runs import PlanRun, StepProgress, StepProgressUpdate
from iris.plan_step_execution_progress_advancement_composition.errors import (
    PlanStepExecutionProgressAdvancementCompositionInvariantError,
)
from iris.plan_step_execution_progress_advancement_composition.models import (
    PlanStepExecutionProgressAdvancementCompositionResult,
)
from iris.plan_step_execution_progress_update_composition import (
    PlanStepExecutionProgressUpdateComposer,
    PlanStepExecutionProgressUpdateCompositionResult,
)
from iris.plan_step_execution_result_recording import (
    PlanStepExecutionResultRecordingResult,
)
from iris.planning import Plan
from iris.step_progress_transition import StepProgressTransitionDecision


class PlanStepExecutionProgressAdvancementComposer:
    """Append at most one exact WP023 advancement to one WP041 reaction."""

    def __init__(
        self,
        *,
        progress_update_composer: PlanStepExecutionProgressUpdateComposer,
        progress_advancer: PlanRunProgressAdvancer | None = None,
    ) -> None:
        if not isinstance(
            progress_update_composer,
            PlanStepExecutionProgressUpdateComposer,
        ):
            raise TypeError(
                "progress_update_composer must be a "
                "PlanStepExecutionProgressUpdateComposer"
            )
        if progress_advancer is not None and not isinstance(
            progress_advancer, PlanRunProgressAdvancer
        ):
            raise TypeError("progress_advancer must be a PlanRunProgressAdvancer")
        self._progress_update_composer = progress_update_composer
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
        *,
        candidates: tuple[ContextCandidate, ...],
        budget: ContextBudget,
        uncertainties: tuple[ContextUncertainty, ...] = (),
        created_at: datetime,
        availability: HandlerAvailability,
        execution_input: ExecutionInput | None = None,
    ) -> PlanStepExecutionProgressAdvancementCompositionResult:
        """Invoke WP041 once, optionally advance its exact update, then stop."""

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
        update_composition = self._progress_update_composer.compose(
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
        self._validate_update_composition(
            plan,
            run,
            step_id,
            update_composition,
        )

        update = update_composition.post_recording_progress_update
        if update is None:
            return self._result(update_composition, None)

        recording = update_composition.execution_recording_result
        if recording is None:  # guarded by delegated-result validation
            raise PlanStepExecutionProgressAdvancementCompositionInvariantError(
                "post-recording update requires its exact recording"
            )
        advancement = self._progress_advancer.advance(
            plan,
            recording.recorded_run,
            update,
        )
        self._validate_advancement(
            plan,
            recording.recorded_run,
            update,
            advancement,
        )
        return self._result(update_composition, advancement)

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
    def _validate_update_composition(
        plan: Plan,
        source_run: PlanRun,
        processed_step_id: str,
        result: PlanStepExecutionProgressUpdateCompositionResult,
    ) -> None:
        invariant = PlanStepExecutionProgressAdvancementCompositionInvariantError
        if not isinstance(result, PlanStepExecutionProgressUpdateCompositionResult):
            raise invariant(
                "WP041 must return a PlanStepExecutionProgressUpdateCompositionResult"
            )
        try:
            result.__post_init__()
        except (RuntimeError, TypeError, ValueError) as exc:
            raise invariant("WP041 result violates its canonical contract") from exc

        inherited_assessment = result.assessment
        inherited_decision = result.transition_decision
        if not isinstance(
            inherited_assessment, StepOutcomeAssessment
        ) or not isinstance(inherited_decision, StepProgressTransitionDecision):
            raise invariant(
                "WP041 result must preserve canonical inherited decision artifacts"
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
                "WP041 result does not match the supplied Plan, source Run, and step"
            )

        update = result.post_recording_progress_update
        if update is None:
            return
        recording = result.execution_recording_result
        assessment = result.post_recording_assessment
        decision = result.post_recording_transition_decision
        if (
            not isinstance(update, StepProgressUpdate)
            or not isinstance(recording, PlanStepExecutionResultRecordingResult)
            or not isinstance(assessment, StepOutcomeAssessment)
            or not isinstance(decision, StepProgressTransitionDecision)
        ):
            raise invariant("WP041 update lineage contains noncanonical artifacts")
        recorded_run = recording.recorded_run
        if (
            recording.plan_id != plan.plan_id
            or update.run_id != recorded_run.run_id
            or update.run_id != recording.run_id
            or update.run_id != assessment.run_id
            or update.run_id != decision.run_id
            or update.expected_revision != recorded_run.revision
            or update.expected_revision != assessment.run_revision
            or update.expected_revision != decision.observed_revision
            or update.step_id != recording.step_id
            or update.step_id != assessment.step_id
            or update.step_id != decision.step_id
            or update.new_state is not decision.target_state
            or update.evidence_ids != assessment.evidence_ids
        ):
            raise invariant("WP041 update contradicts its exact post-recording lineage")

    @classmethod
    def _validate_advancement(
        cls,
        plan: Plan,
        source_run: PlanRun,
        update: StepProgressUpdate,
        advancement: PlanRunProgressAdvanceResult,
    ) -> None:
        invariant = PlanStepExecutionProgressAdvancementCompositionInvariantError
        if not isinstance(advancement, PlanRunProgressAdvanceResult):
            raise invariant("WP023 must return a PlanRunProgressAdvanceResult")
        try:
            advancement.__post_init__()
        except (RuntimeError, TypeError, ValueError) as exc:
            raise invariant("WP023 result violates its canonical contract") from exc
        updated_run = advancement.updated_run
        control = advancement.control_decision
        if not isinstance(updated_run, PlanRun) or not isinstance(
            control, ControlDecision
        ):
            raise invariant("WP023 result contains noncanonical artifacts")
        if (
            advancement.source_update_id != update.update_id
            or advancement.source_revision != update.expected_revision
            or advancement.source_revision != source_run.revision
            or updated_run.plan_id != plan.plan_id
            or updated_run.plan_id != source_run.plan_id
            or updated_run.run_id != source_run.run_id
            or updated_run.run_id != update.run_id
            or updated_run.goal_id != source_run.goal_id
            or updated_run.revision != source_run.revision + 1
            or updated_run.created_at != source_run.created_at
            or updated_run.updated_at != update.updated_at
            or control.plan_id != plan.plan_id
            or control.run_id != updated_run.run_id
            or control.observed_revision != updated_run.revision
        ):
            raise invariant(
                "WP023 result contradicts the exact update and recorded Run lineage"
            )
        cls._validate_successor_state(source_run, update, updated_run)

    @staticmethod
    def _validate_successor_state(
        source_run: PlanRun,
        update: StepProgressUpdate,
        updated_run: PlanRun,
    ) -> None:
        invariant = PlanStepExecutionProgressAdvancementCompositionInvariantError
        if (
            updated_run.observations != source_run.observations
            or updated_run.blockers != source_run.blockers
        ):
            raise invariant("WP023 changed observations or blockers")
        source = {item.step_id: item for item in source_run.step_progress}
        successor = {item.step_id: item for item in updated_run.step_progress}
        if source.keys() != successor.keys():
            raise invariant("WP023 changed the StepProgress identity set")
        target = successor.get(update.step_id)
        if target is None or not isinstance(target, StepProgress):
            raise invariant("WP023 successor is missing the target StepProgress")
        if (
            target.state is not update.new_state
            or target.changed_at != update.updated_at
            or target.evidence_ids != update.evidence_ids
        ):
            raise invariant("WP023 target StepProgress does not reflect the update")
        if any(
            successor[step_id] != progress
            for step_id, progress in source.items()
            if step_id != update.step_id
        ):
            raise invariant("WP023 changed an unrelated StepProgress")

    @staticmethod
    def _result(
        update_composition: PlanStepExecutionProgressUpdateCompositionResult,
        advancement: PlanRunProgressAdvanceResult | None,
    ) -> PlanStepExecutionProgressAdvancementCompositionResult:
        return PlanStepExecutionProgressAdvancementCompositionResult(
            assessment=update_composition.assessment,
            transition_decision=update_composition.transition_decision,
            progress_update=update_composition.progress_update,
            advancement_result=update_composition.advancement_result,
            handling_preparation=update_composition.handling_preparation,
            work_subject=update_composition.work_subject,
            context_snapshot=update_composition.context_snapshot,
            orchestration_decision=update_composition.orchestration_decision,
            execution_request=update_composition.execution_request,
            execution_binding=update_composition.execution_binding,
            execution_start_result=update_composition.execution_start_result,
            execution_recording_result=update_composition.execution_recording_result,
            post_recording_assessment=update_composition.post_recording_assessment,
            post_recording_transition_decision=(
                update_composition.post_recording_transition_decision
            ),
            post_recording_progress_update=(
                update_composition.post_recording_progress_update
            ),
            post_recording_advancement_result=advancement,
        )
