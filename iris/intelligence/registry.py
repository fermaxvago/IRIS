"""Explicit instance registry for intelligence providers."""

from __future__ import annotations

from collections.abc import Iterable

from iris.intelligence.contracts import IntelligenceProvider


class DuplicateProviderError(ValueError):
    """Raised when a provider identifier is registered more than once."""


class ProviderNotFoundError(LookupError):
    """Raised when a provider identifier is absent from a registry."""


class ProviderRegistry:
    """Register and discover providers without globals or implicit discovery."""

    def __init__(self, providers: Iterable[IntelligenceProvider] = ()) -> None:
        self._providers: dict[str, IntelligenceProvider] = {}
        for provider in providers:
            self.register(provider)

    def register(self, provider: IntelligenceProvider) -> IntelligenceProvider:
        """Register one provider, rejecting invalid or duplicate identities."""

        provider_id = provider.provider_id
        if not isinstance(provider_id, str):
            raise TypeError("provider_id must be a string")
        if not provider_id.strip():
            raise ValueError("provider_id must not be blank")
        if provider_id != provider_id.strip():
            raise ValueError("provider_id must not contain surrounding whitespace")
        if provider_id in self._providers:
            raise DuplicateProviderError(f"provider already registered: {provider_id}")
        self._providers[provider_id] = provider
        return provider

    def get(self, provider_id: str) -> IntelligenceProvider:
        """Return a provider or fail explicitly when it is unknown."""

        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise ProviderNotFoundError(
                f"provider is not registered: {provider_id}"
            ) from exc

    def list_providers(self) -> tuple[IntelligenceProvider, ...]:
        """Return providers in deterministic identifier order."""

        return tuple(
            self._providers[provider_id] for provider_id in sorted(self._providers)
        )
