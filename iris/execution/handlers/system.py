"""Adapter from SYSTEM decisions to the existing deterministic dispatcher."""

from iris.capabilities import CapabilityNotFoundError
from iris.dispatch import Dispatcher
from iris.execution.models import (
    ExecutionFailure,
    ExecutionOutput,
    ExecutionRequest,
    ExecutionStatus,
    HandlerOutcome,
    SystemExecutionInput,
)
from iris.orchestrator import OrchestrationTarget
from iris.router import RouteDecision


class SystemExecutionHandler:
    """Execute one already-recognized deterministic system route."""

    target = OrchestrationTarget.SYSTEM
    handler_reference = "system.dispatcher"

    def __init__(self, dispatcher: Dispatcher) -> None:
        self._dispatcher = dispatcher

    def execute(self, request: ExecutionRequest) -> HandlerOutcome:
        requirement = request.decision.requirement
        execution_input = request.execution_input
        if requirement is None or requirement.system_route is None:
            raise ValueError("system decision lacks a deterministic route")
        if not isinstance(execution_input, SystemExecutionInput):
            raise TypeError("system handler requires SystemExecutionInput")
        route = RouteDecision(
            target=requirement.system_route,
            reason="selected by orchestration decision",
            metadata={"decision_id": request.decision.decision_id},
        )
        try:
            result = self._dispatcher.dispatch(execution_input.request, route)
        except CapabilityNotFoundError as exc:
            return HandlerOutcome(
                status=ExecutionStatus.REJECTED,
                failure=ExecutionFailure(
                    code="system_handler_unavailable",
                    message=str(exc),
                    details={"route": route.target.value},
                ),
            )
        return HandlerOutcome(
            status=ExecutionStatus.SUCCEEDED,
            output=ExecutionOutput(
                value={
                    "output": result.output,
                    "exit_requested": result.exit_requested,
                }
            ),
            metadata={"system_route": route.target.value},
        )
