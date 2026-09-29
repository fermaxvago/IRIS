"""StepProgress transition-decision to update synthesis tests."""

from __future__ import annotations

import builtins
import json
import socket
import subprocess
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from iris.outcome_assessment import StepOutcomeAssessment, StepOutcomeStatus
from iris.plan_runs import (
    PlanObservation,
    PlanRun,
    PlanRunFactory,
    PlanRunReducer,
    RecordObservationUpdate,
    RunProvenance,
    StalePlanRunUpdateError,
    StepProgressState,
    StepProgressUpdate,
)
from iris.planning import Plan, PlanStep
from iris.step_progress_transition import (
    StaleStepProgressTransitionDecisionError,
    StepProgressTransitionAction,
    StepProgressTransitionDecider,
    StepProgressTransitionDecision,
    StepProgressTransitionReason,
    TransitionDecisionIdentityError,
)
from iris.step_progress_update_synthesis import (
    NonActionableTransitionDecisionError,
    StepProgressUpdateGenerationError,
    StepProgressUpdateSynthesisError,
    StepProgressUpdateSynthesizer,
    TransitionAssessmentBindingError,
)

CREATED = datetime(2026, 9, 29, 12, tzinfo=UTC)
OBSERVED = CREATED + timedelta(seconds=1)
ACTIVATED = CREATED + timedelta(seconds=2)
ASSESSED = CREATED + timedelta(seconds=3)
DECIDED = CREATED + timedelta(seconds=4)
UPDATED = CREATED + timedelta(seconds=5)
PROVENANCE = RunProvenance("test", "wp022")


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
) -> PlanObservation:
    return PlanObservation(
        observation_id=observation_id,
        run_id=run.run_id,
        step_id=step_id,
        source="execution",
        source_reference=f"execution-{observation_id}",
        observed_at=observed_at,
        kind="execution_result",
        data={"status": "succeeded"},
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
            provenance=PROVENANCE,
            observation=observation,
        ),
    )


def activate(plan: Plan, run: PlanRun) -> PlanRun:
    return PlanRunReducer().apply(
        plan,
        run,
        StepProgressUpdate(
            update_id="activate-step-1",
            run_id=run.run_id,
            expected_revision=run.revision,
            updated_at=ACTIVATED,
            provenance=PROVENANCE,
            step_id="step-1",
            new_state=StepProgressState.ACTIVE,
        ),
    )


def make_assessment(
    plan: Plan,
    run: PlanRun,
    *,
    assessment_id: str = "assessment-1",
    plan_id: str | None = None,
    run_id: str | None = None,
    run_revision: int | None = None,
    step_id: str = "step-1",
    status: StepOutcomeStatus = StepOutcomeStatus.SATISFIED,
    evidence_ids: tuple[str, ...] = ("observation-1",),
    assessed_at: datetime = ASSESSED,
) -> StepOutcomeAssessment:
    return StepOutcomeAssessment(
        assessment_id=assessment_id,
        plan_id=plan.plan_id if plan_id is None else plan_id,
        run_id=run.run_id if run_id is None else run_id,
        run_revision=run.revision if run_revision is None else run_revision,
        step_id=step_id,
        status=status,
        evidence_ids=evidence_ids,
        evaluator_reference="test.satisfied.v1",
        assessed_at=assessed_at,
        details={"reason": "test_fixture"},
    )


def decide(
    plan: Plan,
    run: PlanRun,
    assessment: StepOutcomeAssessment,
    *,
    decision_id: str = "decision-1",
    decided_at: datetime = DECIDED,
) -> StepProgressTransitionDecision:
    return StepProgressTransitionDecider(
        clock=lambda: decided_at,
        decision_id_factory=lambda: decision_id,
    ).decide(plan, run, plan.steps[0], assessment)


def prepared() -> tuple[
    Plan,
    PlanRun,
    StepOutcomeAssessment,
    StepProgressTransitionDecision,
]:
    plan = make_plan()
    run = make_run(plan)
    run = record(plan, run, make_observation(run))
    run = activate(plan, run)
    assessment = make_assessment(plan, run)
    decision = decide(plan, run, assessment)
    return plan, run, assessment, decision


def synthesizer(
    *,
    update_id: str = "update-1",
    updated_at: datetime = UPDATED,
) -> StepProgressUpdateSynthesizer:
    return StepProgressUpdateSynthesizer(
        clock=lambda: updated_at,
        update_id_factory=lambda: update_id,
    )


