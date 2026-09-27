"""Pure policy contracts and deterministic READY-step selection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol

from iris.plan_control.models import (
    StepSelectionRequest,
    StepSelectionResult,
    StepSelectionResultKind,
    _identifier,
)


class StepSelectionPolicy(Protocol):
    """Resolve multiple READY candidates without performing any action."""

    @property
    def policy_id(self) -> str:
        """Return a stable implementation/configuration identity."""
        ...

    @property
    def policy_version(self) -> str | None:
        """Return an optional policy version for provenance."""
        ...

    def select(self, request: StepSelectionRequest) -> StepSelectionResult:
        """Select one candidate or explicitly abstain."""
        ...


@dataclass(frozen=True, slots=True)
class ExplicitPriorityStepSelectionPolicy:
    """Select the unique highest explicitly configured candidate priority."""

    priorities: Mapping[str, int]
    policy_id: str = "explicit_priority"
    policy_version: str | None = "1"

    def __post_init__(self) -> None:
        _identifier(self.policy_id, "policy_id")
        if self.policy_version is not None:
            _identifier(self.policy_version, "policy_version")
        if not isinstance(self.priorities, Mapping):
            raise TypeError("priorities must be a mapping")
        copied: dict[str, int] = {}
        for step_id in sorted(self.priorities):
            _identifier(step_id, "priority step_id")
            value = self.priorities[step_id]
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError("priority values must be integers")
            copied[step_id] = value
        frozen = MappingProxyType(copied)
        object.__setattr__(self, "priorities", frozen)

    def select(self, request: StepSelectionRequest) -> StepSelectionResult:
        if not isinstance(request, StepSelectionRequest):
            raise TypeError("request must be a StepSelectionRequest")
        missing = tuple(
            step_id
            for step_id in request.candidate_step_ids
            if step_id not in self.priorities
        )
        if missing:
            return StepSelectionResult(
                StepSelectionResultKind.UNRESOLVED,
                "missing_explicit_priority",
            )

        highest = max(self.priorities[item] for item in request.candidate_step_ids)
        winners = tuple(
            item
            for item in request.candidate_step_ids
            if self.priorities[item] == highest
        )
        if len(winners) != 1:
            return StepSelectionResult(
                StepSelectionResultKind.UNRESOLVED,
                "highest_priority_tied",
            )
        return StepSelectionResult(
            StepSelectionResultKind.SELECTED,
            "highest_explicit_priority",
            winners[0],
        )
