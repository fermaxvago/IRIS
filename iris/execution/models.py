"""Immutable models at the explicit IRIS side-effect boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime
from enum import Enum, StrEnum
from types import MappingProxyType
from typing import TypeAlias, cast

from iris.capabilities import CapabilityInput
from iris.core import Request
from iris.intelligence import IntelligenceResource
from iris.memory import MemoryCandidate, MemoryQuery
from iris.memory.models import identifier, utc_time, vocabulary
from iris.orchestrator import (
    MemoryOperation,
    OrchestrationDecision,
    OrchestrationReason,
    OrchestrationTarget,
)

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | tuple["JsonValue", ...] | Mapping[str, "JsonValue"]


def _freeze_json(value: object, *, field_name: str) -> JsonValue:
    """Copy a JSON-like value into an immutable representation."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return utc_time(value, field_name).isoformat()
    if isinstance(value, Enum):
        return _freeze_json(value.value, field_name=field_name)
    if is_dataclass(value) and not isinstance(value, type):
        return MappingProxyType(
            {
                item.name: _freeze_json(
                    getattr(value, item.name), field_name=f"{field_name}.{item.name}"
                )
                for item in fields(value)
            }
        )
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError(f"{field_name} keys must be strings")
        return MappingProxyType(
            {
                key: _freeze_json(item, field_name=f"{field_name}.{key}")
                for key, item in value.items()
            }
        )
    if isinstance(value, (tuple, list)):
        return tuple(
            _freeze_json(item, field_name=f"{field_name} item") for item in value
        )
    if isinstance(value, (set, frozenset)):
        frozen = tuple(
            _freeze_json(item, field_name=f"{field_name} item") for item in value
        )
        try:
            return tuple(sorted(frozen, key=repr))
        except TypeError as exc:  # pragma: no cover - defensive for exotic values
            raise TypeError(f"{field_name} must be JSON-compatible") from exc
    raise TypeError(f"{field_name} must be JSON-compatible")


def _thaw_json(value: JsonValue) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


