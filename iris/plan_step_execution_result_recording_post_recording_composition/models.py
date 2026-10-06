"""Immutable WP049 lineage plus the exact optional Step C recording."""

from copy import copy
from dataclasses import dataclass, fields

from iris.plan_runs import PlanObservation, PlanRun
from iris.plan_step_execution_result_recording import (
    PlanStepExecutionResultRecordingResult,
)
from iris.plan_step_execution_result_recording_post_recording_composition.errors import (
    PlanStepExecutionResultRecordingPostRecordingCompositionInvariantError,
)
from iris.plan_step_execution_start import PlanStepExecutionStartResult
from iris.plan_step_execution_start_post_recording_composition import (
    PlanStepExecutionStartPostRecordingCompositionResult,
)
from iris.plan_step_execution_start_post_recording_composition.models import (
    _validate_run_shape,
)


def _validate_recording(
    base: PlanRun,
    start: PlanStepExecutionStartResult,
    recording: PlanStepExecutionResultRecordingResult,
) -> None:
    """Check WP026 postconditions, never adapt, reduce, or interpret evidence."""

    invariant = PlanStepExecutionResultRecordingPostRecordingCompositionInvariantError
    if not isinstance(recording, PlanStepExecutionResultRecordingResult):
        raise invariant("WP026 must return a PlanStepExecutionResultRecordingResult")
    try:
        PlanStepExecutionResultRecordingResult.__post_init__(recording)
        observation = recording.observation
        checked = copy(observation)
        PlanObservation.__post_init__(checked)
        if any(
            type(getattr(observation, item.name))
            is not type(getattr(checked, item.name))
            or getattr(observation, item.name) != getattr(checked, item.name)
            for item in fields(PlanObservation)
        ):
            raise invariant("WP026 observation would require normalization/repair")
        recorded = recording.recorded_run
        _validate_run_shape(recorded)
        if (
            recording.plan_id != start.plan_id
            or recording.plan_id != base.plan_id
            or recording.run_id != start.run_id
            or recording.run_id != base.run_id
            or recording.step_id != start.step_id
            or recording.execution_id != start.execution_id
            or recording.recorded_from_revision != base.revision
            or recorded.plan_id != base.plan_id
            or recorded.run_id != base.run_id
            or recorded.goal_id != base.goal_id
            or recorded.revision != base.revision + 1
            or recorded.created_at != base.created_at
            or recorded.updated_at != max(base.updated_at, observation.observed_at)
            or observation.observed_at < start.execution_result.completed_at
        ):
            raise invariant("WP026 recording contradicts exact Step C recording base")
        if (
            recorded.step_progress != base.step_progress
            or recorded.blockers != base.blockers
        ):
            raise invariant("WP026 recording changed progress or blockers")
        # WP050-C1: canonical ordering is by identity, not recording chronology.
        if (
            len(recorded.observations) != len(base.observations) + 1
            or not any(item is observation for item in recorded.observations)
            or any(
                not any(item is prior for item in recorded.observations)
                for prior in base.observations
            )
            or any(
                prior.observation_id == observation.observation_id
                for prior in base.observations
            )
        ):
            raise invariant(
                "WP026 must preserve every exact prior observation and add only its exact new observation"
            )
        # Compare raw facts only. This is not an assessment or a status policy.
        facts = start.execution_result.to_trace()
        expected_data = {
            key: value
            for key, value in facts.items()
            if key not in {"execution_id", "subject_id"}
        }
        if observation.to_data()["data"] != expected_data:
            raise invariant("WP026 observation changed the canonical execution facts")
    except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
        raise invariant("WP026 returned contradictory recording lineage") from exc


@dataclass(frozen=True, slots=True)
class PlanStepExecutionResultRecordingPostRecordingCompositionResult(
    PlanStepExecutionStartPostRecordingCompositionResult
):
    """Preserve WP049 and record the fact, without assessing or continuing it."""

    post_recording_execution_recording_result: (
        PlanStepExecutionResultRecordingResult | None
    )

    def __post_init__(self) -> None:
        PlanStepExecutionStartPostRecordingCompositionResult.__post_init__(self)
        invariant = (
            PlanStepExecutionResultRecordingPostRecordingCompositionInvariantError
        )
        start = self.post_recording_execution_start_result
        recording = self.post_recording_execution_recording_result
        if (start is None) != (recording is None):
            raise invariant("Step C start and recording must exist together")
        if start is None:
            return
        assert recording is not None
        advancement = self.post_recording_advancement_result
        assert advancement is not None
        base = (
            start.active_run
            if start.active_run is not None
            else advancement.updated_run
        )
        _validate_recording(base, start, recording)
        if recording is self.execution_recording_result:
            raise invariant(
                "Step B and Step C recording artifacts must remain distinct"
            )

    def to_data(self) -> dict[str, object]:
        """Append the exact WP026 representation to inherited WP049 data."""

        data = PlanStepExecutionStartPostRecordingCompositionResult.to_data(self)
        data["post_recording_execution_recording_result"] = (
            None
            if self.post_recording_execution_recording_result is None
            else self.post_recording_execution_recording_result.to_data()
        )
        return data
