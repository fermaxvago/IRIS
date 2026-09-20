"""Structural contract for interchangeable intelligence providers."""

from typing import Protocol, runtime_checkable

from iris.intelligence.models import (
    IntelligenceRequest,
    IntelligenceResult,
    ModelDescriptor,
)


@runtime_checkable
class IntelligenceProvider(Protocol):
    """A backend that performs inference for explicitly described models."""

    @property
    def provider_id(self) -> str:
        """Return the provider's stable registry identifier."""
        ...

    def list_models(self) -> tuple[ModelDescriptor, ...]:
        """Return the models currently exposed by this provider."""
        ...

    def infer(self, request: IntelligenceRequest) -> IntelligenceResult:
        """Execute one text inference request without selecting another model."""
        ...
