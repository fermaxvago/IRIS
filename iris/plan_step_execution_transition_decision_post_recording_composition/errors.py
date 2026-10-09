"""Errors owned by bounded post-recording Step C transition composition."""


class PlanStepExecutionTransitionDecisionPostRecordingCompositionError(RuntimeError):
    """Base error for the WP052 composition boundary."""


class PlanStepExecutionTransitionDecisionPostRecordingCompositionInvariantError(
    PlanStepExecutionTransitionDecisionPostRecordingCompositionError
):
    """A delegated artifact contradicted the exact WP052 causal boundary."""
