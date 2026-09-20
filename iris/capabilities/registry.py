"""Explicit in-process registry for executable capabilities."""

from __future__ import annotations

from collections.abc import Iterable

from iris.capabilities.contracts import Capability
from iris.capabilities.models import CapabilityDescriptor


class DuplicateCapabilityError(ValueError):
    """Raised when an identifier is registered more than once."""


class CapabilityNotFoundError(LookupError):
    """Raised when an identifier is not present in a registry."""


class CapabilityRegistry:
    """Register and discover capabilities without implicit global state."""

    def __init__(self, capabilities: Iterable[Capability] = ()) -> None:
        self._capabilities: dict[str, Capability] = {}
        for capability in capabilities:
            self.register(capability)

    def register(self, capability: Capability) -> Capability:
        """Register one capability, rejecting duplicate identifiers."""

        capability_id = capability.descriptor.capability_id
        if capability_id in self._capabilities:
            raise DuplicateCapabilityError(
                f"capability already registered: {capability_id}"
            )
        self._capabilities[capability_id] = capability
        return capability

    def get(self, capability_id: str) -> Capability:
        """Return a capability or fail explicitly when it is unknown."""

        try:
            return self._capabilities[capability_id]
        except KeyError as exc:
            raise CapabilityNotFoundError(
                f"capability is not registered: {capability_id}"
            ) from exc

    def list_capabilities(self) -> tuple[CapabilityDescriptor, ...]:
        """Return descriptors in deterministic identifier order."""

        return tuple(
            self._capabilities[capability_id].descriptor
            for capability_id in sorted(self._capabilities)
        )
