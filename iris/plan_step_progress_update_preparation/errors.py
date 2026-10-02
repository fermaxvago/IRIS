"""Errors owned by PlanStep progress-update preparation."""


class PlanStepProgressUpdatePreparationError(RuntimeError):
    """Base error for WP029-owned composition failures."""


class PlanStepProgressUpdatePreparationInvariantError(
    PlanStepProgressUpdatePreparationError
):
    """A composed artifact contradicts WP029 lineage or shape."""
