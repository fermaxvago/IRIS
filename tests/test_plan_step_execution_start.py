"""WP025 PlanStep activation at the concrete handler invocation boundary."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from iris.context import ContextBudget, ContextEngine
from iris.execution import (
    ExecutionContractError,
    ExecutionCoordinator,
    ExecutionFailure,
    ExecutionRequest,
    ExecutionStartGate,
    ExecutionStatus,
    HandlerOutcome,
    SystemExecutionInput,
)
from iris.orchestrator import (
    HandlerAvailability,
    HandlingKind,
    HandlingNeed,
    OrchestrationInput,
    OrchestrationTarget,
    Orchestrator,
)
from iris.plan_control import PlanRunController
from iris.plan_handling import (
    PlanStepHandlingPreparer,
    StepHandlingSpecification,
)
from iris.plan_runs import (
    InvalidStepTransitionError,
    PlanRun,
    PlanRunFactory,
    PlanRunReducer,
    PlanRunUpdate,
    StepProgressState,
)
from iris.plan_step_execution_binding import (
    PlanStepExecutionBinder,
    PlanStepExecutionBinding,
    StalePlanStepExecutionBindingError,
)
from iris.plan_step_execution_start import (
    PlanStepExecutionInvocationError,
    PlanStepExecutionRequestMismatchError,
    PlanStepExecutionStartCoordinator,
    PlanStepExecutionStartGenerationError,
    PlanStepExecutionStartInvariantError,
    PlanStepExecutionStartResult,
)
from iris.planning import Plan, PlanStep
from iris.router import RouteTarget
from iris.work_identity import (
    PlanStepWorkReference,
    WorkSubject,
    WorkSubjectKind,
)

NOW = datetime(2026, 9, 30, 16, tzinfo=UTC)
DECIDED = NOW + timedelta(seconds=1)
ATTEMPT_STARTED = NOW + timedelta(seconds=2)
START_BOUNDARY = NOW + timedelta(seconds=3)
COMPLETED = NOW + timedelta(seconds=4)


class ClockSequence:
    def __init__(self, *values: datetime) -> None:
        self._values = iter(values)

    def __call__(self) -> datetime:
        return next(self._values)


@dataclass
class RecordingHandler:
    outcome: HandlerOutcome = field(
        default_factory=lambda: HandlerOutcome(ExecutionStatus.SUCCEEDED)
    )
    error: Exception | None = None
    invalid_outcome: bool = False
    calls: list[ExecutionRequest] = field(default_factory=list)

    @property
    def target(self) -> OrchestrationTarget:
        return OrchestrationTarget.SYSTEM

    @property
    def handler_reference(self) -> str:
        return "handler.system.recording"

    def execute(self, request: ExecutionRequest) -> HandlerOutcome:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        if self.invalid_outcome:
            return cast(HandlerOutcome, object())
        return self.outcome


class CountingReducer(PlanRunReducer):
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[tuple[Plan, PlanRun, PlanRunUpdate]] = []
        self.error = error

    def apply(self, plan: Plan, run: PlanRun, update: PlanRunUpdate) -> PlanRun:
        self.calls.append((plan, run, update))
        if self.error is not None:
            raise self.error
        return super().apply(plan, run, update)


def _plan() -> Plan:
    return Plan(
        "plan-1",
        "goal-1",
        (),
        (
            PlanStep(
                "step-a",
                "Execute A",
                "A is complete",
                (),
                HandlingKind.SYSTEM,
            ),
        ),
    )


def _run(plan: Plan) -> PlanRun:
    return PlanRunFactory(
        clock=lambda: NOW,
        run_id_factory=lambda: "run-1",
    ).create(plan)


def _execution(
    plan: Plan,
    run: PlanRun,
    need: HandlingNeed,
    *,
    execution_id: str = "execution-1",
    reference: PlanStepWorkReference | None = None,
) -> ExecutionRequest:
    work_reference = (
        PlanStepWorkReference(plan.plan_id, run.run_id, "step-a")
        if reference is None
        else reference
    )
    subject = WorkSubject(WorkSubjectKind.PLAN_STEP, work_reference)
    context = ContextEngine().build(
        subject=subject,
        candidates=(),
        budget=ContextBudget(0),
        created_at=NOW,
    )
    decision = Orchestrator(
        clock=lambda: DECIDED,
        id_factory=lambda: "orchestration-1",
    ).decide(
        OrchestrationInput(
            subject,
            context,
            (need,),
            HandlerAvailability(system=True),
        )
    )
    return ExecutionRequest(
        execution_id,
        subject,
        context,
        decision,
        DECIDED,
        SystemExecutionInput(),
    )


def valid_inputs() -> tuple[Plan, PlanRun, PlanStepExecutionBinding, ExecutionRequest]:
    plan = _plan()
    run = _run(plan)
    control = PlanRunController().decide(plan, run)
    preparation = PlanStepHandlingPreparer().prepare(
        plan,
        run,
        control,
        StepHandlingSpecification(
            "step-a",
            HandlingKind.SYSTEM,
            system_route=RouteTarget.SYSTEM_STATUS,
        ),
    )
    assert preparation.handling_need is not None
    execution = _execution(plan, run, preparation.handling_need)
    binding = PlanStepExecutionBinder().bind(
        plan,
        run,
        control,
        preparation,
        execution,
    )
    return plan, run, binding, execution


def start_coordinator(
    handler: RecordingHandler | None,
    *,
    reducer: PlanRunReducer | None = None,
    update_id_factory: Callable[[], str] = lambda: "activation-update-1",
    clock: Callable[[], datetime] | None = None,
) -> PlanStepExecutionStartCoordinator:
    handlers = () if handler is None else (handler,)
    runtime_clock = (
        ClockSequence(ATTEMPT_STARTED, START_BOUNDARY, COMPLETED)
        if clock is None
        else clock
    )
    return PlanStepExecutionStartCoordinator(
        ExecutionCoordinator(handlers, clock=runtime_clock),
        reducer=reducer,
        update_id_factory=update_id_factory,
    )


def test_public_api_and_generic_gate_export() -> None:
    assert PlanStepExecutionStartCoordinator.__name__.endswith("Coordinator")
    assert PlanStepExecutionStartResult.__name__.endswith("Result")
    assert ExecutionStartGate.__name__ == "ExecutionStartGate"


@pytest.mark.parametrize(
    ("position", "bad_value", "message"),
    [
        (0, object(), "plan must be a Plan"),
        (1, object(), "run must be a PlanRun"),
        (2, object(), "binding must be a PlanStepExecutionBinding"),
        (3, object(), "execution_request must be a ExecutionRequest"),
    ],
)
def test_start_rejects_wrong_top_level_types(
    position: int,
    bad_value: object,
    message: str,
) -> None:
    values: list[object] = list(valid_inputs())
    values[position] = bad_value
    coordinator = start_coordinator(RecordingHandler())

    with pytest.raises(TypeError, match=message):
        coordinator.start(*cast(Any, values))


def test_happy_path_activates_then_invokes_exact_handler_once() -> None:
    plan, run, binding, execution = valid_inputs()
    handler = RecordingHandler()
    reducer = CountingReducer()

    result = start_coordinator(handler, reducer=reducer).start(
        plan, run, binding, execution
    )

    assert len(reducer.calls) == 1
    assert len(handler.calls) == 1
    assert handler.calls[0] is execution
    assert result.source_revision == run.revision
    assert result.active_run is not None
    assert result.active_run is not run
    assert result.active_run.revision == run.revision + 1
    assert result.active_run.updated_at == START_BOUNDARY
    assert result.activation_update_id == "activation-update-1"
    assert result.execution_result.status is ExecutionStatus.SUCCEEDED
    assert result.execution_result.started_at == ATTEMPT_STARTED
    assert result.execution_result.completed_at == COMPLETED
    assert run.step_progress[0].state is StepProgressState.NOT_STARTED
    assert result.active_run.step_progress[0].state is StepProgressState.ACTIVE


def test_activation_update_has_canonical_lineage_and_timestamp() -> None:
    plan, run, binding, execution = valid_inputs()
    reducer = CountingReducer()

    start_coordinator(RecordingHandler(), reducer=reducer).start(
        plan, run, binding, execution
    )

    update = reducer.calls[0][2]
    assert update.update_id == "activation-update-1"
    assert update.run_id == run.run_id
    assert update.expected_revision == binding.observed_revision
    assert update.updated_at == START_BOUNDARY
    assert update.provenance.source_type == "plan_step_execution_start"
    assert update.provenance.source_id == execution.execution_id
    assert update.provenance.actor is None
    assert update.to_data()["new_state"] == "active"
    assert update.to_data()["evidence_ids"] == []


def test_handler_unavailable_rejects_without_activation() -> None:
    plan, run, binding, execution = valid_inputs()
    reducer = CountingReducer()
    result = start_coordinator(None, reducer=reducer).start(
        plan, run, binding, execution
    )

    assert reducer.calls == []
    assert result.active_run is None
    assert result.activation_update_id is None
    assert result.execution_result.status is ExecutionStatus.REJECTED
    assert result.execution_result.handler_reference is None
    assert result.execution_result.failure is not None
    assert result.execution_result.failure.code == "handler_unavailable"
    assert run.step_progress[0].state is StepProgressState.NOT_STARTED


def test_stale_binding_fails_before_runtime_or_reducer() -> None:
    plan, run, binding, execution = valid_inputs()
    stale = replace(binding, observed_revision=run.revision + 1)
    handler = RecordingHandler()
    reducer = CountingReducer()

    with pytest.raises(StalePlanStepExecutionBindingError):
        start_coordinator(handler, reducer=reducer).start(plan, run, stale, execution)
    assert reducer.calls == []
    assert handler.calls == []


@pytest.mark.parametrize(
    ("field_name", "wrong_value"),
    [
        ("execution_id", "execution-other"),
        ("subject_id", "subject-other"),
        ("orchestration_decision_id", "decision-other"),
        ("context_snapshot_id", "context-other"),
        ("handling_need_id", "need-other"),
    ],
)
def test_binding_request_lineage_mismatch_prevents_activation(
    field_name: str,
    wrong_value: str,
) -> None:
    plan, run, binding, execution = valid_inputs()
    mismatched = replace(binding, **{field_name: wrong_value})
    handler = RecordingHandler()
    reducer = CountingReducer()

    with pytest.raises(PlanStepExecutionRequestMismatchError):
        start_coordinator(handler, reducer=reducer).start(
            plan, run, mismatched, execution
        )
    assert reducer.calls == []
    assert handler.calls == []


def test_request_plan_step_reference_mismatch_prevents_activation() -> None:
    plan, run, binding, execution = valid_inputs()
    assert execution.decision.requirement is not None
    other = _execution(
        plan,
        run,
        execution.decision.requirement,
        reference=PlanStepWorkReference("plan-other", run.run_id, "step-a"),
    )
    handler = RecordingHandler()
    reducer = CountingReducer()

    with pytest.raises(PlanStepExecutionRequestMismatchError):
        start_coordinator(handler, reducer=reducer).start(plan, run, binding, other)
    assert reducer.calls == []
    assert handler.calls == []


def test_stale_at_boundary_prevents_activation_and_invocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import iris.plan_step_execution_start.coordinator as module

    plan, run, binding, execution = valid_inputs()
    handler = RecordingHandler()
    reducer = CountingReducer()
    calls = 0
    canonical = module.validate_plan_step_execution_binding_current

    def current_then_stale(
        checked_plan: Plan,
        checked_run: PlanRun,
        checked_binding: PlanStepExecutionBinding,
    ) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise StalePlanStepExecutionBindingError("stale at boundary")
        canonical(checked_plan, checked_run, checked_binding)

    monkeypatch.setattr(
        module,
        "validate_plan_step_execution_binding_current",
        current_then_stale,
    )
    with pytest.raises(StalePlanStepExecutionBindingError, match="boundary"):
        start_coordinator(handler, reducer=reducer).start(plan, run, binding, execution)
    assert calls == 2
    assert reducer.calls == []
    assert handler.calls == []


def test_reducer_failure_prevents_handler_invocation() -> None:
    plan, run, binding, execution = valid_inputs()
    handler = RecordingHandler()
    reducer = CountingReducer(InvalidStepTransitionError("activation refused"))

    with pytest.raises(InvalidStepTransitionError, match="activation refused"):
        start_coordinator(handler, reducer=reducer).start(plan, run, binding, execution)
    assert len(reducer.calls) == 1
    assert handler.calls == []
    assert run.step_progress[0].state is StepProgressState.NOT_STARTED


@pytest.mark.parametrize(
    "outcome",
    [
        HandlerOutcome(ExecutionStatus.SUCCEEDED),
        HandlerOutcome(
            ExecutionStatus.FAILED,
            failure=ExecutionFailure("handler_failed", "handler failed"),
        ),
        HandlerOutcome(
            ExecutionStatus.REJECTED,
            failure=ExecutionFailure("handler_rejected", "handler rejected"),
        ),
    ],
)
def test_all_invoked_handler_statuses_leave_step_active(
    outcome: HandlerOutcome,
) -> None:
    plan, run, binding, execution = valid_inputs()
    handler = RecordingHandler(outcome=outcome)

    result = start_coordinator(handler).start(plan, run, binding, execution)

    assert result.active_run is not None
    assert result.active_run.step_progress[0].state is StepProgressState.ACTIVE
    assert result.execution_result.status is outcome.status
    assert result.execution_result.handler_reference == handler.handler_reference
    assert len(handler.calls) == 1


def test_handler_exception_preserves_active_run_and_chains_cause() -> None:
    plan, run, binding, execution = valid_inputs()
    defect = RuntimeError("handler exploded")
    handler = RecordingHandler(error=defect)

    with pytest.raises(PlanStepExecutionInvocationError) as captured:
        start_coordinator(handler).start(plan, run, binding, execution)

    error = captured.value
    assert error.active_run.revision == run.revision + 1
    assert error.active_run.step_progress[0].state is StepProgressState.ACTIVE
    assert error.activation_update_id == "activation-update-1"
    assert error.execution_id == execution.execution_id
    assert error.__cause__ is defect
    assert len(handler.calls) == 1


def test_invalid_handler_outcome_preserves_active_run_and_contract_cause() -> None:
    plan, run, binding, execution = valid_inputs()
    handler = RecordingHandler(invalid_outcome=True)

    with pytest.raises(PlanStepExecutionInvocationError) as captured:
        start_coordinator(handler).start(plan, run, binding, execution)

    assert captured.value.active_run.step_progress[0].state is StepProgressState.ACTIVE
    assert isinstance(captured.value.__cause__, ExecutionContractError)
    assert len(handler.calls) == 1


def test_completion_before_start_boundary_preserves_active_run() -> None:
    plan, run, binding, execution = valid_inputs()
    handler = RecordingHandler()
    clock = ClockSequence(
        ATTEMPT_STARTED,
        START_BOUNDARY,
        ATTEMPT_STARTED + timedelta(microseconds=1),
    )

    with pytest.raises(PlanStepExecutionInvocationError) as captured:
        start_coordinator(handler, clock=clock).start(plan, run, binding, execution)

    assert captured.value.active_run.step_progress[0].state is StepProgressState.ACTIVE
    assert isinstance(captured.value.__cause__, ValueError)
    assert len(handler.calls) == 1


@pytest.mark.parametrize(
    "factory",
    [
        lambda: " ",
        lambda: "execution-1",
        lambda: cast(str, 42),
    ],
)
def test_invalid_generated_update_identity_prevents_invocation(
    factory: Callable[[], str],
) -> None:
    plan, run, binding, execution = valid_inputs()
    handler = RecordingHandler()

    with pytest.raises(PlanStepExecutionStartGenerationError):
        start_coordinator(handler, update_id_factory=factory).start(
            plan, run, binding, execution
        )
    assert handler.calls == []


def test_update_identity_factory_failure_is_chained_before_invocation() -> None:
    plan, run, binding, execution = valid_inputs()
    handler = RecordingHandler()
    defect = LookupError("identity service failed")

    def fail() -> str:
        raise defect

    with pytest.raises(PlanStepExecutionStartGenerationError) as captured:
        start_coordinator(handler, update_id_factory=fail).start(
            plan, run, binding, execution
        )
    assert captured.value.__cause__ is defect
    assert handler.calls == []


def test_backwards_start_boundary_fails_before_activation_or_invocation() -> None:
    plan, run, binding, execution = valid_inputs()
    handler = RecordingHandler()
    reducer = CountingReducer()
    clock = ClockSequence(ATTEMPT_STARTED, ATTEMPT_STARTED - timedelta(seconds=1))

    with pytest.raises(ValueError, match="boundary cannot predate"):
        start_coordinator(handler, reducer=reducer, clock=clock).start(
            plan, run, binding, execution
        )
    assert reducer.calls == []
    assert handler.calls == []


def test_generic_execution_without_gate_retains_existing_two_clock_semantics() -> None:
    _, _, _, execution = valid_inputs()
    handler = RecordingHandler()
    result = ExecutionCoordinator(
        (handler,),
        clock=ClockSequence(ATTEMPT_STARTED, COMPLETED),
    ).execute(execution)

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.started_at == ATTEMPT_STARTED
    assert result.completed_at == COMPLETED
    assert len(handler.calls) == 1


def test_result_is_immutable_serializable_and_deterministic() -> None:
    plan, run, binding, execution = valid_inputs()
    first = start_coordinator(RecordingHandler()).start(plan, run, binding, execution)
    second = start_coordinator(RecordingHandler()).start(plan, run, binding, execution)

    assert first == second
    assert first.to_data() == second.to_data()
    json.dumps(first.to_data())
    with pytest.raises(FrozenInstanceError):
        first.execution_id = "changed"  # type: ignore[misc]


def test_result_rejects_contradictory_started_and_nonstarted_shapes() -> None:
    plan, run, binding, execution = valid_inputs()
    started = start_coordinator(RecordingHandler()).start(plan, run, binding, execution)
    unavailable = start_coordinator(None).start(plan, run, binding, execution)
    assert started.active_run is not None

    with pytest.raises(PlanStepExecutionStartInvariantError, match="requires"):
        replace(started, activation_update_id=None)
    with pytest.raises(PlanStepExecutionStartInvariantError, match="cannot contain"):
        replace(unavailable, activation_update_id="impossible")
    with pytest.raises(PlanStepExecutionStartInvariantError, match="unavailability"):
        replace(unavailable, execution_result=started.execution_result)


def test_inputs_remain_unchanged_after_start() -> None:
    plan, run, binding, execution = valid_inputs()
    snapshots = (
        plan.to_data(),
        run.to_data(),
        binding.to_data(),
        execution.to_trace(),
    )

    start_coordinator(RecordingHandler()).start(plan, run, binding, execution)

    assert plan.to_data() == snapshots[0]
    assert run.to_data() == snapshots[1]
    assert binding.to_data() == snapshots[2]
    assert execution.to_trace() == snapshots[3]


def test_coordinator_constructor_requires_canonical_collaborators() -> None:
    runtime = ExecutionCoordinator()
    with pytest.raises(TypeError, match="ExecutionCoordinator"):
        PlanStepExecutionStartCoordinator(cast(ExecutionCoordinator, object()))
    with pytest.raises(TypeError, match="PlanRunReducer"):
        PlanStepExecutionStartCoordinator(
            runtime,
            reducer=cast(PlanRunReducer, object()),
        )
    with pytest.raises(TypeError, match="callable"):
        PlanStepExecutionStartCoordinator(
            runtime,
            update_id_factory=cast(Callable[[], str], "not callable"),
        )


def test_execution_coordinator_rejects_invalid_gate_without_invocation() -> None:
    _, _, _, execution = valid_inputs()
    handler = RecordingHandler()
    runtime = ExecutionCoordinator((handler,), clock=lambda: ATTEMPT_STARTED)

    with pytest.raises(TypeError, match="ExecutionStartGate"):
        runtime.execute(execution, start_gate=cast(ExecutionStartGate, object()))
    assert handler.calls == []
