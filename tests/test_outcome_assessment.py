"""Step outcome assessment contracts and WP019 integration tests."""

from __future__ import annotations

import builtins
import socket
import subprocess
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta

import pytest

from iris.execution import (
    ExecutionFailure,
    ExecutionOutput,
    ExecutionResult,
    ExecutionStatus,
)
from iris.execution_observation import ExecutionObservationAdapter
from iris.orchestrator import OrchestrationReason, OrchestrationTarget
from iris.outcome_assessment import (
    ConservativeStepOutcomeEvaluator,
    DuplicateOutcomeEvidenceError,
    ForeignOutcomeEvidenceError,
    OutcomeAssessmentIdentityError,
    OutcomeEvaluationError,
    StepOutcomeAssessment,
    StepOutcomeEvaluator,
    StepOutcomeStatus,
)
from iris.plan_runs import (
    AddBlockerUpdate,
    PlanBlocker,
    PlanObservation,
    PlanRun,
    PlanRunFactory,
    PlanRunIdentityError,
    PlanRunReducer,
    RecordObservationUpdate,
    RunProvenance,
    StepProgress,
    StepProgressState,
)
from iris.planning import Plan, PlanStep
from iris.work_identity import work_subject_from_plan_step

CREATED = datetime(2026, 9, 28, 12, tzinfo=UTC)
OBSERVED = CREATED + timedelta(seconds=1)
ASSESSED = CREATED + timedelta(seconds=2)


def make_plan(*, plan_id: str = "plan-1") -> Plan:
    return Plan(
        plan_id,
        "goal-1",
        (),
        (
            PlanStep("step-1", "Perform work", "The intended result exists"),
            PlanStep("step-2", "Check work", "The result is verified"),
        ),
    )


def make_run(plan: Plan, *, run_id: str = "run-1") -> PlanRun:
    return PlanRunFactory(clock=lambda: CREATED, run_id_factory=lambda: run_id).create(
        plan
    )


def make_observation(
    run: PlanRun,
    *,
    observation_id: str = "observation-1",
    step_id: str | None = "step-1",
    observed_at: datetime = OBSERVED,
    status: str = "succeeded",
) -> PlanObservation:
    return PlanObservation(
        observation_id=observation_id,
        run_id=run.run_id,
        step_id=step_id,
        source="execution",
        source_reference=f"execution-{observation_id}",
        observed_at=observed_at,
        kind="execution_result",
        data={"status": status, "raw": {"value": 1}},
    )


def record(plan: Plan, run: PlanRun, observation: PlanObservation) -> PlanRun:
    return PlanRunReducer().apply(
        plan,
        run,
        RecordObservationUpdate(
            update_id=f"record-{observation.observation_id}",
            run_id=run.run_id,
            expected_revision=run.revision,
            updated_at=observation.observed_at,
            provenance=RunProvenance("execution", observation.source_reference),
            observation=observation,
        ),
    )


def evaluator(
    *,
    assessed_at: datetime = ASSESSED,
    assessment_id: str = "assessment-1",
) -> ConservativeStepOutcomeEvaluator:
    return ConservativeStepOutcomeEvaluator(
        clock=lambda: assessed_at,
        assessment_id_factory=lambda: assessment_id,
    )


def recorded_evidence() -> tuple[Plan, PlanRun, PlanStep, PlanObservation]:
    plan = make_plan()
    run = make_run(plan)
    observation = make_observation(run)
    run = record(plan, run, observation)
    return plan, run, plan.steps[0], run.observations[0]


def test_public_status_vocabulary_is_exact() -> None:
    assert {item.value for item in StepOutcomeStatus} == {
        "satisfied",
        "not_satisfied",
        "insufficient_evidence",
        "indeterminate",
    }


