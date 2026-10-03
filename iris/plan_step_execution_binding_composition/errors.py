"""Errors owned by bounded post-request PlanStep binding composition."""


class PlanStepExecutionBindingCompositionError(RuntimeError):
    """Base error for the WP036 composition boundary."""


class PlanStepExecutionBindingCompositionInvariantError(
    PlanStepExecutionBindingCompositionError
):
    """A delegated artifact contradicted the WP036 causal boundary."""
