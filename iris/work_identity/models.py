"""Pure, immutable identity models for current work and causal origin."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypeAlias

from iris.work_identity.errors import WorkReferenceMismatchError

_VOCABULARY = re.compile(r"[a-z][a-z0-9_]*\Z")


def _identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a nonblank identifier")
    return value


def _vocabulary(value: str, name: str) -> str:
    if not isinstance(value, str) or not _VOCABULARY.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase identifier")
    return value


class WorkSubjectKind(StrEnum):
    """The two operational subject kinds supported by the foundation."""

    REQUEST = "request"
    PLAN_STEP = "plan_step"


@dataclass(frozen=True, slots=True)
class WorkOrigin:
    """A descriptive root-cause reference, never trust or authorization."""

    source_type: str
    source_id: str

    def __post_init__(self) -> None:
        _vocabulary(self.source_type, "origin source_type")
        _identifier(self.source_id, "origin source_id")

    def to_data(self) -> dict[str, object]:
        return {
            "source_type": self.source_type,
            "source_id": self.source_id,
        }


@dataclass(frozen=True, slots=True)
class RequestWorkReference:
    """Identity-only reference to an incoming Request."""

    request_id: str

    def __post_init__(self) -> None:
        _identifier(self.request_id, "work request_id")

    def to_data(self) -> dict[str, object]:
        return {"request_id": self.request_id}


@dataclass(frozen=True, slots=True)
class PlanStepWorkReference:
    """Stable identity of one PlanStep within one concrete PlanRun."""

    plan_id: str
    run_id: str
    step_id: str

    def __post_init__(self) -> None:
        _identifier(self.plan_id, "work plan_id")
        _identifier(self.run_id, "work run_id")
        _identifier(self.step_id, "work step_id")

    def to_data(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "run_id": self.run_id,
            "step_id": self.step_id,
        }


WorkReference: TypeAlias = RequestWorkReference | PlanStepWorkReference


def _canonical_subject_id(
    kind: WorkSubjectKind,
    reference: WorkReference,
) -> str:
    material = json.dumps(
        {
            "kind": kind.value,
            "reference": reference.to_data(),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"work_subject_{hashlib.sha256(material).hexdigest()}"


@dataclass(frozen=True, slots=True)
class WorkSubject:
    """The current operational work identity, separate from root origin."""

    kind: WorkSubjectKind
    reference: WorkReference
    origin: WorkOrigin | None = None
    subject_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, WorkSubjectKind):
            raise TypeError("work subject kind must be a WorkSubjectKind")
        expected_type = {
            WorkSubjectKind.REQUEST: RequestWorkReference,
            WorkSubjectKind.PLAN_STEP: PlanStepWorkReference,
        }[self.kind]
        if not isinstance(self.reference, expected_type):
            raise WorkReferenceMismatchError(
                f"{self.kind.value} requires {expected_type.__name__}"
            )
        if self.origin is not None and not isinstance(self.origin, WorkOrigin):
            raise TypeError("work subject origin must be a WorkOrigin or None")
        object.__setattr__(
            self,
            "subject_id",
            _canonical_subject_id(self.kind, self.reference),
        )

    def to_data(self) -> dict[str, object]:
        return {
            "subject_id": self.subject_id,
            "kind": self.kind.value,
            "reference": self.reference.to_data(),
            "origin": None if self.origin is None else self.origin.to_data(),
        }
