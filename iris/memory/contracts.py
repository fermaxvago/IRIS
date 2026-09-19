"""Model-independent storage contract for IRIS-owned memory."""

from typing import Protocol, TypeVar, runtime_checkable

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
