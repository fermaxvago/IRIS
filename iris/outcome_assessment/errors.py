"""Domain errors for PlanStep outcome assessment."""


class StepOutcomeAssessmentError(ValueError):
    """Base class for rejected outcome-assessment operations."""


class OutcomeAssessmentIdentityError(StepOutcomeAssessmentError):
    """Assessment identity, ownership, or temporal lineage is invalid."""


class ForeignOutcomeEvidenceError(StepOutcomeAssessmentError):
    """Supplied evidence is not canonical evidence for the target Run and step."""


class DuplicateOutcomeEvidenceError(StepOutcomeAssessmentError):
    """One observation was supplied more than once for an assessment."""


class OutcomeEvaluationError(StepOutcomeAssessmentError):
    """The evaluator could not perform its operational contract."""
