"""Compose one WP031 result with optional exact WP015 materialization."""

from __future__ import annotations

from collections.abc import Callable

from iris.outcome_assessment import StepOutcomeAssessment
from iris.plan_control import (
    ControlDecision,
    ControlDecisionKind,
    PlanControlError,
    validate_control_decision_current,
)
from iris.plan_handling import (
    PlanHandlingError,
    StepHandlingPreparationResult,
    validate_step_handling_preparation_current,
)
from iris.plan_run_advancement import PlanRunProgressAdvanceResult
from iris.plan_runs import PlanRun, PlanRunError, StepProgressUpdate
from iris.plan_step_handling_preparation import (
    PlanStepHandlingPreparationComposer,
    PlanStepHandlingPreparationResult,
)
from iris.plan_step_work_subject_materialization.errors import (
    PlanStepWorkSubjectMaterializationInvariantError,
)
from iris.plan_step_work_subject_materialization.models import (
    PlanStepWorkSubjectMaterializationResult,
)
from iris.planning import Plan
from iris.step_progress_transition import StepProgressTransitionDecision
from iris.work_identity import (
    PlanStepWorkReference,
    WorkSubject,
    WorkSubjectKind,
    work_subject_from_plan_step,
)

WorkSubjectAdapter = Callable[[Plan, PlanRun, str], WorkSubject]


