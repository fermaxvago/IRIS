"""Errors owned by bounded post-recording Step C advancement composition."""


class PlanStepExecutionProgressAdvancementPostRecordingCompositionError(RuntimeError):
    """Base error for the WP054 composition boundary."""


class PlanStepExecutionProgressAdvancementPostRecordingCompositionInvariantError(
    PlanStepExecutionProgressAdvancementPostRecordingCompositionError
):
    """A delegated artifact contradicts the exact WP054 causal boundary."""