def test_public_api_and_happy_path_map_causal_lineage_then_stop() -> None:
    plan, run, assessment, decision = prepared()
    before = (plan.to_data(), run.to_data(), assessment.to_data(), decision.to_data())

    update = synthesizer().synthesize(plan, run, assessment, decision)

    assert isinstance(update, StepProgressUpdate)
    assert isinstance(
        TransitionAssessmentBindingError("x"), StepProgressUpdateSynthesisError
    )
    assert update.update_id == "update-1"
    assert update.run_id == decision.run_id
    assert update.expected_revision == decision.observed_revision == run.revision
    assert update.step_id == decision.step_id
    assert update.new_state is decision.target_state is StepProgressState.SUCCEEDED
    assert update.evidence_ids == assessment.evidence_ids
    assert update.provenance == RunProvenance(
        "step_progress_transition", decision.decision_id, None
    )
    assert update.updated_at == UPDATED
    assert run.revision == 2
    assert (
        plan.to_data(),
        run.to_data(),
        assessment.to_data(),
        decision.to_data(),
    ) == before


@pytest.mark.parametrize("position", range(4))
def test_wrong_python_input_types_fail_before_domain_validation(position: int) -> None:
    plan, run, assessment, decision = prepared()
    arguments: list[object] = [plan, run, assessment, decision]
    arguments[position] = object()

    with pytest.raises(TypeError):
        synthesizer().synthesize(*arguments)  # type: ignore[arg-type]


def test_non_actionable_decision_is_not_materialized_as_another_noop() -> None:
    plan, run, assessment, decision = prepared()
    non_actionable = replace(
        decision,
        action=StepProgressTransitionAction.NO_TRANSITION,
        target_state=None,
        reason=StepProgressTransitionReason.OUTCOME_NOT_SATISFIED,
    )

    with pytest.raises(NonActionableTransitionDecisionError):
        synthesizer().synthesize(plan, run, assessment, non_actionable)


def test_stale_decision_precedes_even_invalid_assessment_binding() -> None:
    plan, run, assessment, decision = prepared()
    stale = replace(decision, observed_revision=run.revision - 1)
    foreign = make_assessment(plan, run, assessment_id="foreign-assessment")

    with pytest.raises(StaleStepProgressTransitionDecisionError):
        synthesizer().synthesize(plan, run, foreign, stale)


@pytest.mark.parametrize(
    ("field", "value"),
    [("plan_id", "foreign-plan"), ("run_id", "foreign-run"), ("step_id", "missing")],
)
def test_foreign_decision_is_rejected_by_wp021_currentness_validator(
    field: str, value: str
) -> None:
    plan, run, assessment, decision = prepared()
    foreign = replace(decision, **{field: value})

    with pytest.raises(TransitionDecisionIdentityError):
        synthesizer().synthesize(plan, run, assessment, foreign)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("assessment_id", "foreign-assessment"),
        ("plan_id", "foreign-plan"),
        ("run_id", "foreign-run"),
        ("step_id", "step-2"),
    ],
)
def test_assessment_identity_must_match_decision(field: str, value: str) -> None:
    plan, run, assessment, decision = prepared()
    foreign = replace(assessment, **{field: value})

    with pytest.raises(TransitionAssessmentBindingError):
        synthesizer().synthesize(plan, run, foreign, decision)


def test_same_assessment_identity_cannot_substitute_a_different_evidence_basis() -> (
    None
):
    plan, run, assessment, _ = prepared()
    second = make_observation(
        run,
        observation_id="observation-2",
        observed_at=ACTIVATED + timedelta(milliseconds=100),
    )
    run = record(plan, run, second)
    complete = replace(
        assessment,
        run_revision=run.revision,
        evidence_ids=("observation-1", "observation-2"),
    )
    decision = decide(plan, run, complete)
    substitute = replace(complete, evidence_ids=("observation-1",))

    with pytest.raises(TransitionAssessmentBindingError):
        synthesizer().synthesize(plan, run, substitute, decision)


@pytest.mark.parametrize(
    "status",
    [
        StepOutcomeStatus.NOT_SATISFIED,
        StepOutcomeStatus.INDETERMINATE,
    ],
)
def test_actionable_decision_requires_satisfied_assessment(
    status: StepOutcomeStatus,
) -> None:
    plan, run, assessment, decision = prepared()
    wrong = replace(assessment, status=status)

    with pytest.raises(TransitionAssessmentBindingError):
        synthesizer().synthesize(plan, run, wrong, decision)


def test_assessment_may_be_older_but_cannot_observe_after_decision_revision() -> None:
    plan, run, assessment, decision = prepared()
    future = replace(assessment, run_revision=decision.observed_revision + 1)

    with pytest.raises(TransitionAssessmentBindingError):
        synthesizer().synthesize(plan, run, future, decision)


def test_assessment_cannot_postdate_decision() -> None:
    plan, run, assessment, decision = prepared()
    future = replace(assessment, assessed_at=decision.decided_at + timedelta(seconds=1))

    with pytest.raises(TransitionAssessmentBindingError):
        synthesizer().synthesize(plan, run, future, decision)


