"""ExecutionResult-to-PlanObservation boundary tests for WP019."""

from __future__ import annotations

import builtins
import socket
import subprocess
from datetime import UTC, datetime, timedelta

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
    UnsupportedObservationSubjectError,
)
from iris.orchestrator import OrchestrationReason, OrchestrationTarget
from iris.plan_runs import (
    AddBlockerUpdate,
    DuplicateRunIdentityError,
    PlanBlocker,
    PlanObservation,
    PlanRun,
    PlanRunCondition,
    PlanRunFactory,
    PlanRunIdentityError,
    PlanRunReducer,
    RecordObservationUpdate,
    RunProvenance,
    StepProgressState,
    StepProgressUpdate,
    UnknownPlanStepError,
    derive_run_condition,
)
from iris.planning import Plan, PlanStep
from iris.work_identity import (
    PlanStepWorkReference,
    RequestWorkReference,
    WorkOrigin,
    WorkSubject,
    WorkSubjectKind,
    work_subject_from_plan_step,
)

CREATED = datetime(2026, 9, 28, 12, tzinfo=UTC)
STARTED = CREATED + timedelta(seconds=1)
COMPLETED = CREATED + timedelta(seconds=2)
OBSERVED = CREATED + timedelta(seconds=3)
PROVENANCE = RunProvenance("execution", "execution-1")


def make_plan(*, plan_id: str = "plan-1") -> Plan:
    return Plan(
        plan_id,
        "goal-1",
        (),
        (PlanStep("step-1", "Perform the work", "The work is complete"),),
    )


def make_run(plan: Plan, *, run_id: str = "run-1") -> PlanRun:
    return PlanRunFactory(
        clock=lambda: CREATED,
        run_id_factory=lambda: run_id,
    ).create(plan)


def make_subject(
    plan: Plan,
    run: PlanRun,
    *,
    origin: WorkOrigin | None = None,
) -> WorkSubject:
    return work_subject_from_plan_step(plan, run, "step-1", origin=origin)


def make_result(
    subject: WorkSubject,
    *,
    execution_id: str = "execution-1",
    decision_id: str = "decision-1",
    status: ExecutionStatus = ExecutionStatus.SUCCEEDED,
    completed_at: datetime = COMPLETED,
) -> ExecutionResult:
    target = OrchestrationTarget.SYSTEM
    reason = OrchestrationReason.DETERMINISTIC_SYSTEM_HANDLING
    handler_reference: str | None = "system-handler"
    output: ExecutionOutput | None = ExecutionOutput(
        {"answer": ["raw", 1]}, "artifact-1"
    )
    failure: ExecutionFailure | None = None
    if status is ExecutionStatus.FAILED:
        output = None
        failure = ExecutionFailure("handler_failed", "Handler failed.", {"code": 7})
    elif status is ExecutionStatus.REJECTED:
        handler_reference = None
        output = None
        failure = ExecutionFailure(
            "handler_unavailable", "Handler unavailable.", {"target": "system"}
        )
    elif status is ExecutionStatus.NOT_EXECUTED:
        target = OrchestrationTarget.UNSATISFIED
        reason = OrchestrationReason.NO_ADMISSIBLE_HANDLER
        handler_reference = None
        output = None
    return ExecutionResult(
        execution_id=execution_id,
        subject_id=subject.subject_id,
        decision_id=decision_id,
        context_snapshot_id="context-1",
        target=target,
        decision_reason=reason,
        status=status,
        handler_reference=handler_reference,
        started_at=STARTED,
        completed_at=completed_at,
        output=output,
        failure=failure,
        metadata={"attempt": 1, "tags": ("raw", "execution")},
    )


def adapter(
    *,
    observed_at: datetime = OBSERVED,
    observation_id: str = "observation-1",
) -> ExecutionObservationAdapter:
    return ExecutionObservationAdapter(
        clock=lambda: observed_at,
        observation_id_factory=lambda: observation_id,
    )


