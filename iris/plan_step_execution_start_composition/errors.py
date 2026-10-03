"""Errors owned by bounded post-binding execution-start composition."""


class PlanStepExecutionStartCompositionError(RuntimeError):
    """Base error for the WP037 composition boundary."""


class PlanStepExecutionStartCompositionInvariantError(
    PlanStepExecutionStartCompositionError
):
    """A delegated artifact contradicted the WP037 causal boundary."""
