"""Errors owned by bounded post-recording Step C evidence assessment."""


class PlanStepExecutionEvidenceAssessmentPostRecordingCompositionError(RuntimeError):
    """Base error for the WP051 composition boundary."""


class PlanStepExecutionEvidenceAssessmentPostRecordingCompositionInvariantError(
    PlanStepExecutionEvidenceAssessmentPostRecordingCompositionError
):
    """A delegated artifact contradicted the exact WP051 causal boundary."""
