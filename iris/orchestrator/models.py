"""Immutable, traceable models for one orchestration decision."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from iris.context import ContextSnapshot, UncertaintyReason
from iris.core import Request
from iris.intelligence.routing import IntelligenceNeed
from iris.memory.models import MemoryScope, identifier, utc_time, vocabulary
from iris.orchestrator.errors import RequestContextMismatchError
from iris.router import RouteTarget


class HandlingKind(StrEnum):
    SYSTEM = "system"
    MEMORY = "memory"
    CAPABILITY = "capability"
    INTELLIGENCE = "intelligence"
    CLARIFICATION = "clarification"


class MemoryOperation(StrEnum):
    RECALL = "recall"
    QUERY = "query"
    STORE = "store"
    FORGET = "forget"
    SUPERSEDE = "supersede"


class ContextBlockerKind(StrEnum):
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    CONFLICTED = "conflicted"


class OrchestrationTarget(StrEnum):
    SYSTEM = "system"
    MEMORY = "memory"
    CAPABILITY = "capability"
    INTELLIGENCE = "intelligence"
    CLARIFY = "clarify"
    UNSATISFIED = "unsatisfied"


class OrchestrationReason(StrEnum):
    DETERMINISTIC_SYSTEM_REQUEST = "deterministic_system_request"
    EXPLICIT_MEMORY_OPERATION = "explicit_memory_operation"
    EXPLICIT_CAPABILITY_REQUEST = "explicit_capability_request"
    INTELLIGENCE_REQUIRED = "intelligence_required"
    CONTEXT_AMBIGUOUS = "context_ambiguous"
    CONTEXT_CONFLICTED = "context_conflicted"
    MISSING_REQUIRED_INFORMATION = "missing_required_information"
    NO_ADMISSIBLE_HANDLER = "no_admissible_handler"
    COMPOSITE_HANDLING_REQUIRED = "composite_handling_required"


@dataclass(frozen=True, slots=True)
class ContextBlocker:
    """Explicitly marks one Context issue as relevant to a handling need."""

    kind: str
    key: str
    scope: MemoryScope
    issue: ContextBlockerKind
    candidate_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        vocabulary(self.kind, "blocker kind")
        vocabulary(self.key, "blocker key")
        if not isinstance(self.scope, MemoryScope):
            raise TypeError("scope must be a MemoryScope")
        if not isinstance(self.issue, ContextBlockerKind):
            raise TypeError("issue must be a ContextBlockerKind")
        provided_ids = tuple(self.candidate_ids)
        for candidate_id in provided_ids:
            identifier(candidate_id, "blocker candidate ID")
        ids = tuple(sorted(provided_ids))
        if len(ids) != len(set(ids)):
            raise ValueError("blocker candidate IDs must be distinct")
        if (
            self.issue
            in (
                ContextBlockerKind.AMBIGUOUS,
                ContextBlockerKind.CONFLICTED,
            )
            and len(ids) < 2
        ):
            raise ValueError("ambiguous/conflicted blockers require two candidates")
        object.__setattr__(self, "candidate_ids", ids)


@dataclass(frozen=True, slots=True)
class HandlingNeed:
    """One explicit request for a subsystem, above subsystem-specific routing."""

    need_id: str
    kind: HandlingKind
    system_route: RouteTarget | None = None
    memory_operation: MemoryOperation | None = None
    capability_id: str | None = None
    intelligence_need: IntelligenceNeed | None = None
    blockers: tuple[ContextBlocker, ...] = ()

    def __post_init__(self) -> None:
        identifier(self.need_id, "need_id")
        if not isinstance(self.kind, HandlingKind):
            raise TypeError("kind must be a HandlingKind")
        provided_blockers = tuple(self.blockers)
        if any(not isinstance(item, ContextBlocker) for item in provided_blockers):
            raise TypeError("blockers must contain ContextBlocker values")
        blockers = tuple(
            sorted(
                provided_blockers,
                key=lambda item: (
                    item.issue.value,
                    item.scope.kind.value,
                    item.scope.identifier or "",
                    item.kind,
                    item.key,
                    item.candidate_ids,
                ),
            )
        )
        if len(blockers) != len(set(blockers)):
            raise ValueError("blockers must not contain duplicates")
        object.__setattr__(self, "blockers", blockers)

        populated = {
            HandlingKind.SYSTEM: self.system_route is not None,
            HandlingKind.MEMORY: self.memory_operation is not None,
            HandlingKind.INTELLIGENCE: self.intelligence_need is not None,
        }
        if self.kind in populated and not populated[self.kind]:
            required = {
                HandlingKind.SYSTEM: "system_route",
                HandlingKind.MEMORY: "memory_operation",
                HandlingKind.INTELLIGENCE: "intelligence_need",
            }[self.kind]
            raise ValueError(f"{self.kind.value} handling requires {required}")
        if self.kind is HandlingKind.CLARIFICATION and not blockers:
            raise ValueError("clarification handling requires a context blocker")
        if self.system_route is not None and not isinstance(
            self.system_route, RouteTarget
        ):
            raise TypeError("system_route must be a RouteTarget or None")
        if self.system_route is RouteTarget.UNKNOWN:
            raise ValueError("an unknown deterministic route is not system handling")
        if self.memory_operation is not None and not isinstance(
            self.memory_operation, MemoryOperation
        ):
            raise TypeError("memory_operation must be a MemoryOperation or None")
        if self.capability_id is not None:
            identifier(self.capability_id, "capability_id")
        if self.intelligence_need is not None and not isinstance(
            self.intelligence_need, IntelligenceNeed
        ):
            raise TypeError("intelligence_need must be an IntelligenceNeed or None")

        allowed = {
            HandlingKind.SYSTEM: ("system_route",),
            HandlingKind.MEMORY: ("memory_operation",),
            HandlingKind.CAPABILITY: ("capability_id",),
            HandlingKind.INTELLIGENCE: ("intelligence_need",),
            HandlingKind.CLARIFICATION: (),
        }[self.kind]
        values = {
            "system_route": self.system_route,
            "memory_operation": self.memory_operation,
            "capability_id": self.capability_id,
            "intelligence_need": self.intelligence_need,
        }
        if any(
            value is not None and name not in allowed for name, value in values.items()
        ):
            raise ValueError(
                "handling need contains a requirement for another subsystem"
            )


@dataclass(frozen=True, slots=True)
class HandlerAvailability:
    """Caller-supplied availability; no discovery occurs during orchestration."""

    system: bool = False
    memory: bool = False
    capability: bool = False
    intelligence: bool = False
    capability_ids: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        for name in ("system", "memory", "capability", "intelligence"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} availability must be bool")
        if isinstance(self.capability_ids, (str, bytes)):
            raise TypeError("capability_ids must be a collection of identifiers")
        ids = frozenset(self.capability_ids)
        for capability_id in ids:
            identifier(capability_id, "available capability ID")
        if ids and not self.capability:
            raise ValueError("capability IDs require capability handling availability")
        object.__setattr__(self, "capability_ids", ids)

    def supports(self, need: HandlingNeed) -> bool:
        """Return whether this declaration admits the requested handler."""

        if not isinstance(need, HandlingNeed):
            raise TypeError("need must be a HandlingNeed")
        if need.kind is HandlingKind.SYSTEM:
            return self.system
        if need.kind is HandlingKind.MEMORY:
            return self.memory
        if need.kind is HandlingKind.CAPABILITY:
            return self.capability and (
                need.capability_id is None or need.capability_id in self.capability_ids
            )
        if need.kind is HandlingKind.INTELLIGENCE:
            return self.intelligence
        return True


def _blocker_matches_context(blocker: ContextBlocker, context: ContextSnapshot) -> bool:
    if blocker.issue is ContextBlockerKind.CONFLICTED:
        return any(
            (item.kind, item.key, item.scope, tuple(sorted(item.candidate_ids)))
            == (blocker.kind, blocker.key, blocker.scope, blocker.candidate_ids)
            for item in context.conflicts
        )
    expected = (
        {UncertaintyReason.MULTIPLE_PLAUSIBLE}
        if blocker.issue is ContextBlockerKind.AMBIGUOUS
        else {UncertaintyReason.MISSING, UncertaintyReason.BUDGET_EXCLUDED}
    )
    return any(
        (item.kind, item.key, item.scope, tuple(sorted(item.candidate_ids)))
        == (blocker.kind, blocker.key, blocker.scope, blocker.candidate_ids)
        and item.reason in expected
        for item in context.uncertainties
    )


@dataclass(frozen=True, slots=True)
class OrchestrationInput:
    request: Request
    context: ContextSnapshot
    needs: tuple[HandlingNeed, ...]
    availability: HandlerAvailability

    def __post_init__(self) -> None:
        if not isinstance(self.request, Request):
            raise TypeError("request must be a Request")
        if not isinstance(self.context, ContextSnapshot):
            raise TypeError("context must be a ContextSnapshot")
        if self.request.request_id != self.context.request_id:
            raise RequestContextMismatchError(
                "request and context snapshot identifiers do not match"
            )
        if not isinstance(self.needs, tuple) or any(
            not isinstance(need, HandlingNeed) for need in self.needs
        ):
            raise TypeError("needs must be a tuple of HandlingNeed")
        ids = tuple(need.need_id for need in self.needs)
        if len(ids) != len(set(ids)):
            raise ValueError("need identifiers must be unique")
        if not isinstance(self.availability, HandlerAvailability):
            raise TypeError("availability must be HandlerAvailability")
        for need in self.needs:
            if any(
                not _blocker_matches_context(blocker, self.context)
                for blocker in need.blockers
            ):
                raise ValueError("context blocker does not exist in the snapshot")


@dataclass(frozen=True, slots=True)
class OrchestrationSelection:
    """Semantic policy output before decision identity and time are assigned."""

    target: OrchestrationTarget
    reason: OrchestrationReason
    need_ids: tuple[str, ...]
    requirement: HandlingNeed | None = None
    context_references: tuple[ContextBlocker, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.target, OrchestrationTarget):
            raise TypeError("target must be an OrchestrationTarget")
        if not isinstance(self.reason, OrchestrationReason):
            raise TypeError("reason must be an OrchestrationReason")
        ids = tuple(self.need_ids)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValueError("selection need_ids must be distinct and sorted")
        for need_id in ids:
            identifier(need_id, "selection need ID")
        object.__setattr__(self, "need_ids", ids)
        if self.requirement is not None and not isinstance(
            self.requirement, HandlingNeed
        ):
            raise TypeError("requirement must be a HandlingNeed or None")
        references = tuple(self.context_references)
        if any(not isinstance(item, ContextBlocker) for item in references):
            raise TypeError("context_references must contain ContextBlocker values")
        object.__setattr__(self, "context_references", references)


_REASONS_BY_TARGET = {
    OrchestrationTarget.SYSTEM: {OrchestrationReason.DETERMINISTIC_SYSTEM_REQUEST},
    OrchestrationTarget.MEMORY: {OrchestrationReason.EXPLICIT_MEMORY_OPERATION},
    OrchestrationTarget.CAPABILITY: {OrchestrationReason.EXPLICIT_CAPABILITY_REQUEST},
    OrchestrationTarget.INTELLIGENCE: {OrchestrationReason.INTELLIGENCE_REQUIRED},
    OrchestrationTarget.CLARIFY: {
        OrchestrationReason.CONTEXT_AMBIGUOUS,
        OrchestrationReason.CONTEXT_CONFLICTED,
        OrchestrationReason.MISSING_REQUIRED_INFORMATION,
    },
    OrchestrationTarget.UNSATISFIED: {
        OrchestrationReason.NO_ADMISSIBLE_HANDLER,
        OrchestrationReason.COMPOSITE_HANDLING_REQUIRED,
    },
}


@dataclass(frozen=True, slots=True)
class OrchestrationDecision:
    """One observable decision. It does not execute the selected subsystem."""

    decision_id: str
    request_id: str
    context_snapshot_id: str
    target: OrchestrationTarget
    reason: OrchestrationReason
    created_at: datetime
    need_ids: tuple[str, ...]
    requirement: HandlingNeed | None = None
    context_references: tuple[ContextBlocker, ...] = ()

    def __post_init__(self) -> None:
        for value, name in (
            (self.decision_id, "decision_id"),
            (self.request_id, "request_id"),
            (self.context_snapshot_id, "context_snapshot_id"),
        ):
            identifier(value, name)
        if not isinstance(self.target, OrchestrationTarget):
            raise TypeError("target must be an OrchestrationTarget")
        if not isinstance(self.reason, OrchestrationReason):
            raise TypeError("reason must be an OrchestrationReason")
        if self.reason not in _REASONS_BY_TARGET[self.target]:
            raise ValueError("reason is incompatible with orchestration target")
        object.__setattr__(self, "created_at", utc_time(self.created_at, "created_at"))
        ids = tuple(self.need_ids)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValueError("need_ids must be distinct and sorted")
        for need_id in ids:
            identifier(need_id, "decision need ID")
        object.__setattr__(self, "need_ids", ids)
        if self.requirement is not None and not isinstance(
            self.requirement, HandlingNeed
        ):
            raise TypeError("requirement must be a HandlingNeed or None")
        if self.requirement is not None and self.requirement.need_id not in ids:
            raise ValueError("requirement must belong to the referenced needs")
        references = tuple(self.context_references)
        if any(not isinstance(item, ContextBlocker) for item in references):
            raise TypeError("context_references must contain ContextBlocker values")
        object.__setattr__(self, "context_references", references)
        if self.target is OrchestrationTarget.CLARIFY and not references:
            raise ValueError("clarification decisions require context references")
        if self.target is not OrchestrationTarget.CLARIFY and references:
            raise ValueError("only clarification decisions may contain blockers")
        expected_kind = {
            OrchestrationTarget.SYSTEM: HandlingKind.SYSTEM,
            OrchestrationTarget.MEMORY: HandlingKind.MEMORY,
            OrchestrationTarget.CAPABILITY: HandlingKind.CAPABILITY,
            OrchestrationTarget.INTELLIGENCE: HandlingKind.INTELLIGENCE,
        }.get(self.target)
        if expected_kind is not None and (
            self.requirement is None or self.requirement.kind is not expected_kind
        ):
            raise ValueError("selected target requires its matching handling need")

    def to_trace(self) -> dict[str, object]:
        """Return a JSON-compatible observable trace without private reasoning."""

        requirement: dict[str, object] | None = None
        if self.requirement is not None:
            need = self.requirement
            requirement = {
                "need_id": need.need_id,
                "kind": need.kind.value,
                "system_route": (
                    None if need.system_route is None else need.system_route.value
                ),
                "memory_operation": (
                    None
                    if need.memory_operation is None
                    else need.memory_operation.value
                ),
                "capability_id": need.capability_id,
            }
            if need.intelligence_need is not None:
                intelligence = need.intelligence_need
                requirement["intelligence_need"] = {
                    "required_capabilities": sorted(
                        item.value for item in intelligence.requirements.capabilities
                    ),
                    "required_location": (
                        None
                        if intelligence.requirements.required_location is None
                        else intelligence.requirements.required_location.value
                    ),
                    "preferred_affinities": [
                        item.value
                        for item in intelligence.preferences.preferred_affinities
                    ],
                }
        return {
            "decision_id": self.decision_id,
            "request_id": self.request_id,
            "context_snapshot_id": self.context_snapshot_id,
            "target": self.target.value,
            "reason": self.reason.value,
            "created_at": self.created_at.isoformat(),
            "need_ids": list(self.need_ids),
            "requirement": requirement,
            "context_references": [
                {
                    "kind": item.kind,
                    "key": item.key,
                    "scope": {
                        "kind": item.scope.kind.value,
                        "identifier": item.scope.identifier,
                    },
                    "issue": item.issue.value,
                    "candidate_ids": list(item.candidate_ids),
                }
                for item in self.context_references
            ],
        }
