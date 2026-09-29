"""Replaceable policy contract for StepProgress transition decisions."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from iris.step_progress_transition.models import (
    StepProgressTransitionPolicyResult,
    StepProgressTransitionRequest,
)


@runtime_checkable
class StepProgressTransitionPolicy(Protocol):
    """Decide over an already validated and applicable assessment binding."""

    @property
    def policy_id(self) -> str:
        """Return a stable policy implementation/configuration identity."""
        ...

    @property
    def policy_version(self) -> str | None:
        """Return the optional policy version used for this decision."""
        ...

    def decide(
        self, request: StepProgressTransitionRequest
    ) -> StepProgressTransitionPolicyResult:
        """Return one transition or auditable abstention, without side effects."""
        ...
