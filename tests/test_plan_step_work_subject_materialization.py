"""WP032 post-advancement selected-Step WorkSubject materialization."""

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
from iris.plan_control import ControlDecisionKind
from iris.plan_handling import (
    PlanStepHandlingPreparer,
    StepHandlingPreparationResult,
    StepHandlingPreparationStatus,
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
    PlanStepHandlingPreparationResult,
)
from iris.plan_step_progress_advancement import PlanStepProgressAdvancementComposer
from iris.plan_step_progress_update_preparation import (
    PlanStepProgressUpdatePreparer,
)
from iris.plan_step_work_subject_materialization import (
    PlanStepWorkSubjectMaterializationError,
    PlanStepWorkSubjectMaterializationInvariantError,
    PlanStepWorkSubjectMaterializationResult,
    PlanStepWorkSubjectMaterializer,
)
from iris.planning import Plan, PlanStep
from iris.step_progress_transition import (
    StepProgressTransitionDecider,
    StepProgressTransitionDecision,
)
from iris.step_progress_update_synthesis import StepProgressUpdateSynthesizer
from iris.work_identity import (
    PlanStepWorkReference,
    RequestWorkReference,
    WorkOrigin,
    WorkSubject,
    WorkSubjectKind,
    work_subject_from_plan_step,
)

BASE = datetime(2026, 10, 2, 22, tzinfo=UTC)
ASSESSED = BASE + timedelta(seconds=100)
DECIDED = BASE + timedelta(seconds=101)
UPDATED = BASE + timedelta(seconds=102)
PROVENANCE = RunProvenance("test", "wp032")


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


