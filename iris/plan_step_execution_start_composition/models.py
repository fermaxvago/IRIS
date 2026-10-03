"""Immutable output of one bounded post-binding execution-start composition."""

from dataclasses import dataclass

from iris.plan_step_execution_binding_composition import (
    PlanStepExecutionBindingCompositionResult,
)
from iris.plan_step_execution_start import PlanStepExecutionStartResult
from iris.plan_step_execution_start_composition.errors import (
    PlanStepExecutionStartCompositionInvariantError,
)


@dataclass(frozen=True, slots=True)
class PlanStepExecutionStartCompositionResult(
    PlanStepExecutionBindingCompositionResult
):
    """Preserve WP036 artifacts and append the optional exact WP025 result."""

    execution_start_result: PlanStepExecutionStartResult | None

    def __post_init__(self) -> None:
        PlanStepExecutionBindingCompositionResult.__post_init__(self)
        if self.execution_start_result is not None and not isinstance(
            self.execution_start_result, PlanStepExecutionStartResult
        ):
            raise TypeError(
                "execution_start_result must be a PlanStepExecutionStartResult or None"
            )
        if (self.execution_binding is None) != (self.execution_start_result is None):
            raise PlanStepExecutionStartCompositionInvariantError(
                "execution start result must exist if and only if binding exists"
            )
        start = self.execution_start_result
        binding = self.execution_binding
        request = self.execution_request
        if start is None or binding is None or request is None:
            return
        if (
            start.plan_id != binding.plan_id
            or start.run_id != binding.run_id
            or start.source_revision != binding.observed_revision
            or start.step_id != binding.step_id
            or start.execution_id != binding.execution_id
            or start.execution_id != request.execution_id
        ):
            raise PlanStepExecutionStartCompositionInvariantError(
                "execution start result must identify the exact WP036 binding"
            )

    def to_data(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible representation."""

        data = PlanStepExecutionBindingCompositionResult.to_data(self)
        data["execution_start_result"] = (
            None
            if self.execution_start_result is None
            else self.execution_start_result.to_data()
        )
        return data