def test_positive_decision_rejects_assessment_predating_active_state() -> None:
    plan, run, assessment, decision = prepared()
    before_active = replace(
        assessment, assessed_at=ACTIVATED - timedelta(microseconds=1)
    )

    with pytest.raises(TransitionAssessmentBindingError):
        synthesizer().synthesize(plan, run, before_active, decision)


def test_missing_assessment_evidence_is_a_binding_error() -> None:
    plan, run, assessment, decision = prepared()
    missing = replace(assessment, evidence_ids=("missing-observation",))

    with pytest.raises(TransitionAssessmentBindingError):
        synthesizer().synthesize(plan, run, missing, decision)


def test_extra_assessment_evidence_is_a_binding_error() -> None:
    plan, run, assessment, decision = prepared()
    extra = replace(
        assessment,
        evidence_ids=("observation-1", "unrecorded-extra-observation"),
    )

    with pytest.raises(TransitionAssessmentBindingError):
        synthesizer().synthesize(plan, run, extra, decision)


def test_wrong_step_assessment_evidence_is_a_binding_error() -> None:
    plan, run, assessment, _ = prepared()
    other = make_observation(
        run,
        observation_id="other-step-observation",
        step_id="step-2",
        observed_at=ACTIVATED + timedelta(milliseconds=100),
    )
    run = record(plan, run, other)
    decision = decide(plan, run, assessment)
    wrong = replace(assessment, evidence_ids=(other.observation_id,))

    with pytest.raises(TransitionAssessmentBindingError):
        synthesizer().synthesize(plan, run, wrong, decision)


def test_run_level_and_other_step_evidence_do_not_expand_current_step_basis() -> None:
    plan, run, assessment, _ = prepared()
    run_level = make_observation(
        run,
        observation_id="run-observation",
        step_id=None,
        observed_at=ACTIVATED + timedelta(milliseconds=100),
    )
    run = record(plan, run, run_level)
    other = make_observation(
        run,
        observation_id="other-step-observation",
        step_id="step-2",
        observed_at=ACTIVATED + timedelta(milliseconds=200),
    )
    run = record(plan, run, other)
    decision = decide(plan, run, assessment)

    update = synthesizer().synthesize(plan, run, assessment, decision)

    assert update.evidence_ids == ("observation-1",)


def test_evidence_basis_comparison_is_order_independent_and_output_is_canonical() -> (
    None
):
    plan, run, assessment, _ = prepared()
    second = make_observation(
        run,
        observation_id="observation-2",
        observed_at=ACTIVATED + timedelta(milliseconds=100),
    )
    run = record(plan, run, second)
    assessment = replace(
        assessment,
        run_revision=run.revision,
        evidence_ids=("observation-2", "observation-1"),
    )
    decision = decide(plan, run, assessment)

    update = synthesizer().synthesize(plan, run, assessment, decision)

    assert update.evidence_ids == ("observation-1", "observation-2")


def test_old_assessment_remains_bindable_to_newer_current_decision_revision() -> None:
    plan, run, assessment, _ = prepared()
    old_revision = assessment.run_revision
    unrelated = make_observation(
        run,
        observation_id="unrelated-observation",
        step_id="step-2",
        observed_at=ACTIVATED + timedelta(milliseconds=100),
    )
    run = record(plan, run, unrelated)
    decision = decide(plan, run, assessment)

    update = synthesizer().synthesize(plan, run, assessment, decision)

    assert old_revision < decision.observed_revision == run.revision
    assert update.expected_revision == decision.observed_revision


def test_all_timestamp_equality_boundaries_are_allowed() -> None:
    plan, run, assessment, decision = prepared()
    assessment = replace(assessment, assessed_at=ACTIVATED)
    decision = replace(decision, decided_at=ACTIVATED)

    update = synthesizer(updated_at=ACTIVATED).synthesize(
        plan, run, assessment, decision
    )

    assert update.updated_at == decision.decided_at == run.updated_at


def test_clock_is_normalized_to_utc() -> None:
    plan, run, assessment, decision = prepared()
    offset = timezone(timedelta(hours=-6))

    update = synthesizer(updated_at=UPDATED.astimezone(offset)).synthesize(
        plan, run, assessment, decision
    )

    assert update.updated_at == UPDATED
    assert update.updated_at.tzinfo is UTC


@pytest.mark.parametrize(
    "colliding_id",
    ["run-1", "step-1", "assessment-1", "decision-1"],
)
def test_update_identity_must_be_independent(colliding_id: str) -> None:
    plan, run, assessment, decision = prepared()

    with pytest.raises(StepProgressUpdateGenerationError):
        synthesizer(update_id=colliding_id).synthesize(plan, run, assessment, decision)


