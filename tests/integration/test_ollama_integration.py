"""Opt-in integration test against a real Ollama instance."""

from __future__ import annotations

import os

import pytest

from iris.intelligence import (
    IntelligenceRequest,
    IntelligenceRuntime,
    ProviderRegistry,
)
from iris.intelligence.providers import OllamaProvider

pytestmark = pytest.mark.integration

if os.getenv("IRIS_RUN_OLLAMA_INTEGRATION") != "1":
    pytest.skip(
        "set IRIS_RUN_OLLAMA_INTEGRATION=1 to use a real Ollama server",
        allow_module_level=True,
    )


def test_real_ollama_inference_path() -> None:
    endpoint = os.getenv("IRIS_OLLAMA_ENDPOINT", "http://127.0.0.1:11434")
    provider_id = os.getenv("IRIS_OLLAMA_PROVIDER_ID", "ollama-local")
    model_id = os.getenv("IRIS_OLLAMA_MODEL", "qwen3:8b")
    timeout = float(os.getenv("IRIS_OLLAMA_TIMEOUT", "120"))
    provider = OllamaProvider(
        endpoint=endpoint,
        provider_id=provider_id,
        timeout=timeout,
    )

    models = provider.list_models()
    assert model_id in {model.model_id for model in models}

    runtime = IntelligenceRuntime(ProviderRegistry([provider]))
    result = runtime.execute(
        provider_id,
        IntelligenceRequest(
            content="Reply with exactly: IRIS local intelligence OK",
            model_id=model_id,
        ),
    )

    assert result.success, result.diagnostic
    assert result.output
