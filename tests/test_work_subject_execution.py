"""WorkSubject-scoped execution lineage and side-effect boundaries for WP018."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta

import pytest

from iris.capabilities import CapabilityInput, CapabilityResult
from iris.context import ContextBudget, ContextEngine, ContextSnapshot
from iris.core import Request
from iris.dispatch import CommandDispatcher
from iris.execution import (
    CapabilityExecutionHandler,
    CapabilityExecutionInput,
    ExecutionCoordinator,
    ExecutionFailure,
    ExecutionOutput,
    ExecutionRequest,
    ExecutionStatus,
    HandlerOutcome,
    MemoryExecutionHandler,
    MemoryExecutionInput,
    SystemExecutionHandler,
    SystemExecutionInput,
)
from iris.memory import MemoryQuery
from iris.orchestrator import (
    HandlerAvailability,
    HandlingKind,
    HandlingNeed,
    MemoryOperation,
    OrchestrationInput,
    OrchestrationTarget,
    Orchestrator,
    StaleOrchestrationDecisionError,
    SubjectContextMismatchError,
)
from iris.plan_runs import PlanRunFactory
from iris.planning import Plan, PlanStep
from iris.router import RouteTarget
from iris.work_identity import (
    WorkOrigin,
    WorkSubject,
    work_subject_from_plan_step,
    work_subject_from_request,
)

NOW = datetime(2026, 9, 28, 18, tzinfo=UTC)
DECIDED = NOW + timedelta(seconds=1)
EXECUTED = NOW + timedelta(seconds=2)


def plan_step_subject(
    *,
    plan_id: str = "plan-1",
    run_id: str = "run-1",
    origin: WorkOrigin | None = None,
) -> WorkSubject:
    plan = Plan(
        plan_id,
        "goal-1",
        (),
        (PlanStep("step-1", "Handle work", "Work was handled"),),
    )
    run = PlanRunFactory(
        clock=lambda: NOW,
        run_id_factory=lambda: run_id,
    ).create(plan)
    return work_subject_from_plan_step(plan, run, "step-1", origin=origin)


def context_for(subject: WorkSubject) -> ContextSnapshot:
    return ContextEngine().build(
        subject=subject,
        candidates=(),
        budget=ContextBudget(0),
        created_at=NOW,
    )


def decision_for(
    subject: WorkSubject,
    context: ContextSnapshot,
    need: HandlingNeed,
):
    availability = HandlerAvailability(
        system=need.kind is HandlingKind.SYSTEM,
        memory=need.kind is HandlingKind.MEMORY,
        capability=need.kind is HandlingKind.CAPABILITY,
        intelligence=need.kind is HandlingKind.INTELLIGENCE,
        capability_ids=(
            frozenset({need.capability_id})
            if need.kind is HandlingKind.CAPABILITY and need.capability_id is not None
            else frozenset()
        ),
    )
    orchestration_input = OrchestrationInput(
        subject,
        context,
        (need,),
        availability,
    )
    return Orchestrator(
        clock=lambda: DECIDED,
        id_factory=lambda: "decision-1",
    ).decide(orchestration_input)


def execution_for(
    subject: WorkSubject,
    context: ContextSnapshot,
    need: HandlingNeed,
    execution_input: object,
    *,
    execution_id: str = "execution-1",
) -> ExecutionRequest:
    return ExecutionRequest(
        execution_id=execution_id,
        subject=subject,
        context=context,
        decision=decision_for(subject, context, need),
        created_at=DECIDED,
        execution_input=execution_input,  # type: ignore[arg-type]
    )


def system_need() -> HandlingNeed:
    return HandlingNeed(
        "system-need",
        HandlingKind.SYSTEM,
        system_route=RouteTarget.CLI_HELP,
    )


def capability_need() -> HandlingNeed:
    return HandlingNeed(
        "capability-need",
        HandlingKind.CAPABILITY,
        capability_id="test.echo",
    )


@dataclass
class RecordingCapabilityRuntime:
    calls: list[tuple[str, CapabilityInput]] = field(default_factory=list)

    def execute(
        self,
        capability_id: str,
        capability_input: CapabilityInput,
    ) -> CapabilityResult:
        self.calls.append((capability_id, capability_input))
        return CapabilityResult.succeeded(
            capability_id,
            output={"echo": capability_input.payload.get("value")},
        )


def test_plan_step_system_executes_without_request_or_synthetic_identity() -> None:
    subject = plan_step_subject(origin=WorkOrigin("request", "root-request"))
    context = context_for(subject)
    request = execution_for(subject, context, system_need(), SystemExecutionInput())

    result = ExecutionCoordinator(
        (SystemExecutionHandler(CommandDispatcher()),),
        clock=lambda: EXECUTED,
    ).execute(request)

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.subject_id == subject.subject_id
    assert not hasattr(request.execution_input, "request")
    assert not hasattr(request.execution_input, "subject")
    assert not hasattr(request.execution_input, "system_route")
    assert not hasattr(result, "request_id")
    assert result.output is not None
    assert result.output.to_data()["value"] == {
        "output": "Comandos disponibles: estado, ayuda, salir",
        "exit_requested": False,
    }


def test_request_subject_uses_the_same_neutral_system_execution_path() -> None:
    incoming = Request("ayuda", "cli", request_id="request-1")
    subject = work_subject_from_request(incoming)
    context = context_for(subject)
    invocation = CapabilityInput(
        payload={"content": incoming.content},
        metadata={"source": incoming.source},
    )
    request = execution_for(
        subject,
        context,
        system_need(),
        SystemExecutionInput(invocation),
    )

    result = ExecutionCoordinator(
        (SystemExecutionHandler(CommandDispatcher()),),
        clock=lambda: EXECUTED,
    ).execute(request)

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.subject_id == subject.subject_id
    assert request.decision.request_id == incoming.request_id


def test_plan_step_capability_execution_uses_generic_subject_lineage() -> None:
    subject = plan_step_subject()
    context = context_for(subject)
    runtime = RecordingCapabilityRuntime()
    request = execution_for(
        subject,
        context,
        capability_need(),
        CapabilityExecutionInput(CapabilityInput(payload={"value": "hello"})),
    )

    result = ExecutionCoordinator(
        (CapabilityExecutionHandler(runtime),),
        clock=lambda: EXECUTED,
    ).execute(request)

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.subject_id == subject.subject_id
    assert runtime.calls[0][0] == "test.echo"
    assert len(runtime.calls) == 1


@dataclass
class RecordingMemoryService:
    queries: list[MemoryQuery] = field(default_factory=list)

    def query(self, query: MemoryQuery) -> tuple[object, ...]:
        self.queries.append(query)
        return ()

    def store(self, item: object) -> object:
        return item

    def get(self, memory_id: str, *, include_history: bool = False) -> None:
        return None

    def forget(self, memory_id: str) -> object:
        return {"id": memory_id}

    def supersede(self, old_id: str, item: object) -> object:
        return item


def test_plan_step_memory_execution_is_not_system_specific() -> None:
    subject = plan_step_subject()
    context = context_for(subject)
    need = HandlingNeed(
        "memory-need",
        HandlingKind.MEMORY,
        memory_operation=MemoryOperation.QUERY,
    )
    service = RecordingMemoryService()
    request = execution_for(
        subject,
        context,
        need,
        MemoryExecutionInput(query=MemoryQuery()),
    )

    result = ExecutionCoordinator(
        (MemoryExecutionHandler(service),),  # type: ignore[arg-type]
        clock=lambda: EXECUTED,
    ).execute(request)

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.subject_id == subject.subject_id
    assert len(service.queries) == 1


def test_stale_context_is_rejected_before_any_handler_invocation() -> None:
    subject = plan_step_subject()
    first_context = context_for(subject)
    second_context = context_for(subject)
    decision = decision_for(subject, first_context, capability_need())
    handler = ForgingHandler()

    with pytest.raises(StaleOrchestrationDecisionError, match="ContextSnapshot"):
        ExecutionRequest(
            "execution-1",
            subject,
            second_context,
            decision,
            DECIDED,
            CapabilityExecutionInput(),
        )

    assert handler.calls == []


def test_wrong_subject_is_rejected_before_any_handler_invocation() -> None:
    first = plan_step_subject(plan_id="plan-1", run_id="run-1")
    second = plan_step_subject(plan_id="plan-2", run_id="run-2")
    first_context = context_for(first)
    second_context = context_for(second)
    decision = decision_for(first, first_context, capability_need())

    with pytest.raises(StaleOrchestrationDecisionError, match="WorkSubject"):
        ExecutionRequest(
            "execution-1",
            second,
            second_context,
            decision,
            DECIDED,
            CapabilityExecutionInput(),
        )


def test_subject_context_mismatch_is_rejected_before_decision_validation() -> None:
    first = plan_step_subject(plan_id="plan-1", run_id="run-1")
    second = plan_step_subject(plan_id="plan-2", run_id="run-2")
    first_context = context_for(first)
    decision = decision_for(first, first_context, capability_need())

    with pytest.raises(SubjectContextMismatchError):
        ExecutionRequest(
            "execution-1",
            second,
            first_context,
            decision,
            DECIDED,
            CapabilityExecutionInput(),
        )


def test_origin_knowledge_change_does_not_change_execution_ownership() -> None:
    unknown_origin = plan_step_subject()
    known_origin = plan_step_subject(origin=WorkOrigin("request", "request-1"))
    context = context_for(unknown_origin)
    decision = decision_for(known_origin, context, capability_need())

    request = ExecutionRequest(
        "execution-1",
        unknown_origin,
        context,
        decision,
        DECIDED,
        CapabilityExecutionInput(),
    )

    assert unknown_origin != known_origin
    assert request.subject.subject_id == decision.subject_id


def test_root_request_cannot_spoof_plan_step_execution_ownership() -> None:
    root = Request("start", "test", request_id="request-1")
    plan_subject = plan_step_subject(origin=WorkOrigin("request", root.request_id))
    plan_context = context_for(plan_subject)
    decision = decision_for(plan_subject, plan_context, capability_need())
    request_subject = work_subject_from_request(root)
    request_context = context_for(request_subject)

    with pytest.raises(StaleOrchestrationDecisionError, match="WorkSubject"):
        ExecutionRequest(
            "execution-1",
            request_subject,
            request_context,
            decision,
            DECIDED,
            CapabilityExecutionInput(),
        )


def test_plan_step_terminal_decision_is_observable_without_handler_call() -> None:
    subject = plan_step_subject()
    context = context_for(subject)
    decision = Orchestrator(
        clock=lambda: DECIDED,
        id_factory=lambda: "decision-1",
    ).decide(OrchestrationInput(subject, context, (), HandlerAvailability()))
    request = ExecutionRequest(
        "execution-1",
        subject,
        context,
        decision,
        DECIDED,
    )
    handler = ForgingHandler()

    result = ExecutionCoordinator((handler,), clock=lambda: EXECUTED).execute(request)

    assert decision.target is OrchestrationTarget.UNSATISFIED
    assert result.status is ExecutionStatus.NOT_EXECUTED
    assert handler.calls == []


@dataclass
class ForgingHandler:
    target = OrchestrationTarget.CAPABILITY
    handler_reference = "test.forging-handler"
    calls: list[ExecutionRequest] = field(default_factory=list)

    def execute(self, request: ExecutionRequest) -> HandlerOutcome:
        self.calls.append(request)
        return HandlerOutcome(
            ExecutionStatus.SUCCEEDED,
            output=ExecutionOutput(value={"subject_id": "forged"}),
            metadata={
                "subject_id": "forged",
                "decision_id": "forged",
                "execution_id": "forged",
                "context_snapshot_id": "forged",
                "target": "memory",
            },
        )


def test_coordinator_constructs_lineage_that_handler_cannot_override() -> None:
    subject = plan_step_subject()
    context = context_for(subject)
    request = execution_for(
        subject,
        context,
        capability_need(),
        CapabilityExecutionInput(),
    )
    handler = ForgingHandler()

    result = ExecutionCoordinator((handler,), clock=lambda: EXECUTED).execute(request)

    assert result.execution_id == request.execution_id
    assert result.subject_id == request.subject.subject_id
    assert result.decision_id == request.decision.decision_id
    assert result.context_snapshot_id == request.context.snapshot_id
    assert result.target == request.decision.target
    assert result.decision_reason == request.decision.reason
    assert len(handler.calls) == 1
    assert result.metadata["subject_id"] == "forged"
    assert result.subject_id != result.metadata["subject_id"]


def test_execution_trace_uses_subject_and_exact_context_canonically() -> None:
    subject = plan_step_subject(origin=WorkOrigin("request", "request-1"))
    context = context_for(subject)
    request = execution_for(
        subject,
        context,
        capability_need(),
        CapabilityExecutionInput(),
    )
    result = ExecutionCoordinator(
        (ForgingHandler(),),
        clock=lambda: EXECUTED,
    ).execute(request)

    request_trace = request.to_trace()
    result_trace = result.to_trace()
    assert request_trace["subject_id"] == subject.subject_id
    assert request_trace["context_snapshot_id"] == context.snapshot_id
    assert result_trace["subject_id"] == subject.subject_id
    assert "request_id" not in request_trace
    assert "request_id" not in result_trace


def test_multiple_execution_instances_are_allowed_without_global_deduplication() -> (
    None
):
    subject = plan_step_subject()
    context = context_for(subject)
    need = capability_need()
    decision = decision_for(subject, context, need)
    first = ExecutionRequest(
        "execution-1",
        subject,
        context,
        decision,
        DECIDED,
        CapabilityExecutionInput(),
    )
    second = replace(first, execution_id="execution-2")

    assert first.decision is second.decision
    assert first.execution_id != second.execution_id


def test_handler_outcome_remains_lineage_free() -> None:
    outcome = HandlerOutcome(
        ExecutionStatus.REJECTED,
        failure=ExecutionFailure("domain_rejection", "operation was refused"),
    )

    for name in (
        "subject_id",
        "context_snapshot_id",
        "decision_id",
        "execution_id",
    ):
        assert not hasattr(outcome, name)
