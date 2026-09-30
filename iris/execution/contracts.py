"""Replaceable contracts used by the single-step execution layer."""

from datetime import datetime
from typing import Protocol, runtime_checkable

from iris.execution.models import ExecutionRequest, HandlerOutcome
from iris.intelligence import (
    IntelligenceNeed,
    IntelligenceRequest,
    IntelligenceResource,
    IntelligenceResult,
    IntelligenceRoute,
)
from iris.memory import MemoryCandidate, MemoryQuery, MemoryRecord
from iris.orchestrator import OrchestrationTarget


@runtime_checkable
class ExecutionHandler(Protocol):
    """Adapter for exactly one already-selected subsystem target."""

    @property
    def target(self) -> OrchestrationTarget: ...

    @property
    def handler_reference(self) -> str: ...

    def execute(self, request: ExecutionRequest) -> HandlerOutcome:
        """Perform at most one subsystem invocation."""
        ...


@runtime_checkable
class ExecutionStartGate(Protocol):
    """Commit higher-level start state immediately before handler invocation."""

    def commit_start(
        self,
        request: ExecutionRequest,
        *,
        start_boundary_at: datetime,
        handler_reference: str,
    ) -> None:
        """Allow invocation only after the caller-owned start commit succeeds."""
        ...


class IntelligenceRouteExecutor(Protocol):
    def route(
        self,
        need: IntelligenceNeed,
        resources: tuple[IntelligenceResource, ...],
    ) -> IntelligenceRoute: ...


class IntelligenceExecutor(Protocol):
    def execute(
        self, provider_id: str, request: IntelligenceRequest
    ) -> IntelligenceResult: ...


class MemoryExecutor(Protocol):
    """Existing MemoryService surface used by the execution adapter."""

    def store(self, candidate: MemoryCandidate) -> MemoryRecord: ...

    def get(
        self, memory_id: str, *, include_history: bool = False
    ) -> MemoryRecord | None: ...

    def query(self, filters: MemoryQuery) -> tuple[MemoryRecord, ...]: ...

    def supersede(self, old_id: str, candidate: MemoryCandidate) -> MemoryRecord: ...

    def forget(self, memory_id: str) -> MemoryRecord: ...
