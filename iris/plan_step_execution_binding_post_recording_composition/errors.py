"""Errors owned by the WP048 post-recording binding boundary."""


class PlanStepExecutionBindingPostRecordingCompositionError(RuntimeError):
    """Base error for bounded post-recording binding composition."""


class PlanStepExecutionBindingPostRecordingCompositionInvariantError(
    PlanStepExecutionBindingPostRecordingCompositionError
):
    """A delegated artifact contradicts the exact WP048 lineage."""
