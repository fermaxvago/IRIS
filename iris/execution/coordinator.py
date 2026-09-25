"""Deterministic at-most-once dispatch for an orchestration decision."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from types import MappingProxyType

from iris.execution.contracts import ExecutionHandler
from iris.execution.errors import (
    DuplicateExecutionHandlerError,
    ExecutionContractError,
)
from iris.execution.models import (
    ExecutionFailure,
    ExecutionOutput,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    HandlerOutcome,
)
from iris.memory.models import identifier, utc_time
from iris.orchestrator import OrchestrationTarget

_EXECUTABLE_TARGETS = frozenset(
    {
        OrchestrationTarget.SYSTEM,
        OrchestrationTarget.MEMORY,
        OrchestrationTarget.CAPABILITY,
        OrchestrationTarget.INTELLIGENCE,
    }
)
_TERMINAL_TARGETS = frozenset(
    {OrchestrationTarget.CLARIFY, OrchestrationTarget.UNSATISFIED}
)


class ExecutionCoordinator:
    """Invoke the handler selected by WP009 once, record the result, then stop."""

    def __init__(
        self,
        handlers: Iterable[ExecutionHandler] = (),
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        registered: dict[OrchestrationTarget, ExecutionHandler] = {}
        for handler in handlers:
            target = handler.target
            if not isinstance(target, OrchestrationTarget):
                raise TypeError("handler target must be an OrchestrationTarget")
            if target not in _EXECUTABLE_TARGETS:
                raise ValueError("execution handlers require an executable target")
            if target in registered:
                raise DuplicateExecutionHandlerError(
                    f"execution handler already registered for {target.value}"
                )
            identifier(handler.handler_reference, "handler_reference")
            registered[target] = handler
        self._handlers = MappingProxyType(registered)
        self._clock: Callable[[], datetime] = (
            (lambda: datetime.now(UTC)) if clock is None else clock
        )

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Dispatch exactly one admissible attempt; never retry or fall back."""

        if not isinstance(request, ExecutionRequest):
            raise TypeError("request must be an ExecutionRequest")
        started_at = utc_time(self._clock(), "execution started_at")
        if started_at < request.created_at:
            raise ValueError("execution cannot start before its request")
        target = request.decision.target
        if target in _TERMINAL_TARGETS:
            return self._result(
                request,
                status=ExecutionStatus.NOT_EXECUTED,
                handler_reference=None,
                started_at=started_at,
                completed_at=self._completion_time(started_at),
                metadata={"terminal_reason": request.decision.reason.value},
            )

        handler = self._handlers.get(target)
        if handler is None:
            return self._result(
                request,
                status=ExecutionStatus.REJECTED,
                handler_reference=None,
                started_at=started_at,
                completed_at=self._completion_time(started_at),
                failure=ExecutionFailure(
                    code="handler_unavailable",
                    message=f"no execution handler is registered for {target.value}",
                    details={"target": target.value},
                ),
            )

        outcome = handler.execute(request)
        if not isinstance(outcome, HandlerOutcome):
            raise ExecutionContractError("handler must return HandlerOutcome")
        return self._result(
            request,
            status=outcome.status,
            handler_reference=handler.handler_reference,
            started_at=started_at,
            completed_at=self._completion_time(started_at),
            output=outcome.output,
            failure=outcome.failure,
            metadata=outcome.metadata,
        )

    def _completion_time(self, started_at: datetime) -> datetime:
        completed_at = utc_time(self._clock(), "execution completed_at")
        if completed_at < started_at:
            raise ValueError("execution completion cannot predate its start")
        return completed_at

    @staticmethod
    def _result(
        request: ExecutionRequest,
        *,
        status: ExecutionStatus,
        handler_reference: str | None,
        started_at: datetime,
        completed_at: datetime,
        output: ExecutionOutput | None = None,
        failure: ExecutionFailure | None = None,
        metadata: object | None = None,
    ) -> ExecutionResult:
        if output is not None and not isinstance(output, ExecutionOutput):
            raise ExecutionContractError("coordinator output must be ExecutionOutput")
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict) and not hasattr(metadata, "items"):
            raise ExecutionContractError("coordinator metadata must be a mapping")
        typed_metadata = dict(metadata.items())
        decision = request.decision
        return ExecutionResult(
            execution_id=request.execution_id,
            decision_id=decision.decision_id,
            request_id=decision.request_id,
            context_snapshot_id=decision.context_snapshot_id,
            target=decision.target,
            decision_reason=decision.reason,
            status=status,
            handler_reference=handler_reference,
            started_at=started_at,
            completed_at=completed_at,
            output=output,
            failure=failure,
            metadata=typed_metadata,
        )
