"""Errors owned by bounded post-recording progress advancement."""


class PlanStepExecutionProgressAdvancementCompositionError(RuntimeError):
    """Base error for the WP042 composition boundary."""


class PlanStepExecutionProgressAdvancementCompositionInvariantError(
    PlanStepExecutionProgressAdvancementCompositionError
):
    """A delegated artifact contradicted the WP042 causal boundary."""
