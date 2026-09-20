"""Typed representation of an input submitted to IRIS."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from uuid import uuid4


def _new_request_id() -> str:
    return uuid4().hex


@dataclass(frozen=True, slots=True)
class Request:
    """A small, provider-independent request entering the IRIS core."""

    content: str
    source: str
    request_id: str = field(default_factory=_new_request_id)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.content, str):
            raise TypeError("content must be a string")
        if not isinstance(self.source, str):
            raise TypeError("source must be a string")
        if not self.source.strip():
            raise ValueError("source must not be blank")
        if not isinstance(self.request_id, str):
            raise TypeError("request_id must be a string")
        if not self.request_id.strip():
            raise ValueError("request_id must not be blank")
        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        if not all(isinstance(key, str) for key in self.metadata):
            raise TypeError("metadata keys must be strings")

        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(dict(self.metadata)),
        )
