"""Domain errors for adapting execution results into PlanRun evidence."""


class ExecutionObservationError(ValueError):
    """Base class for rejected execution-observation adaptations."""


class UnsupportedObservationSubjectError(ExecutionObservationError):
    """The work subject cannot own execution evidence for a PlanStep."""


class ExecutionObservationIdentityError(ExecutionObservationError):
    """Plan, Run, subject, result, or temporal lineage does not match."""


class DuplicateExecutionObservationError(ExecutionObservationError):
    """The same execution is already recorded as evidence in this PlanRun."""
