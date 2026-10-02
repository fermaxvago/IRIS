"""Errors owned by post-advancement PlanStep handling preparation."""


class PlanStepHandlingPreparationError(RuntimeError):
    """Base error for WP031-owned composition failures."""


class PlanStepHandlingPreparationInvariantError(PlanStepHandlingPreparationError):
    """A delegated WP030 or WP014 artifact contradicts WP031 lineage."""
