"""Domain and contract errors for single-step execution."""


class DuplicateExecutionHandlerError(ValueError):
    """More than one handler was registered for the same target."""


class ExecutionContractError(ValueError):
    """An execution request or handler result violates its public contract."""
