"""Compose one bounded WP046 result with the existing WP018 request authority."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from iris.context import ContextBudget, ContextCandidate, ContextUncertainty
from iris.execution import ExecutionRequest
from iris.execution.models import (
    CapabilityExecutionInput,
    ExecutionInput,
    IntelligenceExecutionInput,
    MemoryExecutionInput,
    SystemExecutionInput,
)
from iris.memory.models import utc_time
from iris.orchestrator import HandlerAvailability
from iris.outcome_assessment import StepOutcomeAssessment
from iris.plan_runs import PlanRun
from iris.plan_step_execution_orchestration_composition import (
    PlanStepExecutionOrchestrationComposer,
    PlanStepExecutionOrchestrationCompositionResult,
)
from iris.plan_step_execution_request_materialization_composition.errors import (
    PlanStepExecutionRequestMaterializationCompositionInvariantError,
)
from iris.plan_step_execution_request_materialization_composition.models import (
    PlanStepExecutionRequestMaterializationCompositionResult,
)
from iris.planning import Plan
from iris.step_progress_transition import StepProgressTransitionDecision


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _new_execution_id() -> str:
    return uuid4().hex


class PlanStepExecutionRequestMaterializationComposer:
    """Append at most one exact WP018 request to one exact WP046 result."""

    def __init__(
        self,
        *,
        orchestration_composer: PlanStepExecutionOrchestrationComposer,
        clock: Callable[[], datetime] | None = None,
        execution_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if not isinstance(
            orchestration_composer, PlanStepExecutionOrchestrationComposer
        ):
            raise TypeError(
                "orchestration_composer must be a "
                "PlanStepExecutionOrchestrationComposer"
            )
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable")
        if execution_id_factory is not None and not callable(execution_id_factory):
            raise TypeError("execution_id_factory must be callable")
        self._orchestration_composer = orchestration_composer
        self._clock = _utc_now if clock is None else clock
        self._execution_id_factory = (
            _new_execution_id if execution_id_factory is None else execution_id_factory
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
    ) -> PlanStepExecutionRequestMaterializationCompositionResult:
        """Invoke WP046 once, optionally materialize exact Step C request, stop."""

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
        orchestration_result = self._orchestration_composer.compose(
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
        )
        self._validate_orchestration_result(
            plan,
            run,
            step_id,
            post_recording_budget,
            post_recording_created_at,
            orchestration_result,
        )

        decision = orchestration_result.post_recording_orchestration_decision
        if decision is None:
            return self._result(orchestration_result, None)

        subject = orchestration_result.post_recording_work_subject
        context = orchestration_result.post_recording_context_snapshot
        assert subject is not None
        assert context is not None
        execution_id = self._execution_id_factory()
        request_created_at = self._clock()
        request = ExecutionRequest(
            execution_id=execution_id,
            subject=subject,
            context=context,
            decision=decision,
            created_at=request_created_at,
            execution_input=post_recording_execution_input,
        )
        inherited_request = orchestration_result.execution_request
        if (
            inherited_request is not None
            and request.execution_id == inherited_request.execution_id
        ):
            raise PlanStepExecutionRequestMaterializationCompositionInvariantError(
                "Step C execution identity must not reuse Step B execution identity"
            )
        return self._result(orchestration_result, request)

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
    def _validate_orchestration_result(
        plan: Plan,
        source_run: PlanRun,
        processed_step_id: str,
        post_recording_budget: ContextBudget,
        post_recording_created_at: datetime,
        result: PlanStepExecutionOrchestrationCompositionResult,
    ) -> None:
        invariant = PlanStepExecutionRequestMaterializationCompositionInvariantError
        if not isinstance(result, PlanStepExecutionOrchestrationCompositionResult):
            raise invariant(
                "WP046 must return a PlanStepExecutionOrchestrationCompositionResult"
            )
        try:
            result.__post_init__()
        except (RuntimeError, TypeError, ValueError) as exc:
            raise invariant("WP046 result violates its canonical contract") from exc
        assessment = result.assessment
        transition = result.transition_decision
        if not isinstance(assessment, StepOutcomeAssessment) or not isinstance(
            transition, StepProgressTransitionDecision
        ):
            raise invariant("WP046 must preserve canonical source decision artifacts")
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
                "WP046 result does not match supplied Plan, source Run, and step"
            )
        context = result.post_recording_context_snapshot
        if context is not None and (
            context.budget != post_recording_budget
            or context.created_at
            != utc_time(post_recording_created_at, "post_recording_created_at")
        ):
            raise invariant(
                "WP046 Step C ContextSnapshot contradicts exact supplied inputs"
            )

    @staticmethod
    def _result(
        orchestration_result: PlanStepExecutionOrchestrationCompositionResult,
        request: ExecutionRequest | None,
    ) -> PlanStepExecutionRequestMaterializationCompositionResult:
        return PlanStepExecutionRequestMaterializationCompositionResult(
            assessment=orchestration_result.assessment,
            transition_decision=orchestration_result.transition_decision,
            progress_update=orchestration_result.progress_update,
            advancement_result=orchestration_result.advancement_result,
            handling_preparation=orchestration_result.handling_preparation,
            work_subject=orchestration_result.work_subject,
            context_snapshot=orchestration_result.context_snapshot,
            orchestration_decision=orchestration_result.orchestration_decision,
            execution_request=orchestration_result.execution_request,
            execution_binding=orchestration_result.execution_binding,
            execution_start_result=orchestration_result.execution_start_result,
            execution_recording_result=(
                orchestration_result.execution_recording_result
            ),
            post_recording_assessment=orchestration_result.post_recording_assessment,
            post_recording_transition_decision=(
                orchestration_result.post_recording_transition_decision
            ),
            post_recording_progress_update=(
                orchestration_result.post_recording_progress_update
            ),
            post_recording_advancement_result=(
                orchestration_result.post_recording_advancement_result
            ),
            post_recording_handling_preparation=(
                orchestration_result.post_recording_handling_preparation
            ),
            post_recording_work_subject=(
                orchestration_result.post_recording_work_subject
            ),
            post_recording_context_snapshot=(
                orchestration_result.post_recording_context_snapshot
            ),
            post_recording_orchestration_decision=(
                orchestration_result.post_recording_orchestration_decision
            ),
            post_recording_execution_request=request,
        )
