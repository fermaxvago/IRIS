"""Domain errors for request-scoped orchestration."""


class RequestContextMismatchError(ValueError):
    """A context snapshot belongs to a different request."""


class OrchestrationPolicyContractError(ValueError):
    """An orchestration policy returned a result outside its explicit input."""
