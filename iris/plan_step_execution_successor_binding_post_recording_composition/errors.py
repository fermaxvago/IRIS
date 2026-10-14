"""Errors owned by bounded successor execution-binding composition."""


class PlanStepExecutionSuccessorBindingPostRecordingCompositionError(RuntimeError):
    """Base error for the WP060 composition boundary."""


class PlanStepExecutionSuccessorBindingPostRecordingCompositionInvariantError(
    PlanStepExecutionSuccessorBindingPostRecordingCompositionError
):
    """A delegated artifact contradicts canonical successor lineage."""