def test_no_evidence_returns_insufficient_evidence_with_run_lineage() -> None:
    plan = make_plan()
    run = make_run(plan)
    before = run.to_data()

    assessment = evaluator().evaluate(plan, run, plan.steps[0], ())

    assert assessment.status is StepOutcomeStatus.INSUFFICIENT_EVIDENCE
    assert assessment.evidence_ids == ()
    assert assessment.plan_id == plan.plan_id
    assert assessment.run_id == run.run_id
    assert assessment.run_revision == run.revision
    assert assessment.step_id == "step-1"
    assert assessment.evaluator_reference == "deterministic.conservative.v1"
    assert assessment.details == {"evidence_count": 0, "reason": "no_evidence"}
    assert run.to_data() == before


def test_recorded_evidence_returns_indeterminate_not_satisfied() -> None:
    plan, run, step, observation = recorded_evidence()

    assessment = evaluator().evaluate(plan, run, step, (observation,))

    assert assessment.status is StepOutcomeStatus.INDETERMINATE
    assert assessment.evidence_ids == (observation.observation_id,)
    assert assessment.run_revision == run.revision
    assert assessment.details == {
        "evidence_count": 1,
        "reason": "unsupported_expected_outcome",
    }


def test_evidence_selection_is_explicit_and_exact() -> None:
    plan = make_plan()
    run = make_run(plan)
    first = make_observation(run, observation_id="observation-b")
    run = record(plan, run, first)
    second = make_observation(
        run,
        observation_id="observation-a",
        observed_at=OBSERVED + timedelta(seconds=1),
    )
    run = record(plan, run, second)
    canonical = {item.observation_id: item for item in run.observations}

    assessment = evaluator(assessed_at=ASSESSED + timedelta(seconds=1)).evaluate(
        plan, run, plan.steps[0], (canonical["observation-b"],)
    )

    assert assessment.evidence_ids == ("observation-b",)
    assert "observation-a" not in assessment.evidence_ids


@pytest.mark.parametrize(
    ("status", "evidence_ids", "valid"),
    [
        (StepOutcomeStatus.SATISFIED, (), False),
        (StepOutcomeStatus.NOT_SATISFIED, (), False),
        (StepOutcomeStatus.INDETERMINATE, (), False),
        (StepOutcomeStatus.INSUFFICIENT_EVIDENCE, (), True),
        (StepOutcomeStatus.SATISFIED, ("observation-1",), True),
        (StepOutcomeStatus.NOT_SATISFIED, ("observation-1",), True),
        (StepOutcomeStatus.INDETERMINATE, ("observation-1",), True),
    ],
)
def test_assessment_status_evidence_invariant(
    status: StepOutcomeStatus, evidence_ids: tuple[str, ...], valid: bool
) -> None:
    kwargs = dict(
        assessment_id="assessment-1",
        plan_id="plan-1",
        run_id="run-1",
        run_revision=0,
        step_id="step-1",
        status=status,
        evidence_ids=evidence_ids,
        evaluator_reference="test.evaluator.v1",
        assessed_at=ASSESSED,
    )
    if valid:
        assert StepOutcomeAssessment(**kwargs).status is status
    else:
        with pytest.raises(ValueError, match="requires evidence"):
            StepOutcomeAssessment(**kwargs)


@pytest.mark.parametrize(
    "collision",
    ["plan-1", "run-1", "step-1", "observation-1"],
)
def test_assessment_identity_is_independent(collision: str) -> None:
    with pytest.raises(OutcomeAssessmentIdentityError):
        StepOutcomeAssessment(
            assessment_id=collision,
            plan_id="plan-1",
            run_id="run-1",
            run_revision=0,
            step_id="step-1",
            status=StepOutcomeStatus.INDETERMINATE,
            evidence_ids=("observation-1",),
            evaluator_reference="test.evaluator.v1",
            assessed_at=ASSESSED,
        )