def wp031_for(status: StepOutcomeStatus) -> PlanStepHandlingPreparationComposer:
    assessor = PlanStepEvidenceAssessor(
        cast(StepOutcomeEvaluator, StatusEvaluator(status))
    )
    transition_composer = PlanStepEvidenceTransitionComposer(
        assessor=assessor,
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
    advancement = PlanStepProgressAdvancementComposer(
        progress_update_preparer=preparer,
        progress_advancer=PlanRunProgressAdvancer(),
    )
    return PlanStepHandlingPreparationComposer(
        progress_advancement_composer=advancement,
        handling_preparer=PlanStepHandlingPreparer(),
    )


class RecordingWP031(PlanStepHandlingPreparationComposer):
    def __init__(
        self,
        delegate: PlanStepHandlingPreparationComposer,
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
    ) -> PlanStepHandlingPreparationResult:
        self.calls.append((plan, run, step_id))
        if self.error is not None:
            raise self.error
        if self.forced is not None:
            return cast(PlanStepHandlingPreparationResult, self.forced)
        return self.delegate.compose(plan, run, step_id)


class RecordingAdapter:
    def __init__(
        self,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        self.forced = forced
        self.error = error
        self.calls: list[tuple[Plan, PlanRun, str]] = []
        self.results: list[WorkSubject] = []

    def __call__(self, plan: Plan, run: PlanRun, step_id: str) -> WorkSubject:
        self.calls.append((plan, run, step_id))
        if self.error is not None:
            raise self.error
        if self.forced is not None:
            result = cast(WorkSubject, self.forced)
        else:
            result = work_subject_from_plan_step(plan, run, step_id)
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
    run = transition(plan, run, "c", StepProgressState.FAILED, ("evidence-c",))
    return plan, active_with_evidence(plan, run)


def canonical_wp031(
    *,
    handling: HandlingKind | None = HandlingKind.CAPABILITY,
) -> tuple[Plan, PlanRun, PlanStepHandlingPreparationResult]:
    plan, run = control_scenario(
        ControlDecisionKind.STEP_SELECTED,
        selected_handling=handling,
    )
    result = wp031_for(StepOutcomeStatus.SATISFIED).compose(plan, run, "a")
    assert result.progress_update is not None
    assert result.advancement_result is not None
    assert result.handling_preparation is not None
    assert (
        result.advancement_result.control_decision.kind
        is ControlDecisionKind.STEP_SELECTED
    )
    return plan, run, result


def unsafe_wp031_result(
    assessment: object,
    decision: object,
    update: object,
    advancement: object,
    preparation: object,
) -> PlanStepHandlingPreparationResult:
    result = object.__new__(PlanStepHandlingPreparationResult)
    object.__setattr__(result, "assessment", assessment)
    object.__setattr__(result, "transition_decision", decision)
    object.__setattr__(result, "progress_update", update)
    object.__setattr__(result, "advancement_result", advancement)
    object.__setattr__(result, "handling_preparation", preparation)
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


def unsafe_subject(
    subject: WorkSubject,
    **changes: object,
) -> WorkSubject:
    result = object.__new__(WorkSubject)
    for name in ("kind", "reference", "origin", "subject_id"):
        object.__setattr__(result, name, changes.get(name, getattr(subject, name)))
    return result


def test_public_api_defaults_and_constructor_dependency_types() -> None:
    assert PlanStepWorkSubjectMaterializer()
    assert issubclass(
        PlanStepWorkSubjectMaterializationInvariantError,
        PlanStepWorkSubjectMaterializationError,
    )
    with pytest.raises(TypeError, match="handling_preparation_composer"):
        PlanStepWorkSubjectMaterializer(
            handling_preparation_composer=cast(Any, object())
        )
    with pytest.raises(TypeError, match="work_subject_adapter"):
        PlanStepWorkSubjectMaterializer(work_subject_adapter=cast(Any, object()))


@pytest.mark.parametrize(
    ("position", "message"),
    [(0, "plan must be a Plan"), (1, "run must be a PlanRun"), (2, "step_id")],
)
def test_invalid_top_level_types_fail_before_wp031(
    position: int,
    message: str,
) -> None:
    plan = make_plan(step("a"))
    values: list[object] = [plan, new_run(plan), "a"]
    values[position] = object()
    wp031 = RecordingWP031(wp031_for(StepOutcomeStatus.INDETERMINATE))

    with pytest.raises(TypeError, match=message):
        PlanStepWorkSubjectMaterializer(
            handling_preparation_composer=wp031
        ).materialize(*cast(Any, values))
    assert wp031.calls == []


def test_no_advancement_stops_without_wp015_and_preserves_artifacts() -> None:
    plan = make_plan(step("a"))
    run = active_with_evidence(plan, new_run(plan))
    delegated = wp031_for(StepOutcomeStatus.INDETERMINATE).compose(plan, run, "a")
    assert delegated.advancement_result is None
    wp031 = RecordingWP031(wp031_for(StepOutcomeStatus.INDETERMINATE), forced=delegated)
    adapter = RecordingAdapter()
    before = (plan.to_data(), run.to_data())

    result = PlanStepWorkSubjectMaterializer(
        handling_preparation_composer=wp031,
        work_subject_adapter=adapter,
    ).materialize(plan, run, "a")

    assert wp031.calls == [(plan, run, "a")]
    assert adapter.calls == []
    assert result.assessment is delegated.assessment
    assert result.transition_decision is delegated.transition_decision
    assert result.progress_update is delegated.progress_update
    assert result.advancement_result is delegated.advancement_result
    assert result.handling_preparation is delegated.handling_preparation
    assert result.work_subject is None
    assert (plan.to_data(), run.to_data()) == before


@pytest.mark.parametrize("kind", list(ControlDecisionKind))
def test_all_fresh_control_kinds_have_exact_bounded_behavior(
    kind: ControlDecisionKind,
) -> None:
    plan, run = control_scenario(kind)
    delegated = wp031_for(StepOutcomeStatus.SATISFIED).compose(plan, run, "a")
    assert delegated.advancement_result is not None
    assert delegated.advancement_result.control_decision.kind is kind
    wp031 = RecordingWP031(wp031_for(StepOutcomeStatus.SATISFIED), forced=delegated)
    adapter = RecordingAdapter()

    result = PlanStepWorkSubjectMaterializer(
        handling_preparation_composer=wp031,
        work_subject_adapter=adapter,
    ).materialize(plan, run, "a")

    assert len(wp031.calls) == 1
    if kind is ControlDecisionKind.STEP_SELECTED:
        assert len(adapter.calls) == 1
        assert result.work_subject is adapter.results[0]
    else:
        assert adapter.calls == []
        assert result.work_subject is None


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
def test_all_handling_statuses_materialize_identity(
    handling: HandlingKind | None,
    status: StepHandlingPreparationStatus,
) -> None:
    plan, run, delegated = canonical_wp031(handling=handling)
    assert delegated.handling_preparation is not None
    assert delegated.handling_preparation.status is status
    adapter = RecordingAdapter()

    result = PlanStepWorkSubjectMaterializer(
        handling_preparation_composer=RecordingWP031(
            wp031_for(StepOutcomeStatus.SATISFIED), forced=delegated
        ),
        work_subject_adapter=adapter,
    ).materialize(plan, run, "a")

    assert len(adapter.calls) == 1
    assert result.handling_preparation is delegated.handling_preparation
    assert result.work_subject is adapter.results[0]


def test_processed_step_a_materializes_fresh_selected_step_b_on_successor() -> None:
    plan, source, delegated = canonical_wp031()
    assert delegated.advancement_result is not None
    advancement = delegated.advancement_result
    assert delegated.assessment.step_id == "a"
    assert advancement.control_decision.selected_step_id == "b"
    adapter = RecordingAdapter()

    result = PlanStepWorkSubjectMaterializer(
        handling_preparation_composer=RecordingWP031(
            wp031_for(StepOutcomeStatus.SATISFIED), forced=delegated
        ),
        work_subject_adapter=adapter,
    ).materialize(plan, source, "a")

    assert adapter.calls == [(plan, advancement.updated_run, "b")]
    assert adapter.calls[0][1] is advancement.updated_run
    assert adapter.calls[0][1] is not source
    assert result.work_subject is adapter.results[0]
    assert result.work_subject.reference == PlanStepWorkReference(
        plan.plan_id, source.run_id, "b"
    )
    assert result.work_subject.origin is None


def test_subject_identity_excludes_revision_and_remains_stable() -> None:
    plan, source, delegated = canonical_wp031()
    assert delegated.advancement_result is not None
    successor = delegated.advancement_result.updated_run
    result = PlanStepWorkSubjectMaterializer(
        handling_preparation_composer=RecordingWP031(
            wp031_for(StepOutcomeStatus.SATISFIED), forced=delegated
        )
    ).materialize(plan, source, "a")
    assert result.work_subject is not None
    later = record(plan, successor, "b", "later-b")
    later_subject = work_subject_from_plan_step(plan, later, "b")

    assert later.revision != successor.revision
    assert result.work_subject == later_subject
    assert result.work_subject.subject_id == later_subject.subject_id
    assert "revision" not in result.work_subject.reference.to_data()


def test_public_api_has_no_origin_input_and_default_subject_has_none() -> None:
    assert (
        "origin"
        not in inspect.signature(PlanStepWorkSubjectMaterializer.materialize).parameters
    )
    assert (
        "origin"
        not in inspect.signature(PlanStepWorkSubjectMaterializer.__init__).parameters
    )
    plan, run, delegated = canonical_wp031()
    result = PlanStepWorkSubjectMaterializer(
        handling_preparation_composer=RecordingWP031(
            wp031_for(StepOutcomeStatus.SATISFIED), forced=delegated
        )
    ).materialize(plan, run, "a")
    assert result.work_subject is not None
    assert result.work_subject.origin is None


def test_exact_delegated_artifact_identity_is_preserved() -> None:
    plan, run, delegated = canonical_wp031()
    adapter = RecordingAdapter()
    result = PlanStepWorkSubjectMaterializer(
        handling_preparation_composer=RecordingWP031(
            wp031_for(StepOutcomeStatus.SATISFIED), forced=delegated
        ),
        work_subject_adapter=adapter,
    ).materialize(plan, run, "a")

    assert result.assessment is delegated.assessment
    assert result.transition_decision is delegated.transition_decision
    assert result.progress_update is delegated.progress_update
    assert result.advancement_result is delegated.advancement_result
    assert result.handling_preparation is delegated.handling_preparation
    assert result.work_subject is adapter.results[0]


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
        "selected_without_preparation",
        "nonselected_with_preparation",
        "preparation_type",
        "preparation_plan",
        "preparation_run",
        "preparation_revision",
        "preparation_step",
    ],
)
def test_malformed_wp031_outputs_fail_before_wp015(mismatch: str) -> None:
    plan, run, canonical = canonical_wp031()
    assessment: object = canonical.assessment
    decision: object = canonical.transition_decision
    update: object = canonical.progress_update
    advancement: object = canonical.advancement_result
    preparation: object = canonical.handling_preparation
    forced: object
    if mismatch == "type":
        forced = object()
    else:
        assert isinstance(assessment, StepOutcomeAssessment)
        assert isinstance(decision, StepProgressTransitionDecision)
        assert isinstance(update, StepProgressUpdate)
        assert isinstance(advancement, PlanRunProgressAdvanceResult)
        assert isinstance(preparation, StepHandlingPreparationResult)
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
                advancement, source_update_id="foreign-update"
            )
        elif mismatch == "advancement_revision":
            advancement = unsafe_advancement(
                advancement, source_revision=run.revision + 1
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
                name, name
            )
            advancement = unsafe_advancement(
                advancement,
                updated_run=unsafe_run(updated, **{field_name: value}),
            )
        elif mismatch == "control_type":
            advancement = unsafe_advancement(advancement, control_decision=object())
        elif mismatch.startswith("control_"):
            control = advancement.control_decision
            name = mismatch.removeprefix("control_")
            if name == "plan":
                changed_control = replace(control, plan_id="foreign-plan")
            elif name == "run":
                changed_control = replace(control, run_id="foreign-run")
            else:
                changed_control = replace(
                    control,
                    observed_revision=advancement.updated_run.revision + 1,
                )
            advancement = unsafe_advancement(
                advancement,
                control_decision=changed_control,
            )
        elif mismatch == "selected_without_preparation":
            preparation = None
        elif mismatch == "nonselected_with_preparation":
            nonselected_plan, nonselected_run = control_scenario(
                ControlDecisionKind.RUN_STRUCTURALLY_COMPLETE
            )
            nonselected = wp031_for(StepOutcomeStatus.SATISFIED).compose(
                nonselected_plan, nonselected_run, "a"
            )
            assessment = nonselected.assessment
            decision = nonselected.transition_decision
            update = nonselected.progress_update
            advancement = nonselected.advancement_result
            plan, run = nonselected_plan, nonselected_run
        elif mismatch == "preparation_type":
            preparation = object()
        elif mismatch == "preparation_plan":
            preparation = replace(preparation, plan_id="foreign-plan")
        elif mismatch == "preparation_run":
            preparation = replace(preparation, run_id="foreign-run")
        elif mismatch == "preparation_revision":
            preparation = replace(
                preparation,
                observed_revision=advancement.updated_run.revision + 1,
            )
        else:
            preparation = replace(preparation, step_id="a")
        forced = unsafe_wp031_result(
            assessment, decision, update, advancement, preparation
        )
    wp031 = RecordingWP031(wp031_for(StepOutcomeStatus.SATISFIED), forced=forced)
    adapter = RecordingAdapter()

    with pytest.raises(PlanStepWorkSubjectMaterializationInvariantError):
        PlanStepWorkSubjectMaterializer(
            handling_preparation_composer=wp031,
            work_subject_adapter=adapter,
        ).materialize(plan, run, "a")
    assert len(wp031.calls) == 1
    assert adapter.calls == []


