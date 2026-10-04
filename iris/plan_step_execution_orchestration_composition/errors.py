"""Errors owned by bounded post-recording PlanStep orchestration."""


class PlanStepExecutionOrchestrationCompositionError(RuntimeError):
    """Base error for the WP046 composition boundary."""


class PlanStepExecutionOrchestrationCompositionInvariantError(
    PlanStepExecutionOrchestrationCompositionError
):
    """A delegated artifact contradicted the WP046 causal boundary."""
