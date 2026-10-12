"""Immutable WP055 lineage plus the optional exact successor WorkSubject."""

from copy import copy
from dataclasses import dataclass, fields

from iris.plan_control import ControlDecisionKind
from iris.plan_step_execution_handling_preparation_post_recording_composition import (
    PlanStepExecutionHandlingPreparationPostRecordingCompositionResult,
)
from iris.plan_step_execution_work_subject_materialization_post_recording_composition.errors import (
    PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionInvariantError,
)
from iris.work_identity import PlanStepWorkReference, WorkSubject, WorkSubjectKind


def validate_successor_subject(
    subject: WorkSubject,
    *,
    plan_id: str,
    run_id: str,
    step_id: str,
) -> None:
    """Recheck WP015 models on copies, without repairing the returned artifact."""

    invariant = PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionInvariantError
    if not isinstance(subject, WorkSubject):
        raise invariant("WP015 must return a WorkSubject")
    reference = subject.reference
    if not isinstance(reference, PlanStepWorkReference):
        raise invariant("WP015 must return a PlanStepWorkReference")
    try:
        checked_reference = copy(reference)
        PlanStepWorkReference.__post_init__(checked_reference)
        if any(
            type(getattr(reference, field.name))
            is not type(getattr(checked_reference, field.name))
            or getattr(reference, field.name) != getattr(checked_reference, field.name)
            for field in fields(PlanStepWorkReference)
        ):
            raise ValueError("WP015 reference requires normalization")
        checked_subject = copy(subject)
        WorkSubject.__post_init__(checked_subject)
        if (
            type(subject.kind) is not type(checked_subject.kind)
            or subject.kind is not checked_subject.kind
            or subject.reference is not checked_subject.reference
            or subject.origin is not checked_subject.origin
            or type(subject.subject_id) is not type(checked_subject.subject_id)
            or subject.subject_id != checked_subject.subject_id
        ):
            raise ValueError("WP015 subject requires normalization")
    except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
        raise invariant("WP015 returned noncanonical identity artifacts") from exc
    if (
        subject.kind is not WorkSubjectKind.PLAN_STEP
        or reference.plan_id != plan_id
        or reference.run_id != run_id
        or reference.step_id != step_id
        or subject.origin is not None
    ):
        raise invariant("WP015 subject does not identify the exact successor Step")


@dataclass(frozen=True, slots=True)
class PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionResult(
    PlanStepExecutionHandlingPreparationPostRecordingCompositionResult
):
    """Preserve WP055 and append one optional exact WP015 identity."""

    post_recording_execution_work_subject: WorkSubject | None

    def __post_init__(self) -> None:
        PlanStepExecutionHandlingPreparationPostRecordingCompositionResult.__post_init__(
            self
        )
        invariant = PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionInvariantError
        advancement = self.post_recording_execution_advancement_result
        subject = self.post_recording_execution_work_subject
        selected = (
            advancement is not None
            and advancement.control_decision.kind is ControlDecisionKind.STEP_SELECTED
        )
        if selected != (subject is not None):
            raise invariant(
                "successor WorkSubject must exist exactly for STEP_SELECTED"
            )
        if subject is None:
            return
        if subject is self.work_subject or subject is self.post_recording_work_subject:
            raise invariant(
                "successor WorkSubject must be distinct from earlier artifacts"
            )
        assert advancement is not None
        control = advancement.control_decision
        selected_id = control.selected_step_id
        if selected_id is None:
            raise invariant("STEP_SELECTED control must identify one PlanStep")
        validate_successor_subject(
            subject,
            plan_id=advancement.updated_run.plan_id,
            run_id=advancement.updated_run.run_id,
            step_id=selected_id,
        )
        reference = subject.reference
        if not isinstance(reference, PlanStepWorkReference):
            raise invariant("successor WorkSubject must have a PlanStep reference")
        if reference.plan_id != control.plan_id or reference.run_id != control.run_id:
            raise invariant("successor WorkSubject contradicts fresh control")

    def to_data(self) -> dict[str, object]:
        """Append canonical WP015 data to inherited WP055 serialization."""

        data = (
            PlanStepExecutionHandlingPreparationPostRecordingCompositionResult.to_data(
                self
            )
        )
        data["post_recording_execution_work_subject"] = (
            None
            if self.post_recording_execution_work_subject is None
            else self.post_recording_execution_work_subject.to_data()
        )
        return data
