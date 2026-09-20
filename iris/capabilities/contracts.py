"""Structural contracts for executable IRIS capabilities."""

from typing import Protocol, runtime_checkable

from iris.capabilities.models import (
    CapabilityDescriptor,
    CapabilityInput,
    CapabilityResult,
)


@runtime_checkable
class Capability(Protocol):
    """A registered, directly executable capability owned by IRIS."""

    @property
    def descriptor(self) -> CapabilityDescriptor:
        """Return stable identity and discovery metadata."""
        ...

    def execute(self, capability_input: CapabilityInput) -> CapabilityResult:
        """Execute one explicit invocation and return a structured result."""
        ...


@runtime_checkable
class Tool(Capability, Protocol):
    """A technical capability invocable through the capability runtime."""


@runtime_checkable
class CapabilityExecutor(Protocol):
    """Runtime boundary used by dispatchers to invoke capabilities."""

    def execute(
        self,
        capability_id: str,
        capability_input: CapabilityInput,
    ) -> CapabilityResult:
        """Execute the named capability with explicit input."""
        ...
