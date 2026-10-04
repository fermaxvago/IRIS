"""Errors owned by bounded post-decision progress-update composition."""


class PlanStepExecutionProgressUpdateCompositionError(RuntimeError):
    """Base error for the WP041 composition boundary."""


class PlanStepExecutionProgressUpdateCompositionInvariantError(
    PlanStepExecutionProgressUpdateCompositionError
):
    """A delegated artifact contradicted the WP041 causal boundary."""
