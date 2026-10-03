"""Immutable output of one bounded post-request binding composition."""

from dataclasses import dataclass

from iris.plan_step_execution_binding import PlanStepExecutionBinding
from iris.plan_step_execution_binding_composition.errors import (
    PlanStepExecutionBindingCompositionInvariantError,
)
from iris.plan_step_execution_request_materialization import (
    PlanStepExecutionRequestMaterializationResult,
)


@dataclass(frozen=True, slots=True)
class PlanStepExecutionBindingCompositionResult(
    PlanStepExecutionRequestMaterializationResult
):
    """Preserve WP035 artifacts and append the optional exact WP024 binding."""

    execution_binding: PlanStepExecutionBinding | None

    def __post_init__(self) -> None:
        PlanStepExecutionRequestMaterializationResult.__post_init__(self)
        if self.execution_binding is not None and not isinstance(
            self.execution_binding, PlanStepExecutionBinding
        ):
            raise TypeError(
                "execution_binding must be a PlanStepExecutionBinding or None"
            )
        if (self.execution_request is None) != (self.execution_binding is None):
            raise PlanStepExecutionBindingCompositionInvariantError(
                "execution binding must exist if and only if execution request exists"
            )
        binding = self.execution_binding
        request = self.execution_request
        if binding is None or request is None:
            return
        if (
            binding.execution_id != request.execution_id
            or binding.subject_id != request.subject.subject_id
            or binding.context_snapshot_id != request.context.snapshot_id
            or binding.orchestration_decision_id != request.decision.decision_id
        ):
            raise PlanStepExecutionBindingCompositionInvariantError(
                "execution binding must identify the exact WP035 request lineage"
            )

    def to_data(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible representation."""

        data = PlanStepExecutionRequestMaterializationResult.to_data(self)
        data["execution_binding"] = (
            None if self.execution_binding is None else self.execution_binding.to_data()
        )
        return data
