"""Execution runtime for explicitly selected capabilities."""

from iris.capabilities.models import CapabilityInput, CapabilityResult
from iris.capabilities.registry import CapabilityRegistry


class CapabilityRuntime:
    """Resolve and execute capabilities independently of any interface."""

    def __init__(self, registry: CapabilityRegistry) -> None:
        self._registry = registry

    def execute(
        self,
        capability_id: str,
        capability_input: CapabilityInput,
    ) -> CapabilityResult:
        """Execute one capability and preserve unexpected exceptions.

        Capabilities represent expected operational failures with a failed
        ``CapabilityResult``. Contract violations and programming errors are
        allowed to propagate instead of being disguised as recoverable output.
        """

        capability = self._registry.get(capability_id)
        result = capability.execute(capability_input)

        if not isinstance(result, CapabilityResult):
            raise TypeError(f"capability {capability_id} returned an invalid result")
        if result.capability_id != capability_id:
            raise ValueError(
                "capability result identifier does not match the invocation"
            )
        return result
