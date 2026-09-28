"""Domain errors for WorkSubject-scoped orchestration."""


class SubjectContextMismatchError(ValueError):
    """A ContextSnapshot belongs to a different WorkSubject identity."""


# WP009 compatibility name. Ownership validation itself is subject-scoped.
RequestContextMismatchError = SubjectContextMismatchError


class StaleOrchestrationDecisionError(ValueError):
    """A decision does not belong to the supplied subject/snapshot pair."""


class OrchestrationPolicyContractError(ValueError):
    """An orchestration policy returned a result outside its explicit input."""
