"""Inference runtime for an explicitly selected provider and model."""

from iris.intelligence.contracts import IntelligenceProvider
from iris.intelligence.models import (
    IntelligenceRequest,
    IntelligenceResult,
    ModelDescriptor,
)
from iris.intelligence.registry import ProviderRegistry


class ModelNotFoundError(LookupError):
    """Raised when a selected provider does not expose the requested model."""


class ModelUnavailableError(RuntimeError):
    """Raised when an explicitly selected model is currently unavailable."""


class ProviderContractError(ValueError):
    """Raised when a provider violates the IntelligenceProvider contract."""


class IntelligenceRuntime:
    """Execute inference without choosing providers or models automatically."""

    def __init__(self, registry: ProviderRegistry) -> None:
        self._registry = registry

    def execute(
        self,
        provider_id: str,
        request: IntelligenceRequest,
    ) -> IntelligenceResult:
        """Execute one explicit inference request and validate provider output.

        Providers represent expected operational failures with a failed
        ``IntelligenceResult``. Unexpected exceptions and contract violations
        remain visible instead of being disguised as successful output.
        """

        if not isinstance(request, IntelligenceRequest):
            raise TypeError("request must be an IntelligenceRequest")
        provider = self._registry.get(provider_id)
        model = self._find_model(provider, provider_id, request.model_id)
        if not model.available:
            raise ModelUnavailableError(
                f"model is not available: {provider_id}/{request.model_id}"
            )

        result = provider.infer(request)
        if not isinstance(result, IntelligenceResult):
            raise TypeError(f"provider {provider_id} returned an invalid result")
        if result.request_id != request.request_id:
            raise ProviderContractError(
                "provider result request identifier does not match the request"
            )
        if result.provider_id != provider_id:
            raise ProviderContractError(
                "provider result identifier does not match the invocation"
            )
        if result.model_id != request.model_id:
            raise ProviderContractError(
                "provider result model identifier does not match the request"
            )
        return result

    @staticmethod
    def _find_model(
        provider: IntelligenceProvider,
        provider_id: str,
        model_id: str,
    ) -> ModelDescriptor:
        models = provider.list_models()
        if not isinstance(models, tuple):
            raise ProviderContractError("provider models must be returned as a tuple")

        selected: ModelDescriptor | None = None
        seen_model_ids: set[str] = set()
        for model in models:
            if not isinstance(model, ModelDescriptor):
                raise ProviderContractError(
                    "provider model listings must contain ModelDescriptor values"
                )
            if model.provider_id != provider_id:
                raise ProviderContractError(
                    "model descriptor provider identifier does not match provider"
                )
            if model.model_id in seen_model_ids:
                raise ProviderContractError(
                    f"provider exposes duplicate model identifier: {model.model_id}"
                )
            seen_model_ids.add(model.model_id)
            if model.model_id == model_id:
                selected = model

        if selected is None:
            raise ModelNotFoundError(
                f"model is not exposed by provider: {provider_id}/{model_id}"
            )
        return selected
