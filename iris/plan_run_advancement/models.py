"""Result model for one bounded PlanRun progress advancement."""

from __future__ import annotations

from dataclasses import dataclass

from iris.plan_control import ControlDecision
from iris.plan_run_advancement.errors import (
    PlanRunProgressAdvanceInvariantError,
)
from iris.plan_runs import PlanRun


def _identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise PlanRunProgressAdvanceInvariantError(
            f"{name} must be a nonblank identifier"
        )
    return value


def _revision(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise PlanRunProgressAdvanceInvariantError(
            f"{name} must be a nonnegative integer"
        )
    return value


@dataclass(frozen=True, slots=True)
class PlanRunProgressAdvanceResult:
    """One new Run revision and its single post-mutation control decision."""

    source_update_id: str
    source_revision: int
    updated_run: PlanRun
    control_decision: ControlDecision

    def __post_init__(self) -> None:
        _identifier(self.source_update_id, "source_update_id")
        _revision(self.source_revision, "source_revision")
        if not isinstance(self.updated_run, PlanRun):
            raise TypeError("updated_run must be a PlanRun")
        if not isinstance(self.control_decision, ControlDecision):
            raise TypeError("control_decision must be a ControlDecision")
        if self.updated_run.revision != self.source_revision + 1:
            raise PlanRunProgressAdvanceInvariantError(
                "updated Run revision must be source_revision + 1"
            )
        if self.control_decision.plan_id != self.updated_run.plan_id:
            raise PlanRunProgressAdvanceInvariantError(
                "control decision plan_id must match updated Run"
            )
        if self.control_decision.run_id != self.updated_run.run_id:
            raise PlanRunProgressAdvanceInvariantError(
                "control decision run_id must match updated Run"
            )
        if self.control_decision.observed_revision != self.updated_run.revision:
            raise PlanRunProgressAdvanceInvariantError(
                "control decision must observe the updated Run revision"
            )

    def to_data(self) -> dict[str, object]:
        return {
            "source_update_id": self.source_update_id,
            "source_revision": self.source_revision,
            "updated_run": self.updated_run.to_data(),
            "control_decision": self.control_decision.to_data(),
        }
