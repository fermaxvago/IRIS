from __future__ import annotations

import json
from dataclasses import dataclass, field
from urllib.error import URLError

import pytest

from iris.intelligence import (
    IntelligenceProvider,
    IntelligenceRequest,
    IntelligenceRuntime,
    ModelCapability,
    ModelLocation,
    ModelNotFoundError,
    ProviderRegistry,
)
from iris.intelligence.providers import (
    DEFAULT_OLLAMA_ENDPOINT,
    DEFAULT_OLLAMA_PROVIDER_ID,
    DEFAULT_OLLAMA_TIMEOUT_SECONDS,
    OllamaAPIError,
    OllamaProtocolError,
    OllamaProvider,
    OllamaTimeoutError,
    OllamaUnavailableError,
)


@dataclass(frozen=True)
class RecordedCall:
    method: str
    url: str
    body: bytes | None
    timeout: float


@dataclass
class StubTransport:
    responses: list[tuple[int, bytes] | BaseException]
    calls: list[RecordedCall] = field(default_factory=list)

    def __call__(
        self,
        method: str,
        url: str,
        body: bytes | None,
        timeout: float,
    ) -> tuple[int, bytes]:
        self.calls.append(RecordedCall(method, url, body, timeout))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def json_response(payload: object, status: int = 200) -> tuple[int, bytes]:
    return status, json.dumps(payload).encode("utf-8")


def model_entry(model_id: str = "qwen3:8b") -> dict[str, object]:
    return {
        "name": model_id,
        "model": model_id,
        "modified_at": "2026-09-22T10:00:00Z",
        "size": 5_200_000_000,
        "digest": "sha256-reference",
        "details": {
            "format": "gguf",
            "family": "qwen3",
            "families": ["qwen3"],
            "parameter_size": "8.2B",
            "quantization_level": "Q4_K_M",
        },
    }


def model_details(
    *,
    capabilities: list[str] | None = None,
) -> dict[str, object]:
    return {
        "capabilities": capabilities or ["completion"],
        "details": {
            "format": "gguf",
            "family": "qwen3",
            "families": ["qwen3"],
            "parameter_size": "8.2B",
            "quantization_level": "Q4_K_M",
        },
        "model_info": {
            "general.architecture": "qwen3",
            "qwen3.context_length": 40_960,
        },
    }


def generation_response(model_id: str = "qwen3:8b") -> dict[str, object]:
    return {
        "model": model_id,
        "created_at": "2026-09-22T10:01:00Z",
        "response": "IRIS local intelligence OK",
        "done": True,
        "done_reason": "stop",
        "total_duration": 2_000_000_000,
        "load_duration": 500_000_000,
        "prompt_eval_count": 8,
        "prompt_eval_cached_count": 2,
        "prompt_eval_duration": 100_000_000,
        "eval_count": 5,
        "eval_duration": 1_000_000_000,
    }


def test_provider_has_explicit_identity_and_configuration() -> None:
    provider = OllamaProvider()

    assert provider.provider_id == DEFAULT_OLLAMA_PROVIDER_ID
    assert provider.endpoint == DEFAULT_OLLAMA_ENDPOINT
    assert provider.timeout == DEFAULT_OLLAMA_TIMEOUT_SECONDS
    assert isinstance(provider, IntelligenceProvider)


def test_provider_supports_multiple_explicit_ollama_instances() -> None:
    transport = StubTransport([json_response({"models": []})])
    provider = OllamaProvider(
        provider_id="ollama-fercore",
        endpoint="http://10.0.0.25:11434/",
        timeout=45,
        _transport=transport,
    )

    assert provider.provider_id == "ollama-fercore"
    assert provider.endpoint == "http://10.0.0.25:11434"
    assert provider.timeout == 45.0

    assert provider.list_models() == ()
    assert transport.calls[0] == RecordedCall(
        "GET",
        "http://10.0.0.25:11434/api/tags",
        None,
        45.0,
    )


@pytest.mark.parametrize(
    ("arguments", "error"),
    [
        ({"provider_id": " "}, "provider_id must not be blank"),
        ({"endpoint": "localhost:11434"}, "absolute HTTP"),
        ({"endpoint": "http://user:secret@localhost:11434"}, "credentials"),
        ({"timeout": 0}, "timeout must be finite and positive"),
        ({"timeout": float("inf")}, "timeout must be finite and positive"),
    ],
)
def test_provider_rejects_invalid_configuration(
    arguments: dict[str, object],
    error: str,
) -> None:
    with pytest.raises((TypeError, ValueError), match=error):
        OllamaProvider(**arguments)  # type: ignore[arg-type]


