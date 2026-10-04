"""Immutable output of post-recording selected-work contextualization."""

from dataclasses import dataclass

from iris.context import ContextSnapshot
from iris.plan_step_execution_context_materialization_composition.errors import (
    PlanStepExecutionContextMaterializationCompositionInvariantError,
)
from iris.plan_step_execution_work_subject_materialization_composition import (
    PlanStepExecutionWorkSubjectMaterializationCompositionResult,
)


@dataclass(frozen=True, slots=True)
class PlanStepExecutionContextMaterializationCompositionResult(
    PlanStepExecutionWorkSubjectMaterializationCompositionResult
):
    """Preserve WP044 artifacts and append the optional exact WP016 snapshot."""

    post_recording_context_snapshot: ContextSnapshot | None

    def __post_init__(self) -> None:
        PlanStepExecutionWorkSubjectMaterializationCompositionResult.__post_init__(self)
        snapshot = self.post_recording_context_snapshot
        if snapshot is not None and not isinstance(snapshot, ContextSnapshot):
            raise TypeError(
                "post_recording_context_snapshot must be a ContextSnapshot or None"
            )
        subject = self.post_recording_work_subject
        if (subject is None) != (snapshot is None):
            raise PlanStepExecutionContextMaterializationCompositionInvariantError(
                "post-recording ContextSnapshot must exist if and only if the "
                "post-recording WorkSubject exists"
            )
        if snapshot is None:
            return
        assert subject is not None
        if snapshot is self.context_snapshot:
            raise PlanStepExecutionContextMaterializationCompositionInvariantError(
                "inherited and post-recording ContextSnapshots must remain distinct "
                "artifacts"
            )
        if snapshot.subject is not subject or snapshot.subject_id != subject.subject_id:
            raise PlanStepExecutionContextMaterializationCompositionInvariantError(
                "post-recording ContextSnapshot must preserve the exact WP044 "
                "WorkSubject owner"
            )

    def to_data(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible representation."""

        data = PlanStepExecutionWorkSubjectMaterializationCompositionResult.to_data(
            self
        )
        data["post_recording_context_snapshot"] = (
            None
            if self.post_recording_context_snapshot is None
            else self.post_recording_context_snapshot.to_data()
        )
        return data