@pytest.mark.parametrize(
    "mismatch",
    ["type", "kind", "reference_type", "plan", "run", "step", "origin"],
)
def test_malformed_wp015_outputs_are_rejected(mismatch: str) -> None:
    plan, run, delegated = canonical_wp031()
    assert delegated.advancement_result is not None
    successor = delegated.advancement_result.updated_run
    canonical = work_subject_from_plan_step(plan, successor, "b")
    forced: object = canonical
    if mismatch == "type":
        forced = object()
    elif mismatch == "kind":
        forced = unsafe_subject(canonical, kind=WorkSubjectKind.REQUEST)
    elif mismatch == "reference_type":
        forced = unsafe_subject(canonical, reference=RequestWorkReference("request-1"))
    elif mismatch == "plan":
        forced = unsafe_subject(
            canonical,
            reference=PlanStepWorkReference("foreign-plan", run.run_id, "b"),
        )
    elif mismatch == "run":
        forced = unsafe_subject(
            canonical,
            reference=PlanStepWorkReference(plan.plan_id, "foreign-run", "b"),
        )
    elif mismatch == "step":
        forced = unsafe_subject(
            canonical,
            reference=PlanStepWorkReference(plan.plan_id, run.run_id, "a"),
        )
    else:
        forced = unsafe_subject(
            canonical,
            origin=WorkOrigin("request", "request-1"),
        )
    adapter = RecordingAdapter(forced=forced)

    with pytest.raises(PlanStepWorkSubjectMaterializationInvariantError):
        PlanStepWorkSubjectMaterializer(
            handling_preparation_composer=RecordingWP031(
                wp031_for(StepOutcomeStatus.SATISFIED), forced=delegated
            ),
            work_subject_adapter=adapter,
        ).materialize(plan, run, "a")
    assert len(adapter.calls) == 1


