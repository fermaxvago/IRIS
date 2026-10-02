"""WP033 post-selection WorkSubject Context materialization composition."""

from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError, dataclass, field, replace
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, cast

import pytest

from iris.context import (
    ContextBudget,
    ContextCandidate,
    ContextEngine,
    ContextEvidence,
    ContextSnapshot,
    ContextUncertainty,
    EvidenceSource,
    Freshness,
    Relevance,
    RequestEvidenceSubjectMismatchError,
    ResolutionStatus,
    UncertaintyReason,
)
from iris.memory import EpistemicStatus, MemoryScope, ScopeKind
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
from iris.plan_step_context_materialization import (
    PlanStepContextMaterializationError,
    PlanStepContextMaterializationInvariantError,
    PlanStepContextMaterializationResult,
    PlanStepContextMaterializer,
)
from iris.plan_step_evidence_assessment import PlanStepEvidenceAssessor
from iris.plan_step_evidence_transition import PlanStepEvidenceTransitionComposer
from iris.plan_step_handling_preparation import PlanStepHandlingPreparationComposer
from iris.plan_step_progress_advancement import PlanStepProgressAdvancementComposer
from iris.plan_step_progress_update_preparation import (
    PlanStepProgressUpdatePreparer,
)
from iris.plan_step_work_subject_materialization import (
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
    WorkOrigin,
    WorkSubject,
    WorkSubjectKind,
)

BASE = datetime(2026, 10, 2, 23, tzinfo=UTC)
ASSESSED = BASE + timedelta(seconds=100)
DECIDED = BASE + timedelta(seconds=101)
UPDATED = BASE + timedelta(seconds=102)
CREATED = BASE + timedelta(seconds=200)
GLOBAL = MemoryScope(ScopeKind.GLOBAL)
PROVENANCE = RunProvenance("test", "wp033")


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


def wp032_for(status: StepOutcomeStatus) -> PlanStepWorkSubjectMaterializer:
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
    update_preparer = PlanStepProgressUpdatePreparer(
        evidence_transition_composer=transition_composer,
        progress_update_synthesizer=StepProgressUpdateSynthesizer(
            clock=lambda: UPDATED,
            update_id_factory=lambda: "progress-update-1",
        ),
    )
    advancement = PlanStepProgressAdvancementComposer(
        progress_update_preparer=update_preparer,
        progress_advancer=PlanRunProgressAdvancer(),
    )
    handling = PlanStepHandlingPreparationComposer(
        progress_advancement_composer=advancement,
        handling_preparer=PlanStepHandlingPreparer(),
    )
    return PlanStepWorkSubjectMaterializer(
        handling_preparation_composer=handling,
    )


class RecordingWP032(PlanStepWorkSubjectMaterializer):
    def __init__(
        self,
        delegate: PlanStepWorkSubjectMaterializer,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__()
        self.delegate = delegate
        self.forced = forced
        self.error = error
        self.calls: list[tuple[Plan, PlanRun, str]] = []

    def materialize(
        self,
        plan: Plan,
        run: PlanRun,
        step_id: str,
    ) -> PlanStepWorkSubjectMaterializationResult:
        self.calls.append((plan, run, step_id))
        if self.error is not None:
            raise self.error
        if self.forced is not None:
            return cast(PlanStepWorkSubjectMaterializationResult, self.forced)
        return self.delegate.materialize(plan, run, step_id)


class RecordingContextEngine(ContextEngine):
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
                WorkSubject | None,
                str | None,
                tuple[ContextCandidate, ...],
                ContextBudget,
                tuple[ContextUncertainty, ...],
                datetime | None,
            ]
        ] = []
        self.results: list[ContextSnapshot] = []

    def build(
        self,
        *,
        subject: WorkSubject | None = None,
        request_id: str | None = None,
        candidates: tuple[ContextCandidate, ...],
        budget: ContextBudget,
        uncertainties: tuple[ContextUncertainty, ...] = (),
        created_at: datetime | None = None,
    ) -> ContextSnapshot:
        self.calls.append(
            (subject, request_id, candidates, budget, uncertainties, created_at)
        )
        if self.error is not None:
            raise self.error
        if self.forced is not None:
            result = cast(ContextSnapshot, self.forced)
        else:
            result = super().build(
                subject=subject,
                request_id=request_id,
                candidates=candidates,
                budget=budget,
                uncertainties=uncertainties,
                created_at=created_at,
            )
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


