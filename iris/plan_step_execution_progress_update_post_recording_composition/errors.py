"""Errors owned by bounded post-recording Step C update composition."""


class PlanStepExecutionProgressUpdatePostRecordingCompositionError(RuntimeError):
    """Base error for the WP053 composition boundary."""


class PlanStepExecutionProgressUpdatePostRecordingCompositionInvariantError(
    PlanStepExecutionProgressUpdatePostRecordingCompositionError
):
    """A returned artifact contradicts the exact WP053 causal boundary."""
