"""Errors owned by bounded post-recording WorkSubject materialization."""


class PlanStepExecutionWorkSubjectMaterializationCompositionError(RuntimeError):
    """Base error for the WP044 composition boundary."""


class PlanStepExecutionWorkSubjectMaterializationCompositionInvariantError(
    PlanStepExecutionWorkSubjectMaterializationCompositionError
):
    """A delegated artifact contradicted the WP044 causal boundary."""
