"""Errors owned by the bounded WP050 composition boundary."""


class PlanStepExecutionResultRecordingPostRecordingCompositionError(RuntimeError):
    """Base error for post-recording execution-result recording composition."""


class PlanStepExecutionResultRecordingPostRecordingCompositionInvariantError(
    PlanStepExecutionResultRecordingPostRecordingCompositionError
):
    """A returned artifact contradicts the exact WP050 causal lineage."""
