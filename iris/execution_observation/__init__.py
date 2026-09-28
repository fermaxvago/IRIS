"""ExecutionResult-to-PlanObservation adaptation without outcome assessment."""

from iris.execution_observation.adapter import ExecutionObservationAdapter
from iris.execution_observation.errors import (
    DuplicateExecutionObservationError,
    ExecutionObservationError,
    ExecutionObservationIdentityError,
    UnsupportedObservationSubjectError,
)

__all__ = [
    "DuplicateExecutionObservationError",
    "ExecutionObservationAdapter",
    "ExecutionObservationError",
    "ExecutionObservationIdentityError",
    "UnsupportedObservationSubjectError",
]
