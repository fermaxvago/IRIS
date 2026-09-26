"""Immutable, serializable models for PlanRun state and explicit updates."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import ClassVar, TypeAlias, cast

from iris.plan_runs.errors import (
    DuplicateRunIdentityError,
    ForeignEvidenceError,
    PlanRunInvariantError,
)

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | tuple["JsonValue", ...] | Mapping[str, "JsonValue"]

_VOCABULARY = re.compile(r"[a-z][a-z0-9_]*\Z")


def utc_time(value: datetime, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be a timezone-aware datetime")
    return value.astimezone(UTC)


def identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a nonblank identifier")
    return value


def vocabulary(value: str, name: str) -> str:
    if not isinstance(value, str) or not _VOCABULARY.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase identifier")
    return value


def _text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonblank text")
    return value.strip()


def _freeze_json(value: object, *, field_name: str) -> JsonValue:
    """Copy JSON-compatible data into deterministic immutable containers."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field_name} must contain finite numbers")
        return value
    if isinstance(value, datetime):
        return utc_time(value, field_name).isoformat()
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError(f"{field_name} keys must be strings")
        return MappingProxyType(
            {
                key: _freeze_json(value[key], field_name=f"{field_name}.{key}")
                for key in sorted(value)
            }
        )
    if isinstance(value, (tuple, list)):
        return tuple(
            _freeze_json(item, field_name=f"{field_name} item") for item in value
        )
    raise TypeError(f"{field_name} must be JSON-compatible")


def _thaw_json(value: JsonValue) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class RunProvenance:
    """Explicit origin of a Run update or blocker; never inferred."""

    source_type: str
    source_id: str | None = None
    actor: str | None = None

    def __post_init__(self) -> None:
        vocabulary(self.source_type, "run provenance source_type")
        for name in ("source_id", "actor"):
            value = getattr(self, name)
            if value is not None:
                identifier(value, f"run provenance {name}")

    def to_data(self) -> dict[str, object]:
        return {
            "source_type": self.source_type,
            "source_id": self.source_id,
            "actor": self.actor,
        }


class StepProgressState(StrEnum):
    NOT_STARTED = "not_started"
    ACTIVE = "active"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class StepAvailability(StrEnum):
    READY = "ready"
    WAITING_DEPENDENCIES = "waiting_dependencies"
    BLOCKED = "blocked"
    ACTIVE = "active"
    TERMINAL = "terminal"


class PlanRunCondition(StrEnum):
    OPEN = "open"
    STRUCTURALLY_COMPLETE = "structurally_complete"
    CANNOT_ADVANCE = "cannot_advance"


