"""Deterministic PlanRun validation, creation, availability, and condition."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from iris.plan_runs.errors import (
    PlanRunIdentityError,
    PlanRunInvariantError,
    UnknownPlanStepError,
)
from iris.plan_runs.models import (
    PlanBlockerState,
    PlanRun,
    PlanRunCondition,
    StepAvailability,
    StepProgress,
    StepProgressState,
    identifier,
    utc_time,
)
from iris.planning import Plan


def validate_plan_run(plan: Plan, run: PlanRun) -> None:
    """Validate all invariants that require the immutable Plan definition."""

    if not isinstance(plan, Plan):
        raise TypeError("plan must be a Plan")
    if not isinstance(run, PlanRun):
        raise TypeError("run must be a PlanRun")
    if run.plan_id != plan.plan_id:
        raise PlanRunIdentityError("PlanRun references a different Plan")
    if run.goal_id != plan.goal_id:
        raise PlanRunIdentityError("PlanRun references a different Goal")

    plan_step_ids = {step.step_id for step in plan.steps}
    progress_ids = {item.step_id for item in run.step_progress}
    missing = plan_step_ids - progress_ids
    unknown = progress_ids - plan_step_ids
    if missing or unknown:
        details: list[str] = []
        if missing:
            details.append(f"missing progress: {', '.join(sorted(missing))}")
        if unknown:
            details.append(f"unknown progress: {', '.join(sorted(unknown))}")
        raise PlanRunInvariantError("; ".join(details))

    for observation in run.observations:
        if observation.step_id is not None and observation.step_id not in plan_step_ids:
            raise UnknownPlanStepError(
                f"observation references unknown step {observation.step_id}"
            )
    for blocker in run.blockers:
        if blocker.step_id not in plan_step_ids:
            raise UnknownPlanStepError(
                f"blocker references unknown step {blocker.step_id}"
            )
        progress = next(
            item for item in run.step_progress if item.step_id == blocker.step_id
        )
        if blocker.state is PlanBlockerState.ACTIVE and (
            progress.state is not StepProgressState.NOT_STARTED
        ):
            raise PlanRunInvariantError(
                "active blockers may exist only on NOT_STARTED steps"
            )


@dataclass(frozen=True, slots=True)
class StepAvailabilityResult:
    """Derived eligibility and structural reason details for one step."""

    step_id: str
    availability: StepAvailability
    explicit_blocker_ids: tuple[str, ...] = ()
    failed_dependency_ids: tuple[str, ...] = ()
    pending_dependency_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        identifier(self.step_id, "availability step_id")
        if not isinstance(self.availability, StepAvailability):
            raise TypeError("availability must be a StepAvailability")
        for name in (
            "explicit_blocker_ids",
            "failed_dependency_ids",
            "pending_dependency_ids",
        ):
            values = tuple(sorted(getattr(self, name)))
            for value in values:
                identifier(value, name)
            if len(values) != len(set(values)):
                raise ValueError(f"{name} must contain distinct identifiers")
            object.__setattr__(self, name, values)

    def to_data(self) -> dict[str, object]:
        return {
            "step_id": self.step_id,
            "availability": self.availability.value,
            "explicit_blocker_ids": list(self.explicit_blocker_ids),
            "failed_dependency_ids": list(self.failed_dependency_ids),
            "pending_dependency_ids": list(self.pending_dependency_ids),
        }


@dataclass(frozen=True, slots=True)
class PlanRunConditionResult:
    """Derived structural Run condition, not Goal satisfaction or failure."""

    run_id: str
    revision: int
    condition: PlanRunCondition

    def __post_init__(self) -> None:
        identifier(self.run_id, "condition run_id")
        if isinstance(self.revision, bool) or not isinstance(self.revision, int):
            raise TypeError("condition revision must be an integer")
        if self.revision < 0:
            raise ValueError("condition revision must be nonnegative")
        if not isinstance(self.condition, PlanRunCondition):
            raise TypeError("condition must be a PlanRunCondition")

    def to_data(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "revision": self.revision,
            "condition": self.condition.value,
        }


def derive_step_availability(
    plan: Plan, run: PlanRun, step_id: str
) -> StepAvailabilityResult:
    """Derive availability using the documented deterministic precedence."""

    validate_plan_run(plan, run)
    identifier(step_id, "availability step_id")
    steps = {step.step_id: step for step in plan.steps}
    step = steps.get(step_id)
    if step is None:
        raise UnknownPlanStepError(f"unknown Plan step {step_id}")
    progress = {item.step_id: item for item in run.step_progress}
    selected = progress[step_id]

    if selected.state in {StepProgressState.SUCCEEDED, StepProgressState.FAILED}:
        return StepAvailabilityResult(step_id, StepAvailability.TERMINAL)
    if selected.state is StepProgressState.ACTIVE:
        return StepAvailabilityResult(step_id, StepAvailability.ACTIVE)

    explicit_blockers = tuple(
        blocker.blocker_id
        for blocker in run.blockers
        if blocker.step_id == step_id and blocker.state is PlanBlockerState.ACTIVE
    )
    failed_dependencies = tuple(
        dependency
        for dependency in step.depends_on
        if progress[dependency].state is StepProgressState.FAILED
    )
    pending_dependencies = tuple(
        dependency
        for dependency in step.depends_on
        if progress[dependency].state is not StepProgressState.SUCCEEDED
    )
    if explicit_blockers:
        return StepAvailabilityResult(
            step_id,
            StepAvailability.BLOCKED,
            explicit_blocker_ids=explicit_blockers,
            failed_dependency_ids=failed_dependencies,
            pending_dependency_ids=pending_dependencies,
        )
    if failed_dependencies:
        return StepAvailabilityResult(
            step_id,
            StepAvailability.BLOCKED,
            failed_dependency_ids=failed_dependencies,
            pending_dependency_ids=pending_dependencies,
        )
    if pending_dependencies:
        return StepAvailabilityResult(
            step_id,
            StepAvailability.WAITING_DEPENDENCIES,
            pending_dependency_ids=pending_dependencies,
        )
    return StepAvailabilityResult(step_id, StepAvailability.READY)


def derive_availability(plan: Plan, run: PlanRun) -> tuple[StepAvailabilityResult, ...]:
    """Return stable derived availability for every PlanStep."""

    validate_plan_run(plan, run)
    return tuple(
        derive_step_availability(plan, run, step.step_id) for step in plan.steps
    )


def derive_run_condition(plan: Plan, run: PlanRun) -> PlanRunConditionResult:
    """Derive completion/liveness without declaring Goal success or failure."""

    validate_plan_run(plan, run)
    if all(
        progress.state is StepProgressState.SUCCEEDED for progress in run.step_progress
    ):
        condition = PlanRunCondition.STRUCTURALLY_COMPLETE
    else:
        available = derive_availability(plan, run)
        if any(
            item.availability in {StepAvailability.READY, StepAvailability.ACTIVE}
            for item in available
        ):
            condition = PlanRunCondition.OPEN
        else:
            condition = PlanRunCondition.CANNOT_ADVANCE
    return PlanRunConditionResult(run.run_id, run.revision, condition)


class PlanRunFactory:
    """Create revision-zero Run state from an explicit immutable Plan."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        run_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._clock: Callable[[], datetime] = (
            (lambda: datetime.now(UTC)) if clock is None else clock
        )
        self._run_id_factory: Callable[[], str] = (
            (lambda: uuid4().hex) if run_id_factory is None else run_id_factory
        )

    def create(self, plan: Plan) -> PlanRun:
        if not isinstance(plan, Plan):
            raise TypeError("plan must be a Plan")
        instant = utc_time(self._clock(), "run created_at")
        run_id = self._run_id_factory()
        identifier(run_id, "run_id")
        run = PlanRun(
            run_id=run_id,
            plan_id=plan.plan_id,
            goal_id=plan.goal_id,
            revision=0,
            created_at=instant,
            updated_at=instant,
            step_progress=tuple(
                StepProgress(step.step_id, StepProgressState.NOT_STARTED, instant)
                for step in plan.steps
            ),
        )
        validate_plan_run(plan, run)
        return run
