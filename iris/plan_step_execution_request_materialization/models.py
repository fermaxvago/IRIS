"""Immutable output of one bounded post-orchestration request materialization."""

from dataclasses import dataclass

from iris.execution import ExecutionRequest
from iris.plan_step_execution_request_materialization.errors import (
    PlanStepExecutionRequestMaterializationInvariantError,
)
from iris.plan_step_orchestration import PlanStepOrchestrationResult


@dataclass(frozen=True, slots=True)
class PlanStepExecutionRequestMaterializationResult(PlanStepOrchestrationResult):
    """Preserve WP034 artifacts and append the optional exact WP018 request."""

    execution_request: ExecutionRequest | None

    def __post_init__(self) -> None:
        PlanStepOrchestrationResult.__post_init__(self)
        if self.execution_request is not None and not isinstance(
            self.execution_request, ExecutionRequest
        ):
            raise TypeError("execution_request must be an ExecutionRequest or None")
        if (self.orchestration_decision is None) != (self.execution_request is None):
            raise PlanStepExecutionRequestMaterializationInvariantError(
                "execution request must exist if and only if orchestration decision exists"
            )
        request = self.execution_request
        if request is None:
            return
        if (
            request.subject is not self.work_subject
            or request.context is not self.context_snapshot
            or request.decision is not self.orchestration_decision
        ):
            raise PlanStepExecutionRequestMaterializationInvariantError(
                "execution request must preserve the exact WP034 subject, context, "
                "and decision"
            )

    def to_data(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible representation."""

        data = PlanStepOrchestrationResult.to_data(self)
        data["execution_request"] = (
            None
            if self.execution_request is None
            else self.execution_request.to_trace()
        )
        return data
