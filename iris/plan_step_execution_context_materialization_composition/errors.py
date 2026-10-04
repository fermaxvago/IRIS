"""Errors owned by bounded post-recording Context materialization."""


class PlanStepExecutionContextMaterializationCompositionError(RuntimeError):
    """Base error for the WP045 composition boundary."""


class PlanStepExecutionContextMaterializationCompositionInvariantError(
    PlanStepExecutionContextMaterializationCompositionError
):
    """A delegated artifact contradicted the WP045 causal boundary."""
