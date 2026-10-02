"""Errors owned by selected PlanStep WorkSubject materialization."""


class PlanStepWorkSubjectMaterializationError(RuntimeError):
    """Base error for WP032-owned composition failures."""


class PlanStepWorkSubjectMaterializationInvariantError(
    PlanStepWorkSubjectMaterializationError
):
    """A delegated WP031 or WP015 artifact contradicts WP032 lineage."""
