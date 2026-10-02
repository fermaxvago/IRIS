"""Compose one WP032 result with optional exact WP016 Context materialization."""

from __future__ import annotations

from datetime import datetime

from iris.context import (
    ContextBudget,
    ContextCandidate,
    ContextEngine,
    ContextSnapshot,
    ContextUncertainty,
)
from iris.memory.models import utc_time
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
    validate_step_handling_preparation_current,
)
from iris.plan_run_advancement import PlanRunProgressAdvanceResult
from iris.plan_runs import PlanRun, PlanRunError, StepProgressUpdate
from iris.plan_step_context_materialization.errors import (
    PlanStepContextMaterializationInvariantError,
)
from iris.plan_step_context_materialization.models import (
    PlanStepContextMaterializationResult,
)
from iris.plan_step_work_subject_materialization import (
    PlanStepWorkSubjectMaterializationResult,
    PlanStepWorkSubjectMaterializer,
)
from iris.planning import Plan
from iris.step_progress_transition import StepProgressTransitionDecision
from iris.work_identity import PlanStepWorkReference, WorkSubject, WorkSubjectKind


class PlanStepContextMaterializer:
    """Materialize selected work once, build its explicit Context once, stop."""

    def __init__(
        self,
        *,
        work_subject_materializer: PlanStepWorkSubjectMaterializer | None = None,
        context_engine: ContextEngine | None = None,
    ) -> None:
        if work_subject_materializer is not None and not isinstance(
            work_subject_materializer, PlanStepWorkSubjectMaterializer
        ):
            raise TypeError(
                "work_subject_materializer must be a PlanStepWorkSubjectMaterializer"
            )
        if context_engine is not None and not isinstance(context_engine, ContextEngine):
            raise TypeError("context_engine must be a ContextEngine")
        self._work_subject_materializer = (
            PlanStepWorkSubjectMaterializer()
            if work_subject_materializer is None
            else work_subject_materializer
        )
        self._context_engine = (
            ContextEngine() if context_engine is None else context_engine
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
    ) -> PlanStepContextMaterializationResult:
        """Return WP032 artifacts and zero or one exact WP016 snapshot."""

        self._validate_input_types(
            plan,
            run,
            step_id,
            candidates,
            budget,
            uncertainties,
            created_at,
        )
        work = self._work_subject_materializer.materialize(plan, run, step_id)
        self._validate_work_result(plan, run, step_id, work)

        subject = work.work_subject
        if subject is None:
            return self._result(work, None)

        snapshot = self._context_engine.build(
            subject=subject,
            candidates=candidates,
            budget=budget,
            uncertainties=uncertainties,
            created_at=created_at,
        )
        self._validate_snapshot(subject, budget, created_at, snapshot)
        return self._result(work, snapshot)

    @staticmethod
    def _validate_input_types(
        plan: Plan,
        run: PlanRun,
        step_id: str,
        candidates: tuple[ContextCandidate, ...],
        budget: ContextBudget,
        uncertainties: tuple[ContextUncertainty, ...],
        created_at: datetime,
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

    @classmethod
    def _validate_work_result(
        cls,
        plan: Plan,
        run: PlanRun,
        step_id: str,
        result: PlanStepWorkSubjectMaterializationResult,
    ) -> None:
        if not isinstance(result, PlanStepWorkSubjectMaterializationResult):
            raise PlanStepContextMaterializationInvariantError(
                "WP032 materializer must return a "
                "PlanStepWorkSubjectMaterializationResult"
            )
        assessment = result.assessment
        decision = result.transition_decision
        update = result.progress_update
        advancement = result.advancement_result
        preparation = result.handling_preparation
        subject = result.work_subject
        if not isinstance(assessment, StepOutcomeAssessment) or not isinstance(
            decision, StepProgressTransitionDecision
        ):
            raise PlanStepContextMaterializationInvariantError(
                "WP032 result must contain canonical assessment and decision types"
            )
        if update is not None and not isinstance(update, StepProgressUpdate):
            raise PlanStepContextMaterializationInvariantError(
                "WP032 progress_update must be a StepProgressUpdate or None"
            )
        if advancement is not None and not isinstance(
            advancement, PlanRunProgressAdvanceResult
        ):
            raise PlanStepContextMaterializationInvariantError(
                "WP032 advancement_result must be canonical or None"
            )
        if preparation is not None and not isinstance(
            preparation, StepHandlingPreparationResult
        ):
            raise PlanStepContextMaterializationInvariantError(
                "WP032 handling_preparation must be canonical or None"
            )
        if subject is not None and not isinstance(subject, WorkSubject):
            raise PlanStepContextMaterializationInvariantError(
                "WP032 work_subject must be canonical or None"
            )
        if (
            assessment.plan_id != plan.plan_id
            or assessment.run_id != run.run_id
            or assessment.run_revision != run.revision
            or assessment.step_id != step_id
            or decision.plan_id != plan.plan_id
            or decision.run_id != run.run_id
            or decision.observed_revision != run.revision
            or decision.step_id != step_id
            or decision.assessment_id != assessment.assessment_id
        ):
            raise PlanStepContextMaterializationInvariantError(
                "WP032 result does not match the supplied Plan, Run revision, and step"
            )
        if (update is None) != (advancement is None):
            raise PlanStepContextMaterializationInvariantError(
                "WP032 progress update and advancement must both exist or be absent"
            )
        if update is None:
            if preparation is not None or subject is not None:
                raise PlanStepContextMaterializationInvariantError(
                    "WP032 cannot produce selected-work artifacts without advancement"
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
            raise PlanStepContextMaterializationInvariantError(
                "WP032 update and advancement do not match the source operation"
            )
        cls._validate_fresh_advancement(plan, run, advancement)

        selected = (
            advancement.control_decision.kind is ControlDecisionKind.STEP_SELECTED
        )
        if selected != (preparation is not None) or selected != (subject is not None):
            raise PlanStepContextMaterializationInvariantError(
                "WP032 selected-work artifacts must exactly match fresh selection"
            )
        if not selected:
            return
        assert preparation is not None
        assert subject is not None
        cls._validate_selected_work(plan, advancement, preparation, subject)

    @staticmethod
    def _validate_fresh_advancement(
        plan: Plan,
        run: PlanRun,
        advancement: PlanRunProgressAdvanceResult,
    ) -> None:
        updated_run = advancement.updated_run
        control = advancement.control_decision
        if not isinstance(updated_run, PlanRun):
            raise PlanStepContextMaterializationInvariantError(
                "WP032 advancement must contain a canonical PlanRun"
            )
        if not isinstance(control, ControlDecision):
            raise PlanStepContextMaterializationInvariantError(
                "WP032 advancement must contain a canonical ControlDecision"
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
            raise PlanStepContextMaterializationInvariantError(
                "WP032 successor Run and fresh control lineage do not match"
            )
        try:
            validate_control_decision_current(plan, updated_run, control)
        except (PlanControlError, PlanRunError) as exc:
            raise PlanStepContextMaterializationInvariantError(
                "WP032 fresh control is not current for its successor Run"
            ) from exc

    @staticmethod
    def _validate_selected_work(
        plan: Plan,
        advancement: PlanRunProgressAdvanceResult,
        preparation: StepHandlingPreparationResult,
        subject: WorkSubject,
    ) -> None:
        updated_run = advancement.updated_run
        control = advancement.control_decision
        selected_step_id = control.selected_step_id
        if selected_step_id is None:
            raise PlanStepContextMaterializationInvariantError(
                "fresh STEP_SELECTED control must identify one PlanStep"
            )
        if (
            preparation.plan_id != plan.plan_id
            or preparation.run_id != updated_run.run_id
            or preparation.observed_revision != updated_run.revision
            or preparation.step_id != selected_step_id
        ):
            raise PlanStepContextMaterializationInvariantError(
                "WP032 preparation does not match the exact fresh selection"
            )
        try:
            validate_step_handling_preparation_current(plan, updated_run, preparation)
        except (PlanHandlingError, PlanControlError, PlanRunError) as exc:
            raise PlanStepContextMaterializationInvariantError(
                "WP032 preparation is not current for the exact successor selection"
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
            raise PlanStepContextMaterializationInvariantError(
                "WP032 subject does not identify the exact selected work without origin"
            )

    @staticmethod
    def _validate_snapshot(
        subject: WorkSubject,
        budget: ContextBudget,
        created_at: datetime,
        snapshot: ContextSnapshot,
    ) -> None:
        if not isinstance(snapshot, ContextSnapshot):
            raise PlanStepContextMaterializationInvariantError(
                "WP016 ContextEngine must return a ContextSnapshot"
            )
        if snapshot.subject is not subject or snapshot.subject_id != subject.subject_id:
            raise PlanStepContextMaterializationInvariantError(
                "WP016 snapshot must preserve the exact WP032 WorkSubject owner"
            )
        if snapshot.budget != budget:
            raise PlanStepContextMaterializationInvariantError(
                "WP016 snapshot budget does not match the supplied ContextBudget"
            )
        if snapshot.created_at != utc_time(created_at, "created_at"):
            raise PlanStepContextMaterializationInvariantError(
                "WP016 snapshot time does not match the supplied created_at"
            )

    @staticmethod
    def _result(
        work: PlanStepWorkSubjectMaterializationResult,
        snapshot: ContextSnapshot | None,
    ) -> PlanStepContextMaterializationResult:
        return PlanStepContextMaterializationResult(
            assessment=work.assessment,
            transition_decision=work.transition_decision,
            progress_update=work.progress_update,
            advancement_result=work.advancement_result,
            handling_preparation=work.handling_preparation,
            work_subject=work.work_subject,
            context_snapshot=snapshot,
        )
