"""Errors owned by bounded post-assessment transition composition."""


class PlanStepExecutionTransitionDecisionCompositionError(RuntimeError):
    """Base error for the WP040 composition boundary."""


class PlanStepExecutionTransitionDecisionCompositionInvariantError(
    PlanStepExecutionTransitionDecisionCompositionError
):
    """A delegated artifact contradicted the WP040 causal boundary."""