@pytest.mark.parametrize("invalid_id", ["", " ", " padded ", 7, None])
def test_invalid_generated_update_identity_is_a_generation_error(
    invalid_id: object,
) -> None:
    plan, run, assessment, decision = prepared()
    subject = StepProgressUpdateSynthesizer(
        clock=lambda: UPDATED,
        update_id_factory=lambda: invalid_id,  # type: ignore[return-value]
    )

    with pytest.raises(StepProgressUpdateGenerationError):
        subject.synthesize(plan, run, assessment, decision)


def test_update_id_factory_failure_is_a_generation_error() -> None:
    plan, run, assessment, decision = prepared()

    def fail() -> str:
        raise RuntimeError("factory unavailable")

    with pytest.raises(StepProgressUpdateGenerationError):
        StepProgressUpdateSynthesizer(
            clock=lambda: UPDATED,
            update_id_factory=fail,
        ).synthesize(plan, run, assessment, decision)


@pytest.mark.parametrize(
    "invalid_time",
    [datetime(2026, 9, 29, 12), "not-a-time", DECIDED - timedelta(microseconds=1)],
)
def test_invalid_or_early_clock_value_is_a_generation_error(
    invalid_time: object,
) -> None:
    plan, run, assessment, decision = prepared()
    subject = StepProgressUpdateSynthesizer(
        clock=lambda: invalid_time,  # type: ignore[return-value]
        update_id_factory=lambda: "update-1",
    )

    with pytest.raises(StepProgressUpdateGenerationError):
        subject.synthesize(plan, run, assessment, decision)


def test_clock_failure_is_a_generation_error() -> None:
    plan, run, assessment, decision = prepared()

    def fail() -> datetime:
        raise RuntimeError("clock unavailable")

    with pytest.raises(StepProgressUpdateGenerationError):
        StepProgressUpdateSynthesizer(
            clock=fail,
            update_id_factory=lambda: "update-1",
        ).synthesize(plan, run, assessment, decision)


def test_repeated_synthesis_is_allowed_without_global_deduplication() -> None:
    plan, run, assessment, decision = prepared()

    first = synthesizer(update_id="update-1").synthesize(
        plan, run, assessment, decision
    )
    second = synthesizer(update_id="update-2").synthesize(
        plan, run, assessment, decision
    )

    assert first.update_id != second.update_id
    assert replace(first, update_id=second.update_id) == second


def test_output_is_deterministic_and_uses_existing_serialization_contract() -> None:
    plan, run, assessment, decision = prepared()

    first = synthesizer().synthesize(plan, run, assessment, decision)
    second = synthesizer().synthesize(plan, run, assessment, decision)

    assert first == second
    assert json.loads(json.dumps(first.to_data())) == first.to_data()
    assert first.to_data() == {
        "operation": "transition_step",
        "update_id": "update-1",
        "run_id": "run-1",
        "expected_revision": 2,
        "updated_at": UPDATED.isoformat(),
        "provenance": {
            "source_type": "step_progress_transition",
            "source_id": "decision-1",
            "actor": None,
        },
        "step_id": "step-1",
        "new_state": "succeeded",
        "evidence_ids": ["observation-1"],
    }


def test_synthesized_update_is_reducer_compatible_without_internal_application() -> (
    None
):
    plan, run, assessment, decision = prepared()
    update = synthesizer().synthesize(plan, run, assessment, decision)

    result = PlanRunReducer().apply(plan, run, update)

    progress = next(item for item in result.step_progress if item.step_id == "step-1")
    assert result.revision == run.revision + 1
    assert progress.state is StepProgressState.SUCCEEDED
    assert progress.evidence_ids == assessment.evidence_ids


def test_update_becomes_stale_if_run_advances_after_synthesis() -> None:
    plan, run, assessment, decision = prepared()
    update = synthesizer().synthesize(plan, run, assessment, decision)
    unrelated = make_observation(
        run,
        observation_id="unrelated-after-synthesis",
        step_id="step-2",
        observed_at=UPDATED + timedelta(seconds=1),
    )
    advanced = record(plan, run, unrelated)

    with pytest.raises(StalePlanRunUpdateError):
        PlanRunReducer().apply(plan, advanced, update)


def test_synthesizer_never_invokes_reducer(monkeypatch: pytest.MonkeyPatch) -> None:
    plan, run, assessment, decision = prepared()

    def forbidden(*args: object, **kwargs: object) -> PlanRun:
        raise AssertionError("reducer must not be invoked")

    monkeypatch.setattr(PlanRunReducer, "apply", forbidden)

    update = synthesizer().synthesize(plan, run, assessment, decision)

    assert isinstance(update, StepProgressUpdate)


def test_baseline_synthesis_performs_no_external_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, run, assessment, decision = prepared()

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("external I/O is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)

    update = synthesizer().synthesize(plan, run, assessment, decision)

    assert isinstance(update, StepProgressUpdate)
