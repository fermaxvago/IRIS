"""WP030 optional PlanStep progress advancement and re-control composition."""

from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError, dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from iris.outcome_assessment import (
    StepOutcomeAssessment,
    StepOutcomeEvaluator,
    StepOutcomeStatus,
)
from iris.plan_control import (
    ControlDecisionKind,
    PlanRunController,
)
from iris.plan_run_advancement import (
    PlanRunProgressAdvancer,
    PlanRunProgressAdvanceResult,
)
from iris.plan_runs import (
    PlanObservation,
    PlanRun,
    PlanRunFactory,
    PlanRunReducer,
    RecordObservationUpdate,
    RunProvenance,
    StepProgressState,
    StepProgressUpdate,
)
from iris.plan_step_evidence_assessment import PlanStepEvidenceAssessor
from iris.plan_step_evidence_transition import PlanStepEvidenceTransitionComposer
from iris.plan_step_progress_advancement import (
    PlanStepProgressAdvancementComposer,
    PlanStepProgressAdvancementError,
    PlanStepProgressAdvancementInvariantError,
    PlanStepProgressAdvancementResult,
)
from iris.plan_step_progress_update_preparation import (
    PlanStepProgressUpdatePreparationResult,
    PlanStepProgressUpdatePreparer,
)
from iris.planning import Plan, PlanStep
from iris.step_progress_transition import (
    StepProgressTransitionDecider,
    StepProgressTransitionDecision,
)
from iris.step_progress_update_synthesis import StepProgressUpdateSynthesizer

BASE = datetime(2026, 10, 2, 16, tzinfo=UTC)
ASSESSED = BASE + timedelta(seconds=100)
DECIDED = BASE + timedelta(seconds=101)
UPDATED = BASE + timedelta(seconds=102)
PROVENANCE = RunProvenance("test", "wp030")


def step(step_id: str, *, depends_on: tuple[str, ...] = ()) -> PlanStep:
    return PlanStep(
        step_id,
        f"Objective {step_id}",
        f"Expected {step_id}",
        depends_on,
    )


def make_plan(*steps: PlanStep, plan_id: str = "plan-1") -> Plan:
    return Plan(plan_id, "goal-1", (), steps)


def new_run(plan: Plan, *, run_id: str = "run-1") -> PlanRun:
    return PlanRunFactory(clock=lambda: BASE, run_id_factory=lambda: run_id).create(
        plan
    )


def next_time(run: PlanRun) -> datetime:
    return run.updated_at + timedelta(seconds=1)


def record(
    plan: Plan,
    run: PlanRun,
    step_id: str,
    observation_id: str,
) -> PlanRun:
    observed_at = next_time(run)
    observation = PlanObservation(
        observation_id=observation_id,
        run_id=run.run_id,
        step_id=step_id,
        source="test",
        source_reference=f"source-{observation_id}",
        observed_at=observed_at,
        kind="verification",
        data={"verified": True},
    )
    return PlanRunReducer().apply(
        plan,
        run,
        RecordObservationUpdate(
            update_id=f"record-{observation_id}",
            run_id=run.run_id,
            expected_revision=run.revision,
            updated_at=observed_at,
            provenance=PROVENANCE,
            observation=observation,
        ),
    )


def transition(
    plan: Plan,
    run: PlanRun,
    step_id: str,
    state: StepProgressState,
    evidence_ids: tuple[str, ...] = (),
) -> PlanRun:
    return PlanRunReducer().apply(
        plan,
        run,
        StepProgressUpdate(
            update_id=f"fixture-{run.revision}-{step_id}-{state.value}",
            run_id=run.run_id,
            expected_revision=run.revision,
            updated_at=next_time(run),
            provenance=PROVENANCE,
            step_id=step_id,
            new_state=state,
            evidence_ids=evidence_ids,
        ),
    )


def active_with_evidence(plan: Plan, run: PlanRun, step_id: str = "a") -> PlanRun:
    run = transition(plan, run, step_id, StepProgressState.ACTIVE)
    return record(plan, run, step_id, f"evidence-{step_id}")


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
        canonical_step: PlanStep,
        evidence: tuple[PlanObservation, ...],
    ) -> StepOutcomeAssessment:
        self.calls.append((plan, run, canonical_step, evidence))
        return StepOutcomeAssessment(
            assessment_id="assessment-1",
            plan_id=plan.plan_id,
            run_id=run.run_id,
            run_revision=run.revision,
            step_id=canonical_step.step_id,
            status=self.status,
            evidence_ids=tuple(item.observation_id for item in evidence),
            evaluator_reference="test.status.v1",
            assessed_at=ASSESSED,
            details={"status": self.status.value},
        )


