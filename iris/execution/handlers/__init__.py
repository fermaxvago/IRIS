"""Small adapters for the established IRIS subsystem boundaries."""

from iris.execution.handlers.capability import CapabilityExecutionHandler
from iris.execution.handlers.intelligence import IntelligenceExecutionHandler
from iris.execution.handlers.memory import MemoryExecutionHandler
from iris.execution.handlers.system import SystemExecutionHandler

__all__ = [
    "CapabilityExecutionHandler",
    "IntelligenceExecutionHandler",
    "MemoryExecutionHandler",
    "SystemExecutionHandler",
]
