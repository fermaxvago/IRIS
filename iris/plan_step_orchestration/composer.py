"""Compose one WP033 result with optional exact WP017 orchestration."""

from __future__ import annotations

from datetime import datetime

from iris.context import (
    ContextBudget,
    ContextCandidate,
    ContextSnapshot,
    ContextUncertainty,
    ResolutionStatus,
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
from iris.plan_run_advancement import PlanRunProgressAdvanceResult
from iris.plan_runs import PlanRun, PlanRunError, StepProgressUpdate
from iris.plan_step_context_materialization import (
    PlanStepContextMaterializationResult,
    PlanStepContextMaterializer,
)
from iris.plan_step_orchestration.errors import PlanStepOrchestrationInvariantError
from iris.plan_step_orchestration.models import PlanStepOrchestrationResult
from iris.planning import Plan
from iris.step_progress_transition import StepProgressTransitionDecision
from iris.work_identity import PlanStepWorkReference, WorkSubject, WorkSubjectKind


class PlanStepOrchestrationComposer:
    """Orchestrate one prepared, Context-owned selected PlanStep, then stop."""

    def __init__(
        self,
        *,
        context_materializer: PlanStepContextMaterializer | None = None,
        orchestrator: Orchestrator | None = None,
    ) -> None:
        if context_materializer is not None and not isinstance(
            context_materializer, PlanStepContextMaterializer
        ):
            raise TypeError(
                "context_materializer must be a PlanStepContextMaterializer"
            )
        if orchestrator is not None and not isinstance(orchestrator, Orchestrator):
            raise TypeError("orchestrator must be an Orchestrator")
        self._context_materializer = (
            PlanStepContextMaterializer()
            if context_materializer is None
            else context_materializer
        )
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
    ) -> PlanStepOrchestrationResult:
        """Return WP033 artifacts and zero or one exact WP017 decision."""

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
        context_result = self._context_materializer.materialize(
            plan,
            run,
            step_id,
            candidates=candidates,
            budget=budget,
            uncertainties=uncertainties,
            created_at=created_at,
        )
        self._validate_context_result(
            plan,
            run,
            step_id,
            budget,
            created_at,
            context_result,
        )

        subject = context_result.work_subject
        context = context_result.context_snapshot
        if subject is None:
            return self._result(context_result, None)

        assert context is not None
        preparation = context_result.handling_preparation
        assert preparation is not None
        if preparation.status is not StepHandlingPreparationStatus.PREPARED:
            return self._result(context_result, None)

        advancement = context_result.advancement_result
        assert advancement is not None
        self._validate_prepared_handling(plan, advancement, preparation)
        need = preparation.handling_need
        assert isinstance(need, HandlingNeed)

        orchestration_input = OrchestrationInput(
            subject=subject,
            context=context,
            needs=(need,),
            availability=availability,
        )
        decision = self._orchestrator.decide(orchestration_input)
        self._validate_orchestration_decision(
            decision,
            subject,
            context,
            need,
        )
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
    def _validate_context_result(
        cls,
        plan: Plan,
        run: PlanRun,
        step_id: str,
        budget: ContextBudget,
        created_at: datetime,
        result: PlanStepContextMaterializationResult,
    ) -> None:
        if not isinstance(result, PlanStepContextMaterializationResult):
            raise PlanStepOrchestrationInvariantError(
                "WP033 materializer must return a PlanStepContextMaterializationResult"
            )
        assessment = result.assessment
        transition = result.transition_decision
        update = result.progress_update
        advancement = result.advancement_result
        preparation = result.handling_preparation
        subject = result.work_subject
        context = result.context_snapshot
        if not isinstance(assessment, StepOutcomeAssessment) or not isinstance(
            transition, StepProgressTransitionDecision
        ):
            raise PlanStepOrchestrationInvariantError(
                "WP033 result must contain canonical assessment and decision types"
            )
        if update is not None and not isinstance(update, StepProgressUpdate):
            raise PlanStepOrchestrationInvariantError(
                "WP033 progress_update must be a StepProgressUpdate or None"
            )
        if advancement is not None and not isinstance(
            advancement, PlanRunProgressAdvanceResult
        ):
            raise PlanStepOrchestrationInvariantError(
                "WP033 advancement_result must be canonical or None"
            )
        if preparation is not None and not isinstance(
            preparation, StepHandlingPreparationResult
        ):
            raise PlanStepOrchestrationInvariantError(
                "WP033 handling_preparation must be canonical or None"
            )
        if subject is not None and not isinstance(subject, WorkSubject):
            raise PlanStepOrchestrationInvariantError(
                "WP033 work_subject must be canonical or None"
            )
        if context is not None and not isinstance(context, ContextSnapshot):
            raise PlanStepOrchestrationInvariantError(
                "WP033 context_snapshot must be canonical or None"
            )
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
            raise PlanStepOrchestrationInvariantError(
                "WP033 result does not match the supplied Plan, Run revision, and step"
            )
        if (update is None) != (advancement is None):
            raise PlanStepOrchestrationInvariantError(
                "WP033 progress update and advancement must both exist or be absent"
            )
        if update is None:
            if any(item is not None for item in (preparation, subject, context)):
                raise PlanStepOrchestrationInvariantError(
                    "WP033 cannot produce selected-work artifacts without advancement"
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
            raise PlanStepOrchestrationInvariantError(
                "WP033 update and advancement do not match the source operation"
            )
        cls._validate_fresh_advancement(plan, run, advancement)

        selected = (
            advancement.control_decision.kind is ControlDecisionKind.STEP_SELECTED
        )
        if (
            selected != (preparation is not None)
            or selected != (subject is not None)
            or selected != (context is not None)
        ):
            raise PlanStepOrchestrationInvariantError(
                "WP033 selected-work artifacts must exactly match fresh selection"
            )
        if not selected:
            return
        assert preparation is not None
        assert subject is not None
        assert context is not None
        cls._validate_selected_context(
            plan,
            advancement,
            preparation,
            subject,
            context,
            budget,
            created_at,
        )

    @staticmethod
    def _validate_fresh_advancement(
        plan: Plan,
        run: PlanRun,
        advancement: PlanRunProgressAdvanceResult,
    ) -> None:
        updated_run = advancement.updated_run
        control = advancement.control_decision
        if not isinstance(updated_run, PlanRun):
            raise PlanStepOrchestrationInvariantError(
                "WP033 advancement must contain a canonical PlanRun"
            )
        if not isinstance(control, ControlDecision):
            raise PlanStepOrchestrationInvariantError(
                "WP033 advancement must contain a canonical ControlDecision"
            )
        if (
            updated_run.plan_id != plan.plan_id
            or updated_run.run_id != run.run_id
            or updated_run.goal_id != run.goal_id
            or updated_run.revision != run.revision + 1
            or control.plan_id != plan.plan_id
            or control.run_id != updated_run.run_id
            or control.observed_revision != updated_run.revision
        ):
            raise PlanStepOrchestrationInvariantError(
                "WP033 successor Run and fresh control lineage do not match"
            )
        try:
            validate_control_decision_current(plan, updated_run, control)
        except (PlanControlError, PlanRunError) as exc:
            raise PlanStepOrchestrationInvariantError(
                "WP033 fresh control is not current for its successor Run"
            ) from exc

    @staticmethod
    def _validate_selected_context(
        plan: Plan,
        advancement: PlanRunProgressAdvanceResult,
        preparation: StepHandlingPreparationResult,
        subject: WorkSubject,
        context: ContextSnapshot,
        budget: ContextBudget,
        created_at: datetime,
    ) -> None:
        updated_run = advancement.updated_run
        control = advancement.control_decision
        selected_step_id = control.selected_step_id
        if selected_step_id is None:
            raise PlanStepOrchestrationInvariantError(
                "fresh STEP_SELECTED control must identify one PlanStep"
            )
        if (
            preparation.plan_id != plan.plan_id
            or preparation.run_id != updated_run.run_id
            or preparation.observed_revision != updated_run.revision
            or preparation.step_id != selected_step_id
        ):
            raise PlanStepOrchestrationInvariantError(
                "WP033 preparation does not match the exact fresh selection"
            )
        if not isinstance(preparation.status, StepHandlingPreparationStatus):
            raise PlanStepOrchestrationInvariantError(
                "WP033 preparation must contain a canonical status"
            )
        try:
            validate_step_handling_preparation_current(plan, updated_run, preparation)
        except (PlanHandlingError, PlanControlError, PlanRunError) as exc:
            raise PlanStepOrchestrationInvariantError(
                "WP033 preparation is not current for the exact successor selection"
            ) from exc
        reference = subject.reference
        if (
            subject.kind is not WorkSubjectKind.PLAN_STEP
            or not isinstance(reference, PlanStepWorkReference)
            or reference.plan_id != plan.plan_id
            or reference.run_id != updated_run.run_id
            or reference.step_id != selected_step_id
            or subject.origin is not None
        ):
            raise PlanStepOrchestrationInvariantError(
                "WP033 subject does not identify the exact selected work without origin"
            )
        if (
            context.subject is not subject
            or context.subject_id != subject.subject_id
            or context.budget != budget
            or context.created_at != utc_time(created_at, "created_at")
            or not isinstance(context.status, ResolutionStatus)
        ):
            raise PlanStepOrchestrationInvariantError(
                "WP033 ContextSnapshot does not match the exact selected subject/input"
            )

    @staticmethod
    def _validate_prepared_handling(
        plan: Plan,
        advancement: PlanRunProgressAdvanceResult,
        preparation: StepHandlingPreparationResult,
    ) -> None:
        try:
            validate_step_handling_preparation_current(
                plan,
                advancement.updated_run,
                preparation,
            )
        except (PlanHandlingError, PlanControlError, PlanRunError) as exc:
            raise PlanStepOrchestrationInvariantError(
                "PREPARED handling is not current for the exact successor Run"
            ) from exc
        need = preparation.handling_need
        if not isinstance(need, HandlingNeed):
            raise PlanStepOrchestrationInvariantError(
                "PREPARED handling must contain a canonical HandlingNeed"
            )
        if need.blockers:
            raise PlanStepOrchestrationInvariantError(
                "WP034 must receive the canonical unmodified PlanStep HandlingNeed"
            )

    @staticmethod
    def _validate_orchestration_decision(
        decision: OrchestrationDecision,
        subject: WorkSubject,
        context: ContextSnapshot,
        need: HandlingNeed,
    ) -> None:
        if not isinstance(decision, OrchestrationDecision):
            raise PlanStepOrchestrationInvariantError(
                "WP017 Orchestrator must return an OrchestrationDecision"
            )
        try:
            validate_orchestration_decision_current(decision, subject, context)
        except (TypeError, ValueError) as exc:
            raise PlanStepOrchestrationInvariantError(
                "WP017 decision is not current for the exact subject/context"
            ) from exc
        if decision.created_at < context.created_at:
            raise PlanStepOrchestrationInvariantError(
                "WP017 decision cannot predate its exact ContextSnapshot"
            )
        if decision.need_ids != (need.need_id,):
            raise PlanStepOrchestrationInvariantError(
                "WP017 decision must account for the exact prepared need"
            )
        if decision.requirement is not None and decision.requirement != need:
            raise PlanStepOrchestrationInvariantError(
                "WP017 decision selected a requirement outside the input"
            )
        if any(
            reference not in need.blockers for reference in decision.context_references
        ):
            raise PlanStepOrchestrationInvariantError(
                "WP017 decision referenced an unsupplied Context blocker"
            )

    @staticmethod
    def _result(
        context_result: PlanStepContextMaterializationResult,
        decision: OrchestrationDecision | None,
    ) -> PlanStepOrchestrationResult:
        return PlanStepOrchestrationResult(
            assessment=context_result.assessment,
            transition_decision=context_result.transition_decision,
            progress_update=context_result.progress_update,
            advancement_result=context_result.advancement_result,
            handling_preparation=context_result.handling_preparation,
            work_subject=context_result.work_subject,
            context_snapshot=context_result.context_snapshot,
            orchestration_decision=decision,
        )
