"""Errors owned by the PlanStep execution-lineage binding boundary."""


class PlanStepExecutionBindingError(ValueError):
    """Base error for valid domain values that cannot form a binding."""


class PlanStepExecutionBindingInvariantError(PlanStepExecutionBindingError):
    """Raised when binding identity or lifecycle invariants are inconsistent."""


class NonBindableControlDecisionError(PlanStepExecutionBindingError):
    """Raised when a valid control outcome does not select executable work."""


class NonBindableHandlingPreparationError(PlanStepExecutionBindingError):
    """Raised when a valid preparation outcome has no prepared handling need."""


class ExecutionBindingMismatchError(PlanStepExecutionBindingError):
    """Raised when supplied lineage values describe different PlanStep work."""


class NonExecutableExecutionRequestError(PlanStepExecutionBindingError):
    """Raised when an ExecutionRequest represents a terminal orchestration outcome."""


class StalePlanStepExecutionBindingError(PlanStepExecutionBindingError):
    """Raised when a binding no longer describes the exact pre-activation state."""
