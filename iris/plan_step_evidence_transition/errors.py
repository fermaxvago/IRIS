"""Errors owned by PlanStep evidence-to-transition composition."""


class PlanStepEvidenceTransitionError(RuntimeError):
    """Base error for WP028-owned composition failures."""


class PlanStepEvidenceTransitionInvariantError(PlanStepEvidenceTransitionError):
    """A composed assessment or decision contradicts WP028 lineage."""
