"""IRIS-owned evidence models; records do not imply current truth or permission."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

_NAME = re.compile(r"[a-z][a-z0-9_]*\Z")


def utc_time(value: datetime, name: str) -> datetime:
    """Require an aware timestamp and normalize it to UTC."""
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be a timezone-aware datetime")
    return value.astimezone(UTC)


def optional_time(value: datetime | None, name: str) -> datetime | None:
    return None if value is None else utc_time(value, name)


def vocabulary(value: str, name: str) -> str:
    if not isinstance(value, str) or not _NAME.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase identifier")
    return value


def identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a nonblank identifier")
    return value


class MemoryClass(StrEnum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


class MemoryKind(StrEnum):
    FACT = "fact"
    PREFERENCE = "preference"
    INTENTION = "intention"
    DECISION = "decision"
    GOAL = "goal"
    EVENT = "event"
    PROJECT_STATE = "project_state"
    SYSTEM_STATE = "system_state"
    FEEDBACK = "feedback"
    OBSERVATION = "observation"


class SourceType(StrEnum):
    USER_STATEMENT = "user_statement"
    OTHER_PERSON_STATEMENT = "other_person_statement"
    CAMERA_OBSERVATION = "camera_observation"
    SCREEN_OBSERVATION = "screen_observation"
    DEVICE_TELEMETRY = "device_telemetry"
    DOCUMENT = "document"
    EMAIL = "email"
    CALENDAR = "calendar"
    EXTERNAL_SERVICE = "external_service"
    SYSTEM_EVENT = "system_event"
    DERIVATION = "derivation"


class EpistemicStatus(StrEnum):
    DIRECT = "direct"
    OBSERVED = "observed"
    DERIVED = "derived"
    INFERRED = "inferred"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


class AcquisitionMode(StrEnum):
    EXPLICIT = "explicit"
    AMBIENT = "ambient"
    IMPORTED = "imported"
    DERIVED = "derived"
    INFERRED = "inferred"


class LifecycleStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    RETRACTED = "retracted"
    FORGOTTEN = "forgotten"


class ScopeKind(StrEnum):
    GLOBAL = "global"
    USER = "user"
    DEVICE = "device"
    PROJECT = "project"
    SESSION = "session"
    TASK = "task"


class Retention(StrEnum):
    TRANSIENT = "transient"
    SHORT = "short"
    SESSION = "session"
    LONG = "long"
    PERSISTENT = "persistent"


class RelationKind(StrEnum):
    SUPERSEDES = "supersedes"
    DERIVED_FROM = "derived_from"
    RESOLVES = "resolves"
    RELATED_TO = "related_to"


@dataclass(frozen=True, slots=True)
class MemoryScope:
    kind: ScopeKind
    identifier: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ScopeKind):
            raise TypeError("scope kind must be a ScopeKind")
        if self.kind is ScopeKind.GLOBAL and self.identifier is not None:
            raise ValueError("global scope cannot have an identifier")
        if self.kind is not ScopeKind.GLOBAL:
            if self.identifier is None:
                raise ValueError("non-global scope requires an identifier")
            identifier(self.identifier, "scope identifier")


@dataclass(frozen=True, slots=True)
class MemoryProvenance:
    source_type: str
    source_id: str | None = None
    actor: str | None = None

    def __post_init__(self) -> None:
        vocabulary(self.source_type, "source_type")
        for name in ("source_id", "actor"):
            value = getattr(self, name)
            if value is not None:
                identifier(value, name)


@dataclass(frozen=True, slots=True)
class MemoryRelation:
    """Directed edge: source_id --kind--> target_id."""

    source_id: str
    target_id: str
    kind: str

    def __post_init__(self) -> None:
        identifier(self.source_id, "source_id")
        identifier(self.target_id, "target_id")
        vocabulary(self.kind, "relation kind")
        if self.source_id == self.target_id:
            raise ValueError("a memory cannot relate to itself")


@dataclass(frozen=True, slots=True)
class MemoryCandidate:
    """Explicitly submitted evidence awaiting persistence."""

    memory_class: MemoryClass
    kind: str
    subject: str
    content: str
    provenance: MemoryProvenance
    epistemic: EpistemicStatus
    acquisition: AcquisitionMode
    scope: MemoryScope
    retention: Retention
    observed_at: datetime | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    source_reference: str | None = None
    artifact_reference: str | None = None

    def __post_init__(self) -> None:
        for name, enum_type in (
            ("memory_class", MemoryClass),
            ("epistemic", EpistemicStatus),
            ("acquisition", AcquisitionMode),
            ("retention", Retention),
        ):
            if not isinstance(getattr(self, name), enum_type):
                raise TypeError(f"{name} must be a {enum_type.__name__}")
        if not isinstance(self.provenance, MemoryProvenance):
            raise TypeError("provenance must be a MemoryProvenance")
        if not isinstance(self.scope, MemoryScope):
            raise TypeError("scope must be a MemoryScope")
        vocabulary(self.kind, "memory kind")
        identifier(self.subject, "subject")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("content must be nonblank text")
        for name in ("source_reference", "artifact_reference"):
            value = getattr(self, name)
            if value is not None:
                identifier(value, name)
        for name in ("observed_at", "valid_from", "valid_until"):
            object.__setattr__(self, name, optional_time(getattr(self, name), name))
        if self.valid_from is not None and self.valid_until is not None:
            if self.valid_from >= self.valid_until:
                raise ValueError("valid_from must precede valid_until")


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    id: str
    candidate: MemoryCandidate
    recorded_at: datetime
    lifecycle: LifecycleStatus = LifecycleStatus.ACTIVE
    relations: tuple[MemoryRelation, ...] = ()

    def __post_init__(self) -> None:
        identifier(self.id, "memory id")
        if not isinstance(self.candidate, MemoryCandidate):
            raise TypeError("candidate must be a MemoryCandidate")
        object.__setattr__(
            self, "recorded_at", utc_time(self.recorded_at, "recorded_at")
        )
        if not isinstance(self.lifecycle, LifecycleStatus):
            raise TypeError("lifecycle must be a LifecycleStatus")
        relations = tuple(self.relations)
        if any(
            not isinstance(edge, MemoryRelation) or edge.source_id != self.id
            for edge in relations
        ):
            raise ValueError("relations must originate from the record")
        object.__setattr__(self, "relations", relations)


@dataclass(frozen=True, slots=True)
class MemoryQuery:
    """Exact filters; observed interval is [start, end) in UTC."""

    id: str | None = None
    memory_class: MemoryClass | None = None
    kind: str | None = None
    subject: str | None = None
    scope: MemoryScope | None = None
    statuses: frozenset[LifecycleStatus] | None = field(
        default_factory=lambda: frozenset({LifecycleStatus.ACTIVE})
    )
    observed_from: datetime | None = None
    observed_until: datetime | None = None

    def __post_init__(self) -> None:
        if self.id is not None:
            identifier(self.id, "id")
        if self.kind is not None:
            vocabulary(self.kind, "kind")
        if self.subject is not None:
            identifier(self.subject, "subject")
        if self.memory_class is not None and not isinstance(
            self.memory_class, MemoryClass
        ):
            raise TypeError("memory_class must be a MemoryClass")
        if self.scope is not None and not isinstance(self.scope, MemoryScope):
            raise TypeError("scope must be a MemoryScope")
        if self.statuses is not None:
            statuses = frozenset(self.statuses)
            if any(not isinstance(status, LifecycleStatus) for status in statuses):
                raise TypeError("statuses must contain LifecycleStatus values")
            object.__setattr__(self, "statuses", statuses)
        for name in ("observed_from", "observed_until"):
            object.__setattr__(self, name, optional_time(getattr(self, name), name))
        if (
            self.observed_from
            and self.observed_until
            and self.observed_from >= self.observed_until
        ):
            raise ValueError("observed_from must precede observed_until")


class CurrentStatus(StrEnum):
    FOUND = "found"
    NONE = "none"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class MemoryResult:
    """Current stored evidence, including explicit uncertainty."""

    status: CurrentStatus
    record: MemoryRecord | None = None
    candidates: tuple[MemoryRecord, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, CurrentStatus):
            raise TypeError("status must be a CurrentStatus")
        if self.record is not None and not isinstance(self.record, MemoryRecord):
            raise TypeError("record must be a MemoryRecord or None")
        try:
            candidates = tuple(self.candidates)
        except TypeError as exc:
            raise TypeError("candidates must be a collection of records") from exc
        if any(not isinstance(candidate, MemoryRecord) for candidate in candidates):
            raise TypeError("candidates must contain MemoryRecord values")
        object.__setattr__(self, "candidates", candidates)
        if self.status is CurrentStatus.FOUND and (
            self.record is None or self.candidates != (self.record,)
        ):
            raise ValueError("FOUND requires exactly its selected record")
        if self.status is CurrentStatus.NONE and (
            self.record is not None or self.candidates
        ):
            raise ValueError("NONE cannot contain records")
        if self.status is CurrentStatus.AMBIGUOUS and (
            self.record is not None or not self.candidates
        ):
            raise ValueError("AMBIGUOUS requires candidates but no selection")
