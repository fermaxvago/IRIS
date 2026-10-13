"""Compose WP058 with one optional canonical WP018 successor request."""

from __future__ import annotations

from collections.abc import Callable
from copy import copy
from dataclasses import fields
from datetime import UTC, datetime
from uuid import uuid4

from iris.context import ContextBudget, ContextCandidate, ContextUncertainty
from iris.execution import ExecutionRequest
from iris.execution.models import ExecutionInput
from iris.memory.models import identifier, utc_time
from iris.orchestrator import HandlerAvailability, OrchestrationTarget
from iris.plan_runs import PlanRun
from iris.plan_step_execution_orchestration_post_recording_composition import (
    PlanStepExecutionOrchestrationPostRecordingComposer,
    PlanStepExecutionOrchestrationPostRecordingCompositionResult,
)
from iris.plan_step_execution_orchestration_post_recording_composition.models import (
    validate_successor_decision,
)
from iris.plan_step_execution_request_materialization_post_recording_composition.errors import (
    PlanStepExecutionRequestMaterializationPostRecordingCompositionInvariantError,
)
from iris.plan_step_execution_request_materialization_post_recording_composition.models import (
    PlanStepExecutionRequestMaterializationPostRecordingCompositionResult,
)
from iris.planning import Plan


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _new_execution_id() -> str:
    return uuid4().hex


class PlanStepExecutionRequestMaterializationPostRecordingComposer:
    """Delegate once, optionally materialize one successor request, then stop."""

    def __init__(
        self,
        *,
        orchestration_composer: PlanStepExecutionOrchestrationPostRecordingComposer,
        clock: Callable[[], datetime] | None = None,
        execution_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if not isinstance(
            orchestration_composer, PlanStepExecutionOrchestrationPostRecordingComposer
        ):
            raise TypeError(
                "orchestration_composer must be a "
                "PlanStepExecutionOrchestrationPostRecordingComposer"
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
        successor_context_candidates: tuple[ContextCandidate, ...],
        successor_context_budget: ContextBudget,
        successor_context_uncertainties: tuple[ContextUncertainty, ...] = (),
        successor_context_created_at: datetime,
        successor_orchestration_availability: HandlerAvailability,
        successor_execution_input: ExecutionInput | None = None,
    ) -> PlanStepExecutionRequestMaterializationPostRecordingCompositionResult:
        """Preserve WP058's causal and lazy semantics before WP059 work."""

        upstream = self._orchestration_composer.compose(
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
            upstream,
        )
        decision = upstream.post_recording_execution_orchestration_decision
        if decision is None or decision.target in {
            OrchestrationTarget.CLARIFY,
            OrchestrationTarget.UNSATISFIED,
        }:
            return self._result(upstream, None)
        if decision.target not in {
            OrchestrationTarget.SYSTEM,
            OrchestrationTarget.MEMORY,
            OrchestrationTarget.CAPABILITY,
            OrchestrationTarget.INTELLIGENCE,
        }:
            raise PlanStepExecutionRequestMaterializationPostRecordingCompositionInvariantError(
                "WP058 returned an unsupported orchestration target"
            )
        subject = upstream.post_recording_execution_work_subject
        context = upstream.post_recording_execution_context_snapshot
        assert subject is not None and context is not None
        execution_id = self._execution_id_factory()
        try:
            identifier(execution_id, "execution_id")
        except (TypeError, ValueError) as exc:
            raise PlanStepExecutionRequestMaterializationPostRecordingCompositionInvariantError(
                "execution ID factory returned a noncanonical identifier"
            ) from exc
        occupied = {subject.subject_id, context.snapshot_id, decision.decision_id}
        occupied.update(
            value.execution_id
            for field in fields(
                PlanStepExecutionOrchestrationPostRecordingCompositionResult
            )
            if isinstance(value := getattr(upstream, field.name), ExecutionRequest)
        )
        if execution_id in occupied:
            raise PlanStepExecutionRequestMaterializationPostRecordingCompositionInvariantError(
                "successor execution identity collides with an inherited artifact"
            )
        request_created_at = self._clock()
        normalized_time = utc_time(request_created_at, "request_created_at")
        if request_created_at.isoformat() != normalized_time.isoformat():
            raise PlanStepExecutionRequestMaterializationPostRecordingCompositionInvariantError(
                "request clock must return a canonical UTC timestamp"
            )
        request = ExecutionRequest(
            execution_id=execution_id,
            subject=subject,
            context=context,
            decision=decision,
            created_at=request_created_at,
            execution_input=successor_execution_input,
        )
        if (
            request.execution_id != execution_id
            or request.created_at.isoformat() != request_created_at.isoformat()
            or request.execution_input is not successor_execution_input
        ):
            raise PlanStepExecutionRequestMaterializationPostRecordingCompositionInvariantError(
                "canonical request construction changed supplied operands"
            )
        return self._result(upstream, request)

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
        result: object,
    ) -> None:
        invariant = PlanStepExecutionRequestMaterializationPostRecordingCompositionInvariantError
        if not isinstance(
            result, PlanStepExecutionOrchestrationPostRecordingCompositionResult
        ):
            raise invariant("WP058 must return its canonical composition result")
        try:
            PlanStepExecutionOrchestrationPostRecordingComposer._validate_upstream(
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
                result,
            )
            PlanStepExecutionOrchestrationPostRecordingCompositionResult.__post_init__(
                result
            )
            decision = result.post_recording_execution_orchestration_decision
            preparation = result.post_recording_execution_handling_preparation
            if decision is not None:
                if not isinstance(
                    successor_orchestration_availability, HandlerAvailability
                ):
                    raise TypeError("successor availability must be canonical")
                checked = copy(successor_orchestration_availability)
                HandlerAvailability.__post_init__(checked)
                if any(
                    type(getattr(successor_orchestration_availability, field.name))
                    is not type(getattr(checked, field.name))
                    or getattr(successor_orchestration_availability, field.name)
                    != getattr(checked, field.name)
                    for field in fields(HandlerAvailability)
                ):
                    raise ValueError("successor availability requires normalization")
                assert preparation is not None and preparation.handling_need is not None
                subject = result.post_recording_execution_work_subject
                context = result.post_recording_execution_context_snapshot
                assert subject is not None and context is not None
                validate_successor_decision(
                    decision,
                    subject,
                    context,
                    preparation.handling_need,
                    successor_orchestration_availability,
                )
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise invariant("WP058 returned contradictory cumulative lineage") from exc

    @staticmethod
    def _result(
        upstream: PlanStepExecutionOrchestrationPostRecordingCompositionResult,
        request: ExecutionRequest | None,
    ) -> PlanStepExecutionRequestMaterializationPostRecordingCompositionResult:
        return PlanStepExecutionRequestMaterializationPostRecordingCompositionResult(
            **{
                field.name: getattr(upstream, field.name)
                for field in fields(
                    PlanStepExecutionOrchestrationPostRecordingCompositionResult
                )
            },
            post_recording_execution_successor_request=request,
        )
