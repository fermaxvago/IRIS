"""Compose one bounded WP044 result with the existing WP016 authority."""

from __future__ import annotations

from datetime import datetime

from iris.context import (
    ContextBudget,
    ContextCandidate,
    ContextEngine,
    ContextSnapshot,
    ContextUncertainty,
)
from iris.execution import ExecutionResult
from iris.execution.models import ExecutionInput
from iris.memory.models import utc_time
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
from iris.plan_step_execution_context_materialization_composition.errors import (
    PlanStepExecutionContextMaterializationCompositionInvariantError,
)
from iris.plan_step_execution_context_materialization_composition.models import (
    PlanStepExecutionContextMaterializationCompositionResult,
)
from iris.plan_step_execution_work_subject_materialization_composition import (
    PlanStepExecutionWorkSubjectMaterializationComposer,
    PlanStepExecutionWorkSubjectMaterializationCompositionResult,
)
from iris.planning import Plan
from iris.step_progress_transition import StepProgressTransitionDecision
from iris.work_identity import PlanStepWorkReference, WorkSubject, WorkSubjectKind


class PlanStepExecutionContextMaterializationComposer:
    """Append at most one exact WP016 snapshot to one WP044 result."""

    def __init__(
        self,
        *,
        work_subject_materialization_composer: (
            PlanStepExecutionWorkSubjectMaterializationComposer
        ),
        context_engine: ContextEngine | None = None,
    ) -> None:
        if not isinstance(
            work_subject_materialization_composer,
            PlanStepExecutionWorkSubjectMaterializationComposer,
        ):
            raise TypeError(
                "work_subject_materialization_composer must be a "
                "PlanStepExecutionWorkSubjectMaterializationComposer"
            )
        if context_engine is not None and not isinstance(context_engine, ContextEngine):
            raise TypeError("context_engine must be a ContextEngine")
        self._work_subject_materialization_composer = (
            work_subject_materialization_composer
        )
        self._context_engine = (
            ContextEngine() if context_engine is None else context_engine
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
    ) -> PlanStepExecutionContextMaterializationCompositionResult:
        """Invoke WP044 once, contextualize its exact optional subject, stop."""

        self._validate_input_types(
            plan,
            run,
            step_id,
            candidates,
            budget,
            uncertainties,
            created_at,
            availability,
            post_recording_candidates,
            post_recording_budget,
            post_recording_uncertainties,
            post_recording_created_at,
        )
        work = self._work_subject_materialization_composer.compose(
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
        self._validate_work_result(plan, run, step_id, work)

        subject = work.post_recording_work_subject
        if subject is None:
            return self._result(work, None)

        self._validate_context_causality(work, post_recording_created_at)
        snapshot = self._context_engine.build(
            subject=subject,
            candidates=post_recording_candidates,
            budget=post_recording_budget,
            uncertainties=post_recording_uncertainties,
            created_at=post_recording_created_at,
        )
        self._validate_snapshot(
            subject,
            post_recording_budget,
            post_recording_created_at,
            snapshot,
        )
        return self._result(work, snapshot)

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
        post_recording_candidates: tuple[ContextCandidate, ...],
        post_recording_budget: ContextBudget,
        post_recording_uncertainties: tuple[ContextUncertainty, ...],
        post_recording_created_at: datetime,
    ) -> None:
        if not isinstance(plan, Plan):
            raise TypeError("plan must be a Plan")
        if not isinstance(run, PlanRun):
            raise TypeError("run must be a PlanRun")
        if not isinstance(step_id, str):
            raise TypeError("step_id must be a string")
        for name, candidate_values in (
            ("candidates", candidates),
            ("post_recording_candidates", post_recording_candidates),
        ):
            if not isinstance(candidate_values, tuple) or any(
                not isinstance(candidate, ContextCandidate)
                for candidate in candidate_values
            ):
                raise TypeError(f"{name} must be a tuple of ContextCandidate")
        if not isinstance(budget, ContextBudget):
            raise TypeError("budget must be ContextBudget")
        if not isinstance(post_recording_budget, ContextBudget):
            raise TypeError("post_recording_budget must be ContextBudget")
        for name, uncertainty_values in (
            ("uncertainties", uncertainties),
            ("post_recording_uncertainties", post_recording_uncertainties),
        ):
            if not isinstance(uncertainty_values, tuple) or any(
                not isinstance(uncertainty, ContextUncertainty)
                for uncertainty in uncertainty_values
            ):
                raise TypeError(f"{name} must be a tuple of ContextUncertainty")
        if not isinstance(created_at, datetime):
            raise TypeError("created_at must be a datetime")
        if not isinstance(post_recording_created_at, datetime):
            raise TypeError("post_recording_created_at must be a datetime")
        if not isinstance(availability, HandlerAvailability):
            raise TypeError("availability must be a HandlerAvailability")

    @classmethod
    def _validate_work_result(
        cls,
        plan: Plan,
        source_run: PlanRun,
        processed_step_id: str,
        result: PlanStepExecutionWorkSubjectMaterializationCompositionResult,
    ) -> None:
        invariant = PlanStepExecutionContextMaterializationCompositionInvariantError
        if not isinstance(
            result,
            PlanStepExecutionWorkSubjectMaterializationCompositionResult,
        ):
            raise invariant(
                "WP044 must return a "
                "PlanStepExecutionWorkSubjectMaterializationCompositionResult"
            )
        try:
            result.__post_init__()
        except (RuntimeError, TypeError, ValueError) as exc:
            raise invariant("WP044 result violates its canonical contract") from exc

        assessment = result.assessment
        decision = result.transition_decision
        if not isinstance(assessment, StepOutcomeAssessment) or not isinstance(
            decision, StepProgressTransitionDecision
        ):
            raise invariant(
                "WP044 result must preserve canonical inherited decision artifacts"
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
                "WP044 result does not match the supplied Plan, source Run, and step"
            )

        advancement = result.post_recording_advancement_result
        subject = result.post_recording_work_subject
        if advancement is None:
            if subject is not None:
                raise invariant("post-recording WorkSubject requires exact advancement")
            return
        preparation = result.post_recording_handling_preparation
        successor = advancement.updated_run
        control = advancement.control_decision
        if not isinstance(successor, PlanRun) or not isinstance(
            control, ControlDecision
        ):
            raise invariant("WP044 advancement contains noncanonical artifacts")
        if (
            successor.plan_id != plan.plan_id
            or successor.run_id != source_run.run_id
            or successor.goal_id != source_run.goal_id
            or control.plan_id != plan.plan_id
            or control.run_id != successor.run_id
            or control.observed_revision != successor.revision
        ):
            raise invariant(
                "WP044 successor Run and fresh control contradict the operation"
            )
        try:
            validate_control_decision_current(plan, successor, control)
        except (PlanControlError, PlanRunError, TypeError) as exc:
            raise invariant(
                "WP044 fresh control is not current for its exact successor Run"
            ) from exc

        if control.kind is not ControlDecisionKind.STEP_SELECTED:
            if subject is not None or preparation is not None:
                raise invariant(
                    "WP044 non-selecting control cannot contain selected-work artifacts"
                )
            return
        if control.selected_step_id is None or subject is None:
            raise invariant(
                "WP044 fresh selection must identify and materialize one PlanStep"
            )

        if not isinstance(preparation, StepHandlingPreparationResult):
            raise invariant(
                "WP044 selected path must contain canonical handling preparation"
            )
        if (
            preparation.plan_id != plan.plan_id
            or preparation.run_id != successor.run_id
            or preparation.observed_revision != successor.revision
            or preparation.step_id != control.selected_step_id
        ):
            raise invariant(
                "WP044 preparation contradicts the exact post-recording selection"
            )
        try:
            validate_step_handling_preparation_current(plan, successor, preparation)
        except (PlanHandlingError, PlanControlError, PlanRunError, TypeError) as exc:
            raise invariant(
                "WP044 preparation is not current for the exact successor selection"
            ) from exc

        if not isinstance(subject, WorkSubject):
            raise invariant("WP044 must preserve a canonical WorkSubject")
        reference = subject.reference
        if (
            subject.kind is not WorkSubjectKind.PLAN_STEP
            or not isinstance(reference, PlanStepWorkReference)
            or reference.plan_id != plan.plan_id
            or reference.plan_id != successor.plan_id
            or reference.run_id != successor.run_id
            or reference.step_id != control.selected_step_id
            or subject.origin is not None
        ):
            raise invariant(
                "WP044 WorkSubject does not identify the exact fresh selected work"
            )

    @staticmethod
    def _validate_context_causality(
        result: PlanStepExecutionWorkSubjectMaterializationCompositionResult,
        created_at: datetime,
    ) -> None:
        invariant = PlanStepExecutionContextMaterializationCompositionInvariantError
        start = result.execution_start_result
        if start is None or not isinstance(start.execution_result, ExecutionResult):
            raise invariant(
                "post-recording Context requires the exact completed execution"
            )
        instant = utc_time(created_at, "post_recording_created_at")
        if instant < start.execution_result.completed_at:
            raise invariant(
                "post-recording Context cannot predate the execution that enabled "
                "the fresh selection"
            )

    @staticmethod
    def _validate_snapshot(
        subject: WorkSubject,
        budget: ContextBudget,
        created_at: datetime,
        snapshot: ContextSnapshot,
    ) -> None:
        invariant = PlanStepExecutionContextMaterializationCompositionInvariantError
        if not isinstance(snapshot, ContextSnapshot):
            raise invariant("WP016 ContextEngine must return a ContextSnapshot")
        try:
            snapshot.__post_init__()
        except (RuntimeError, TypeError, ValueError) as exc:
            raise invariant("WP016 returned a noncanonical ContextSnapshot") from exc
        if snapshot.subject is not subject or snapshot.subject_id != subject.subject_id:
            raise invariant(
                "WP016 snapshot must preserve the exact WP044 WorkSubject owner"
            )
        if snapshot.budget != budget:
            raise invariant(
                "WP016 snapshot budget does not match post_recording_budget"
            )
        if snapshot.created_at != utc_time(
            created_at,
            "post_recording_created_at",
        ):
            raise invariant(
                "WP016 snapshot time does not match post_recording_created_at"
            )

    @staticmethod
    def _result(
        work: PlanStepExecutionWorkSubjectMaterializationCompositionResult,
        snapshot: ContextSnapshot | None,
    ) -> PlanStepExecutionContextMaterializationCompositionResult:
        return PlanStepExecutionContextMaterializationCompositionResult(
            assessment=work.assessment,
            transition_decision=work.transition_decision,
            progress_update=work.progress_update,
            advancement_result=work.advancement_result,
            handling_preparation=work.handling_preparation,
            work_subject=work.work_subject,
            context_snapshot=work.context_snapshot,
            orchestration_decision=work.orchestration_decision,
            execution_request=work.execution_request,
            execution_binding=work.execution_binding,
            execution_start_result=work.execution_start_result,
            execution_recording_result=work.execution_recording_result,
            post_recording_assessment=work.post_recording_assessment,
            post_recording_transition_decision=(
                work.post_recording_transition_decision
            ),
            post_recording_progress_update=work.post_recording_progress_update,
            post_recording_advancement_result=(work.post_recording_advancement_result),
            post_recording_handling_preparation=(
                work.post_recording_handling_preparation
            ),
            post_recording_work_subject=work.post_recording_work_subject,
            post_recording_context_snapshot=snapshot,
        )
