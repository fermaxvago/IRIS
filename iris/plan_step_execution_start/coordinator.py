"""Compose one current PlanStep binding with the real execution-start boundary."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from iris.execution import (
    ExecutionCoordinator,
    ExecutionRequest,
    ExecutionStartGate,
)
from iris.plan_runs import (
    PlanRun,
    PlanRunReducer,
    RunProvenance,
    StepProgressState,
    StepProgressUpdate,
)
from iris.plan_step_execution_binding import (
    PlanStepExecutionBinding,
    validate_plan_step_execution_binding_current,
)
from iris.plan_step_execution_start.errors import (
    PlanStepExecutionInvocationError,
    PlanStepExecutionRequestMismatchError,
    PlanStepExecutionStartGenerationError,
    PlanStepExecutionStartInvariantError,
)
from iris.plan_step_execution_start.models import PlanStepExecutionStartResult
from iris.planning import Plan
from iris.work_identity import PlanStepWorkReference, WorkSubjectKind


def _validate_inputs(
    plan: Plan,
    run: PlanRun,
    binding: PlanStepExecutionBinding,
    execution_request: ExecutionRequest,
) -> None:
    for value, expected, name in (
        (plan, Plan, "plan"),
        (run, PlanRun, "run"),
        (binding, PlanStepExecutionBinding, "binding"),
        (execution_request, ExecutionRequest, "execution_request"),
    ):
        if not isinstance(value, expected):
            raise TypeError(f"{name} must be a {expected.__name__}")


def _validate_request_lineage(
    binding: PlanStepExecutionBinding,
    request: ExecutionRequest,
) -> None:
    subject = request.subject
    decision = request.decision
    reference = subject.reference
    requirement = decision.requirement
    if (
        request.execution_id != binding.execution_id
        or subject.subject_id != binding.subject_id
        or decision.decision_id != binding.orchestration_decision_id
        or request.context.snapshot_id != binding.context_snapshot_id
        or subject.kind is not WorkSubjectKind.PLAN_STEP
        or not isinstance(reference, PlanStepWorkReference)
        or reference.plan_id != binding.plan_id
        or reference.run_id != binding.run_id
        or reference.step_id != binding.step_id
        or requirement is None
        or requirement.need_id != binding.handling_need_id
    ):
        raise PlanStepExecutionRequestMismatchError(
            "ExecutionRequest does not match PlanStepExecutionBinding lineage"
        )


class _PlanStepActivationGate(ExecutionStartGate):
    def __init__(
        self,
        *,
        plan: Plan,
        run: PlanRun,
        binding: PlanStepExecutionBinding,
        reducer: PlanRunReducer,
        update_id_factory: Callable[[], str],
    ) -> None:
        self._plan = plan
        self._run = run
        self._binding = binding
        self._reducer = reducer
        self._update_id_factory = update_id_factory
        self.active_run: PlanRun | None = None
        self.activation_update_id: str | None = None

    def commit_start(
        self,
        request: ExecutionRequest,
        *,
        start_boundary_at: datetime,
        handler_reference: str,
    ) -> None:
        validate_plan_step_execution_binding_current(
            self._plan,
            self._run,
            self._binding,
        )
        _validate_request_lineage(self._binding, request)
        if not isinstance(handler_reference, str) or not handler_reference.strip():
            raise PlanStepExecutionStartInvariantError(
                "resolved handler reference must be nonblank"
            )
        update_id = self._generate_update_id()
        update = StepProgressUpdate(
            update_id=update_id,
            run_id=self._run.run_id,
            expected_revision=self._binding.observed_revision,
            updated_at=start_boundary_at,
            provenance=RunProvenance(
                source_type="plan_step_execution_start",
                source_id=request.execution_id,
                actor=None,
            ),
            step_id=self._binding.step_id,
            new_state=StepProgressState.ACTIVE,
            evidence_ids=(),
        )
        active_run = self._reducer.apply(self._plan, self._run, update)
        progress = next(
            (
                item
                for item in active_run.step_progress
                if item.step_id == self._binding.step_id
            ),
            None,
        )
        if (
            active_run.revision != self._run.revision + 1
            or progress is None
            or progress.state is not StepProgressState.ACTIVE
        ):
            raise PlanStepExecutionStartInvariantError(
                "activation must derive revision N+1 with the bound step ACTIVE"
            )
        self.activation_update_id = update_id
        self.active_run = active_run

    def _generate_update_id(self) -> str:
        try:
            update_id = self._update_id_factory()
        except Exception as exc:
            raise PlanStepExecutionStartGenerationError(
                "activation update identity generation failed"
            ) from exc
        reserved = {
            self._binding.plan_id,
            self._binding.run_id,
            self._binding.step_id,
            self._binding.execution_id,
            self._binding.subject_id,
            self._binding.orchestration_decision_id,
            self._binding.context_snapshot_id,
            self._binding.handling_need_id,
        }
        if (
            not isinstance(update_id, str)
            or not update_id
            or update_id != update_id.strip()
            or update_id in reserved
        ):
            raise PlanStepExecutionStartGenerationError(
                "activation update identity must be new and nonblank"
            )
        return update_id


class PlanStepExecutionStartCoordinator:
    """Activate one bound PlanStep immediately before its handler is invoked."""

    def __init__(
        self,
        execution_coordinator: ExecutionCoordinator,
        *,
        reducer: PlanRunReducer | None = None,
        update_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if not isinstance(execution_coordinator, ExecutionCoordinator):
            raise TypeError("execution_coordinator must be an ExecutionCoordinator")
        if reducer is not None and not isinstance(reducer, PlanRunReducer):
            raise TypeError("reducer must be a PlanRunReducer")
        if update_id_factory is not None and not callable(update_id_factory):
            raise TypeError("update_id_factory must be callable")
        self._execution_coordinator = execution_coordinator
        self._reducer = PlanRunReducer() if reducer is None else reducer
        self._update_id_factory = (
            (lambda: uuid4().hex) if update_id_factory is None else update_id_factory
        )

    def start(
        self,
        plan: Plan,
        run: PlanRun,
        binding: PlanStepExecutionBinding,
        execution_request: ExecutionRequest,
    ) -> PlanStepExecutionStartResult:
        """Commit ACTIVE only for an available handler, invoke once, then stop."""

        _validate_inputs(plan, run, binding, execution_request)
        validate_plan_step_execution_binding_current(plan, run, binding)
        _validate_request_lineage(binding, execution_request)
        gate = _PlanStepActivationGate(
            plan=plan,
            run=run,
            binding=binding,
            reducer=self._reducer,
            update_id_factory=self._update_id_factory,
        )
        try:
            execution_result = self._execution_coordinator.execute(
                execution_request,
                start_gate=gate,
            )
        except Exception as exc:
            if gate.active_run is None or gate.activation_update_id is None:
                raise
            raise PlanStepExecutionInvocationError(
                "execution failed after PlanStep activation",
                active_run=gate.active_run,
                activation_update_id=gate.activation_update_id,
                execution_id=execution_request.execution_id,
            ) from exc

        return PlanStepExecutionStartResult(
            plan_id=binding.plan_id,
            run_id=binding.run_id,
            source_revision=binding.observed_revision,
            step_id=binding.step_id,
            execution_id=binding.execution_id,
            activation_update_id=gate.activation_update_id,
            active_run=gate.active_run,
            execution_result=execution_result,
        )
