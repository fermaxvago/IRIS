"""Opt-in integration test against a real Ollama instance."""

from __future__ import annotations

import os

import pytest

from iris.intelligence import (
    ConversationSession,
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


def test_real_ollama_two_turn_conversation() -> None:
    provider = OllamaProvider(
        endpoint=os.getenv("IRIS_OLLAMA_ENDPOINT", "http://127.0.0.1:11434"),
        provider_id=os.getenv("IRIS_OLLAMA_PROVIDER_ID", "ollama-local"),
        timeout=float(os.getenv("IRIS_OLLAMA_TIMEOUT", "120")),
    )
    models = provider.list_models()
    model_id = os.getenv("IRIS_OLLAMA_MODEL", "qwen3:8b")
    assert model_id in {model.model_id for model in models}
    conversation = ConversationSession(
        IntelligenceRuntime(ProviderRegistry([provider])),
        provider_id=provider.provider_id,
        model_id=model_id,
    )
    first = conversation.send("Reply briefly: what is the capital of France?")
    assert first.success, first.diagnostic
    second = conversation.send("Which country was my previous question about?")
    assert second.success, second.diagnostic
    assert conversation.completed_turns == 2
    assert second.output