def test_assessment_model_is_frozen_and_serializes_stably() -> None:
    plan, run, step, observation = recorded_evidence()
    assessment = evaluator().evaluate(plan, run, step, (observation,))

    with pytest.raises(FrozenInstanceError):
        assessment.status = StepOutcomeStatus.SATISFIED  # type: ignore[misc]
    with pytest.raises(TypeError):
        assessment.details["reason"] = "changed"  # type: ignore[index]
    assert assessment.to_data() == assessment.to_data()
    assert set(assessment.to_data()) == {
        "assessment_id",
        "plan_id",
        "run_id",
        "run_revision",
        "step_id",
        "status",
        "evidence_ids",
        "evaluator_reference",
        "assessed_at",
        "details",
    }
    assert "expected_outcome" not in assessment.to_data()
    assert "score" not in assessment.to_data()
    assert "confidence" not in assessment.to_data()


def test_details_are_deeply_immutable_json_and_ordered() -> None:
    assessment = StepOutcomeAssessment(
        "assessment-1",
        "plan-1",
        "run-1",
        0,
        "step-1",
        StepOutcomeStatus.INSUFFICIENT_EVIDENCE,
        (),
        "test.evaluator.v1",
        ASSESSED,
        {"z": [2, 1], "a": {"b": True}},
    )
    assert list(assessment.details) == ["a", "z"]
    assert assessment.to_data()["details"] == {
        "a": {"b": True},
        "z": [2, 1],
    }
    with pytest.raises(TypeError):
        StepOutcomeAssessment(
            "assessment-2",
            "plan-1",
            "run-1",
            0,
            "step-1",
            StepOutcomeStatus.INSUFFICIENT_EVIDENCE,
            (),
            "test.evaluator.v1",
            ASSESSED,
            {"bad": object()},
        )


def test_evidence_ids_are_distinct_and_canonically_ordered() -> None:
    assessment = StepOutcomeAssessment(
        "assessment-1",
        "plan-1",
        "run-1",
        0,
        "step-1",
        StepOutcomeStatus.INDETERMINATE,
        ("observation-z", "observation-a"),
        "test.evaluator.v1",
        ASSESSED,
    )
    assert assessment.evidence_ids == ("observation-a", "observation-z")
    with pytest.raises(ValueError, match="distinct"):
        replace(assessment, evidence_ids=("observation-a", "observation-a"))


def test_foreign_run_evidence_is_rejected() -> None:
    plan, run, step, _ = recorded_evidence()
    evidence = replace(run.observations[0], run_id="run-foreign")
    with pytest.raises(ForeignOutcomeEvidenceError, match="another Run"):
        evaluator().evaluate(plan, run, step, (evidence,))


@pytest.mark.parametrize("step_id", ["step-2", None])
def test_foreign_or_run_level_evidence_is_rejected(step_id: str | None) -> None:
    plan = make_plan()
    run = make_run(plan)
    observation = make_observation(run, step_id=step_id)
    run = record(plan, run, observation)
    with pytest.raises(ForeignOutcomeEvidenceError, match="not scoped"):
        evaluator().evaluate(plan, run, plan.steps[0], (run.observations[0],))


def test_unrecorded_evidence_is_rejected() -> None:
    plan = make_plan()
    run = make_run(plan)
    observation = make_observation(run)
    with pytest.raises(ForeignOutcomeEvidenceError, match="not recorded"):
        evaluator().evaluate(plan, run, plan.steps[0], (observation,))


def test_same_id_with_modified_content_is_rejected() -> None:
    plan, run, step, observation = recorded_evidence()
    modified = replace(observation, data={"status": "failed"})
    with pytest.raises(ForeignOutcomeEvidenceError, match="differs from canonical"):
        evaluator().evaluate(plan, run, step, (modified,))


def test_duplicate_evidence_input_is_rejected() -> None:
    plan, run, step, observation = recorded_evidence()
    with pytest.raises(DuplicateOutcomeEvidenceError):
        evaluator().evaluate(plan, run, step, (observation, observation))


def test_noncanonical_step_definition_is_rejected() -> None:
    plan = make_plan()
    run = make_run(plan)
    modified = replace(plan.steps[0], expected_outcome="A different criterion")
    with pytest.raises(OutcomeAssessmentIdentityError, match="canonical PlanStep"):
        evaluator().evaluate(plan, run, modified, ())


