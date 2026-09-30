"""Immutable result of one bounded PlanStep execution-start attempt."""

from dataclasses import dataclass

from iris.execution import ExecutionResult, ExecutionStatus
from iris.plan_runs import PlanRun, StepProgressState
from iris.plan_step_execution_start.errors import (
    PlanStepExecutionStartInvariantError,
)


def _identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise PlanStepExecutionStartInvariantError(
            f"{name} must be a nonblank identifier"
        )
    return value


@dataclass(frozen=True, slots=True)
class PlanStepExecutionStartResult:
    """Lineage and outputs from either a rejected or activated start attempt."""

    plan_id: str
    run_id: str
    source_revision: int
    step_id: str
    execution_id: str
    activation_update_id: str | None
    active_run: PlanRun | None
    execution_result: ExecutionResult

    def __post_init__(self) -> None:
        for value, name in (
            (self.plan_id, "start result plan_id"),
            (self.run_id, "start result run_id"),
            (self.step_id, "start result step_id"),
            (self.execution_id, "start result execution_id"),
        ):
            _identifier(value, name)
        if isinstance(self.source_revision, bool) or not isinstance(
            self.source_revision, int
        ):
            raise TypeError("start result source_revision must be an integer")
        if self.source_revision < 0:
            raise PlanStepExecutionStartInvariantError(
                "start result source_revision must be nonnegative"
            )
        if not isinstance(self.execution_result, ExecutionResult):
            raise TypeError("execution_result must be an ExecutionResult")
        if self.execution_result.execution_id != self.execution_id:
            raise PlanStepExecutionStartInvariantError(
                "execution result identity does not match start lineage"
            )

        if self.active_run is None:
            if self.activation_update_id is not None:
                raise PlanStepExecutionStartInvariantError(
                    "non-started result cannot contain an activation update"
                )
            failure = self.execution_result.failure
            if (
                self.execution_result.status is not ExecutionStatus.REJECTED
                or self.execution_result.handler_reference is not None
                or failure is None
                or failure.code != "handler_unavailable"
            ):
                raise PlanStepExecutionStartInvariantError(
                    "non-started result must be canonical handler unavailability"
                )
            return

        if not isinstance(self.active_run, PlanRun):
            raise TypeError("active_run must be a PlanRun or None")
        if self.activation_update_id is None:
            raise PlanStepExecutionStartInvariantError(
                "an ACTIVE Run requires an activation update identity"
            )
        _identifier(self.activation_update_id, "activation_update_id")
        if (
            self.active_run.plan_id != self.plan_id
            or self.active_run.run_id != self.run_id
        ):
            raise PlanStepExecutionStartInvariantError(
                "ACTIVE Run identity does not match start lineage"
            )
        if self.active_run.revision != self.source_revision + 1:
            raise PlanStepExecutionStartInvariantError(
                "ACTIVE Run must advance exactly one revision"
            )
        progress = next(
            (
                item
                for item in self.active_run.step_progress
                if item.step_id == self.step_id
            ),
            None,
        )
        if progress is None or progress.state is not StepProgressState.ACTIVE:
            raise PlanStepExecutionStartInvariantError(
                "started PlanStep must be ACTIVE in the derived Run"
            )
        if self.execution_result.handler_reference is None:
            raise PlanStepExecutionStartInvariantError(
                "started execution result must identify its concrete handler"
            )

    def to_data(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible representation."""

        return {
            "plan_id": self.plan_id,
            "run_id": self.run_id,
            "source_revision": self.source_revision,
            "step_id": self.step_id,
            "execution_id": self.execution_id,
            "activation_update_id": self.activation_update_id,
            "active_run": (
                None if self.active_run is None else self.active_run.to_data()
            ),
            "execution_result": self.execution_result.to_trace(),
        }
