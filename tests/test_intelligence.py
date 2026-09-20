from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass, field

import pytest

from iris.intelligence import (
    DuplicateProviderError,
    IntelligenceProvider,
    IntelligenceRequest,
    IntelligenceResult,
    IntelligenceRuntime,
    IntelligenceStatus,
    ModelCapability,
    ModelDescriptor,
    ModelLocation,
    ModelNotFoundError,
    ModelUnavailableError,
    ProviderContractError,
    ProviderNotFoundError,
    ProviderRegistry,
)


def make_model(
    model_id: str = "test-text",
    *,
    provider_id: str = "test-provider",
    available: bool = True,
) -> ModelDescriptor:
    return ModelDescriptor(
        model_id=model_id,
        provider_id=provider_id,
        location=ModelLocation.LOCAL,
        context_window=4096,
        available=available,
        metadata={"family": "test"},
    )


ResultFactory = Callable[[IntelligenceRequest, str], IntelligenceResult]


def successful_result(
    request: IntelligenceRequest,
    provider_id: str,
) -> IntelligenceResult:
    return IntelligenceResult.succeeded(
        request,
        provider_id=provider_id,
        output=f"response: {request.content}",
        metadata={"test": True},
    )


@dataclass
class FakeProvider:
    provider_id: str = "test-provider"
    models: tuple[ModelDescriptor, ...] = field(default_factory=lambda: (make_model(),))
    result_factory: ResultFactory = successful_result
    requests: list[IntelligenceRequest] = field(default_factory=list)

    def list_models(self) -> tuple[ModelDescriptor, ...]:
        return self.models

    def infer(self, request: IntelligenceRequest) -> IntelligenceResult:
        self.requests.append(request)
        return self.result_factory(request, self.provider_id)


def test_intelligence_request_is_validated_copied_and_immutable() -> None:
    metadata = {"correlation": "parent-1"}
    request = IntelligenceRequest(
        content="Explain this state",
        model_id="test-text",
        request_id="request-1",
        metadata=metadata,
    )

    metadata["correlation"] = "changed"

    assert request.content == "Explain this state"
    assert request.model_id == "test-text"
    assert request.request_id == "request-1"
    assert request.metadata["correlation"] == "parent-1"
    with pytest.raises(TypeError):
        request.metadata["new"] = True  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        request.content = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("content", " ", "content must not be blank"),
        ("model_id", "", "model_id must not be blank"),
        ("request_id", " ", "request_id must not be blank"),
    ],
)
def test_intelligence_request_rejects_invalid_values(
    field: str,
    value: str,
    error: str,
) -> None:
    arguments = {
        "content": "hello",
        "model_id": "test-text",
        "request_id": "request-1",
    }
    arguments[field] = value

    with pytest.raises(ValueError, match=error):
        IntelligenceRequest(**arguments)


def test_intelligence_request_generates_a_correlation_identifier() -> None:
    first = IntelligenceRequest(content="first", model_id="test-text")
    second = IntelligenceRequest(content="second", model_id="test-text")

    assert first.request_id
    assert second.request_id
    assert first.request_id != second.request_id


def test_model_descriptor_exposes_small_provider_independent_identity() -> None:
    capabilities = {ModelCapability.TEXT_GENERATION}
    metadata = {"family": "reference"}
    descriptor = ModelDescriptor(
        model_id="local-reference",
        provider_id="local-engine",
        location=ModelLocation.LOCAL,
        capabilities=capabilities,
        context_window=8192,
        metadata=metadata,
    )

    capabilities.clear()
    metadata["family"] = "changed"

    assert descriptor.capabilities == frozenset({ModelCapability.TEXT_GENERATION})
    assert descriptor.metadata["family"] == "reference"
    assert descriptor.context_window == 8192
    assert descriptor.available is True
    with pytest.raises(TypeError):
        descriptor.metadata["new"] = True  # type: ignore[index]


def test_model_descriptor_rejects_invalid_context_or_capabilities() -> None:
    with pytest.raises(ValueError, match="context_window must be positive"):
        ModelDescriptor(
            model_id="test-text",
            provider_id="test-provider",
            location=ModelLocation.CLOUD,
            context_window=0,
        )

    with pytest.raises(TypeError, match="ModelCapability"):
        ModelDescriptor(
            model_id="test-text",
            provider_id="test-provider",
            location=ModelLocation.CLOUD,
            capabilities=frozenset({"vision"}),  # type: ignore[arg-type]
        )


def test_provider_contract_is_structural() -> None:
    assert isinstance(FakeProvider(), IntelligenceProvider)


def test_registry_registers_looks_up_and_lists_deterministically() -> None:
    zulu = FakeProvider(
        provider_id="zulu",
        models=(make_model(provider_id="zulu"),),
    )
    alpha = FakeProvider(
        provider_id="alpha",
        models=(make_model(provider_id="alpha"),),
    )
    registry = ProviderRegistry([zulu])

    registered = registry.register(alpha)

    assert registered is alpha
    assert registry.get("alpha") is alpha
    assert registry.get("zulu") is zulu
    assert [provider.provider_id for provider in registry.list_providers()] == [
        "alpha",
        "zulu",
    ]


def test_registry_rejects_duplicate_provider_identifiers() -> None:
    registry = ProviderRegistry([FakeProvider()])

    with pytest.raises(DuplicateProviderError, match="test-provider"):
        registry.register(FakeProvider())


def test_registry_fails_explicitly_for_unknown_provider() -> None:
    registry = ProviderRegistry()

    with pytest.raises(ProviderNotFoundError, match="missing-provider"):
        registry.get("missing-provider")


