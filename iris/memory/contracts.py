"""Model-independent storage contract for IRIS-owned memory."""

from typing import Protocol, TypeVar, runtime_checkable

from iris.memory.models import (
    LifecycleStatus,
    MemoryQuery,
    MemoryRecord,
    MemoryRelation,
)

KeyT = TypeVar("KeyT", contravariant=True)
ValueT = TypeVar("ValueT")


@runtime_checkable
class Memory(Protocol[KeyT, ValueT]):
    """Store, retrieve and remove IRIS-owned values independently of models."""

    def store(self, key: KeyT, value: ValueT) -> None:
        """Associate a value with a key."""
        ...

    def retrieve(self, key: KeyT) -> ValueT | None:
        """Return the stored value, or ``None`` when the key is absent."""
        ...

    def forget(self, key: KeyT) -> bool:
        """Remove a value and report whether it existed."""
        ...


@runtime_checkable
class MemoryStore(Protocol):
    """Persistence boundary for domain records, independent of SQLite."""

    def insert(self, record: MemoryRecord) -> None: ...

    def get(self, memory_id: str) -> MemoryRecord | None: ...

    def query(self, filters: MemoryQuery) -> tuple[MemoryRecord, ...]: ...

    def transition(
        self, memory_id: str, lifecycle: LifecycleStatus
    ) -> MemoryRecord: ...

    def supersede(self, old_id: str, new_record: MemoryRecord) -> MemoryRecord: ...

    def add_relation(self, relation: MemoryRelation) -> None: ...