def test_wp031_failure_propagates_exactly_without_wp015() -> None:
    plan = make_plan(step("a"))
    run = new_run(plan)
    failure = RuntimeError("wp031 failed")
    wp031 = RecordingWP031(wp031_for(StepOutcomeStatus.INDETERMINATE), error=failure)
    adapter = RecordingAdapter()

    with pytest.raises(RuntimeError) as caught:
        PlanStepWorkSubjectMaterializer(
            handling_preparation_composer=wp031,
            work_subject_adapter=adapter,
        ).materialize(plan, run, "a")
    assert caught.value is failure
    assert len(wp031.calls) == 1
    assert adapter.calls == []


def test_wp015_failure_is_wrapped_once_without_fallback() -> None:
    plan, run, delegated = canonical_wp031()
    failure = RuntimeError("wp015 failed")
    adapter = RecordingAdapter(error=failure)

    with pytest.raises(PlanStepWorkSubjectMaterializationInvariantError) as caught:
        PlanStepWorkSubjectMaterializer(
            handling_preparation_composer=RecordingWP031(
                wp031_for(StepOutcomeStatus.SATISFIED), forced=delegated
            ),
            work_subject_adapter=adapter,
        ).materialize(plan, run, "a")
    assert caught.value.__cause__ is failure
    assert len(adapter.calls) == 1
    assert adapter.calls[0][2] == "b"


