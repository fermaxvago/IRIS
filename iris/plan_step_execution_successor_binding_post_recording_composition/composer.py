"""Compose the exact WP059 successor request with canonical WP024 binding."""

from __future__ import annotations

from dataclasses import fields
from datetime import datetime

from iris.context import ContextBudget, ContextCandidate, ContextUncertainty
from iris.execution.models import ExecutionInput
from iris.orchestrator import HandlerAvailability
from iris.plan_control import ControlDecisionKind
from iris.plan_handling import StepHandlingPreparationStatus
from iris.plan_runs import PlanRun
from iris.plan_step_execution_binding import (
    PlanStepExecutionBinder,
    PlanStepExecutionBinding,
    validate_plan_step_execution_binding_current,
)
from iris.plan_step_execution_request_materialization_post_recording_composition import (
    PlanStepExecutionRequestMaterializationPostRecordingComposer,
    PlanStepExecutionRequestMaterializationPostRecordingCompositionResult,
)
from iris.plan_step_execution_successor_binding_post_recording_composition.errors import (
    PlanStepExecutionSuccessorBindingPostRecordingCompositionInvariantError,
)
from iris.plan_step_execution_successor_binding_post_recording_composition.models import (
    PlanStepExecutionSuccessorBindingPostRecordingCompositionResult,
    validate_successor_binding,
)
from iris.planning import Plan


class PlanStepExecutionSuccessorBindingPostRecordingComposer:
    """Delegate WP059 once; bind its optional exact successor request; stop."""

    def __init__(
        self,
        *,
        request_materialization_composer: (
            PlanStepExecutionRequestMaterializationPostRecordingComposer
        ),
        execution_binder: PlanStepExecutionBinder | None = None,
    ) -> None:
        if not isinstance(
            request_materialization_composer,
            PlanStepExecutionRequestMaterializationPostRecordingComposer,
        ):
            raise TypeError(
                "request_materialization_composer must be a "
                "PlanStepExecutionRequestMaterializationPostRecordingComposer"
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
        successor_context_candidates: tuple[ContextCandidate, ...],
        successor_context_budget: ContextBudget,
        successor_context_uncertainties: tuple[ContextUncertainty, ...] = (),
        successor_context_created_at: datetime,
        successor_orchestration_availability: HandlerAvailability,
        successor_execution_input: ExecutionInput | None = None,
    ) -> PlanStepExecutionSuccessorBindingPostRecordingCompositionResult:
        """Preserve upstream lazy semantics and return one inert lineage witness."""

        upstream = self._request_materialization_composer.compose(
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
            successor_context_candidates=successor_context_candidates,
            successor_context_budget=successor_context_budget,
            successor_context_uncertainties=successor_context_uncertainties,
            successor_context_created_at=successor_context_created_at,
            successor_orchestration_availability=successor_orchestration_availability,
            successor_execution_input=successor_execution_input,
        )
        self._validate_upstream(
            plan,
            run,
            step_id,
            post_recording_budget,
            post_recording_created_at,
            post_recording_execution_input,
            successor_context_candidates,
            successor_context_budget,
            successor_context_uncertainties,
            successor_context_created_at,
            successor_orchestration_availability,
            successor_execution_input,
            upstream,
        )
        request = upstream.post_recording_execution_successor_request
        if request is None:
            return self._result(upstream, None)
        advancement = upstream.post_recording_execution_advancement_result
        preparation = upstream.post_recording_execution_handling_preparation
        assert advancement is not None and preparation is not None
        successor_run = advancement.updated_run
        control = advancement.control_decision
        if (
            control.kind is not ControlDecisionKind.STEP_SELECTED
            or preparation.status is not StepHandlingPreparationStatus.PREPARED
            or request.subject is not upstream.post_recording_execution_work_subject
            or request.context is not upstream.post_recording_execution_context_snapshot
            or request.decision
            is not upstream.post_recording_execution_orchestration_decision
        ):
            raise PlanStepExecutionSuccessorBindingPostRecordingCompositionInvariantError(
                "WP059 request does not identify the exact selected successor"
            )
        binding = self._execution_binder.bind(
            plan, successor_run, control, preparation, request
        )
        validate_successor_binding(binding, upstream)
        try:
            validate_plan_step_execution_binding_current(plan, successor_run, binding)
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise PlanStepExecutionSuccessorBindingPostRecordingCompositionInvariantError(
                "WP024 returned a noncurrent successor binding"
            ) from exc
        return self._result(upstream, binding)

    @staticmethod
    def _validate_upstream(
        plan: Plan,
        source_run: PlanRun,
        processed_step_id: str,
        post_recording_budget: ContextBudget,
        post_recording_created_at: datetime,
        post_recording_execution_input: ExecutionInput | None,
        successor_context_candidates: tuple[ContextCandidate, ...],
        successor_context_budget: ContextBudget,
        successor_context_uncertainties: tuple[ContextUncertainty, ...],
        successor_context_created_at: datetime,
        successor_orchestration_availability: HandlerAvailability,
        successor_execution_input: ExecutionInput | None,
        result: object,
    ) -> None:
        invariant = (
            PlanStepExecutionSuccessorBindingPostRecordingCompositionInvariantError
        )
        if not isinstance(
            result,
            PlanStepExecutionRequestMaterializationPostRecordingCompositionResult,
        ):
            raise invariant("WP059 must return its canonical composition result")
        try:
            PlanStepExecutionRequestMaterializationPostRecordingComposer._validate_upstream(
                plan,
                source_run,
                processed_step_id,
                post_recording_budget,
                post_recording_created_at,
                post_recording_execution_input,
                successor_context_candidates,
                successor_context_budget,
                successor_context_uncertainties,
                successor_context_created_at,
                successor_orchestration_availability,
                result,
            )
            PlanStepExecutionRequestMaterializationPostRecordingCompositionResult.__post_init__(
                result
            )
            request = result.post_recording_execution_successor_request
            if (
                request is not None
                and request.execution_input is not successor_execution_input
            ):
                raise ValueError("WP059 changed the explicit successor input")
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise invariant("WP059 returned contradictory cumulative lineage") from exc

    @staticmethod
    def _result(
        upstream: PlanStepExecutionRequestMaterializationPostRecordingCompositionResult,
        binding: PlanStepExecutionBinding | None,
    ) -> PlanStepExecutionSuccessorBindingPostRecordingCompositionResult:
        return PlanStepExecutionSuccessorBindingPostRecordingCompositionResult(
            **{
                field.name: getattr(upstream, field.name)
                for field in fields(
                    PlanStepExecutionRequestMaterializationPostRecordingCompositionResult
                )
            },
            post_recording_execution_successor_binding=binding,
        )