def canonical_wp032(
    *,
    handling: HandlingKind | None = HandlingKind.CAPABILITY,
) -> tuple[Plan, PlanRun, PlanStepWorkSubjectMaterializationResult]:
    plan, run = control_scenario(
        ControlDecisionKind.STEP_SELECTED,
        selected_handling=handling,
    )
    result = wp032_for(StepOutcomeStatus.SATISFIED).materialize(plan, run, "a")
    assert result.work_subject is not None
    assert result.handling_preparation is not None
    return plan, run, result


def candidate(
    candidate_id: str = "candidate-1",
    value: str = "context",
    *,
    key: str = "active_task",
    source: EvidenceSource = EvidenceSource.CALLER,
    reference: str = "caller-1",
    relevance: Relevance = Relevance.HIGH,
    freshness: Freshness = Freshness.CURRENT,
) -> ContextCandidate:
    return ContextCandidate(
        candidate_id,
        "task",
        key,
        value,
        ContextEvidence(source, reference, EpistemicStatus.UNKNOWN),
        GLOBAL,
        relevance,
        freshness,
        BASE,
    )


def unsafe_wp032_result(
    assessment: object,
    decision: object,
    update: object,
    advancement: object,
    preparation: object,
    subject: object,
) -> PlanStepWorkSubjectMaterializationResult:
    result = object.__new__(PlanStepWorkSubjectMaterializationResult)
    object.__setattr__(result, "assessment", assessment)
    object.__setattr__(result, "transition_decision", decision)
    object.__setattr__(result, "progress_update", update)
    object.__setattr__(result, "advancement_result", advancement)
    object.__setattr__(result, "handling_preparation", preparation)
    object.__setattr__(result, "work_subject", subject)
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


def test_public_api_defaults_and_constructor_dependency_types() -> None:
    assert PlanStepContextMaterializer()
    assert issubclass(
        PlanStepContextMaterializationInvariantError,
        PlanStepContextMaterializationError,
    )
    with pytest.raises(TypeError, match="work_subject_materializer"):
        PlanStepContextMaterializer(work_subject_materializer=cast(Any, object()))
    with pytest.raises(TypeError, match="context_engine"):
        PlanStepContextMaterializer(context_engine=cast(Any, object()))


@pytest.mark.parametrize(
    ("position", "message"),
    [
        (0, "plan must be a Plan"),
        (1, "run must be a PlanRun"),
        (2, "step_id"),
        (3, "candidates"),
        (4, "budget"),
        (5, "uncertainties"),
        (6, "created_at"),
    ],
)
def test_invalid_direct_input_types_fail_before_wp032(
    position: int,
    message: str,
) -> None:
    plan = make_plan(step("a"))
    values: list[object] = [
        plan,
        new_run(plan),
        "a",
        (),
        ContextBudget(0),
        (),
        CREATED,
    ]
    values[position] = object()
    wp032 = RecordingWP032(wp032_for(StepOutcomeStatus.INDETERMINATE))

    with pytest.raises(TypeError, match=message):
        PlanStepContextMaterializer(work_subject_materializer=wp032).materialize(
            cast(Plan, values[0]),
            cast(PlanRun, values[1]),
            cast(str, values[2]),
            candidates=cast(tuple[ContextCandidate, ...], values[3]),
            budget=cast(ContextBudget, values[4]),
            uncertainties=cast(tuple[ContextUncertainty, ...], values[5]),
            created_at=cast(datetime, values[6]),
        )
    assert wp032.calls == []


def test_no_work_subject_stops_without_context_and_preserves_artifacts() -> None:
    plan = make_plan(step("a"))
    run = active_with_evidence(plan, new_run(plan))
    delegated = wp032_for(StepOutcomeStatus.INDETERMINATE).materialize(plan, run, "a")
    assert delegated.work_subject is None
    wp032 = RecordingWP032(wp032_for(StepOutcomeStatus.INDETERMINATE), forced=delegated)
    engine = RecordingContextEngine()
    before = (plan.to_data(), run.to_data())

    result = PlanStepContextMaterializer(
        work_subject_materializer=wp032,
        context_engine=engine,
    ).materialize(
        plan,
        run,
        "a",
        candidates=(),
        budget=ContextBudget(0),
        created_at=CREATED,
    )

    assert wp032.calls == [(plan, run, "a")]
    assert engine.calls == []
    assert result.assessment is delegated.assessment
    assert result.transition_decision is delegated.transition_decision
    assert result.progress_update is delegated.progress_update
    assert result.advancement_result is delegated.advancement_result
    assert result.handling_preparation is delegated.handling_preparation
    assert result.work_subject is None
    assert result.context_snapshot is None
    assert (plan.to_data(), run.to_data()) == before


