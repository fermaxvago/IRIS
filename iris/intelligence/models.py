"""Provider-independent models for generative intelligence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from uuid import uuid4


def _new_request_id() -> str:
    return uuid4().hex


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


def _validate_identifier(value: str, *, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")
    if value != value.strip():
        raise ValueError(f"{field_name} must not contain surrounding whitespace")


class ModelLocation(StrEnum):
    """Execution locations useful to future model selection."""

    LOCAL = "local"
    CLOUD = "cloud"


class ModelCapability(StrEnum):
    """Demonstrable technical capabilities exposed by model descriptors."""

    TEXT_GENERATION = "text_generation"
    EMBEDDING = "embedding"


@dataclass(frozen=True, slots=True)
class IntelligenceRequest:
    """Immutable text inference request independent of provider wire formats."""

    content: str
    model_id: str
    request_id: str = field(default_factory=_new_request_id)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.content, str):
            raise TypeError("content must be a string")
        if not self.content.strip():
            raise ValueError("content must not be blank")
        _validate_identifier(self.model_id, field_name="model_id")
        _validate_identifier(self.request_id, field_name="request_id")
        object.__setattr__(
            self,
            "metadata",
            _freeze_mapping(self.metadata, field_name="metadata"),
        )


@dataclass(frozen=True, slots=True)
class ModelDescriptor:
    """Stable, provider-independent identity for one text model."""

    model_id: str
    provider_id: str
    location: ModelLocation
    capabilities: frozenset[ModelCapability] = field(
        default_factory=lambda: frozenset({ModelCapability.TEXT_GENERATION})
    )
    context_window: int | None = None
    available: bool = True
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_identifier(self.model_id, field_name="model_id")
        _validate_identifier(self.provider_id, field_name="provider_id")
        if not isinstance(self.location, ModelLocation):
            raise TypeError("location must be a ModelLocation")
        if isinstance(self.capabilities, (str, bytes)):
            raise TypeError(
                "capabilities must be a collection of ModelCapability values"
            )
        try:
            capabilities = frozenset(self.capabilities)
        except TypeError as exc:
            raise TypeError(
                "capabilities must be a collection of ModelCapability values"
            ) from exc
        if not capabilities:
            raise ValueError("capabilities must not be empty")
        if not all(
            isinstance(capability, ModelCapability) for capability in capabilities
        ):
            raise TypeError("capabilities must contain ModelCapability values")
        if self.context_window is not None:
            if isinstance(self.context_window, bool) or not isinstance(
                self.context_window, int
            ):
                raise TypeError("context_window must be an integer or None")
            if self.context_window <= 0:
                raise ValueError("context_window must be positive")
        if not isinstance(self.available, bool):
            raise TypeError("available must be a bool")
        object.__setattr__(self, "capabilities", capabilities)
        object.__setattr__(
            self,
            "metadata",
            _freeze_mapping(self.metadata, field_name="metadata"),
        )


class IntelligenceStatus(StrEnum):
    """Inspectable outcome state for one inference request."""

    SUCCESS = "success"
    FAILURE = "failure"


@dataclass(frozen=True, slots=True)
class IntelligenceResult:
    """Structured, provider-independent result from an inference provider."""

    request_id: str
    provider_id: str
    model_id: str
    status: IntelligenceStatus
    output: str | None = None
    diagnostic: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_identifier(self.request_id, field_name="request_id")
        _validate_identifier(self.provider_id, field_name="provider_id")
        _validate_identifier(self.model_id, field_name="model_id")
        if not isinstance(self.status, IntelligenceStatus):
            raise TypeError("status must be an IntelligenceStatus")
        if self.output is not None and not isinstance(self.output, str):
            raise TypeError("output must be a string or None")
        if self.diagnostic is not None:
            if not isinstance(self.diagnostic, str):
                raise TypeError("diagnostic must be a string or None")
            if not self.diagnostic.strip():
                raise ValueError("diagnostic must not be blank")
        if self.status is IntelligenceStatus.SUCCESS and self.output is None:
            raise ValueError("successful results require textual output")
        if self.status is IntelligenceStatus.FAILURE and self.diagnostic is None:
            raise ValueError("failed results require a diagnostic")
        object.__setattr__(
            self,
            "metadata",
            _freeze_mapping(self.metadata, field_name="metadata"),
        )

    @property
    def success(self) -> bool:
        """Return whether inference completed successfully."""

        return self.status is IntelligenceStatus.SUCCESS

    @classmethod
    def succeeded(
        cls,
        request: IntelligenceRequest,
        *,
        provider_id: str,
        output: str,
        metadata: Mapping[str, object] | None = None,
    ) -> IntelligenceResult:
        """Build a successful result for an explicit request identity."""

        return cls(
            request_id=request.request_id,
            provider_id=provider_id,
            model_id=request.model_id,
            status=IntelligenceStatus.SUCCESS,
            output=output,
            metadata={} if metadata is None else metadata,
        )

    @classmethod
    def failed(
        cls,
        request: IntelligenceRequest,
        *,
        provider_id: str,
        diagnostic: str,
        metadata: Mapping[str, object] | None = None,
    ) -> IntelligenceResult:
        """Build an expected failure for an explicit request identity."""

        return cls(
            request_id=request.request_id,
            provider_id=provider_id,
            model_id=request.model_id,
            status=IntelligenceStatus.FAILURE,
            diagnostic=diagnostic,
            metadata={} if metadata is None else metadata,
        )
