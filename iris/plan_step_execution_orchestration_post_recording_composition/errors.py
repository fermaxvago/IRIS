"""Errors for bounded successor orchestration after Step C recording."""


class PlanStepExecutionOrchestrationPostRecordingCompositionError(RuntimeError):
    """Base error for the WP058 composition boundary."""


class PlanStepExecutionOrchestrationPostRecordingCompositionInvariantError(
    PlanStepExecutionOrchestrationPostRecordingCompositionError
):
    """A delegated artifact contradicts the WP058 causal contract."""
