"""WP029 assessment/transition to optional progress-update preparation."""

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
from iris.plan_run_advancement import PlanRunProgressAdvancer
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
from iris.plan_step_evidence_assessment import (
    PlanStepEvidenceAssessmentLineageError,
    PlanStepEvidenceAssessor,
)
from iris.plan_step_evidence_transition import (
    PlanStepEvidenceTransitionComposer,
    PlanStepEvidenceTransitionDecisionResult,
)
from iris.plan_step_progress_update_preparation import (
    PlanStepProgressUpdatePreparationError,
    PlanStepProgressUpdatePreparationInvariantError,
    PlanStepProgressUpdatePreparationResult,
    PlanStepProgressUpdatePreparer,
)
from iris.planning import Plan, PlanStep
from iris.step_progress_transition import (
    StepProgressTransitionAction,
    StepProgressTransitionDecider,
    StepProgressTransitionDecision,
    StepProgressTransitionProvenance,
    StepProgressTransitionReason,
)
from iris.step_progress_update_synthesis import StepProgressUpdateSynthesizer

CREATED = datetime(2026, 10, 2, 8, tzinfo=UTC)
OBSERVED = CREATED + timedelta(seconds=1)
ACTIVATED = CREATED + timedelta(seconds=2)
ASSESSED = CREATED + timedelta(seconds=3)
DECIDED = CREATED + timedelta(seconds=4)
UPDATED = CREATED + timedelta(seconds=5)
PROVENANCE = RunProvenance("test", "wp029")


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
            "record-observation-1",
            run.run_id,
            run.revision,
            OBSERVED,
            PROVENANCE,
            observation,
        ),
    )