def test_result_is_immutable_and_serializes_exact_artifacts() -> None:
    plan, run, delegated = canonical_wp031()
    result = PlanStepWorkSubjectMaterializer(
        handling_preparation_composer=RecordingWP031(
            wp031_for(StepOutcomeStatus.SATISFIED), forced=delegated
        )
    ).materialize(plan, run, "a")
    assert result.work_subject is not None
    subject = result.work_subject

    with pytest.raises(FrozenInstanceError):
        result.work_subject = None  # type: ignore[misc]
    assert result.to_data() == {
        "assessment": delegated.assessment.to_data(),
        "transition_decision": delegated.transition_decision.to_data(),
        "progress_update": delegated.progress_update.to_data(),  # type: ignore[union-attr]
        "advancement_result": delegated.advancement_result.to_data(),  # type: ignore[union-attr]
        "handling_preparation": delegated.handling_preparation.to_data(),  # type: ignore[union-attr]
        "work_subject": subject.to_data(),
    }


def test_result_rejects_invalid_optional_shapes() -> None:
    plan, run, delegated = canonical_wp031()
    subject = WorkSubject(
        WorkSubjectKind.PLAN_STEP,
        PlanStepWorkReference(plan.plan_id, run.run_id, "b"),
    )
    with pytest.raises(PlanStepWorkSubjectMaterializationInvariantError):
        PlanStepWorkSubjectMaterializationResult(
            delegated.assessment,
            delegated.transition_decision,
            delegated.progress_update,
            delegated.advancement_result,
            delegated.handling_preparation,
            None,
        )

    no_plan = make_plan(step("a"))
    no_run = active_with_evidence(no_plan, new_run(no_plan))
    no_result = wp031_for(StepOutcomeStatus.INDETERMINATE).compose(no_plan, no_run, "a")
    with pytest.raises(PlanStepWorkSubjectMaterializationInvariantError):
        PlanStepWorkSubjectMaterializationResult(
            no_result.assessment,
            no_result.transition_decision,
            None,
            None,
            None,
            subject,
        )


