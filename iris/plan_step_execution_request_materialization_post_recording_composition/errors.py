"""Errors owned by bounded successor request materialization."""


class PlanStepExecutionRequestMaterializationPostRecordingCompositionError(
    RuntimeError
):
    """Base error for this composition boundary."""


class PlanStepExecutionRequestMaterializationPostRecordingCompositionInvariantError(
    PlanStepExecutionRequestMaterializationPostRecordingCompositionError
):
    """A delegated or accumulated artifact contradicts canonical lineage."""
