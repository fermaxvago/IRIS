"""Concrete intelligence provider adapters."""

from iris.intelligence.providers.ollama import (
    DEFAULT_OLLAMA_ENDPOINT,
    DEFAULT_OLLAMA_PROVIDER_ID,
    DEFAULT_OLLAMA_TIMEOUT_SECONDS,
    OllamaAPIError,
    OllamaInferenceError,
    OllamaOperationalError,
    OllamaProtocolError,
    OllamaProvider,
    OllamaTimeoutError,
    OllamaUnavailableError,
)

__all__ = [
    "DEFAULT_OLLAMA_ENDPOINT",
    "DEFAULT_OLLAMA_PROVIDER_ID",
    "DEFAULT_OLLAMA_TIMEOUT_SECONDS",
    "OllamaAPIError",
    "OllamaInferenceError",
    "OllamaOperationalError",
    "OllamaProtocolError",
    "OllamaProvider",
    "OllamaTimeoutError",
    "OllamaUnavailableError",
]
