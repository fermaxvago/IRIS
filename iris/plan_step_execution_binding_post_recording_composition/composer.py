"""Compose the exact WP047 Step C request with the canonical WP024 binder."""

from __future__ import annotations

from datetime import datetime

from iris.context import (
    ContextBudget,
    ContextCandidate,
    ContextSnapshot,
    ContextUncertainty,
    ResolutionStatus,
)
from iris.execution import ExecutionRequest
from iris.execution.models import (
    CapabilityExecutionInput,
    ExecutionInput,
    IntelligenceExecutionInput,
    MemoryExecutionInput,
    SystemExecutionInput,
)
from iris.memory.models import utc_time
from iris.orchestrator import (
    HandlerAvailability,
    OrchestrationDecision,
    validate_orchestration_decision_current,
)
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
    StepHandlingPreparationStatus,
    validate_step_handling_preparation_current,
)
from iris.plan_runs import PlanRun, PlanRunError
from iris.plan_step_execution_binding import (
    PlanStepExecutionBinder,
    PlanStepExecutionBinding,
    validate_plan_step_execution_binding_current,
)
from iris.plan_step_execution_binding_post_recording_composition.errors import (
    PlanStepExecutionBindingPostRecordingCompositionInvariantError,
)
from iris.plan_step_execution_binding_post_recording_composition.models import (
    PlanStepExecutionBindingPostRecordingCompositionResult,
)
from iris.plan_step_execution_request_materialization_composition import (
    PlanStepExecutionRequestMaterializationComposer,
    PlanStepExecutionRequestMaterializationCompositionResult,
)
from iris.planning import Plan
from iris.step_progress_transition import StepProgressTransitionDecision
from iris.work_identity import PlanStepWorkReference, WorkSubject, WorkSubjectKind


