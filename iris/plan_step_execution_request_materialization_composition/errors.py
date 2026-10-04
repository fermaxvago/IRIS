"""Errors owned by bounded post-recording ExecutionRequest materialization."""


class PlanStepExecutionRequestMaterializationCompositionError(RuntimeError):
    """Base error for the WP047 composition boundary."""


class PlanStepExecutionRequestMaterializationCompositionInvariantError(
    PlanStepExecutionRequestMaterializationCompositionError
):
    """A delegated artifact contradicted the WP047 causal boundary."""