def preparer_for(status: StepOutcomeStatus) -> PlanStepProgressUpdatePreparer:
    transition_composer = PlanStepEvidenceTransitionComposer(
        assessor=PlanStepEvidenceAssessor(
            cast(StepOutcomeEvaluator, StatusEvaluator(status))
        ),
        transition_decider=StepProgressTransitionDecider(
            clock=lambda: DECIDED,
            decision_id_factory=lambda: "decision-1",
        ),
    )
    return PlanStepProgressUpdatePreparer(
        evidence_transition_composer=transition_composer,
        progress_update_synthesizer=StepProgressUpdateSynthesizer(
            clock=lambda: UPDATED,
            update_id_factory=lambda: "progress-update-1",
        ),
    )


class RecordingPreparer(PlanStepProgressUpdatePreparer):
    def __init__(
        self,
        delegate: PlanStepProgressUpdatePreparer,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__()
        self.delegate = delegate
        self.forced = forced
        self.error = error
        self.calls: list[tuple[Plan, PlanRun, str]] = []

    def prepare(
        self, plan: Plan, run: PlanRun, step_id: str
    ) -> PlanStepProgressUpdatePreparationResult:
        self.calls.append((plan, run, step_id))
        if self.error is not None:
            raise self.error
        if self.forced is not None:
            return cast(PlanStepProgressUpdatePreparationResult, self.forced)
        return self.delegate.prepare(plan, run, step_id)


class RecordingAdvancer(PlanRunProgressAdvancer):
    def __init__(
        self,
        delegate: PlanRunProgressAdvancer,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__()
        self.delegate = delegate
        self.forced = forced
        self.error = error
        self.calls: list[tuple[Plan, PlanRun, StepProgressUpdate]] = []

    def advance(
        self,
        plan: Plan,
        run: PlanRun,
        update: StepProgressUpdate,
    ) -> PlanRunProgressAdvanceResult:
        self.calls.append((plan, run, update))
        if self.error is not None:
            raise self.error
        if self.forced is not None:
            return cast(PlanRunProgressAdvanceResult, self.forced)
        return self.delegate.advance(plan, run, update)


def canonical_started(
    *steps: PlanStep,
) -> tuple[Plan, PlanRun, PlanStepProgressUpdatePreparationResult]:
    plan = make_plan(*(steps or (step("a"), step("b", depends_on=("a",)))))
    run = active_with_evidence(plan, new_run(plan))
    preparation = preparer_for(StepOutcomeStatus.SATISFIED).prepare(plan, run, "a")
    assert preparation.progress_update is not None
    return plan, run, preparation


def test_public_api_defaults_and_constructor_dependency_types() -> None:
    assert PlanStepProgressAdvancementComposer()
    assert issubclass(
        PlanStepProgressAdvancementInvariantError,
        PlanStepProgressAdvancementError,
    )
    with pytest.raises(TypeError, match="progress_update_preparer"):
        PlanStepProgressAdvancementComposer(
            progress_update_preparer=cast(Any, object())
        )
    with pytest.raises(TypeError, match="progress_advancer"):
        PlanStepProgressAdvancementComposer(progress_advancer=cast(Any, object()))


@pytest.mark.parametrize(
    ("position", "message"),
    [(0, "plan must be a Plan"), (1, "run must be a PlanRun"), (2, "step_id")],
)
def test_invalid_top_level_types_fail_before_wp029(
    position: int,
    message: str,
) -> None:
    plan = make_plan(step("a"))
    values: list[object] = [plan, new_run(plan), "a"]
    values[position] = object()
    preparer = RecordingPreparer(preparer_for(StepOutcomeStatus.SATISFIED))

    with pytest.raises(TypeError, match=message):
        PlanStepProgressAdvancementComposer(progress_update_preparer=preparer).compose(
            *cast(Any, values)
        )
    assert preparer.calls == []


def test_update_path_preserves_exact_artifacts_and_advances_exactly_once() -> None:
    plan, run, preparation = canonical_started()
    preparer = RecordingPreparer(
        preparer_for(StepOutcomeStatus.SATISFIED), forced=preparation
    )
    advancer = RecordingAdvancer(PlanRunProgressAdvancer())
    before = (plan.to_data(), run.to_data())

    result = PlanStepProgressAdvancementComposer(
        progress_update_preparer=preparer,
        progress_advancer=advancer,
    ).compose(plan, run, "a")

    assert len(preparer.calls) == len(advancer.calls) == 1
    assert advancer.calls[0][2] is preparation.progress_update
    assert result.assessment is preparation.assessment
    assert result.transition_decision is preparation.transition_decision
    assert result.progress_update is preparation.progress_update
    assert result.advancement_result is not None
    assert (
        result.advancement_result.source_update_id == result.progress_update.update_id
    )
    assert result.advancement_result.source_revision == run.revision
    assert result.advancement_result.updated_run.revision == run.revision + 1
    assert (plan.to_data(), run.to_data()) == before


def test_no_update_stops_without_wp023_and_preserves_wp029_artifacts() -> None:
    plan = make_plan(step("a"))
    run = active_with_evidence(plan, new_run(plan))
    preparation = preparer_for(StepOutcomeStatus.INDETERMINATE).prepare(plan, run, "a")
    assert preparation.progress_update is None
    preparer = RecordingPreparer(
        preparer_for(StepOutcomeStatus.INDETERMINATE), forced=preparation
    )
    advancer = RecordingAdvancer(PlanRunProgressAdvancer())

    result = PlanStepProgressAdvancementComposer(
        progress_update_preparer=preparer,
        progress_advancer=advancer,
    ).compose(plan, run, "a")

    assert len(preparer.calls) == 1
    assert advancer.calls == []
    assert result.assessment is preparation.assessment
    assert result.transition_decision is preparation.transition_decision
    assert result.progress_update is None
    assert result.advancement_result is None


def control_scenario(kind: ControlDecisionKind) -> tuple[Plan, PlanRun]:
    if kind is ControlDecisionKind.RUN_STRUCTURALLY_COMPLETE:
        plan = make_plan(step("a"))
        return plan, active_with_evidence(plan, new_run(plan))
    if kind is ControlDecisionKind.STEP_SELECTED:
        plan = make_plan(step("a"), step("b", depends_on=("a",)))
        return plan, active_with_evidence(plan, new_run(plan))
    if kind is ControlDecisionKind.SELECTION_UNRESOLVED:
        plan = make_plan(
            step("a"),
            step("b", depends_on=("a",)),
            step("c", depends_on=("a",)),
        )
        return plan, active_with_evidence(plan, new_run(plan))
    if kind is ControlDecisionKind.ACTIVE_WORK_PENDING:
        plan = make_plan(step("a"), step("b"), step("c"))
        run = transition(plan, new_run(plan), "b", StepProgressState.ACTIVE)
        return plan, active_with_evidence(plan, run)

    plan = make_plan(
        step("a"),
        step("c"),
        step("b", depends_on=("a", "c")),
    )
    run = record(plan, new_run(plan), "c", "evidence-c")
    run = transition(
        plan,
        run,
        "c",
        StepProgressState.FAILED,
        ("evidence-c",),
    )
    return plan, active_with_evidence(plan, run)


@pytest.mark.parametrize("kind", list(ControlDecisionKind))
def test_all_control_decision_kinds_are_returned_inertly(
    kind: ControlDecisionKind,
) -> None:
    plan, run = control_scenario(kind)
    before = run.to_data()

    result = PlanStepProgressAdvancementComposer(
        progress_update_preparer=preparer_for(StepOutcomeStatus.SATISFIED),
        progress_advancer=PlanRunProgressAdvancer(),
    ).compose(plan, run, "a")

    assert result.advancement_result is not None
    assert result.advancement_result.control_decision.kind is kind
    assert run.to_data() == before


def test_step_selected_is_inert_and_does_not_activate_or_execute_step_b() -> None:
    plan, run = control_scenario(ControlDecisionKind.STEP_SELECTED)
    result = PlanStepProgressAdvancementComposer(
        progress_update_preparer=preparer_for(StepOutcomeStatus.SATISFIED)
    ).compose(plan, run, "a")

    assert result.advancement_result is not None
    decision = result.advancement_result.control_decision
    assert decision.kind is ControlDecisionKind.STEP_SELECTED
    assert decision.selected_step_id == "b"
    progress = {
        item.step_id: item.state
        for item in result.advancement_result.updated_run.step_progress
    }
    assert progress == {
        "a": StepProgressState.SUCCEEDED,
        "b": StepProgressState.NOT_STARTED,
    }


def test_successor_exact_update_and_unrelated_state_postconditions() -> None:
    plan, run, preparation = canonical_started(step("a"), step("b", depends_on=("a",)))
    result = PlanStepProgressAdvancementComposer(
        progress_update_preparer=RecordingPreparer(
            preparer_for(StepOutcomeStatus.SATISFIED), forced=preparation
        )
    ).compose(plan, run, "a")
    assert result.progress_update is not None
    assert result.advancement_result is not None
    updated = result.advancement_result.updated_run
    target = next(item for item in updated.step_progress if item.step_id == "a")
    source_other = next(item for item in run.step_progress if item.step_id == "b")
    updated_other = next(item for item in updated.step_progress if item.step_id == "b")

    assert updated.plan_id == plan.plan_id
    assert updated.run_id == run.run_id
    assert updated.goal_id == run.goal_id
    assert updated.created_at == run.created_at
    assert updated.updated_at == result.progress_update.updated_at
    assert target.state is result.progress_update.new_state
    assert target.changed_at == result.progress_update.updated_at
    assert target.evidence_ids == result.progress_update.evidence_ids
    assert updated.observations == run.observations
    assert updated.blockers == run.blockers
    assert updated_other == source_other
    control = result.advancement_result.control_decision
    assert control.plan_id == plan.plan_id
    assert control.run_id == run.run_id
    assert control.observed_revision == updated.revision


def unsafe_preparation(
    assessment: object,
    decision: object,
    update: object,
) -> PlanStepProgressUpdatePreparationResult:
    result = object.__new__(PlanStepProgressUpdatePreparationResult)
    object.__setattr__(result, "assessment", assessment)
    object.__setattr__(result, "transition_decision", decision)
    object.__setattr__(result, "progress_update", update)
    return result


@pytest.mark.parametrize(
    "mismatch",
    ["type", "plan", "run", "revision", "step", "assessment", "update"],
)
def test_malformed_wp029_outputs_fail_before_wp023(mismatch: str) -> None:
    plan, run, preparation = canonical_started()
    assessment: object = preparation.assessment
    decision: object = preparation.transition_decision
    update: object = preparation.progress_update
    forced: object
    if mismatch == "type":
        forced = object()
    else:
        assert isinstance(assessment, StepOutcomeAssessment)
        assert isinstance(decision, StepProgressTransitionDecision)
        assert isinstance(update, StepProgressUpdate)
        if mismatch == "plan":
            assessment = replace(assessment, plan_id="foreign-plan")
            decision = replace(decision, plan_id="foreign-plan")
        elif mismatch == "run":
            assessment = replace(assessment, run_id="foreign-run")
            decision = replace(decision, run_id="foreign-run")
        elif mismatch == "revision":
            assessment = replace(assessment, run_revision=run.revision + 1)
            decision = replace(decision, observed_revision=run.revision + 1)
        elif mismatch == "step":
            assessment = replace(assessment, step_id="b")
            decision = replace(decision, step_id="b")
        elif mismatch == "assessment":
            decision = replace(decision, assessment_id="foreign-assessment")
        else:
            update = replace(update, expected_revision=run.revision + 1)
        forced = unsafe_preparation(assessment, decision, update)
    preparer = RecordingPreparer(
        preparer_for(StepOutcomeStatus.SATISFIED), forced=forced
    )
    advancer = RecordingAdvancer(PlanRunProgressAdvancer())

    with pytest.raises(PlanStepProgressAdvancementInvariantError):
        PlanStepProgressAdvancementComposer(
            progress_update_preparer=preparer,
            progress_advancer=advancer,
        ).compose(plan, run, "a")
    assert len(preparer.calls) == 1
    assert advancer.calls == []


def unsafe_run(run: PlanRun, **changes: object) -> PlanRun:
    result = object.__new__(PlanRun)
    for name in (
        "run_id",
        "plan_id",
        "goal_id",
        "revision",
        "created_at",
        "updated_at",
        "step_progress",
        "observations",
        "blockers",
    ):
        object.__setattr__(result, name, changes.get(name, getattr(run, name)))
    return result


def unsafe_advancement(
    advancement: PlanRunProgressAdvanceResult,
    **changes: object,
) -> PlanRunProgressAdvanceResult:
    result = object.__new__(PlanRunProgressAdvanceResult)
    for name in (
        "source_update_id",
        "source_revision",
        "updated_run",
        "control_decision",
    ):
        object.__setattr__(
            result,
            name,
            changes.get(name, getattr(advancement, name)),
        )
    return result


def canonical_advancement() -> tuple[
    Plan,
    PlanRun,
    PlanStepProgressUpdatePreparationResult,
    PlanRunProgressAdvanceResult,
]:
    plan, run, preparation = canonical_started()
    assert preparation.progress_update is not None
    advancement = PlanRunProgressAdvancer().advance(
        plan, run, preparation.progress_update
    )
    return plan, run, preparation, advancement


@pytest.mark.parametrize(
    "mismatch",
    [
        "type",
        "source_update",
        "source_revision",
        "plan",
        "run",
        "goal",
        "revision",
        "created_at",
        "updated_at",
        "control_plan",
        "control_run",
        "control_revision",
        "control_type",
        "observations",
        "blockers",
        "target",
        "non_target",
    ],
)
def test_malformed_wp023_outputs_are_rejected(mismatch: str) -> None:
    plan, run, preparation, advancement = canonical_advancement()
    forced: object = advancement
    updated = advancement.updated_run
    if mismatch == "type":
        forced = object()
    elif mismatch == "source_update":
        forced = unsafe_advancement(advancement, source_update_id="foreign-update")
    elif mismatch == "source_revision":
        forced = unsafe_advancement(advancement, source_revision=run.revision + 1)
    elif mismatch in {
        "plan",
        "run",
        "goal",
        "revision",
        "created_at",
        "updated_at",
    }:
        value: object
        if mismatch == "plan":
            value = "foreign-plan"
            changed = unsafe_run(updated, plan_id=value)
        elif mismatch == "run":
            value = "foreign-run"
            changed = unsafe_run(updated, run_id=value)
        elif mismatch == "goal":
            value = "foreign-goal"
            changed = unsafe_run(updated, goal_id=value)
        elif mismatch == "revision":
            value = updated.revision + 1
            changed = unsafe_run(updated, revision=value)
        elif mismatch == "created_at":
            value = updated.created_at + timedelta(seconds=1)
            changed = unsafe_run(updated, created_at=value)
        else:
            value = updated.updated_at + timedelta(seconds=1)
            changed = unsafe_run(updated, updated_at=value)
        forced = unsafe_advancement(advancement, updated_run=changed)
    elif mismatch == "control_type":
        forced = unsafe_advancement(advancement, control_decision=object())
    elif mismatch.startswith("control_"):
        field_name = mismatch.removeprefix("control_")
        if field_name == "plan":
            control = replace(advancement.control_decision, plan_id="foreign-plan")
        elif field_name == "run":
            control = replace(advancement.control_decision, run_id="foreign-run")
        else:
            control = replace(
                advancement.control_decision,
                observed_revision=updated.revision + 1,
            )
        forced = unsafe_advancement(advancement, control_decision=control)
    elif mismatch == "observations":
        changed = unsafe_run(updated, observations=())
        forced = unsafe_advancement(advancement, updated_run=changed)
    elif mismatch == "blockers":
        changed = unsafe_run(updated, blockers=(object(),))
        forced = unsafe_advancement(advancement, updated_run=changed)
    elif mismatch == "target":
        target_progress = tuple(
            replace(item, state=StepProgressState.FAILED)
            if item.step_id == "a"
            else item
            for item in updated.step_progress
        )
        changed = unsafe_run(updated, step_progress=target_progress)
        forced = unsafe_advancement(advancement, updated_run=changed)
    else:
        other_progress = tuple(
            replace(
                item,
                state=StepProgressState.ACTIVE,
                changed_at=updated.updated_at,
            )
            if item.step_id == "b"
            else item
            for item in updated.step_progress
        )
        changed = unsafe_run(updated, step_progress=other_progress)
        forced = unsafe_advancement(advancement, updated_run=changed)

    advancer = RecordingAdvancer(PlanRunProgressAdvancer(), forced=forced)
    with pytest.raises(PlanStepProgressAdvancementInvariantError):
        PlanStepProgressAdvancementComposer(
            progress_update_preparer=RecordingPreparer(
                preparer_for(StepOutcomeStatus.SATISFIED), forced=preparation
            ),
            progress_advancer=advancer,
        ).compose(plan, run, "a")
    assert len(advancer.calls) == 1


def test_exact_wp023_result_object_is_preserved() -> None:
    plan, run, preparation, advancement = canonical_advancement()

    result = PlanStepProgressAdvancementComposer(
        progress_update_preparer=RecordingPreparer(
            preparer_for(StepOutcomeStatus.SATISFIED), forced=preparation
        ),
        progress_advancer=RecordingAdvancer(
            PlanRunProgressAdvancer(), forced=advancement
        ),
    ).compose(plan, run, "a")

    assert result.advancement_result is advancement


def test_wp029_failure_propagates_without_wp023() -> None:
    plan = make_plan(step("a"))
    run = new_run(plan)
    failure = RuntimeError("preparation failed")
    preparer = RecordingPreparer(
        preparer_for(StepOutcomeStatus.SATISFIED), error=failure
    )
    advancer = RecordingAdvancer(PlanRunProgressAdvancer())

    with pytest.raises(RuntimeError, match="preparation failed") as caught:
        PlanStepProgressAdvancementComposer(
            progress_update_preparer=preparer,
            progress_advancer=advancer,
        ).compose(plan, run, "a")
    assert caught.value is failure
    assert len(preparer.calls) == 1
    assert advancer.calls == []


def test_wp023_failure_propagates_once_without_none_fallback() -> None:
    plan, run, preparation = canonical_started()
    failure = RuntimeError("advancement failed")
    advancer = RecordingAdvancer(PlanRunProgressAdvancer(), error=failure)

    with pytest.raises(RuntimeError, match="advancement failed") as caught:
        PlanStepProgressAdvancementComposer(
            progress_update_preparer=RecordingPreparer(
                preparer_for(StepOutcomeStatus.SATISFIED), forced=preparation
            ),
            progress_advancer=advancer,
        ).compose(plan, run, "a")
    assert caught.value is failure
    assert len(advancer.calls) == 1
    assert run.revision == preparation.progress_update.expected_revision  # type: ignore[union-attr]


def test_result_immutability_serialization_and_optional_equivalence() -> None:
    plan, run, preparation, advancement = canonical_advancement()
    assert preparation.progress_update is not None
    result = PlanStepProgressAdvancementResult(
        preparation.assessment,
        preparation.transition_decision,
        preparation.progress_update,
        advancement,
    )
    with pytest.raises(FrozenInstanceError):
        result.advancement_result = None  # type: ignore[misc]
    assert result.to_data() == {
        "assessment": preparation.assessment.to_data(),
        "transition_decision": preparation.transition_decision.to_data(),
        "progress_update": preparation.progress_update.to_data(),
        "advancement_result": advancement.to_data(),
    }
    with pytest.raises(PlanStepProgressAdvancementInvariantError, match="both"):
        PlanStepProgressAdvancementResult(
            preparation.assessment,
            preparation.transition_decision,
            preparation.progress_update,
            None,
        )
    no_update = preparer_for(StepOutcomeStatus.INDETERMINATE).prepare(plan, run, "a")
    no_result = PlanStepProgressAdvancementResult(
        no_update.assessment,
        no_update.transition_decision,
        None,
        None,
    )
    assert no_result.to_data()["progress_update"] is None
    assert no_result.to_data()["advancement_result"] is None


def test_repeated_invocations_are_allowed_without_hidden_deduplication() -> None:
    plan, run = control_scenario(ControlDecisionKind.STEP_SELECTED)
    composer = PlanStepProgressAdvancementComposer(
        progress_update_preparer=preparer_for(StepOutcomeStatus.SATISFIED)
    )

    first = composer.compose(plan, run, "a")
    second = composer.compose(plan, run, "a")

    assert first.advancement_result is not None
    assert second.advancement_result is not None
    assert first.advancement_result.updated_run == second.advancement_result.updated_run
    assert run.step_progress[0].state is StepProgressState.ACTIVE


def test_wp030_has_no_direct_reducer_controller_or_lower_seam_dependency() -> None:
    import iris.plan_step_progress_advancement.composer as composer_module

    source = inspect.getsource(composer_module)
    assert "PlanRunReducer" not in source
    assert "PlanRunController" not in source
    assert "plan_step_evidence_transition" not in source
    assert "step_progress_update_synthesis" not in source
    assert "execution" not in source


def test_no_direct_reducer_or_controller_call_with_controlled_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, run, preparation, advancement = canonical_advancement()

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("WP030 invoked a lower authority directly")

    monkeypatch.setattr(PlanRunReducer, "apply", forbidden)
    monkeypatch.setattr(PlanRunController, "decide", forbidden)
    result = PlanStepProgressAdvancementComposer(
        progress_update_preparer=RecordingPreparer(
            preparer_for(StepOutcomeStatus.SATISFIED), forced=preparation
        ),
        progress_advancer=RecordingAdvancer(
            PlanRunProgressAdvancer(), forced=advancement
        ),
    ).compose(plan, run, "a")
    assert result.advancement_result is advancement