def record(
    plan: Plan,
    run: PlanRun,
    observation: PlanObservation,
    *,
    updated_at: datetime | None = None,
) -> PlanRun:
    return PlanRunReducer().apply(
        plan,
        run,
        RecordObservationUpdate(
            update_id=f"record-{run.revision + 1}",
            run_id=run.run_id,
            expected_revision=run.revision,
            updated_at=updated_at or observation.observed_at,
            provenance=RunProvenance("execution", observation.source_reference),
            observation=observation,
        ),
    )


def test_basic_plan_step_observation_has_explicit_raw_schema() -> None:
    plan = make_plan()
    run = make_run(plan)
    subject = make_subject(plan, run)
    result = make_result(subject)

    observation = adapter().create(plan, run, subject, result)
    data = observation.to_data()["data"]

    assert observation.source == "execution"
    assert observation.kind == "execution_result"
    assert observation.source_reference == result.execution_id
    assert observation.run_id == run.run_id
    assert observation.step_id == "step-1"
    assert observation.observation_id != result.execution_id
    assert set(data) == {
        "decision_id",
        "context_snapshot_id",
        "target",
        "decision_reason",
        "status",
        "handler_reference",
        "started_at",
        "completed_at",
        "output",
        "failure",
        "metadata",
    }
    assert "execution_id" not in data
    assert "subject_id" not in data
    assert "expected_outcome" not in data


def test_output_failure_and_metadata_are_preserved_without_interpretation() -> None:
    plan = make_plan()
    run = make_run(plan)
    subject = make_subject(plan, run)

    succeeded = adapter().create(plan, run, subject, make_result(subject))
    failed = adapter(observation_id="observation-2").create(
        plan,
        run,
        subject,
        make_result(subject, execution_id="execution-2", status=ExecutionStatus.FAILED),
    )

    succeeded_data = succeeded.to_data()["data"]
    failed_data = failed.to_data()["data"]
    assert succeeded_data["output"] == {
        "value": {"answer": ["raw", 1]},
        "reference": "artifact-1",
    }
    assert succeeded_data["metadata"] == {
        "attempt": 1,
        "tags": ["raw", "execution"],
    }
    assert failed_data["failure"] == {
        "code": "handler_failed",
        "message": "Handler failed.",
        "details": {"code": 7},
    }


@pytest.mark.parametrize(
    "status",
    tuple(ExecutionStatus),
)
def test_all_execution_statuses_are_recorded_as_raw_evidence(
    status: ExecutionStatus,
) -> None:
    plan = make_plan()
    run = make_run(plan)
    subject = make_subject(plan, run)

    observation = adapter().create(
        plan,
        run,
        subject,
        make_result(subject, status=status),
    )

    assert observation.to_data()["data"]["status"] == status.value
    if status is ExecutionStatus.NOT_EXECUTED:
        data = observation.to_data()["data"]
        assert data["handler_reference"] is None
        assert data["output"] is None
        assert data["failure"] is None


def test_request_subject_and_root_request_spoof_are_rejected() -> None:
    plan = make_plan()
    run = make_run(plan)
    request_subject = WorkSubject(
        WorkSubjectKind.REQUEST,
        RequestWorkReference("request-1"),
        WorkOrigin("request", "request-1"),
    )

    with pytest.raises(UnsupportedObservationSubjectError):
        adapter().create(plan, run, request_subject, make_result(request_subject))


def test_foreign_execution_subject_is_rejected() -> None:
    plan = make_plan()
    run = make_run(plan)
    subject = make_subject(plan, run)
    other = WorkSubject(
        WorkSubjectKind.PLAN_STEP,
        PlanStepWorkReference(plan.plan_id, run.run_id, "step-other"),
    )

    with pytest.raises(ExecutionObservationIdentityError):
        adapter().create(plan, run, subject, make_result(other))


def test_foreign_plan_and_run_are_rejected() -> None:
    plan = make_plan()
    run = make_run(plan)
    foreign_plan_subject = WorkSubject(
        WorkSubjectKind.PLAN_STEP,
        PlanStepWorkReference("plan-other", run.run_id, "step-1"),
    )
    foreign_run_subject = WorkSubject(
        WorkSubjectKind.PLAN_STEP,
        PlanStepWorkReference(plan.plan_id, "run-other", "step-1"),
    )

    with pytest.raises(ExecutionObservationIdentityError, match="different Plan$"):
        adapter().create(
            plan, run, foreign_plan_subject, make_result(foreign_plan_subject)
        )
    with pytest.raises(ExecutionObservationIdentityError, match="different PlanRun"):
        adapter().create(
            plan, run, foreign_run_subject, make_result(foreign_run_subject)
        )