def set_state(plan: Plan, run: PlanRun, state: StepProgressState) -> PlanRun:
    if state is StepProgressState.NOT_STARTED:
        return run
    active = PlanRunReducer().apply(
        plan,
        run,
        StepProgressUpdate(
            "activate-step-1",
            run.run_id,
            run.revision,
            ACTIVATED,
            PROVENANCE,
            "step-1",
            StepProgressState.ACTIVE,
        ),
    )
    if state is StepProgressState.ACTIVE:
        return active
    return PlanRunReducer().apply(
        plan,
        active,
        StepProgressUpdate(
            f"terminal-{state.value}",
            active.run_id,
            active.revision,
            DECIDED,
            PROVENANCE,
            "step-1",
            state,
            ("observation-1",),
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
            "assessment-1",
            plan.plan_id,
            run.run_id,
            run.revision,
            step.step_id,
            self.status,
            tuple(item.observation_id for item in evidence),
            "test.status.v1",
            ASSESSED,
            {"status": self.status.value},
        )


def composer_for(status: StepOutcomeStatus) -> PlanStepEvidenceTransitionComposer:
    return PlanStepEvidenceTransitionComposer(
        assessor=PlanStepEvidenceAssessor(
            cast(StepOutcomeEvaluator, StatusEvaluator(status))
        ),
        transition_decider=StepProgressTransitionDecider(
            clock=lambda: DECIDED,
            decision_id_factory=lambda: "decision-1",
        ),
    )


def synthesizer_for(
    update_id_factory: Any = lambda: "progress-update-1",
) -> StepProgressUpdateSynthesizer:
    return StepProgressUpdateSynthesizer(
        clock=lambda: UPDATED,
        update_id_factory=update_id_factory,
    )


class RecordingComposer(PlanStepEvidenceTransitionComposer):
    def __init__(
        self,
        delegate: PlanStepEvidenceTransitionComposer,
        forced: object | None = None,
    ) -> None:
        super().__init__()
        self.delegate = delegate
        self.forced = forced
        self.calls: list[tuple[Plan, PlanRun, str]] = []

    def compose(
        self, plan: Plan, run: PlanRun, step_id: str
    ) -> PlanStepEvidenceTransitionDecisionResult:
        self.calls.append((plan, run, step_id))
        if self.forced is not None:
            return cast(PlanStepEvidenceTransitionDecisionResult, self.forced)
        return self.delegate.compose(plan, run, step_id)


class RecordingSynthesizer(StepProgressUpdateSynthesizer):
    def __init__(
        self,
        delegate: StepProgressUpdateSynthesizer,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__()
        self.delegate = delegate
        self.forced = forced
        self.error = error
        self.calls: list[
            tuple[
                Plan,
                PlanRun,
                StepOutcomeAssessment,
                StepProgressTransitionDecision,
            ]
        ] = []

    def synthesize(
        self,
        plan: Plan,
        run: PlanRun,
        assessment: StepOutcomeAssessment,
        decision: StepProgressTransitionDecision,
    ) -> StepProgressUpdate:
        self.calls.append((plan, run, assessment, decision))
        if self.error is not None:
            raise self.error
        if self.forced is not None:
            return cast(StepProgressUpdate, self.forced)
        return self.delegate.synthesize(plan, run, assessment, decision)


def test_public_api_defaults_and_injected_component_types() -> None:
    assert PlanStepProgressUpdatePreparer()
    assert issubclass(
        PlanStepProgressUpdatePreparationInvariantError,
        PlanStepProgressUpdatePreparationError,
    )
    with pytest.raises(TypeError, match="evidence_transition_composer"):
        PlanStepProgressUpdatePreparer(evidence_transition_composer=cast(Any, object()))
    with pytest.raises(TypeError, match="progress_update_synthesizer"):
        PlanStepProgressUpdatePreparer(progress_update_synthesizer=cast(Any, object()))


@pytest.mark.parametrize(
    ("position", "message"),
    [(0, "plan must be a Plan"), (1, "run must be a PlanRun"), (2, "step_id")],
)
def test_wrong_top_level_types_fail_explicitly(position: int, message: str) -> None:
    plan = make_plan()
    values: list[object] = [plan, make_run(plan), "step-1"]
    values[position] = object()
    with pytest.raises(TypeError, match=message):
        PlanStepProgressUpdatePreparer().prepare(*cast(Any, values))


def test_blank_unknown_and_foreign_lineage_fail_canonically() -> None:
    plan = make_plan()
    run = make_run(plan)
    with pytest.raises(PlanStepEvidenceAssessmentLineageError, match="step_id"):
        PlanStepProgressUpdatePreparer().prepare(plan, run, "")
    with pytest.raises(UnknownPlanStepError):
        PlanStepProgressUpdatePreparer().prepare(plan, run, "unknown")
    foreign = make_run(make_plan(plan_id="plan-2"))
    with pytest.raises(PlanRunIdentityError):
        PlanStepProgressUpdatePreparer().prepare(plan, foreign, "step-1")


def test_transition_calls_each_boundary_once_and_preserves_exact_artifacts() -> None:
    plan, run = prepared()
    composer = RecordingComposer(composer_for(StepOutcomeStatus.SATISFIED))
    synthesizer = RecordingSynthesizer(synthesizer_for())
    before = (plan.to_data(), run.to_data())

    result = PlanStepProgressUpdatePreparer(
        evidence_transition_composer=composer,
        progress_update_synthesizer=synthesizer,
    ).prepare(plan, run, "step-1")

    assert len(composer.calls) == len(synthesizer.calls) == 1
    assert result.assessment is synthesizer.calls[0][2]
    assert result.transition_decision is synthesizer.calls[0][3]
    assert result.progress_update is not None
    assert result.transition_decision.action is StepProgressTransitionAction.TRANSITION
    assert result.progress_update.expected_revision == run.revision
    assert result.progress_update.new_state is StepProgressState.SUCCEEDED
    assert result.progress_update.evidence_ids == result.assessment.evidence_ids
    assert result.progress_update.provenance == RunProvenance(
        "step_progress_transition", result.transition_decision.decision_id, None
    )
    assert (plan.to_data(), run.to_data()) == before


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
def test_normal_no_transition_never_invokes_wp022(
    state: StepProgressState,
    status: StepOutcomeStatus,
    with_evidence: bool,
    reason: StepProgressTransitionReason,
) -> None:
    plan, run = prepared(state=state, with_evidence=with_evidence)
    composer = RecordingComposer(composer_for(status))
    synthesizer = RecordingSynthesizer(synthesizer_for())

    result = PlanStepProgressUpdatePreparer(
        evidence_transition_composer=composer,
        progress_update_synthesizer=synthesizer,
    ).prepare(plan, run, "step-1")

    assert len(composer.calls) == 1
    assert synthesizer.calls == []
    assert result.progress_update is None
    assert result.transition_decision.reason is reason


def applicability_result(
    plan: Plan,
    run: PlanRun,
    reason: StepProgressTransitionReason,
) -> PlanStepEvidenceTransitionDecisionResult:
    base = composer_for(StepOutcomeStatus.SATISFIED).compose(plan, run, "step-1")
    decision = replace(
        base.transition_decision,
        action=StepProgressTransitionAction.NO_TRANSITION,
        target_state=None,
        reason=reason,
        provenance=StepProgressTransitionProvenance("test-decider", "1"),
    )
    return PlanStepEvidenceTransitionDecisionResult(base.assessment, decision)


@pytest.mark.parametrize(
    "reason",
    [
        StepProgressTransitionReason.INCOMPLETE_CURRENT_EVIDENCE_BASIS,
        StepProgressTransitionReason.ASSESSMENT_PREDATES_CURRENT_STEP_STATE,
    ],
)
def test_applicability_no_transition_branches_only_on_action(
    reason: StepProgressTransitionReason,
) -> None:
    plan, run = prepared()
    forced = applicability_result(plan, run, reason)
    composer = RecordingComposer(composer_for(StepOutcomeStatus.SATISFIED), forced)
    synthesizer = RecordingSynthesizer(synthesizer_for())

    result = PlanStepProgressUpdatePreparer(
        evidence_transition_composer=composer,
        progress_update_synthesizer=synthesizer,
    ).prepare(plan, run, "step-1")

    assert result.transition_decision.reason is reason
    assert result.progress_update is None
    assert synthesizer.calls == []


def unsafe_result(
    assessment: StepOutcomeAssessment,
    decision: StepProgressTransitionDecision,
) -> PlanStepEvidenceTransitionDecisionResult:
    result = object.__new__(PlanStepEvidenceTransitionDecisionResult)
    object.__setattr__(result, "assessment", assessment)
    object.__setattr__(result, "transition_decision", decision)
    return result


@pytest.mark.parametrize(
    "mismatch",
    ["plan_id", "run_id", "revision", "step_id", "assessment_id"],
)
def test_wp028_postconditions_reject_injected_lineage_contradictions(
    mismatch: str,
) -> None:
    plan, run = prepared()
    base = composer_for(StepOutcomeStatus.SATISFIED).compose(plan, run, "step-1")
    assessment = base.assessment
    decision = base.transition_decision
    if mismatch == "plan_id":
        assessment = replace(assessment, plan_id="other-plan")
        decision = replace(decision, plan_id="other-plan")
    elif mismatch == "run_id":
        assessment = replace(assessment, run_id="other-run")
        decision = replace(decision, run_id="other-run")
    elif mismatch == "revision":
        assessment = replace(assessment, run_revision=run.revision + 1)
        decision = replace(decision, observed_revision=run.revision + 1)
    elif mismatch == "step_id":
        assessment = replace(assessment, step_id="step-2")
        decision = replace(decision, step_id="step-2")
    else:
        decision = replace(decision, assessment_id="assessment-other")
    composer = RecordingComposer(
        composer_for(StepOutcomeStatus.SATISFIED),
        unsafe_result(assessment, decision),
    )
    synthesizer = RecordingSynthesizer(synthesizer_for())

    with pytest.raises(PlanStepProgressUpdatePreparationInvariantError):
        PlanStepProgressUpdatePreparer(
            evidence_transition_composer=composer,
            progress_update_synthesizer=synthesizer,
        ).prepare(plan, run, "step-1")
    assert len(composer.calls) == 1
    assert synthesizer.calls == []


def canonical_transition_artifacts() -> tuple[
    Plan, PlanRun, PlanStepEvidenceTransitionDecisionResult, StepProgressUpdate
]:
    plan, run = prepared()
    transition = composer_for(StepOutcomeStatus.SATISFIED).compose(plan, run, "step-1")
    update = synthesizer_for().synthesize(
        plan,
        run,
        transition.assessment,
        transition.transition_decision,
    )
    return plan, run, transition, update


@pytest.mark.parametrize(
    "mismatch",
    [
        "run_id",
        "revision",
        "step_id",
        "target",
        "evidence",
        "provenance",
        "actor",
    ],
)
def test_wp022_postconditions_reject_injected_update_contradictions(
    mismatch: str,
) -> None:
    plan, run, transition, update = canonical_transition_artifacts()
    if mismatch == "run_id":
        update = replace(update, run_id="other-run")
    elif mismatch == "revision":
        update = replace(update, expected_revision=run.revision + 1)
    elif mismatch == "step_id":
        update = replace(update, step_id="step-2")
    elif mismatch == "target":
        update = replace(update, new_state=StepProgressState.FAILED)
    elif mismatch == "evidence":
        update = replace(update, evidence_ids=("other-evidence",))
    elif mismatch == "provenance":
        update = replace(update, provenance=RunProvenance("other", "source"))
    else:
        update = replace(
            update,
            provenance=RunProvenance(
                "step_progress_transition",
                transition.transition_decision.decision_id,
                "actor-1",
            ),
        )
    composer = RecordingComposer(composer_for(StepOutcomeStatus.SATISFIED), transition)
    synthesizer = RecordingSynthesizer(synthesizer_for(), forced=update)

    with pytest.raises(PlanStepProgressUpdatePreparationInvariantError):
        PlanStepProgressUpdatePreparer(
            evidence_transition_composer=composer,
            progress_update_synthesizer=synthesizer,
        ).prepare(plan, run, "step-1")
    assert len(synthesizer.calls) == 1


def test_wrong_component_result_types_fail_as_wp029_invariants() -> None:
    plan, run = prepared()
    bad_composer = RecordingComposer(
        composer_for(StepOutcomeStatus.SATISFIED), object()
    )
    with pytest.raises(PlanStepProgressUpdatePreparationInvariantError, match="WP028"):
        PlanStepProgressUpdatePreparer(
            evidence_transition_composer=bad_composer
        ).prepare(plan, run, "step-1")

    transition = composer_for(StepOutcomeStatus.SATISFIED).compose(plan, run, "step-1")
    bad_synthesizer = RecordingSynthesizer(synthesizer_for(), forced=object())
    with pytest.raises(PlanStepProgressUpdatePreparationInvariantError, match="WP022"):
        PlanStepProgressUpdatePreparer(
            evidence_transition_composer=RecordingComposer(
                composer_for(StepOutcomeStatus.SATISFIED), transition
            ),
            progress_update_synthesizer=bad_synthesizer,
        ).prepare(plan, run, "step-1")


def test_wp022_failure_propagates_once_without_fallback_or_retry() -> None:
    plan, run = prepared()
    failure = RuntimeError("synthesis failed")
    synthesizer = RecordingSynthesizer(synthesizer_for(), error=failure)

    with pytest.raises(RuntimeError, match="synthesis failed") as caught:
        PlanStepProgressUpdatePreparer(
            evidence_transition_composer=RecordingComposer(
                composer_for(StepOutcomeStatus.SATISFIED)
            ),
            progress_update_synthesizer=synthesizer,
        ).prepare(plan, run, "step-1")
    assert caught.value is failure
    assert len(synthesizer.calls) == 1


def test_result_invariants_immutability_and_serialization() -> None:
    plan, run, transition, update = canonical_transition_artifacts()
    result = PlanStepProgressUpdatePreparationResult(
        transition.assessment, transition.transition_decision, update
    )
    with pytest.raises(FrozenInstanceError):
        result.progress_update = None  # type: ignore[misc]
    assert result.to_data() == {
        "assessment": transition.assessment.to_data(),
        "transition_decision": transition.transition_decision.to_data(),
        "progress_update": update.to_data(),
    }
    no_transition = composer_for(StepOutcomeStatus.NOT_SATISFIED).compose(
        plan, run, "step-1"
    )
    no_result = PlanStepProgressUpdatePreparationResult(
        no_transition.assessment, no_transition.transition_decision, None
    )
    assert no_result.to_data()["progress_update"] is None


def test_result_rejects_action_update_equivalence_violations() -> None:
    _, _, transition, update = canonical_transition_artifacts()
    with pytest.raises(
        PlanStepProgressUpdatePreparationInvariantError, match="if and only"
    ):
        PlanStepProgressUpdatePreparationResult(
            transition.assessment, transition.transition_decision, None
        )
    no_transition = replace(
        transition.transition_decision,
        action=StepProgressTransitionAction.NO_TRANSITION,
        target_state=None,
        reason=StepProgressTransitionReason.OUTCOME_NOT_SATISFIED,
    )
    with pytest.raises(
        PlanStepProgressUpdatePreparationInvariantError, match="if and only"
    ):
        PlanStepProgressUpdatePreparationResult(
            transition.assessment, no_transition, update
        )


def test_no_reducer_or_wp023_invocation_and_no_run_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, run = prepared()
    before = run.to_data()

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("mutation/advancement boundary was invoked")

    monkeypatch.setattr(PlanRunReducer, "apply", forbidden)
    monkeypatch.setattr(PlanRunProgressAdvancer, "advance", forbidden)
    result = PlanStepProgressUpdatePreparer(
        evidence_transition_composer=composer_for(StepOutcomeStatus.SATISFIED),
        progress_update_synthesizer=synthesizer_for(),
    ).prepare(plan, run, "step-1")
    assert result.progress_update is not None
    assert run.to_data() == before


def test_repeated_calls_are_allowed_without_deduplication() -> None:
    plan, run = prepared()
    update_ids = iter(("progress-update-1", "progress-update-2"))
    preparer = PlanStepProgressUpdatePreparer(
        evidence_transition_composer=composer_for(StepOutcomeStatus.SATISFIED),
        progress_update_synthesizer=synthesizer_for(lambda: next(update_ids)),
    )

    first = preparer.prepare(plan, run, "step-1")
    second = preparer.prepare(plan, run, "step-1")

    assert first.progress_update is not None
    assert second.progress_update is not None
    assert first.progress_update.update_id != second.progress_update.update_id
    assert run.revision == first.progress_update.expected_revision
    assert run.revision == second.progress_update.expected_revision


def test_actionable_update_is_structurally_consumable_by_wp023() -> None:
    plan, run = prepared()
    result = PlanStepProgressUpdatePreparer(
        evidence_transition_composer=composer_for(StepOutcomeStatus.SATISFIED),
        progress_update_synthesizer=synthesizer_for(),
    ).prepare(plan, run, "step-1")

    assert result.progress_update is not None
    advanced = PlanRunProgressAdvancer().advance(plan, run, result.progress_update)

    assert advanced.updated_run.revision == run.revision + 1
    progress = next(
        item for item in advanced.updated_run.step_progress if item.step_id == "step-1"
    )
    assert progress.state is StepProgressState.SUCCEEDED
