"""Inspectable output models for IRIS routing decisions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType


class RouteTarget(StrEnum):
    """Destinations currently understood by the deterministic dispatcher."""

    SYSTEM_STATUS = "system.status"
    CLI_HELP = "cli.help"
    CLI_EXIT = "cli.exit"
    UNKNOWN = "cli.unknown"


@dataclass(frozen=True, slots=True)
class RouteDecision:
    """A Router's explicit, side-effect-free decision for one request."""

    target: RouteTarget
    reason: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.target, RouteTarget):
            raise TypeError("target must be a RouteTarget")
        if not isinstance(self.reason, str):
            raise TypeError("reason must be a string")
        if not self.reason.strip():
            raise ValueError("reason must not be blank")
        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        if not all(isinstance(key, str) for key in self.metadata):
            raise TypeError("metadata keys must be strings")

        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(dict(self.metadata)),
        )