def test_plan_run_validation_is_delegated_to_wp012() -> None:
    plan = make_plan(plan_id="plan-1")
    run = make_run(plan)
    other_plan = make_plan(plan_id="plan-2")
    subject = make_subject(plan, run)

    with pytest.raises(PlanRunIdentityError):
        adapter().create(other_plan, run, subject, make_result(subject))


def test_unknown_step_is_rejected_with_plan_run_error() -> None:
    plan = make_plan()
    run = make_run(plan)
    subject = WorkSubject(
        WorkSubjectKind.PLAN_STEP,
        PlanStepWorkReference(plan.plan_id, run.run_id, "missing-step"),
    )

    with pytest.raises(UnknownPlanStepError):
        adapter().create(plan, run, subject, make_result(subject))


def test_changed_origin_knowledge_does_not_change_observation_ownership() -> None:
    plan = make_plan()
    run = make_run(plan)
    original = make_subject(plan, run)
    enriched = make_subject(plan, run, origin=WorkOrigin("request", "request-1"))
    assert original != enriched
    assert original.subject_id == enriched.subject_id

    observation = adapter().create(plan, run, enriched, make_result(original))

    assert observation.step_id == "step-1"


def test_duplicate_execution_evidence_is_rejected_but_other_sources_are_not() -> None:
    plan = make_plan()
    run = make_run(plan)
    subject = make_subject(plan, run)
    result = make_result(subject)
    first = adapter().create(plan, run, subject, result)
    recorded = record(plan, run, first)

    with pytest.raises(DuplicateExecutionObservationError):
        adapter(observed_at=OBSERVED + timedelta(seconds=1)).create(
            plan, recorded, subject, result
        )

    other_source = PlanObservation(
        "external-observation",
        run.run_id,
        "caller",
        OBSERVED,
        "external_fact",
        "step-1",
        result.execution_id,
    )
    externally_recorded = record(plan, run, other_source)
    created = adapter(
        observed_at=OBSERVED + timedelta(seconds=1),
        observation_id="execution-observation",
    ).create(plan, externally_recorded, subject, result)
    assert created.source == "execution"


def test_same_decision_and_subject_allow_distinct_execution_evidence() -> None:
    plan = make_plan()
    run = make_run(plan)
    subject = make_subject(plan, run)
    first_result = make_result(subject, execution_id="execution-1")
    second_result = make_result(subject, execution_id="execution-2")
    first = adapter().create(plan, run, subject, first_result)
    recorded = record(plan, run, first)

    second = adapter(
        observed_at=OBSERVED + timedelta(seconds=1),
        observation_id="observation-2",
    ).create(plan, recorded, subject, second_result)

    assert second.source_reference == "execution-2"
    assert second.to_data()["data"]["decision_id"] == "decision-1"


def test_observation_time_cannot_predate_completion_but_may_equal_it() -> None:
    plan = make_plan()
    run = make_run(plan)
    subject = make_subject(plan, run)
    result = make_result(subject)

    with pytest.raises(ExecutionObservationIdentityError, match="completion"):
        adapter(observed_at=COMPLETED - timedelta(microseconds=1)).create(
            plan, run, subject, result
        )

    observation = adapter(observed_at=COMPLETED).create(plan, run, subject, result)
    assert observation.observed_at == result.completed_at


def test_observation_identity_is_independent_and_generic_duplicates_stay_generic() -> (
    None
):
    plan = make_plan()
    run = make_run(plan)
    subject = make_subject(plan, run)
    result = make_result(subject)

    with pytest.raises(ExecutionObservationIdentityError, match="must differ"):
        adapter(observation_id=result.execution_id).create(plan, run, subject, result)

    existing = PlanObservation(
        "observation-1",
        run.run_id,
        "caller",
        OBSERVED,
        "external_fact",
        "step-1",
    )
    recorded = record(plan, run, existing)
    with pytest.raises(DuplicateRunIdentityError):
        adapter(observed_at=OBSERVED + timedelta(seconds=1)).create(
            plan, recorded, subject, result
        )


