"""Compose one bounded WP036 reaction with the existing WP025 start boundary."""

from __future__ import annotations

from datetime import datetime

from iris.context import (
    ContextBudget,
    ContextCandidate,
    ContextSnapshot,
    ContextUncertainty,
)
from iris.execution import ExecutionRequest, ExecutionResult, ExecutionStatus
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
from iris.plan_runs import PlanRun, PlanRunError, StepProgressState, StepProgressUpdate
from iris.plan_step_execution_binding import (
    PlanStepExecutionBinding,
    PlanStepExecutionBindingError,
    validate_plan_step_execution_binding_current,
)
from iris.plan_step_execution_binding_composition import (
    PlanStepExecutionBindingComposer,
    PlanStepExecutionBindingCompositionResult,
)
from iris.plan_step_execution_start import (
    PlanStepExecutionStartCoordinator,
    PlanStepExecutionStartResult,
)
from iris.plan_step_execution_start_composition.errors import (
    PlanStepExecutionStartCompositionInvariantError,
)
from iris.plan_step_execution_start_composition.models import (
    PlanStepExecutionStartCompositionResult,
)
from iris.planning import Plan
from iris.step_progress_transition import StepProgressTransitionDecision
from iris.work_identity import PlanStepWorkReference, WorkSubject, WorkSubjectKind


