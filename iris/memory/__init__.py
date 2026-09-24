"""IRIS-owned structured memory: domain operations and local persistence."""

from iris.memory.contracts import Memory, MemoryStore
from iris.memory.errors import (
    MemoryConflictError,
    MemoryDataError,
    MemoryNotFoundError,
    MemorySchemaError,
)
from iris.memory.models import (
    AcquisitionMode,
    CurrentStatus,
    EpistemicStatus,
    LifecycleStatus,
    MemoryCandidate,
    MemoryClass,
    MemoryKind,
    MemoryProvenance,
    MemoryQuery,
    MemoryRecord,
    MemoryRelation,
    MemoryResult,
    MemoryScope,
    RelationKind,
    Retention,
    ScopeKind,
    SourceType,
)
from iris.memory.service import MemoryService
from iris.memory.sqlite import SCHEMA_VERSION, SQLiteMemoryStore

__all__ = [
    "AcquisitionMode",
    "CurrentStatus",
    "EpistemicStatus",
    "LifecycleStatus",
    "Memory",
    "MemoryCandidate",
    "MemoryClass",
    "MemoryConflictError",
    "MemoryDataError",
    "MemoryKind",
    "MemoryNotFoundError",
    "MemoryProvenance",
    "MemoryQuery",
    "MemoryRecord",
    "MemoryRelation",
    "MemoryResult",
    "MemorySchemaError",
    "MemoryScope",
    "MemoryService",
    "MemoryStore",
    "RelationKind",
    "Retention",
    "SCHEMA_VERSION",
    "SQLiteMemoryStore",
    "ScopeKind",
    "SourceType",
]
