"""Immutable, deterministic models for PlanRun control decisions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from iris.plan_control.errors import PlanControlInvariantError

_VOCABULARY = re.compile(r"[a-z][a-z0-9_]*\Z")


def _identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a nonblank identifier")
    return value


def _vocabulary(value: str, name: str) -> str:
    if not isinstance(value, str) or not _VOCABULARY.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase identifier")
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


def _ordered_ids(
    values: tuple[str, ...], name: str, *, minimum: int = 0
) -> tuple[str, ...]:
    items = tuple(values)
    for value in items:
        _identifier(value, name)
    if len(items) != len(set(items)):
        raise ValueError(f"{name} must contain distinct identifiers")
    if len(items) < minimum:
        raise ValueError(f"{name} requires at least {minimum} identifiers")
    return tuple(sorted(items))


class ControlDecisionKind(StrEnum):
    STEP_SELECTED = "step_selected"
    ACTIVE_WORK_PENDING = "active_work_pending"
    SELECTION_UNRESOLVED = "selection_unresolved"
    RUN_CANNOT_ADVANCE = "run_cannot_advance"
    RUN_STRUCTURALLY_COMPLETE = "run_structurally_complete"


class ControlReason(StrEnum):
    ONLY_READY_STEP = "only_ready_step"
    POLICY_SELECTED = "policy_selected"
    ACTIVE_STEP_EXISTS = "active_step_exists"
    MULTIPLE_READY_UNRESOLVED = "multiple_ready_unresolved"
    RUN_CANNOT_ADVANCE = "run_cannot_advance"
    RUN_STRUCTURALLY_COMPLETE = "run_structurally_complete"


class StepSelectionResultKind(StrEnum):
    SELECTED = "selected"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class ControlProvenance:
    """Traceable decision origin, without authorization or trust semantics."""

    controller_id: str
    controller_version: str | None = None
    policy_id: str | None = None
    policy_version: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.controller_id, "controller_id")
        _optional_identifier(self.controller_version, "controller_version")
        _optional_identifier(self.policy_id, "policy_id")
        _optional_identifier(self.policy_version, "policy_version")
        if self.policy_id is None and self.policy_version is not None:
            raise ValueError("policy_version requires policy_id")

    def to_data(self) -> dict[str, object]:
        return {
            "controller_id": self.controller_id,
            "controller_version": self.controller_version,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
        }


@dataclass(frozen=True, slots=True)
class StepSelectionRequest:
    """A stable unordered set of READY candidates for explicit resolution."""

    plan_id: str
    run_id: str
    observed_revision: int
    candidate_step_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _identifier(self.plan_id, "selection plan_id")
        _identifier(self.run_id, "selection run_id")
        _revision(self.observed_revision, "selection observed_revision")
        object.__setattr__(
            self,
            "candidate_step_ids",
            _ordered_ids(
                self.candidate_step_ids,
                "selection candidate_step_ids",
                minimum=2,
            ),
        )

    def to_data(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "run_id": self.run_id,
            "observed_revision": self.observed_revision,
            "candidate_step_ids": list(self.candidate_step_ids),
        }


@dataclass(frozen=True, slots=True)
class StepSelectionResult:
    """Explicit policy selection or legitimate abstention."""

    kind: StepSelectionResultKind
    reason: str
    selected_step_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, StepSelectionResultKind):
            raise TypeError("selection result kind must be a StepSelectionResultKind")
        _vocabulary(self.reason, "selection result reason")
        if self.kind is StepSelectionResultKind.SELECTED:
            if self.selected_step_id is None:
                raise PlanControlInvariantError(
                    "SELECTED selection result requires selected_step_id"
                )
            _identifier(self.selected_step_id, "selected_step_id")
        elif self.selected_step_id is not None:
            raise PlanControlInvariantError(
                "UNRESOLVED selection result cannot contain selected_step_id"
            )

    def to_data(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "selected_step_id": self.selected_step_id,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ControlDecision:
    """One immutable decision over one exact PlanRun revision."""

    plan_id: str
    run_id: str
    observed_revision: int
    kind: ControlDecisionKind
    reason: ControlReason
    provenance: ControlProvenance
    candidate_step_ids: tuple[str, ...] = ()
    selected_step_id: str | None = None
    active_step_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _identifier(self.plan_id, "decision plan_id")
        _identifier(self.run_id, "decision run_id")
        _revision(self.observed_revision, "decision observed_revision")
        if not isinstance(self.kind, ControlDecisionKind):
            raise TypeError("decision kind must be a ControlDecisionKind")
        if not isinstance(self.reason, ControlReason):
            raise TypeError("decision reason must be a ControlReason")
        if not isinstance(self.provenance, ControlProvenance):
            raise TypeError("decision provenance must be ControlProvenance")
        candidates = _ordered_ids(
            self.candidate_step_ids, "decision candidate_step_ids"
        )
        active = _ordered_ids(self.active_step_ids, "decision active_step_ids")
        object.__setattr__(self, "candidate_step_ids", candidates)
        object.__setattr__(self, "active_step_ids", active)
        self._validate_shape(candidates, active)

    def _validate_shape(
        self, candidates: tuple[str, ...], active: tuple[str, ...]
    ) -> None:
        expected_reason = {
            ControlDecisionKind.ACTIVE_WORK_PENDING: ControlReason.ACTIVE_STEP_EXISTS,
            ControlDecisionKind.SELECTION_UNRESOLVED: (
                ControlReason.MULTIPLE_READY_UNRESOLVED
            ),
            ControlDecisionKind.RUN_CANNOT_ADVANCE: ControlReason.RUN_CANNOT_ADVANCE,
            ControlDecisionKind.RUN_STRUCTURALLY_COMPLETE: (
                ControlReason.RUN_STRUCTURALLY_COMPLETE
            ),
        }
        if self.kind is ControlDecisionKind.STEP_SELECTED:
            if self.reason not in {
                ControlReason.ONLY_READY_STEP,
                ControlReason.POLICY_SELECTED,
            }:
                raise PlanControlInvariantError(
                    "STEP_SELECTED has an incompatible reason"
                )
            if self.selected_step_id is None:
                raise PlanControlInvariantError(
                    "STEP_SELECTED requires selected_step_id"
                )
            _identifier(self.selected_step_id, "decision selected_step_id")
            if self.selected_step_id not in candidates:
                raise PlanControlInvariantError(
                    "selected_step_id must be a recorded candidate"
                )
            if active:
                raise PlanControlInvariantError(
                    "STEP_SELECTED cannot contain active steps"
                )
            if self.reason is ControlReason.ONLY_READY_STEP and len(candidates) != 1:
                raise PlanControlInvariantError(
                    "ONLY_READY_STEP requires exactly one candidate"
                )
            if self.reason is ControlReason.POLICY_SELECTED:
                if len(candidates) < 2:
                    raise PlanControlInvariantError(
                        "POLICY_SELECTED requires multiple candidates"
                    )
                if self.provenance.policy_id is None:
                    raise PlanControlInvariantError(
                        "POLICY_SELECTED requires policy provenance"
                    )
            return

        if self.selected_step_id is not None:
            raise PlanControlInvariantError(
                f"{self.kind.value} cannot contain selected_step_id"
            )
        if self.reason is not expected_reason[self.kind]:
            raise PlanControlInvariantError(
                f"{self.kind.value} has an incompatible reason"
            )
        if self.kind is ControlDecisionKind.ACTIVE_WORK_PENDING and not active:
            raise PlanControlInvariantError(
                "ACTIVE_WORK_PENDING requires at least one active step"
            )
        if self.kind is ControlDecisionKind.SELECTION_UNRESOLVED:
            if len(candidates) < 2 or active:
                raise PlanControlInvariantError(
                    "SELECTION_UNRESOLVED requires multiple candidates and no active step"
                )
        if self.kind in {
            ControlDecisionKind.RUN_CANNOT_ADVANCE,
            ControlDecisionKind.RUN_STRUCTURALLY_COMPLETE,
        } and (candidates or active):
            raise PlanControlInvariantError(
                f"{self.kind.value} cannot contain candidates or active steps"
            )

    def to_data(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "run_id": self.run_id,
            "observed_revision": self.observed_revision,
            "kind": self.kind.value,
            "reason": self.reason.value,
            "provenance": self.provenance.to_data(),
            "candidate_step_ids": list(self.candidate_step_ids),
            "selected_step_id": self.selected_step_id,
            "active_step_ids": list(self.active_step_ids),
        }
