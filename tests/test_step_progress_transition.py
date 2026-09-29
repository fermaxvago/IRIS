"""Step outcome assessment applicability and transition-decision tests."""

from __future__ import annotations

import builtins
import json
import socket
import subprocess
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from iris.outcome_assessment import (
    ConservativeStepOutcomeEvaluator,
    StepOutcomeAssessment,
    StepOutcomeStatus,
)
from iris.plan_runs import (
    PlanObservation,
    PlanRun,
    PlanRunFactory,
    PlanRunReducer,
    RecordObservationUpdate,
    RunProvenance,
    StepProgress,
    StepProgressState,
    StepProgressUpdate,
)
from iris.planning import Plan, PlanStep
from iris.step_progress_transition import (
    ConservativeStepProgressTransitionPolicy,
    StaleStepProgressTransitionDecisionError,
    StepProgressTransitionAction,
    StepProgressTransitionDecider,
    StepProgressTransitionDecision,
    StepProgressTransitionPolicy,
    StepProgressTransitionPolicyResult,
    StepProgressTransitionProvenance,
    StepProgressTransitionReason,
    StepProgressTransitionRequest,
    TransitionAssessmentEvidenceError,
    TransitionAssessmentIdentityError,
    TransitionDecisionGenerationError,
    TransitionDecisionIdentityError,
    TransitionPolicyContractViolationError,
    TransitionPolicyExecutionError,
    validate_step_progress_transition_decision_current,
)

CREATED = datetime(2026, 9, 29, 12, tzinfo=UTC)
OBSERVED = CREATED + timedelta(seconds=1)
ACTIVATED = CREATED + timedelta(seconds=2)
ASSESSED = CREATED + timedelta(seconds=3)
DECIDED = CREATED + timedelta(seconds=4)
PROVENANCE = RunProvenance("test", "wp021")


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


def transition(
    plan: Plan,
    run: PlanRun,
    step_id: str,
    state: StepProgressState,
    *,
    updated_at: datetime,
    evidence_ids: tuple[str, ...] = (),
) -> PlanRun:
    return PlanRunReducer().apply(
        plan,
        run,
        StepProgressUpdate(
            update_id=f"transition-{step_id}-{run.revision}",
            run_id=run.run_id,
            expected_revision=run.revision,
            updated_at=updated_at,
            provenance=PROVENANCE,
            step_id=step_id,
            new_state=state,
            evidence_ids=evidence_ids,
        ),
    )


def prepared_run(
    *,
    state: StepProgressState = StepProgressState.ACTIVE,
) -> tuple[Plan, PlanRun, PlanObservation]:
    plan = make_plan()
    run = make_run(plan)
    observation = make_observation(run)
    run = record(plan, run, observation)
    if state is StepProgressState.ACTIVE:
        run = transition(
            plan,
            run,
            "step-1",
            StepProgressState.ACTIVE,
            updated_at=ACTIVATED,
        )
    elif state is StepProgressState.SUCCEEDED:
        run = transition(
            plan,
            run,
            "step-1",
            StepProgressState.ACTIVE,
            updated_at=ACTIVATED,
        )
        run = transition(
            plan,
            run,
            "step-1",
            StepProgressState.SUCCEEDED,
            updated_at=ASSESSED,
            evidence_ids=(observation.observation_id,),
        )
    elif state is StepProgressState.FAILED:
        run = transition(
            plan,
            run,
            "step-1",
            StepProgressState.FAILED,
            updated_at=ACTIVATED,
            evidence_ids=(observation.observation_id,),
        )
    return plan, run, observation


def make_assessment(
    plan: Plan,
    run: PlanRun,
    *,
    status: StepOutcomeStatus = StepOutcomeStatus.SATISFIED,
    evidence_ids: tuple[str, ...] = ("observation-1",),
    assessment_id: str = "assessment-1",
    step_id: str = "step-1",
    run_revision: int | None = None,
    assessed_at: datetime = ASSESSED,
) -> StepOutcomeAssessment:
    return StepOutcomeAssessment(
        assessment_id=assessment_id,
        plan_id=plan.plan_id,
        run_id=run.run_id,
        run_revision=run.revision if run_revision is None else run_revision,
        step_id=step_id,
        status=status,
        evidence_ids=evidence_ids,
        evaluator_reference="test.satisfied.v1",
        assessed_at=assessed_at,
        details={"reason": "test_fixture"},
    )


