"""Replaceable provider-independent Planning contract."""

from typing import Protocol, runtime_checkable

from iris.planning.models import PlanningRequest, PlanningResult


@runtime_checkable
class Planner(Protocol):
    def plan(self, request: PlanningRequest) -> PlanningResult:
        """Represent a strategy or terminal Planning outcome, then stop."""
        ...
