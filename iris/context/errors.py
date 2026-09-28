"""Domain errors for subject-scoped Context ownership and evidence."""


class ContextOwnershipError(ValueError):
    """The caller did not provide exactly one valid Context owner input."""


class RequestEvidenceSubjectMismatchError(ValueError):
    """REQUEST evidence is not causally compatible with the WorkSubject."""