def test_plan_run_validation_is_reused() -> None:
    plan = make_plan()
    foreign_plan = make_plan(plan_id="plan-foreign")
    run = make_run(foreign_plan)
    with pytest.raises(PlanRunIdentityError):
        evaluator().evaluate(plan, run, plan.steps[0], ())


def test_assessment_timestamp_must_follow_run_and_evidence() -> None:
    plan = make_plan()
    run = make_run(plan)
    with pytest.raises(OutcomeAssessmentIdentityError, match="Run creation"):
        evaluator(assessed_at=CREATED - timedelta(seconds=1)).evaluate(
            plan, run, plan.steps[0], ()
        )

    observation = make_observation(run)
    run = record(plan, run, observation)
    with pytest.raises(OutcomeAssessmentIdentityError, match="latest evidence"):
        evaluator(assessed_at=CREATED).evaluate(
            plan, run, plan.steps[0], (run.observations[0],)
        )
    assessment = evaluator(assessed_at=OBSERVED).evaluate(
        plan, run, plan.steps[0], (run.observations[0],)
    )
    assert assessment.assessed_at == OBSERVED


def test_multiple_assessments_are_allowed_and_not_persisted() -> None:
    plan, run, step, observation = recorded_evidence()
    first = evaluator(assessment_id="assessment-1").evaluate(
        plan, run, step, (observation,)
    )
    second = evaluator(assessment_id="assessment-2").evaluate(
        plan, run, step, (observation,)
    )
    assert first.assessment_id != second.assessment_id
    assert first.status == second.status
    assert "assessments" not in run.to_data()


def test_custom_evaluator_reference_is_preserved_exactly() -> None:
    plan = make_plan()
    run = make_run(plan)
    custom = ConservativeStepOutcomeEvaluator(
        evaluator_reference="rule_based.file_exists.v1",
        clock=lambda: ASSESSED,
        assessment_id_factory=lambda: "assessment-custom",
    )
    assessment = custom.evaluate(plan, run, plan.steps[0], ())
    assert custom.evaluator_reference == "rule_based.file_exists.v1"
    assert assessment.evaluator_reference == "rule_based.file_exists.v1"