def test_exact_explicit_inputs_and_subject_are_forwarded_once() -> None:
    plan, run, delegated = canonical_wp032()
    assert delegated.work_subject is not None
    item = candidate()
    uncertainty = ContextUncertainty(
        "task", "missing_detail", GLOBAL, UncertaintyReason.MISSING
    )
    candidates = (item,)
    uncertainties = (uncertainty,)
    budget = ContextBudget(2)
    engine = RecordingContextEngine()

    result = PlanStepContextMaterializer(
        work_subject_materializer=RecordingWP032(
            wp032_for(StepOutcomeStatus.SATISFIED), forced=delegated
        ),
        context_engine=engine,
    ).materialize(
        plan,
        run,
        "a",
        candidates=candidates,
        budget=budget,
        uncertainties=uncertainties,
        created_at=CREATED,
    )

    assert engine.calls == [
        (delegated.work_subject, None, candidates, budget, uncertainties, CREATED)
    ]
    assert result.context_snapshot is engine.results[0]
    assert result.context_snapshot.subject is delegated.work_subject
    assert result.context_snapshot.subject_id == delegated.work_subject.subject_id


def test_empty_context_is_real_snapshot_not_absence() -> None:
    plan, run, delegated = canonical_wp032()
    result = PlanStepContextMaterializer(
        work_subject_materializer=RecordingWP032(
            wp032_for(StepOutcomeStatus.SATISFIED), forced=delegated
        )
    ).materialize(
        plan,
        run,
        "a",
        candidates=(),
        budget=ContextBudget(0),
        created_at=CREATED,
    )

    assert result.work_subject is not None
    assert result.context_snapshot is not None
    assert result.context_snapshot.items == ()
    assert result.context_snapshot.status is ResolutionStatus.RESOLVED


@pytest.mark.parametrize(
    "expected",
    [
        ResolutionStatus.RESOLVED,
        ResolutionStatus.PARTIAL,
        ResolutionStatus.AMBIGUOUS,
        ResolutionStatus.CONFLICTED,
    ],
)
def test_all_resolution_statuses_are_preserved_without_retry(
    expected: ResolutionStatus,
) -> None:
    plan, run, delegated = canonical_wp032()
    candidates: tuple[ContextCandidate, ...]
    uncertainties: tuple[ContextUncertainty, ...] = ()
    if expected is ResolutionStatus.RESOLVED:
        candidates = (candidate(),)
    elif expected is ResolutionStatus.PARTIAL:
        candidates = ()
        uncertainties = (
            ContextUncertainty(
                "task", "missing_detail", GLOBAL, UncertaintyReason.MISSING
            ),
        )
    elif expected is ResolutionStatus.AMBIGUOUS:
        candidates = (
            candidate("candidate-a", key="option_a"),
            candidate("candidate-b", key="option_b"),
        )
        uncertainties = (
            ContextUncertainty(
                "task",
                "intended_task",
                GLOBAL,
                UncertaintyReason.MULTIPLE_PLAUSIBLE,
                ("candidate-a", "candidate-b"),
            ),
        )
    else:
        candidates = (
            candidate("candidate-a", "alpha"),
            candidate("candidate-b", "beta"),
        )
    engine = RecordingContextEngine()

    result = PlanStepContextMaterializer(
        work_subject_materializer=RecordingWP032(
            wp032_for(StepOutcomeStatus.SATISFIED), forced=delegated
        ),
        context_engine=engine,
    ).materialize(
        plan,
        run,
        "a",
        candidates=candidates,
        budget=ContextBudget(2),
        uncertainties=uncertainties,
        created_at=CREATED,
    )

    assert len(engine.calls) == 1
    assert result.context_snapshot is engine.results[0]
    assert result.context_snapshot.status is expected


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
def test_handling_status_never_gates_context(
    handling: HandlingKind | None,
    status: StepHandlingPreparationStatus,
) -> None:
    plan, run, delegated = canonical_wp032(handling=handling)
    assert delegated.handling_preparation is not None
    assert delegated.handling_preparation.status is status
    engine = RecordingContextEngine()

    result = PlanStepContextMaterializer(
        work_subject_materializer=RecordingWP032(
            wp032_for(StepOutcomeStatus.SATISFIED), forced=delegated
        ),
        context_engine=engine,
    ).materialize(
        plan,
        run,
        "a",
        candidates=(),
        budget=ContextBudget(0),
        created_at=CREATED,
    )

    assert len(engine.calls) == 1
    assert result.context_snapshot is not None


