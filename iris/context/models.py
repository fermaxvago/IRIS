"""Ephemeral, evidence-backed context for one IRIS work subject."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from iris.context.errors import RequestEvidenceSubjectMismatchError
from iris.memory.models import (
    EpistemicStatus,
    MemoryScope,
    identifier,
    optional_time,
    utc_time,
    vocabulary,
)
from iris.work_identity.models import (
    RequestWorkReference,
    WorkSubject,
    WorkSubjectKind,
)


class ContextKind(StrEnum):
    USER = "user"
    SESSION = "session"
    PROJECT = "project"
    TASK = "task"
    DEVICE = "device"
    ACTIVITY = "activity"
    ENVIRONMENT = "environment"
    RESOURCE = "resource"
    INTERACTION = "interaction"
    TEMPORAL = "temporal"
    OTHER = "other"


class EvidenceSource(StrEnum):
    REQUEST = "request"
    MEMORY = "memory"
    SESSION = "session"
    SYSTEM = "system"
    RESOURCE = "resource"
    ENVIRONMENT = "environment"
    CALLER = "caller"


class Relevance(StrEnum):
    REQUIRED = "required"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class Freshness(StrEnum):
    CURRENT = "current"
    RECENT = "recent"
    STALE = "stale"
    UNKNOWN = "unknown"


class ResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    CONFLICTED = "conflicted"


class UncertaintyReason(StrEnum):
    MISSING = "missing"
    MULTIPLE_PLAUSIBLE = "multiple_plausible"
    BUDGET_EXCLUDED = "budget_excluded"


class ConflictReason(StrEnum):
    INCOMPATIBLE_VALUES = "incompatible_values"


ContextValue = str | int | float | bool


def _validate_value(value: object) -> None:
    if type(value) not in (str, int, float, bool):
        raise TypeError("context value must be a JSON scalar (not null)")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("context value must be finite")


@dataclass(frozen=True, slots=True)
class ContextEvidence:
    """Reference to evidence; epistemic status is not an authorization grant."""

    source: EvidenceSource
    reference: str
    epistemic: EpistemicStatus = EpistemicStatus.UNKNOWN

    def __post_init__(self) -> None:
        if not isinstance(self.source, EvidenceSource):
            raise TypeError("source must be an EvidenceSource")
        identifier(self.reference, "evidence reference")
        if not isinstance(self.epistemic, EpistemicStatus):
            raise TypeError("epistemic must be an EpistemicStatus")


@dataclass(frozen=True, slots=True)
class ContextCandidate:
    """Available evidence; inclusion requires explicit eligibility and selection."""

    candidate_id: str
    kind: str
    key: str
    value: ContextValue
    evidence: ContextEvidence
    scope: MemoryScope
    relevance: Relevance
    freshness: Freshness
    observed_at: datetime | None = None
    eligible: bool = True

    def __post_init__(self) -> None:
        identifier(self.candidate_id, "candidate_id")
        vocabulary(self.kind, "context kind")
        vocabulary(self.key, "context key")
        _validate_value(self.value)
        if not isinstance(self.evidence, ContextEvidence):
            raise TypeError("evidence must be ContextEvidence")
        if not isinstance(self.scope, MemoryScope):
            raise TypeError("scope must be MemoryScope")
        if not isinstance(self.relevance, Relevance):
            raise TypeError("relevance must be Relevance")
        if not isinstance(self.freshness, Freshness):
            raise TypeError("freshness must be Freshness")
        if not isinstance(self.eligible, bool):
            raise TypeError("eligible must be bool")
        object.__setattr__(
            self, "observed_at", optional_time(self.observed_at, "observed_at")
        )

    def to_item(self) -> ContextItem:
        """Preserve the exact evidence and selection metadata."""
        return ContextItem(
            candidate_id=self.candidate_id,
            kind=self.kind,
            key=self.key,
            value=self.value,
            evidence=self.evidence,
            scope=self.scope,
            relevance=self.relevance,
            freshness=self.freshness,
            observed_at=self.observed_at,
        )


@dataclass(frozen=True, slots=True)
class ContextItem:
    """One selected, traceable claim in the current subject context."""

    candidate_id: str
    kind: str
    key: str
    value: ContextValue
    evidence: ContextEvidence
    scope: MemoryScope
    relevance: Relevance
    freshness: Freshness
    observed_at: datetime | None = None

    def __post_init__(self) -> None:
        # The same domain validation applies before and after selection.
        ContextCandidate(
            self.candidate_id,
            self.kind,
            self.key,
            self.value,
            self.evidence,
            self.scope,
            self.relevance,
            self.freshness,
            self.observed_at,
        )
        object.__setattr__(
            self, "observed_at", optional_time(self.observed_at, "observed_at")
        )


@dataclass(frozen=True, slots=True)
class ContextBudget:
    max_items: int

    def __post_init__(self) -> None:
        if isinstance(self.max_items, bool) or not isinstance(self.max_items, int):
            raise TypeError("max_items must be an integer")
        if self.max_items < 0:
            raise ValueError("max_items must be nonnegative")


@dataclass(frozen=True, slots=True)
class ContextConflict:
    kind: str
    key: str
    scope: MemoryScope
    candidate_ids: tuple[str, ...]
    evidence: tuple[ContextEvidence, ...]
    reason: ConflictReason = ConflictReason.INCOMPATIBLE_VALUES

    def __post_init__(self) -> None:
        vocabulary(self.kind, "conflict kind")
        vocabulary(self.key, "conflict key")
        if not isinstance(self.scope, MemoryScope):
            raise TypeError("scope must be MemoryScope")
        if not isinstance(self.reason, ConflictReason):
            raise TypeError("reason must be ConflictReason")
        ids = tuple(self.candidate_ids)
        if len(ids) < 2 or len(ids) != len(set(ids)):
            raise ValueError("conflict requires at least two distinct candidates")
        for candidate_id in ids:
            identifier(candidate_id, "conflict candidate ID")
        evidence = tuple(self.evidence)
        if len(evidence) != len(ids) or any(
            not isinstance(reference, ContextEvidence) for reference in evidence
        ):
            raise ValueError("conflict requires one evidence reference per candidate")
        object.__setattr__(self, "candidate_ids", ids)
        object.__setattr__(self, "evidence", evidence)


@dataclass(frozen=True, slots=True)
class ContextUncertainty:
    kind: str
    key: str
    scope: MemoryScope
    reason: UncertaintyReason
    candidate_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        vocabulary(self.kind, "uncertainty kind")
        vocabulary(self.key, "uncertainty key")
        if not isinstance(self.scope, MemoryScope):
            raise TypeError("scope must be MemoryScope")
        if not isinstance(self.reason, UncertaintyReason):
            raise TypeError("reason must be UncertaintyReason")
        ids = tuple(self.candidate_ids)
        if len(ids) != len(set(ids)):
            raise ValueError("uncertainty candidates must be distinct")
        for candidate_id in ids:
            identifier(candidate_id, "uncertainty candidate ID")
        if self.reason is UncertaintyReason.MULTIPLE_PLAUSIBLE and len(ids) < 2:
            raise ValueError("multiple plausible candidates requires at least two IDs")
        if self.reason is UncertaintyReason.BUDGET_EXCLUDED and not ids:
            raise ValueError("budget uncertainty requires an excluded ID")
        object.__setattr__(self, "candidate_ids", ids)


@dataclass(frozen=True, slots=True)
class ContextSnapshot:
    """Subject-scoped result; the engine never stores this in Memory."""

    snapshot_id: str
    subject: WorkSubject
    created_at: datetime
    budget: ContextBudget
    items: tuple[ContextItem, ...]
    status: ResolutionStatus
    uncertainties: tuple[ContextUncertainty, ...] = ()
    conflicts: tuple[ContextConflict, ...] = ()
    budget_excluded_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        identifier(self.snapshot_id, "snapshot_id")
        if not isinstance(self.subject, WorkSubject):
            raise TypeError("subject must be a WorkSubject")
        object.__setattr__(self, "created_at", utc_time(self.created_at, "created_at"))
        if not isinstance(self.budget, ContextBudget):
            raise TypeError("budget must be ContextBudget")
        if not isinstance(self.status, ResolutionStatus):
            raise TypeError("status must be ResolutionStatus")
        for name, item_type in (
            ("items", ContextItem),
            ("uncertainties", ContextUncertainty),
            ("conflicts", ContextConflict),
        ):
            values = tuple(getattr(self, name))
            if any(not isinstance(value, item_type) for value in values):
                raise TypeError(f"{name} must contain {item_type.__name__} values")
            object.__setattr__(self, name, values)
        _validate_context_evidence_for_subject(
            self.subject,
            tuple(item.evidence for item in self.items)
            + tuple(
                evidence
                for conflict in self.conflicts
                for evidence in conflict.evidence
            ),
        )
        if len(self.items) > self.budget.max_items:
            raise ValueError("snapshot exceeds context budget")
        keys = [(item.kind, item.key, item.scope) for item in self.items]
        if len(keys) != len(set(keys)):
            raise ValueError(
                "snapshot cannot select multiple values for one scoped key"
            )
        if any(
            (conflict.kind, conflict.key, conflict.scope) in keys
            for conflict in self.conflicts
        ):
            raise ValueError("conflicted scoped keys cannot also be selected")
        if self.status is ResolutionStatus.CONFLICTED and not self.conflicts:
            raise ValueError("CONFLICTED requires a conflict")
        if self.status is ResolutionStatus.AMBIGUOUS and not any(
            uncertainty.reason is UncertaintyReason.MULTIPLE_PLAUSIBLE
            for uncertainty in self.uncertainties
        ):
            raise ValueError("AMBIGUOUS requires multiple plausible candidates")
        if self.status is ResolutionStatus.PARTIAL and not self.uncertainties:
            raise ValueError("PARTIAL requires known missing information")
        if self.status is not ResolutionStatus.CONFLICTED and self.conflicts:
            raise ValueError("conflicts require CONFLICTED status")
        if self.status is ResolutionStatus.RESOLVED and self.uncertainties:
            raise ValueError("RESOLVED cannot carry known uncertainty")
        excluded = tuple(self.budget_excluded_ids)
        if len(excluded) != len(set(excluded)):
            raise ValueError("budget excluded IDs must be distinct")
        for candidate_id in excluded:
            identifier(candidate_id, "excluded candidate ID")
        object.__setattr__(self, "budget_excluded_ids", excluded)

    @property
    def subject_id(self) -> str:
        """Return the canonical owner identity without storing it twice."""

        return self.subject.subject_id

    @property
    def request_id(self) -> str | None:
        """Legacy owner identity, applicable only to REQUEST subjects."""

        if self.subject.kind is WorkSubjectKind.REQUEST and isinstance(
            self.subject.reference, RequestWorkReference
        ):
            return self.subject.reference.request_id
        return None

    def to_data(self) -> dict[str, object]:
        """Serialize the snapshot with WorkSubject as its only owner field."""

        def evidence_data(evidence: ContextEvidence) -> dict[str, object]:
            return {
                "source": evidence.source.value,
                "reference": evidence.reference,
                "epistemic": evidence.epistemic.value,
            }

        def scope_data(scope: MemoryScope) -> dict[str, object]:
            return {
                "kind": scope.kind.value,
                "identifier": scope.identifier,
            }

        return {
            "snapshot_id": self.snapshot_id,
            "subject": self.subject.to_data(),
            "created_at": self.created_at.isoformat(),
            "budget": {"max_items": self.budget.max_items},
            "items": [
                {
                    "candidate_id": item.candidate_id,
                    "kind": item.kind,
                    "key": item.key,
                    "value": item.value,
                    "evidence": evidence_data(item.evidence),
                    "scope": scope_data(item.scope),
                    "relevance": item.relevance.value,
                    "freshness": item.freshness.value,
                    "observed_at": (
                        None
                        if item.observed_at is None
                        else item.observed_at.isoformat()
                    ),
                }
                for item in self.items
            ],
            "status": self.status.value,
            "uncertainties": [
                {
                    "kind": uncertainty.kind,
                    "key": uncertainty.key,
                    "scope": scope_data(uncertainty.scope),
                    "reason": uncertainty.reason.value,
                    "candidate_ids": list(uncertainty.candidate_ids),
                }
                for uncertainty in self.uncertainties
            ],
            "conflicts": [
                {
                    "kind": conflict.kind,
                    "key": conflict.key,
                    "scope": scope_data(conflict.scope),
                    "candidate_ids": list(conflict.candidate_ids),
                    "evidence": [
                        evidence_data(evidence) for evidence in conflict.evidence
                    ],
                    "reason": conflict.reason.value,
                }
                for conflict in self.conflicts
            ],
            "budget_excluded_ids": list(self.budget_excluded_ids),
        }


def _known_request_reference(subject: WorkSubject) -> str | None:
    """Return the structurally known root Request, if one is available."""

    if subject.kind is WorkSubjectKind.REQUEST:
        if not isinstance(subject.reference, RequestWorkReference):
            raise TypeError("REQUEST subject must use RequestWorkReference")
        return subject.reference.request_id
    if subject.origin is not None and subject.origin.source_type == "request":
        return subject.origin.source_id
    return None


def _validate_context_evidence_for_subject(
    subject: WorkSubject,
    evidence_values: tuple[ContextEvidence, ...],
) -> None:
    """Validate causal compatibility without changing epistemic status."""

    if not isinstance(subject, WorkSubject):
        raise TypeError("subject must be a WorkSubject")
    known_request = _known_request_reference(subject)
    for evidence in evidence_values:
        if not isinstance(evidence, ContextEvidence):
            raise TypeError("evidence_values must contain ContextEvidence")
        if evidence.source is not EvidenceSource.REQUEST:
            continue
        if known_request is None or evidence.reference != known_request:
            raise RequestEvidenceSubjectMismatchError(
                "REQUEST evidence does not match a known Request for the subject"
            )