class PlanStepExecutionStartComposer:
    """Append at most one exact WP025 start result to one WP036 reaction."""

    def __init__(
        self,
        *,
        start_coordinator: PlanStepExecutionStartCoordinator,
        binding_composer: PlanStepExecutionBindingComposer | None = None,
    ) -> None:
        if not isinstance(start_coordinator, PlanStepExecutionStartCoordinator):
            raise TypeError(
                "start_coordinator must be a PlanStepExecutionStartCoordinator"
            )
        if binding_composer is not None and not isinstance(
            binding_composer, PlanStepExecutionBindingComposer
        ):
            raise TypeError(
                "binding_composer must be a PlanStepExecutionBindingComposer"
            )
        self._binding_composer = (
            PlanStepExecutionBindingComposer()
            if binding_composer is None
            else binding_composer
        )
        self._start_coordinator = start_coordinator

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
    ) -> PlanStepExecutionStartCompositionResult:
        """Invoke WP036 once, optionally start its exact binding, then stop."""

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
        binding_result = self._binding_composer.compose(
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
        self._validate_binding_result(
            plan,
            run,
            step_id,
            budget,
            created_at,
            binding_result,
        )

        binding = binding_result.execution_binding
        if binding is None:
            return self._result(binding_result, None)

        advancement = binding_result.advancement_result
        request = binding_result.execution_request
        assert advancement is not None
        assert request is not None
        pre_activation_run = advancement.updated_run
        start_result = self._start_coordinator.start(
            plan,
            pre_activation_run,
            binding,
            request,
        )
        self._validate_start_result(
            plan,
            pre_activation_run,
            binding,
            request,
            start_result,
        )
        return self._result(binding_result, start_result)

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
    def _validate_binding_result(
        cls,
        plan: Plan,
        run: PlanRun,
        step_id: str,
        budget: ContextBudget,
        created_at: datetime,
        result: PlanStepExecutionBindingCompositionResult,
    ) -> None:
        invariant = PlanStepExecutionStartCompositionInvariantError
        if not isinstance(result, PlanStepExecutionBindingCompositionResult):
            raise invariant(
                "WP036 must return a PlanStepExecutionBindingCompositionResult"
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
        binding = result.execution_binding
        if not isinstance(assessment, StepOutcomeAssessment) or not isinstance(
            transition, StepProgressTransitionDecision
        ):
            raise invariant(
                "WP036 result must contain canonical assessment and transition types"
            )
        if update is not None and not isinstance(update, StepProgressUpdate):
            raise invariant("WP036 progress_update must be canonical or None")
        if advancement is not None and not isinstance(
            advancement, PlanRunProgressAdvanceResult
        ):
            raise invariant("WP036 advancement_result must be canonical or None")
        if preparation is not None and not isinstance(
            preparation, StepHandlingPreparationResult
        ):
            raise invariant("WP036 handling_preparation must be canonical or None")
        if subject is not None and not isinstance(subject, WorkSubject):
            raise invariant("WP036 work_subject must be canonical or None")
        if context is not None and not isinstance(context, ContextSnapshot):
            raise invariant("WP036 context_snapshot must be canonical or None")
        if decision is not None and not isinstance(decision, OrchestrationDecision):
            raise invariant("WP036 orchestration_decision must be canonical or None")
        if request is not None and not isinstance(request, ExecutionRequest):
            raise invariant("WP036 execution_request must be canonical or None")
        if binding is not None and not isinstance(binding, PlanStepExecutionBinding):
            raise invariant("WP036 execution_binding must be canonical or None")
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
                "WP036 result does not match the supplied Plan, Run revision, and step"
            )
        if (update is None) != (advancement is None):
            raise invariant(
                "WP036 progress update and advancement must both exist or be absent"
            )
        if (request is None) != (binding is None):
            raise invariant(
                "WP036 request and binding must both exist or both be absent"
            )
        if update is None:
            if any(
                artifact is not None
                for artifact in (
                    preparation,
                    subject,
                    context,
                    decision,
                    request,
                    binding,
                )
            ):
                raise invariant(
                    "WP036 cannot produce downstream artifacts without advancement"
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
                "WP036 update and advancement do not match the source operation"
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
                "WP036 successor Run and fresh control lineage do not match"
            )
        try:
            validate_control_decision_current(plan, updated_run, control)
        except (PlanControlError, PlanRunError) as exc:
            raise invariant(
                "WP036 fresh control is not current for its successor Run"
            ) from exc

        selected = control.kind is ControlDecisionKind.STEP_SELECTED
        if (
            selected != (preparation is not None)
            or selected != (subject is not None)
            or selected != (context is not None)
        ):
            raise invariant(
                "WP036 selected-work artifacts must exactly match fresh selection"
            )
        if not selected:
            if decision is not None or request is not None or binding is not None:
                raise invariant("WP036 cannot bind without selected work")
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
            raise invariant("WP036 preparation does not match the fresh selection")
        try:
            validate_step_handling_preparation_current(plan, updated_run, preparation)
        except (PlanHandlingError, PlanControlError, PlanRunError) as exc:
            raise invariant(
                "WP036 preparation is not current for the successor Run"
            ) from exc
        if (
            subject.kind is not WorkSubjectKind.PLAN_STEP
            or not isinstance(reference, PlanStepWorkReference)
            or reference.plan_id != plan.plan_id
            or reference.run_id != updated_run.run_id
            or reference.step_id != selected_step_id
            or subject.origin is not None
        ):
            raise invariant("WP036 subject does not identify the fresh selected work")
        if (
            context.subject is not subject
            or context.subject_id != subject.subject_id
            or context.budget != budget
            or context.created_at != utc_time(created_at, "created_at")
        ):
            raise invariant("WP036 ContextSnapshot does not match its subject/input")

        prepared = preparation.status is StepHandlingPreparationStatus.PREPARED
        if prepared != (decision is not None) or (decision is None) != (
            request is None
        ):
            raise invariant(
                "WP036 request must exist exactly for PREPARED selected handling"
            )
        if not prepared:
            if binding is not None:
                raise invariant("WP036 cannot bind unprepared handling")
            return
        if preparation.handling_need is None or decision is None or request is None:
            raise invariant("PREPARED WP036 lineage is incomplete")
        try:
            validate_orchestration_decision_current(decision, subject, context)
        except (TypeError, ValueError) as exc:
            raise invariant(
                "WP036 decision is not current for the exact subject/context"
            ) from exc
        if decision.need_ids != (preparation.handling_need.need_id,) or (
            decision.requirement is not None
            and decision.requirement != preparation.handling_need
        ):
            raise invariant("WP036 decision does not account for the prepared need")
        if (
            request.subject is not subject
            or request.context is not context
            or request.decision is not decision
            or request.created_at < decision.created_at
        ):
            raise invariant(
                "WP036 request does not preserve the exact decision lineage"
            )
        if binding is None:
            raise invariant("PREPARED WP036 request requires its canonical binding")
        try:
            validate_plan_step_execution_binding_current(plan, updated_run, binding)
        except (PlanStepExecutionBindingError, PlanRunError) as exc:
            raise invariant(
                "WP036 binding is not current for the successor Run"
            ) from exc
        if (
            binding.plan_id != plan.plan_id
            or binding.run_id != updated_run.run_id
            or binding.observed_revision != updated_run.revision
            or binding.step_id != selected_step_id
            or binding.execution_id != request.execution_id
            or binding.subject_id != request.subject.subject_id
            or binding.context_snapshot_id != request.context.snapshot_id
            or binding.orchestration_decision_id != request.decision.decision_id
            or binding.handling_need_id != preparation.handling_need.need_id
        ):
            raise invariant("WP036 binding contradicts the exact request lineage")

    @staticmethod
    def _validate_start_result(
        plan: Plan,
        pre_activation_run: PlanRun,
        binding: PlanStepExecutionBinding,
        request: ExecutionRequest,
        start_result: PlanStepExecutionStartResult,
    ) -> None:
        invariant = PlanStepExecutionStartCompositionInvariantError
        if not isinstance(start_result, PlanStepExecutionStartResult):
            raise invariant("WP025 must return a PlanStepExecutionStartResult")
        execution_result = start_result.execution_result
        if not isinstance(execution_result, ExecutionResult):
            raise invariant("WP025 start result must contain an ExecutionResult")
        if (
            start_result.plan_id != binding.plan_id
            or start_result.run_id != binding.run_id
            or start_result.source_revision != binding.observed_revision
            or start_result.source_revision != pre_activation_run.revision
            or start_result.step_id != binding.step_id
            or start_result.execution_id != binding.execution_id
            or start_result.execution_id != request.execution_id
            or execution_result.execution_id != request.execution_id
            or execution_result.subject_id != request.subject.subject_id
            or execution_result.decision_id != request.decision.decision_id
            or execution_result.context_snapshot_id != request.context.snapshot_id
            or execution_result.target is not request.decision.target
            or execution_result.decision_reason is not request.decision.reason
        ):
            raise invariant("WP025 result contradicts the exact start lineage")

        active_run = start_result.active_run
        if active_run is None:
            failure = execution_result.failure
            if (
                start_result.activation_update_id is not None
                or execution_result.status is not ExecutionStatus.REJECTED
                or execution_result.handler_reference is not None
                or failure is None
                or failure.code != "handler_unavailable"
            ):
                raise invariant(
                    "non-activated WP025 result must be canonical handler unavailability"
                )
            return

        if not isinstance(active_run, PlanRun):
            raise invariant("WP025 active_run must be a canonical PlanRun")
        if (
            active_run.plan_id != plan.plan_id
            or active_run.plan_id != pre_activation_run.plan_id
            or active_run.run_id != pre_activation_run.run_id
            or active_run.goal_id != pre_activation_run.goal_id
            or active_run.revision != pre_activation_run.revision + 1
            or start_result.activation_update_id is None
        ):
            raise invariant(
                "WP025 ACTIVE Run must derive exactly from the pre-activation Run"
            )
        progress = next(
            (
                item
                for item in active_run.step_progress
                if item.step_id == binding.step_id
            ),
            None,
        )
        if progress is None or progress.state is not StepProgressState.ACTIVE:
            raise invariant("WP025 bound PlanStep must be ACTIVE after activation")
        prior_non_target = tuple(
            item
            for item in pre_activation_run.step_progress
            if item.step_id != binding.step_id
        )
        active_non_target = tuple(
            item for item in active_run.step_progress if item.step_id != binding.step_id
        )
        if (
            active_non_target != prior_non_target
            or active_run.observations != pre_activation_run.observations
            or active_run.blockers != pre_activation_run.blockers
        ):
            raise invariant("WP025 activation mutated unrelated PlanRun content")

    @staticmethod
    def _result(
        binding_result: PlanStepExecutionBindingCompositionResult,
        start_result: PlanStepExecutionStartResult | None,
    ) -> PlanStepExecutionStartCompositionResult:
        return PlanStepExecutionStartCompositionResult(
            assessment=binding_result.assessment,
            transition_decision=binding_result.transition_decision,
            progress_update=binding_result.progress_update,
            advancement_result=binding_result.advancement_result,
            handling_preparation=binding_result.handling_preparation,
            work_subject=binding_result.work_subject,
            context_snapshot=binding_result.context_snapshot,
            orchestration_decision=binding_result.orchestration_decision,
            execution_request=binding_result.execution_request,
            execution_binding=binding_result.execution_binding,
            execution_start_result=start_result,
        )
