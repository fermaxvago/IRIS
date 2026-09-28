"""Domain errors for immutable operational work identity."""


class WorkIdentityError(ValueError):
    """Base class for rejected WorkIdentity data."""


class WorkSubjectInvariantError(WorkIdentityError):
    """A WorkSubject contradicts its identity invariants."""


class WorkReferenceMismatchError(WorkSubjectInvariantError):
    """A WorkSubject kind and typed reference are incompatible."""
