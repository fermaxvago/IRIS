"""WP026 execution-result recording without assessment or progress mutation."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from iris.execution import (
    ExecutionFailure,
    ExecutionOutput,
    ExecutionResult,
    ExecutionStatus,
)
from iris.execution_observation import (
    DuplicateExecutionObservationError,
    ExecutionObservationAdapter,
    ExecutionObservationIdentityError,
)
from iris.orchestrator import OrchestrationReason, OrchestrationTarget
from iris.plan_runs import (
    PlanObservation,
    PlanRun,
    PlanRunFactory,
    PlanRunIdentityError,
    PlanRunInvariantError,
    PlanRunReducer,
    PlanRunUpdate,
    RecordObservationUpdate,
    RunProvenance,
    StepProgressState,
    StepProgressUpdate,
    UnknownPlanStepError,
)
from iris.plan_step_execution_result_recording import (
    PlanStepExecutionResultRecorder,
    PlanStepExecutionResultRecordingGenerationError,
    PlanStepExecutionResultRecordingInvariantError,
    PlanStepExecutionResultRecordingLineageError,
    PlanStepExecutionResultRecordingResult,
)
from iris.plan_step_execution_start import PlanStepExecutionStartResult
from iris.planning import Plan, PlanStep
from iris.work_identity import PlanStepWorkReference, WorkSubject, WorkSubjectKind

CREATED = datetime(2026, 9, 30, 18, tzinfo=UTC)
ACTIVATED = CREATED + timedelta(seconds=1)
STARTED = CREATED + timedelta(seconds=2)
COMPLETED = CREATED + timedelta(seconds=3)
OBSERVED = CREATED + timedelta(seconds=4)


def make_plan(*, plan_id: str = "plan-1", step_id: str = "step-1") -> Plan:
    return Plan(
        plan_id,
        "goal-1",
        (),
        (PlanStep(step_id, "Execute the work", "The expected state exists"),),
    )


def make_run(plan: Plan, *, run_id: str = "run-1") -> PlanRun:
    return PlanRunFactory(
        clock=lambda: CREATED,
        run_id_factory=lambda: run_id,
    ).create(plan)


def activate(plan: Plan, run: PlanRun) -> PlanRun:
    return PlanRunReducer().apply(
        plan,
        run,
        StepProgressUpdate(
            update_id="activation-update-1",
            run_id=run.run_id,
            expected_revision=run.revision,
            updated_at=ACTIVATED,
            provenance=RunProvenance(
                "plan_step_execution_start",
                "execution-1",
            ),
            step_id="step-1",
            new_state=StepProgressState.ACTIVE,
        ),
    )


def subject(plan: Plan, run: PlanRun) -> WorkSubject:
    return WorkSubject(
        WorkSubjectKind.PLAN_STEP,
        PlanStepWorkReference(plan.plan_id, run.run_id, "step-1"),
    )


def execution_result(
    plan: Plan,
    run: PlanRun,
    *,
    status: ExecutionStatus = ExecutionStatus.SUCCEEDED,
    execution_id: str = "execution-1",
) -> ExecutionResult:
    handler_reference: str | None = "handler.system"
    output: ExecutionOutput | None = None
    failure: ExecutionFailure | None = None
    if status is ExecutionStatus.SUCCEEDED:
        output = ExecutionOutput({"recorded": True}, "artifact-1")
    elif status is ExecutionStatus.FAILED:
        failure = ExecutionFailure("handler_failed", "Handler failed.")
    elif status is ExecutionStatus.REJECTED:
        failure = ExecutionFailure("handler_rejected", "Handler rejected the work.")
    else:  # pragma: no cover - helpers construct only invoked outcomes here
        raise AssertionError("unsupported started status")
    return ExecutionResult(
        execution_id=execution_id,
        subject_id=subject(plan, run).subject_id,
        decision_id="decision-1",
        context_snapshot_id="context-1",
        target=OrchestrationTarget.SYSTEM,
        decision_reason=OrchestrationReason.DETERMINISTIC_SYSTEM_HANDLING,
        status=status,
        handler_reference=handler_reference,
        started_at=STARTED,
        completed_at=COMPLETED,
        output=output,
        failure=failure,
        metadata={"attempt": 1},
    )


def unavailable_result(plan: Plan, run: PlanRun) -> ExecutionResult:
    return ExecutionResult(
        execution_id="execution-1",
        subject_id=subject(plan, run).subject_id,
        decision_id="decision-1",
        context_snapshot_id="context-1",
        target=OrchestrationTarget.SYSTEM,
        decision_reason=OrchestrationReason.DETERMINISTIC_SYSTEM_HANDLING,
        status=ExecutionStatus.REJECTED,
        handler_reference=None,
        started_at=STARTED,
        completed_at=COMPLETED,
        failure=ExecutionFailure(
            "handler_unavailable",
            "No concrete handler is registered.",
        ),
    )


def started_fixture(
    status: ExecutionStatus = ExecutionStatus.SUCCEEDED,
) -> tuple[Plan, PlanRun, PlanStepExecutionStartResult]:
    plan = make_plan()
    source_run = make_run(plan)
    active_run = activate(plan, source_run)
    result = PlanStepExecutionStartResult(
        plan_id=plan.plan_id,
        run_id=source_run.run_id,
        source_revision=source_run.revision,
        step_id="step-1",
        execution_id="execution-1",
        activation_update_id="activation-update-1",
        active_run=active_run,
        execution_result=execution_result(plan, source_run, status=status),
    )
    return plan, source_run, result


def unavailable_fixture() -> tuple[Plan, PlanRun, PlanStepExecutionStartResult]:
    plan = make_plan()
    run = make_run(plan)
    result = PlanStepExecutionStartResult(
        plan_id=plan.plan_id,
        run_id=run.run_id,
        source_revision=run.revision,
        step_id="step-1",
        execution_id="execution-1",
        activation_update_id=None,
        active_run=None,
        execution_result=unavailable_result(plan, run),
    )
    return plan, run, result


class CountingAdapter(ExecutionObservationAdapter):
    def __init__(
        self,
        *,
        observation_id: str = "observation-1",
        error: Exception | None = None,
    ) -> None:
        super().__init__(
            clock=lambda: OBSERVED,
            observation_id_factory=lambda: observation_id,
        )
        self.calls: list[tuple[Plan, PlanRun, WorkSubject, ExecutionResult]] = []
        self.error = error

    def create(
        self,
        plan: Plan,
        run: PlanRun,
        work_subject: WorkSubject,
        result: ExecutionResult,
    ) -> PlanObservation:
        self.calls.append((plan, run, work_subject, result))
        if self.error is not None:
            raise self.error
        return super().create(plan, run, work_subject, result)


class CountingReducer(PlanRunReducer):
    def __init__(self, *, error: Exception | None = None) -> None:
        self.calls: list[tuple[Plan, PlanRun, PlanRunUpdate]] = []
        self.error = error

    def apply(self, plan: Plan, run: PlanRun, update: PlanRunUpdate) -> PlanRun:
        self.calls.append((plan, run, update))
        if self.error is not None:
            raise self.error
        return super().apply(plan, run, update)


def recorder(
    *,
    adapter: ExecutionObservationAdapter | None = None,
    reducer: PlanRunReducer | None = None,
    update_id_factory: Callable[[], str] = lambda: "record-update-1",
) -> PlanStepExecutionResultRecorder:
    return PlanStepExecutionResultRecorder(
        observation_adapter=(CountingAdapter() if adapter is None else adapter),
        reducer=reducer,
        update_id_factory=update_id_factory,
    )


def selected_state(run: PlanRun) -> StepProgressState:
    return next(item.state for item in run.step_progress if item.step_id == "step-1")


def test_public_api_is_importable() -> None:
    assert PlanStepExecutionResultRecorder.__name__.endswith("Recorder")
    assert PlanStepExecutionResultRecordingResult.__name__.endswith("Result")


@pytest.mark.parametrize(
    ("position", "bad_value", "message"),
    [
        (0, object(), "plan must be a Plan"),
        (1, object(), "run must be a PlanRun"),
        (
            2,
            object(),
            "start_result must be a PlanStepExecutionStartResult",
        ),
    ],
)
def test_record_rejects_wrong_top_level_types(
    position: int,
    bad_value: object,
    message: str,
) -> None:
    plan, _, start_result = started_fixture()
    values: list[object] = [plan, start_result.active_run, start_result]
    values[position] = bad_value

    with pytest.raises(TypeError, match=message):
        recorder().record(*cast(Any, values))


@pytest.mark.parametrize(
    ("keyword", "bad_value", "message"),
    [
        (
            "observation_adapter",
            object(),
            "observation_adapter must be an ExecutionObservationAdapter",
        ),
        ("reducer", object(), "reducer must be a PlanRunReducer"),
        ("update_id_factory", object(), "update_id_factory must be callable"),
    ],
)
def test_constructor_rejects_wrong_dependency_types(
    keyword: str,
    bad_value: object,
    message: str,
) -> None:
    with pytest.raises(TypeError, match=message):
        PlanStepExecutionResultRecorder(**cast(Any, {keyword: bad_value}))


@pytest.mark.parametrize(
    "status",
    [
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.FAILED,
        ExecutionStatus.REJECTED,
    ],
)
def test_started_execution_records_one_observation_and_remains_active(
    status: ExecutionStatus,
) -> None:
    plan, source_run, start_result = started_fixture(status)
    active_run = start_result.active_run
    assert active_run is not None

    recording = recorder().record(plan, active_run, start_result)

    assert recording.recorded_from_revision == active_run.revision
    assert recording.recorded_run.revision == source_run.revision + 2
    assert recording.recorded_run.revision == active_run.revision + 1
    assert selected_state(recording.recorded_run) is StepProgressState.ACTIVE
    assert recording.recorded_run.step_progress == active_run.step_progress
    assert len(recording.recorded_run.observations) == 1
    assert recording.observation.source == "execution"
    assert recording.observation.source_reference == start_result.execution_id
    assert recording.observation.kind == "execution_result"
    assert recording.observation.to_data()["data"]["status"] == status.value
    assert selected_state(recording.recorded_run) not in {
        StepProgressState.SUCCEEDED,
        StepProgressState.FAILED,
    }


def test_handler_unavailable_records_evidence_without_activation() -> None:
    plan, run, start_result = unavailable_fixture()

    recording = recorder().record(plan, run, start_result)

    assert recording.recorded_from_revision == run.revision
    assert recording.recorded_run.revision == run.revision + 1
    assert selected_state(recording.recorded_run) is StepProgressState.NOT_STARTED
    assert recording.recorded_run.step_progress == run.step_progress
    assert len(recording.recorded_run.observations) == 1
    data = recording.observation.to_data()["data"]
    assert data["status"] == ExecutionStatus.REJECTED.value
    assert data["handler_reference"] is None
    assert cast(dict[str, object], data["failure"])["code"] == ("handler_unavailable")


def test_started_result_requires_its_exact_active_run() -> None:
    plan, source_run, start_result = started_fixture()
    adapter = CountingAdapter()
    reducer = CountingReducer()

    with pytest.raises(
        PlanStepExecutionResultRecordingLineageError,
        match="exact ACTIVE Run",
    ):
        recorder(adapter=adapter, reducer=reducer).record(
            plan,
            source_run,
            start_result,
        )

    assert adapter.calls == []
    assert reducer.calls == []


def test_non_started_result_rejects_a_later_run_revision() -> None:
    plan, run, start_result = unavailable_fixture()
    later_run = replace(run, revision=run.revision + 1)
    adapter = CountingAdapter()

    with pytest.raises(
        PlanStepExecutionResultRecordingLineageError,
        match="source Run revision",
    ):
        recorder(adapter=adapter).record(plan, later_run, start_result)

    assert adapter.calls == []


def test_repeated_recording_against_descendant_is_lineage_error_first() -> None:
    plan, _, start_result = started_fixture()
    active_run = start_result.active_run
    assert active_run is not None
    adapter = CountingAdapter()
    reducer = CountingReducer()
    service = recorder(adapter=adapter, reducer=reducer)
    first = service.record(plan, active_run, start_result)

    with pytest.raises(
        PlanStepExecutionResultRecordingLineageError,
        match="exact ACTIVE Run",
    ):
        service.record(plan, first.recorded_run, start_result)

    assert len(adapter.calls) == 1
    assert len(reducer.calls) == 1
    assert len(first.recorded_run.observations) == 1


def test_unavailable_retry_against_descendant_is_lineage_error_first() -> None:
    plan, run, start_result = unavailable_fixture()
    adapter = CountingAdapter()
    reducer = CountingReducer()
    service = recorder(adapter=adapter, reducer=reducer)
    first = service.record(plan, run, start_result)

    with pytest.raises(
        PlanStepExecutionResultRecordingLineageError,
        match="source Run revision",
    ):
        service.record(plan, first.recorded_run, start_result)

    assert len(adapter.calls) == 1
    assert len(reducer.calls) == 1
    assert len(first.recorded_run.observations) == 1
    assert selected_state(first.recorded_run) is StepProgressState.NOT_STARTED


def test_adapter_duplicate_authority_propagates_for_an_exact_base() -> None:
    plan, _, original_start = started_fixture()
    active_run = original_start.active_run
    assert active_run is not None
    observation = CountingAdapter().create(
        plan,
        active_run,
        subject(plan, active_run),
        original_start.execution_result,
    )
    already_recorded = PlanRunReducer().apply(
        plan,
        active_run,
        RecordObservationUpdate(
            update_id="preexisting-record-update",
            run_id=active_run.run_id,
            expected_revision=active_run.revision,
            updated_at=OBSERVED,
            provenance=RunProvenance("execution", "execution-1"),
            observation=observation,
        ),
    )
    exact_start = replace(
        original_start,
        source_revision=already_recorded.revision - 1,
        active_run=already_recorded,
    )
    reducer = CountingReducer()

    with pytest.raises(DuplicateExecutionObservationError):
        recorder(
            adapter=CountingAdapter(observation_id="observation-2"),
            reducer=reducer,
        ).record(plan, already_recorded, exact_start)

    assert reducer.calls == []


def test_subject_lineage_mismatch_is_rejected_before_adapter() -> None:
    plan, _, start_result = started_fixture()
    active_run = start_result.active_run
    assert active_run is not None
    bad_execution = replace(
        start_result.execution_result,
        subject_id="work_subject_wrong",
    )
    bad_start = replace(start_result, execution_result=bad_execution)
    adapter = CountingAdapter()

    with pytest.raises(
        PlanStepExecutionResultRecordingLineageError,
        match="different WorkSubject",
    ):
        recorder(adapter=adapter).record(plan, active_run, bad_start)

    assert adapter.calls == []


def test_plan_mismatch_uses_canonical_plan_run_validation() -> None:
    plan, _, start_result = started_fixture()
    active_run = start_result.active_run
    assert active_run is not None
    other_plan = make_plan(plan_id="plan-2")

    with pytest.raises(PlanRunIdentityError, match="different Plan"):
        recorder().record(other_plan, active_run, start_result)


def test_start_result_run_identity_mismatch_is_rejected() -> None:
    plan, run, start_result = unavailable_fixture()
    bad_start = replace(start_result, run_id="run-2")

    with pytest.raises(
        PlanStepExecutionResultRecordingLineageError,
        match="different PlanRun",
    ):
        recorder().record(plan, run, bad_start)


def test_unknown_start_result_step_uses_canonical_error() -> None:
    plan, run, start_result = unavailable_fixture()
    bad_start = replace(start_result, step_id="step-missing")

    with pytest.raises(UnknownPlanStepError, match="step-missing"):
        recorder().record(plan, run, bad_start)


def test_one_record_observation_update_has_exact_envelope() -> None:
    plan, _, start_result = started_fixture()
    active_run = start_result.active_run
    assert active_run is not None
    reducer = CountingReducer()

    recording = recorder(reducer=reducer).record(plan, active_run, start_result)

    assert len(reducer.calls) == 1
    _, supplied_run, update = reducer.calls[0]
    assert supplied_run is active_run
    assert type(update) is RecordObservationUpdate
    assert not isinstance(update, StepProgressUpdate)
    assert update.update_id == "record-update-1"
    assert update.run_id == active_run.run_id
    assert update.expected_revision == active_run.revision
    assert update.updated_at == max(active_run.updated_at, OBSERVED)
    assert update.observation == recording.observation
    assert update.provenance == RunProvenance(
        "plan_step_execution_result_recording",
        "execution-1",
        None,
    )


@pytest.mark.parametrize(
    "generated_id",
    [
        "",
        " record-update-1",
        "plan-1",
        "run-1",
        "step-1",
        "execution-1",
        "activation-update-1",
        "observation-1",
    ],
)
def test_generated_update_identity_must_be_new_and_nonblank(
    generated_id: str,
) -> None:
    plan, _, start_result = started_fixture()
    active_run = start_result.active_run
    assert active_run is not None

    with pytest.raises(PlanStepExecutionResultRecordingGenerationError):
        recorder(update_id_factory=lambda: generated_id).record(
            plan,
            active_run,
            start_result,
        )


def test_generated_update_identity_must_be_a_string() -> None:
    plan, _, start_result = started_fixture()
    active_run = start_result.active_run
    assert active_run is not None
    invalid_factory = cast(Callable[[], str], lambda: None)

    with pytest.raises(PlanStepExecutionResultRecordingGenerationError):
        recorder(update_id_factory=invalid_factory).record(
            plan,
            active_run,
            start_result,
        )


def test_update_identity_factory_failure_is_chained() -> None:
    plan, _, start_result = started_fixture()
    active_run = start_result.active_run
    assert active_run is not None

    def fail() -> str:
        raise LookupError("generator unavailable")

    with pytest.raises(PlanStepExecutionResultRecordingGenerationError) as caught:
        recorder(update_id_factory=fail).record(plan, active_run, start_result)

    assert isinstance(caught.value.__cause__, LookupError)


def test_adapter_failure_prevents_reduction_and_propagates() -> None:
    plan, _, start_result = started_fixture()
    active_run = start_result.active_run
    assert active_run is not None
    adapter = CountingAdapter(
        error=ExecutionObservationIdentityError("adapter rejected evidence")
    )
    reducer = CountingReducer()

    with pytest.raises(ExecutionObservationIdentityError):
        recorder(adapter=adapter, reducer=reducer).record(
            plan,
            active_run,
            start_result,
        )

    assert len(adapter.calls) == 1
    assert reducer.calls == []


def test_reducer_failure_is_not_retried_or_wrapped() -> None:
    plan, _, start_result = started_fixture()
    active_run = start_result.active_run
    assert active_run is not None
    reducer = CountingReducer(error=PlanRunInvariantError("reducer rejected update"))

    with pytest.raises(PlanRunInvariantError, match="reducer rejected update"):
        recorder(reducer=reducer).record(plan, active_run, start_result)

    assert len(reducer.calls) == 1
    assert type(reducer.calls[0][2]) is RecordObservationUpdate


class InvalidProgressReducer(PlanRunReducer):
    def apply(self, plan: Plan, run: PlanRun, update: PlanRunUpdate) -> PlanRun:
        recorded = super().apply(plan, run, update)
        changed = replace(
            recorded.step_progress[0],
            state=StepProgressState.FAILED,
            changed_at=recorded.updated_at,
            evidence_ids=(update.observation.observation_id,),
        )
        return replace(recorded, step_progress=(changed,))


def test_postcondition_rejects_any_step_progress_mutation() -> None:
    plan, _, start_result = started_fixture()
    active_run = start_result.active_run
    assert active_run is not None

    with pytest.raises(
        PlanStepExecutionResultRecordingInvariantError,
        match="must not change StepProgress",
    ):
        recorder(reducer=InvalidProgressReducer()).record(
            plan,
            active_run,
            start_result,
        )


def test_inputs_remain_immutable_and_result_is_frozen() -> None:
    plan, _, start_result = started_fixture()
    active_run = start_result.active_run
    assert active_run is not None
    before_plan = plan.to_data()
    before_run = active_run.to_data()
    before_start = start_result.to_data()

    recording = recorder().record(plan, active_run, start_result)

    assert plan.to_data() == before_plan
    assert active_run.to_data() == before_run
    assert start_result.to_data() == before_start
    assert recording.recorded_run is not active_run
    with pytest.raises(FrozenInstanceError):
        recording.execution_id = "changed"  # type: ignore[misc]


def valid_recording() -> PlanStepExecutionResultRecordingResult:
    plan, _, start_result = started_fixture()
    active_run = start_result.active_run
    assert active_run is not None
    return recorder().record(plan, active_run, start_result)


@pytest.mark.parametrize(
    "change",
    [
        {"plan_id": ""},
        {"recorded_from_revision": -1},
        {"observation_id": "observation-other"},
        {"record_update_id": "execution-1"},
    ],
)
def test_result_rejects_invalid_scalar_lineage(change: dict[str, object]) -> None:
    with pytest.raises(PlanStepExecutionResultRecordingInvariantError):
        replace(valid_recording(), **cast(Any, change))


def test_result_rejects_wrong_run_identity_and_revision() -> None:
    valid = valid_recording()
    wrong_identity = replace(valid.recorded_run, plan_id="plan-other")
    wrong_revision = replace(
        valid.recorded_run,
        revision=valid.recorded_from_revision,
    )

    with pytest.raises(PlanStepExecutionResultRecordingInvariantError):
        replace(valid, recorded_run=wrong_identity)
    with pytest.raises(PlanStepExecutionResultRecordingInvariantError):
        replace(valid, recorded_run=wrong_revision)


def test_result_rejects_non_execution_or_absent_observation() -> None:
    valid = valid_recording()
    wrong_source = replace(valid.observation, source="memory")
    without_observation = replace(valid.recorded_run, observations=())

    with pytest.raises(PlanStepExecutionResultRecordingInvariantError):
        replace(valid, observation=wrong_source)
    with pytest.raises(PlanStepExecutionResultRecordingInvariantError):
        replace(valid, recorded_run=without_observation)


def test_result_serialization_is_deterministic_and_json_compatible() -> None:
    valid = valid_recording()

    first = valid.to_data()
    second = valid.to_data()

    assert first == second
    assert json.loads(json.dumps(first, sort_keys=True)) == first
    assert set(first) == {
        "plan_id",
        "run_id",
        "recorded_from_revision",
        "step_id",
        "execution_id",
        "observation_id",
        "record_update_id",
        "observation",
        "recorded_run",
    }
