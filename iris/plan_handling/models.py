"""Immutable models for declarative PlanStep handling preparation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from iris.intelligence.routing import IntelligenceNeed
from iris.orchestrator import HandlingKind, HandlingNeed, MemoryOperation
from iris.plan_handling.errors import PlanHandlingInvariantError
from iris.router import RouteTarget


def _identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a nonblank identifier")
    return value


def _optional_identifier(value: str | None, name: str) -> str | None:
    if value is not None:
        _identifier(value, name)
    return value


def _revision(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value


def _intelligence_need_data(need: IntelligenceNeed | None) -> object:
    if need is None:
        return None
    return {
        "required_capabilities": sorted(
            capability.value for capability in need.requirements.capabilities
        ),
        "required_location": (
            None
            if need.requirements.required_location is None
            else need.requirements.required_location.value
        ),
        "preferred_affinities": [
            affinity.value for affinity in need.preferences.preferred_affinities
        ],
        "metadata": {key: need.metadata[key] for key in sorted(need.metadata)},
    }


def _handling_need_data(need: HandlingNeed | None) -> object:
    if need is None:
        return None
    return {
        "need_id": need.need_id,
        "kind": need.kind.value,
        "system_route": (
            None if need.system_route is None else need.system_route.value
        ),
        "memory_operation": (
            None if need.memory_operation is None else need.memory_operation.value
        ),
        "capability_id": need.capability_id,
        "intelligence_need": _intelligence_need_data(need.intelligence_need),
        "blockers": [],
    }


class StepHandlingPreparationStatus(StrEnum):
    PREPARED = "prepared"
    HANDLING_UNSPECIFIED = "handling_unspecified"
    INSUFFICIENT_DETAIL = "insufficient_detail"


class StepHandlingPreparationReason(StrEnum):
    HANDLING_NOT_DECLARED = "handling_not_declared"
    CAPABILITY_KIND_SUFFICIENT = "capability_kind_sufficient"
    SPECIFICATION_COMPLETED_HANDLING = "specification_completed_handling"
    SYSTEM_ROUTE_REQUIRED = "system_route_required"
    MEMORY_OPERATION_REQUIRED = "memory_operation_required"
    INTELLIGENCE_NEED_REQUIRED = "intelligence_need_required"


@dataclass(frozen=True, slots=True)
class StepHandlingPreparationProvenance:
    """Traceable preparer origin without trust or authorization semantics."""

    preparer_id: str
    preparer_version: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.preparer_id, "preparer_id")
        _optional_identifier(self.preparer_version, "preparer_version")

    def to_data(self) -> dict[str, object]:
        return {
            "preparer_id": self.preparer_id,
            "preparer_version": self.preparer_version,
        }


@dataclass(frozen=True, slots=True)
class StepHandlingSpecification:
    """Complete explicit handling detail for exactly one selected PlanStep."""

    step_id: str
    kind: HandlingKind
    system_route: RouteTarget | None = None
    memory_operation: MemoryOperation | None = None
    capability_id: str | None = None
    intelligence_need: IntelligenceNeed | None = None

    def __post_init__(self) -> None:
        _identifier(self.step_id, "specification step_id")
        if not isinstance(self.kind, HandlingKind):
            raise TypeError("specification kind must be a HandlingKind")
        if self.kind is HandlingKind.CLARIFICATION:
            raise ValueError("clarification is not supported for PlanStep handling")
        if self.system_route is not None and not isinstance(
            self.system_route, RouteTarget
        ):
            raise TypeError("system_route must be a RouteTarget or None")
        if self.system_route is RouteTarget.UNKNOWN:
            raise ValueError("an unknown route cannot specify SYSTEM handling")
        if self.memory_operation is not None and not isinstance(
            self.memory_operation, MemoryOperation
        ):
            raise TypeError("memory_operation must be a MemoryOperation or None")
        if self.capability_id is not None:
            _identifier(self.capability_id, "specification capability_id")
        if self.intelligence_need is not None and not isinstance(
            self.intelligence_need, IntelligenceNeed
        ):
            raise TypeError("intelligence_need must be an IntelligenceNeed or None")

        values = {
            "system_route": self.system_route,
            "memory_operation": self.memory_operation,
            "capability_id": self.capability_id,
            "intelligence_need": self.intelligence_need,
        }
        allowed = {
            HandlingKind.SYSTEM: ("system_route",),
            HandlingKind.MEMORY: ("memory_operation",),
            HandlingKind.CAPABILITY: ("capability_id",),
            HandlingKind.INTELLIGENCE: ("intelligence_need",),
        }[self.kind]
        if any(
            value is not None and field_name not in allowed
            for field_name, value in values.items()
        ):
            raise ValueError(
                "specification contains detail for another handling subsystem"
            )
        required = {
            HandlingKind.SYSTEM: ("system_route", self.system_route),
            HandlingKind.MEMORY: ("memory_operation", self.memory_operation),
            HandlingKind.INTELLIGENCE: (
                "intelligence_need",
                self.intelligence_need,
            ),
        }.get(self.kind)
        if required is not None and required[1] is None:
            raise ValueError(f"{self.kind.value} specification requires {required[0]}")

    def to_data(self) -> dict[str, object]:
        return {
            "step_id": self.step_id,
            "kind": self.kind.value,
            "system_route": (
                None if self.system_route is None else self.system_route.value
            ),
            "memory_operation": (
                None if self.memory_operation is None else self.memory_operation.value
            ),
            "capability_id": self.capability_id,
            "intelligence_need": _intelligence_need_data(self.intelligence_need),
        }


@dataclass(frozen=True, slots=True)
class StepHandlingPreparationResult:
    """One preparation outcome tied to one exact PlanRun revision and step."""

    plan_id: str
    run_id: str
    observed_revision: int
    step_id: str
    status: StepHandlingPreparationStatus
    reason: StepHandlingPreparationReason
    provenance: StepHandlingPreparationProvenance
    handling_kind: HandlingKind | None = None
    handling_need: HandlingNeed | None = None

    def __post_init__(self) -> None:
        _identifier(self.plan_id, "preparation plan_id")
        _identifier(self.run_id, "preparation run_id")
        _revision(self.observed_revision, "preparation observed_revision")
        _identifier(self.step_id, "preparation step_id")
        if not isinstance(self.status, StepHandlingPreparationStatus):
            raise TypeError("status must be a StepHandlingPreparationStatus")
        if not isinstance(self.reason, StepHandlingPreparationReason):
            raise TypeError("reason must be a StepHandlingPreparationReason")
        if not isinstance(self.provenance, StepHandlingPreparationProvenance):
            raise TypeError("provenance must be a StepHandlingPreparationProvenance")
        if self.handling_kind is not None and not isinstance(
            self.handling_kind, HandlingKind
        ):
            raise TypeError("handling_kind must be a HandlingKind or None")
        if self.handling_need is not None and not isinstance(
            self.handling_need, HandlingNeed
        ):
            raise TypeError("handling_need must be a HandlingNeed or None")
        self._validate_shape()

    def _validate_shape(self) -> None:
        if self.status is StepHandlingPreparationStatus.HANDLING_UNSPECIFIED:
            if self.reason is not StepHandlingPreparationReason.HANDLING_NOT_DECLARED:
                raise PlanHandlingInvariantError(
                    "HANDLING_UNSPECIFIED requires HANDLING_NOT_DECLARED"
                )
            if self.handling_kind is not None or self.handling_need is not None:
                raise PlanHandlingInvariantError(
                    "HANDLING_UNSPECIFIED cannot contain handling data"
                )
            return

        if self.handling_kind is None:
            raise PlanHandlingInvariantError(
                f"{self.status.value} requires handling_kind"
            )
        if self.handling_kind is HandlingKind.CLARIFICATION:
            raise PlanHandlingInvariantError(
                "clarification is not valid PlanStep handling"
            )

        if self.status is StepHandlingPreparationStatus.INSUFFICIENT_DETAIL:
            if self.handling_need is not None:
                raise PlanHandlingInvariantError(
                    "INSUFFICIENT_DETAIL cannot contain HandlingNeed"
                )
            expected_reason = {
                HandlingKind.SYSTEM: StepHandlingPreparationReason.SYSTEM_ROUTE_REQUIRED,
                HandlingKind.MEMORY: (
                    StepHandlingPreparationReason.MEMORY_OPERATION_REQUIRED
                ),
                HandlingKind.INTELLIGENCE: (
                    StepHandlingPreparationReason.INTELLIGENCE_NEED_REQUIRED
                ),
            }.get(self.handling_kind)
            if expected_reason is None or self.reason is not expected_reason:
                raise PlanHandlingInvariantError(
                    "INSUFFICIENT_DETAIL reason is incompatible with handling_kind"
                )
            return

        if self.handling_need is None:
            raise PlanHandlingInvariantError("PREPARED requires HandlingNeed")
        if self.handling_need.kind is not self.handling_kind:
            raise PlanHandlingInvariantError(
                "HandlingNeed kind must match preparation handling_kind"
            )
        if self.handling_need.blockers:
            raise PlanHandlingInvariantError(
                "PlanStep preparation cannot fabricate Context blockers"
            )
        if self.reason is StepHandlingPreparationReason.CAPABILITY_KIND_SUFFICIENT:
            if self.handling_kind is not HandlingKind.CAPABILITY:
                raise PlanHandlingInvariantError(
                    "CAPABILITY_KIND_SUFFICIENT requires CAPABILITY handling"
                )
        elif self.reason is not (
            StepHandlingPreparationReason.SPECIFICATION_COMPLETED_HANDLING
        ):
            raise PlanHandlingInvariantError("PREPARED has an incompatible reason")

    def to_data(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "run_id": self.run_id,
            "observed_revision": self.observed_revision,
            "step_id": self.step_id,
            "status": self.status.value,
            "reason": self.reason.value,
            "provenance": self.provenance.to_data(),
            "handling_kind": (
                None if self.handling_kind is None else self.handling_kind.value
            ),
            "handling_need": _handling_need_data(self.handling_need),
        }
