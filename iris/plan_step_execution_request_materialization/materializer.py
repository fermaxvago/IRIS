"""Materialize one exact WP018 request from one bounded WP034 result."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from iris.context import (
    ContextBudget,
    ContextCandidate,
    ContextSnapshot,
    ContextUncertainty,
    ResolutionStatus,
)
from iris.execution import ExecutionRequest
from iris.execution.models import ExecutionInput
from iris.memory.models import utc_time
from iris.orchestrator import (
    HandlerAvailability,
    HandlingNeed,
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
from iris.plan_step_execution_request_materialization.errors import (
    PlanStepExecutionRequestMaterializationInvariantError,
)
from iris.plan_step_execution_request_materialization.models import (
    PlanStepExecutionRequestMaterializationResult,
)
from iris.plan_step_orchestration import (
    PlanStepOrchestrationComposer,
    PlanStepOrchestrationResult,
)
from iris.planning import Plan
from iris.step_progress_transition import StepProgressTransitionDecision
from iris.work_identity import PlanStepWorkReference, WorkSubject, WorkSubjectKind


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _new_execution_id() -> str:
    return uuid4().hex


class PlanStepExecutionRequestMaterializer:
    """Append at most one canonical ExecutionRequest to one WP034 reaction."""

    def __init__(
        self,
        *,
        orchestration_composer: PlanStepOrchestrationComposer | None = None,
        clock: Callable[[], datetime] | None = None,
        execution_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if orchestration_composer is not None and not isinstance(
            orchestration_composer, PlanStepOrchestrationComposer
        ):
            raise TypeError(
                "orchestration_composer must be a PlanStepOrchestrationComposer"
            )
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable")
        if execution_id_factory is not None and not callable(execution_id_factory):
            raise TypeError("execution_id_factory must be callable")
        self._orchestration_composer = (
            PlanStepOrchestrationComposer()
            if orchestration_composer is None
            else orchestration_composer
        )
        self._clock = _utc_now if clock is None else clock
        self._execution_id_factory = (
            _new_execution_id if execution_id_factory is None else execution_id_factory
        )

    def materialize(
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
    ) -> PlanStepExecutionRequestMaterializationResult:
        """Invoke WP034 once, optionally materialize one request, then stop."""

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
        orchestration_result = self._orchestration_composer.compose(
            plan,
            run,
            step_id,
            candidates=candidates,
            budget=budget,
            uncertainties=uncertainties,
            created_at=created_at,
            availability=availability,
        )
        self._validate_orchestration_result(
            plan,
            run,
            step_id,
            budget,
            created_at,
            orchestration_result,
        )

        decision = orchestration_result.orchestration_decision
        if decision is None:
            return self._result(orchestration_result, None)

        subject = orchestration_result.work_subject
        context = orchestration_result.context_snapshot
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
            execution_input=execution_input,
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
    def _validate_orchestration_result(
        cls,
        plan: Plan,
        run: PlanRun,
        step_id: str,
        budget: ContextBudget,
        created_at: datetime,
        result: PlanStepOrchestrationResult,
    ) -> None:
        invariant = PlanStepExecutionRequestMaterializationInvariantError
        if not isinstance(result, PlanStepOrchestrationResult):
            raise invariant("WP034 must return a PlanStepOrchestrationResult")
        assessment = result.assessment
        transition = result.transition_decision
        update = result.progress_update
        advancement = result.advancement_result
        preparation = result.handling_preparation
        subject = result.work_subject
        context = result.context_snapshot
        decision = result.orchestration_decision
        if not isinstance(assessment, StepOutcomeAssessment) or not isinstance(
            transition, StepProgressTransitionDecision
        ):
            raise invariant(
                "WP034 result must contain canonical assessment and transition types"
            )
        if update is not None and not isinstance(update, StepProgressUpdate):
            raise invariant("WP034 progress_update must be canonical or None")
        if advancement is not None and not isinstance(
            advancement, PlanRunProgressAdvanceResult
        ):
            raise invariant("WP034 advancement_result must be canonical or None")
        if preparation is not None and not isinstance(
            preparation, StepHandlingPreparationResult
        ):
            raise invariant("WP034 handling_preparation must be canonical or None")
        if subject is not None and not isinstance(subject, WorkSubject):
            raise invariant("WP034 work_subject must be canonical or None")
        if context is not None and not isinstance(context, ContextSnapshot):
            raise invariant("WP034 context_snapshot must be canonical or None")
        if decision is not None and not isinstance(decision, OrchestrationDecision):
            raise invariant("WP034 orchestration_decision must be canonical or None")
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
                "WP034 result does not match the supplied Plan, Run revision, and step"
            )
        if (update is None) != (advancement is None):
            raise invariant(
                "WP034 progress update and advancement must both exist or be absent"
            )
        if update is None:
            if any(
                artifact is not None
                for artifact in (preparation, subject, context, decision)
            ):
                raise invariant(
                    "WP034 cannot produce downstream artifacts without advancement"
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
                "WP034 update and advancement do not match the source operation"
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
            raise invariant(
                "WP034 selected-work artifacts must exactly match fresh selection"
            )
        if not selected:
            if decision is not None:
                raise invariant("WP034 cannot orchestrate without selected work")
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
        prepared = preparation.status is StepHandlingPreparationStatus.PREPARED
        if prepared != (decision is not None):
            raise invariant(
                "WP034 decision must exist if and only if selected handling is PREPARED"
            )
        if not prepared:
            return
        cls._validate_prepared_decision(
            plan,
            advancement,
            preparation,
            subject,
            context,
            decision,
        )

    @staticmethod
    def _validate_fresh_advancement(
        plan: Plan,
        run: PlanRun,
        advancement: PlanRunProgressAdvanceResult,
    ) -> None:
        invariant = PlanStepExecutionRequestMaterializationInvariantError
        updated_run = advancement.updated_run
        control = advancement.control_decision
        if not isinstance(updated_run, PlanRun):
            raise invariant("WP034 advancement must contain a canonical PlanRun")
        if not isinstance(control, ControlDecision):
            raise invariant("WP034 advancement must contain canonical fresh control")
        if (
            updated_run.plan_id != plan.plan_id
            or updated_run.run_id != run.run_id
            or updated_run.goal_id != run.goal_id
            or updated_run.revision != run.revision + 1
            or control.plan_id != plan.plan_id
            or control.run_id != updated_run.run_id
            or control.observed_revision != updated_run.revision
        ):
            raise invariant(
                "WP034 successor Run and fresh control lineage do not match"
            )
        try:
            validate_control_decision_current(plan, updated_run, control)
        except (PlanControlError, PlanRunError) as exc:
            raise invariant(
                "WP034 fresh control is not current for its successor Run"
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
        invariant = PlanStepExecutionRequestMaterializationInvariantError
        updated_run = advancement.updated_run
        selected_step_id = advancement.control_decision.selected_step_id
        if selected_step_id is None:
            raise invariant("fresh STEP_SELECTED control must identify one PlanStep")
        if (
            preparation.plan_id != plan.plan_id
            or preparation.run_id != updated_run.run_id
            or preparation.observed_revision != updated_run.revision
            or preparation.step_id != selected_step_id
        ):
            raise invariant("WP034 preparation does not match the fresh selection")
        if not isinstance(preparation.status, StepHandlingPreparationStatus):
            raise invariant("WP034 preparation status must be canonical")
        try:
            validate_step_handling_preparation_current(plan, updated_run, preparation)
        except (PlanHandlingError, PlanControlError, PlanRunError) as exc:
            raise invariant(
                "WP034 preparation is not current for the successor Run"
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
            raise invariant("WP034 subject does not identify the fresh selected work")
        if (
            context.subject is not subject
            or context.subject_id != subject.subject_id
            or context.budget != budget
            or context.created_at != utc_time(created_at, "created_at")
            or not isinstance(context.status, ResolutionStatus)
        ):
            raise invariant("WP034 ContextSnapshot does not match its subject/input")

    @staticmethod
    def _validate_prepared_decision(
        plan: Plan,
        advancement: PlanRunProgressAdvanceResult,
        preparation: StepHandlingPreparationResult,
        subject: WorkSubject,
        context: ContextSnapshot,
        decision: OrchestrationDecision | None,
    ) -> None:
        invariant = PlanStepExecutionRequestMaterializationInvariantError
        try:
            validate_step_handling_preparation_current(
                plan,
                advancement.updated_run,
                preparation,
            )
        except (PlanHandlingError, PlanControlError, PlanRunError) as exc:
            raise invariant(
                "PREPARED handling is not current for the successor Run"
            ) from exc
        need = preparation.handling_need
        if not isinstance(need, HandlingNeed) or need.blockers:
            raise invariant(
                "PREPARED handling must contain its canonical unmodified need"
            )
        if not isinstance(decision, OrchestrationDecision):
            raise invariant("PREPARED handling requires a canonical WP034 decision")
        try:
            validate_orchestration_decision_current(decision, subject, context)
        except (TypeError, ValueError) as exc:
            raise invariant(
                "WP034 decision is not current for the exact subject/context"
            ) from exc
        if decision.created_at < context.created_at:
            raise invariant("WP034 decision cannot predate its ContextSnapshot")
        if decision.need_ids != (need.need_id,):
            raise invariant("WP034 decision must account for the prepared need")
        if decision.requirement is not None and decision.requirement != need:
            raise invariant("WP034 decision selected a foreign handling requirement")
        if any(
            reference not in need.blockers for reference in decision.context_references
        ):
            raise invariant("WP034 decision references an unsupplied Context blocker")

    @staticmethod
    def _result(
        orchestration_result: PlanStepOrchestrationResult,
        execution_request: ExecutionRequest | None,
    ) -> PlanStepExecutionRequestMaterializationResult:
        return PlanStepExecutionRequestMaterializationResult(
            assessment=orchestration_result.assessment,
            transition_decision=orchestration_result.transition_decision,
            progress_update=orchestration_result.progress_update,
            advancement_result=orchestration_result.advancement_result,
            handling_preparation=orchestration_result.handling_preparation,
            work_subject=orchestration_result.work_subject,
            context_snapshot=orchestration_result.context_snapshot,
            orchestration_decision=orchestration_result.orchestration_decision,
            execution_request=execution_request,
        )
