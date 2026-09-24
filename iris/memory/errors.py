"""Backend-independent errors for memory operations."""


class MemorySchemaError(RuntimeError):
    """Unsupported or unversioned nonempty database."""


class MemoryDataError(RuntimeError):
    """Persisted data cannot be interpreted as a valid memory record."""


class MemoryNotFoundError(LookupError):
    """A requested memory record does not exist."""


class MemoryConflictError(ValueError):
    """Duplicate identity, invalid transition, or invalid relation."""
