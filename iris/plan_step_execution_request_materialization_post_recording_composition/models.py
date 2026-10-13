"""Immutable WP058 lineage with at most one operational successor request."""

from __future__ import annotations

from copy import copy
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from typing import Protocol, cast

from iris.execution import ExecutionRequest
from iris.orchestrator import OrchestrationTarget
from iris.plan_step_execution_orchestration_post_recording_composition import (
    PlanStepExecutionOrchestrationPostRecordingCompositionResult,
)
from iris.plan_step_execution_request_materialization_post_recording_composition.errors import (
    PlanStepExecutionRequestMaterializationPostRecordingCompositionInvariantError,
)

_OPERATIONAL_TARGETS = frozenset(
    {
        OrchestrationTarget.SYSTEM,
        OrchestrationTarget.MEMORY,
        OrchestrationTarget.CAPABILITY,
        OrchestrationTarget.INTELLIGENCE,
    }
)


class _PostInit(Protocol):
    def __post_init__(self) -> None: ...


def _revalidate_copy(value: object) -> None:
    """Run canonical model validation on scratch copies, rejecting normalization."""

    if isinstance(value, tuple):
        for item in value:
            _revalidate_copy(item)
        return
    if not is_dataclass(value) or isinstance(value, type):
        return
    checked = copy(value)
    cast(_PostInit, checked).__post_init__()
    for field in fields(value):
        original = getattr(value, field.name)
        canonical = getattr(checked, field.name)
        if (
            type(original) is not type(canonical)
            or original != canonical
            or (
                isinstance(original, datetime)
                and original.isoformat() != canonical.isoformat()
            )
        ):
            raise ValueError(f"{field.name} requires canonical normalization")
        _revalidate_copy(original)


def validate_successor_request(
    request: ExecutionRequest,
    result: PlanStepExecutionOrchestrationPostRecordingCompositionResult,
) -> None:
    """Recheck WP018 shape, exact owner identity, and WP059 collision rules."""

    invariant = (
        PlanStepExecutionRequestMaterializationPostRecordingCompositionInvariantError
    )
    if not isinstance(request, ExecutionRequest):
        raise invariant("successor request must be a canonical ExecutionRequest")
    subject = result.post_recording_execution_work_subject
    context = result.post_recording_execution_context_snapshot
    decision = result.post_recording_execution_orchestration_decision
    if (
        request.subject is not subject
        or request.context is not context
        or request.decision is not decision
    ):
        raise invariant("successor request must retain exact WP058 artifacts")
    if decision is None or decision.target not in _OPERATIONAL_TARGETS:
        raise invariant("successor request requires an operational decision")
    try:
        _revalidate_copy(request)
    except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
        raise invariant("successor request is noncanonical") from exc
    inherited_requests = (
        getattr(result, field.name)
        for field in fields(
            PlanStepExecutionOrchestrationPostRecordingCompositionResult
        )
    )
    for inherited in inherited_requests:
        if isinstance(inherited, ExecutionRequest) and (
            request is inherited or request.execution_id == inherited.execution_id
        ):
            raise invariant("successor request reuses an earlier execution identity")
    if request.execution_id in {
        subject.subject_id,
        context.snapshot_id,
        decision.decision_id,
    }:
        raise invariant("successor execution identity collides with its lineage")


@dataclass(frozen=True, slots=True)
class PlanStepExecutionRequestMaterializationPostRecordingCompositionResult(
    PlanStepExecutionOrchestrationPostRecordingCompositionResult
):
    """Preserve WP058 and append only the optional successor WP018 request."""

    post_recording_execution_successor_request: ExecutionRequest | None

    def __post_init__(self) -> None:
        PlanStepExecutionOrchestrationPostRecordingCompositionResult.__post_init__(self)
        decision = self.post_recording_execution_orchestration_decision
        operational = decision is not None and decision.target in _OPERATIONAL_TARGETS
        request = self.post_recording_execution_successor_request
        if operational != (request is not None):
            raise PlanStepExecutionRequestMaterializationPostRecordingCompositionInvariantError(
                "successor request must exist exactly for operational decisions"
            )
        if request is not None:
            validate_successor_request(request, self)

    def to_data(self) -> dict[str, object]:
        """Append only the canonical WP018 trace to inherited serialization."""

        data = PlanStepExecutionOrchestrationPostRecordingCompositionResult.to_data(
            self
        )
        request = self.post_recording_execution_successor_request
        data["post_recording_execution_successor_request"] = (
            None if request is None else request.to_trace()
        )
        return data
