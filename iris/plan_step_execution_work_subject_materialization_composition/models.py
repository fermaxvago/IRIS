"""Immutable output of post-recording selected-work identity materialization."""

from dataclasses import dataclass

from iris.plan_control import ControlDecisionKind
from iris.plan_step_execution_handling_preparation_composition import (
    PlanStepExecutionHandlingPreparationCompositionResult,
)
from iris.plan_step_execution_work_subject_materialization_composition.errors import (
    PlanStepExecutionWorkSubjectMaterializationCompositionInvariantError,
)
from iris.work_identity import PlanStepWorkReference, WorkSubject, WorkSubjectKind


@dataclass(frozen=True, slots=True)
class PlanStepExecutionWorkSubjectMaterializationCompositionResult(
    PlanStepExecutionHandlingPreparationCompositionResult
):
    """Preserve WP043 artifacts and append the optional exact WP015 subject."""

    post_recording_work_subject: WorkSubject | None

    def __post_init__(self) -> None:
        PlanStepExecutionHandlingPreparationCompositionResult.__post_init__(self)
        subject = self.post_recording_work_subject
        if subject is not None and not isinstance(subject, WorkSubject):
            raise TypeError("post_recording_work_subject must be a WorkSubject or None")

        advancement = self.post_recording_advancement_result
        selected = (
            advancement is not None
            and advancement.control_decision.kind is ControlDecisionKind.STEP_SELECTED
        )
        if selected != (subject is not None):
            raise (
                PlanStepExecutionWorkSubjectMaterializationCompositionInvariantError(
                    "post-recording WorkSubject must exist if and only if fresh "
                    "post-recording control selected a step"
                )
            )
        if subject is None:
            return
        if subject is self.work_subject:
            raise (
                PlanStepExecutionWorkSubjectMaterializationCompositionInvariantError(
                    "inherited and post-recording WorkSubjects must remain distinct "
                    "artifacts"
                )
            )

        assert advancement is not None
        control = advancement.control_decision
        reference = subject.reference
        if (
            subject.kind is not WorkSubjectKind.PLAN_STEP
            or not isinstance(reference, PlanStepWorkReference)
            or reference.plan_id != advancement.updated_run.plan_id
            or reference.plan_id != control.plan_id
            or reference.run_id != advancement.updated_run.run_id
            or reference.run_id != control.run_id
            or reference.step_id != control.selected_step_id
            or subject.origin is not None
        ):
            raise (
                PlanStepExecutionWorkSubjectMaterializationCompositionInvariantError(
                    "post-recording WorkSubject must identify the exact fresh "
                    "selected PlanStep without origin"
                )
            )

    def to_data(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible representation."""

        data = PlanStepExecutionHandlingPreparationCompositionResult.to_data(self)
        data["post_recording_work_subject"] = (
            None
            if self.post_recording_work_subject is None
            else self.post_recording_work_subject.to_data()
        )
        return data
