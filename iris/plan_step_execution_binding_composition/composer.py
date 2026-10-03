"""Compose one bounded WP035 request with the existing WP024 binder."""

from __future__ import annotations

from datetime import datetime

from iris.context import (
    ContextBudget,
    ContextCandidate,
    ContextSnapshot,
    ContextUncertainty,
)
from iris.execution import ExecutionRequest
from iris.execution.models import ExecutionInput
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
from iris.plan_run_advancement import PlanRunProgressAdvanceResult
from iris.plan_runs import PlanRun, PlanRunError, StepProgressUpdate
from iris.plan_step_execution_binding import (
    PlanStepExecutionBinder,
    PlanStepExecutionBinding,
    PlanStepExecutionBindingError,
    validate_plan_step_execution_binding_current,
)
from iris.plan_step_execution_binding_composition.errors import (
    PlanStepExecutionBindingCompositionInvariantError,
)
from iris.plan_step_execution_binding_composition.models import (
    PlanStepExecutionBindingCompositionResult,
)
from iris.plan_step_execution_request_materialization import (
    PlanStepExecutionRequestMaterializationResult,
    PlanStepExecutionRequestMaterializer,
)
from iris.planning import Plan
from iris.step_progress_transition import StepProgressTransitionDecision
from iris.work_identity import PlanStepWorkReference, WorkSubject, WorkSubjectKind