def make_decider(
    *,
    policy: StepProgressTransitionPolicy | None = None,
    decided_at: datetime = DECIDED,
    decision_id: str = "decision-1",
) -> StepProgressTransitionDecider:
    return StepProgressTransitionDecider(
        transition_policy=policy,
        clock=lambda: decided_at,
        decision_id_factory=lambda: decision_id,
    )


def test_public_vocabularies_are_exact() -> None:
    assert {item.value for item in StepProgressTransitionAction} == {
        "transition",
        "no_transition",
    }
    assert {item.value for item in StepProgressTransitionReason} == {
        "outcome_satisfied",
        "outcome_not_satisfied",
        "insufficient_evidence",
        "indeterminate_outcome",
        "incomplete_current_evidence_basis",
        "assessment_predates_current_step_state",
        "step_not_started",
        "step_already_succeeded",
        "step_already_failed",
    }


def test_happy_path_requests_only_active_to_succeeded_and_stops() -> None:
    plan, run, observation = prepared_run()
    assessment = make_assessment(plan, run)
    run_before = run.to_data()
    assessment_before = assessment.to_data()

    decision = make_decider().decide(plan, run, plan.steps[0], assessment)

    assert decision.action is StepProgressTransitionAction.TRANSITION
    assert decision.target_state is StepProgressState.SUCCEEDED
    assert decision.reason is StepProgressTransitionReason.OUTCOME_SATISFIED
    assert decision.source_state is StepProgressState.ACTIVE
    assert decision.observed_revision == run.revision
    assert decision.assessment_id == assessment.assessment_id
    assert observation.observation_id not in decision.to_data()
    assert run.to_data() == run_before
    assert assessment.to_data() == assessment_before


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (
            StepOutcomeStatus.NOT_SATISFIED,
            StepProgressTransitionReason.OUTCOME_NOT_SATISFIED,
        ),
        (
            StepOutcomeStatus.INSUFFICIENT_EVIDENCE,
            StepProgressTransitionReason.INSUFFICIENT_EVIDENCE,
        ),
        (
            StepOutcomeStatus.INDETERMINATE,
            StepProgressTransitionReason.INDETERMINATE_OUTCOME,
        ),
    ],
)
def test_active_non_satisfied_statuses_abstain_without_failure(
    status: StepOutcomeStatus, reason: StepProgressTransitionReason
) -> None:
    plan, run, _ = prepared_run()
    evidence_ids = (
        () if status is StepOutcomeStatus.INSUFFICIENT_EVIDENCE else ("observation-1",)
    )
    if not evidence_ids:
        run = replace(run, observations=())
    assessment = make_assessment(
        plan,
        run,
        status=status,
        evidence_ids=evidence_ids,
    )

    decision = make_decider().decide(plan, run, plan.steps[0], assessment)

    assert decision.action is StepProgressTransitionAction.NO_TRANSITION
    assert decision.target_state is None
    assert decision.reason is reason


@pytest.mark.parametrize(
    ("state", "reason"),
    [
        (StepProgressState.NOT_STARTED, StepProgressTransitionReason.STEP_NOT_STARTED),
        (
            StepProgressState.SUCCEEDED,
            StepProgressTransitionReason.STEP_ALREADY_SUCCEEDED,
        ),
        (StepProgressState.FAILED, StepProgressTransitionReason.STEP_ALREADY_FAILED),
    ],
)
def test_non_active_states_never_transition_or_resurrect(
    state: StepProgressState, reason: StepProgressTransitionReason
) -> None:
    plan, run, _ = prepared_run(state=state)
    assessment = make_assessment(
        plan,
        run,
        assessed_at=max(ASSESSED, run.updated_at),
    )

    decision = make_decider(decided_at=max(DECIDED, run.updated_at)).decide(
        plan, run, plan.steps[0], assessment
    )

    assert decision.action is StepProgressTransitionAction.NO_TRANSITION
    assert decision.target_state is None
    assert decision.reason is reason


