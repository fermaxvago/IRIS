"""Minimal execution boundary for decisions made by the IRIS Router."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from iris.core.request import Request
from iris.core.system import SystemInfo, format_system_info, get_system_info
from iris.router.models import RouteDecision, RouteTarget

SystemInfoProvider = Callable[[], SystemInfo]
SystemInfoFormatter = Callable[[SystemInfo], str]


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
    """Execute the small set of routed commands supported by the current CLI."""

    def __init__(
        self,
        *,
        system_info_provider: SystemInfoProvider = get_system_info,
        system_info_formatter: SystemInfoFormatter = format_system_info,
    ) -> None:
        self._system_info_provider = system_info_provider
        self._system_info_formatter = system_info_formatter

    def dispatch(
        self,
        _request: Request,
        decision: RouteDecision,
    ) -> DispatchResult:
        """Handle a prior routing decision outside the Router."""

        if decision.target is RouteTarget.SYSTEM_STATUS:
            info = self._system_info_provider()
            return DispatchResult(self._system_info_formatter(info))

        if decision.target is RouteTarget.CLI_HELP:
            return DispatchResult("Comandos disponibles: estado, ayuda, salir")

        if decision.target is RouteTarget.CLI_EXIT:
            return DispatchResult("IRIS apagándose.", exit_requested=True)

        if decision.target is RouteTarget.UNKNOWN:
            return DispatchResult(
                "Todavía no sé hacer eso, pero lo voy a aprender."
            )

        raise ValueError(f"unsupported route target: {decision.target}")