class PlanStepExecutionBindingComposer:
    """Append at most one canonical WP024 binding to one WP035 reaction."""

    def __init__(
        self,
        *,
        request_materializer: PlanStepExecutionRequestMaterializer | None = None,
        execution_binder: PlanStepExecutionBinder | None = None,
    ) -> None:
        if request_materializer is not None and not isinstance(
            request_materializer, PlanStepExecutionRequestMaterializer
        ):
            raise TypeError(
                "request_materializer must be a PlanStepExecutionRequestMaterializer"
            )
        if execution_binder is not None and not isinstance(
            execution_binder, PlanStepExecutionBinder
        ):
            raise TypeError("execution_binder must be a PlanStepExecutionBinder")
        self._request_materializer = (
            PlanStepExecutionRequestMaterializer()
            if request_materializer is None
            else request_materializer
        )
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
    ) -> PlanStepExecutionBindingCompositionResult:
        """Invoke WP035 once, optionally bind its exact request, then stop."""

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
        request_result = self._request_materializer.materialize(
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
        self._validate_request_result(
            plan,
            run,
            step_id,
            budget,
            created_at,
            request_result,
        )

        request = request_result.execution_request
        if request is None:
            return self._result(request_result, None)

        advancement = request_result.advancement_result
        preparation = request_result.handling_preparation
        assert advancement is not None
        assert preparation is not None
        binding = self._execution_binder.bind(
            plan,
            advancement.updated_run,
            advancement.control_decision,
            preparation,
            request,
        )
        self._validate_binding(plan, request_result, binding)
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
    def _validate_request_result(
        cls,
        plan: Plan,
        run: PlanRun,
        step_id: str,
        budget: ContextBudget,
        created_at: datetime,
        result: PlanStepExecutionRequestMaterializationResult,
    ) -> None:
        invariant = PlanStepExecutionBindingCompositionInvariantError
        if not isinstance(result, PlanStepExecutionRequestMaterializationResult):
            raise invariant(
                "WP035 must return a PlanStepExecutionRequestMaterializationResult"
            )
        assessment = result.assessment
        transition = result.transition_decision
        update = result.progress_update
        advancement = result.advancement_result
        preparation = result.handling_preparation
        subject = result.work_subject
        context = result.context_snapshot
        decision = result.orchestration_decision
        request = result.execution_request
        if not isinstance(assessment, StepOutcomeAssessment) or not isinstance(
            transition, StepProgressTransitionDecision
        ):
            raise invariant(
                "WP035 result must contain canonical assessment and transition types"
            )
        if update is not None and not isinstance(update, StepProgressUpdate):
            raise invariant("WP035 progress_update must be canonical or None")
        if advancement is not None and not isinstance(
            advancement, PlanRunProgressAdvanceResult
        ):
            raise invariant("WP035 advancement_result must be canonical or None")
        if preparation is not None and not isinstance(
            preparation, StepHandlingPreparationResult
        ):
            raise invariant("WP035 handling_preparation must be canonical or None")
        if subject is not None and not isinstance(subject, WorkSubject):
            raise invariant("WP035 work_subject must be canonical or None")
        if context is not None and not isinstance(context, ContextSnapshot):
            raise invariant("WP035 context_snapshot must be canonical or None")
        if decision is not None and not isinstance(decision, OrchestrationDecision):
            raise invariant("WP035 orchestration_decision must be canonical or None")
        if request is not None and not isinstance(request, ExecutionRequest):
            raise invariant("WP035 execution_request must be canonical or None")
        if (
            assessment.plan_id != plan.plan_id
            or assessment.run_id != run.run_id
            or assessment.run_revision != run.revision
            or assessment.step_id != step_id
            or transition.plan_id != plan.plan_id
            or transition.run_id != run.run_id
            or transition.observed_revision != run.revision
            or transition.step_id != step_id
            or transition.assessment_id != assessment.assessment_id
        ):
            raise invariant(
                "WP035 result does not match the supplied Plan, Run revision, and step"
            )
        if (update is None) != (advancement is None):
            raise invariant(
                "WP035 progress update and advancement must both exist or be absent"
            )
        if update is None:
            if any(
                artifact is not None
                for artifact in (preparation, subject, context, decision, request)
            ):
                raise invariant(
                    "WP035 cannot produce downstream artifacts without advancement"
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
            raise invariant(
                "WP035 update and advancement do not match the source operation"
            )
        updated_run = advancement.updated_run
        control = advancement.control_decision
        if (
            not isinstance(updated_run, PlanRun)
            or not isinstance(control, ControlDecision)
            or updated_run.plan_id != plan.plan_id
            or updated_run.run_id != run.run_id
            or updated_run.goal_id != run.goal_id
            or updated_run.revision != run.revision + 1
            or control.plan_id != plan.plan_id
            or control.run_id != updated_run.run_id
            or control.observed_revision != updated_run.revision
        ):
            raise invariant(
                "WP035 successor Run and fresh control lineage do not match"
            )
        try:
            validate_control_decision_current(plan, updated_run, control)
        except (PlanControlError, PlanRunError) as exc:
            raise invariant(
                "WP035 fresh control is not current for its successor Run"
            ) from exc

        selected = control.kind is ControlDecisionKind.STEP_SELECTED
        if (
            selected != (preparation is not None)
            or selected != (subject is not None)
            or selected != (context is not None)
        ):
            raise invariant(
                "WP035 selected-work artifacts must exactly match fresh selection"
            )
        if not selected:
            if decision is not None or request is not None:
                raise invariant("WP035 cannot create a request without selected work")
            return

        assert preparation is not None
        assert subject is not None
        assert context is not None
        selected_step_id = control.selected_step_id
        reference = subject.reference
        if selected_step_id is None or (
            preparation.plan_id != plan.plan_id
            or preparation.run_id != updated_run.run_id
            or preparation.observed_revision != updated_run.revision
            or preparation.step_id != selected_step_id
        ):
            raise invariant("WP035 preparation does not match the fresh selection")
        try:
            validate_step_handling_preparation_current(plan, updated_run, preparation)
        except (PlanHandlingError, PlanControlError, PlanRunError) as exc:
            raise invariant(
                "WP035 preparation is not current for the successor Run"
            ) from exc
        if (
            subject.kind is not WorkSubjectKind.PLAN_STEP
            or not isinstance(reference, PlanStepWorkReference)
            or reference.plan_id != plan.plan_id
            or reference.run_id != updated_run.run_id
            or reference.step_id != selected_step_id
            or subject.origin is not None
        ):
            raise invariant("WP035 subject does not identify the fresh selected work")
        if (
            context.subject is not subject
            or context.subject_id != subject.subject_id
            or context.budget != budget
            or context.created_at != utc_time(created_at, "created_at")
        ):
            raise invariant("WP035 ContextSnapshot does not match its subject/input")

        prepared = preparation.status is StepHandlingPreparationStatus.PREPARED
        if prepared != (decision is not None) or (decision is None) != (
            request is None
        ):
            raise invariant(
                "WP035 request must exist exactly for PREPARED selected handling"
            )
        if not prepared:
            return
        if preparation.handling_need is None or decision is None or request is None:
            raise invariant("PREPARED WP035 lineage is incomplete")
        try:
            validate_orchestration_decision_current(decision, subject, context)
        except (TypeError, ValueError) as exc:
            raise invariant(
                "WP035 decision is not current for the exact subject/context"
            ) from exc
        if decision.need_ids != (preparation.handling_need.need_id,) or (
            decision.requirement is not None
            and decision.requirement != preparation.handling_need
        ):
            raise invariant("WP035 decision does not account for the prepared need")
        if (
            request.subject is not subject
            or request.context is not context
            or request.decision is not decision
            or request.created_at < decision.created_at
        ):
            raise invariant(
                "WP035 request does not preserve the exact decision lineage"
            )

    @staticmethod
    def _validate_binding(
        plan: Plan,
        result: PlanStepExecutionRequestMaterializationResult,
        binding: PlanStepExecutionBinding,
    ) -> None:
        invariant = PlanStepExecutionBindingCompositionInvariantError
        if not isinstance(binding, PlanStepExecutionBinding):
            raise invariant("WP024 must return a PlanStepExecutionBinding")
        advancement = result.advancement_result
        preparation = result.handling_preparation
        request = result.execution_request
        assert advancement is not None
        assert preparation is not None
        assert request is not None
        updated_run = advancement.updated_run
        try:
            validate_plan_step_execution_binding_current(plan, updated_run, binding)
        except (PlanStepExecutionBindingError, PlanRunError) as exc:
            raise invariant(
                "WP024 returned a binding that is not current for the successor Run"
            ) from exc
        selected_step_id = advancement.control_decision.selected_step_id
        need = preparation.handling_need
        if need is None or (
            binding.plan_id != plan.plan_id
            or binding.run_id != updated_run.run_id
            or binding.observed_revision != updated_run.revision
            or binding.step_id != selected_step_id
            or binding.execution_id != request.execution_id
            or binding.subject_id != request.subject.subject_id
            or binding.context_snapshot_id != request.context.snapshot_id
            or binding.orchestration_decision_id != request.decision.decision_id
            or binding.handling_need_id != need.need_id
        ):
            raise invariant("WP024 binding contradicts the exact WP035 lineage")

    @staticmethod
    def _result(
        request_result: PlanStepExecutionRequestMaterializationResult,
        binding: PlanStepExecutionBinding | None,
    ) -> PlanStepExecutionBindingCompositionResult:
        return PlanStepExecutionBindingCompositionResult(
            assessment=request_result.assessment,
            transition_decision=request_result.transition_decision,
            progress_update=request_result.progress_update,
            advancement_result=request_result.advancement_result,
            handling_preparation=request_result.handling_preparation,
            work_subject=request_result.work_subject,
            context_snapshot=request_result.context_snapshot,
            orchestration_decision=request_result.orchestration_decision,
            execution_request=request_result.execution_request,
            execution_binding=binding,
        )