class PlanBlockerState(StrEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"


@dataclass(frozen=True, slots=True)
class StepProgress:
    """Runtime state for one PlanStep, without copying its definition."""

    step_id: str
    state: StepProgressState
    changed_at: datetime
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        identifier(self.step_id, "step progress step_id")
        if not isinstance(self.state, StepProgressState):
            raise TypeError("step progress state must be a StepProgressState")
        object.__setattr__(
            self, "changed_at", utc_time(self.changed_at, "step changed_at")
        )
        evidence = tuple(sorted(self.evidence_ids))
        for evidence_id in evidence:
            identifier(evidence_id, "step evidence ID")
        if len(evidence) != len(set(evidence)):
            raise PlanRunInvariantError("step evidence references must be distinct")
        terminal = self.state in {
            StepProgressState.SUCCEEDED,
            StepProgressState.FAILED,
        }
        if terminal and not evidence:
            raise PlanRunInvariantError("terminal step progress requires evidence")
        if not terminal and evidence:
            raise PlanRunInvariantError(
                "only terminal step progress may contain evidence"
            )
        object.__setattr__(self, "evidence_ids", evidence)

    def to_data(self) -> dict[str, object]:
        return {
            "step_id": self.step_id,
            "state": self.state.value,
            "changed_at": self.changed_at.isoformat(),
            "evidence_ids": list(self.evidence_ids),
        }


@dataclass(frozen=True, slots=True)
class PlanObservation:
    """Append-only evidence data; recording it never changes progress."""

    observation_id: str
    run_id: str
    source: str
    observed_at: datetime
    kind: str
    step_id: str | None = None
    source_reference: str | None = None
    data: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        identifier(self.observation_id, "observation_id")
        identifier(self.run_id, "observation run_id")
        vocabulary(self.source, "observation source")
        vocabulary(self.kind, "observation kind")
        if self.step_id is not None:
            identifier(self.step_id, "observation step_id")
        if self.source_reference is not None:
            identifier(self.source_reference, "observation source_reference")
        object.__setattr__(
            self, "observed_at", utc_time(self.observed_at, "observed_at")
        )
        frozen = _freeze_json(self.data, field_name="observation data")
        if not isinstance(frozen, Mapping):  # pragma: no cover - mapping input
            raise TypeError("observation data must be a mapping")
        object.__setattr__(self, "data", frozen)

    def to_data(self) -> dict[str, object]:
        return {
            "observation_id": self.observation_id,
            "run_id": self.run_id,
            "step_id": self.step_id,
            "source": self.source,
            "source_reference": self.source_reference,
            "observed_at": self.observed_at.isoformat(),
            "kind": self.kind,
            "data": _thaw_json(cast(JsonValue, self.data)),
        }


@dataclass(frozen=True, slots=True)
class PlanBlocker:
    """Explicit external condition preventing one NOT_STARTED step."""

    blocker_id: str
    run_id: str
    step_id: str
    kind: str
    reason: str
    provenance: RunProvenance
    created_at: datetime
    state: PlanBlockerState = PlanBlockerState.ACTIVE
    resolved_at: datetime | None = None

    def __post_init__(self) -> None:
        identifier(self.blocker_id, "blocker_id")
        identifier(self.run_id, "blocker run_id")
        identifier(self.step_id, "blocker step_id")
        vocabulary(self.kind, "blocker kind")
        object.__setattr__(self, "reason", _text(self.reason, "blocker reason"))
        if not isinstance(self.provenance, RunProvenance):
            raise TypeError("blocker provenance must be RunProvenance")
        created = utc_time(self.created_at, "blocker created_at")
        object.__setattr__(self, "created_at", created)
        if not isinstance(self.state, PlanBlockerState):
            raise TypeError("blocker state must be a PlanBlockerState")
        resolved = (
            None
            if self.resolved_at is None
            else utc_time(self.resolved_at, "blocker resolved_at")
        )
        if self.state is PlanBlockerState.ACTIVE and resolved is not None:
            raise PlanRunInvariantError("an active blocker cannot have resolved_at")
        if self.state is PlanBlockerState.RESOLVED and resolved is None:
            raise PlanRunInvariantError("a resolved blocker requires resolved_at")
        if resolved is not None and resolved < created:
            raise PlanRunInvariantError("blocker resolved_at cannot predate created_at")
        object.__setattr__(self, "resolved_at", resolved)

    def to_data(self) -> dict[str, object]:
        return {
            "blocker_id": self.blocker_id,
            "run_id": self.run_id,
            "step_id": self.step_id,
            "kind": self.kind,
            "reason": self.reason,
            "provenance": self.provenance.to_data(),
            "created_at": self.created_at.isoformat(),
            "state": self.state.value,
            "resolved_at": (
                None if self.resolved_at is None else self.resolved_at.isoformat()
            ),
        }


@dataclass(frozen=True, slots=True)
class PlanRun:
    """One immutable revision of operational state for a specific Plan."""

    run_id: str
    plan_id: str
    goal_id: str
    revision: int
    created_at: datetime
    updated_at: datetime
    step_progress: tuple[StepProgress, ...]
    observations: tuple[PlanObservation, ...] = ()
    blockers: tuple[PlanBlocker, ...] = ()

    def __post_init__(self) -> None:
        for value, name in (
            (self.run_id, "run_id"),
            (self.plan_id, "run plan_id"),
            (self.goal_id, "run goal_id"),
        ):
            identifier(value, name)
        if self.run_id in {self.plan_id, self.goal_id}:
            raise PlanRunInvariantError(
                "PlanRun identity must differ from Plan and Goal identities"
            )
        if isinstance(self.revision, bool) or not isinstance(self.revision, int):
            raise TypeError("revision must be an integer")
        if self.revision < 0:
            raise PlanRunInvariantError("revision must be nonnegative")
        created = utc_time(self.created_at, "run created_at")
        updated = utc_time(self.updated_at, "run updated_at")
        if updated < created:
            raise PlanRunInvariantError("run updated_at cannot predate created_at")
        object.__setattr__(self, "created_at", created)
        object.__setattr__(self, "updated_at", updated)

        progress = tuple(self.step_progress)
        if any(not isinstance(item, StepProgress) for item in progress):
            raise TypeError("step_progress must contain StepProgress values")
        progress = tuple(sorted(progress, key=lambda item: item.step_id))
        progress_ids = tuple(item.step_id for item in progress)
        if len(progress_ids) != len(set(progress_ids)):
            raise PlanRunInvariantError("step progress identities must be unique")
        for progress_item in progress:
            if not created <= progress_item.changed_at <= updated:
                raise PlanRunInvariantError(
                    "step changed_at must fall within the Run revision interval"
                )
        object.__setattr__(self, "step_progress", progress)

        observations = tuple(self.observations)
        if any(not isinstance(item, PlanObservation) for item in observations):
            raise TypeError("observations must contain PlanObservation values")
        observations = tuple(sorted(observations, key=lambda item: item.observation_id))
        observation_ids = tuple(item.observation_id for item in observations)
        if len(observation_ids) != len(set(observation_ids)):
            raise DuplicateRunIdentityError("observation identities must be unique")
        for observation in observations:
            if observation.run_id != self.run_id:
                raise PlanRunInvariantError("observation belongs to a different Run")
            if not created <= observation.observed_at <= updated:
                raise PlanRunInvariantError(
                    "observation time must fall within the Run revision interval"
                )
        object.__setattr__(self, "observations", observations)

        blockers = tuple(self.blockers)
        if any(not isinstance(item, PlanBlocker) for item in blockers):
            raise TypeError("blockers must contain PlanBlocker values")
        blockers = tuple(sorted(blockers, key=lambda item: item.blocker_id))
        blocker_ids = tuple(item.blocker_id for item in blockers)
        if len(blocker_ids) != len(set(blocker_ids)):
            raise DuplicateRunIdentityError("blocker identities must be unique")
        for blocker in blockers:
            if blocker.run_id != self.run_id:
                raise PlanRunInvariantError("blocker belongs to a different Run")
            if not created <= blocker.created_at <= updated:
                raise PlanRunInvariantError(
                    "blocker created_at must fall within the Run revision interval"
                )
            if blocker.resolved_at is not None and blocker.resolved_at > updated:
                raise PlanRunInvariantError(
                    "blocker resolved_at cannot follow run updated_at"
                )
        object.__setattr__(self, "blockers", blockers)
        self._validate_evidence()

    def _validate_evidence(self) -> None:
        observations = {item.observation_id: item for item in self.observations}
        for progress in self.step_progress:
            for evidence_id in progress.evidence_ids:
                observation = observations.get(evidence_id)
                if observation is None:
                    raise ForeignEvidenceError(
                        f"step {progress.step_id} references unknown evidence "
                        f"{evidence_id}"
                    )
                if observation.step_id not in {None, progress.step_id}:
                    raise ForeignEvidenceError(
                        f"evidence {evidence_id} is scoped to another step"
                    )

    def to_data(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "plan_id": self.plan_id,
            "goal_id": self.goal_id,
            "revision": self.revision,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "step_progress": [item.to_data() for item in self.step_progress],
            "observations": [item.to_data() for item in self.observations],
            "blockers": [item.to_data() for item in self.blockers],
        }


@dataclass(frozen=True, slots=True)
class PlanRunUpdate:
    """Common optimistic-revision envelope for one atomic Run operation."""

    operation: ClassVar[str] = "abstract"

    update_id: str
    run_id: str
    expected_revision: int
    updated_at: datetime
    provenance: RunProvenance

    def __post_init__(self) -> None:
        if type(self) is PlanRunUpdate:
            raise TypeError("PlanRunUpdate must use a concrete operation")
        identifier(self.update_id, "update_id")
        identifier(self.run_id, "update run_id")
        if isinstance(self.expected_revision, bool) or not isinstance(
            self.expected_revision, int
        ):
            raise TypeError("expected_revision must be an integer")
        if self.expected_revision < 0:
            raise ValueError("expected_revision must be nonnegative")
        object.__setattr__(
            self, "updated_at", utc_time(self.updated_at, "update updated_at")
        )
        if not isinstance(self.provenance, RunProvenance):
            raise TypeError("update provenance must be RunProvenance")

    def _base_data(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "update_id": self.update_id,
            "run_id": self.run_id,
            "expected_revision": self.expected_revision,
            "updated_at": self.updated_at.isoformat(),
            "provenance": self.provenance.to_data(),
        }


@dataclass(frozen=True, slots=True)
class StepProgressUpdate(PlanRunUpdate):
    """Request one explicit StepProgress transition."""

    operation: ClassVar[str] = "transition_step"

    step_id: str
    new_state: StepProgressState
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        PlanRunUpdate.__post_init__(self)
        identifier(self.step_id, "update step_id")
        if not isinstance(self.new_state, StepProgressState):
            raise TypeError("new_state must be a StepProgressState")
        evidence = tuple(sorted(self.evidence_ids))
        for evidence_id in evidence:
            identifier(evidence_id, "update evidence ID")
        if len(evidence) != len(set(evidence)):
            raise ValueError("update evidence references must be distinct")
        terminal = self.new_state in {
            StepProgressState.SUCCEEDED,
            StepProgressState.FAILED,
        }
        if terminal and not evidence:
            raise ValueError("terminal transition requires evidence")
        if not terminal and evidence:
            raise ValueError("non-terminal transition cannot contain evidence")
        object.__setattr__(self, "evidence_ids", evidence)

    def to_data(self) -> dict[str, object]:
        data = self._base_data()
        data.update(
            {
                "step_id": self.step_id,
                "new_state": self.new_state.value,
                "evidence_ids": list(self.evidence_ids),
            }
        )
        return data


@dataclass(frozen=True, slots=True)
class RecordObservationUpdate(PlanRunUpdate):
    """Append one observation without changing StepProgress."""

    operation: ClassVar[str] = "record_observation"

    observation: PlanObservation

    def __post_init__(self) -> None:
        PlanRunUpdate.__post_init__(self)
        if not isinstance(self.observation, PlanObservation):
            raise TypeError("observation must be a PlanObservation")

    def to_data(self) -> dict[str, object]:
        data = self._base_data()
        data["observation"] = self.observation.to_data()
        return data


@dataclass(frozen=True, slots=True)
class AddBlockerUpdate(PlanRunUpdate):
    """Add one explicit active blocker to a NOT_STARTED step."""

    operation: ClassVar[str] = "add_blocker"

    blocker: PlanBlocker

    def __post_init__(self) -> None:
        PlanRunUpdate.__post_init__(self)
        if not isinstance(self.blocker, PlanBlocker):
            raise TypeError("blocker must be a PlanBlocker")

    def to_data(self) -> dict[str, object]:
        data = self._base_data()
        data["blocker"] = self.blocker.to_data()
        return data


@dataclass(frozen=True, slots=True)
class ResolveBlockerUpdate(PlanRunUpdate):
    """Resolve one existing active blocker without changing progress."""

    operation: ClassVar[str] = "resolve_blocker"

    blocker_id: str

    def __post_init__(self) -> None:
        PlanRunUpdate.__post_init__(self)
        identifier(self.blocker_id, "update blocker_id")

    def to_data(self) -> dict[str, object]:
        data = self._base_data()
        data["blocker_id"] = self.blocker_id
        return data