def test_incomplete_current_step_evidence_short_circuits_policy() -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run)
    second = make_observation(
        run,
        observation_id="observation-2",
        observed_at=ASSESSED + timedelta(milliseconds=100),
    )
    current = record(plan, run, second)
    policy = ExplodingPolicy()

    decision = make_decider(
        policy=policy,
        decided_at=DECIDED + timedelta(seconds=1),
    ).decide(plan, current, plan.steps[0], assessment)

    assert policy.calls == 0
    assert decision.action is StepProgressTransitionAction.NO_TRANSITION
    assert (
        decision.reason
        is StepProgressTransitionReason.INCOMPLETE_CURRENT_EVIDENCE_BASIS
    )
    assert decision.provenance.policy_id is None
    assert decision.provenance.policy_version is None


def test_evidence_basis_is_set_equivalent_and_ignores_unrelated_scopes() -> None:
    plan, run, _ = prepared_run()
    second = make_observation(
        run,
        observation_id="observation-2",
        observed_at=ACTIVATED + timedelta(milliseconds=100),
    )
    run = record(plan, run, second)
    other_step = make_observation(
        run,
        observation_id="other-step",
        step_id="step-2",
        observed_at=ACTIVATED + timedelta(milliseconds=200),
    )
    run = record(plan, run, other_step)
    run_level = make_observation(
        run,
        observation_id="run-level",
        step_id=None,
        observed_at=ACTIVATED + timedelta(milliseconds=300),
    )
    run = record(plan, run, run_level)
    assessment = make_assessment(
        plan,
        run,
        evidence_ids=("observation-2", "observation-1"),
        assessed_at=ASSESSED,
    )

    decision = make_decider().decide(plan, run, plan.steps[0], assessment)

    assert decision.action is StepProgressTransitionAction.TRANSITION
    assert decision.reason is StepProgressTransitionReason.OUTCOME_SATISFIED


def test_old_assessment_survives_newer_unrelated_run_revision() -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run)
    assessment_revision = assessment.run_revision
    unrelated = make_observation(
        run,
        observation_id="unrelated",
        step_id="step-2",
        observed_at=ASSESSED + timedelta(milliseconds=100),
    )
    current = record(plan, run, unrelated)

    decision = make_decider(decided_at=DECIDED + timedelta(seconds=1)).decide(
        plan, current, plan.steps[0], assessment
    )

    assert assessment_revision < current.revision
    assert assessment.run_revision == assessment_revision
    assert decision.observed_revision == current.revision
    assert decision.action is StepProgressTransitionAction.TRANSITION


def test_future_assessment_revision_is_identity_error() -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run, run_revision=run.revision + 1)

    with pytest.raises(TransitionAssessmentIdentityError, match="future"):
        make_decider().decide(plan, run, plan.steps[0], assessment)


def test_assessment_cannot_predate_run_creation() -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(
        plan,
        run,
        assessed_at=CREATED - timedelta(microseconds=1),
    )

    with pytest.raises(TransitionAssessmentIdentityError, match="predate"):
        make_decider().decide(plan, run, plan.steps[0], assessment)


def test_missing_assessment_evidence_is_lineage_error_not_incomplete_basis() -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run)
    current = replace(
        run,
        revision=run.revision + 1,
        updated_at=run.updated_at + timedelta(seconds=1),
        observations=(),
    )

    with pytest.raises(TransitionAssessmentEvidenceError, match="absent"):
        make_decider(decided_at=DECIDED + timedelta(seconds=1)).decide(
            plan, current, plan.steps[0], assessment
        )


def test_assessment_evidence_resolved_to_another_step_is_lineage_error() -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run)
    foreign = make_observation(
        run,
        observation_id="observation-1",
        step_id="step-2",
    )
    current = replace(run, observations=(foreign,))

    with pytest.raises(TransitionAssessmentEvidenceError, match="not scoped"):
        make_decider().decide(plan, current, plan.steps[0], assessment)


