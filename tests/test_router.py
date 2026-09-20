from __future__ import annotations

import pytest

from iris.capabilities import (
    CapabilityExecutor,
    CapabilityInput,
    CapabilityResult,
)
from iris.core import Request
from iris.dispatch import CommandDispatcher, Dispatcher
from iris.router import DeterministicRouter, RouteDecision, RouteTarget


@pytest.mark.parametrize(
    ("content", "expected_target"),
    [
        ("estado", RouteTarget.SYSTEM_STATUS),
        (" ESTADO ", RouteTarget.SYSTEM_STATUS),
        ("ayuda", RouteTarget.CLI_HELP),
        ("salir", RouteTarget.CLI_EXIT),
        ("algo nuevo", RouteTarget.UNKNOWN),
        ("", RouteTarget.UNKNOWN),
    ],
)
def test_deterministic_router_selects_expected_target(
    content: str,
    expected_target: RouteTarget,
) -> None:
    request = Request(
        request_id="route-test",
        content=content,
        source="test",
    )

    decision = DeterministicRouter().route(request)

    assert decision.target is expected_target
    assert decision.reason


def test_repeated_routing_produces_the_same_decision() -> None:
    router = DeterministicRouter()
    request = Request(
        request_id="deterministic-test",
        content="estado",
        source="test",
    )

    assert router.route(request) == router.route(request)


def test_router_does_not_execute_system_status(monkeypatch) -> None:
    def unexpected_execution():
        raise AssertionError("routing must not execute system status")

    monkeypatch.setattr("iris.core.system.get_system_info", unexpected_execution)
    request = Request(content="estado", source="test")

    decision = DeterministicRouter().route(request)

    assert decision.target is RouteTarget.SYSTEM_STATUS


def test_dispatch_occurs_only_after_routing_decision() -> None:
    runtime_calls: list[tuple[str, CapabilityInput]] = []

    class RecordingRuntime:
        def execute(
            self,
            capability_id: str,
            capability_input: CapabilityInput,
        ) -> CapabilityResult:
            runtime_calls.append((capability_id, capability_input))
            return CapabilityResult.succeeded(
                capability_id,
                output="formatted status",
            )

    router = DeterministicRouter()
    dispatcher = CommandDispatcher(
        capability_runtime=RecordingRuntime(),
    )
    request = Request(content="estado", source="test")

    decision = router.route(request)

    assert runtime_calls == []
    result = dispatcher.dispatch(request, decision)
    assert len(runtime_calls) == 1
    capability_id, capability_input = runtime_calls[0]
    assert capability_id == "system.status"
    assert capability_input.metadata["source"] == "test"
    assert result.output == "formatted status"
    assert isinstance(dispatcher, Dispatcher)
    assert isinstance(RecordingRuntime(), CapabilityExecutor)


def test_dispatcher_exposes_expected_capability_failure() -> None:
    class FailingRuntime:
        def execute(
            self,
            capability_id: str,
            capability_input: CapabilityInput,
        ) -> CapabilityResult:
            return CapabilityResult.failed(
                capability_id,
                diagnostic="system status temporarily unavailable",
            )

    request = Request(content="estado", source="test")
    decision = DeterministicRouter().route(request)

    result = CommandDispatcher(capability_runtime=FailingRuntime()).dispatch(
        request, decision
    )

    assert result.output == "system status temporarily unavailable"


def test_route_decision_is_explicit_and_read_only() -> None:
    metadata = {"rule": "status"}
    decision = RouteDecision(
        target=RouteTarget.SYSTEM_STATUS,
        reason="matched status",
        metadata=metadata,
    )

    metadata["rule"] = "changed"

    assert decision.target is RouteTarget.SYSTEM_STATUS
    assert decision.reason == "matched status"
    assert decision.metadata["rule"] == "status"
    with pytest.raises(TypeError):
        decision.metadata["new"] = "value"  # type: ignore[index]


def test_route_decision_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        RouteDecision(target=RouteTarget.UNKNOWN, reason=" ")

    with pytest.raises(TypeError):
        RouteDecision(target="system.status", reason="matched")  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        RouteDecision(
            target=RouteTarget.UNKNOWN,
            reason="unknown",
            metadata={1: "value"},  # type: ignore[dict-item]
        )
