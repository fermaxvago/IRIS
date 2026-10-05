"""Immutable cumulative output of bounded post-recording binding."""

from dataclasses import dataclass

from iris.plan_step_execution_binding import PlanStepExecutionBinding
from iris.plan_step_execution_binding_post_recording_composition.errors import (
    PlanStepExecutionBindingPostRecordingCompositionInvariantError,
)
from iris.plan_step_execution_request_materialization_composition import (
    PlanStepExecutionRequestMaterializationCompositionResult,
)


@dataclass(frozen=True, slots=True)
class PlanStepExecutionBindingPostRecordingCompositionResult(
    PlanStepExecutionRequestMaterializationCompositionResult
):
    """Preserve WP047 and append one optional compact WP024 lineage witness."""

    post_recording_execution_binding: PlanStepExecutionBinding | None

    def __post_init__(self) -> None:
        PlanStepExecutionRequestMaterializationCompositionResult.__post_init__(self)
        invariant = PlanStepExecutionBindingPostRecordingCompositionInvariantError
        binding = self.post_recording_execution_binding
        request = self.post_recording_execution_request
        if binding is not None and not isinstance(binding, PlanStepExecutionBinding):
            raise invariant(
                "post_recording_execution_binding must be canonical or None"
            )
        if (request is None) != (binding is None):
            raise invariant("successful request and binding must exist together")
        if binding is None:
            return
        assert request is not None
        advancement = self.post_recording_advancement_result
        preparation = self.post_recording_handling_preparation
        assert advancement is not None
        assert preparation is not None
        need = preparation.handling_need
        successor = advancement.updated_run
        control = advancement.control_decision
        try:
            PlanStepExecutionBinding.__post_init__(binding)
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise invariant("WP024 binding has a malformed canonical shape") from exc
        if need is None or (
            binding.plan_id != successor.plan_id
            or binding.run_id != successor.run_id
            or binding.observed_revision != successor.revision
            or binding.step_id != control.selected_step_id
            or binding.execution_id != request.execution_id
            or binding.subject_id != request.subject.subject_id
            or binding.context_snapshot_id != request.context.snapshot_id
            or binding.orchestration_decision_id != request.decision.decision_id
            or binding.handling_need_id != need.need_id
        ):
            raise invariant("WP024 binding contradicts exact post-recording lineage")
        if binding is self.execution_binding or (
            self.execution_binding is not None
            and binding.execution_id == self.execution_binding.execution_id
        ):
            raise invariant("Step B and Step C binding attempts must remain distinct")

    def to_data(self) -> dict[str, object]:
        """Append canonical binding data to the unchanged WP047 serialization."""

        data = PlanStepExecutionRequestMaterializationCompositionResult.to_data(self)
        data["post_recording_execution_binding"] = (
            None
            if self.post_recording_execution_binding is None
            else self.post_recording_execution_binding.to_data()
        )
        return data
