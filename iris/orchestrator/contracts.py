"""Replaceable contract for a pure orchestration policy."""

from typing import Protocol, runtime_checkable

from iris.orchestrator.models import OrchestrationInput, OrchestrationSelection


@runtime_checkable
class OrchestrationPolicy(Protocol):
    def select(self, orchestration_input: OrchestrationInput) -> OrchestrationSelection:
        """Return one semantic decision without executing a subsystem."""
        ...
