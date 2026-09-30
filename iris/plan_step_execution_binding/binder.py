"""Deterministic binding of selected PlanStep lineage to an ExecutionRequest."""

from iris.execution import ExecutionRequest
from iris.orchestrator import OrchestrationTarget
from iris.plan_control import (
    ControlDecision,
    ControlDecisionKind,
    validate_control_decision_current,
)
from iris.plan_handling import (
    StepHandlingPreparationResult,
    StepHandlingPreparationStatus,
    validate_step_handling_preparation_current,
)
from iris.plan_runs import (
    PlanRun,
    StepAvailability,
    StepProgressState,
    derive_step_availability,
    validate_plan_run,
)
from iris.plan_step_execution_binding.errors import (
    ExecutionBindingMismatchError,
    NonBindableControlDecisionError,
    NonBindableHandlingPreparationError,
    NonExecutableExecutionRequestError,
    PlanStepExecutionBindingInvariantError,
    StalePlanStepExecutionBindingError,
)
from iris.plan_step_execution_binding.models import PlanStepExecutionBinding
from iris.planning import Plan
from iris.work_identity import (
    PlanStepWorkReference,
    WorkSubjectKind,
)

_EXECUTABLE_TARGETS = frozenset(
    {
        OrchestrationTarget.SYSTEM,
        OrchestrationTarget.MEMORY,
        OrchestrationTarget.CAPABILITY,
        OrchestrationTarget.INTELLIGENCE,
    }
)


def _validate_types(
    plan: Plan,
    run: PlanRun,
    control_decision: ControlDecision,
    preparation: StepHandlingPreparationResult,
    execution_request: ExecutionRequest,
) -> None:
    for value, expected, name in (
        (plan, Plan, "plan"),
        (run, PlanRun, "run"),
        (control_decision, ControlDecision, "control_decision"),
        (
            preparation,
            StepHandlingPreparationResult,
            "preparation",
        ),
        (execution_request, ExecutionRequest, "execution_request"),
    ):
        if not isinstance(value, expected):
            raise TypeError(f"{name} must be a {expected.__name__}")


def _require_pre_activation_step(plan: Plan, run: PlanRun, step_id: str) -> None:
    progress = next(
        (item for item in run.step_progress if item.step_id == step_id),
        None,
    )
    if progress is None:
        raise PlanStepExecutionBindingInvariantError(
            f"selected step {step_id} has no canonical progress record"
        )
    if progress.state is not StepProgressState.NOT_STARTED:
        raise StalePlanStepExecutionBindingError(
            f"step {step_id} is {progress.state.value}, not NOT_STARTED"
        )
    availability = derive_step_availability(plan, run, step_id).availability
    if availability is not StepAvailability.READY:
        raise StalePlanStepExecutionBindingError(
            f"step {step_id} is {availability.value}, not READY"
        )


class PlanStepExecutionBinder:
    """Prove execution lineage for one selected, prepared, current PlanStep."""

    def bind(
        self,
        plan: Plan,
        run: PlanRun,
        control_decision: ControlDecision,
        preparation: StepHandlingPreparationResult,
        execution_request: ExecutionRequest,
    ) -> PlanStepExecutionBinding:
        _validate_types(
            plan,
            run,
            control_decision,
            preparation,
            execution_request,
        )
        validate_plan_run(plan, run)
        validate_control_decision_current(plan, run, control_decision)
        if control_decision.kind is not ControlDecisionKind.STEP_SELECTED:
            raise NonBindableControlDecisionError(
                f"{control_decision.kind.value} does not select PlanStep execution"
            )
        step_id = control_decision.selected_step_id
        if step_id is None or not any(item.step_id == step_id for item in plan.steps):
            raise PlanStepExecutionBindingInvariantError(
                "STEP_SELECTED must identify a canonical PlanStep"
            )

        validate_step_handling_preparation_current(plan, run, preparation)
        if preparation.status is not StepHandlingPreparationStatus.PREPARED:
            raise NonBindableHandlingPreparationError(
                f"{preparation.status.value} does not provide executable handling"
            )
        if preparation.step_id != step_id:
            raise ExecutionBindingMismatchError(
                "selected and prepared PlanStep identities differ"
            )
        need = preparation.handling_need
        if need is None:
            raise PlanStepExecutionBindingInvariantError(
                "PREPARED handling must contain a HandlingNeed"
            )

        _require_pre_activation_step(plan, run, step_id)

        subject = execution_request.subject
        if subject.kind is not WorkSubjectKind.PLAN_STEP:
            raise ExecutionBindingMismatchError(
                "execution request subject must be PLAN_STEP"
            )
        reference = subject.reference
        if not isinstance(reference, PlanStepWorkReference):
            raise ExecutionBindingMismatchError(
                "PLAN_STEP execution requires a PlanStepWorkReference"
            )
        if (
            reference.plan_id != plan.plan_id
            or reference.run_id != run.run_id
            or reference.step_id != step_id
        ):
            raise ExecutionBindingMismatchError(
                "execution request PlanStep reference does not match selected work"
            )

        decision = execution_request.decision
        if decision.target not in _EXECUTABLE_TARGETS:
            raise NonExecutableExecutionRequestError(
                f"orchestration target {decision.target.value} is not executable"
            )
        if decision.requirement != need:
            raise ExecutionBindingMismatchError(
                "orchestration requirement does not match prepared HandlingNeed"
            )

        return PlanStepExecutionBinding(
            plan_id=plan.plan_id,
            run_id=run.run_id,
            observed_revision=run.revision,
            step_id=step_id,
            execution_id=execution_request.execution_id,
            subject_id=subject.subject_id,
            orchestration_decision_id=decision.decision_id,
            context_snapshot_id=execution_request.context.snapshot_id,
            handling_need_id=need.need_id,
        )


def validate_plan_step_execution_binding_current(
    plan: Plan,
    run: PlanRun,
    binding: PlanStepExecutionBinding,
) -> None:
    """Reject a binding that no longer matches the exact pre-activation Run."""

    if not isinstance(plan, Plan):
        raise TypeError("plan must be a Plan")
    if not isinstance(run, PlanRun):
        raise TypeError("run must be a PlanRun")
    if not isinstance(binding, PlanStepExecutionBinding):
        raise TypeError("binding must be a PlanStepExecutionBinding")
    validate_plan_run(plan, run)
    if binding.plan_id != plan.plan_id:
        raise PlanStepExecutionBindingInvariantError(
            "binding references a different Plan"
        )
    if binding.run_id != run.run_id:
        raise PlanStepExecutionBindingInvariantError(
            "binding references a different PlanRun"
        )
    if binding.observed_revision != run.revision:
        raise StalePlanStepExecutionBindingError(
            "binding observed revision "
            f"{binding.observed_revision}; current revision is {run.revision}"
        )
    if not any(item.step_id == binding.step_id for item in plan.steps):
        raise PlanStepExecutionBindingInvariantError(
            f"binding step {binding.step_id} does not exist in Plan"
        )
    _require_pre_activation_step(plan, run, binding.step_id)