@pytest.mark.parametrize("field", ["plan_id", "run_id", "step_id"])
def test_foreign_assessment_identity_is_an_error(field: str) -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run)
    assessment = replace(assessment, **{field: f"foreign-{field}"})

    with pytest.raises(TransitionAssessmentIdentityError, match="different"):
        make_decider().decide(plan, run, plan.steps[0], assessment)


def test_noncanonical_plan_step_is_rejected() -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run)
    changed = PlanStep("step-1", "Perform work", "A different result")

    with pytest.raises(TransitionAssessmentIdentityError, match="canonical"):
        make_decider().decide(plan, run, changed, assessment)


def test_assessment_predating_active_state_short_circuits_policy() -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(
        plan,
        run,
        assessed_at=ACTIVATED - timedelta(microseconds=1),
    )
    policy = ExplodingPolicy()

    decision = make_decider(policy=policy).decide(plan, run, plan.steps[0], assessment)

    assert policy.calls == 0
    assert decision.action is StepProgressTransitionAction.NO_TRANSITION
    assert (
        decision.reason
        is StepProgressTransitionReason.ASSESSMENT_PREDATES_CURRENT_STEP_STATE
    )
    assert decision.provenance.policy_id is None


@pytest.mark.parametrize(
    "assessed_at", [ACTIVATED, ACTIVATED + timedelta(microseconds=1)]
)
def test_assessment_at_or_after_activation_can_transition(
    assessed_at: datetime,
) -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run, assessed_at=assessed_at)

    decision = make_decider().decide(plan, run, plan.steps[0], assessment)

    assert decision.action is StepProgressTransitionAction.TRANSITION


def test_policy_request_contains_only_validated_operational_projection() -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run)
    policy = CapturingPolicy()

    make_decider(policy=policy).decide(plan, run, plan.steps[0], assessment)

    assert policy.request == StepProgressTransitionRequest(
        plan.plan_id,
        run.run_id,
        run.revision,
        "step-1",
        assessment.assessment_id,
        StepProgressState.ACTIVE,
        StepOutcomeStatus.SATISFIED,
    )
    assert "expected_outcome" not in policy.request.to_data()
    assert "evidence_ids" not in policy.request.to_data()


@pytest.mark.parametrize(
    ("state", "status", "action", "target", "reason"),
    [
        (
            StepProgressState.ACTIVE,
            StepOutcomeStatus.SATISFIED,
            StepProgressTransitionAction.TRANSITION,
            StepProgressState.SUCCEEDED,
            StepProgressTransitionReason.OUTCOME_SATISFIED,
        ),
        (
            StepProgressState.ACTIVE,
            StepOutcomeStatus.NOT_SATISFIED,
            StepProgressTransitionAction.NO_TRANSITION,
            None,
            StepProgressTransitionReason.OUTCOME_NOT_SATISFIED,
        ),
        (
            StepProgressState.ACTIVE,
            StepOutcomeStatus.INSUFFICIENT_EVIDENCE,
            StepProgressTransitionAction.NO_TRANSITION,
            None,
            StepProgressTransitionReason.INSUFFICIENT_EVIDENCE,
        ),
        (
            StepProgressState.ACTIVE,
            StepOutcomeStatus.INDETERMINATE,
            StepProgressTransitionAction.NO_TRANSITION,
            None,
            StepProgressTransitionReason.INDETERMINATE_OUTCOME,
        ),
        (
            StepProgressState.NOT_STARTED,
            StepOutcomeStatus.SATISFIED,
            StepProgressTransitionAction.NO_TRANSITION,
            None,
            StepProgressTransitionReason.STEP_NOT_STARTED,
        ),
        (
            StepProgressState.SUCCEEDED,
            StepOutcomeStatus.SATISFIED,
            StepProgressTransitionAction.NO_TRANSITION,
            None,
            StepProgressTransitionReason.STEP_ALREADY_SUCCEEDED,
        ),
        (
            StepProgressState.FAILED,
            StepOutcomeStatus.SATISFIED,
            StepProgressTransitionAction.NO_TRANSITION,
            None,
            StepProgressTransitionReason.STEP_ALREADY_FAILED,
        ),
    ],
)
def test_conservative_policy_matrix(
    state: StepProgressState,
    status: StepOutcomeStatus,
    action: StepProgressTransitionAction,
    target: StepProgressState | None,
    reason: StepProgressTransitionReason,
) -> None:
    request = StepProgressTransitionRequest(
        "plan-1", "run-1", 3, "step-1", "assessment-1", state, status
    )

    result = ConservativeStepProgressTransitionPolicy().decide(request)

    assert result == StepProgressTransitionPolicyResult(action, target, reason)


