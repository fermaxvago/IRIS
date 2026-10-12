"""Errors for bounded successor WorkSubject materialization."""


class PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionError(
    RuntimeError
):
    """Base error for the WP056 composition boundary."""


class PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionInvariantError(
    PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionError
):
    """A delegated artifact contradicts the WP056 causal contract."""
