"""Bounded composition of one progress reduction and one control pass."""

from __future__ import annotations

from iris.plan_control import (
    PlanRunController,
    validate_control_decision_current,
)
from iris.plan_run_advancement.errors import (
    PlanRunProgressAdvanceInvariantError,
)
from iris.plan_run_advancement.models import PlanRunProgressAdvanceResult
from iris.plan_runs import PlanRun, PlanRunReducer, StepProgressUpdate
from iris.planning import Plan


class PlanRunProgressAdvancer:
    """Apply one StepProgressUpdate, re-control once, and stop."""

    def __init__(self, *, controller: PlanRunController | None = None) -> None:
        if controller is not None and not isinstance(controller, PlanRunController):
            raise TypeError("controller must be a PlanRunController")
        self._controller = controller or PlanRunController()

    def advance(
        self,
        plan: Plan,
        run: PlanRun,
        update: StepProgressUpdate,
    ) -> PlanRunProgressAdvanceResult:
        """Derive one new Run and one decision over that exact revision."""

        if not isinstance(plan, Plan):
            raise TypeError("plan must be a Plan")
        if not isinstance(run, PlanRun):
            raise TypeError("run must be a PlanRun")
        if not isinstance(update, StepProgressUpdate):
            raise TypeError("update must be a StepProgressUpdate")

        updated_run = PlanRunReducer().apply(plan, run, update)
        if updated_run.revision != run.revision + 1:
            raise PlanRunProgressAdvanceInvariantError(
                "reducer must advance the PlanRun by exactly one revision"
            )

        decision = self._controller.decide(plan, updated_run)
        validate_control_decision_current(plan, updated_run, decision)
        return PlanRunProgressAdvanceResult(
            source_update_id=update.update_id,
            source_revision=update.expected_revision,
            updated_run=updated_run,
            control_decision=decision,
        )
