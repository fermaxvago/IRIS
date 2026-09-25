"""Adapter from CAPABILITY decisions to the existing CapabilityRuntime."""

from iris.capabilities import (
    CapabilityExecutor,
    CapabilityNotFoundError,
)
from iris.execution.models import (
    CapabilityExecutionInput,
    ExecutionFailure,
    ExecutionOutput,
    ExecutionRequest,
    ExecutionStatus,
    HandlerOutcome,
)
from iris.orchestrator import OrchestrationTarget


class CapabilityExecutionHandler:
    """Invoke one explicit capability ID exactly once."""

    target = OrchestrationTarget.CAPABILITY
    handler_reference = "capability.runtime"

    def __init__(self, runtime: CapabilityExecutor) -> None:
        self._runtime = runtime

    def execute(self, request: ExecutionRequest) -> HandlerOutcome:
        requirement = request.decision.requirement
        execution_input = request.execution_input
        if requirement is None:
            raise ValueError("capability decision lacks a requirement")
        if not isinstance(execution_input, CapabilityExecutionInput):
            raise TypeError("capability handler requires CapabilityExecutionInput")
        capability_id = requirement.capability_id
        if capability_id is None:
            return HandlerOutcome(
                status=ExecutionStatus.REJECTED,
                failure=ExecutionFailure(
                    code="missing_capability_reference",
                    message="capability execution requires an explicit capability ID",
                ),
            )
        try:
            result = self._runtime.execute(capability_id, execution_input.invocation)
        except CapabilityNotFoundError as exc:
            return HandlerOutcome(
                status=ExecutionStatus.REJECTED,
                failure=ExecutionFailure(
                    code="capability_unavailable",
                    message=str(exc),
                    details={"capability_id": capability_id},
                ),
            )
        output = ExecutionOutput(
            value={
                "capability_id": result.capability_id,
                "value": result.output,
            },
            reference=result.capability_id,
        )
        if not result.success:
            if result.diagnostic is None:  # protected by CapabilityResult
                raise ValueError("failed capability result lacks a diagnostic")
            return HandlerOutcome(
                status=ExecutionStatus.FAILED,
                output=output,
                failure=ExecutionFailure(
                    code="capability_operational_failure",
                    message=result.diagnostic,
                    details={"capability_id": result.capability_id},
                ),
                metadata=result.metadata,
            )
        return HandlerOutcome(
            status=ExecutionStatus.SUCCEEDED,
            output=output,
            metadata=result.metadata,
        )