def test_late_evidence_is_allowed_for_a_terminal_step() -> None:
    plan = make_plan()
    run = make_run(plan)
    reducer = PlanRunReducer()
    active_at = CREATED + timedelta(seconds=1)
    active = reducer.apply(
        plan,
        run,
        StepProgressUpdate(
            "activate-1",
            run.run_id,
            run.revision,
            active_at,
            RunProvenance("controller", "controller-1"),
            "step-1",
            StepProgressState.ACTIVE,
        ),
    )
    evidence = PlanObservation(
        "terminal-evidence",
        run.run_id,
        "caller",
        CREATED + timedelta(seconds=2),
        "terminal_evidence",
        "step-1",
    )
    observed = record(plan, active, evidence)
    terminal = reducer.apply(
        plan,
        observed,
        StepProgressUpdate(
            "finish-1",
            run.run_id,
            observed.revision,
            CREATED + timedelta(seconds=3),
            RunProvenance("controller", "controller-1"),
            "step-1",
            StepProgressState.SUCCEEDED,
            (evidence.observation_id,),
        ),
    )
    subject = make_subject(plan, terminal)
    result = make_result(
        subject,
        completed_at=CREATED + timedelta(seconds=4),
    )

    execution_observation = adapter(observed_at=CREATED + timedelta(seconds=5)).create(
        plan, terminal, subject, result
    )

    assert execution_observation.step_id == "step-1"
    assert terminal.step_progress[0].state is StepProgressState.SUCCEEDED


def test_reducer_integration_appends_once_without_changing_progress_or_blockers() -> (
    None
):
    plan = make_plan()
    run = make_run(plan)
    blocker_at = CREATED + timedelta(microseconds=1)
    blocker = PlanBlocker(
        "blocker-1",
        run.run_id,
        "step-1",
        "external_precondition",
        "Still waiting for an independent condition.",
        RunProvenance("caller", "caller-1"),
        blocker_at,
    )
    blocked = PlanRunReducer().apply(
        plan,
        run,
        AddBlockerUpdate(
            "add-blocker",
            run.run_id,
            run.revision,
            blocker_at,
            RunProvenance("caller", "caller-1"),
            blocker,
        ),
    )
    subject = make_subject(plan, blocked)
    result = make_result(subject)
    observation = adapter().create(plan, blocked, subject, result)
    before_progress = blocked.step_progress
    before_blockers = blocked.blockers
    before_condition = derive_run_condition(plan, blocked).condition

    updated = record(
        plan,
        blocked,
        observation,
        updated_at=OBSERVED + timedelta(seconds=1),
    )

    assert updated.revision == blocked.revision + 1
    assert updated.observations.count(observation) == 1
    assert updated.step_progress == before_progress
    assert updated.blockers == before_blockers
    assert derive_run_condition(plan, updated).condition is before_condition
    assert before_condition is PlanRunCondition.CANNOT_ADVANCE


def test_adapter_is_pure_and_injected_values_are_deterministic() -> None:
    plan = make_plan()
    run = make_run(plan)
    subject = make_subject(plan, run)
    result = make_result(subject)
    before = (plan.to_data(), run.to_data(), subject.to_data(), result.to_trace())

    first = adapter().create(plan, run, subject, result)
    second = adapter().create(plan, run, subject, result)

    assert first == second
    assert first.observation_id == "observation-1"
    assert first.observed_at == OBSERVED
    assert before == (
        plan.to_data(),
        run.to_data(),
        subject.to_data(),
        result.to_trace(),
    )


def test_adapter_performs_no_filesystem_network_or_subprocess_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = make_plan()
    run = make_run(plan)
    subject = make_subject(plan, run)
    result = make_result(subject)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("external side effect attempted")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)

    observation = adapter().create(plan, run, subject, result)
    assert observation.source_reference == result.execution_id
