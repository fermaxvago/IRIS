"""Structural contracts for interchangeable intelligence providers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from iris.intelligence.models import (
    IntelligenceRequest,
    IntelligenceResult,
    ModelDescriptor,
)

if TYPE_CHECKING:
    from iris.intelligence.conversation import ConversationRequest


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


@runtime_checkable
class ConversationalIntelligenceProvider(IntelligenceProvider, Protocol):
    """Optional chat capability; infer-only providers remain valid."""

    def chat(self, request: ConversationRequest) -> IntelligenceResult:
        """Generate one assistant response for ordered conversational messages."""
        ...
