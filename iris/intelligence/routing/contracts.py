"""Structural contracts for replaceable intelligence routing policies."""

from typing import Protocol, runtime_checkable

from iris.intelligence.routing.models import IntelligenceNeed, IntelligenceResource


@runtime_checkable
class RoutingPolicy(Protocol):
    """Select one resource from an already validated candidate set."""

    def select(
        self,
        need: IntelligenceNeed,
        candidates: tuple[IntelligenceResource, ...],
    ) -> IntelligenceResource:
        """Select one candidate without relaxing any requirement."""
        ...
