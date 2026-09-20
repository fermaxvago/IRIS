"""Provider-independent generative intelligence boundary for IRIS."""

from iris.intelligence.contracts import IntelligenceProvider
from iris.intelligence.models import (
    IntelligenceRequest,
    IntelligenceResult,
    IntelligenceStatus,
    ModelCapability,
    ModelDescriptor,
    ModelLocation,
)
from iris.intelligence.registry import (
    DuplicateProviderError,
    ProviderNotFoundError,
    ProviderRegistry,
)
from iris.intelligence.runtime import (
    IntelligenceRuntime,
    ModelNotFoundError,
    ModelUnavailableError,
    ProviderContractError,
)

__all__ = [
    "DuplicateProviderError",
    "IntelligenceProvider",
    "IntelligenceRequest",
    "IntelligenceResult",
    "IntelligenceRuntime",
    "IntelligenceStatus",
    "ModelCapability",
    "ModelDescriptor",
    "ModelLocation",
    "ModelNotFoundError",
    "ModelUnavailableError",
    "ProviderContractError",
    "ProviderNotFoundError",
    "ProviderRegistry",
]
