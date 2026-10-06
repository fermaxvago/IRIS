"""Compose exact validated WP048 lineage with WP025 execution start, then stop."""

from __future__ import annotations

from copy import copy
from datetime import datetime

from iris.context import (
    ContextBudget,
    ContextCandidate,
    ContextSnapshot,
    ContextUncertainty,
    ResolutionStatus,
)
from iris.execution import ExecutionRequest
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
from iris.plan_runs import PlanRun, PlanRunError, validate_plan_run
from iris.plan_step_execution_binding import (
    PlanStepExecutionBinding,
    validate_plan_step_execution_binding_current,
)
from iris.plan_step_execution_binding_post_recording_composition import (
    PlanStepExecutionBindingPostRecordingComposer,
    PlanStepExecutionBindingPostRecordingCompositionResult,
)
from iris.plan_step_execution_start import (
    PlanStepExecutionStartCoordinator,
    PlanStepExecutionStartResult,
)
from iris.plan_step_execution_start_post_recording_composition.errors import (
    PlanStepExecutionStartPostRecordingCompositionInvariantError,
)
from iris.plan_step_execution_start_post_recording_composition.models import (
    PlanStepExecutionStartPostRecordingCompositionResult,
    _validate_run_shape,
    _validate_start_lineage,
)
from iris.planning import Plan
from iris.step_progress_transition import StepProgressTransitionDecision
from iris.work_identity import PlanStepWorkReference, WorkSubject, WorkSubjectKind


