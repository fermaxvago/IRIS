"""Immutable WP056 lineage plus one optional exact successor ContextSnapshot."""

from copy import copy
from dataclasses import dataclass, fields

from iris.context import (
    ContextBudget,
    ContextConflict,
    ContextEvidence,
    ContextItem,
    ContextSnapshot,
    ContextUncertainty,
)
from iris.memory.models import MemoryScope
from iris.plan_step_execution_context_materialization_post_recording_composition.errors import (
    PlanStepExecutionContextMaterializationPostRecordingCompositionInvariantError,
)
from iris.plan_step_execution_work_subject_materialization_post_recording_composition import (
    PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionResult,
)
from iris.work_identity import WorkSubject


def _revalidate(value: object, model: type[object]) -> None:
    """Run a canonical model's checks on a copy and detect normalization."""

    invariant = (
        PlanStepExecutionContextMaterializationPostRecordingCompositionInvariantError
    )
    if not isinstance(value, model):
        raise invariant(f"WP016 returned a noncanonical {model.__name__}")
    try:
        checked = copy(value)
        model.__post_init__(checked)  # type: ignore[attr-defined]
        for field in fields(model):  # type: ignore[arg-type]
            original = getattr(value, field.name)
            canonical = getattr(checked, field.name)
            if type(original) is not type(canonical) or original != canonical:
                raise ValueError(f"{model.__name__} requires normalization")
    except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
        raise invariant(f"WP016 returned a noncanonical {model.__name__}") from exc


def validate_successor_snapshot(
    snapshot: ContextSnapshot, subject: WorkSubject
) -> None:
    """Check canonical WP016 structure and exact owner without repairing it."""

    invariant = (
        PlanStepExecutionContextMaterializationPostRecordingCompositionInvariantError
    )
    _revalidate(snapshot, ContextSnapshot)
    _revalidate(snapshot.budget, ContextBudget)
    for item in snapshot.items:
        _revalidate(item, ContextItem)
        _revalidate(item.scope, MemoryScope)
        _revalidate(item.evidence, ContextEvidence)
    for uncertainty in snapshot.uncertainties:
        _revalidate(uncertainty, ContextUncertainty)
        _revalidate(uncertainty.scope, MemoryScope)
    for conflict in snapshot.conflicts:
        _revalidate(conflict, ContextConflict)
        _revalidate(conflict.scope, MemoryScope)
        for evidence in conflict.evidence:
            _revalidate(evidence, ContextEvidence)
    if snapshot.subject is not subject or snapshot.subject_id != subject.subject_id:
        raise invariant("WP016 snapshot must preserve the exact successor WorkSubject")


@dataclass(frozen=True, slots=True)
class PlanStepExecutionContextMaterializationPostRecordingCompositionResult(
    PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionResult
):
    """Preserve WP056 and append only the optional exact WP016 snapshot."""

    post_recording_execution_context_snapshot: ContextSnapshot | None

    def __post_init__(self) -> None:
        PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionResult.__post_init__(
            self
        )
        invariant = PlanStepExecutionContextMaterializationPostRecordingCompositionInvariantError
        subject = self.post_recording_execution_work_subject
        snapshot = self.post_recording_execution_context_snapshot
        if (subject is None) != (snapshot is None):
            raise invariant("successor Context must exist exactly with successor work")
        if snapshot is None:
            return
        assert subject is not None
        if (
            snapshot is self.context_snapshot
            or snapshot is self.post_recording_context_snapshot
        ):
            raise invariant("successor Context must be distinct from earlier snapshots")
        validate_successor_snapshot(snapshot, subject)

    def to_data(self) -> dict[str, object]:
        """Append WP016 serialization without changing inherited keys."""

        data = PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionResult.to_data(
            self
        )
        data["post_recording_execution_context_snapshot"] = (
            None
            if self.post_recording_execution_context_snapshot is None
            else self.post_recording_execution_context_snapshot.to_data()
        )
        return data
