"""Immutable epistemic outcome-assessment models."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import TypeAlias, cast

from iris.outcome_assessment.errors import OutcomeAssessmentIdentityError

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | tuple["JsonValue", ...] | Mapping[str, "JsonValue"]


def _identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a nonblank identifier")
    return value


def _utc_time(value: datetime, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be a timezone-aware datetime")
    return value.astimezone(UTC)


def _freeze_json(value: object, *, field_name: str) -> JsonValue:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field_name} must contain finite numbers")
        return value
    if isinstance(value, datetime):
        return _utc_time(value, field_name).isoformat()
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


class StepOutcomeStatus(StrEnum):
    """Epistemic conclusion about one PlanStep expected outcome."""

    SATISFIED = "satisfied"
    NOT_SATISFIED = "not_satisfied"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True, slots=True)
class StepOutcomeAssessment:
    """One inert, auditable conclusion over explicitly selected evidence."""

    assessment_id: str
    plan_id: str
    run_id: str
    run_revision: int
    step_id: str
    status: StepOutcomeStatus
    evidence_ids: tuple[str, ...]
    evaluator_reference: str
    assessed_at: datetime
    details: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for value, name in (
            (self.assessment_id, "assessment_id"),
            (self.plan_id, "assessment plan_id"),
            (self.run_id, "assessment run_id"),
            (self.step_id, "assessment step_id"),
            (self.evaluator_reference, "evaluator_reference"),
        ):
            _identifier(value, name)
        if isinstance(self.run_revision, bool) or not isinstance(
            self.run_revision, int
        ):
            raise TypeError("run_revision must be an integer")
        if self.run_revision < 0:
            raise ValueError("run_revision must be nonnegative")
        if not isinstance(self.status, StepOutcomeStatus):
            raise TypeError("status must be a StepOutcomeStatus")

        evidence_ids = tuple(sorted(self.evidence_ids))
        for evidence_id in evidence_ids:
            _identifier(evidence_id, "assessment evidence ID")
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("assessment evidence IDs must be distinct")
        if (
            self.status
            in {
                StepOutcomeStatus.SATISFIED,
                StepOutcomeStatus.NOT_SATISFIED,
                StepOutcomeStatus.INDETERMINATE,
            }
            and not evidence_ids
        ):
            raise ValueError(f"{self.status.value} assessment requires evidence")
        object.__setattr__(self, "evidence_ids", evidence_ids)

        if self.assessment_id in {
            self.plan_id,
            self.run_id,
            self.step_id,
            *evidence_ids,
        }:
            raise OutcomeAssessmentIdentityError(
                "assessment_id must be independent from Plan, Run, step, and evidence"
            )
        object.__setattr__(
            self, "assessed_at", _utc_time(self.assessed_at, "assessed_at")
        )
        frozen = _freeze_json(self.details, field_name="assessment details")
        if not isinstance(frozen, Mapping):  # pragma: no cover - mapping input
            raise TypeError("assessment details must be a mapping")
        object.__setattr__(self, "details", frozen)

    def to_data(self) -> dict[str, object]:
        return {
            "assessment_id": self.assessment_id,
            "plan_id": self.plan_id,
            "run_id": self.run_id,
            "run_revision": self.run_revision,
            "step_id": self.step_id,
            "status": self.status.value,
            "evidence_ids": list(self.evidence_ids),
            "evaluator_reference": self.evaluator_reference,
            "assessed_at": self.assessed_at.isoformat(),
            "details": _thaw_json(cast(JsonValue, self.details)),
        }
