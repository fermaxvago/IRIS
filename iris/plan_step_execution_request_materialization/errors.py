"""Errors owned by bounded PlanStep ExecutionRequest materialization."""


class PlanStepExecutionRequestMaterializationError(RuntimeError):
    """Base error for the WP035 composition boundary."""


class PlanStepExecutionRequestMaterializationInvariantError(
    PlanStepExecutionRequestMaterializationError
):
    """A delegated artifact contradicted the WP035 causal boundary."""
