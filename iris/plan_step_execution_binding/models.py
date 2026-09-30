"""Immutable lineage witness for one current PlanStep execution request."""

from dataclasses import dataclass

from iris.plan_step_execution_binding.errors import (
    PlanStepExecutionBindingInvariantError,
)


def _identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise PlanStepExecutionBindingInvariantError(
            f"{name} must be a nonblank identifier"
        )
    return value


@dataclass(frozen=True, slots=True)
class PlanStepExecutionBinding:
    """Compact proof that execution lineage matches one exact PlanRun revision."""

    plan_id: str
    run_id: str
    observed_revision: int
    step_id: str
    execution_id: str
    subject_id: str
    orchestration_decision_id: str
    context_snapshot_id: str
    handling_need_id: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.plan_id, "binding plan_id"),
            (self.run_id, "binding run_id"),
            (self.step_id, "binding step_id"),
            (self.execution_id, "binding execution_id"),
            (self.subject_id, "binding subject_id"),
            (
                self.orchestration_decision_id,
                "binding orchestration_decision_id",
            ),
            (self.context_snapshot_id, "binding context_snapshot_id"),
            (self.handling_need_id, "binding handling_need_id"),
        ):
            _identifier(value, name)
        if isinstance(self.observed_revision, bool) or not isinstance(
            self.observed_revision, int
        ):
            raise TypeError("binding observed_revision must be an integer")
        if self.observed_revision < 0:
            raise PlanStepExecutionBindingInvariantError(
                "binding observed_revision must be nonnegative"
            )

    def to_data(self) -> dict[str, object]:
        """Return the deterministic JSON-compatible lineage representation."""

        return {
            "plan_id": self.plan_id,
            "run_id": self.run_id,
            "observed_revision": self.observed_revision,
            "step_id": self.step_id,
            "execution_id": self.execution_id,
            "subject_id": self.subject_id,
            "orchestration_decision_id": self.orchestration_decision_id,
            "context_snapshot_id": self.context_snapshot_id,
            "handling_need_id": self.handling_need_id,
        }
