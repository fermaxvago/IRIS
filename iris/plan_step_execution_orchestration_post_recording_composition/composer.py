"""Compose exact WP057 successor Context with one canonical WP017 decision."""

from __future__ import annotations

from copy import copy
from dataclasses import fields
from datetime import datetime

from iris.context import ContextBudget, ContextCandidate, ContextUncertainty
from iris.execution.models import ExecutionInput
from iris.orchestrator import (
    HandlerAvailability,
    HandlingNeed,
    OrchestrationDecision,
    OrchestrationInput,
    Orchestrator,
)
from iris.plan_handling import StepHandlingPreparationStatus
from iris.plan_runs import PlanRun
from iris.plan_step_execution_context_materialization_post_recording_composition import (
    PlanStepExecutionContextMaterializationPostRecordingComposer,
    PlanStepExecutionContextMaterializationPostRecordingCompositionResult,
)
from iris.plan_step_execution_orchestration_post_recording_composition.errors import (
    PlanStepExecutionOrchestrationPostRecordingCompositionInvariantError,
)
from iris.plan_step_execution_orchestration_post_recording_composition.models import (
    PlanStepExecutionOrchestrationPostRecordingCompositionResult,
    validate_successor_decision,
)
from iris.planning import Plan


class PlanStepExecutionOrchestrationPostRecordingComposer:
    """Append at most one exact successor orchestration decision, then stop."""

    def __init__(
        self,
        *,
        context_materialization_composer: (
            PlanStepExecutionContextMaterializationPostRecordingComposer
        ),
        orchestrator: Orchestrator | None = None,
    ) -> None:
        if not isinstance(
            context_materialization_composer,
            PlanStepExecutionContextMaterializationPostRecordingComposer,
        ):
            raise TypeError(
                "context_materialization_composer must be a "
                "PlanStepExecutionContextMaterializationPostRecordingComposer"
            )
        if orchestrator is not None and not isinstance(orchestrator, Orchestrator):
            raise TypeError("orchestrator must be an Orchestrator")
        self._context_materialization_composer = context_materialization_composer
        self._orchestrator = Orchestrator() if orchestrator is None else orchestrator

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
    ) -> PlanStepExecutionOrchestrationPostRecordingCompositionResult:
        """Delegate once, decide only for exact prepared successor, then stop."""

        upstream = self._context_materialization_composer.compose(
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
            upstream,
        )
        subject = upstream.post_recording_execution_work_subject
        if subject is None:
            return self._result(upstream, None)
        preparation = upstream.post_recording_execution_handling_preparation
        if preparation is None:
            raise PlanStepExecutionOrchestrationPostRecordingCompositionInvariantError(
                "selected successor lacks handling preparation"
            )
        if preparation.status is not StepHandlingPreparationStatus.PREPARED:
            return self._result(upstream, None)

        context = upstream.post_recording_execution_context_snapshot
        need = preparation.handling_need
        if context is None or not isinstance(need, HandlingNeed) or need.blockers:
            raise PlanStepExecutionOrchestrationPostRecordingCompositionInvariantError(
                "PREPARED successor requires exact Context and unblocked need"
            )
        if not isinstance(successor_orchestration_availability, HandlerAvailability):
            raise TypeError(
                "successor_orchestration_availability must be HandlerAvailability"
            )
        checked_availability = copy(successor_orchestration_availability)
        HandlerAvailability.__post_init__(checked_availability)
        if any(
            type(getattr(successor_orchestration_availability, field.name))
            is not type(getattr(checked_availability, field.name))
            or getattr(successor_orchestration_availability, field.name)
            != getattr(checked_availability, field.name)
            for field in fields(HandlerAvailability)
        ):
            raise ValueError("successor_orchestration_availability is not canonical")
        orchestration_input = OrchestrationInput(
            subject=subject,
            context=context,
            needs=(need,),
            availability=successor_orchestration_availability,
        )
        decision = self._orchestrator.decide(orchestration_input)
        validate_successor_decision(
            decision,
            subject,
            context,
            need,
            successor_orchestration_availability,
        )
        return self._result(upstream, decision)

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
        result: PlanStepExecutionContextMaterializationPostRecordingCompositionResult,
    ) -> None:
        invariant = PlanStepExecutionOrchestrationPostRecordingCompositionInvariantError
        if not isinstance(
            result,
            PlanStepExecutionContextMaterializationPostRecordingCompositionResult,
        ):
            raise invariant("WP057 must return its canonical composition result")
        try:
            PlanStepExecutionContextMaterializationPostRecordingComposer._validate_upstream(
                plan,
                source_run,
                processed_step_id,
                post_recording_budget,
                post_recording_created_at,
                post_recording_execution_input,
                result,
            )
            PlanStepExecutionContextMaterializationPostRecordingCompositionResult.__post_init__(
                result
            )
            subject = result.post_recording_execution_work_subject
            if subject is not None:
                PlanStepExecutionContextMaterializationPostRecordingComposer._validate_context_causality(
                    result, successor_context_created_at
                )
                context = result.post_recording_execution_context_snapshot
                assert context is not None
                PlanStepExecutionContextMaterializationPostRecordingComposer._validate_snapshot(
                    subject,
                    successor_context_candidates,
                    successor_context_budget,
                    successor_context_uncertainties,
                    successor_context_created_at,
                    context,
                )
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise invariant("WP057 returned contradictory cumulative lineage") from exc

    @staticmethod
    def _result(
        upstream: PlanStepExecutionContextMaterializationPostRecordingCompositionResult,
        decision: OrchestrationDecision | None,
    ) -> PlanStepExecutionOrchestrationPostRecordingCompositionResult:
        return PlanStepExecutionOrchestrationPostRecordingCompositionResult(
            **{
                field.name: getattr(upstream, field.name)
                for field in fields(
                    PlanStepExecutionContextMaterializationPostRecordingCompositionResult
                )
            },
            post_recording_execution_orchestration_decision=decision,
        )