class PlanStepExecutionStartPostRecordingComposer:
    """Validate one WP048 result before delegating its Step C start to WP025."""

    def __init__(
        self,
        *,
        binding_composer: PlanStepExecutionBindingPostRecordingComposer,
        start_coordinator: PlanStepExecutionStartCoordinator,
    ) -> None:
        if not isinstance(
            binding_composer, PlanStepExecutionBindingPostRecordingComposer
        ):
            raise TypeError(
                "binding_composer must be a PlanStepExecutionBindingPostRecordingComposer"
            )
        if not isinstance(start_coordinator, PlanStepExecutionStartCoordinator):
            raise TypeError(
                "start_coordinator must be a PlanStepExecutionStartCoordinator"
            )
        self._binding_composer = binding_composer
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
        post_recording_candidates: tuple[ContextCandidate, ...],
        post_recording_budget: ContextBudget,
        post_recording_uncertainties: tuple[ContextUncertainty, ...] = (),
        post_recording_created_at: datetime,
        post_recording_availability: HandlerAvailability,
        post_recording_execution_input: ExecutionInput | None = None,
    ) -> PlanStepExecutionStartPostRecordingCompositionResult:
        """Invoke WP048 once; optionally invoke WP025 once, preserving errors; stop."""

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
            post_recording_candidates=post_recording_candidates,
            post_recording_budget=post_recording_budget,
            post_recording_uncertainties=post_recording_uncertainties,
            post_recording_created_at=post_recording_created_at,
            post_recording_availability=post_recording_availability,
            post_recording_execution_input=post_recording_execution_input,
        )
        self._validate_binding_result(
            plan,
            run,
            step_id,
            post_recording_budget,
            post_recording_created_at,
            post_recording_execution_input,
            binding_result,
        )

        binding = binding_result.post_recording_execution_binding
        if binding is None:
            return self._result(binding_result, None)
        advancement = binding_result.post_recording_advancement_result
        request = binding_result.post_recording_execution_request
        assert advancement is not None
        assert request is not None
        start_result = self._start_coordinator.start(
            plan, advancement.updated_run, binding, request
        )
        # Operational failures, including committed activation failures, are not caught.
        try:
            _validate_start_lineage(
                advancement.updated_run, binding, request, start_result
            )
            if start_result.active_run is not None:
                validate_plan_run(plan, start_result.active_run)
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise PlanStepExecutionStartPostRecordingCompositionInvariantError(
                "WP025 returned contradictory Step C start lineage"
            ) from exc
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
    def _validate_binding_result(
        plan: Plan,
        source_run: PlanRun,
        processed_step_id: str,
        post_recording_budget: ContextBudget,
        post_recording_created_at: datetime,
        post_recording_execution_input: ExecutionInput | None,
        result: PlanStepExecutionBindingPostRecordingCompositionResult,
    ) -> None:
        invariant = PlanStepExecutionStartPostRecordingCompositionInvariantError
        if not isinstance(
            result,
            PlanStepExecutionBindingPostRecordingCompositionResult,
        ):
            raise invariant(
                "WP048 must return a "
                "PlanStepExecutionBindingPostRecordingCompositionResult"
            )
        try:
            PlanStepExecutionBindingPostRecordingCompositionResult.__post_init__(result)
            runs = [source_run]
            if result.advancement_result is not None:
                runs.append(result.advancement_result.updated_run)
            if result.execution_start_result is not None:
                active = result.execution_start_result.active_run
                if active is not None:
                    runs.append(active)
            if result.execution_recording_result is not None:
                runs.append(result.execution_recording_result.recorded_run)
            if result.post_recording_advancement_result is not None:
                runs.append(result.post_recording_advancement_result.updated_run)
            for run in runs:
                _validate_run_shape(run)
                validate_plan_run(plan, run)
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise invariant("WP048 result violates its canonical contract") from exc

        assessment = result.assessment
        transition = result.transition_decision
        if not isinstance(assessment, StepOutcomeAssessment) or not isinstance(
            transition, StepProgressTransitionDecision
        ):
            raise invariant("WP048 must preserve canonical source decision artifacts")
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
                "WP048 result does not match the supplied Plan, source Run, and step"
            )

        advancement = result.post_recording_advancement_result
        preparation = result.post_recording_handling_preparation
        subject = result.post_recording_work_subject
        context = result.post_recording_context_snapshot
        if advancement is None:
            if any(item is not None for item in (preparation, subject, context)):
                raise invariant(
                    "WP048 cannot preserve Step C artifacts without advancement"
                )
            return

        successor = advancement.updated_run
        control = advancement.control_decision
        if not isinstance(successor, PlanRun) or not isinstance(
            control, ControlDecision
        ):
            raise invariant("WP048 advancement contains noncanonical artifacts")
        if (
            successor.plan_id != plan.plan_id
            or successor.run_id != source_run.run_id
            or successor.goal_id != source_run.goal_id
            or control.plan_id != plan.plan_id
            or control.run_id != successor.run_id
            or control.observed_revision != successor.revision
        ):
            raise invariant("WP048 successor Run and fresh control contradict input")
        try:
            ControlDecision.__post_init__(copy(control))
            validate_control_decision_current(plan, successor, control)
        except (
            PlanControlError,
            PlanRunError,
            TypeError,
            ValueError,
            AttributeError,
        ) as exc:
            raise invariant(
                "WP048 fresh control is not current for its exact successor Run"
            ) from exc

        if control.kind is not ControlDecisionKind.STEP_SELECTED:
            if any(item is not None for item in (preparation, subject, context)):
                raise invariant(
                    "WP048 non-selecting control cannot contain Step C artifacts"
                )
            return
        if control.selected_step_id is None:
            raise invariant("WP048 fresh selection must identify Step C")
        if not isinstance(preparation, StepHandlingPreparationResult):
            raise invariant("WP048 selected path requires canonical preparation")
        if not isinstance(preparation.status, StepHandlingPreparationStatus):
            raise invariant("WP048 preparation must contain a canonical status")
        if (
            preparation.plan_id != plan.plan_id
            or preparation.run_id != successor.run_id
            or preparation.observed_revision != successor.revision
            or preparation.step_id != control.selected_step_id
        ):
            raise invariant("WP048 preparation contradicts exact Step C selection")
        try:
            StepHandlingPreparationResult.__post_init__(copy(preparation))
            validate_step_handling_preparation_current(plan, successor, preparation)
        except (
            PlanHandlingError,
            PlanControlError,
            PlanRunError,
            TypeError,
            ValueError,
            AttributeError,
        ) as exc:
            raise invariant(
                "WP048 preparation is not current for exact Step C selection"
            ) from exc

        if not isinstance(subject, WorkSubject):
            raise invariant("WP048 selected path requires canonical WorkSubject")
        reference = subject.reference
        if (
            subject.kind is not WorkSubjectKind.PLAN_STEP
            or not isinstance(reference, PlanStepWorkReference)
            or reference.plan_id != plan.plan_id
            or reference.run_id != successor.run_id
            or reference.step_id != control.selected_step_id
            or subject.origin is not None
        ):
            raise invariant("WP048 WorkSubject does not identify exact Step C")

        if not isinstance(context, ContextSnapshot):
            raise invariant("WP048 selected path requires canonical ContextSnapshot")
        try:
            ContextSnapshot.__post_init__(copy(context))
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise invariant("WP048 returned a noncanonical ContextSnapshot") from exc
        if (
            context.subject is not subject
            or context.subject_id != subject.subject_id
            or context.budget != post_recording_budget
            or context.created_at
            != utc_time(post_recording_created_at, "post_recording_created_at")
            or not isinstance(context.status, ResolutionStatus)
        ):
            raise invariant("WP048 ContextSnapshot contradicts exact Step C inputs")
        start = result.execution_start_result
        if start is None or context.created_at < start.execution_result.completed_at:
            raise invariant("WP048 Step C Context predates its completed execution")

        decision = result.post_recording_orchestration_decision
        request = result.post_recording_execution_request
        if decision is None:
            return
        assert request is not None
        try:
            OrchestrationDecision.__post_init__(copy(decision))
            validate_orchestration_decision_current(decision, subject, context)
            ExecutionRequest.__post_init__(copy(request))
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise invariant("WP048 returned invalid decision/request lineage") from exc
        if request.execution_input is not post_recording_execution_input:
            raise invariant("WP048 request does not preserve the exact Step C input")
        binding = result.post_recording_execution_binding
        if not isinstance(binding, PlanStepExecutionBinding):
            raise invariant("WP048 request requires its exact canonical binding")
        try:
            validate_plan_step_execution_binding_current(plan, successor, binding)
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise invariant(
                "WP048 binding is not current for the exact Step C Run"
            ) from exc

    @staticmethod
    def _result(
        binding_result: PlanStepExecutionBindingPostRecordingCompositionResult,
        start_result: PlanStepExecutionStartResult | None,
    ) -> PlanStepExecutionStartPostRecordingCompositionResult:
        return PlanStepExecutionStartPostRecordingCompositionResult(
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
            execution_start_result=binding_result.execution_start_result,
            execution_recording_result=binding_result.execution_recording_result,
            post_recording_assessment=binding_result.post_recording_assessment,
            post_recording_transition_decision=(
                binding_result.post_recording_transition_decision
            ),
            post_recording_progress_update=(
                binding_result.post_recording_progress_update
            ),
            post_recording_advancement_result=(
                binding_result.post_recording_advancement_result
            ),
            post_recording_handling_preparation=(
                binding_result.post_recording_handling_preparation
            ),
            post_recording_work_subject=binding_result.post_recording_work_subject,
            post_recording_context_snapshot=(
                binding_result.post_recording_context_snapshot
            ),
            post_recording_orchestration_decision=(
                binding_result.post_recording_orchestration_decision
            ),
            post_recording_execution_request=binding_result.post_recording_execution_request,
            post_recording_execution_binding=binding_result.post_recording_execution_binding,
            post_recording_execution_start_result=start_result,
        )
