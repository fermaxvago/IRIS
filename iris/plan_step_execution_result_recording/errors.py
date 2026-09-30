"""Errors owned by PlanStep execution-result recording."""


class PlanStepExecutionResultRecordingError(RuntimeError):
    """Base error for WP026-owned recording failures."""


class PlanStepExecutionResultRecordingInvariantError(
    PlanStepExecutionResultRecordingError
):
    """A WP026 result or composition postcondition is contradictory."""


class PlanStepExecutionResultRecordingGenerationError(
    PlanStepExecutionResultRecordingError
):
    """A fresh recording-update identity could not be generated safely."""


class PlanStepExecutionResultRecordingLineageError(
    PlanStepExecutionResultRecordingError
):
    """Plan, Run, start-result, or execution lineage does not match."""