class PlanStepWorkSubjectMaterializer:
    """React once through WP031, materialize selected work identity, stop."""

    def __init__(
        self,
        *,
        handling_preparation_composer: PlanStepHandlingPreparationComposer
        | None = None,
        work_subject_adapter: WorkSubjectAdapter | None = None,
    ) -> None:
        if handling_preparation_composer is not None and not isinstance(
            handling_preparation_composer, PlanStepHandlingPreparationComposer
        ):
            raise TypeError(
                "handling_preparation_composer must be a "
                "PlanStepHandlingPreparationComposer"
            )
        if work_subject_adapter is not None and not callable(work_subject_adapter):
            raise TypeError("work_subject_adapter must be callable")
        self._handling_preparation_composer = (
            PlanStepHandlingPreparationComposer()
            if handling_preparation_composer is None
            else handling_preparation_composer
        )
        self._work_subject_adapter = (
            work_subject_from_plan_step
            if work_subject_adapter is None
            else work_subject_adapter
        )

    def materialize(
        self,
        plan: Plan,
        run: PlanRun,
        step_id: str,
    ) -> PlanStepWorkSubjectMaterializationResult:
        """Return WP031 artifacts and zero or one exact WP015 WorkSubject."""

        self._validate_input_types(plan, run, step_id)
        handling = self._handling_preparation_composer.compose(plan, run, step_id)
        self._validate_handling_result(plan, run, step_id, handling)

        advancement = handling.advancement_result
        if advancement is None:
            return self._result(handling, None)

        control = advancement.control_decision
        if control.kind is not ControlDecisionKind.STEP_SELECTED:
            return self._result(handling, None)

        selected_step_id = control.selected_step_id
        if selected_step_id is None:
            raise PlanStepWorkSubjectMaterializationInvariantError(
                "fresh STEP_SELECTED control must identify one PlanStep"
            )
        try:
            subject = self._work_subject_adapter(
                plan,
                advancement.updated_run,
                selected_step_id,
            )
        except Exception as exc:
            raise PlanStepWorkSubjectMaterializationInvariantError(
                "WP015 could not materialize the exact fresh selected work"
            ) from exc
        self._validate_work_subject(plan, advancement, subject)
        return self._result(handling, subject)

    @staticmethod
    def _validate_input_types(plan: Plan, run: PlanRun, step_id: str) -> None:
        if not isinstance(plan, Plan):
            raise TypeError("plan must be a Plan")
        if not isinstance(run, PlanRun):
            raise TypeError("run must be a PlanRun")
        if not isinstance(step_id, str):
            raise TypeError("step_id must be a string")

    @classmethod
    def _validate_handling_result(
        cls,
        plan: Plan,
        run: PlanRun,
        step_id: str,
        result: PlanStepHandlingPreparationResult,
    ) -> None:
        if not isinstance(result, PlanStepHandlingPreparationResult):
            raise PlanStepWorkSubjectMaterializationInvariantError(
                "WP031 composer must return a PlanStepHandlingPreparationResult"
            )
        assessment = result.assessment
        decision = result.transition_decision
        update = result.progress_update
        advancement = result.advancement_result
        preparation = result.handling_preparation
        if not isinstance(assessment, StepOutcomeAssessment) or not isinstance(
            decision, StepProgressTransitionDecision
        ):
            raise PlanStepWorkSubjectMaterializationInvariantError(
                "WP031 result must contain canonical assessment and decision types"
            )
        if update is not None and not isinstance(update, StepProgressUpdate):
            raise PlanStepWorkSubjectMaterializationInvariantError(
                "WP031 progress_update must be a StepProgressUpdate or None"
            )
        if advancement is not None and not isinstance(
            advancement, PlanRunProgressAdvanceResult
        ):
            raise PlanStepWorkSubjectMaterializationInvariantError(
                "WP031 advancement_result must be a PlanRunProgressAdvanceResult or None"
            )
        if preparation is not None and not isinstance(
            preparation, StepHandlingPreparationResult
        ):
            raise PlanStepWorkSubjectMaterializationInvariantError(
                "WP031 handling_preparation must be canonical or None"
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
            raise PlanStepWorkSubjectMaterializationInvariantError(
                "WP031 result does not match the supplied Plan, Run revision, and step"
            )
        if (update is None) != (advancement is None):
            raise PlanStepWorkSubjectMaterializationInvariantError(
                "WP031 progress update and advancement must both exist or be absent"
            )
        if update is None:
            if preparation is not None:
                raise PlanStepWorkSubjectMaterializationInvariantError(
                    "WP031 cannot prepare handling without advancement"
                )
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
            raise PlanStepWorkSubjectMaterializationInvariantError(
                "WP031 update and advancement do not match the source operation"
            )
        cls._validate_fresh_advancement(plan, run, advancement)

        selected = (
            advancement.control_decision.kind is ControlDecisionKind.STEP_SELECTED
        )
        if selected != (preparation is not None):
            raise PlanStepWorkSubjectMaterializationInvariantError(
                "WP031 handling preparation must exactly match fresh selection"
            )
        if preparation is not None:
            cls._validate_preparation(plan, advancement, preparation)

    @staticmethod
    def _validate_fresh_advancement(
        plan: Plan,
        run: PlanRun,
        advancement: PlanRunProgressAdvanceResult,
    ) -> None:
        updated_run = advancement.updated_run
        control = advancement.control_decision
        if not isinstance(updated_run, PlanRun):
            raise PlanStepWorkSubjectMaterializationInvariantError(
                "WP031 advancement must contain a canonical PlanRun"
            )
        if not isinstance(control, ControlDecision):
            raise PlanStepWorkSubjectMaterializationInvariantError(
                "WP031 advancement must contain a canonical ControlDecision"
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
            raise PlanStepWorkSubjectMaterializationInvariantError(
                "WP031 successor Run and fresh control lineage do not match"
            )
        try:
            validate_control_decision_current(plan, updated_run, control)
        except (PlanControlError, PlanRunError) as exc:
            raise PlanStepWorkSubjectMaterializationInvariantError(
                "WP031 fresh control is not current for its successor Run"
            ) from exc

    @staticmethod
    def _validate_preparation(
        plan: Plan,
        advancement: PlanRunProgressAdvanceResult,
        preparation: StepHandlingPreparationResult,
    ) -> None:
        updated_run = advancement.updated_run
        control = advancement.control_decision
        if (
            preparation.plan_id != plan.plan_id
            or preparation.run_id != updated_run.run_id
            or preparation.observed_revision != updated_run.revision
            or preparation.step_id != control.selected_step_id
        ):
            raise PlanStepWorkSubjectMaterializationInvariantError(
                "WP031 preparation does not match the exact fresh selection"
            )
        try:
            validate_step_handling_preparation_current(plan, updated_run, preparation)
        except (PlanHandlingError, PlanControlError, PlanRunError) as exc:
            raise PlanStepWorkSubjectMaterializationInvariantError(
                "WP031 preparation is not current for the exact successor selection"
            ) from exc

    @staticmethod
    def _validate_work_subject(
        plan: Plan,
        advancement: PlanRunProgressAdvanceResult,
        subject: WorkSubject,
    ) -> None:
        if not isinstance(subject, WorkSubject):
            raise PlanStepWorkSubjectMaterializationInvariantError(
                "WP015 adapter must return a WorkSubject"
            )
        control = advancement.control_decision
        reference = subject.reference
        if (
            subject.kind is not WorkSubjectKind.PLAN_STEP
            or not isinstance(reference, PlanStepWorkReference)
            or reference.plan_id != plan.plan_id
            or reference.run_id != advancement.updated_run.run_id
            or reference.step_id != control.selected_step_id
            or subject.origin is not None
        ):
            raise PlanStepWorkSubjectMaterializationInvariantError(
                "WP015 subject does not identify the exact selected work without origin"
            )

    @staticmethod
    def _result(
        handling: PlanStepHandlingPreparationResult,
        subject: WorkSubject | None,
    ) -> PlanStepWorkSubjectMaterializationResult:
        return PlanStepWorkSubjectMaterializationResult(
            assessment=handling.assessment,
            transition_decision=handling.transition_decision,
            progress_update=handling.progress_update,
            advancement_result=handling.advancement_result,
            handling_preparation=handling.handling_preparation,
            work_subject=subject,
        )