class PlanStepExecutionBindingPostRecordingComposer:
    """Bind one exact validated WP047 Step C request through WP024, then stop."""

    def __init__(
        self,
        *,
        request_materialization_composer: PlanStepExecutionRequestMaterializationComposer,
        execution_binder: PlanStepExecutionBinder | None = None,
    ) -> None:
        if not isinstance(
            request_materialization_composer,
            PlanStepExecutionRequestMaterializationComposer,
        ):
            raise TypeError(
                "request_materialization_composer must be a "
                "PlanStepExecutionRequestMaterializationComposer"
            )
        if execution_binder is not None and not isinstance(
            execution_binder, PlanStepExecutionBinder
        ):
            raise TypeError("execution_binder must be a PlanStepExecutionBinder")
        self._request_materialization_composer = request_materialization_composer
        self._execution_binder = (
            PlanStepExecutionBinder() if execution_binder is None else execution_binder
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
    ) -> PlanStepExecutionBindingPostRecordingCompositionResult:
        """Invoke WP047 once; bind each validated request once; stop."""

        self._validate_input_types(
            plan,
            run,
            step_id,
            candidates,
            budget,
            uncertainties,
            created_at,
            availability,
            execution_input,
            post_recording_candidates,
            post_recording_budget,
            post_recording_uncertainties,
            post_recording_created_at,
            post_recording_availability,
        )
        request_result = self._request_materialization_composer.compose(
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
        self._validate_request_result(
            plan,
            run,
            step_id,
            post_recording_budget,
            post_recording_created_at,
            post_recording_execution_input,
            request_result,
        )

        request = request_result.post_recording_execution_request
        if request is None:
            return self._result(request_result, None)

        advancement = request_result.post_recording_advancement_result
        preparation = request_result.post_recording_handling_preparation
        assert advancement is not None
        assert preparation is not None
        binding = self._execution_binder.bind(
            plan,
            advancement.updated_run,
            advancement.control_decision,
            preparation,
            request,
        )
        if not isinstance(binding, PlanStepExecutionBinding):
            raise PlanStepExecutionBindingPostRecordingCompositionInvariantError(
                "WP024 must return a PlanStepExecutionBinding"
            )
        try:
            PlanStepExecutionBinding.__post_init__(binding)
            validate_plan_step_execution_binding_current(
                plan, advancement.updated_run, binding
            )
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise PlanStepExecutionBindingPostRecordingCompositionInvariantError(
                "WP024 returned a malformed or noncurrent Step C binding"
            ) from exc
        return self._result(request_result, binding)

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
        execution_input: ExecutionInput | None,
        post_recording_candidates: tuple[ContextCandidate, ...],
        post_recording_budget: ContextBudget,
        post_recording_uncertainties: tuple[ContextUncertainty, ...],
        post_recording_created_at: datetime,
        post_recording_availability: HandlerAvailability,
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
                not isinstance(value, ContextCandidate) for value in candidate_values
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
                not isinstance(value, ContextUncertainty)
                for value in uncertainty_values
            ):
                raise TypeError(f"{name} must be a tuple of ContextUncertainty")
        if not isinstance(created_at, datetime):
            raise TypeError("created_at must be a datetime")
        if not isinstance(post_recording_created_at, datetime):
            raise TypeError("post_recording_created_at must be a datetime")
        if not isinstance(availability, HandlerAvailability):
            raise TypeError("availability must be a HandlerAvailability")
        if not isinstance(post_recording_availability, HandlerAvailability):
            raise TypeError("post_recording_availability must be a HandlerAvailability")
        if execution_input is not None and not isinstance(
            execution_input,
            (
                SystemExecutionInput,
                MemoryExecutionInput,
                CapabilityExecutionInput,
                IntelligenceExecutionInput,
            ),
        ):
            raise TypeError("execution_input must be an ExecutionInput or None")

    @staticmethod
    def _validate_request_result(
        plan: Plan,
        source_run: PlanRun,
        processed_step_id: str,
        post_recording_budget: ContextBudget,
        post_recording_created_at: datetime,
        post_recording_execution_input: ExecutionInput | None,
        result: PlanStepExecutionRequestMaterializationCompositionResult,
    ) -> None:
        invariant = PlanStepExecutionBindingPostRecordingCompositionInvariantError
        if not isinstance(
            result,
            PlanStepExecutionRequestMaterializationCompositionResult,
        ):
            raise invariant(
                "WP047 must return a "
                "PlanStepExecutionRequestMaterializationCompositionResult"
            )
        try:
            PlanStepExecutionRequestMaterializationCompositionResult.__post_init__(
                result
            )
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise invariant("WP047 result violates its canonical contract") from exc

        assessment = result.assessment
        transition = result.transition_decision
        if not isinstance(assessment, StepOutcomeAssessment) or not isinstance(
            transition, StepProgressTransitionDecision
        ):
            raise invariant("WP047 must preserve canonical source decision artifacts")
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
                "WP047 result does not match the supplied Plan, source Run, and step"
            )

        advancement = result.post_recording_advancement_result
        preparation = result.post_recording_handling_preparation
        subject = result.post_recording_work_subject
        context = result.post_recording_context_snapshot
        if advancement is None:
            if any(item is not None for item in (preparation, subject, context)):
                raise invariant(
                    "WP047 cannot preserve Step C artifacts without advancement"
                )
            return

        successor = advancement.updated_run
        control = advancement.control_decision
        if not isinstance(successor, PlanRun) or not isinstance(
            control, ControlDecision
        ):
            raise invariant("WP047 advancement contains noncanonical artifacts")
        if (
            successor.plan_id != plan.plan_id
            or successor.run_id != source_run.run_id
            or successor.goal_id != source_run.goal_id
            or control.plan_id != plan.plan_id
            or control.run_id != successor.run_id
            or control.observed_revision != successor.revision
        ):
            raise invariant("WP047 successor Run and fresh control contradict input")
        try:
            ControlDecision.__post_init__(control)
            validate_control_decision_current(plan, successor, control)
        except (
            PlanControlError,
            PlanRunError,
            TypeError,
            ValueError,
            AttributeError,
        ) as exc:
            raise invariant(
                "WP047 fresh control is not current for its exact successor Run"
            ) from exc

        if control.kind is not ControlDecisionKind.STEP_SELECTED:
            if any(item is not None for item in (preparation, subject, context)):
                raise invariant(
                    "WP047 non-selecting control cannot contain Step C artifacts"
                )
            return
        if control.selected_step_id is None:
            raise invariant("WP047 fresh selection must identify Step C")
        if not isinstance(preparation, StepHandlingPreparationResult):
            raise invariant("WP047 selected path requires canonical preparation")
        if not isinstance(preparation.status, StepHandlingPreparationStatus):
            raise invariant("WP047 preparation must contain a canonical status")
        if (
            preparation.plan_id != plan.plan_id
            or preparation.run_id != successor.run_id
            or preparation.observed_revision != successor.revision
            or preparation.step_id != control.selected_step_id
        ):
            raise invariant("WP047 preparation contradicts exact Step C selection")
        try:
            StepHandlingPreparationResult.__post_init__(preparation)
            validate_step_handling_preparation_current(plan, successor, preparation)
        except (
            PlanHandlingError,
            PlanControlError,
            PlanRunError,
            TypeError,
            ValueError,
            AttributeError,
        ) as exc:
            raise invariant(
                "WP047 preparation is not current for exact Step C selection"
            ) from exc

        if not isinstance(subject, WorkSubject):
            raise invariant("WP047 selected path requires canonical WorkSubject")
        reference = subject.reference
        if (
            subject.kind is not WorkSubjectKind.PLAN_STEP
            or not isinstance(reference, PlanStepWorkReference)
            or reference.plan_id != plan.plan_id
            or reference.run_id != successor.run_id
            or reference.step_id != control.selected_step_id
            or subject.origin is not None
        ):
            raise invariant("WP047 WorkSubject does not identify exact Step C")

        if not isinstance(context, ContextSnapshot):
            raise invariant("WP047 selected path requires canonical ContextSnapshot")
        try:
            context.__post_init__()
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise invariant("WP047 returned a noncanonical ContextSnapshot") from exc
        if (
            context.subject is not subject
            or context.subject_id != subject.subject_id
            or context.budget != post_recording_budget
            or context.created_at
            != utc_time(post_recording_created_at, "post_recording_created_at")
            or not isinstance(context.status, ResolutionStatus)
        ):
            raise invariant("WP047 ContextSnapshot contradicts exact Step C inputs")
        start = result.execution_start_result
        if start is None or context.created_at < start.execution_result.completed_at:
            raise invariant("WP047 Step C Context predates its completed execution")

        decision = result.post_recording_orchestration_decision
        request = result.post_recording_execution_request
        if decision is None:
            return
        assert request is not None
        try:
            OrchestrationDecision.__post_init__(decision)
            validate_orchestration_decision_current(decision, subject, context)
            ExecutionRequest.__post_init__(request)
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise invariant("WP047 returned invalid decision/request lineage") from exc
        if request.execution_input is not post_recording_execution_input:
            raise invariant("WP047 request does not preserve the exact Step C input")

    @staticmethod
    def _result(
        request_result: PlanStepExecutionRequestMaterializationCompositionResult,
        binding: PlanStepExecutionBinding | None,
    ) -> PlanStepExecutionBindingPostRecordingCompositionResult:
        return PlanStepExecutionBindingPostRecordingCompositionResult(
            assessment=request_result.assessment,
            transition_decision=request_result.transition_decision,
            progress_update=request_result.progress_update,
            advancement_result=request_result.advancement_result,
            handling_preparation=request_result.handling_preparation,
            work_subject=request_result.work_subject,
            context_snapshot=request_result.context_snapshot,
            orchestration_decision=request_result.orchestration_decision,
            execution_request=request_result.execution_request,
            execution_binding=request_result.execution_binding,
            execution_start_result=request_result.execution_start_result,
            execution_recording_result=request_result.execution_recording_result,
            post_recording_assessment=request_result.post_recording_assessment,
            post_recording_transition_decision=(
                request_result.post_recording_transition_decision
            ),
            post_recording_progress_update=(
                request_result.post_recording_progress_update
            ),
            post_recording_advancement_result=(
                request_result.post_recording_advancement_result
            ),
            post_recording_handling_preparation=(
                request_result.post_recording_handling_preparation
            ),
            post_recording_work_subject=request_result.post_recording_work_subject,
            post_recording_context_snapshot=(
                request_result.post_recording_context_snapshot
            ),
            post_recording_orchestration_decision=(
                request_result.post_recording_orchestration_decision
            ),
            post_recording_execution_request=request_result.post_recording_execution_request,
            post_recording_execution_binding=binding,
        )