def test_model_discovery_translates_only_demonstrated_text_models() -> None:
    embedding = model_entry("nomic-embed-text:latest")
    transport = StubTransport(
        [
            json_response({"models": [embedding, model_entry()]}),
            json_response(model_details(capabilities=["embedding"])),
            json_response(model_details(capabilities=["completion", "tools"])),
        ]
    )
    provider = OllamaProvider(_transport=transport)

    models = provider.list_models()

    assert len(models) == 1
    model = models[0]
    assert model.model_id == "qwen3:8b"
    assert model.provider_id == "ollama-local"
    assert model.location is ModelLocation.LOCAL
    assert model.available is True
    assert model.capabilities == frozenset({ModelCapability.TEXT_GENERATION})
    assert model.context_window == 40_960
    assert model.metadata == {
        "ollama.capabilities": ("completion", "tools"),
        "ollama.name": "qwen3:8b",
        "ollama.digest": "sha256-reference",
        "ollama.modified_at": "2026-09-22T10:00:00Z",
        "ollama.size_bytes": 5_200_000_000,
        "ollama.format": "gguf",
        "ollama.family": "qwen3",
        "ollama.parameter_size": "8.2B",
        "ollama.quantization_level": "Q4_K_M",
        "ollama.families": ("qwen3",),
    }
    assert [call.url for call in transport.calls] == [
        "http://127.0.0.1:11434/api/tags",
        "http://127.0.0.1:11434/api/show",
        "http://127.0.0.1:11434/api/show",
    ]
    assert json.loads(transport.calls[1].body or b"") == {
        "model": "nomic-embed-text:latest"
    }
    assert json.loads(transport.calls[2].body or b"") == {"model": "qwen3:8b"}


def test_model_discovery_is_deterministic() -> None:
    transport = StubTransport(
        [
            json_response(
                {"models": [model_entry("zulu:latest"), model_entry("alpha:latest")]}
            ),
            json_response(model_details()),
            json_response(model_details()),
        ]
    )
    provider = OllamaProvider(_transport=transport)

    assert [model.model_id for model in provider.list_models()] == [
        "alpha:latest",
        "zulu:latest",
    ]


def test_successful_inference_is_normalized_without_hidden_selection() -> None:
    transport = StubTransport([json_response(generation_response())])
    provider = OllamaProvider(_transport=transport)
    request = IntelligenceRequest(
        content="Confirm local inference",
        model_id="qwen3:8b",
        request_id="request-ollama-1",
        metadata={"private": "not forwarded"},
    )

    result = provider.infer(request)

    assert result.success is True
    assert result.request_id == "request-ollama-1"
    assert result.provider_id == "ollama-local"
    assert result.model_id == "qwen3:8b"
    assert result.output == "IRIS local intelligence OK"
    assert result.metadata == {
        "ollama.created_at": "2026-09-22T10:01:00Z",
        "ollama.done_reason": "stop",
        "ollama.total_duration_ns": 2_000_000_000,
        "ollama.load_duration_ns": 500_000_000,
        "ollama.prompt_eval_count": 8,
        "ollama.prompt_eval_cached_count": 2,
        "ollama.prompt_eval_duration_ns": 100_000_000,
        "ollama.eval_count": 5,
        "ollama.eval_duration_ns": 1_000_000_000,
    }
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call.method == "POST"
    assert call.url.endswith("/api/generate")
    assert json.loads(call.body or b"") == {
        "model": "qwen3:8b",
        "prompt": "Confirm local inference",
        "stream": False,
    }


def test_real_provider_path_executes_through_intelligence_runtime() -> None:
    transport = StubTransport(
        [
            json_response({"models": [model_entry()]}),
            json_response(model_details()),
            json_response(generation_response()),
        ]
    )
    provider = OllamaProvider(_transport=transport)
    runtime = IntelligenceRuntime(ProviderRegistry([provider]))
    request = IntelligenceRequest(content="hello", model_id="qwen3:8b")

    result = runtime.execute("ollama-local", request)

    assert result.success is True
    assert result.output == "IRIS local intelligence OK"
    assert [call.url.rsplit("/", 1)[-1] for call in transport.calls] == [
        "tags",
        "show",
        "generate",
    ]


