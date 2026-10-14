"""Immutable WP059 lineage plus one optional exact WP024 binding."""

from __future__ import annotations

from copy import copy
from dataclasses import dataclass, fields

from iris.plan_control import ControlDecisionKind
from iris.plan_handling import StepHandlingPreparationStatus
from iris.plan_step_execution_binding import PlanStepExecutionBinding
from iris.plan_step_execution_request_materialization_post_recording_composition import (
    PlanStepExecutionRequestMaterializationPostRecordingCompositionResult,
)
from iris.plan_step_execution_successor_binding_post_recording_composition.errors import (
    PlanStepExecutionSuccessorBindingPostRecordingCompositionInvariantError,
)


def validate_successor_binding(
    binding: PlanStepExecutionBinding,
    result: PlanStepExecutionRequestMaterializationPostRecordingCompositionResult,
) -> None:
    """Reject malformed or foreign bindings without changing the returned object."""

    invariant = PlanStepExecutionSuccessorBindingPostRecordingCompositionInvariantError
    if not isinstance(binding, PlanStepExecutionBinding):
        raise invariant("WP024 must return a canonical PlanStepExecutionBinding")
    try:
        checked = copy(binding)
        PlanStepExecutionBinding.__post_init__(checked)
        if any(
            type(getattr(binding, field.name)) is not type(getattr(checked, field.name))
            or getattr(binding, field.name) != getattr(checked, field.name)
            for field in fields(PlanStepExecutionBinding)
        ):
            raise ValueError("binding requires canonical normalization")
    except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
        raise invariant("WP024 returned a malformed canonical binding") from exc

    advancement = result.post_recording_execution_advancement_result
    preparation = result.post_recording_execution_handling_preparation
    request = result.post_recording_execution_successor_request
    if advancement is None or preparation is None or request is None:
        raise invariant("successor binding requires exact advancement and request")
    successor = advancement.updated_run
    control = advancement.control_decision
    need = preparation.handling_need
    if (
        control.kind is not ControlDecisionKind.STEP_SELECTED
        or preparation.status is not StepHandlingPreparationStatus.PREPARED
        or need is None
    ):
        raise invariant("successor binding requires selected, prepared work")
    expected = (
        successor.plan_id,
        successor.run_id,
        successor.revision,
        control.selected_step_id,
        request.execution_id,
        request.subject.subject_id,
        request.decision.decision_id,
        request.context.snapshot_id,
        need.need_id,
    )
    actual = (
        binding.plan_id,
        binding.run_id,
        binding.observed_revision,
        binding.step_id,
        binding.execution_id,
        binding.subject_id,
        binding.orchestration_decision_id,
        binding.context_snapshot_id,
        binding.handling_need_id,
    )
    if actual != expected:
        raise invariant("WP024 binding contradicts exact nine-field successor lineage")
    for field in fields(
        PlanStepExecutionRequestMaterializationPostRecordingCompositionResult
    ):
        earlier = getattr(result, field.name)
        if isinstance(earlier, PlanStepExecutionBinding):
            if binding is earlier or binding.execution_id == earlier.execution_id:
                raise invariant("successor binding reuses an earlier binding identity")
            if earlier.observed_revision >= binding.observed_revision:
                raise invariant("successor binding does not follow earlier revision")


@dataclass(frozen=True, slots=True)
class PlanStepExecutionSuccessorBindingPostRecordingCompositionResult(
    PlanStepExecutionRequestMaterializationPostRecordingCompositionResult
):
    """Preserve every WP059 field and append only the optional WP024 witness."""

    post_recording_execution_successor_binding: PlanStepExecutionBinding | None

    def __post_init__(self) -> None:
        PlanStepExecutionRequestMaterializationPostRecordingCompositionResult.__post_init__(
            self
        )
        request = self.post_recording_execution_successor_request
        binding = self.post_recording_execution_successor_binding
        if (request is None) != (binding is None):
            raise PlanStepExecutionSuccessorBindingPostRecordingCompositionInvariantError(
                "successor request and binding must share presence"
            )
        if binding is not None:
            validate_successor_binding(binding, self)

    def to_data(self) -> dict[str, object]:
        """Append the canonical WP024 representation to inherited data."""

        data = PlanStepExecutionRequestMaterializationPostRecordingCompositionResult.to_data(
            self
        )
        binding = self.post_recording_execution_successor_binding
        data["post_recording_execution_successor_binding"] = (
            None if binding is None else binding.to_data()
        )
        return data
