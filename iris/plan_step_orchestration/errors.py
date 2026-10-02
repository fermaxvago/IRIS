"""Errors owned by post-Context PlanStep orchestration composition."""


class PlanStepOrchestrationError(RuntimeError):
    """Base error for WP034-owned composition failures."""


class PlanStepOrchestrationInvariantError(PlanStepOrchestrationError):
    """A delegated WP033 or WP017 artifact contradicts WP034 lineage."""
