"""Errors owned by bounded post-recording handling preparation."""


class PlanStepExecutionHandlingPreparationCompositionError(RuntimeError):
    """Base error for the WP043 composition boundary."""


class PlanStepExecutionHandlingPreparationCompositionInvariantError(
    PlanStepExecutionHandlingPreparationCompositionError
):
    """A delegated artifact contradicted the WP043 causal boundary."""
