"""WP031 post-advancement selected-Step handling preparation composition."""

from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError, dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from iris.orchestrator import HandlingKind
from iris.outcome_assessment import (
    StepOutcomeAssessment,
    StepOutcomeEvaluator,
    StepOutcomeStatus,
)
from iris.plan_control import ControlDecision, ControlDecisionKind
from iris.plan_handling import (
    PlanStepHandlingPreparer,
    StepHandlingPreparationResult,
    StepHandlingPreparationStatus,
    StepHandlingSpecification,
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
from iris.plan_step_handling_preparation import (
    PlanStepHandlingPreparationComposer,
    PlanStepHandlingPreparationError,
    PlanStepHandlingPreparationInvariantError,
    PlanStepHandlingPreparationResult,
)
from iris.plan_step_progress_advancement import (
    PlanStepProgressAdvancementComposer,
    PlanStepProgressAdvancementResult,
)
from iris.plan_step_progress_update_preparation import (
    PlanStepProgressUpdatePreparer,
)
from iris.planning import Plan, PlanStep
from iris.step_progress_transition import (
    StepProgressTransitionDecider,
    StepProgressTransitionDecision,
)
from iris.step_progress_update_synthesis import StepProgressUpdateSynthesizer

BASE = datetime(2026, 10, 2, 20, tzinfo=UTC)
ASSESSED = BASE + timedelta(seconds=100)
DECIDED = BASE + timedelta(seconds=101)
UPDATED = BASE + timedelta(seconds=102)
PROVENANCE = RunProvenance("test", "wp031")


def step(
    step_id: str,
    *,
    depends_on: tuple[str, ...] = (),
    handling: HandlingKind | None = None,
) -> PlanStep:
    return PlanStep(
        step_id,
        f"Objective {step_id}",
        f"Expected {step_id}",
        depends_on,
        handling,
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


def wp030_for(status: StepOutcomeStatus) -> PlanStepProgressAdvancementComposer:
    assessment = PlanStepEvidenceAssessor(
        cast(StepOutcomeEvaluator, StatusEvaluator(status))
    )
    transition_composer = PlanStepEvidenceTransitionComposer(
        assessor=assessment,
        transition_decider=StepProgressTransitionDecider(
            clock=lambda: DECIDED,
            decision_id_factory=lambda: "decision-1",
        ),
    )
    preparer = PlanStepProgressUpdatePreparer(
        evidence_transition_composer=transition_composer,
        progress_update_synthesizer=StepProgressUpdateSynthesizer(
            clock=lambda: UPDATED,
            update_id_factory=lambda: "progress-update-1",
        ),
    )
    return PlanStepProgressAdvancementComposer(
        progress_update_preparer=preparer,
        progress_advancer=PlanRunProgressAdvancer(),
    )


class RecordingWP030(PlanStepProgressAdvancementComposer):
    def __init__(
        self,
        delegate: PlanStepProgressAdvancementComposer,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__()
        self.delegate = delegate
        self.forced = forced
        self.error = error
        self.calls: list[tuple[Plan, PlanRun, str]] = []

    def compose(
        self,
        plan: Plan,
        run: PlanRun,
        step_id: str,
    ) -> PlanStepProgressAdvancementResult:
        self.calls.append((plan, run, step_id))
        if self.error is not None:
            raise self.error
        if self.forced is not None:
            return cast(PlanStepProgressAdvancementResult, self.forced)
        return self.delegate.compose(plan, run, step_id)


class RecordingHandlingPreparer(PlanStepHandlingPreparer):
    def __init__(
        self,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__()
        self.forced = forced
        self.error = error
        self.calls: list[
            tuple[
                Plan,
                PlanRun,
                ControlDecision,
                StepHandlingSpecification | None,
            ]
        ] = []
        self.results: list[StepHandlingPreparationResult] = []

    def prepare(
        self,
        plan: Plan,
        run: PlanRun,
        decision: ControlDecision,
        specification: StepHandlingSpecification | None = None,
    ) -> StepHandlingPreparationResult:
        self.calls.append((plan, run, decision, specification))
        if self.error is not None:
            raise self.error
        if self.forced is not None:
            result = cast(StepHandlingPreparationResult, self.forced)
        else:
            result = super().prepare(plan, run, decision, specification)
        self.results.append(result)
        return result


def control_scenario(
    kind: ControlDecisionKind,
    *,
    selected_handling: HandlingKind | None = HandlingKind.CAPABILITY,
) -> tuple[Plan, PlanRun]:
    if kind is ControlDecisionKind.RUN_STRUCTURALLY_COMPLETE:
        plan = make_plan(step("a"))
        return plan, active_with_evidence(plan, new_run(plan))
    if kind is ControlDecisionKind.STEP_SELECTED:
        plan = make_plan(
            step("a"),
            step("b", depends_on=("a",), handling=selected_handling),
        )
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


def canonical_progress(
    *,
    handling: HandlingKind | None = HandlingKind.CAPABILITY,
) -> tuple[Plan, PlanRun, PlanStepProgressAdvancementResult]:
    plan, run = control_scenario(
        ControlDecisionKind.STEP_SELECTED,
        selected_handling=handling,
    )
    progress = wp030_for(StepOutcomeStatus.SATISFIED).compose(plan, run, "a")
    assert progress.progress_update is not None
    assert progress.advancement_result is not None
    assert (
        progress.advancement_result.control_decision.kind
        is ControlDecisionKind.STEP_SELECTED
    )
    return plan, run, progress


def test_public_api_defaults_and_constructor_dependency_types() -> None:
    assert PlanStepHandlingPreparationComposer()
    assert issubclass(
        PlanStepHandlingPreparationInvariantError,
        PlanStepHandlingPreparationError,
    )
    with pytest.raises(TypeError, match="progress_advancement_composer"):
        PlanStepHandlingPreparationComposer(
            progress_advancement_composer=cast(Any, object())
        )
    with pytest.raises(TypeError, match="handling_preparer"):
        PlanStepHandlingPreparationComposer(handling_preparer=cast(Any, object()))


@pytest.mark.parametrize(
    ("position", "message"),
    [(0, "plan must be a Plan"), (1, "run must be a PlanRun"), (2, "step_id")],
)
def test_invalid_top_level_types_fail_before_wp030(
    position: int,
    message: str,
) -> None:
    plan = make_plan(step("a"))
    values: list[object] = [plan, new_run(plan), "a"]
    values[position] = object()
    wp030 = RecordingWP030(wp030_for(StepOutcomeStatus.INDETERMINATE))

    with pytest.raises(TypeError, match=message):
        PlanStepHandlingPreparationComposer(
            progress_advancement_composer=wp030
        ).compose(*cast(Any, values))
    assert wp030.calls == []


def test_no_advancement_stops_without_wp014_and_preserves_wp030_artifacts() -> None:
    plan = make_plan(step("a"))
    run = active_with_evidence(plan, new_run(plan))
    delegate = wp030_for(StepOutcomeStatus.INDETERMINATE)
    progress = delegate.compose(plan, run, "a")
    assert progress.progress_update is None
    assert progress.advancement_result is None
    wp030 = RecordingWP030(delegate, forced=progress)
    handling = RecordingHandlingPreparer()
    before = (plan.to_data(), run.to_data())

    result = PlanStepHandlingPreparationComposer(
        progress_advancement_composer=wp030,
        handling_preparer=handling,
    ).compose(plan, run, "a")

    assert wp030.calls == [(plan, run, "a")]
    assert handling.calls == []
    assert result.assessment is progress.assessment
    assert result.transition_decision is progress.transition_decision
    assert result.progress_update is None
    assert result.advancement_result is None
    assert result.handling_preparation is None
    assert (plan.to_data(), run.to_data()) == before


@pytest.mark.parametrize("kind", list(ControlDecisionKind))
def test_all_fresh_control_kinds_have_exact_bounded_behavior(
    kind: ControlDecisionKind,
) -> None:
    plan, run = control_scenario(kind)
    progress = wp030_for(StepOutcomeStatus.SATISFIED).compose(plan, run, "a")
    assert progress.advancement_result is not None
    assert progress.advancement_result.control_decision.kind is kind
    wp030 = RecordingWP030(
        wp030_for(StepOutcomeStatus.SATISFIED),
        forced=progress,
    )
    handling = RecordingHandlingPreparer()

    result = PlanStepHandlingPreparationComposer(
        progress_advancement_composer=wp030,
        handling_preparer=handling,
    ).compose(plan, run, "a")

    assert len(wp030.calls) == 1
    assert result.assessment is progress.assessment
    assert result.transition_decision is progress.transition_decision
    assert result.progress_update is progress.progress_update
    assert result.advancement_result is progress.advancement_result
    if kind is ControlDecisionKind.STEP_SELECTED:
        assert len(handling.calls) == 1
        call = handling.calls[0]
        assert call[0] is plan
        assert call[1] is progress.advancement_result.updated_run
        assert call[2] is progress.advancement_result.control_decision
        assert call[3] is None
        assert result.handling_preparation is not None
        assert (
            result.handling_preparation.status is StepHandlingPreparationStatus.PREPARED
        )
    else:
        assert handling.calls == []
        assert result.handling_preparation is None


@pytest.mark.parametrize(
    ("handling", "status"),
    [
        (HandlingKind.CAPABILITY, StepHandlingPreparationStatus.PREPARED),
        (None, StepHandlingPreparationStatus.HANDLING_UNSPECIFIED),
        (HandlingKind.SYSTEM, StepHandlingPreparationStatus.INSUFFICIENT_DETAIL),
        (HandlingKind.MEMORY, StepHandlingPreparationStatus.INSUFFICIENT_DETAIL),
        (HandlingKind.INTELLIGENCE, StepHandlingPreparationStatus.INSUFFICIENT_DETAIL),
    ],
)
def test_wp014_outcomes_are_preserved_without_specification_or_continuation(
    handling: HandlingKind | None,
    status: StepHandlingPreparationStatus,
) -> None:
    plan, run, progress = canonical_progress(handling=handling)
    wp030 = RecordingWP030(wp030_for(StepOutcomeStatus.SATISFIED), forced=progress)
    preparer = RecordingHandlingPreparer()

    result = PlanStepHandlingPreparationComposer(
        progress_advancement_composer=wp030,
        handling_preparer=preparer,
    ).compose(plan, run, "a")

    assert len(preparer.calls) == 1
    assert preparer.calls[0][3] is None
    assert result.handling_preparation is not None
    assert result.handling_preparation.status is status
    assert result.handling_preparation is preparer.results[0]


def unsafe_progress_result(
    assessment: object,
    decision: object,
    update: object,
    advancement: object,
) -> PlanStepProgressAdvancementResult:
    result = object.__new__(PlanStepProgressAdvancementResult)
    object.__setattr__(result, "assessment", assessment)
    object.__setattr__(result, "transition_decision", decision)
    object.__setattr__(result, "progress_update", update)
    object.__setattr__(result, "advancement_result", advancement)
    return result


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


@pytest.mark.parametrize(
    "mismatch",
    [
        "type",
        "assessment_type",
        "decision_type",
        "plan",
        "run",
        "source_revision",
        "step",
        "assessment_link",
        "shape_update_only",
        "shape_advancement_only",
        "update_revision",
        "update_run",
        "update_step",
        "source_update",
        "advancement_revision",
        "successor_plan",
        "successor_run",
        "successor_goal",
        "successor_revision",
        "control_type",
        "control_plan",
        "control_run",
        "control_revision",
    ],
)
def test_malformed_wp030_outputs_fail_before_wp014(mismatch: str) -> None:
    plan, run, progress = canonical_progress()
    assessment: object = progress.assessment
    decision: object = progress.transition_decision
    update: object = progress.progress_update
    advancement: object = progress.advancement_result
    forced: object
    if mismatch == "type":
        forced = object()
    else:
        assert isinstance(assessment, StepOutcomeAssessment)
        assert isinstance(decision, StepProgressTransitionDecision)
        assert isinstance(update, StepProgressUpdate)
        assert isinstance(advancement, PlanRunProgressAdvanceResult)
        if mismatch == "assessment_type":
            assessment = object()
        elif mismatch == "decision_type":
            decision = object()
        elif mismatch == "plan":
            assessment = replace(assessment, plan_id="foreign-plan")
            decision = replace(decision, plan_id="foreign-plan")
        elif mismatch == "run":
            assessment = replace(assessment, run_id="foreign-run")
            decision = replace(decision, run_id="foreign-run")
        elif mismatch == "source_revision":
            assessment = replace(assessment, run_revision=run.revision + 1)
            decision = replace(decision, observed_revision=run.revision + 1)
        elif mismatch == "step":
            assessment = replace(assessment, step_id="b")
            decision = replace(decision, step_id="b")
        elif mismatch == "assessment_link":
            decision = replace(decision, assessment_id="foreign-assessment")
        elif mismatch == "shape_update_only":
            advancement = None
        elif mismatch == "shape_advancement_only":
            update = None
        elif mismatch == "update_revision":
            update = replace(update, expected_revision=run.revision + 1)
        elif mismatch == "update_run":
            update = replace(update, run_id="foreign-run")
        elif mismatch == "update_step":
            update = replace(update, step_id="b")
        elif mismatch == "source_update":
            advancement = unsafe_advancement(
                advancement,
                source_update_id="foreign-update",
            )
        elif mismatch == "advancement_revision":
            advancement = unsafe_advancement(
                advancement,
                source_revision=run.revision + 1,
            )
        elif mismatch.startswith("successor_"):
            updated = advancement.updated_run
            name = mismatch.removeprefix("successor_")
            value: object = {
                "plan": "foreign-plan",
                "run": "foreign-run",
                "goal": "foreign-goal",
                "revision": run.revision + 2,
            }[name]
            field_name = {"plan": "plan_id", "run": "run_id", "goal": "goal_id"}.get(
                name,
                name,
            )
            advancement = unsafe_advancement(
                advancement,
                updated_run=unsafe_run(updated, **{field_name: value}),
            )
        elif mismatch == "control_type":
            advancement = unsafe_advancement(advancement, control_decision=object())
        else:
            control = advancement.control_decision
            field_name = mismatch.removeprefix("control_")
            value = {
                "plan": "foreign-plan",
                "run": "foreign-run",
                "revision": advancement.updated_run.revision + 1,
            }[field_name]
            actual_name = {
                "plan": "plan_id",
                "run": "run_id",
                "revision": "observed_revision",
            }[field_name]
            advancement = unsafe_advancement(
                advancement,
                control_decision=replace(control, **{actual_name: value}),
            )
        forced = unsafe_progress_result(assessment, decision, update, advancement)
    wp030 = RecordingWP030(wp030_for(StepOutcomeStatus.SATISFIED), forced=forced)
    handling = RecordingHandlingPreparer()

    with pytest.raises(PlanStepHandlingPreparationInvariantError):
        PlanStepHandlingPreparationComposer(
            progress_advancement_composer=wp030,
            handling_preparer=handling,
        ).compose(plan, run, "a")
    assert len(wp030.calls) == 1
    assert handling.calls == []


@pytest.mark.parametrize(
    "mismatch",
    ["type", "plan", "run", "revision", "step", "need_identity"],
)
def test_malformed_wp014_outputs_are_rejected(mismatch: str) -> None:
    plan, run, progress = canonical_progress()
    assert progress.advancement_result is not None
    advancement = progress.advancement_result
    canonical = PlanStepHandlingPreparer().prepare(
        plan,
        advancement.updated_run,
        advancement.control_decision,
    )
    forced: object = canonical
    if mismatch == "type":
        forced = object()
    elif mismatch == "plan":
        forced = replace(canonical, plan_id="foreign-plan")
    elif mismatch == "run":
        forced = replace(canonical, run_id="foreign-run")
    elif mismatch == "revision":
        forced = replace(
            canonical,
            observed_revision=advancement.updated_run.revision + 1,
        )
    elif mismatch == "step":
        forced = replace(canonical, step_id="a")
    else:
        assert canonical.handling_need is not None
        forced = replace(
            canonical,
            handling_need=replace(
                canonical.handling_need,
                need_id="noncanonical-need",
            ),
        )
    handling = RecordingHandlingPreparer(forced=forced)

    with pytest.raises(PlanStepHandlingPreparationInvariantError):
        PlanStepHandlingPreparationComposer(
            progress_advancement_composer=RecordingWP030(
                wp030_for(StepOutcomeStatus.SATISFIED),
                forced=progress,
            ),
            handling_preparer=handling,
        ).compose(plan, run, "a")
    assert len(handling.calls) == 1


def test_wp030_failure_propagates_exactly_without_wp014() -> None:
    plan = make_plan(step("a"))
    run = new_run(plan)
    failure = RuntimeError("wp030 failed")
    wp030 = RecordingWP030(
        wp030_for(StepOutcomeStatus.INDETERMINATE),
        error=failure,
    )
    handling = RecordingHandlingPreparer()

    with pytest.raises(RuntimeError) as caught:
        PlanStepHandlingPreparationComposer(
            progress_advancement_composer=wp030,
            handling_preparer=handling,
        ).compose(plan, run, "a")
    assert caught.value is failure
    assert len(wp030.calls) == 1
    assert handling.calls == []


def test_wp014_failure_propagates_exactly_once_and_is_not_none() -> None:
    plan, run, progress = canonical_progress()
    failure = RuntimeError("wp014 failed")
    handling = RecordingHandlingPreparer(error=failure)

    with pytest.raises(RuntimeError) as caught:
        PlanStepHandlingPreparationComposer(
            progress_advancement_composer=RecordingWP030(
                wp030_for(StepOutcomeStatus.SATISFIED),
                forced=progress,
            ),
            handling_preparer=handling,
        ).compose(plan, run, "a")
    assert caught.value is failure
    assert len(handling.calls) == 1


def test_result_is_immutable_and_serializes_exact_artifacts() -> None:
    plan, run, progress = canonical_progress()
    result = PlanStepHandlingPreparationComposer(
        progress_advancement_composer=RecordingWP030(
            wp030_for(StepOutcomeStatus.SATISFIED),
            forced=progress,
        )
    ).compose(plan, run, "a")
    assert result.handling_preparation is not None

    with pytest.raises(FrozenInstanceError):
        result.handling_preparation = None  # type: ignore[misc]
    assert result.to_data() == {
        "assessment": progress.assessment.to_data(),
        "transition_decision": progress.transition_decision.to_data(),
        "progress_update": progress.progress_update.to_data(),  # type: ignore[union-attr]
        "advancement_result": progress.advancement_result.to_data(),  # type: ignore[union-attr]
        "handling_preparation": result.handling_preparation.to_data(),
    }


def test_result_rejects_invalid_optional_shapes() -> None:
    plan, run, progress = canonical_progress()
    assert progress.advancement_result is not None
    preparation = PlanStepHandlingPreparer().prepare(
        plan,
        progress.advancement_result.updated_run,
        progress.advancement_result.control_decision,
    )
    with pytest.raises(PlanStepHandlingPreparationInvariantError):
        PlanStepHandlingPreparationResult(
            progress.assessment,
            progress.transition_decision,
            progress.progress_update,
            progress.advancement_result,
            None,
        )

    no_plan = make_plan(step("a"))
    no_run = active_with_evidence(no_plan, new_run(no_plan))
    no_progress = wp030_for(StepOutcomeStatus.INDETERMINATE).compose(
        no_plan,
        no_run,
        "a",
    )
    with pytest.raises(PlanStepHandlingPreparationInvariantError):
        PlanStepHandlingPreparationResult(
            no_progress.assessment,
            no_progress.transition_decision,
            None,
            None,
            preparation,
        )


def test_repeated_invocations_are_allowed_without_hidden_deduplication() -> None:
    plan, run, progress = canonical_progress()
    wp030 = RecordingWP030(wp030_for(StepOutcomeStatus.SATISFIED), forced=progress)
    handling = RecordingHandlingPreparer()
    composer = PlanStepHandlingPreparationComposer(
        progress_advancement_composer=wp030,
        handling_preparer=handling,
    )

    first = composer.compose(plan, run, "a")
    second = composer.compose(plan, run, "a")

    assert len(wp030.calls) == len(handling.calls) == 2
    assert first.handling_preparation == second.handling_preparation
    assert first.advancement_result is second.advancement_result


def test_wp031_has_no_lower_authority_or_continuation_dependencies() -> None:
    import iris.plan_step_handling_preparation.composer as composer_module

    source = inspect.getsource(composer_module)
    for forbidden in (
        "PlanRunReducer",
        "PlanRunController",
        "PlanStepEvidenceAssessor",
        "StepProgressTransitionDecider",
        "StepProgressUpdateSynthesizer",
        "StepHandlingSpecification",
        "Orchestrator",
        "ExecutionCoordinator",
        "PlanStepExecutionBinder",
    ):
        assert forbidden not in source


def test_prepared_selected_step_remains_not_started_and_no_execution_occurs() -> None:
    plan, run, progress = canonical_progress()
    result = PlanStepHandlingPreparationComposer(
        progress_advancement_composer=RecordingWP030(
            wp030_for(StepOutcomeStatus.SATISFIED),
            forced=progress,
        )
    ).compose(plan, run, "a")

    assert result.handling_preparation is not None
    assert result.handling_preparation.status is StepHandlingPreparationStatus.PREPARED
    assert result.advancement_result is not None
    selected = result.advancement_result.control_decision.selected_step_id
    selected_progress = next(
        item
        for item in result.advancement_result.updated_run.step_progress
        if item.step_id == selected
    )
    assert selected_progress.state is StepProgressState.NOT_STARTED