def test_repeated_invocations_are_allowed_without_hidden_deduplication() -> None:
    plan, run, delegated = canonical_wp031()
    wp031 = RecordingWP031(wp031_for(StepOutcomeStatus.SATISFIED), forced=delegated)
    adapter = RecordingAdapter()
    materializer = PlanStepWorkSubjectMaterializer(
        handling_preparation_composer=wp031,
        work_subject_adapter=adapter,
    )

    first = materializer.materialize(plan, run, "a")
    second = materializer.materialize(plan, run, "a")

    assert len(wp031.calls) == len(adapter.calls) == 2
    assert first.work_subject == second.work_subject
    assert first.work_subject is adapter.results[0]
    assert second.work_subject is adapter.results[1]


def test_wp032_has_no_lower_authority_or_continuation_dependencies() -> None:
    import iris.plan_step_work_subject_materialization.materializer as module

    source = inspect.getsource(module)
    for forbidden in (
        "PlanRunReducer",
        "PlanRunController",
        "derive_step_availability",
        "PlanStepHandlingPreparer",
        "PlanStepProgressAdvancementComposer",
        "StepProgressTransitionDecider",
        "StepProgressUpdateSynthesizer",
        "ContextSnapshot",
        "Orchestrator",
        "ExecutionRequest",
        "ExecutionCoordinator",
        "PlanStepExecutionBinder",
    ):
        assert forbidden not in source


def test_successful_materialization_stops_before_context_or_execution() -> None:
    plan, run, delegated = canonical_wp031()
    result = PlanStepWorkSubjectMaterializer(
        handling_preparation_composer=RecordingWP031(
            wp031_for(StepOutcomeStatus.SATISFIED), forced=delegated
        )
    ).materialize(plan, run, "a")

    assert result.work_subject is not None
    assert result.work_subject.kind is WorkSubjectKind.PLAN_STEP
    assert result.work_subject.origin is None
    assert result.advancement_result is delegated.advancement_result
    assert result.advancement_result is not None
    selected = result.advancement_result.control_decision.selected_step_id
    selected_progress = next(
        item
        for item in result.advancement_result.updated_run.step_progress
        if item.step_id == selected
    )
    assert selected_progress.state is StepProgressState.NOT_STARTED
