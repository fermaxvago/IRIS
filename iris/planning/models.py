"""Immutable representations for goals and planning without execution."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TypeAlias

from iris.context import ContextSnapshot
from iris.memory import MemoryScope, ScopeKind
from iris.memory.models import identifier, utc_time, vocabulary
from iris.orchestrator import HandlingKind
from iris.planning.errors import PlanValidationError

ConstraintValue: TypeAlias = str | int | float | bool | datetime | None


def _text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonblank text")
    return value.strip()


@dataclass(frozen=True, slots=True)
class GoalScope:
    """The declared domain of a Goal; it is not an authorization grant."""

    kind: ScopeKind
    identifier: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ScopeKind):
            raise TypeError("scope kind must be a ScopeKind")
        if self.kind is ScopeKind.GLOBAL and self.identifier is not None:
            raise ValueError("global goal scope cannot have an identifier")
        if self.kind is not ScopeKind.GLOBAL:
            if self.identifier is None:
                raise ValueError("non-global goal scope requires an identifier")
            identifier(self.identifier, "goal scope identifier")

    def to_data(self) -> dict[str, object]:
        return {"kind": self.kind.value, "identifier": self.identifier}


@dataclass(frozen=True, slots=True)
class GoalProvenance:
    """Explicit origin supplied by the caller; absence is never inferred."""

    source_type: str
    source_id: str | None = None
    actor: str | None = None

    def __post_init__(self) -> None:
        vocabulary(self.source_type, "goal provenance source_type")
        for name in ("source_id", "actor"):
            value = getattr(self, name)
            if value is not None:
                identifier(value, f"goal provenance {name}")

    def to_data(self) -> dict[str, object]:
        return {
            "source_type": self.source_type,
            "source_id": self.source_id,
            "actor": self.actor,
        }


class ConstraintKind(StrEnum):
    REQUIRE = "require"
    FORBID = "forbid"
    NOT_BEFORE = "not_before"
    DEADLINE = "deadline"


@dataclass(frozen=True, slots=True)
class PlanningConstraint:
    """A declared planning limitation, never an authorization decision."""

    kind: ConstraintKind
    subject: str
    value: ConstraintValue = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ConstraintKind):
            raise TypeError("constraint kind must be a ConstraintKind")
        vocabulary(self.subject, "constraint subject")
        value = self.value
        if self.kind in {ConstraintKind.NOT_BEFORE, ConstraintKind.DEADLINE}:
            if not isinstance(value, datetime):
                raise TypeError("temporal constraints require a datetime value")
            value = utc_time(value, "constraint value")
        elif value is not None and type(value) not in (str, int, float, bool):
            raise TypeError("constraint value must be a JSON scalar or datetime")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("constraint value must be finite")
        if isinstance(value, str):
            value = _text(value, "constraint value")
        object.__setattr__(self, "value", value)

    def to_data(self) -> dict[str, object]:
        value: object = self.value
        if isinstance(value, datetime):
            value = value.isoformat()
        return {"kind": self.kind.value, "subject": self.subject, "value": value}


def _constraint_key(item: PlanningConstraint) -> tuple[str, str, str]:
    return (item.kind.value, item.subject, repr(item.value))


def _normalize_constraints(
    constraints: tuple[PlanningConstraint, ...],
) -> tuple[PlanningConstraint, ...]:
    values = tuple(constraints)
    if any(not isinstance(item, PlanningConstraint) for item in values):
        raise TypeError("constraints must contain PlanningConstraint values")
    ordered = tuple(sorted(values, key=_constraint_key))
    if len(ordered) != len(set(ordered)):
        raise ValueError("constraints must not contain duplicates")
    return ordered


def _constraint_conflicts(
    constraints: tuple[PlanningConstraint, ...],
) -> tuple[str, ...]:
    conflicts: list[str] = []
    required = [item for item in constraints if item.kind is ConstraintKind.REQUIRE]
    forbidden = [item for item in constraints if item.kind is ConstraintKind.FORBID]
    for requirement in required:
        for prohibition in forbidden:
            if requirement.subject != prohibition.subject:
                continue
            if (
                requirement.value == prohibition.value
                or requirement.value is None
                or prohibition.value is None
            ):
                conflicts.append(f"required_and_forbidden:{requirement.subject}")

    temporal_subjects = sorted(
        {
            item.subject
            for item in constraints
            if item.kind in {ConstraintKind.NOT_BEFORE, ConstraintKind.DEADLINE}
        }
    )
    for subject in temporal_subjects:
        starts = [
            item.value
            for item in constraints
            if item.subject == subject
            and item.kind is ConstraintKind.NOT_BEFORE
            and isinstance(item.value, datetime)
        ]
        deadlines = [
            item.value
            for item in constraints
            if item.subject == subject
            and item.kind is ConstraintKind.DEADLINE
            and isinstance(item.value, datetime)
        ]
        if starts and deadlines and max(starts) >= min(deadlines):
            conflicts.append(f"invalid_time_window:{subject}")
    return tuple(sorted(set(conflicts)))


@dataclass(frozen=True, slots=True)
class Goal:
    """Desired state, constraints, and success criteria without a strategy."""

    goal_id: str
    objective: str
    scope: GoalScope
    provenance: GoalProvenance
    constraints: tuple[PlanningConstraint, ...] = ()
    success_criteria: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        identifier(self.goal_id, "goal_id")
        object.__setattr__(self, "objective", _text(self.objective, "objective"))
        if not isinstance(self.scope, GoalScope):
            raise TypeError("scope must be a GoalScope")
        if not isinstance(self.provenance, GoalProvenance):
            raise TypeError("provenance must be GoalProvenance")
        object.__setattr__(
            self, "constraints", _normalize_constraints(self.constraints)
        )
        criteria = tuple(
            sorted(_text(item, "success criterion") for item in self.success_criteria)
        )
        if len(criteria) != len(set(criteria)):
            raise ValueError("success criteria must be distinct")
        object.__setattr__(self, "success_criteria", criteria)

    def to_data(self) -> dict[str, object]:
        return {
            "goal_id": self.goal_id,
            "objective": self.objective,
            "scope": self.scope.to_data(),
            "provenance": self.provenance.to_data(),
            "constraints": [item.to_data() for item in self.constraints],
            "success_criteria": list(self.success_criteria),
        }


@dataclass(frozen=True, slots=True)
class PlanStep:
    """One conceptual objective in a Plan, not an executable instruction."""

    step_id: str
    objective: str
    expected_outcome: str
    depends_on: tuple[str, ...] = ()
    required_handling: HandlingKind | None = None
    constraints: tuple[PlanningConstraint, ...] = ()

    def __post_init__(self) -> None:
        identifier(self.step_id, "step_id")
        object.__setattr__(self, "objective", _text(self.objective, "step objective"))
        object.__setattr__(
            self,
            "expected_outcome",
            _text(self.expected_outcome, "expected outcome"),
        )
        dependencies = tuple(sorted(self.depends_on))
        for dependency in dependencies:
            identifier(dependency, "step dependency")
        if len(dependencies) != len(set(dependencies)):
            raise PlanValidationError("step dependencies must be distinct")
        if self.step_id in dependencies:
            raise PlanValidationError("a step cannot depend on itself")
        object.__setattr__(self, "depends_on", dependencies)
        if self.required_handling is not None:
            if not isinstance(self.required_handling, HandlingKind):
                raise TypeError("required_handling must be a HandlingKind or None")
            if self.required_handling is HandlingKind.CLARIFICATION:
                raise ValueError("clarification is not executable step handling")
        constraints = _normalize_constraints(self.constraints)
        if conflicts := _constraint_conflicts(constraints):
            raise PlanValidationError(
                f"step constraints are incompatible: {', '.join(conflicts)}"
            )
        object.__setattr__(self, "constraints", constraints)

    def to_data(self) -> dict[str, object]:
        return {
            "step_id": self.step_id,
            "objective": self.objective,
            "depends_on": list(self.depends_on),
            "required_handling": (
                None if self.required_handling is None else self.required_handling.value
            ),
            "constraints": [item.to_data() for item in self.constraints],
            "expected_outcome": self.expected_outcome,
        }


def _validate_step_graph(steps: tuple[PlanStep, ...]) -> None:
    if not steps:
        raise PlanValidationError("a Plan requires at least one step")
    ids = tuple(item.step_id for item in steps)
    if len(ids) != len(set(ids)):
        raise PlanValidationError("step identifiers must be unique")
    known = set(ids)
    for step in steps:
        unknown = set(step.depends_on) - known
        if unknown:
            raise PlanValidationError(
                f"step {step.step_id} references unknown dependencies: "
                f"{', '.join(sorted(unknown))}"
            )

    dependencies = {item.step_id: item.depends_on for item in steps}
    state: dict[str, int] = {}

    def visit(step_id: str) -> None:
        marker = state.get(step_id, 0)
        if marker == 1:
            raise PlanValidationError("plan dependencies must form an acyclic graph")
        if marker == 2:
            return
        state[step_id] = 1
        for dependency in dependencies[step_id]:
            visit(dependency)
        state[step_id] = 2

    for step_id in sorted(dependencies):
        visit(step_id)


@dataclass(frozen=True, slots=True)
class Plan:
    """Validated strategy data. It contains no run or observed outcome state."""

    plan_id: str
    goal_id: str
    assumptions: tuple[str, ...]
    steps: tuple[PlanStep, ...]

    def __post_init__(self) -> None:
        identifier(self.plan_id, "plan_id")
        identifier(self.goal_id, "goal_id")
        if self.plan_id == self.goal_id:
            raise PlanValidationError("Plan and Goal must have independent identities")
        assumptions = tuple(
            sorted(_text(item, "plan assumption") for item in self.assumptions)
        )
        if len(assumptions) != len(set(assumptions)):
            raise PlanValidationError("plan assumptions must be distinct")
        object.__setattr__(self, "assumptions", assumptions)
        steps = tuple(self.steps)
        if any(not isinstance(item, PlanStep) for item in steps):
            raise TypeError("steps must contain PlanStep values")
        steps = tuple(sorted(steps, key=lambda item: item.step_id))
        _validate_step_graph(steps)
        object.__setattr__(self, "steps", steps)

    def to_data(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "goal_id": self.goal_id,
            "assumptions": list(self.assumptions),
            "steps": [item.to_data() for item in self.steps],
        }


@dataclass(frozen=True, slots=True)
class PlanningContextRequirement:
    """One Context item a deterministic rule requires; no lookup is performed."""

    kind: str
    key: str
    scope: MemoryScope

    def __post_init__(self) -> None:
        vocabulary(self.kind, "planning context kind")
        vocabulary(self.key, "planning context key")
        if not isinstance(self.scope, MemoryScope):
            raise TypeError("planning context scope must be a MemoryScope")

    def to_data(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "key": self.key,
            "scope": {
                "kind": self.scope.kind.value,
                "identifier": self.scope.identifier,
            },
        }


def _context_requirement_key(
    item: PlanningContextRequirement,
) -> tuple[str, str, str, str]:
    return (
        item.scope.kind.value,
        item.scope.identifier or "",
        item.kind,
        item.key,
    )


@dataclass(frozen=True, slots=True)
class PlanningRequest:
    """Explicit Planning input; Context is supplied, never discovered."""

    planning_request_id: str
    goal: Goal
    created_at: datetime
    context: ContextSnapshot | None = None

    def __post_init__(self) -> None:
        identifier(self.planning_request_id, "planning_request_id")
        if not isinstance(self.goal, Goal):
            raise TypeError("goal must be a Goal")
        instant = utc_time(self.created_at, "planning request created_at")
        object.__setattr__(self, "created_at", instant)
        if self.context is not None:
            if not isinstance(self.context, ContextSnapshot):
                raise TypeError("context must be a ContextSnapshot or None")
            if self.context.created_at > instant:
                raise ValueError("planning request cannot predate its context snapshot")
            provenance = self.goal.provenance
            if (
                provenance.source_type == "request"
                and provenance.source_id is not None
                and provenance.source_id != self.context.request_id
            ):
                raise ValueError("Goal provenance and Context request do not match")

    def to_data(self) -> dict[str, object]:
        return {
            "planning_request_id": self.planning_request_id,
            "goal": self.goal.to_data(),
            "created_at": self.created_at.isoformat(),
            "context_snapshot_id": (
                None if self.context is None else self.context.snapshot_id
            ),
        }


class PlanningStatus(StrEnum):
    PLAN_CREATED = "plan_created"
    NO_PLAN_REQUIRED = "no_plan_required"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    UNSATISFIABLE = "unsatisfiable"


class PlanningReason(StrEnum):
    DECOMPOSITION_CREATED = "decomposition_created"
    DECOMPOSITION_UNNECESSARY = "decomposition_unnecessary"
    MISSING_REQUIRED_CONTEXT = "missing_required_context"
    CONFLICTING_CONSTRAINTS = "conflicting_constraints"
    NO_REGISTERED_STRATEGY = "no_registered_strategy"


_REASONS_BY_STATUS = {
    PlanningStatus.PLAN_CREATED: {PlanningReason.DECOMPOSITION_CREATED},
    PlanningStatus.NO_PLAN_REQUIRED: {PlanningReason.DECOMPOSITION_UNNECESSARY},
    PlanningStatus.INSUFFICIENT_CONTEXT: {PlanningReason.MISSING_REQUIRED_CONTEXT},
    PlanningStatus.UNSATISFIABLE: {
        PlanningReason.CONFLICTING_CONSTRAINTS,
        PlanningReason.NO_REGISTERED_STRATEGY,
    },
}


@dataclass(frozen=True, slots=True)
class PlanningResult:
    """Observable Planning representation. It never reports execution state."""

    planning_result_id: str
    planning_request_id: str
    goal_id: str
    status: PlanningStatus
    reason: PlanningReason
    created_at: datetime
    plan: Plan | None = None
    missing_context: tuple[PlanningContextRequirement, ...] = ()
    constraint_conflicts: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for value, name in (
            (self.planning_result_id, "planning_result_id"),
            (self.planning_request_id, "planning_request_id"),
            (self.goal_id, "goal_id"),
        ):
            identifier(value, name)
        if not isinstance(self.status, PlanningStatus):
            raise TypeError("status must be a PlanningStatus")
        if not isinstance(self.reason, PlanningReason):
            raise TypeError("reason must be a PlanningReason")
        if self.reason not in _REASONS_BY_STATUS[self.status]:
            raise ValueError("reason is incompatible with planning status")
        object.__setattr__(
            self, "created_at", utc_time(self.created_at, "planning result created_at")
        )
        if self.plan is not None and not isinstance(self.plan, Plan):
            raise TypeError("plan must be a Plan or None")
        if self.status is PlanningStatus.PLAN_CREATED:
            if self.plan is None:
                raise ValueError("PLAN_CREATED requires a Plan")
            if self.plan.goal_id != self.goal_id:
                raise ValueError("PlanningResult Plan references a different Goal")
        elif self.plan is not None:
            raise ValueError("only PLAN_CREATED may contain a Plan")

        missing = tuple(self.missing_context)
        if any(not isinstance(item, PlanningContextRequirement) for item in missing):
            raise TypeError(
                "missing_context must contain PlanningContextRequirement values"
            )
        missing = tuple(sorted(missing, key=_context_requirement_key))
        if len(missing) != len(set(missing)):
            raise ValueError("missing context requirements must be distinct")
        if self.status is PlanningStatus.INSUFFICIENT_CONTEXT and not missing:
            raise ValueError("INSUFFICIENT_CONTEXT requires missing context")
        if self.status is not PlanningStatus.INSUFFICIENT_CONTEXT and missing:
            raise ValueError("only INSUFFICIENT_CONTEXT may report missing context")
        object.__setattr__(self, "missing_context", missing)

        conflicts = tuple(
            sorted(
                _text(item, "constraint conflict") for item in self.constraint_conflicts
            )
        )
        if len(conflicts) != len(set(conflicts)):
            raise ValueError("constraint conflicts must be distinct")
        if self.reason is PlanningReason.CONFLICTING_CONSTRAINTS and not conflicts:
            raise ValueError("conflicting constraints require conflict details")
        if self.reason is not PlanningReason.CONFLICTING_CONSTRAINTS and conflicts:
            raise ValueError("constraint conflict details require the matching reason")
        object.__setattr__(self, "constraint_conflicts", conflicts)

    def to_trace(self) -> dict[str, object]:
        return {
            "planning_result_id": self.planning_result_id,
            "planning_request_id": self.planning_request_id,
            "goal_id": self.goal_id,
            "status": self.status.value,
            "reason": self.reason.value,
            "created_at": self.created_at.isoformat(),
            "plan": None if self.plan is None else self.plan.to_data(),
            "missing_context": [item.to_data() for item in self.missing_context],
            "constraint_conflicts": list(self.constraint_conflicts),
        }