class ExecutionStatus(StrEnum):
    """Observable state of one coordinator call."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"
    NOT_EXECUTED = "not_executed"


@dataclass(frozen=True, slots=True)
class ExecutionOutput:
    """Small JSON-compatible output envelope, not an artifact store."""

    value: object = None
    reference: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "value", _freeze_json(self.value, field_name="execution output")
        )
        if self.reference is not None:
            identifier(self.reference, "output reference")

    def to_data(self) -> dict[str, object]:
        return {
            "value": _thaw_json(cast(JsonValue, self.value)),
            "reference": self.reference,
        }


@dataclass(frozen=True, slots=True)
class ExecutionFailure:
    """Structured expected domain or operational failure."""

    code: str
    message: str
    details: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        vocabulary(self.code, "failure code")
        if not isinstance(self.message, str):
            raise TypeError("failure message must be a string")
        if not self.message.strip():
            raise ValueError("failure message must not be blank")
        frozen = _freeze_json(self.details, field_name="failure details")
        if not isinstance(frozen, Mapping):  # pragma: no cover - guaranteed by input
            raise TypeError("failure details must be a mapping")
        object.__setattr__(self, "details", frozen)

    def to_data(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "details": _thaw_json(cast(JsonValue, self.details)),
        }


@dataclass(frozen=True, slots=True)
class SystemExecutionInput:
    """Original request needed by the existing deterministic dispatcher."""

    request: Request

    def __post_init__(self) -> None:
        if not isinstance(self.request, Request):
            raise TypeError("request must be a Request")


@dataclass(frozen=True, slots=True)
class CapabilityExecutionInput:
    """Explicit input for an already-selected capability."""

    invocation: CapabilityInput = field(default_factory=CapabilityInput)

    def __post_init__(self) -> None:
        if not isinstance(self.invocation, CapabilityInput):
            raise TypeError("invocation must be a CapabilityInput")


@dataclass(frozen=True, slots=True)
class IntelligenceExecutionInput:
    """Inference content plus caller-supplied resources for existing routing."""

    content: str
    resources: tuple[IntelligenceResource, ...]
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.content, str):
            raise TypeError("content must be a string")
        if not self.content.strip():
            raise ValueError("content must not be blank")
        if not isinstance(self.resources, tuple) or any(
            not isinstance(item, IntelligenceResource) for item in self.resources
        ):
            raise TypeError("resources must be a tuple of IntelligenceResource")
        frozen = _freeze_json(self.metadata, field_name="intelligence metadata")
        if not isinstance(frozen, Mapping):  # pragma: no cover - guaranteed by input
            raise TypeError("intelligence metadata must be a mapping")
        object.__setattr__(self, "metadata", frozen)


@dataclass(frozen=True, slots=True)
class MemoryExecutionInput:
    """Operands for exactly one existing MemoryService operation."""

    memory_id: str | None = None
    query: MemoryQuery | None = None
    candidate: MemoryCandidate | None = None

    def __post_init__(self) -> None:
        if self.memory_id is not None:
            identifier(self.memory_id, "memory_id")
        if self.query is not None and not isinstance(self.query, MemoryQuery):
            raise TypeError("query must be a MemoryQuery or None")
        if self.candidate is not None and not isinstance(
            self.candidate, MemoryCandidate
        ):
            raise TypeError("candidate must be a MemoryCandidate or None")


ExecutionInput: TypeAlias = (
    SystemExecutionInput
    | MemoryExecutionInput
    | CapabilityExecutionInput
    | IntelligenceExecutionInput
)


_INPUT_BY_TARGET = {
    OrchestrationTarget.SYSTEM: SystemExecutionInput,
    OrchestrationTarget.MEMORY: MemoryExecutionInput,
    OrchestrationTarget.CAPABILITY: CapabilityExecutionInput,
    OrchestrationTarget.INTELLIGENCE: IntelligenceExecutionInput,
}


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    """One explicit request to cross the execution side-effect boundary."""

    execution_id: str
    decision: OrchestrationDecision
    created_at: datetime
    execution_input: ExecutionInput | None = None

    def __post_init__(self) -> None:
        identifier(self.execution_id, "execution_id")
        if not isinstance(self.decision, OrchestrationDecision):
            raise TypeError("decision must be an OrchestrationDecision")
        created_at = utc_time(self.created_at, "created_at")
        object.__setattr__(self, "created_at", created_at)
        if created_at < self.decision.created_at:
            raise ValueError("execution request cannot predate its decision")
        expected = _INPUT_BY_TARGET.get(self.decision.target)
        if expected is None:
            if self.execution_input is not None:
                raise ValueError("terminal decisions cannot contain execution input")
            return
        if not isinstance(self.execution_input, expected):
            raise TypeError(
                f"{self.decision.target.value} execution requires {expected.__name__}"
            )
        self._validate_linkage()

    def _validate_linkage(self) -> None:
        requirement = self.decision.requirement
        if requirement is None:
            raise ValueError("executable decisions require a handling requirement")
        if self.decision.target is OrchestrationTarget.SYSTEM:
            system_input = self.execution_input
            assert isinstance(system_input, SystemExecutionInput)
            if system_input.request.request_id != self.decision.request_id:
                raise ValueError("system request identifier does not match decision")
        if self.decision.target is OrchestrationTarget.MEMORY:
            memory_input = self.execution_input
            assert isinstance(memory_input, MemoryExecutionInput)
            _validate_memory_input(requirement.memory_operation, memory_input)

    def to_trace(self) -> dict[str, object]:
        """Return identity and input descriptors without runtime objects."""

        input_trace: dict[str, object] | None = None
        if isinstance(self.execution_input, SystemExecutionInput):
            input_trace = {
                "kind": "system",
                "request_id": self.execution_input.request.request_id,
                "source": self.execution_input.request.source,
            }
        elif isinstance(self.execution_input, MemoryExecutionInput):
            input_trace = {
                "kind": "memory",
                "memory_id": self.execution_input.memory_id,
                "has_query": self.execution_input.query is not None,
                "has_candidate": self.execution_input.candidate is not None,
            }
        elif isinstance(self.execution_input, CapabilityExecutionInput):
            input_trace = {
                "kind": "capability",
                "payload_keys": sorted(self.execution_input.invocation.payload),
                "metadata_keys": sorted(self.execution_input.invocation.metadata),
            }
        elif isinstance(self.execution_input, IntelligenceExecutionInput):
            input_trace = {
                "kind": "intelligence",
                "resources": [
                    {
                        "provider_id": item.provider_id,
                        "model_id": item.model_id,
                        "location": item.model.location.value,
                    }
                    for item in self.execution_input.resources
                ],
                "metadata_keys": sorted(self.execution_input.metadata),
            }
        return {
            "execution_id": self.execution_id,
            "created_at": self.created_at.isoformat(),
            "decision": self.decision.to_trace(),
            "execution_input": input_trace,
        }


def _validate_memory_input(
    operation: MemoryOperation | None, memory_input: MemoryExecutionInput
) -> None:
    if operation is None:
        raise ValueError("memory decision lacks an operation")
    populated = {
        "memory_id": memory_input.memory_id is not None,
        "query": memory_input.query is not None,
        "candidate": memory_input.candidate is not None,
    }
    required = {
        MemoryOperation.RECALL: {"memory_id"},
        MemoryOperation.QUERY: {"query"},
        MemoryOperation.STORE: {"candidate"},
        MemoryOperation.FORGET: {"memory_id"},
        MemoryOperation.SUPERSEDE: {"memory_id", "candidate"},
    }[operation]
    actual = {name for name, present in populated.items() if present}
    if actual != required:
        raise ValueError(
            f"{operation.value} memory execution requires exactly {sorted(required)}"
        )


@dataclass(frozen=True, slots=True)
class HandlerOutcome:
    """Validated handler-neutral result before coordinator timestamps are added."""

    status: ExecutionStatus
    output: ExecutionOutput | None = None
    failure: ExecutionFailure | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.status, ExecutionStatus):
            raise TypeError("status must be an ExecutionStatus")
        if self.status is ExecutionStatus.NOT_EXECUTED:
            raise ValueError("invoked handlers cannot return NOT_EXECUTED")
        if self.output is not None and not isinstance(self.output, ExecutionOutput):
            raise TypeError("output must be an ExecutionOutput or None")
        if self.failure is not None and not isinstance(self.failure, ExecutionFailure):
            raise TypeError("failure must be an ExecutionFailure or None")
        if self.status is ExecutionStatus.SUCCEEDED and self.failure is not None:
            raise ValueError("successful outcomes cannot contain a failure")
        if self.status in {ExecutionStatus.FAILED, ExecutionStatus.REJECTED} and (
            self.failure is None
        ):
            raise ValueError("failed/rejected outcomes require failure information")
        frozen = _freeze_json(self.metadata, field_name="handler metadata")
        if not isinstance(frozen, Mapping):  # pragma: no cover - guaranteed by input
            raise TypeError("handler metadata must be a mapping")
        object.__setattr__(self, "metadata", frozen)


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Observable result of at most one selected-handler invocation."""

    execution_id: str
    decision_id: str
    request_id: str
    context_snapshot_id: str
    target: OrchestrationTarget
    decision_reason: OrchestrationReason
    status: ExecutionStatus
    handler_reference: str | None
    started_at: datetime
    completed_at: datetime
    output: ExecutionOutput | None = None
    failure: ExecutionFailure | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for value, name in (
            (self.execution_id, "execution_id"),
            (self.decision_id, "decision_id"),
            (self.request_id, "request_id"),
            (self.context_snapshot_id, "context_snapshot_id"),
        ):
            identifier(value, name)
        if not isinstance(self.target, OrchestrationTarget):
            raise TypeError("target must be an OrchestrationTarget")
        if not isinstance(self.decision_reason, OrchestrationReason):
            raise TypeError("decision_reason must be an OrchestrationReason")
        if self.decision_reason not in _REASONS_BY_TARGET[self.target]:
            raise ValueError("decision_reason is incompatible with execution target")
        if not isinstance(self.status, ExecutionStatus):
            raise TypeError("status must be an ExecutionStatus")
        started = utc_time(self.started_at, "started_at")
        completed = utc_time(self.completed_at, "completed_at")
        if completed < started:
            raise ValueError("completed_at cannot predate started_at")
        object.__setattr__(self, "started_at", started)
        object.__setattr__(self, "completed_at", completed)
        if self.handler_reference is not None:
            identifier(self.handler_reference, "handler reference")
        if self.output is not None and not isinstance(self.output, ExecutionOutput):
            raise TypeError("output must be an ExecutionOutput or None")
        if self.failure is not None and not isinstance(self.failure, ExecutionFailure):
            raise TypeError("failure must be an ExecutionFailure or None")
        if self.status is ExecutionStatus.NOT_EXECUTED:
            if self.target not in {
                OrchestrationTarget.CLARIFY,
                OrchestrationTarget.UNSATISFIED,
            }:
                raise ValueError("only terminal decisions may be NOT_EXECUTED")
            if (
                self.handler_reference is not None
                or self.failure is not None
                or self.output is not None
            ):
                raise ValueError(
                    "terminal non-execution cannot contain handler/output/failure"
                )
        elif self.status is ExecutionStatus.SUCCEEDED:
            if self.handler_reference is None or self.failure is not None:
                raise ValueError("successful execution requires only a handler")
        else:
            if self.failure is None:
                raise ValueError(
                    "failed/rejected execution requires failure information"
                )
            if self.status is ExecutionStatus.FAILED and self.handler_reference is None:
                raise ValueError("failed execution requires an invoked handler")
        frozen = _freeze_json(self.metadata, field_name="execution metadata")
        if not isinstance(frozen, Mapping):  # pragma: no cover - guaranteed by input
            raise TypeError("execution metadata must be a mapping")
        object.__setattr__(self, "metadata", frozen)

    def to_trace(self) -> dict[str, object]:
        """Return a JSON-compatible trace without private reasoning."""

        return {
            "execution_id": self.execution_id,
            "decision_id": self.decision_id,
            "request_id": self.request_id,
            "context_snapshot_id": self.context_snapshot_id,
            "target": self.target.value,
            "decision_reason": self.decision_reason.value,
            "status": self.status.value,
            "handler_reference": self.handler_reference,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "output": None if self.output is None else self.output.to_data(),
            "failure": None if self.failure is None else self.failure.to_data(),
            "metadata": _thaw_json(cast(JsonValue, self.metadata)),
        }


_REASONS_BY_TARGET = {
    OrchestrationTarget.SYSTEM: {OrchestrationReason.DETERMINISTIC_SYSTEM_REQUEST},
    OrchestrationTarget.MEMORY: {OrchestrationReason.EXPLICIT_MEMORY_OPERATION},
    OrchestrationTarget.CAPABILITY: {OrchestrationReason.EXPLICIT_CAPABILITY_REQUEST},
    OrchestrationTarget.INTELLIGENCE: {OrchestrationReason.INTELLIGENCE_REQUIRED},
    OrchestrationTarget.CLARIFY: {
        OrchestrationReason.CONTEXT_AMBIGUOUS,
        OrchestrationReason.CONTEXT_CONFLICTED,
        OrchestrationReason.MISSING_REQUIRED_INFORMATION,
    },
    OrchestrationTarget.UNSATISFIED: {
        OrchestrationReason.NO_ADMISSIBLE_HANDLER,
        OrchestrationReason.COMPOSITE_HANDLING_REQUIRED,
    },
}
