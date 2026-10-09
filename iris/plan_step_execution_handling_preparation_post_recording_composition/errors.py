"""Errors owned by bounded post-Step-C handling preparation."""


class PlanStepExecutionHandlingPreparationPostRecordingCompositionError(RuntimeError):
    """Base error for the WP055 composition boundary."""


class PlanStepExecutionHandlingPreparationPostRecordingCompositionInvariantError(
    PlanStepExecutionHandlingPreparationPostRecordingCompositionError
):
    """A delegated artifact contradicts the exact WP055 causal boundary."""