def test_processed_step_a_context_owns_exact_selected_subject_b() -> None:
    plan, run, delegated = canonical_wp032()
    assert delegated.assessment.step_id == "a"
    assert delegated.work_subject is not None
    assert isinstance(delegated.work_subject.reference, PlanStepWorkReference)
    assert delegated.work_subject.reference.step_id == "b"
    engine = RecordingContextEngine()

    result = PlanStepContextMaterializer(
        work_subject_materializer=RecordingWP032(
            wp032_for(StepOutcomeStatus.SATISFIED), forced=delegated
        ),
        context_engine=engine,
    ).materialize(
        plan,
        run,
        "a",
        candidates=(candidate(),),
        budget=ContextBudget(1),
        created_at=CREATED,
    )

    assert engine.calls[0][0] is delegated.work_subject
    assert result.context_snapshot is not None
    assert result.context_snapshot.subject is delegated.work_subject
    reference = result.context_snapshot.subject.reference
    assert isinstance(reference, PlanStepWorkReference)
    assert reference.step_id == "b"
    assert "revision" not in delegated.work_subject.reference.to_data()


def test_request_evidence_without_origin_is_canonical_context_error() -> None:
    plan, run, delegated = canonical_wp032()
    assert delegated.work_subject is not None
    assert delegated.work_subject.origin is None
    request_evidence = candidate(
        source=EvidenceSource.REQUEST,
        reference="request-root",
    )
    engine = RecordingContextEngine()

    with pytest.raises(RequestEvidenceSubjectMismatchError):
        PlanStepContextMaterializer(
            work_subject_materializer=RecordingWP032(
                wp032_for(StepOutcomeStatus.SATISFIED), forced=delegated
            ),
            context_engine=engine,
        ).materialize(
            plan,
            run,
            "a",
            candidates=(request_evidence,),
            budget=ContextBudget(1),
            created_at=CREATED,
        )
    assert len(engine.calls) == 1
    assert delegated.work_subject.origin is None


def test_created_at_is_forwarded_exactly_and_snapshot_uses_canonical_utc() -> None:
    plan, run, delegated = canonical_wp032()
    local_time = datetime(2026, 10, 2, 17, tzinfo=timezone(timedelta(hours=-6)))
    engine = RecordingContextEngine()

    result = PlanStepContextMaterializer(
        work_subject_materializer=RecordingWP032(
            wp032_for(StepOutcomeStatus.SATISFIED), forced=delegated
        ),
        context_engine=engine,
    ).materialize(
        plan,
        run,
        "a",
        candidates=(),
        budget=ContextBudget(0),
        created_at=local_time,
    )

    assert engine.calls[0][5] is local_time
    assert result.context_snapshot is not None
    assert result.context_snapshot.created_at == local_time.astimezone(UTC)


