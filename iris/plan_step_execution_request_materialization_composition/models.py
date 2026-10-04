"""Immutable output of bounded post-recording ExecutionRequest materialization."""

from dataclasses import dataclass

from iris.execution import ExecutionRequest
from iris.plan_step_execution_orchestration_composition import (
    PlanStepExecutionOrchestrationCompositionResult,
)
from iris.plan_step_execution_request_materialization_composition.errors import (
    PlanStepExecutionRequestMaterializationCompositionInvariantError,
)


@dataclass(frozen=True, slots=True)
class PlanStepExecutionRequestMaterializationCompositionResult(
    PlanStepExecutionOrchestrationCompositionResult
):
    """Preserve WP046 artifacts and append the optional exact WP018 request."""

    post_recording_execution_request: ExecutionRequest | None

    def __post_init__(self) -> None:
        PlanStepExecutionOrchestrationCompositionResult.__post_init__(self)
        request = self.post_recording_execution_request
        if request is not None and not isinstance(request, ExecutionRequest):
            raise TypeError(
                "post_recording_execution_request must be an ExecutionRequest or None"
            )
        if (self.post_recording_orchestration_decision is None) != (request is None):
            raise PlanStepExecutionRequestMaterializationCompositionInvariantError(
                "post-recording request must exist if and only if the exact Step C "
                "orchestration decision exists"
            )
        if request is None:
            return
        if (
            request.subject is not self.post_recording_work_subject
            or request.context is not self.post_recording_context_snapshot
            or request.decision is not self.post_recording_orchestration_decision
        ):
            raise PlanStepExecutionRequestMaterializationCompositionInvariantError(
                "post-recording request must preserve the exact Step C subject, "
                "ContextSnapshot, and orchestration decision"
            )
        if request is self.execution_request:
            raise PlanStepExecutionRequestMaterializationCompositionInvariantError(
                "Step B and Step C ExecutionRequest artifacts must remain distinct"
            )
        if (
            self.execution_request is not None
            and request.execution_id == self.execution_request.execution_id
        ):
            raise PlanStepExecutionRequestMaterializationCompositionInvariantError(
                "Step C execution identity must not reuse Step B execution identity"
            )

    def to_data(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible representation."""

        data = PlanStepExecutionOrchestrationCompositionResult.to_data(self)
        data["post_recording_execution_request"] = (
            None
            if self.post_recording_execution_request is None
            else self.post_recording_execution_request.to_trace()
        )
        return data