@pytest.mark.parametrize(
    ("action", "target", "reason"),
    [
        (
            StepProgressTransitionAction.TRANSITION,
            StepProgressState.FAILED,
            StepProgressTransitionReason.OUTCOME_SATISFIED,
        ),
        (
            StepProgressTransitionAction.TRANSITION,
            StepProgressState.ACTIVE,
            StepProgressTransitionReason.OUTCOME_SATISFIED,
        ),
        (
            StepProgressTransitionAction.TRANSITION,
            StepProgressState.NOT_STARTED,
            StepProgressTransitionReason.OUTCOME_SATISFIED,
        ),
        (
            StepProgressTransitionAction.TRANSITION,
            None,
            StepProgressTransitionReason.OUTCOME_SATISFIED,
        ),
        (
            StepProgressTransitionAction.NO_TRANSITION,
            StepProgressState.SUCCEEDED,
            StepProgressTransitionReason.OUTCOME_NOT_SATISFIED,
        ),
    ],
)
def test_policy_result_rejects_unsupported_transition_shapes(
    action: StepProgressTransitionAction,
    target: StepProgressState | None,
    reason: StepProgressTransitionReason,
) -> None:
    with pytest.raises(TransitionPolicyContractViolationError):
        StepProgressTransitionPolicyResult(action, target, reason)


def test_policy_wrong_return_type_is_contract_violation() -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run)

    with pytest.raises(TransitionPolicyContractViolationError, match="must return"):
        make_decider(policy=WrongReturnPolicy()).decide(
            plan, run, plan.steps[0], assessment
        )


def test_policy_incompatible_valid_result_is_contract_violation() -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run)
    result = StepProgressTransitionPolicyResult(
        StepProgressTransitionAction.NO_TRANSITION,
        None,
        StepProgressTransitionReason.INDETERMINATE_OUTCOME,
    )

    with pytest.raises(TransitionPolicyContractViolationError, match="incompatible"):
        make_decider(policy=StaticPolicy(result)).decide(
            plan, run, plan.steps[0], assessment
        )


def test_policy_malformed_provenance_is_contract_violation() -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run)

    with pytest.raises(TransitionPolicyContractViolationError, match="provenance"):
        make_decider(policy=BlankPolicyId()).decide(
            plan, run, plan.steps[0], assessment
        )


def test_policy_operational_failure_is_not_no_transition() -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run)

    with pytest.raises(TransitionPolicyExecutionError, match="execution failed"):
        make_decider(policy=ExplodingPolicy()).decide(
            plan, run, plan.steps[0], assessment
        )


def test_policy_provenance_is_recorded_only_after_invocation() -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run)
    decision = make_decider().decide(plan, run, plan.steps[0], assessment)

    assert decision.provenance == StepProgressTransitionProvenance(
        "step_progress_transition_decider",
        "1",
        "conservative_step_progress_transition",
        "1",
    )


def test_decision_serialization_is_stable_and_minimal() -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run)
    decision = make_decider().decide(plan, run, plan.steps[0], assessment)

    data = decision.to_data()
    assert tuple(data) == (
        "decision_id",
        "plan_id",
        "run_id",
        "observed_revision",
        "step_id",
        "assessment_id",
        "source_state",
        "action",
        "target_state",
        "reason",
        "provenance",
        "decided_at",
    )
    assert data["source_state"] == "active"
    assert data["action"] == "transition"
    assert data["target_state"] == "succeeded"
    assert json.dumps(data, sort_keys=True) == json.dumps(
        decision.to_data(), sort_keys=True
    )
    assert "evidence_ids" not in data
    assert "expected_outcome" not in data
    assert "details" not in data


