"""Errors owned by the bounded WP049 composition boundary."""


class PlanStepExecutionStartPostRecordingCompositionError(RuntimeError):
    """Base error for post-recording execution-start composition."""


class PlanStepExecutionStartPostRecordingCompositionInvariantError(
    PlanStepExecutionStartPostRecordingCompositionError
):
    """Delegated lineage contradicts the WP049 composition contract."""
