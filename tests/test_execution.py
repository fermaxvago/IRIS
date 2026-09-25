"""Single-step execution, adapters, failure boundaries, and traceability."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from iris.capabilities import (
    CapabilityDescriptor,
    CapabilityInput,
    CapabilityKind,
    CapabilityRegistry,
    CapabilityResult,
    CapabilityRuntime,
)
from iris.core import Request
from iris.dispatch import DispatchResult
from iris.execution import (
    CapabilityExecutionHandler,
    CapabilityExecutionInput,
    DuplicateExecutionHandlerError,
    ExecutionContractError,
    ExecutionCoordinator,
    ExecutionFailure,
    ExecutionOutput,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    HandlerOutcome,
    IntelligenceExecutionHandler,
    IntelligenceExecutionInput,
    MemoryExecutionHandler,
    MemoryExecutionInput,
    SystemExecutionHandler,
    SystemExecutionInput,
)
from iris.intelligence import (
    IntelligenceNeed,
    IntelligencePreferences,
    IntelligenceRequest,
    IntelligenceRequirements,
    IntelligenceResource,
    IntelligenceResult,
    IntelligenceRouter,
    ModelAffinity,
    ModelCapability,
    ModelDescriptor,
    ModelLocation,
)
from iris.memory import (
    AcquisitionMode,
    EpistemicStatus,
    MemoryCandidate,
    MemoryClass,
    MemoryKind,
    MemoryProvenance,
    MemoryQuery,
    MemoryScope,
    MemoryService,
    Retention,
    ScopeKind,
    SourceType,
    SQLiteMemoryStore,
)
from iris.orchestrator import (
    ContextBlocker,
    ContextBlockerKind,
    HandlingKind,
    HandlingNeed,
    MemoryOperation,
    OrchestrationDecision,
    OrchestrationReason,
    OrchestrationTarget,
)
from iris.router import RouteTarget

NOW = datetime(2026, 9, 25, 18, tzinfo=UTC)
LATER = NOW + timedelta(seconds=1)
GLOBAL = MemoryScope(ScopeKind.GLOBAL)


def need_for(
    target: OrchestrationTarget,
    *,
    capability_id: str | None = "test.echo",
    memory_operation: MemoryOperation = MemoryOperation.QUERY,
) -> HandlingNeed:
    kwargs: dict[str, object] = {"need_id": "need-1"}
    if target is OrchestrationTarget.SYSTEM:
        kwargs.update(kind=HandlingKind.SYSTEM, system_route=RouteTarget.CLI_HELP)
    elif target is OrchestrationTarget.MEMORY:
        kwargs.update(kind=HandlingKind.MEMORY, memory_operation=memory_operation)
    elif target is OrchestrationTarget.CAPABILITY:
        kwargs.update(kind=HandlingKind.CAPABILITY, capability_id=capability_id)
    elif target is OrchestrationTarget.INTELLIGENCE:
        kwargs.update(
            kind=HandlingKind.INTELLIGENCE, intelligence_need=IntelligenceNeed()
        )
    else:
        raise ValueError("terminal targets do not have executable needs")
    return HandlingNeed(**kwargs)  # type: ignore[arg-type]


def decision_for(
    target: OrchestrationTarget,
    *,
    capability_id: str | None = "test.echo",
    memory_operation: MemoryOperation = MemoryOperation.QUERY,
) -> OrchestrationDecision:
    reason = {
        OrchestrationTarget.SYSTEM: OrchestrationReason.DETERMINISTIC_SYSTEM_REQUEST,
        OrchestrationTarget.MEMORY: OrchestrationReason.EXPLICIT_MEMORY_OPERATION,
        OrchestrationTarget.CAPABILITY: OrchestrationReason.EXPLICIT_CAPABILITY_REQUEST,
        OrchestrationTarget.INTELLIGENCE: OrchestrationReason.INTELLIGENCE_REQUIRED,
    }[target]
    requirement = need_for(
        target,
        capability_id=capability_id,
        memory_operation=memory_operation,
    )
    return OrchestrationDecision(
        decision_id="decision-1",
        request_id="request-1",
        context_snapshot_id="context-1",
        target=target,
        reason=reason,
        created_at=NOW,
        need_ids=(requirement.need_id,),
        requirement=requirement,
    )


def terminal_decision(target: OrchestrationTarget) -> OrchestrationDecision:
    if target is OrchestrationTarget.CLARIFY:
        blocker = ContextBlocker(
            kind="task",
            key="active",
            scope=GLOBAL,
            issue=ContextBlockerKind.AMBIGUOUS,
            candidate_ids=("candidate-a", "candidate-b"),
        )
        return OrchestrationDecision(
            decision_id="decision-1",
            request_id="request-1",
            context_snapshot_id="context-1",
            target=target,
            reason=OrchestrationReason.CONTEXT_AMBIGUOUS,
            created_at=NOW,
            need_ids=("need-1",),
            context_references=(blocker,),
        )
    return OrchestrationDecision(
        decision_id="decision-1",
        request_id="request-1",
        context_snapshot_id="context-1",
        target=target,
        reason=OrchestrationReason.COMPOSITE_HANDLING_REQUIRED,
        created_at=NOW,
        need_ids=("need-1", "need-2"),
    )


def input_for(target: OrchestrationTarget) -> object:
    if target is OrchestrationTarget.SYSTEM:
        return SystemExecutionInput(Request("ayuda", "test", request_id="request-1"))
    if target is OrchestrationTarget.MEMORY:
        return MemoryExecutionInput(query=MemoryQuery())
    if target is OrchestrationTarget.CAPABILITY:
        return CapabilityExecutionInput(CapabilityInput(payload={"value": "hi"}))
    if target is OrchestrationTarget.INTELLIGENCE:
        return IntelligenceExecutionInput("explain", (resource(),))
    raise ValueError(target)


def execution_request(
    target: OrchestrationTarget,
    *,
    decision: OrchestrationDecision | None = None,
    execution_input: object | None = None,
) -> ExecutionRequest:
    selected = decision if decision is not None else decision_for(target)
    supplied = input_for(target) if execution_input is None else execution_input
    return ExecutionRequest(
        execution_id="execution-1",
        decision=selected,
        created_at=NOW,
        execution_input=supplied,  # type: ignore[arg-type]
    )


def resource(
    *,
    location: ModelLocation = ModelLocation.LOCAL,
    available: bool = True,
) -> IntelligenceResource:
    return IntelligenceResource(
        ModelDescriptor(
            model_id="model-a",
            provider_id="provider-a",
            location=location,
            capabilities=frozenset({ModelCapability.TEXT_GENERATION}),
            available=available,
        )
    )


def candidate(content: str = "remembered") -> MemoryCandidate:
    return MemoryCandidate(
        memory_class=MemoryClass.SEMANTIC,
        kind=MemoryKind.FACT,
        subject="iris.test",
        content=content,
        provenance=MemoryProvenance(SourceType.USER_STATEMENT, "chat-1", "fer"),
        epistemic=EpistemicStatus.DIRECT,
        acquisition=AcquisitionMode.EXPLICIT,
        scope=GLOBAL,
        retention=Retention.LONG,
        observed_at=NOW,
    )


@dataclass
class RecordingHandler:
    target: OrchestrationTarget
    outcome: HandlerOutcome = field(
        default_factory=lambda: HandlerOutcome(ExecutionStatus.SUCCEEDED)
    )
    handler_reference: str = "test.handler"
    calls: list[ExecutionRequest] = field(default_factory=list)
    defect: Exception | None = None

    def execute(self, request: ExecutionRequest) -> HandlerOutcome:
        self.calls.append(request)
        if self.defect is not None:
            raise self.defect
        return self.outcome


@pytest.mark.parametrize(
    "target",
    [
        OrchestrationTarget.SYSTEM,
        OrchestrationTarget.MEMORY,
        OrchestrationTarget.CAPABILITY,
        OrchestrationTarget.INTELLIGENCE,
    ],
)
def test_coordinator_dispatches_only_selected_handler_once(
    target: OrchestrationTarget,
) -> None:
    handlers = {
        item: RecordingHandler(item)
        for item in (
            OrchestrationTarget.SYSTEM,
            OrchestrationTarget.MEMORY,
            OrchestrationTarget.CAPABILITY,
            OrchestrationTarget.INTELLIGENCE,
        )
    }
    request = execution_request(target)

    result = ExecutionCoordinator(handlers.values(), clock=lambda: LATER).execute(
        request
    )

    assert result.status is ExecutionStatus.SUCCEEDED
    assert handlers[target].calls == [request]
    assert sum(len(handler.calls) for handler in handlers.values()) == 1


@pytest.mark.parametrize(
    "target", [OrchestrationTarget.CLARIFY, OrchestrationTarget.UNSATISFIED]
)
def test_terminal_decisions_never_invoke_handlers(target: OrchestrationTarget) -> None:
    handler = RecordingHandler(OrchestrationTarget.CAPABILITY)
    request = ExecutionRequest(
        execution_id="execution-1",
        decision=terminal_decision(target),
        created_at=NOW,
    )

    result = ExecutionCoordinator((handler,), clock=lambda: LATER).execute(request)

    assert result.status is ExecutionStatus.NOT_EXECUTED
    assert result.handler_reference is None
    assert result.decision_reason is request.decision.reason
    assert handler.calls == []


def test_missing_handler_is_rejected_without_fallback() -> None:
    unrelated = RecordingHandler(OrchestrationTarget.SYSTEM)

    result = ExecutionCoordinator((unrelated,), clock=lambda: LATER).execute(
        execution_request(OrchestrationTarget.CAPABILITY)
    )

    assert result.status is ExecutionStatus.REJECTED
    assert result.failure is not None
    assert result.failure.code == "handler_unavailable"
    assert unrelated.calls == []


def test_success_failure_and_programming_defect_each_invoke_at_most_once() -> None:
    failed = RecordingHandler(
        OrchestrationTarget.CAPABILITY,
        HandlerOutcome(
            ExecutionStatus.FAILED,
            failure=ExecutionFailure("operational_failure", "expected failure"),
        ),
    )
    coordinator = ExecutionCoordinator((failed,), clock=lambda: LATER)
    assert (
        coordinator.execute(execution_request(OrchestrationTarget.CAPABILITY)).status
        is ExecutionStatus.FAILED
    )
    assert len(failed.calls) == 1

    broken = RecordingHandler(
        OrchestrationTarget.CAPABILITY,
        defect=AttributeError("programming defect"),
    )
    with pytest.raises(AttributeError, match="programming defect"):
        ExecutionCoordinator((broken,), clock=lambda: LATER).execute(
            execution_request(OrchestrationTarget.CAPABILITY)
        )
    assert len(broken.calls) == 1


def test_duplicate_and_invalid_handler_contracts_are_rejected() -> None:
    first = RecordingHandler(OrchestrationTarget.CAPABILITY)
    second = RecordingHandler(OrchestrationTarget.CAPABILITY)
    with pytest.raises(DuplicateExecutionHandlerError):
        ExecutionCoordinator((first, second))

    malformed = RecordingHandler(OrchestrationTarget.SYSTEM)
    malformed.handler_reference = " "
    with pytest.raises(ValueError, match="nonblank"):
        ExecutionCoordinator((malformed,))

    class InvalidHandler(RecordingHandler):
        def execute(self, request: ExecutionRequest) -> HandlerOutcome:
            return "invalid"  # type: ignore[return-value]

    with pytest.raises(ExecutionContractError, match="HandlerOutcome"):
        ExecutionCoordinator(
            (InvalidHandler(OrchestrationTarget.CAPABILITY),), clock=lambda: LATER
        ).execute(execution_request(OrchestrationTarget.CAPABILITY))


def test_execution_models_are_immutable_serializable_and_traceable() -> None:
    request = execution_request(OrchestrationTarget.CAPABILITY)
    result = ExecutionCoordinator(
        (RecordingHandler(OrchestrationTarget.CAPABILITY),), clock=lambda: LATER
    ).execute(request)

    trace = result.to_trace()
    request_trace = request.to_trace()

    assert trace["request_id"] == "request-1"
    assert trace["context_snapshot_id"] == "context-1"
    assert trace["decision_id"] == "decision-1"
    assert trace["execution_id"] == "execution-1"
    assert "reasoning" not in trace
    json.dumps(trace)
    json.dumps(request_trace)
    assert request_trace["decision"]["decision_id"] == "decision-1"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        result.status = ExecutionStatus.FAILED  # type: ignore[misc]
    with pytest.raises(TypeError):
        result.metadata["changed"] = True  # type: ignore[index]


def test_time_and_linkage_validation() -> None:
    decision = decision_for(OrchestrationTarget.SYSTEM)
    with pytest.raises(ValueError, match="timezone-aware"):
        ExecutionRequest(
            "execution-1",
            decision,
            datetime(2026, 9, 25),
            SystemExecutionInput(Request("ayuda", "test", request_id="request-1")),
        )
    with pytest.raises(ValueError, match="predate"):
        ExecutionRequest(
            "execution-1",
            decision,
            NOW - timedelta(seconds=1),
            SystemExecutionInput(Request("ayuda", "test", request_id="request-1")),
        )
    with pytest.raises(ValueError, match="does not match"):
        execution_request(
            OrchestrationTarget.SYSTEM,
            execution_input=SystemExecutionInput(
                Request("ayuda", "test", request_id="different")
            ),
        )
    with pytest.raises(ValueError, match="completed_at"):
        ExecutionResult(
            "execution-1",
            "decision-1",
            "request-1",
            "context-1",
            OrchestrationTarget.CAPABILITY,
            OrchestrationReason.EXPLICIT_CAPABILITY_REQUEST,
            ExecutionStatus.SUCCEEDED,
            "test.handler",
            LATER,
            NOW,
        )
    with pytest.raises(ValueError, match="incompatible"):
        ExecutionResult(
            "execution-1",
            "decision-1",
            "request-1",
            "context-1",
            OrchestrationTarget.CAPABILITY,
            OrchestrationReason.INTELLIGENCE_REQUIRED,
            ExecutionStatus.SUCCEEDED,
            "test.handler",
            NOW,
            LATER,
        )


@pytest.mark.parametrize(
    ("operation", "execution_input"),
    [
        (MemoryOperation.RECALL, MemoryExecutionInput(memory_id="memory-1")),
        (MemoryOperation.QUERY, MemoryExecutionInput(query=MemoryQuery())),
        (MemoryOperation.STORE, MemoryExecutionInput(candidate=candidate())),
        (MemoryOperation.FORGET, MemoryExecutionInput(memory_id="memory-1")),
        (
            MemoryOperation.SUPERSEDE,
            MemoryExecutionInput(memory_id="memory-1", candidate=candidate("new")),
        ),
    ],
)
def test_memory_input_accepts_only_exact_operation_operands(
    operation: MemoryOperation, execution_input: MemoryExecutionInput
) -> None:
    request = ExecutionRequest(
        "execution-1",
        decision_for(OrchestrationTarget.MEMORY, memory_operation=operation),
        NOW,
        execution_input,
    )
    assert request.execution_input is execution_input


def test_memory_input_rejects_impossible_operand_combination() -> None:
    with pytest.raises(ValueError, match="requires exactly"):
        ExecutionRequest(
            "execution-1",
            decision_for(
                OrchestrationTarget.MEMORY,
                memory_operation=MemoryOperation.STORE,
            ),
            NOW,
            MemoryExecutionInput(memory_id="unrelated", candidate=candidate()),
        )


@dataclass
class FakeDispatcher:
    calls: list[tuple[Request, object]] = field(default_factory=list)

    def dispatch(self, request: Request, decision: object) -> DispatchResult:
        self.calls.append((request, decision))
        return DispatchResult("help", exit_requested=False)


def test_system_handler_reuses_existing_dispatcher_once() -> None:
    dispatcher = FakeDispatcher()
    handler = SystemExecutionHandler(dispatcher)  # type: ignore[arg-type]

    result = ExecutionCoordinator((handler,), clock=lambda: LATER).execute(
        execution_request(OrchestrationTarget.SYSTEM)
    )

    assert result.status is ExecutionStatus.SUCCEEDED
    assert len(dispatcher.calls) == 1
    assert result.output is not None
    assert result.output.to_data()["value"] == {
        "output": "help",
        "exit_requested": False,
    }


@dataclass
class RecordingTool:
    fail: bool = False
    defect: bool = False
    calls: list[CapabilityInput] = field(default_factory=list)

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor("test.echo", "test tool", CapabilityKind.TOOL)

    def execute(self, invocation: CapabilityInput) -> CapabilityResult:
        self.calls.append(invocation)
        if self.defect:
            raise RuntimeError("programming defect")
        if self.fail:
            return CapabilityResult.failed("test.echo", diagnostic="device unavailable")
        return CapabilityResult.succeeded(
            "test.echo", output={"echo": invocation.payload.get("value")}
        )


@pytest.mark.parametrize("fails", [False, True])
def test_capability_handler_invokes_existing_runtime_once(fails: bool) -> None:
    tool = RecordingTool(fail=fails)
    handler = CapabilityExecutionHandler(CapabilityRuntime(CapabilityRegistry((tool,))))

    result = ExecutionCoordinator((handler,), clock=lambda: LATER).execute(
        execution_request(OrchestrationTarget.CAPABILITY)
    )

    assert len(tool.calls) == 1
    assert result.status is (
        ExecutionStatus.FAILED if fails else ExecutionStatus.SUCCEEDED
    )


def test_capability_missing_reference_or_registration_is_rejected() -> None:
    runtime = CapabilityRuntime(CapabilityRegistry())
    handler = CapabilityExecutionHandler(runtime)
    generic = decision_for(OrchestrationTarget.CAPABILITY, capability_id=None)

    generic_result = ExecutionCoordinator((handler,), clock=lambda: LATER).execute(
        execution_request(OrchestrationTarget.CAPABILITY, decision=generic)
    )
    missing_result = ExecutionCoordinator((handler,), clock=lambda: LATER).execute(
        execution_request(OrchestrationTarget.CAPABILITY)
    )

    assert generic_result.failure is not None
    assert generic_result.failure.code == "missing_capability_reference"
    assert missing_result.failure is not None
    assert missing_result.failure.code == "capability_unavailable"


def test_capability_programming_defect_propagates_without_retry() -> None:
    tool = RecordingTool(defect=True)
    handler = CapabilityExecutionHandler(CapabilityRuntime(CapabilityRegistry((tool,))))
    with pytest.raises(RuntimeError, match="programming defect"):
        ExecutionCoordinator((handler,), clock=lambda: LATER).execute(
            execution_request(OrchestrationTarget.CAPABILITY)
        )
    assert len(tool.calls) == 1


@dataclass
class RecordingIntelligenceRuntime:
    fail: bool = False
    defect: bool = False
    calls: list[tuple[str, IntelligenceRequest]] = field(default_factory=list)

    def execute(
        self, provider_id: str, request: IntelligenceRequest
    ) -> IntelligenceResult:
        self.calls.append((provider_id, request))
        if self.defect:
            raise AttributeError("runtime defect")
        if self.fail:
            return IntelligenceResult.failed(
                request, provider_id=provider_id, diagnostic="inference failed"
            )
        return IntelligenceResult.succeeded(
            request, provider_id=provider_id, output="answer"
        )


@pytest.mark.parametrize("fails", [False, True])
def test_intelligence_handler_routes_then_invokes_runtime_once(fails: bool) -> None:
    runtime = RecordingIntelligenceRuntime(fail=fails)
    handler = IntelligenceExecutionHandler(IntelligenceRouter(), runtime)

    result = ExecutionCoordinator((handler,), clock=lambda: LATER).execute(
        execution_request(OrchestrationTarget.INTELLIGENCE)
    )

    assert len(runtime.calls) == 1
    provider_id, inference = runtime.calls[0]
    assert provider_id == "provider-a"
    assert inference.model_id == "model-a"
    assert inference.request_id == "execution-1"
    assert result.status is (
        ExecutionStatus.FAILED if fails else ExecutionStatus.SUCCEEDED
    )


def test_unsatisfied_intelligence_route_does_not_invoke_runtime_or_fallback() -> None:
    required_local = IntelligenceNeed(
        requirements=IntelligenceRequirements(required_location=ModelLocation.LOCAL)
    )
    need = HandlingNeed(
        "need-1", HandlingKind.INTELLIGENCE, intelligence_need=required_local
    )
    decision = OrchestrationDecision(
        "decision-1",
        "request-1",
        "context-1",
        OrchestrationTarget.INTELLIGENCE,
        OrchestrationReason.INTELLIGENCE_REQUIRED,
        NOW,
        ("need-1",),
        need,
    )
    runtime = RecordingIntelligenceRuntime()
    handler = IntelligenceExecutionHandler(IntelligenceRouter(), runtime)
    request = ExecutionRequest(
        "execution-1",
        decision,
        NOW,
        IntelligenceExecutionInput(
            "explain", (resource(location=ModelLocation.CLOUD),)
        ),
    )

    result = ExecutionCoordinator((handler,), clock=lambda: LATER).execute(request)

    assert result.status is ExecutionStatus.REJECTED
    assert result.failure is not None
    assert result.failure.code == "intelligence_route_unsatisfied"
    assert runtime.calls == []


def test_degraded_intelligence_route_remains_executable() -> None:
    preferred = IntelligenceNeed(
        preferences=IntelligencePreferences(
            preferred_affinities=(ModelAffinity.REASONING,)
        )
    )
    need = HandlingNeed(
        "need-1", HandlingKind.INTELLIGENCE, intelligence_need=preferred
    )
    decision = OrchestrationDecision(
        "decision-1",
        "request-1",
        "context-1",
        OrchestrationTarget.INTELLIGENCE,
        OrchestrationReason.INTELLIGENCE_REQUIRED,
        NOW,
        ("need-1",),
        need,
    )
    runtime = RecordingIntelligenceRuntime()
    request = ExecutionRequest(
        "execution-1",
        decision,
        NOW,
        IntelligenceExecutionInput("explain", (resource(),)),
    )

    result = ExecutionCoordinator(
        (IntelligenceExecutionHandler(IntelligenceRouter(), runtime),),
        clock=lambda: LATER,
    ).execute(request)

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.metadata["route_status"] == "degraded"
    assert len(runtime.calls) == 1


def test_intelligence_programming_defect_propagates_without_reroute() -> None:
    runtime = RecordingIntelligenceRuntime(defect=True)
    handler = IntelligenceExecutionHandler(IntelligenceRouter(), runtime)
    with pytest.raises(AttributeError, match="runtime defect"):
        ExecutionCoordinator((handler,), clock=lambda: LATER).execute(
            execution_request(OrchestrationTarget.INTELLIGENCE)
        )
    assert len(runtime.calls) == 1


def test_memory_handler_uses_only_explicit_operation_with_real_service(
    tmp_path: Path,
) -> None:
    with SQLiteMemoryStore(tmp_path / "memory.sqlite") as store:
        service = MemoryService(store)
        stored = service.store(candidate())
        handler = MemoryExecutionHandler(service)
        decision = decision_for(
            OrchestrationTarget.MEMORY,
            memory_operation=MemoryOperation.RECALL,
        )
        request = ExecutionRequest(
            "execution-1",
            decision,
            NOW,
            MemoryExecutionInput(memory_id=stored.id),
        )

        result = ExecutionCoordinator((handler,), clock=lambda: LATER).execute(request)

        assert result.status is ExecutionStatus.SUCCEEDED
        assert result.output is not None
        output = result.output.to_data()["value"]
        assert isinstance(output, dict)
        assert output["id"] == stored.id
        assert service.query(MemoryQuery()) == (stored,)


@dataclass
class RecordingMemoryService:
    queries: list[MemoryQuery] = field(default_factory=list)
    store_calls: list[MemoryCandidate] = field(default_factory=list)
    defect: bool = False

    def query(self, query: MemoryQuery) -> tuple[object, ...]:
        self.queries.append(query)
        if self.defect:
            raise RuntimeError("memory defect")
        return ()

    def store(self, item: MemoryCandidate) -> object:
        self.store_calls.append(item)
        return item

    def get(self, memory_id: str, *, include_history: bool = False) -> None:
        return None

    def forget(self, memory_id: str) -> object:
        return {"id": memory_id}

    def supersede(self, old_id: str, item: MemoryCandidate) -> object:
        return item


def test_memory_query_does_not_trigger_automatic_store() -> None:
    service = RecordingMemoryService()
    handler = MemoryExecutionHandler(service)  # type: ignore[arg-type]

    result = ExecutionCoordinator((handler,), clock=lambda: LATER).execute(
        execution_request(OrchestrationTarget.MEMORY)
    )

    assert result.status is ExecutionStatus.SUCCEEDED
    assert len(service.queries) == 1
    assert service.store_calls == []


def test_memory_programming_defect_propagates() -> None:
    service = RecordingMemoryService(defect=True)
    handler = MemoryExecutionHandler(service)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="memory defect"):
        ExecutionCoordinator((handler,), clock=lambda: LATER).execute(
            execution_request(OrchestrationTarget.MEMORY)
        )
    assert len(service.queries) == 1


def test_output_and_failure_reject_nonserializable_or_malformed_values() -> None:
    with pytest.raises(TypeError, match="JSON-compatible"):
        ExecutionOutput(value=object())
    with pytest.raises(ValueError, match="lowercase"):
        ExecutionFailure("Bad Code", "failure")
    with pytest.raises(ValueError, match="require failure"):
        HandlerOutcome(ExecutionStatus.FAILED)
    with pytest.raises(TypeError, match="ExecutionStatus"):
        HandlerOutcome("failed")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="execution_id"):
        ExecutionRequest(
            " ",
            decision_for(OrchestrationTarget.CAPABILITY),
            NOW,
            CapabilityExecutionInput(),
        )


def test_memory_domain_rejection_is_structured(tmp_path: Path) -> None:
    with SQLiteMemoryStore(tmp_path / "memory.sqlite") as store:
        handler = MemoryExecutionHandler(MemoryService(store))
        decision = decision_for(
            OrchestrationTarget.MEMORY,
            memory_operation=MemoryOperation.FORGET,
        )
        request = ExecutionRequest(
            "execution-1",
            decision,
            NOW,
            MemoryExecutionInput(memory_id="missing-memory"),
        )

        result = ExecutionCoordinator((handler,), clock=lambda: LATER).execute(request)

        assert result.status is ExecutionStatus.REJECTED
        assert result.failure is not None
        assert result.failure.code == "memory_operation_rejected"