@pytest.mark.parametrize("collision", ["plan-1", "run-1", "step-1", "assessment-1"])
def test_decision_identity_is_independent(collision: str) -> None:
    with pytest.raises(TransitionDecisionIdentityError, match="independent"):
        StepProgressTransitionDecision(
            collision,
            "plan-1",
            "run-1",
            0,
            "step-1",
            "assessment-1",
            StepProgressState.ACTIVE,
            StepProgressTransitionAction.TRANSITION,
            StepProgressState.SUCCEEDED,
            StepProgressTransitionReason.OUTCOME_SATISFIED,
            StepProgressTransitionProvenance("decider", policy_id="policy"),
            DECIDED,
        )


def test_decision_models_are_frozen_and_utc_normalized() -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run)
    mexico = timezone(timedelta(hours=-6))
    decision = make_decider(decided_at=DECIDED.astimezone(mexico)).decide(
        plan, run, plan.steps[0], assessment
    )

    assert decision.decided_at.tzinfo is UTC
    with pytest.raises(FrozenInstanceError):
        decision.run_id = "changed"  # type: ignore[misc]


def test_decision_timestamp_must_follow_run_and_assessment() -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run)

    with pytest.raises(TransitionDecisionIdentityError, match="assessment"):
        make_decider(
            decided_at=assessment.assessed_at - timedelta(microseconds=1)
        ).decide(plan, run, plan.steps[0], assessment)


@pytest.mark.parametrize("factory", ["clock", "id"])
def test_generation_service_failures_are_errors(factory: str) -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run)

    def fail() -> object:
        raise RuntimeError("boom")

    kwargs: dict[str, object]
    if factory == "clock":
        kwargs = {"clock": fail}
    else:
        kwargs = {"decision_id_factory": fail}
    decider = StepProgressTransitionDecider(**kwargs)  # type: ignore[arg-type]

    with pytest.raises(TransitionDecisionGenerationError):
        decider.decide(plan, run, plan.steps[0], assessment)


def test_multiple_decisions_over_same_inputs_are_allowed() -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run)
    first = make_decider(decision_id="decision-1").decide(
        plan, run, plan.steps[0], assessment
    )
    second = make_decider(decision_id="decision-2").decide(
        plan, run, plan.steps[0], assessment
    )

    assert first.decision_id != second.decision_id
    assert first.action == second.action
    assert first.observed_revision == second.observed_revision


def test_currentness_validator_accepts_same_revision_and_source_state() -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run)
    decision = make_decider().decide(plan, run, plan.steps[0], assessment)

    assert (
        validate_step_progress_transition_decision_current(plan, run, decision) is None
    )


def test_decision_is_stale_after_unrelated_run_revision() -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run)
    decision = make_decider().decide(plan, run, plan.steps[0], assessment)
    unrelated = make_observation(
        run,
        observation_id="unrelated",
        step_id="step-2",
        observed_at=DECIDED + timedelta(milliseconds=100),
    )
    current = record(plan, run, unrelated)

    with pytest.raises(
        StaleStepProgressTransitionDecisionError, match="current revision"
    ):
        validate_step_progress_transition_decision_current(plan, current, decision)


def test_currentness_validator_rejects_same_revision_source_state_mismatch() -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run, status=StepOutcomeStatus.NOT_SATISFIED)
    decision = make_decider().decide(plan, run, plan.steps[0], assessment)
    progress = tuple(
        StepProgress(item.step_id, StepProgressState.NOT_STARTED, run.created_at)
        if item.step_id == decision.step_id
        else item
        for item in run.step_progress
    )
    fabricated = replace(run, step_progress=progress)

    with pytest.raises(TransitionDecisionIdentityError, match="source_state"):
        validate_step_progress_transition_decision_current(plan, fabricated, decision)


