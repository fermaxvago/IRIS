"""Errors owned by PlanStep progress advancement composition."""


class PlanStepProgressAdvancementError(RuntimeError):
    """Base error for WP030-owned composition failures."""


class PlanStepProgressAdvancementInvariantError(PlanStepProgressAdvancementError):
    """A composed WP029 or WP023 artifact contradicts WP030 lineage."""
