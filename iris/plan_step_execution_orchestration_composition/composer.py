"""Compose one bounded WP045 result with the existing WP017 authority."""

from __future__ import annotations

from datetime import datetime

from iris.context import (
    ContextBudget,
    ContextCandidate,
    ContextSnapshot,
    ContextUncertainty,
    ResolutionStatus,
)
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
    HandlingNeed,
    OrchestrationDecision,
    OrchestrationInput,
    Orchestrator,
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
from iris.plan_step_execution_context_materialization_composition import (
    PlanStepExecutionContextMaterializationComposer,
    PlanStepExecutionContextMaterializationCompositionResult,
)
from iris.plan_step_execution_orchestration_composition.errors import (
    PlanStepExecutionOrchestrationCompositionInvariantError,
)
from iris.plan_step_execution_orchestration_composition.models import (
    PlanStepExecutionOrchestrationCompositionResult,
)
from iris.planning import Plan
from iris.step_progress_transition import StepProgressTransitionDecision
from iris.work_identity import PlanStepWorkReference, WorkSubject, WorkSubjectKind


class PlanStepExecutionOrchestrationComposer:
    """Append at most one exact WP017 decision to one exact WP045 result."""

    def __init__(
        self,
        *,
        context_materialization_composer: (
            PlanStepExecutionContextMaterializationComposer
        ),
        orchestrator: Orchestrator | None = None,
    ) -> None:
        if not isinstance(
            context_materialization_composer,
            PlanStepExecutionContextMaterializationComposer,
        ):
            raise TypeError(
                "context_materialization_composer must be a "
                "PlanStepExecutionContextMaterializationComposer"
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
    ) -> PlanStepExecutionOrchestrationCompositionResult:
        """Invoke WP045 once, optionally orchestrate exact Step C, then stop."""

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
        context_result = self._context_materialization_composer.compose(
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
        )
        self._validate_context_result(
            plan,
            run,
            step_id,
            post_recording_budget,
            post_recording_created_at,
            context_result,
        )

        subject = context_result.post_recording_work_subject
        if subject is None:
            return self._result(context_result, None)

        preparation = context_result.post_recording_handling_preparation
        context = context_result.post_recording_context_snapshot
        assert preparation is not None
        assert context is not None
        if preparation.status is not StepHandlingPreparationStatus.PREPARED:
            return self._result(context_result, None)

        need = preparation.handling_need
        if not isinstance(need, HandlingNeed) or need.blockers:
            raise PlanStepExecutionOrchestrationCompositionInvariantError(
                "PREPARED Step C handling must contain its exact unmodified need"
            )
        orchestration_input = OrchestrationInput(
            subject=subject,
            context=context,
            needs=(need,),
            availability=post_recording_availability,
        )
        decision = self._orchestrator.decide(orchestration_input)
        self._validate_orchestration_decision(decision, subject, context, need)
        return self._result(context_result, decision)

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
                not isinstance(item, ContextCandidate) for item in candidate_values
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
                not isinstance(item, ContextUncertainty) for item in uncertainty_values
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

    @classmethod
    def _validate_context_result(
        cls,
        plan: Plan,
        source_run: PlanRun,
        processed_step_id: str,
        post_recording_budget: ContextBudget,
        post_recording_created_at: datetime,
        result: PlanStepExecutionContextMaterializationCompositionResult,
    ) -> None:
        invariant = PlanStepExecutionOrchestrationCompositionInvariantError
        if not isinstance(
            result,
            PlanStepExecutionContextMaterializationCompositionResult,
        ):
            raise invariant(
                "WP045 must return a "
                "PlanStepExecutionContextMaterializationCompositionResult"
            )
        try:
            result.__post_init__()
        except (RuntimeError, TypeError, ValueError) as exc:
            raise invariant("WP045 result violates its canonical contract") from exc

        assessment = result.assessment
        transition = result.transition_decision
        if not isinstance(assessment, StepOutcomeAssessment) or not isinstance(
            transition, StepProgressTransitionDecision
        ):
            raise invariant("WP045 must preserve canonical source decision artifacts")
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
                "WP045 result does not match the supplied Plan, source Run, and step"
            )

        advancement = result.post_recording_advancement_result
        preparation = result.post_recording_handling_preparation
        subject = result.post_recording_work_subject
        context = result.post_recording_context_snapshot
        if advancement is None:
            if any(item is not None for item in (preparation, subject, context)):
                raise invariant(
                    "WP045 cannot preserve Step C artifacts without advancement"
                )
            return

        successor = advancement.updated_run
        control = advancement.control_decision
        if not isinstance(successor, PlanRun) or not isinstance(
            control, ControlDecision
        ):
            raise invariant("WP045 advancement contains noncanonical artifacts")
        if (
            successor.plan_id != plan.plan_id
            or successor.run_id != source_run.run_id
            or successor.goal_id != source_run.goal_id
            or control.plan_id != plan.plan_id
            or control.run_id != successor.run_id
            or control.observed_revision != successor.revision
        ):
            raise invariant("WP045 successor Run and fresh control contradict input")
        try:
            validate_control_decision_current(plan, successor, control)
        except (PlanControlError, PlanRunError, TypeError) as exc:
            raise invariant(
                "WP045 fresh control is not current for its exact successor Run"
            ) from exc

        if control.kind is not ControlDecisionKind.STEP_SELECTED:
            if any(item is not None for item in (preparation, subject, context)):
                raise invariant(
                    "WP045 non-selecting control cannot contain Step C artifacts"
                )
            return
        if control.selected_step_id is None:
            raise invariant("WP045 fresh selection must identify Step C")
        if not isinstance(preparation, StepHandlingPreparationResult):
            raise invariant("WP045 selected path requires canonical preparation")
        if not isinstance(preparation.status, StepHandlingPreparationStatus):
            raise invariant("WP045 preparation must contain a canonical status")
        if (
            preparation.plan_id != plan.plan_id
            or preparation.run_id != successor.run_id
            or preparation.observed_revision != successor.revision
            or preparation.step_id != control.selected_step_id
        ):
            raise invariant("WP045 preparation contradicts exact Step C selection")
        try:
            validate_step_handling_preparation_current(plan, successor, preparation)
        except (PlanHandlingError, PlanControlError, PlanRunError, TypeError) as exc:
            raise invariant(
                "WP045 preparation is not current for exact Step C selection"
            ) from exc

        if not isinstance(subject, WorkSubject):
            raise invariant("WP045 selected path requires canonical WorkSubject")
        reference = subject.reference
        if (
            subject.kind is not WorkSubjectKind.PLAN_STEP
            or not isinstance(reference, PlanStepWorkReference)
            or reference.plan_id != plan.plan_id
            or reference.run_id != successor.run_id
            or reference.step_id != control.selected_step_id
            or subject.origin is not None
        ):
            raise invariant("WP045 WorkSubject does not identify exact Step C")

        if not isinstance(context, ContextSnapshot):
            raise invariant("WP045 selected path requires canonical ContextSnapshot")
        try:
            context.__post_init__()
        except (RuntimeError, TypeError, ValueError) as exc:
            raise invariant("WP045 returned a noncanonical ContextSnapshot") from exc
        if (
            context.subject is not subject
            or context.subject_id != subject.subject_id
            or context.budget != post_recording_budget
            or context.created_at
            != utc_time(post_recording_created_at, "post_recording_created_at")
            or not isinstance(context.status, ResolutionStatus)
        ):
            raise invariant("WP045 ContextSnapshot contradicts exact Step C inputs")

    @staticmethod
    def _validate_orchestration_decision(
        decision: OrchestrationDecision,
        subject: WorkSubject,
        context: ContextSnapshot,
        need: HandlingNeed,
    ) -> None:
        invariant = PlanStepExecutionOrchestrationCompositionInvariantError
        if not isinstance(decision, OrchestrationDecision):
            raise invariant("WP017 Orchestrator must return an OrchestrationDecision")
        try:
            decision.__post_init__()
            validate_orchestration_decision_current(decision, subject, context)
        except (RuntimeError, TypeError, ValueError) as exc:
            raise invariant(
                "WP017 decision is not canonical/current for exact Step C artifacts"
            ) from exc
        if decision.created_at < context.created_at:
            raise invariant("WP017 decision cannot predate exact Step C Context")
        if decision.need_ids != (need.need_id,):
            raise invariant("WP017 decision must account for exact Step C need")
        if decision.requirement is not None and decision.requirement is not need:
            raise invariant("WP017 decision selected a foreign handling requirement")
        if any(
            reference not in need.blockers for reference in decision.context_references
        ):
            raise invariant("WP017 decision referenced an unsupplied Context blocker")

    @staticmethod
    def _result(
        context_result: PlanStepExecutionContextMaterializationCompositionResult,
        decision: OrchestrationDecision | None,
    ) -> PlanStepExecutionOrchestrationCompositionResult:
        return PlanStepExecutionOrchestrationCompositionResult(
            assessment=context_result.assessment,
            transition_decision=context_result.transition_decision,
            progress_update=context_result.progress_update,
            advancement_result=context_result.advancement_result,
            handling_preparation=context_result.handling_preparation,
            work_subject=context_result.work_subject,
            context_snapshot=context_result.context_snapshot,
            orchestration_decision=context_result.orchestration_decision,
            execution_request=context_result.execution_request,
            execution_binding=context_result.execution_binding,
            execution_start_result=context_result.execution_start_result,
            execution_recording_result=context_result.execution_recording_result,
            post_recording_assessment=context_result.post_recording_assessment,
            post_recording_transition_decision=(
                context_result.post_recording_transition_decision
            ),
            post_recording_progress_update=(
                context_result.post_recording_progress_update
            ),
            post_recording_advancement_result=(
                context_result.post_recording_advancement_result
            ),
            post_recording_handling_preparation=(
                context_result.post_recording_handling_preparation
            ),
            post_recording_work_subject=context_result.post_recording_work_subject,
            post_recording_context_snapshot=(
                context_result.post_recording_context_snapshot
            ),
            post_recording_orchestration_decision=decision,
        )
