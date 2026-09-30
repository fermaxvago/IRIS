"""Immutable output of one bounded PlanStep execution-result recording."""

from dataclasses import dataclass

from iris.plan_runs import PlanObservation, PlanRun
from iris.plan_step_execution_result_recording.errors import (
    PlanStepExecutionResultRecordingInvariantError,
)


def _identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise PlanStepExecutionResultRecordingInvariantError(
            f"{name} must be a nonblank identifier"
        )
    return value


@dataclass(frozen=True, slots=True)
class PlanStepExecutionResultRecordingResult:
    """Lineage from one execution fact to one recorded PlanRun revision."""

    plan_id: str
    run_id: str
    recorded_from_revision: int
    step_id: str
    execution_id: str
    observation_id: str
    record_update_id: str
    observation: PlanObservation
    recorded_run: PlanRun

    def __post_init__(self) -> None:
        for value, name in (
            (self.plan_id, "recording result plan_id"),
            (self.run_id, "recording result run_id"),
            (self.step_id, "recording result step_id"),
            (self.execution_id, "recording result execution_id"),
            (self.observation_id, "recording result observation_id"),
            (self.record_update_id, "recording result record_update_id"),
        ):
            _identifier(value, name)
        if self.observation_id == self.execution_id or self.record_update_id in {
            self.plan_id,
            self.run_id,
            self.step_id,
            self.execution_id,
            self.observation_id,
        }:
            raise PlanStepExecutionResultRecordingInvariantError(
                "observation and recording-update identities must be independent"
            )
        if isinstance(self.recorded_from_revision, bool) or not isinstance(
            self.recorded_from_revision, int
        ):
            raise TypeError("recorded_from_revision must be an integer")
        if self.recorded_from_revision < 0:
            raise PlanStepExecutionResultRecordingInvariantError(
                "recorded_from_revision must be nonnegative"
            )
        if not isinstance(self.observation, PlanObservation):
            raise TypeError("observation must be a PlanObservation")
        if not isinstance(self.recorded_run, PlanRun):
            raise TypeError("recorded_run must be a PlanRun")
        if (
            self.recorded_run.plan_id != self.plan_id
            or self.recorded_run.run_id != self.run_id
        ):
            raise PlanStepExecutionResultRecordingInvariantError(
                "recorded Run identity does not match recording lineage"
            )
        if self.recorded_run.revision != self.recorded_from_revision + 1:
            raise PlanStepExecutionResultRecordingInvariantError(
                "recorded Run must advance exactly one revision"
            )
        if (
            self.observation.observation_id != self.observation_id
            or self.observation.run_id != self.run_id
            or self.observation.step_id != self.step_id
        ):
            raise PlanStepExecutionResultRecordingInvariantError(
                "observation identity does not match recording lineage"
            )
        if (
            self.observation.source != "execution"
            or self.observation.source_reference != self.execution_id
            or self.observation.kind != "execution_result"
        ):
            raise PlanStepExecutionResultRecordingInvariantError(
                "observation must be canonical execution-result evidence"
            )
        if self.observation not in self.recorded_run.observations:
            raise PlanStepExecutionResultRecordingInvariantError(
                "recorded Run does not contain the claimed observation"
            )

    def to_data(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible representation."""

        return {
            "plan_id": self.plan_id,
            "run_id": self.run_id,
            "recorded_from_revision": self.recorded_from_revision,
            "step_id": self.step_id,
            "execution_id": self.execution_id,
            "observation_id": self.observation_id,
            "record_update_id": self.record_update_id,
            "observation": self.observation.to_data(),
            "recorded_run": self.recorded_run.to_data(),
        }
