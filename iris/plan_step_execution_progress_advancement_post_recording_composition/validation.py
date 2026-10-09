"""Non-repairing checks for the one delegated WP023 successor artifact."""

from copy import copy
from dataclasses import fields, is_dataclass

from iris.plan_control import ControlDecision
from iris.plan_control.models import ControlProvenance
from iris.plan_run_advancement import PlanRunProgressAdvanceResult
from iris.plan_runs import (
    PlanBlocker,
    PlanObservation,
    PlanRun,
    RunProvenance,
    StepProgress,
    StepProgressUpdate,
)
from iris.plan_step_execution_progress_advancement_post_recording_composition.errors import (
    PlanStepExecutionProgressAdvancementPostRecordingCompositionInvariantError,
)


def _unchanged_by_validation(original: object, checked: object) -> bool:
    if not is_dataclass(original):
        return False
    return all(
        type(getattr(original, item.name)) is type(getattr(checked, item.name))
        and getattr(original, item.name) == getattr(checked, item.name)
        for item in fields(original)
    )


def _validate_nested(run: PlanRun, control: ControlDecision) -> None:
    """Recheck forged nested models without changing returned artifacts."""

    for progress in run.step_progress:
        checked_progress = copy(progress)
        StepProgress.__post_init__(checked_progress)
        if not _unchanged_by_validation(progress, checked_progress):
            raise ValueError("StepProgress requires normalization")
    for observation in run.observations:
        checked_observation = copy(observation)
        PlanObservation.__post_init__(checked_observation)
        if not _unchanged_by_validation(observation, checked_observation):
            raise ValueError("PlanObservation requires normalization")
    for blocker in run.blockers:
        checked_blocker = copy(blocker)
        PlanBlocker.__post_init__(checked_blocker)
        if not _unchanged_by_validation(blocker, checked_blocker):
            raise ValueError("PlanBlocker requires normalization")
        checked_provenance = copy(blocker.provenance)
        RunProvenance.__post_init__(checked_provenance)
        if not _unchanged_by_validation(blocker.provenance, checked_provenance):
            raise ValueError("blocker provenance requires normalization")
    checked_control_provenance = copy(control.provenance)
    ControlProvenance.__post_init__(checked_control_provenance)
    if not _unchanged_by_validation(control.provenance, checked_control_provenance):
        raise ValueError("control provenance requires normalization")


def validate_advancement(
    plan_id: str,
    source_run: PlanRun,
    update: StepProgressUpdate,
    advancement: PlanRunProgressAdvanceResult,
) -> None:
    """Prove the returned successor reflects only the exact Step C update."""

    invariant = (
        PlanStepExecutionProgressAdvancementPostRecordingCompositionInvariantError
    )
    if not isinstance(advancement, PlanRunProgressAdvanceResult):
        raise invariant("WP023 must return a PlanRunProgressAdvanceResult")
    try:
        PlanRunProgressAdvanceResult.__post_init__(advancement)
        successor = advancement.updated_run
        control = advancement.control_decision
        if not isinstance(successor, PlanRun) or not isinstance(
            control, ControlDecision
        ):
            raise TypeError("WP023 returned noncanonical nested artifacts")
        checked_run = copy(successor)
        PlanRun.__post_init__(checked_run)
        if not _unchanged_by_validation(successor, checked_run):
            raise ValueError("successor Run requires normalization")
        checked_control = copy(control)
        ControlDecision.__post_init__(checked_control)
        if not _unchanged_by_validation(control, checked_control):
            raise ValueError("control decision requires normalization")
        _validate_nested(successor, control)
    except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
        raise invariant("WP023 returned noncanonical advancement artifacts") from exc

    if (
        advancement.source_update_id != update.update_id
        or advancement.source_revision != update.expected_revision
        or advancement.source_revision != source_run.revision
        or successor.plan_id != plan_id
        or successor.plan_id != source_run.plan_id
        or successor.run_id != source_run.run_id
        or successor.run_id != update.run_id
        or successor.goal_id != source_run.goal_id
        or successor.revision != source_run.revision + 1
        or successor.created_at != source_run.created_at
        or successor.updated_at != update.updated_at
        or control.plan_id != plan_id
        or control.run_id != successor.run_id
        or control.observed_revision != successor.revision
    ):
        raise invariant("WP023 advancement contradicts the Step C update lineage")

    if (
        len(successor.observations) != len(source_run.observations)
        or any(
            after is not before
            for before, after in zip(
                source_run.observations, successor.observations, strict=True
            )
        )
        or len(successor.blockers) != len(source_run.blockers)
        or any(
            after is not before
            for before, after in zip(
                source_run.blockers, successor.blockers, strict=True
            )
        )
    ):
        raise invariant("WP023 changed observations or blockers")
    source_progress = {item.step_id: item for item in source_run.step_progress}
    successor_progress = {item.step_id: item for item in successor.step_progress}
    if source_progress.keys() != successor_progress.keys():
        raise invariant("WP023 changed the StepProgress identity set")
    target = successor_progress.get(update.step_id)
    if (
        target is None
        or target.state is not update.new_state
        or target.changed_at != update.updated_at
        or target.evidence_ids != update.evidence_ids
    ):
        raise invariant("WP023 target StepProgress contradicts the update")
    if any(
        successor_progress[step_id] is not progress
        for step_id, progress in source_progress.items()
        if step_id != update.step_id
    ):
        raise invariant("WP023 changed unrelated StepProgress")
