"""Errors owned by complete PlanStep evidence assessment."""


class PlanStepEvidenceAssessmentError(RuntimeError):
    """Base error for WP027-owned assessment composition failures."""


class PlanStepEvidenceAssessmentLineageError(PlanStepEvidenceAssessmentError):
    """The requested PlanStep assessment lineage is invalid."""


class PlanStepEvidenceAssessmentInvariantError(PlanStepEvidenceAssessmentError):
    """A replaceable evaluator violated the WP027 composition contract."""
