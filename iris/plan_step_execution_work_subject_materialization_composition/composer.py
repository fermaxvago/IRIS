"""Compose one bounded WP043 result with the existing WP015 adapter."""

from __future__ import annotations

from collections.abc import Callable
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
    StepHandlingPreparationResult,
    validate_step_handling_preparation_current,
)
from iris.plan_runs import PlanRun, PlanRunError
from iris.plan_step_execution_handling_preparation_composition import (
    PlanStepExecutionHandlingPreparationComposer,
    PlanStepExecutionHandlingPreparationCompositionResult,
)
from iris.plan_step_execution_work_subject_materialization_composition.errors import (
    PlanStepExecutionWorkSubjectMaterializationCompositionInvariantError,
)
from iris.plan_step_execution_work_subject_materialization_composition.models import (
    PlanStepExecutionWorkSubjectMaterializationCompositionResult,
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


class PlanStepExecutionWorkSubjectMaterializationComposer:
    """Append at most one exact WP015 subject to one WP043 reaction."""

    def __init__(
        self,
        *,
        handling_preparation_composer: PlanStepExecutionHandlingPreparationComposer,
        work_subject_adapter: WorkSubjectAdapter | None = None,
    ) -> None:
        if not isinstance(
            handling_preparation_composer,
            PlanStepExecutionHandlingPreparationComposer,
        ):
            raise TypeError(
                "handling_preparation_composer must be a "
                "PlanStepExecutionHandlingPreparationComposer"
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
    ) -> PlanStepExecutionWorkSubjectMaterializationCompositionResult:
        """Invoke WP043 once, optionally materialize selected identity, stop."""

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
        handling = self._handling_preparation_composer.compose(
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
        self._validate_handling_result(plan, run, step_id, handling)

        advancement = handling.post_recording_advancement_result
        if advancement is None:
            return self._result(handling, None)

        control = advancement.control_decision
        if control.kind is not ControlDecisionKind.STEP_SELECTED:
            return self._result(handling, None)

        selected_step_id = control.selected_step_id
        if selected_step_id is None:
            raise (
                PlanStepExecutionWorkSubjectMaterializationCompositionInvariantError(
                    "fresh post-recording STEP_SELECTED control must identify one "
                    "PlanStep"
                )
            )
        try:
            subject = self._work_subject_adapter(
                plan,
                advancement.updated_run,
                selected_step_id,
            )
        except Exception as exc:
            raise (
                PlanStepExecutionWorkSubjectMaterializationCompositionInvariantError(
                    "WP015 could not materialize the exact post-recording selected work"
                )
            ) from exc
        self._validate_work_subject(plan, advancement.updated_run, control, subject)
        return self._result(handling, subject)

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

    @classmethod
    def _validate_handling_result(
        cls,
        plan: Plan,
        source_run: PlanRun,
        processed_step_id: str,
        result: PlanStepExecutionHandlingPreparationCompositionResult,
    ) -> None:
        invariant = PlanStepExecutionWorkSubjectMaterializationCompositionInvariantError
        if not isinstance(
            result, PlanStepExecutionHandlingPreparationCompositionResult
        ):
            raise invariant(
                "WP043 must return a "
                "PlanStepExecutionHandlingPreparationCompositionResult"
            )
        try:
            result.__post_init__()
        except (RuntimeError, TypeError, ValueError) as exc:
            raise invariant("WP043 result violates its canonical contract") from exc

        assessment = result.assessment
        decision = result.transition_decision
        if not isinstance(assessment, StepOutcomeAssessment) or not isinstance(
            decision, StepProgressTransitionDecision
        ):
            raise invariant(
                "WP043 result must preserve canonical inherited decision artifacts"
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
                "WP043 result does not match the supplied Plan, source Run, and step"
            )

        advancement = result.post_recording_advancement_result
        if advancement is None:
            return
        successor = advancement.updated_run
        control = advancement.control_decision
        if not isinstance(successor, PlanRun) or not isinstance(
            control, ControlDecision
        ):
            raise invariant("WP043 advancement contains noncanonical artifacts")
        if (
            successor.plan_id != plan.plan_id
            or successor.run_id != source_run.run_id
            or successor.goal_id != source_run.goal_id
            or control.plan_id != plan.plan_id
            or control.run_id != successor.run_id
            or control.observed_revision != successor.revision
        ):
            raise invariant(
                "WP043 successor Run and fresh control contradict the operation"
            )
        try:
            validate_control_decision_current(plan, successor, control)
        except (PlanControlError, PlanRunError, TypeError) as exc:
            raise invariant(
                "WP043 fresh control is not current for its exact successor Run"
            ) from exc

        selected = control.kind is ControlDecisionKind.STEP_SELECTED
        preparation = result.post_recording_handling_preparation
        if selected != (preparation is not None):
            raise invariant(
                "WP043 post-recording handling preparation must exactly match fresh "
                "selection"
            )
        if not selected:
            return
        if not isinstance(preparation, StepHandlingPreparationResult):
            raise invariant(
                "WP043 selected path must contain canonical handling preparation"
            )
        if control.selected_step_id is None:
            raise invariant("fresh STEP_SELECTED control must identify one PlanStep")
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
                "WP043 preparation contradicts the exact post-recording selection"
            )
        try:
            validate_step_handling_preparation_current(
                plan,
                successor,
                preparation,
            )
        except (PlanHandlingError, PlanControlError, PlanRunError, TypeError) as exc:
            raise invariant(
                "WP043 preparation is not current for the exact successor selection"
            ) from exc

    @staticmethod
    def _validate_work_subject(
        plan: Plan,
        successor: PlanRun,
        control: ControlDecision,
        subject: WorkSubject,
    ) -> None:
        invariant = PlanStepExecutionWorkSubjectMaterializationCompositionInvariantError
        if not isinstance(subject, WorkSubject):
            raise invariant("WP015 adapter must return a WorkSubject")
        reference = subject.reference
        if (
            subject.kind is not WorkSubjectKind.PLAN_STEP
            or not isinstance(reference, PlanStepWorkReference)
            or reference.plan_id != plan.plan_id
            or reference.plan_id != successor.plan_id
            or reference.plan_id != control.plan_id
            or reference.run_id != successor.run_id
            or reference.run_id != control.run_id
            or reference.step_id != control.selected_step_id
            or subject.origin is not None
        ):
            raise invariant(
                "WP015 subject does not identify the exact post-recording selected "
                "work without origin"
            )

    @staticmethod
    def _result(
        handling: PlanStepExecutionHandlingPreparationCompositionResult,
        subject: WorkSubject | None,
    ) -> PlanStepExecutionWorkSubjectMaterializationCompositionResult:
        return PlanStepExecutionWorkSubjectMaterializationCompositionResult(
            assessment=handling.assessment,
            transition_decision=handling.transition_decision,
            progress_update=handling.progress_update,
            advancement_result=handling.advancement_result,
            handling_preparation=handling.handling_preparation,
            work_subject=handling.work_subject,
            context_snapshot=handling.context_snapshot,
            orchestration_decision=handling.orchestration_decision,
            execution_request=handling.execution_request,
            execution_binding=handling.execution_binding,
            execution_start_result=handling.execution_start_result,
            execution_recording_result=handling.execution_recording_result,
            post_recording_assessment=handling.post_recording_assessment,
            post_recording_transition_decision=(
                handling.post_recording_transition_decision
            ),
            post_recording_progress_update=(handling.post_recording_progress_update),
            post_recording_advancement_result=(
                handling.post_recording_advancement_result
            ),
            post_recording_handling_preparation=(
                handling.post_recording_handling_preparation
            ),
            post_recording_work_subject=subject,
        )
