"""Pure adaptation of one ExecutionResult into raw PlanRun evidence."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from iris.execution import ExecutionResult
from iris.execution_observation.errors import (
    DuplicateExecutionObservationError,
    ExecutionObservationIdentityError,
    UnsupportedObservationSubjectError,
)
from iris.plan_runs import (
    DuplicateRunIdentityError,
    PlanObservation,
    PlanRun,
    UnknownPlanStepError,
    validate_plan_run,
)
from iris.planning import Plan
from iris.work_identity import (
    PlanStepWorkReference,
    WorkSubject,
    WorkSubjectKind,
)


def _utc_time(value: datetime, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ExecutionObservationIdentityError(
            f"{name} must be a timezone-aware datetime"
        )
    return value.astimezone(UTC)


class ExecutionObservationAdapter:
    """Create one uninterpreted execution observation and then stop."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        observation_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)
        self._observation_id_factory = (
            observation_id_factory
            if observation_id_factory is not None
            else lambda: uuid4().hex
        )

    def create(
        self,
        plan: Plan,
        run: PlanRun,
        subject: WorkSubject,
        result: ExecutionResult,
    ) -> PlanObservation:
        """Adapt observable execution facts without assessing their outcome."""

        validate_plan_run(plan, run)
        if not isinstance(subject, WorkSubject):
            raise TypeError("subject must be a WorkSubject")
        if not isinstance(result, ExecutionResult):
            raise TypeError("result must be an ExecutionResult")
        if subject.kind is not WorkSubjectKind.PLAN_STEP:
            raise UnsupportedObservationSubjectError(
                "execution observations require a PLAN_STEP WorkSubject"
            )
        reference = subject.reference
        if not isinstance(reference, PlanStepWorkReference):  # defensive boundary
            raise ExecutionObservationIdentityError(
                "PLAN_STEP subject requires a PlanStepWorkReference"
            )
        if reference.plan_id != plan.plan_id:
            raise ExecutionObservationIdentityError(
                "work subject references a different Plan"
            )
        if reference.run_id != run.run_id:
            raise ExecutionObservationIdentityError(
                "work subject references a different PlanRun"
            )
        if all(step.step_id != reference.step_id for step in plan.steps):
            raise UnknownPlanStepError(f"unknown Plan step {reference.step_id}")
        if result.subject_id != subject.subject_id:
            raise ExecutionObservationIdentityError(
                "ExecutionResult belongs to a different WorkSubject"
            )
        if any(
            observation.source == "execution"
            and observation.source_reference == result.execution_id
            for observation in run.observations
        ):
            raise DuplicateExecutionObservationError(
                f"execution {result.execution_id} is already recorded in this PlanRun"
            )

        observed_at = _utc_time(self._clock(), "observed_at")
        if observed_at < result.completed_at:
            raise ExecutionObservationIdentityError(
                "observation cannot predate execution completion"
            )
        if observed_at < run.created_at:
            raise ExecutionObservationIdentityError(
                "observation cannot predate PlanRun creation"
            )

        observation_id = self._observation_id_factory()
        if observation_id == result.execution_id:
            raise ExecutionObservationIdentityError(
                "observation_id must differ from execution_id"
            )
        if any(
            observation.observation_id == observation_id
            for observation in run.observations
        ):
            raise DuplicateRunIdentityError(
                f"duplicate observation identity {observation_id}"
            )

        return PlanObservation(
            observation_id=observation_id,
            run_id=run.run_id,
            step_id=reference.step_id,
            source="execution",
            source_reference=result.execution_id,
            observed_at=observed_at,
            kind="execution_result",
            data={
                "decision_id": result.decision_id,
                "context_snapshot_id": result.context_snapshot_id,
                "target": result.target.value,
                "decision_reason": result.decision_reason.value,
                "status": result.status.value,
                "handler_reference": result.handler_reference,
                "started_at": result.started_at.isoformat(),
                "completed_at": result.completed_at.isoformat(),
                "output": None if result.output is None else result.output.to_data(),
                "failure": (
                    None if result.failure is None else result.failure.to_data()
                ),
                "metadata": result.metadata,
            },
        )
