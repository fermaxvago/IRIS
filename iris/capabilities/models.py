"""Typed, inspectable models for executable capabilities."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType


def _freeze_mapping(
    value: Mapping[str, object],
    *,
    field_name: str,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    if not all(isinstance(key, str) for key in value):
        raise TypeError(f"{field_name} keys must be strings")
    return MappingProxyType(dict(value))


class CapabilityKind(StrEnum):
    """Kinds currently executable by the capability runtime."""

    TOOL = "tool"


@dataclass(frozen=True, slots=True)
class CapabilityDescriptor:
    """Stable identity and discovery information for one capability."""

    capability_id: str
    description: str
    kind: CapabilityKind
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.capability_id, str):
            raise TypeError("capability_id must be a string")
        if not self.capability_id.strip():
            raise ValueError("capability_id must not be blank")
        if self.capability_id != self.capability_id.strip():
            raise ValueError("capability_id must not contain surrounding whitespace")
        if not isinstance(self.description, str):
            raise TypeError("description must be a string")
        if not self.description.strip():
            raise ValueError("description must not be blank")
        if not isinstance(self.kind, CapabilityKind):
            raise TypeError("kind must be a CapabilityKind")
        object.__setattr__(
            self,
            "metadata",
            _freeze_mapping(self.metadata, field_name="metadata"),
        )


@dataclass(frozen=True, slots=True)
class CapabilityInput:
    """Explicit input supplied to a single capability invocation."""

    payload: Mapping[str, object] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "payload",
            _freeze_mapping(self.payload, field_name="payload"),
        )
        object.__setattr__(
            self,
            "metadata",
            _freeze_mapping(self.metadata, field_name="metadata"),
        )


class ExecutionStatus(StrEnum):
    """Inspectable outcome state for a capability invocation."""

    SUCCESS = "success"
    FAILURE = "failure"


@dataclass(frozen=True, slots=True)
class CapabilityResult:
    """Structured output from an executable capability."""

    capability_id: str
    status: ExecutionStatus
    output: object | None = None
    diagnostic: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.capability_id, str):
            raise TypeError("capability_id must be a string")
        if not self.capability_id.strip():
            raise ValueError("capability_id must not be blank")
        if not isinstance(self.status, ExecutionStatus):
            raise TypeError("status must be an ExecutionStatus")
        if self.diagnostic is not None:
            if not isinstance(self.diagnostic, str):
                raise TypeError("diagnostic must be a string or None")
            if not self.diagnostic.strip():
                raise ValueError("diagnostic must not be blank")
        if self.status is ExecutionStatus.FAILURE and self.diagnostic is None:
            raise ValueError("failed results require a diagnostic")
        object.__setattr__(
            self,
            "metadata",
            _freeze_mapping(self.metadata, field_name="metadata"),
        )

    @property
    def success(self) -> bool:
        """Return whether the capability completed successfully."""

        return self.status is ExecutionStatus.SUCCESS

    @classmethod
    def succeeded(
        cls,
        capability_id: str,
        *,
        output: object | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> CapabilityResult:
        """Build a successful result."""

        return cls(
            capability_id=capability_id,
            status=ExecutionStatus.SUCCESS,
            output=output,
            metadata={} if metadata is None else metadata,
        )

    @classmethod
    def failed(
        cls,
        capability_id: str,
        *,
        diagnostic: str,
        output: object | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> CapabilityResult:
        """Build an expected, inspectable failure result."""

        return cls(
            capability_id=capability_id,
            status=ExecutionStatus.FAILURE,
            output=output,
            diagnostic=diagnostic,
            metadata={} if metadata is None else metadata,
        )
