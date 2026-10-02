"""Errors owned by selected PlanStep Context materialization."""


class PlanStepContextMaterializationError(RuntimeError):
    """Base error for WP033-owned composition failures."""


class PlanStepContextMaterializationInvariantError(PlanStepContextMaterializationError):
    """A delegated WP032 or WP016 artifact contradicts WP033 lineage."""
