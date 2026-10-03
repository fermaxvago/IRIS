"""Errors owned by bounded post-recording evidence assessment composition."""


class PlanStepExecutionEvidenceAssessmentCompositionError(RuntimeError):
    """Base error for the WP039 composition boundary."""


class PlanStepExecutionEvidenceAssessmentCompositionInvariantError(
    PlanStepExecutionEvidenceAssessmentCompositionError
):
    """A delegated artifact contradicted the WP039 causal boundary."""
