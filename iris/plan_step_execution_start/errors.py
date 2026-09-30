"""Errors owned by the PlanStep execution-start composition boundary."""

from iris.plan_runs import PlanRun


class PlanStepExecutionStartError(RuntimeError):
    """Base error for WP025-owned execution-start failures."""


class PlanStepExecutionStartInvariantError(PlanStepExecutionStartError):
    """PlanStep start lineage or result state is contradictory."""


class PlanStepExecutionStartGenerationError(PlanStepExecutionStartError):
    """An activation update identity could not be generated safely."""


class PlanStepExecutionRequestMismatchError(PlanStepExecutionStartError):
    """The supplied ExecutionRequest is not the request represented by a binding."""


class PlanStepExecutionInvocationError(PlanStepExecutionStartError):
    """Execution failed after the PlanStep had already become ACTIVE."""

    def __init__(
        self,
        message: str,
        *,
        active_run: PlanRun,
        activation_update_id: str,
        execution_id: str,
    ) -> None:
        super().__init__(message)
        self.active_run = active_run
        self.activation_update_id = activation_update_id
        self.execution_id = execution_id
