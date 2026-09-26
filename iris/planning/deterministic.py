"""Explicit-rule deterministic Planner with no discovery or side effects."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from iris.memory.models import identifier, utc_time
from iris.planning.errors import DuplicatePlanningRuleError
from iris.planning.models import (
    Plan,
    PlanningContextRequirement,
    PlanningReason,
    PlanningRequest,
    PlanningResult,
    PlanningStatus,
    PlanStep,
    _constraint_conflicts,
    _context_requirement_key,
    _validate_step_graph,
)


def _objective_key(value: str) -> str:
    return " ".join(value.split()).casefold()


@dataclass(frozen=True, slots=True)
class PlanningRule:
    """Caller-supplied exact-objective template for deterministic Planning."""

    objective: str
    steps: tuple[PlanStep, ...] = ()
    assumptions: tuple[str, ...] = ()
    required_context: tuple[PlanningContextRequirement, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.objective, str) or not self.objective.strip():
            raise ValueError("rule objective must be nonblank text")
        object.__setattr__(self, "objective", self.objective.strip())
        steps = tuple(self.steps)
        if any(not isinstance(item, PlanStep) for item in steps):
            raise TypeError("rule steps must contain PlanStep values")
        if steps:
            _validate_step_graph(steps)
        object.__setattr__(
            self, "steps", tuple(sorted(steps, key=lambda item: item.step_id))
        )
        assumptions = tuple(sorted(item.strip() for item in self.assumptions))
        if any(not item for item in assumptions):
            raise ValueError("rule assumptions must be nonblank text")
        if len(assumptions) != len(set(assumptions)):
            raise ValueError("rule assumptions must be distinct")
        if not steps and assumptions:
            raise ValueError("a no-plan rule cannot declare plan assumptions")
        object.__setattr__(self, "assumptions", assumptions)
        requirements = tuple(self.required_context)
        if any(
            not isinstance(item, PlanningContextRequirement) for item in requirements
        ):
            raise TypeError(
                "required_context must contain PlanningContextRequirement values"
            )
        requirements = tuple(sorted(requirements, key=_context_requirement_key))
        if len(requirements) != len(set(requirements)):
            raise ValueError("required context requirements must be distinct")
        object.__setattr__(self, "required_context", requirements)


class DeterministicPlanner:
    """Match explicit rules and validate a representation without executing it."""

    def __init__(
        self,
        rules: tuple[PlanningRule, ...],
        *,
        clock: Callable[[], datetime] | None = None,
        plan_id_factory: Callable[[], str] | None = None,
        result_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if not isinstance(rules, tuple) or any(
            not isinstance(rule, PlanningRule) for rule in rules
        ):
            raise TypeError("rules must be a tuple of PlanningRule")
        by_objective: dict[str, PlanningRule] = {}
        for rule in rules:
            key = _objective_key(rule.objective)
            if key in by_objective:
                raise DuplicatePlanningRuleError(
                    f"duplicate deterministic objective: {rule.objective}"
                )
            by_objective[key] = rule
        self._rules = by_objective
        self._clock: Callable[[], datetime] = (
            (lambda: datetime.now(UTC)) if clock is None else clock
        )
        self._plan_id_factory: Callable[[], str] = (
            (lambda: uuid4().hex) if plan_id_factory is None else plan_id_factory
        )
        self._result_id_factory: Callable[[], str] = (
            (lambda: uuid4().hex) if result_id_factory is None else result_id_factory
        )

    def plan(self, request: PlanningRequest) -> PlanningResult:
        if not isinstance(request, PlanningRequest):
            raise TypeError("request must be a PlanningRequest")
        instant = utc_time(self._clock(), "planning result created_at")
        if instant < request.created_at:
            raise ValueError("planning result cannot predate its request")
        result_id = self._result_id_factory()
        identifier(result_id, "planning_result_id")

        conflicts = _constraint_conflicts(request.goal.constraints)
        if conflicts:
            return self._result(
                request,
                result_id,
                instant,
                PlanningStatus.UNSATISFIABLE,
                PlanningReason.CONFLICTING_CONSTRAINTS,
                constraint_conflicts=conflicts,
            )

        rule = self._rules.get(_objective_key(request.goal.objective))
        if rule is None:
            return self._result(
                request,
                result_id,
                instant,
                PlanningStatus.UNSATISFIABLE,
                PlanningReason.NO_REGISTERED_STRATEGY,
            )

        available = (
            set()
            if request.context is None
            else {(item.kind, item.key, item.scope) for item in request.context.items}
        )
        missing = tuple(
            item
            for item in rule.required_context
            if (item.kind, item.key, item.scope) not in available
        )
        if missing:
            return self._result(
                request,
                result_id,
                instant,
                PlanningStatus.INSUFFICIENT_CONTEXT,
                PlanningReason.MISSING_REQUIRED_CONTEXT,
                missing_context=missing,
            )

        if not rule.steps:
            return self._result(
                request,
                result_id,
                instant,
                PlanningStatus.NO_PLAN_REQUIRED,
                PlanningReason.DECOMPOSITION_UNNECESSARY,
            )

        plan_id = self._plan_id_factory()
        identifier(plan_id, "plan_id")
        plan = Plan(
            plan_id=plan_id,
            goal_id=request.goal.goal_id,
            assumptions=rule.assumptions,
            steps=rule.steps,
        )
        return self._result(
            request,
            result_id,
            instant,
            PlanningStatus.PLAN_CREATED,
            PlanningReason.DECOMPOSITION_CREATED,
            plan=plan,
        )

    @staticmethod
    def _result(
        request: PlanningRequest,
        result_id: str,
        created_at: datetime,
        status: PlanningStatus,
        reason: PlanningReason,
        *,
        plan: Plan | None = None,
        missing_context: tuple[PlanningContextRequirement, ...] = (),
        constraint_conflicts: tuple[str, ...] = (),
    ) -> PlanningResult:
        return PlanningResult(
            planning_result_id=result_id,
            planning_request_id=request.planning_request_id,
            goal_id=request.goal.goal_id,
            status=status,
            reason=reason,
            created_at=created_at,
            plan=plan,
            missing_context=missing_context,
            constraint_conflicts=constraint_conflicts,
        )
