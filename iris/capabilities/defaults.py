"""Composition root for capabilities shipped with IRIS."""

from iris.capabilities.registry import CapabilityRegistry
from iris.capabilities.runtime import CapabilityRuntime
from iris.capabilities.system_status import SystemStatusTool


def create_default_runtime() -> CapabilityRuntime:
    """Build a runtime containing the current built-in capabilities."""

    registry = CapabilityRegistry([SystemStatusTool()])
    return CapabilityRuntime(registry)