def test_exact_cumulative_artifact_identity_is_preserved() -> None:
    plan, run, delegated = canonical_wp032()
    engine = RecordingContextEngine()
    result = PlanStepContextMaterializer(
        work_subject_materializer=RecordingWP032(
            wp032_for(StepOutcomeStatus.SATISFIED), forced=delegated
        ),
        context_engine=engine,
    ).materialize(
        plan,
        run,
        "a",
        candidates=(),
        budget=ContextBudget(0),
        created_at=CREATED,
    )

    assert result.assessment is delegated.assessment
    assert result.transition_decision is delegated.transition_decision
    assert result.progress_update is delegated.progress_update
    assert result.advancement_result is delegated.advancement_result
    assert result.handling_preparation is delegated.handling_preparation
    assert result.work_subject is delegated.work_subject
    assert result.context_snapshot is engine.results[0]


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
        "selected_without_subject",
        "preparation_step",
        "subject_plan",
        "subject_run",
        "subject_step",
        "subject_origin",
    ],
)
def test_malformed_wp032_outputs_fail_before_context(mismatch: str) -> None:
    plan, run, canonical = canonical_wp032()
    assessment: object = canonical.assessment
    decision: object = canonical.transition_decision
    update: object = canonical.progress_update
    advancement: object = canonical.advancement_result
    preparation: object = canonical.handling_preparation
    subject: object = canonical.work_subject
    forced: object
    if mismatch == "type":
        forced = object()
    else:
        assert isinstance(assessment, StepOutcomeAssessment)
        assert isinstance(decision, StepProgressTransitionDecision)
        assert isinstance(update, StepProgressUpdate)
        assert isinstance(advancement, PlanRunProgressAdvanceResult)
        assert isinstance(preparation, StepHandlingPreparationResult)
        assert isinstance(subject, WorkSubject)
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
                advancement, control_decision=changed_control
            )
        elif mismatch == "selected_without_preparation":
            preparation = None
        elif mismatch == "selected_without_subject":
            subject = None
        elif mismatch == "preparation_step":
            preparation = replace(preparation, step_id="a")
        elif mismatch == "subject_plan":
            subject = WorkSubject(
                WorkSubjectKind.PLAN_STEP,
                PlanStepWorkReference("foreign-plan", run.run_id, "b"),
            )
        elif mismatch == "subject_run":
            subject = WorkSubject(
                WorkSubjectKind.PLAN_STEP,
                PlanStepWorkReference(plan.plan_id, "foreign-run", "b"),
            )
        elif mismatch == "subject_step":
            subject = WorkSubject(
                WorkSubjectKind.PLAN_STEP,
                PlanStepWorkReference(plan.plan_id, run.run_id, "a"),
            )
        else:
            subject = replace(
                subject,
                origin=WorkOrigin("request", "request-root"),
            )
        forced = unsafe_wp032_result(
            assessment, decision, update, advancement, preparation, subject
        )
    wp032 = RecordingWP032(wp032_for(StepOutcomeStatus.SATISFIED), forced=forced)
    engine = RecordingContextEngine()

    with pytest.raises(PlanStepContextMaterializationInvariantError):
        PlanStepContextMaterializer(
            work_subject_materializer=wp032,
            context_engine=engine,
        ).materialize(
            plan,
            run,
            "a",
            candidates=(),
            budget=ContextBudget(0),
            created_at=CREATED,
        )
    assert len(wp032.calls) == 1
    assert engine.calls == []


@pytest.mark.parametrize("mismatch", ["type", "owner", "budget", "time"])
def test_malformed_context_returns_are_rejected(mismatch: str) -> None:
    plan, run, delegated = canonical_wp032()
    assert delegated.work_subject is not None
    budget = ContextBudget(0)
    canonical = ContextEngine().build(
        subject=delegated.work_subject,
        candidates=(),
        budget=budget,
        created_at=CREATED,
    )
    forced: object = canonical
    if mismatch == "type":
        forced = object()
    elif mismatch == "owner":
        equivalent = WorkSubject(
            WorkSubjectKind.PLAN_STEP,
            cast(PlanStepWorkReference, delegated.work_subject.reference),
        )
        assert equivalent == delegated.work_subject
        assert equivalent is not delegated.work_subject
        forced = replace(canonical, subject=equivalent)
    elif mismatch == "budget":
        forced = replace(canonical, budget=ContextBudget(1))
    else:
        forced = replace(canonical, created_at=CREATED + timedelta(seconds=1))
    engine = RecordingContextEngine(forced=forced)

    with pytest.raises(PlanStepContextMaterializationInvariantError):
        PlanStepContextMaterializer(
            work_subject_materializer=RecordingWP032(
                wp032_for(StepOutcomeStatus.SATISFIED), forced=delegated
            ),
            context_engine=engine,
        ).materialize(
            plan,
            run,
            "a",
            candidates=(),
            budget=budget,
            created_at=CREATED,
        )
    assert len(engine.calls) == 1


def test_wp032_failure_propagates_exactly_without_context() -> None:
    plan = make_plan(step("a"))
    run = new_run(plan)
    failure = RuntimeError("wp032 failed")
    wp032 = RecordingWP032(wp032_for(StepOutcomeStatus.INDETERMINATE), error=failure)
    engine = RecordingContextEngine()

    with pytest.raises(RuntimeError) as caught:
        PlanStepContextMaterializer(
            work_subject_materializer=wp032,
            context_engine=engine,
        ).materialize(
            plan,
            run,
            "a",
            candidates=(),
            budget=ContextBudget(0),
            created_at=CREATED,
        )
    assert caught.value is failure
    assert engine.calls == []


