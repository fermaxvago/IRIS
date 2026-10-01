"""WP028 complete-evidence assessment to transition-decision composition."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from iris.outcome_assessment import (
    StepOutcomeAssessment,
    StepOutcomeEvaluator,
    StepOutcomeStatus,
)
from iris.plan_runs import (
    PlanObservation,
    PlanRun,
    PlanRunFactory,
    PlanRunIdentityError,
    PlanRunReducer,
    RecordObservationUpdate,
    RunProvenance,
    StepProgressState,
    StepProgressUpdate,
    UnknownPlanStepError,
)
from iris.plan_step_evidence_assessment import PlanStepEvidenceAssessor
from iris.plan_step_evidence_transition import (
    PlanStepEvidenceTransitionComposer,
    PlanStepEvidenceTransitionDecisionResult,
    PlanStepEvidenceTransitionInvariantError,
)
from iris.planning import Plan, PlanStep
from iris.step_progress_transition import (
    StaleStepProgressTransitionDecisionError,
    StepProgressTransitionAction,
    StepProgressTransitionDecider,
    StepProgressTransitionDecision,
    StepProgressTransitionReason,
)
from iris.step_progress_update_synthesis import StepProgressUpdateSynthesizer

CREATED = datetime(2026, 10, 1, 15, tzinfo=UTC)
OBSERVED = CREATED + timedelta(seconds=1)
ACTIVATED = CREATED + timedelta(seconds=2)
TERMINATED = CREATED + timedelta(seconds=3)
ASSESSED = CREATED + timedelta(seconds=4)
DECIDED = CREATED + timedelta(seconds=5)
UPDATED = CREATED + timedelta(seconds=6)
PROVENANCE = RunProvenance("test", "wp028-reconstruction")


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


def record_observation(plan: Plan, run: PlanRun) -> PlanRun:
    observation = PlanObservation(
        observation_id="observation-1",
        run_id=run.run_id,
        step_id="step-1",
        source="test",
        source_reference="evidence-1",
        observed_at=OBSERVED,
        kind="verification",
        data={"verified": True},
    )
    return PlanRunReducer().apply(
        plan,
        run,
        RecordObservationUpdate(
            update_id="record-observation-1",
            run_id=run.run_id,
            expected_revision=run.revision,
            updated_at=OBSERVED,
            provenance=PROVENANCE,
            observation=observation,
        ),
    )


def set_state(
    plan: Plan,
    run: PlanRun,
    state: StepProgressState,
) -> PlanRun:
    if state is StepProgressState.NOT_STARTED:
        return run
    if state is StepProgressState.ACTIVE:
        return PlanRunReducer().apply(
            plan,
            run,
            StepProgressUpdate(
                update_id=f"activate-{run.revision}",
                run_id=run.run_id,
                expected_revision=run.revision,
                updated_at=ACTIVATED,
                provenance=PROVENANCE,
                step_id="step-1",
                new_state=state,
                evidence_ids=(),
            ),
        )
    if state is StepProgressState.SUCCEEDED:
        active = set_state(plan, run, StepProgressState.ACTIVE)
        return PlanRunReducer().apply(
            plan,
            active,
            StepProgressUpdate(
                update_id=f"succeed-{active.revision}",
                run_id=active.run_id,
                expected_revision=active.revision,
                updated_at=TERMINATED,
                provenance=PROVENANCE,
                step_id="step-1",
                new_state=state,
                evidence_ids=("observation-1",),
            ),
        )
    return PlanRunReducer().apply(
        plan,
        run,
        StepProgressUpdate(
            update_id=f"fail-{run.revision}",
            run_id=run.run_id,
            expected_revision=run.revision,
            updated_at=TERMINATED,
            provenance=PROVENANCE,
            step_id="step-1",
            new_state=state,
            evidence_ids=("observation-1",),
        ),
    )


@dataclass
class StatusEvaluator:
    status: StepOutcomeStatus
    calls: list[tuple[Plan, PlanRun, PlanStep, tuple[PlanObservation, ...]]] = field(
        default_factory=list
    )

    def evaluate(
        self,
        plan: Plan,
        run: PlanRun,
        step: PlanStep,
        evidence: tuple[PlanObservation, ...],
    ) -> StepOutcomeAssessment:
        self.calls.append((plan, run, step, evidence))
        return StepOutcomeAssessment(
            assessment_id="assessment-1",
            plan_id=plan.plan_id,
            run_id=run.run_id,
            run_revision=run.revision,
            step_id=step.step_id,
            status=self.status,
            evidence_ids=tuple(item.observation_id for item in evidence),
            evaluator_reference="test.status.v1",
            assessed_at=ASSESSED,
            details={"status": self.status.value},
        )


def composer_for(status: StepOutcomeStatus) -> PlanStepEvidenceTransitionComposer:
    evaluator = StatusEvaluator(status)
    return PlanStepEvidenceTransitionComposer(
        assessor=PlanStepEvidenceAssessor(cast(StepOutcomeEvaluator, evaluator)),
        transition_decider=StepProgressTransitionDecider(
            clock=lambda: DECIDED,
            decision_id_factory=lambda: "decision-1",
        ),
    )


def prepared(
    *,
    state: StepProgressState = StepProgressState.ACTIVE,
    with_evidence: bool = True,
) -> tuple[Plan, PlanRun]:
    plan = make_plan()
    run = make_run(plan)
    if with_evidence:
        run = record_observation(plan, run)
    return plan, set_state(plan, run, state)


def test_public_api_and_constructor_contract() -> None:
    assert (
        PlanStepEvidenceTransitionComposer.__name__
        == "PlanStepEvidenceTransitionComposer"
    )
    assert (
        PlanStepEvidenceTransitionDecisionResult.__name__
        == "PlanStepEvidenceTransitionDecisionResult"
    )
    with pytest.raises(TypeError, match="assessor"):
        PlanStepEvidenceTransitionComposer(assessor=cast(Any, object()))
    with pytest.raises(TypeError, match="transition_decider"):
        PlanStepEvidenceTransitionComposer(transition_decider=cast(Any, object()))


@pytest.mark.parametrize(
    ("position", "bad_value", "message"),
    [
        (0, object(), "plan must be a Plan"),
        (1, object(), "run must be a PlanRun"),
        (2, object(), "step_id must be a string"),
    ],
)
def test_wrong_top_level_inputs_propagate_canonical_validation(
    position: int,
    bad_value: object,
    message: str,
) -> None:
    plan = make_plan()
    values: list[object] = [plan, make_run(plan), "step-1"]
    values[position] = bad_value
    with pytest.raises(TypeError, match=message):
        PlanStepEvidenceTransitionComposer().compose(*cast(Any, values))


def test_positive_path_preserves_assessment_and_returns_succeeded_decision() -> None:
    plan, run = prepared()
    before = run.to_data()

    result = composer_for(StepOutcomeStatus.SATISFIED).compose(plan, run, "step-1")

    assert result.assessment.run_revision == run.revision
    assert result.transition_decision.observed_revision == run.revision
    assert result.transition_decision.assessment_id == result.assessment.assessment_id
    assert result.transition_decision.action is StepProgressTransitionAction.TRANSITION
    assert result.transition_decision.target_state is StepProgressState.SUCCEEDED
    assert (
        result.transition_decision.reason
        is StepProgressTransitionReason.OUTCOME_SATISFIED
    )
    assert run.to_data() == before


@pytest.mark.parametrize(
    ("state", "status", "with_evidence", "reason"),
    [
        (
            StepProgressState.NOT_STARTED,
            StepOutcomeStatus.SATISFIED,
            True,
            StepProgressTransitionReason.STEP_NOT_STARTED,
        ),
        (
            StepProgressState.SUCCEEDED,
            StepOutcomeStatus.SATISFIED,
            True,
            StepProgressTransitionReason.STEP_ALREADY_SUCCEEDED,
        ),
        (
            StepProgressState.FAILED,
            StepOutcomeStatus.SATISFIED,
            True,
            StepProgressTransitionReason.STEP_ALREADY_FAILED,
        ),
        (
            StepProgressState.ACTIVE,
            StepOutcomeStatus.NOT_SATISFIED,
            True,
            StepProgressTransitionReason.OUTCOME_NOT_SATISFIED,
        ),
        (
            StepProgressState.ACTIVE,
            StepOutcomeStatus.INSUFFICIENT_EVIDENCE,
            False,
            StepProgressTransitionReason.INSUFFICIENT_EVIDENCE,
        ),
        (
            StepProgressState.ACTIVE,
            StepOutcomeStatus.INDETERMINATE,
            True,
            StepProgressTransitionReason.INDETERMINATE_OUTCOME,
        ),
    ],
)
def test_valid_no_transition_results_are_returned_normally(
    state: StepProgressState,
    status: StepOutcomeStatus,
    with_evidence: bool,
    reason: StepProgressTransitionReason,
) -> None:
    plan, run = prepared(state=state, with_evidence=with_evidence)

    result = composer_for(status).compose(plan, run, "step-1")

    assert (
        result.transition_decision.action is StepProgressTransitionAction.NO_TRANSITION
    )
    assert result.transition_decision.target_state is None
    assert result.transition_decision.reason is reason


def test_default_components_preserve_empty_evidence_semantics() -> None:
    plan, run = prepared(with_evidence=False)

    result = PlanStepEvidenceTransitionComposer().compose(plan, run, "step-1")

    assert result.assessment.status is StepOutcomeStatus.INSUFFICIENT_EVIDENCE
    assert result.assessment.evidence_ids == ()
    assert (
        result.transition_decision.reason
        is StepProgressTransitionReason.INSUFFICIENT_EVIDENCE
    )


def test_unknown_step_fails_explicitly() -> None:
    plan = make_plan()
    with pytest.raises(UnknownPlanStepError, match="step-missing"):
        PlanStepEvidenceTransitionComposer().compose(
            plan, make_run(plan), "step-missing"
        )


def test_invalid_plan_run_lineage_propagates_canonical_error() -> None:
    plan = make_plan()
    foreign_plan = make_plan(plan_id="plan-2")
    with pytest.raises(PlanRunIdentityError):
        PlanStepEvidenceTransitionComposer().compose(
            plan, make_run(foreign_plan), "step-1"
        )


class RecordingAssessor(PlanStepEvidenceAssessor):
    def __init__(self, delegate: PlanStepEvidenceAssessor) -> None:
        super().__init__()
        self.delegate = delegate
        self.calls: list[tuple[Plan, PlanRun, str]] = []

    def assess(self, plan: Plan, run: PlanRun, step_id: str) -> StepOutcomeAssessment:
        self.calls.append((plan, run, step_id))
        return self.delegate.assess(plan, run, step_id)


class RecordingDecider(StepProgressTransitionDecider):
    def __init__(self, delegate: StepProgressTransitionDecider) -> None:
        super().__init__()
        self.delegate = delegate
        self.calls: list[tuple[Plan, PlanRun, PlanStep, StepOutcomeAssessment]] = []

    def decide(
        self,
        plan: Plan,
        run: PlanRun,
        step: PlanStep,
        assessment: StepOutcomeAssessment,
    ) -> StepProgressTransitionDecision:
        self.calls.append((plan, run, step, assessment))
        return self.delegate.decide(plan, run, step, assessment)


def test_exactly_one_operation_and_exact_artifact_preservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, run = prepared()
    evaluator = StatusEvaluator(StepOutcomeStatus.SATISFIED)
    assessor = RecordingAssessor(
        PlanStepEvidenceAssessor(cast(StepOutcomeEvaluator, evaluator))
    )
    decider = RecordingDecider(
        StepProgressTransitionDecider(
            clock=lambda: DECIDED,
            decision_id_factory=lambda: "decision-1",
        )
    )
    import iris.plan_step_evidence_transition.composer as composer_module

    original_validator = (
        composer_module.validate_step_progress_transition_decision_current
    )
    validator_calls: list[tuple[Plan, PlanRun, StepProgressTransitionDecision]] = []

    def recording_validator(
        supplied_plan: Plan,
        supplied_run: PlanRun,
        decision: StepProgressTransitionDecision,
    ) -> None:
        validator_calls.append((supplied_plan, supplied_run, decision))
        original_validator(supplied_plan, supplied_run, decision)

    monkeypatch.setattr(
        composer_module,
        "validate_step_progress_transition_decision_current",
        recording_validator,
    )

    result = PlanStepEvidenceTransitionComposer(
        assessor=assessor,
        transition_decider=decider,
    ).compose(plan, run, "step-1")

    assert len(assessor.calls) == len(decider.calls) == len(validator_calls) == 1
    assert decider.calls[0][2] is plan.steps[0]
    assert decider.calls[0][3] is result.assessment
    assert validator_calls[0][2] is result.transition_decision


class StaleDecisionDecider(StepProgressTransitionDecider):
    def __init__(self) -> None:
        super().__init__(
            clock=lambda: DECIDED,
            decision_id_factory=lambda: "decision-1",
        )

    def decide(
        self,
        plan: Plan,
        run: PlanRun,
        step: PlanStep,
        assessment: StepOutcomeAssessment,
    ) -> StepProgressTransitionDecision:
        decision = super().decide(plan, run, step, assessment)
        return replace(decision, observed_revision=run.revision + 1)


def test_noncurrent_decision_is_not_returned() -> None:
    plan, run = prepared()
    evaluator = StatusEvaluator(StepOutcomeStatus.SATISFIED)
    with pytest.raises(StaleStepProgressTransitionDecisionError):
        PlanStepEvidenceTransitionComposer(
            assessor=PlanStepEvidenceAssessor(cast(StepOutcomeEvaluator, evaluator)),
            transition_decider=StaleDecisionDecider(),
        ).compose(plan, run, "step-1")


def test_actionable_result_is_structurally_consumable_by_wp022() -> None:
    plan, run = prepared()
    result = composer_for(StepOutcomeStatus.SATISFIED).compose(plan, run, "step-1")

    update = StepProgressUpdateSynthesizer(
        clock=lambda: UPDATED,
        update_id_factory=lambda: "progress-update-1",
    ).synthesize(
        plan,
        run,
        result.assessment,
        result.transition_decision,
    )

    assert update.expected_revision == run.revision
    assert update.new_state is StepProgressState.SUCCEEDED
    assert update.evidence_ids == result.assessment.evidence_ids


def test_result_is_immutable_and_serializes_both_artifacts() -> None:
    plan, run = prepared()
    result = composer_for(StepOutcomeStatus.SATISFIED).compose(plan, run, "step-1")

    with pytest.raises(FrozenInstanceError):
        result.assessment = result.assessment  # type: ignore[misc]
    assert result.to_data() == {
        "assessment": result.assessment.to_data(),
        "transition_decision": result.transition_decision.to_data(),
    }


def test_result_rejects_contradictory_lineage_and_types() -> None:
    plan, run = prepared()
    valid = composer_for(StepOutcomeStatus.SATISFIED).compose(plan, run, "step-1")
    with pytest.raises(TypeError, match="assessment"):
        PlanStepEvidenceTransitionDecisionResult(
            cast(Any, object()), valid.transition_decision
        )
    with pytest.raises(TypeError, match="transition_decision"):
        PlanStepEvidenceTransitionDecisionResult(valid.assessment, cast(Any, object()))
    with pytest.raises(PlanStepEvidenceTransitionInvariantError, match="lineage"):
        PlanStepEvidenceTransitionDecisionResult(
            valid.assessment,
            replace(valid.transition_decision, assessment_id="assessment-2"),
        )
    with pytest.raises(PlanStepEvidenceTransitionInvariantError, match="revision"):
        PlanStepEvidenceTransitionDecisionResult(
            valid.assessment,
            replace(
                valid.transition_decision,
                observed_revision=valid.transition_decision.observed_revision + 1,
            ),
        )
