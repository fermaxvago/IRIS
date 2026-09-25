"""Adapter from explicit MEMORY decisions to the existing MemoryService."""

from iris.execution.contracts import MemoryExecutor
from iris.execution.models import (
    ExecutionFailure,
    ExecutionOutput,
    ExecutionRequest,
    ExecutionStatus,
    HandlerOutcome,
    MemoryExecutionInput,
)
from iris.memory import MemoryConflictError, MemoryNotFoundError
from iris.orchestrator import MemoryOperation, OrchestrationTarget


class MemoryExecutionHandler:
    """Invoke only the MemoryService operation named by the decision."""

    target = OrchestrationTarget.MEMORY
    handler_reference = "memory.service"

    def __init__(self, service: MemoryExecutor) -> None:
        self._service = service

    def execute(self, request: ExecutionRequest) -> HandlerOutcome:
        requirement = request.decision.requirement
        execution_input = request.execution_input
        if requirement is None or requirement.memory_operation is None:
            raise ValueError("memory decision lacks an operation")
        if not isinstance(execution_input, MemoryExecutionInput):
            raise TypeError("memory handler requires MemoryExecutionInput")
        operation = requirement.memory_operation
        try:
            value = self._invoke(operation, execution_input)
        except (MemoryNotFoundError, MemoryConflictError) as exc:
            return HandlerOutcome(
                status=ExecutionStatus.REJECTED,
                failure=ExecutionFailure(
                    code="memory_operation_rejected",
                    message=str(exc),
                    details={"operation": operation.value},
                ),
            )
        return HandlerOutcome(
            status=ExecutionStatus.SUCCEEDED,
            output=ExecutionOutput(value=value),
            metadata={"memory_operation": operation.value},
        )

    def _invoke(
        self, operation: MemoryOperation, execution_input: MemoryExecutionInput
    ) -> object:
        if operation is MemoryOperation.RECALL:
            assert execution_input.memory_id is not None
            return self._service.get(execution_input.memory_id)
        if operation is MemoryOperation.QUERY:
            assert execution_input.query is not None
            return self._service.query(execution_input.query)
        if operation is MemoryOperation.STORE:
            assert execution_input.candidate is not None
            return self._service.store(execution_input.candidate)
        if operation is MemoryOperation.FORGET:
            assert execution_input.memory_id is not None
            return self._service.forget(execution_input.memory_id)
        if operation is MemoryOperation.SUPERSEDE:
            assert execution_input.memory_id is not None
            assert execution_input.candidate is not None
            return self._service.supersede(
                execution_input.memory_id, execution_input.candidate
            )
        raise ValueError(f"unsupported memory operation: {operation}")