@pytest.mark.parametrize("run_revision", [-1, True])
def test_assessment_rejects_invalid_run_revision(run_revision: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        StepOutcomeAssessment(
            assessment_id="assessment-1",
            plan_id="plan-1",
            run_id="run-1",
            run_revision=run_revision,  # type: ignore[arg-type]
            step_id="step-1",
            status=StepOutcomeStatus.INSUFFICIENT_EVIDENCE,
            evidence_ids=(),
            evaluator_reference="test.evaluator.v1",
            assessed_at=ASSESSED,
        )


def test_operational_factory_failures_raise_not_status() -> None:
    plan = make_plan()
    run = make_run(plan)

    def broken_id_factory() -> str:
        raise RuntimeError("factory offline")

    failing = ConservativeStepOutcomeEvaluator(
        clock=lambda: ASSESSED, assessment_id_factory=broken_id_factory
    )
    with pytest.raises(OutcomeEvaluationError, match="ID factory failed"):
        failing.evaluate(plan, run, plan.steps[0], ())


def test_protocol_is_replaceable_and_not_intelligence_specific() -> None:
    assert isinstance(evaluator(), StepOutcomeEvaluator)


@pytest.mark.parametrize(
    "progress_state",
    [
        StepProgressState.NOT_STARTED,
        StepProgressState.ACTIVE,
        StepProgressState.SUCCEEDED,
        StepProgressState.FAILED,
    ],
)
def test_progress_state_does_not_determine_assessment(
    progress_state: StepProgressState,
) -> None:
    plan, run, step, observation = recorded_evidence()
    progress = tuple(
        StepProgress(
            item.step_id,
            progress_state if item.step_id == step.step_id else item.state,
            run.updated_at,
            (
                (observation.observation_id,)
                if progress_state
                in {StepProgressState.SUCCEEDED, StepProgressState.FAILED}
                else ()
            ),
        )
        if item.step_id == step.step_id
        else item
        for item in run.step_progress
    )
    varied = replace(run, step_progress=progress)
    assessment = evaluator().evaluate(plan, varied, step, (observation,))
    assert assessment.status is StepOutcomeStatus.INDETERMINATE


def test_blockers_do_not_determine_assessment() -> None:
    plan, run, step, observation = recorded_evidence()
    instant = run.updated_at + timedelta(seconds=1)
    blocked = PlanRunReducer().apply(
        plan,
        run,
        AddBlockerUpdate(
            update_id="add-blocker",
            run_id=run.run_id,
            expected_revision=run.revision,
            updated_at=instant,
            provenance=RunProvenance("caller", "caller-1"),
            blocker=PlanBlocker(
                blocker_id="blocker-1",
                run_id=run.run_id,
                step_id=step.step_id,
                kind="external_precondition",
                reason="An unrelated condition is unavailable.",
                provenance=RunProvenance("caller", "caller-1"),
                created_at=instant,
            ),
        ),
    )
    assessment = evaluator().evaluate(plan, blocked, step, (observation,))
    assert assessment.status is StepOutcomeStatus.INDETERMINATE


def make_execution_result(
    subject_id: str, status: ExecutionStatus, *, execution_id: str
) -> ExecutionResult:
    target = OrchestrationTarget.SYSTEM
    reason = OrchestrationReason.DETERMINISTIC_SYSTEM_HANDLING
    handler_reference: str | None = "system-handler"
    output: ExecutionOutput | None = ExecutionOutput("raw-result", "artifact-1")
    failure: ExecutionFailure | None = None
    if status is ExecutionStatus.FAILED:
        output = None
        failure = ExecutionFailure("handler_failed", "Handler failed.")
    elif status is ExecutionStatus.REJECTED:
        output = None
        handler_reference = None
        failure = ExecutionFailure("handler_unavailable", "No handler.")
    elif status is ExecutionStatus.NOT_EXECUTED:
        target = OrchestrationTarget.UNSATISFIED
        reason = OrchestrationReason.NO_ADMISSIBLE_HANDLER
        output = None
        handler_reference = None
    return ExecutionResult(
        execution_id=execution_id,
        subject_id=subject_id,
        decision_id=f"decision-{execution_id}",
        context_snapshot_id="context-1",
        target=target,
        decision_reason=reason,
        status=status,
        handler_reference=handler_reference,
        started_at=CREATED,
        completed_at=CREATED + timedelta(milliseconds=500),
        output=output,
        failure=failure,
    )


@pytest.mark.parametrize(
    "execution_status",
    [
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.FAILED,
        ExecutionStatus.REJECTED,
        ExecutionStatus.NOT_EXECUTED,
    ],
)
def test_wp019_execution_evidence_remains_indeterminate(
    execution_status: ExecutionStatus,
) -> None:
    plan = make_plan()
    run = make_run(plan)
    subject = work_subject_from_plan_step(plan, run, "step-1")
    result = make_execution_result(
        subject.subject_id,
        execution_status,
        execution_id=f"execution-{execution_status.value}",
    )
    observation = ExecutionObservationAdapter(
        clock=lambda: OBSERVED,
        observation_id_factory=lambda: f"observation-{execution_status.value}",
    ).create(plan, run, subject, result)
    run = record(plan, run, observation)
    progress_before = run.step_progress

    assessment = evaluator().evaluate(plan, run, plan.steps[0], (run.observations[0],))

    assert assessment.status is StepOutcomeStatus.INDETERMINATE
    assert run.step_progress == progress_before
    assert assessment.details["reason"] == "unsupported_expected_outcome"


def test_evaluator_performs_no_external_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = make_plan()
    run = make_run(plan)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("external I/O is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)

    assessment = evaluator().evaluate(plan, run, plan.steps[0], ())
    assert assessment.status is StepOutcomeStatus.INSUFFICIENT_EVIDENCE
