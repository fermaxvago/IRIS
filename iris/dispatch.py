"""Dispatch routing decisions to interface handling or capability execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from iris.capabilities import (
    CapabilityExecutor,
    CapabilityInput,
    create_default_runtime,
)
from iris.core.request import Request
from iris.router.models import RouteDecision, RouteTarget


@dataclass(frozen=True, slots=True)
class DispatchResult:
    """Observable result returned to an interface after handling a decision."""

    output: str
    exit_requested: bool = False


@runtime_checkable
class Dispatcher(Protocol):
    """Execute an already-made route decision for a request."""

    def dispatch(
        self,
        request: Request,
        decision: RouteDecision,
    ) -> DispatchResult:
        """Handle a decision and return an interface-neutral result."""
        ...


class CommandDispatcher:
    """Coordinate routed commands without implementing capabilities."""

    def __init__(
        self,
        *,
        capability_runtime: CapabilityExecutor | None = None,
    ) -> None:
        self._capability_runtime = capability_runtime or create_default_runtime()

    def dispatch(
        self,
        _request: Request,
        decision: RouteDecision,
    ) -> DispatchResult:
        """Handle a prior routing decision outside the Router."""

        if decision.target is RouteTarget.CLI_HELP:
            return DispatchResult("Comandos disponibles: estado, ayuda, salir")

        if decision.target is RouteTarget.CLI_EXIT:
            return DispatchResult("IRIS apagándose.", exit_requested=True)

        if decision.target is RouteTarget.UNKNOWN:
            return DispatchResult("Todavía no sé hacer eso, pero lo voy a aprender.")

        capability_input = CapabilityInput(
            payload={"content": _request.content},
            metadata={
                "request_id": _request.request_id,
                "source": _request.source,
            },
        )
        capability_result = self._capability_runtime.execute(
            decision.target.value,
            capability_input,
        )

        if not capability_result.success:
            if capability_result.diagnostic is None:
                raise ValueError("failed capability result lacks a diagnostic")
            return DispatchResult(capability_result.diagnostic)
        if not isinstance(capability_result.output, str):
            raise TypeError("CLI capabilities must return a string output")
        return DispatchResult(capability_result.output)