def test_runtime_fails_explicitly_for_unknown_provider() -> None:
    runtime = IntelligenceRuntime(ProviderRegistry())
    request = IntelligenceRequest(content="hello", model_id="test-text")

    with pytest.raises(ProviderNotFoundError, match="missing-provider"):
        runtime.execute("missing-provider", request)


def test_runtime_executes_explicit_provider_and_model() -> None:
    provider = FakeProvider()
    runtime = IntelligenceRuntime(ProviderRegistry([provider]))
    request = IntelligenceRequest(
        content="hello",
        model_id="test-text",
        request_id="request-1",
    )

    result = runtime.execute("test-provider", request)

    assert provider.requests == [request]
    assert result.success is True
    assert result.status is IntelligenceStatus.SUCCESS
    assert result.output == "response: hello"
    assert result.request_id == "request-1"
    assert result.provider_id == "test-provider"
    assert result.model_id == "test-text"


def test_runtime_preserves_expected_provider_failure() -> None:
    def expected_failure(
        request: IntelligenceRequest,
        provider_id: str,
    ) -> IntelligenceResult:
        return IntelligenceResult.failed(
            request,
            provider_id=provider_id,
            diagnostic="provider is temporarily unavailable",
            metadata={"retryable": True},
        )

    runtime = IntelligenceRuntime(
        ProviderRegistry([FakeProvider(result_factory=expected_failure)])
    )
    request = IntelligenceRequest(content="hello", model_id="test-text")

    result = runtime.execute("test-provider", request)

    assert result.success is False
    assert result.status is IntelligenceStatus.FAILURE
    assert result.diagnostic == "provider is temporarily unavailable"
    assert result.metadata["retryable"] is True


def test_runtime_rejects_invalid_provider_result() -> None:
    class InvalidResultProvider(FakeProvider):
        def infer(self, request: IntelligenceRequest) -> IntelligenceResult:
            return object()  # type: ignore[return-value]

    runtime = IntelligenceRuntime(ProviderRegistry([InvalidResultProvider()]))
    request = IntelligenceRequest(content="hello", model_id="test-text")

    with pytest.raises(TypeError, match="returned an invalid result"):
        runtime.execute("test-provider", request)


def test_runtime_preserves_unexpected_programming_errors() -> None:
    class BrokenProvider(FakeProvider):
        def infer(self, request: IntelligenceRequest) -> IntelligenceResult:
            raise TypeError("programming defect")

    runtime = IntelligenceRuntime(ProviderRegistry([BrokenProvider()]))
    request = IntelligenceRequest(content="hello", model_id="test-text")

    with pytest.raises(TypeError, match="programming defect"):
        runtime.execute("test-provider", request)


@pytest.mark.parametrize(
    ("changed_field", "error"),
    [
        ("request_id", "request identifier"),
        ("provider_id", "provider result identifier"),
        ("model_id", "model identifier"),
    ],
)
def test_runtime_rejects_inconsistent_result_identity(
    changed_field: str,
    error: str,
) -> None:
    def inconsistent_result(
        request: IntelligenceRequest,
        provider_id: str,
    ) -> IntelligenceResult:
        values = {
            "request_id": request.request_id,
            "provider_id": provider_id,
            "model_id": request.model_id,
        }
        values[changed_field] = "different"
        return IntelligenceResult(
            **values,
            status=IntelligenceStatus.SUCCESS,
            output="invalid identity",
        )

    runtime = IntelligenceRuntime(
        ProviderRegistry([FakeProvider(result_factory=inconsistent_result)])
    )
    request = IntelligenceRequest(content="hello", model_id="test-text")

    with pytest.raises(ProviderContractError, match=error):
        runtime.execute("test-provider", request)


def test_runtime_rejects_unknown_model_before_inference() -> None:
    provider = FakeProvider()
    runtime = IntelligenceRuntime(ProviderRegistry([provider]))
    request = IntelligenceRequest(content="hello", model_id="missing-model")

    with pytest.raises(ModelNotFoundError, match="missing-model"):
        runtime.execute("test-provider", request)

    assert provider.requests == []


def test_runtime_rejects_unavailable_model_before_inference() -> None:
    provider = FakeProvider(models=(make_model(available=False),))
    runtime = IntelligenceRuntime(ProviderRegistry([provider]))
    request = IntelligenceRequest(content="hello", model_id="test-text")

    with pytest.raises(ModelUnavailableError, match="test-text"):
        runtime.execute("test-provider", request)

    assert provider.requests == []


def test_runtime_rejects_inconsistent_model_provider_identity() -> None:
    provider = FakeProvider(models=(make_model(provider_id="different-provider"),))
    runtime = IntelligenceRuntime(ProviderRegistry([provider]))
    request = IntelligenceRequest(content="hello", model_id="test-text")

    with pytest.raises(ProviderContractError, match="descriptor provider identifier"):
        runtime.execute("test-provider", request)


def test_intelligence_result_metadata_is_copied_and_immutable() -> None:
    request = IntelligenceRequest(content="hello", model_id="test-text")
    metadata = {"tokens": 3}

    result = IntelligenceResult.succeeded(
        request,
        provider_id="test-provider",
        output="world",
        metadata=metadata,
    )
    metadata["tokens"] = 100

    assert result.metadata["tokens"] == 3
    with pytest.raises(TypeError):
        result.metadata["new"] = True  # type: ignore[index]


def test_failed_result_requires_a_diagnostic() -> None:
    with pytest.raises(ValueError, match="require a diagnostic"):
        IntelligenceResult(
            request_id="request-1",
            provider_id="test-provider",
            model_id="test-text",
            status=IntelligenceStatus.FAILURE,
        )