def test_discovery_distinguishes_unavailable_provider() -> None:
    transport = StubTransport([URLError(ConnectionRefusedError())])
    provider = OllamaProvider(_transport=transport)

    with pytest.raises(OllamaUnavailableError, match="unavailable"):
        provider.list_models()


def test_discovery_distinguishes_timeout() -> None:
    transport = StubTransport([TimeoutError("timed out")])
    provider = OllamaProvider(timeout=7.5, _transport=transport)

    with pytest.raises(OllamaTimeoutError, match="7.5 seconds"):
        provider.list_models()


def test_discovery_reports_http_api_failure() -> None:
    transport = StubTransport([json_response({"error": "backend failed"}, status=500)])
    provider = OllamaProvider(_transport=transport)

    with pytest.raises(OllamaAPIError, match="backend failed") as error:
        provider.list_models()

    assert error.value.status_code == 500


@pytest.mark.parametrize(
    "payload",
    [
        b"not-json",
        json.dumps([]).encode(),
        json.dumps({"unexpected": []}).encode(),
    ],
)
def test_discovery_rejects_malformed_responses(payload: bytes) -> None:
    transport = StubTransport([(200, payload)])
    provider = OllamaProvider(_transport=transport)

    with pytest.raises(OllamaProtocolError):
        provider.list_models()


def test_runtime_distinguishes_absent_model_without_inference_or_fallback() -> None:
    transport = StubTransport([json_response({"models": []})])
    provider = OllamaProvider(_transport=transport)
    runtime = IntelligenceRuntime(ProviderRegistry([provider]))
    request = IntelligenceRequest(content="hello", model_id="missing:latest")

    with pytest.raises(ModelNotFoundError, match="missing:latest"):
        runtime.execute("ollama-local", request)

    assert [call.url for call in transport.calls] == ["http://127.0.0.1:11434/api/tags"]


@pytest.mark.parametrize(
    ("failure", "failure_kind"),
    [
        (URLError(ConnectionRefusedError()), "provider_unavailable"),
        (TimeoutError("timed out"), "timeout"),
    ],
)
def test_inference_normalizes_transport_failures(
    failure: BaseException,
    failure_kind: str,
) -> None:
    transport = StubTransport([failure])
    provider = OllamaProvider(_transport=transport)
    request = IntelligenceRequest(content="hello", model_id="qwen3:8b")

    result = provider.infer(request)

    assert result.success is False
    assert result.metadata["failure_kind"] == failure_kind
    assert result.metadata["ollama.endpoint"] == DEFAULT_OLLAMA_ENDPOINT
    assert result.diagnostic


@pytest.mark.parametrize(
    ("status", "failure_kind"),
    [(404, "model_not_found"), (500, "api_error")],
)
def test_inference_normalizes_http_failures(
    status: int,
    failure_kind: str,
) -> None:
    transport = StubTransport(
        [json_response({"error": "model unavailable"}, status=status)]
    )
    provider = OllamaProvider(_transport=transport)
    request = IntelligenceRequest(content="hello", model_id="qwen3:8b")

    result = provider.infer(request)

    assert result.success is False
    assert result.metadata["failure_kind"] == failure_kind
    assert result.metadata["ollama.http_status"] == status
    assert "model unavailable" in (result.diagnostic or "")


@pytest.mark.parametrize(
    "response",
    [
        (200, b"not-json"),
        json_response({"model": "qwen3:8b", "response": "partial", "done": False}),
        json_response({"model": "different:latest", "response": "wrong", "done": True}),
        json_response({"error": "generation rejected"}),
    ],
)
def test_inference_normalizes_backend_protocol_failures(
    response: tuple[int, bytes],
) -> None:
    transport = StubTransport([response])
    provider = OllamaProvider(_transport=transport)
    request = IntelligenceRequest(content="hello", model_id="qwen3:8b")

    result = provider.infer(request)

    assert result.success is False
    assert result.metadata["failure_kind"] in {
        "inference_rejected",
        "protocol_error",
    }
    assert result.request_id == request.request_id
    assert result.provider_id == provider.provider_id
    assert result.model_id == request.model_id


def test_unexpected_transport_programming_error_remains_visible() -> None:
    transport = StubTransport([TypeError("programming defect")])
    provider = OllamaProvider(_transport=transport)
    request = IntelligenceRequest(content="hello", model_id="qwen3:8b")

    with pytest.raises(TypeError, match="programming defect"):
        provider.infer(request)
