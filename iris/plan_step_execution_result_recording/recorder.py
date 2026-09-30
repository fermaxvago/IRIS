"""Record one already-produced PlanStep ExecutionResult as PlanRun evidence."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from iris.execution_observation import ExecutionObservationAdapter
from iris.plan_runs import (
    PlanObservation,
    PlanRun,
    PlanRunReducer,
    RecordObservationUpdate,
    RunProvenance,
    StepProgressState,
    UnknownPlanStepError,
    validate_plan_run,
)
from iris.plan_step_execution_result_recording.errors import (
    PlanStepExecutionResultRecordingGenerationError,
    PlanStepExecutionResultRecordingInvariantError,
    PlanStepExecutionResultRecordingLineageError,
)
from iris.plan_step_execution_result_recording.models import (
    PlanStepExecutionResultRecordingResult,
)
from iris.plan_step_execution_start import PlanStepExecutionStartResult
from iris.planning import Plan
from iris.work_identity import (
    PlanStepWorkReference,
    WorkSubject,
    WorkSubjectKind,
)


def _validate_inputs(
    plan: Plan,
    run: PlanRun,
    start_result: PlanStepExecutionStartResult,
) -> None:
    for value, expected, name in (
        (plan, Plan, "plan"),
        (run, PlanRun, "run"),
        (start_result, PlanStepExecutionStartResult, "start_result"),
    ):
        if not isinstance(value, expected):
            raise TypeError(f"{name} must be a {expected.__name__}")


def _step_state(run: PlanRun, step_id: str) -> StepProgressState:
    progress = next(
        (item for item in run.step_progress if item.step_id == step_id),
        None,
    )
    if progress is None:
        raise UnknownPlanStepError(f"unknown Plan step {step_id}")
    return progress.state


def _validate_observation(
    observation: PlanObservation,
    *,
    run: PlanRun,
    step_id: str,
    execution_id: str,
) -> None:
    if not isinstance(observation, PlanObservation):
        raise TypeError("execution observation adapter must return a PlanObservation")
    if (
        observation.run_id != run.run_id
        or observation.step_id != step_id
        or observation.source != "execution"
        or observation.source_reference != execution_id
        or observation.kind != "execution_result"
    ):
        raise PlanStepExecutionResultRecordingInvariantError(
            "adapter output is not canonical execution-result evidence"
        )


class PlanStepExecutionResultRecorder:
    """Record one WP025 execution result without interpreting or advancing it."""

    def __init__(
        self,
        *,
        observation_adapter: ExecutionObservationAdapter | None = None,
        reducer: PlanRunReducer | None = None,
        update_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if observation_adapter is not None and not isinstance(
            observation_adapter, ExecutionObservationAdapter
        ):
            raise TypeError(
                "observation_adapter must be an ExecutionObservationAdapter"
            )
        if reducer is not None and not isinstance(reducer, PlanRunReducer):
            raise TypeError("reducer must be a PlanRunReducer")
        if update_id_factory is not None and not callable(update_id_factory):
            raise TypeError("update_id_factory must be callable")
        self._observation_adapter = (
            ExecutionObservationAdapter()
            if observation_adapter is None
            else observation_adapter
        )
        self._reducer = PlanRunReducer() if reducer is None else reducer
        self._update_id_factory: Callable[[], str] = (
            (lambda: uuid4().hex) if update_id_factory is None else update_id_factory
        )

    def record(
        self,
        plan: Plan,
        run: PlanRun,
        start_result: PlanStepExecutionStartResult,
    ) -> PlanStepExecutionResultRecordingResult:
        """Record one execution fact into revision N+1 and then stop."""

        _validate_inputs(plan, run, start_result)
        validate_plan_run(plan, run)
        subject = self._validate_lineage(plan, run, start_result)
        observation = self._observation_adapter.create(
            plan,
            run,
            subject,
            start_result.execution_result,
        )
        _validate_observation(
            observation,
            run=run,
            step_id=start_result.step_id,
            execution_id=start_result.execution_id,
        )
        update_id = self._generate_update_id(start_result, observation)
        update = RecordObservationUpdate(
            update_id=update_id,
            run_id=run.run_id,
            expected_revision=run.revision,
            updated_at=max(run.updated_at, observation.observed_at),
            provenance=RunProvenance(
                source_type="plan_step_execution_result_recording",
                source_id=start_result.execution_id,
                actor=None,
            ),
            observation=observation,
        )
        recorded_run = self._reducer.apply(plan, run, update)
        self._validate_recorded_run(run, recorded_run, observation)
        return PlanStepExecutionResultRecordingResult(
            plan_id=start_result.plan_id,
            run_id=start_result.run_id,
            recorded_from_revision=run.revision,
            step_id=start_result.step_id,
            execution_id=start_result.execution_id,
            observation_id=observation.observation_id,
            record_update_id=update_id,
            observation=observation,
            recorded_run=recorded_run,
        )

    @staticmethod
    def _validate_lineage(
        plan: Plan,
        run: PlanRun,
        start_result: PlanStepExecutionStartResult,
    ) -> WorkSubject:
        if start_result.plan_id != plan.plan_id:
            raise PlanStepExecutionResultRecordingLineageError(
                "start result references a different Plan"
            )
        if start_result.run_id != run.run_id:
            raise PlanStepExecutionResultRecordingLineageError(
                "start result references a different PlanRun"
            )
        if all(step.step_id != start_result.step_id for step in plan.steps):
            raise UnknownPlanStepError(f"unknown Plan step {start_result.step_id}")
        if start_result.execution_id != start_result.execution_result.execution_id:
            raise PlanStepExecutionResultRecordingLineageError(
                "ExecutionResult identity does not match start result"
            )

        subject = WorkSubject(
            WorkSubjectKind.PLAN_STEP,
            PlanStepWorkReference(
                plan_id=start_result.plan_id,
                run_id=start_result.run_id,
                step_id=start_result.step_id,
            ),
        )
        if subject.subject_id != start_result.execution_result.subject_id:
            raise PlanStepExecutionResultRecordingLineageError(
                "ExecutionResult belongs to a different WorkSubject"
            )

        if start_result.active_run is not None:
            if run != start_result.active_run:
                raise PlanStepExecutionResultRecordingLineageError(
                    "started execution must be recorded against its exact ACTIVE Run"
                )
            expected_state = StepProgressState.ACTIVE
        else:
            if run.revision != start_result.source_revision:
                raise PlanStepExecutionResultRecordingLineageError(
                    "non-started execution must use its source Run revision"
                )
            expected_state = StepProgressState.NOT_STARTED
        if _step_state(run, start_result.step_id) is not expected_state:
            raise PlanStepExecutionResultRecordingLineageError(
                f"recording step must remain {expected_state.value}"
            )
        return subject

    def _generate_update_id(
        self,
        start_result: PlanStepExecutionStartResult,
        observation: PlanObservation,
    ) -> str:
        try:
            update_id = self._update_id_factory()
        except Exception as exc:
            raise PlanStepExecutionResultRecordingGenerationError(
                "recording update identity generation failed"
            ) from exc
        reserved = {
            start_result.plan_id,
            start_result.run_id,
            start_result.step_id,
            start_result.execution_id,
            start_result.execution_result.subject_id,
            observation.observation_id,
        }
        if start_result.activation_update_id is not None:
            reserved.add(start_result.activation_update_id)
        if (
            not isinstance(update_id, str)
            or not update_id
            or update_id != update_id.strip()
            or update_id in reserved
        ):
            raise PlanStepExecutionResultRecordingGenerationError(
                "recording update identity must be new and nonblank"
            )
        return update_id

    @staticmethod
    def _validate_recorded_run(
        source_run: PlanRun,
        recorded_run: PlanRun,
        observation: PlanObservation,
    ) -> None:
        if not isinstance(recorded_run, PlanRun):
            raise TypeError("reducer must return a PlanRun")
        if (
            recorded_run.plan_id != source_run.plan_id
            or recorded_run.run_id != source_run.run_id
            or recorded_run.revision != source_run.revision + 1
        ):
            raise PlanStepExecutionResultRecordingInvariantError(
                "recording must derive exactly the next Run revision"
            )
        if recorded_run.step_progress != source_run.step_progress:
            raise PlanStepExecutionResultRecordingInvariantError(
                "execution-result recording must not change StepProgress"
            )
        if (
            len(recorded_run.observations) != len(source_run.observations) + 1
            or observation not in recorded_run.observations
        ):
            raise PlanStepExecutionResultRecordingInvariantError(
                "recording must add exactly the adapter-produced observation"
            )
