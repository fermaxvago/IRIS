"""Errors for bounded successor Context materialization."""


class PlanStepExecutionContextMaterializationPostRecordingCompositionError(
    RuntimeError
):
    """Base error for the WP057 composition boundary."""


class PlanStepExecutionContextMaterializationPostRecordingCompositionInvariantError(
    PlanStepExecutionContextMaterializationPostRecordingCompositionError
):
    """A delegated artifact contradicts the WP057 causal contract."""