def test_context_failure_propagates_exactly_once_and_is_not_none() -> None:
    plan, run, delegated = canonical_wp032()
    failure = RuntimeError("context failed")
    engine = RecordingContextEngine(error=failure)

    with pytest.raises(RuntimeError) as caught:
        PlanStepContextMaterializer(
            work_subject_materializer=RecordingWP032(
                wp032_for(StepOutcomeStatus.SATISFIED), forced=delegated
            ),
            context_engine=engine,
        ).materialize(
            plan,
            run,
            "a",
            candidates=(),
            budget=ContextBudget(0),
            created_at=CREATED,
        )
    assert caught.value is failure
    assert len(engine.calls) == 1


def test_result_is_immutable_and_serializes_exact_snapshot() -> None:
    plan, run, delegated = canonical_wp032()
    result = PlanStepContextMaterializer(
        work_subject_materializer=RecordingWP032(
            wp032_for(StepOutcomeStatus.SATISFIED), forced=delegated
        )
    ).materialize(
        plan,
        run,
        "a",
        candidates=(),
        budget=ContextBudget(0),
        created_at=CREATED,
    )
    assert result.context_snapshot is not None
    snapshot = result.context_snapshot

    with pytest.raises(FrozenInstanceError):
        result.context_snapshot = None  # type: ignore[misc]
    assert result.to_data() == {
        "assessment": delegated.assessment.to_data(),
        "transition_decision": delegated.transition_decision.to_data(),
        "progress_update": delegated.progress_update.to_data(),  # type: ignore[union-attr]
        "advancement_result": delegated.advancement_result.to_data(),  # type: ignore[union-attr]
        "handling_preparation": delegated.handling_preparation.to_data(),  # type: ignore[union-attr]
        "work_subject": delegated.work_subject.to_data(),  # type: ignore[union-attr]
        "context_snapshot": snapshot.to_data(),
    }


def test_result_rejects_absent_vs_empty_snapshot_confusion() -> None:
    plan, run, delegated = canonical_wp032()
    with pytest.raises(PlanStepContextMaterializationInvariantError):
        PlanStepContextMaterializationResult(
            delegated.assessment,
            delegated.transition_decision,
            delegated.progress_update,
            delegated.advancement_result,
            delegated.handling_preparation,
            delegated.work_subject,
            None,
        )

    no_plan = make_plan(step("a"))
    no_run = active_with_evidence(no_plan, new_run(no_plan))
    no_work = wp032_for(StepOutcomeStatus.INDETERMINATE).materialize(
        no_plan, no_run, "a"
    )
    assert delegated.work_subject is not None
    foreign_snapshot = ContextEngine().build(
        subject=delegated.work_subject,
        candidates=(),
        budget=ContextBudget(0),
        created_at=CREATED,
    )
    with pytest.raises(PlanStepContextMaterializationInvariantError):
        PlanStepContextMaterializationResult(
            no_work.assessment,
            no_work.transition_decision,
            None,
            None,
            None,
            None,
            foreign_snapshot,
        )


def test_repeated_invocations_build_distinct_snapshots_without_dedup() -> None:
    plan, run, delegated = canonical_wp032()
    wp032 = RecordingWP032(wp032_for(StepOutcomeStatus.SATISFIED), forced=delegated)
    engine = RecordingContextEngine()
    materializer = PlanStepContextMaterializer(
        work_subject_materializer=wp032,
        context_engine=engine,
    )

    first = materializer.materialize(
        plan,
        run,
        "a",
        candidates=(),
        budget=ContextBudget(0),
        created_at=CREATED,
    )
    second = materializer.materialize(
        plan,
        run,
        "a",
        candidates=(),
        budget=ContextBudget(0),
        created_at=CREATED,
    )

    assert len(wp032.calls) == len(engine.calls) == 2
    assert first.work_subject is second.work_subject is delegated.work_subject
    assert first.context_snapshot is not None
    assert second.context_snapshot is not None
    assert first.context_snapshot.snapshot_id != second.context_snapshot.snapshot_id


def test_wp033_has_no_discovery_or_continuation_dependencies() -> None:
    import iris.plan_step_context_materialization.materializer as module

    source = inspect.getsource(module)
    for forbidden in (
        "MemoryContextSource",
        "MemoryService",
        "PlanRunReducer",
        "PlanRunController",
        "Orchestrator",
        "ExecutionCoordinator",
        "PlanStepExecutionBinder",
        "PlanStepExecutionStartCoordinator",
        "PlanStepHandlingPreparer",
        "PlanStepProgressAdvancementComposer",
        "work_subject_from_plan_step",
        "subprocess",
        "socket",
        "open(",
    ):
        assert forbidden not in source
