"""Errors owned by bounded post-start execution-result recording composition."""


class PlanStepExecutionResultRecordingCompositionError(RuntimeError):
    """Base error for the WP038 composition boundary."""


class PlanStepExecutionResultRecordingCompositionInvariantError(
    PlanStepExecutionResultRecordingCompositionError
):
    """A delegated artifact contradicted the WP038 causal boundary."""
