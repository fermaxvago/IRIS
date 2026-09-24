"""Structural, replaceable policy for selecting contextual evidence."""

from typing import Protocol, runtime_checkable

from iris.context.models import ContextBudget, ContextCandidate
from iris.context.selection import ContextSelection


@runtime_checkable
class ContextSelectionPolicy(Protocol):
    def select(
        self,
        candidates: tuple[ContextCandidate, ...],
        budget: ContextBudget,
    ) -> ContextSelection:
        """Select bounded context without calling other IRIS runtimes."""
        ...