def test_currentness_validator_rejects_wrong_plan_run_and_unknown_step() -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run, status=StepOutcomeStatus.NOT_SATISFIED)
    decision = make_decider().decide(plan, run, plan.steps[0], assessment)

    with pytest.raises(TransitionDecisionIdentityError, match="different Plan"):
        validate_step_progress_transition_decision_current(
            plan, run, replace(decision, plan_id="foreign-plan")
        )
    with pytest.raises(TransitionDecisionIdentityError, match="different PlanRun"):
        validate_step_progress_transition_decision_current(
            plan, run, replace(decision, run_id="foreign-run")
        )
    with pytest.raises(TransitionDecisionIdentityError, match="unknown step"):
        validate_step_progress_transition_decision_current(
            plan, run, replace(decision, step_id="unknown-step")
        )


def test_wp020_evaluator_integration_remains_epistemic_and_no_transition() -> None:
    plan, run, observation = prepared_run()
    assessment = ConservativeStepOutcomeEvaluator(
        clock=lambda: ASSESSED,
        assessment_id_factory=lambda: "assessment-wp020",
    ).evaluate(plan, run, plan.steps[0], (observation,))

    decision = make_decider().decide(plan, run, plan.steps[0], assessment)

    assert assessment.status is StepOutcomeStatus.INDETERMINATE
    assert decision.action is StepProgressTransitionAction.NO_TRANSITION
    assert decision.reason is StepProgressTransitionReason.INDETERMINATE_OUTCOME


def test_no_evidence_wp020_assessment_maps_to_insufficient_not_failure() -> None:
    plan = make_plan()
    run = make_run(plan)
    run = transition(
        plan,
        run,
        "step-1",
        StepProgressState.ACTIVE,
        updated_at=ACTIVATED,
    )
    assessment = ConservativeStepOutcomeEvaluator(
        clock=lambda: ASSESSED,
        assessment_id_factory=lambda: "assessment-empty",
    ).evaluate(plan, run, plan.steps[0], ())

    decision = make_decider().decide(plan, run, plan.steps[0], assessment)

    assert decision.reason is StepProgressTransitionReason.INSUFFICIENT_EVIDENCE
    assert decision.target_state is None


def test_baseline_decider_performs_no_external_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, run, _ = prepared_run()
    assessment = make_assessment(plan, run)

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("external I/O is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)

    decision = make_decider().decide(plan, run, plan.steps[0], assessment)

    assert decision.action is StepProgressTransitionAction.TRANSITION


def test_policy_protocol_is_runtime_checkable() -> None:
    assert isinstance(
        ConservativeStepProgressTransitionPolicy(), StepProgressTransitionPolicy
    )


class ExplodingPolicy:
    policy_id = "exploding"
    policy_version = "1"

    def __init__(self) -> None:
        self.calls = 0

    def decide(
        self, request: StepProgressTransitionRequest
    ) -> StepProgressTransitionPolicyResult:
        self.calls += 1
        raise RuntimeError("policy failed")


class CapturingPolicy:
    policy_id = "capturing"
    policy_version = "1"

    def __init__(self) -> None:
        self.request: StepProgressTransitionRequest | None = None

    def decide(
        self, request: StepProgressTransitionRequest
    ) -> StepProgressTransitionPolicyResult:
        self.request = request
        return StepProgressTransitionPolicyResult(
            StepProgressTransitionAction.TRANSITION,
            StepProgressState.SUCCEEDED,
            StepProgressTransitionReason.OUTCOME_SATISFIED,
        )


class WrongReturnPolicy:
    policy_id = "wrong_return"
    policy_version = "1"

    def decide(self, request: StepProgressTransitionRequest) -> object:
        return {"action": "transition"}


class StaticPolicy:
    policy_id = "static"
    policy_version = "1"

    def __init__(self, result: StepProgressTransitionPolicyResult) -> None:
        self.result = result

    def decide(
        self, request: StepProgressTransitionRequest
    ) -> StepProgressTransitionPolicyResult:
        return self.result


class BlankPolicyId:
    policy_id = ""
    policy_version = "1"

    def decide(
        self, request: StepProgressTransitionRequest
    ) -> StepProgressTransitionPolicyResult:
        return StepProgressTransitionPolicyResult(
            StepProgressTransitionAction.TRANSITION,
            StepProgressState.SUCCEEDED,
            StepProgressTransitionReason.OUTCOME_SATISFIED,
        )
