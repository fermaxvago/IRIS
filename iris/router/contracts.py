"""Minimal routing contract for future IRIS request handling."""

from typing import Protocol, TypeVar, runtime_checkable

RequestT = TypeVar("RequestT", contravariant=True)
DecisionT = TypeVar("DecisionT", covariant=True)


@runtime_checkable
class Router(Protocol[RequestT, DecisionT]):
    """Decide how an IRIS request should be handled."""

    def route(self, request: RequestT) -> DecisionT:
        """Return a routing decision without executing it."""
        ...
