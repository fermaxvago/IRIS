"""Immutable WP048 lineage plus one exact optional WP025 start result."""

from copy import copy
from dataclasses import dataclass, fields

from iris.execution import ExecutionRequest, ExecutionResult
from iris.plan_runs import PlanRun, StepProgress, StepProgressState
from iris.plan_step_execution_binding import PlanStepExecutionBinding
from iris.plan_step_execution_binding_post_recording_composition import (
    PlanStepExecutionBindingPostRecordingCompositionResult,
)
from iris.plan_step_execution_start import PlanStepExecutionStartResult
from iris.plan_step_execution_start_post_recording_composition.errors import (
    PlanStepExecutionStartPostRecordingCompositionInvariantError,
)


def _validate_run_shape(run: PlanRun) -> None:
    """Validate canonical shape without modifying or repairing the delegated Run.

    Scratch copies only exercise canonical validation. They are never returned
    or used as call operands; normalization that changes shape is rejected.
    """

    invariant = PlanStepExecutionStartPostRecordingCompositionInvariantError
    if not isinstance(run, PlanRun):
        raise invariant("delegated Run must be canonical")
    checked_run = copy(run)
    PlanRun.__post_init__(checked_run)
    for item in fields(PlanRun):
        before = getattr(run, item.name)
        after = getattr(checked_run, item.name)
        if type(before) is not type(after) or before != after:
            raise invariant("delegated Run would require normalization/repair")
    for progress in run.step_progress:
        checked_progress = copy(progress)
        StepProgress.__post_init__(checked_progress)
        for item in fields(StepProgress):
            before = getattr(progress, item.name)
            after = getattr(checked_progress, item.name)
            if type(before) is not type(after) or before != after:
                raise invariant("delegated progress would require normalization/repair")


def _validate_start_lineage(
    source: PlanRun,
    binding: PlanStepExecutionBinding,
    request: ExecutionRequest,
    start: PlanStepExecutionStartResult,
) -> None:
    """Validate the returned witness, never perform activation or admission."""

    invariant = PlanStepExecutionStartPostRecordingCompositionInvariantError
    if not isinstance(start, PlanStepExecutionStartResult):
        raise invariant("WP025 must return a PlanStepExecutionStartResult")
    try:
        PlanStepExecutionStartResult.__post_init__(start)
        execution = start.execution_result
        ExecutionResult.__post_init__(copy(execution))
    except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
        raise invariant("WP025 returned a malformed canonical start result") from exc
    if (
        start.plan_id != binding.plan_id
        or start.plan_id != source.plan_id
        or start.run_id != binding.run_id
        or start.run_id != source.run_id
        or start.source_revision != binding.observed_revision
        or start.source_revision != source.revision
        or start.step_id != binding.step_id
        or start.execution_id != binding.execution_id
        or start.execution_id != request.execution_id
        or execution.execution_id != request.execution_id
        or execution.subject_id != request.subject.subject_id
        or execution.decision_id != request.decision.decision_id
        or execution.context_snapshot_id != request.context.snapshot_id
        or execution.target is not request.decision.target
        or execution.decision_reason is not request.decision.reason
        or execution.started_at < request.created_at
    ):
        raise invariant("WP025 start/result contradicts the exact Step C lineage")
    active = start.active_run
    if active is None:
        # WP025's model already validates the handler-unavailable return shape.
        return
    try:
        _validate_run_shape(active)
    except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
        raise invariant("WP025 returned a malformed active Run") from exc
    if (
        active.plan_id != source.plan_id
        or active.run_id != source.run_id
        or active.goal_id != source.goal_id
        or active.revision != source.revision + 1
        or active.created_at != source.created_at
        or active.observations != source.observations
        or active.blockers != source.blockers
        or {item.step_id for item in active.step_progress}
        != {item.step_id for item in source.step_progress}
    ):
        raise invariant("WP025 activation changed unrelated Run lineage/content")
    selected = next(
        item for item in active.step_progress if item.step_id == binding.step_id
    )
    if (
        selected.state is not StepProgressState.ACTIVE
        or selected.evidence_ids != ()
        or selected.changed_at != active.updated_at
        or active.updated_at < source.updated_at
        or active.updated_at < execution.started_at
        or active.updated_at > execution.completed_at
    ):
        raise invariant("WP025 selected progress contradicts canonical activation")
    if tuple(
        item for item in active.step_progress if item.step_id != binding.step_id
    ) != tuple(
        item for item in source.step_progress if item.step_id != binding.step_id
    ):
        raise invariant("WP025 activation changed unrelated StepProgress")


@dataclass(frozen=True, slots=True)
class PlanStepExecutionStartPostRecordingCompositionResult(
    PlanStepExecutionBindingPostRecordingCompositionResult
):
    """A start attempt can exist without activation; its result remains inert."""

    post_recording_execution_start_result: PlanStepExecutionStartResult | None

    def __post_init__(self) -> None:
        PlanStepExecutionBindingPostRecordingCompositionResult.__post_init__(self)
        invariant = PlanStepExecutionStartPostRecordingCompositionInvariantError
        start = self.post_recording_execution_start_result
        binding = self.post_recording_execution_binding
        if (binding is None) != (start is None):
            raise invariant("Step C binding and start result must exist together")
        if start is None:
            return
        assert binding is not None
        advancement = self.post_recording_advancement_result
        request = self.post_recording_execution_request
        assert advancement is not None
        assert request is not None
        _validate_start_lineage(advancement.updated_run, binding, request, start)
        if start is self.execution_start_result:
            raise invariant("Step B and Step C start artifacts must remain distinct")

    def to_data(self) -> dict[str, object]:
        """Append the exact canonical WP025 serialization to WP048 data."""

        data = PlanStepExecutionBindingPostRecordingCompositionResult.to_data(self)
        data["post_recording_execution_start_result"] = (
            None
            if self.post_recording_execution_start_result is None
            else self.post_recording_execution_start_result.to_data()
        )
        return data
