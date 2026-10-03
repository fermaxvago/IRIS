"""WP034 bounded post-Context PlanStep orchestration composition."""

from __future__ import annotations

import inspect
import json
from dataclasses import FrozenInstanceError, dataclass, field, replace
from datetime import UTC, datetime, timedelta
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
    ResolutionStatus,
    UncertaintyReason,
)
from iris.memory import EpistemicStatus, MemoryScope, ScopeKind
from iris.orchestrator import (
    ContextBlocker,
    ContextBlockerKind,
    HandlerAvailability,
    HandlingKind,
    OrchestrationDecision,
    OrchestrationInput,
    OrchestrationReason,
    OrchestrationTarget,
    Orchestrator,
    StaleOrchestrationDecisionError,
    validate_orchestration_decision_current,
)
from iris.outcome_assessment import (
    StepOutcomeAssessment,
    StepOutcomeEvaluator,
    StepOutcomeStatus,
)
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
    PlanStepContextMaterializationResult,
    PlanStepContextMaterializer,
)
from iris.plan_step_evidence_assessment import PlanStepEvidenceAssessor
from iris.plan_step_evidence_transition import PlanStepEvidenceTransitionComposer
from iris.plan_step_handling_preparation import PlanStepHandlingPreparationComposer
from iris.plan_step_orchestration import (
    PlanStepOrchestrationComposer,
    PlanStepOrchestrationError,
    PlanStepOrchestrationInvariantError,
    PlanStepOrchestrationResult,
)
from iris.plan_step_progress_advancement import PlanStepProgressAdvancementComposer
from iris.plan_step_progress_update_preparation import (
    PlanStepProgressUpdatePreparer,
)
from iris.plan_step_work_subject_materialization import (
    PlanStepWorkSubjectMaterializer,
)
from iris.planning import Plan, PlanStep
from iris.step_progress_transition import (
    StepProgressTransitionDecider,
)
from iris.step_progress_update_synthesis import StepProgressUpdateSynthesizer
from iris.work_identity import PlanStepWorkReference, WorkSubject

BASE = datetime(2026, 10, 3, tzinfo=UTC)
ASSESSED = BASE + timedelta(seconds=100)
DECIDED = BASE + timedelta(seconds=101)
UPDATED = BASE + timedelta(seconds=102)
CONTEXT_CREATED = BASE + timedelta(seconds=200)
ORCHESTRATED = BASE + timedelta(seconds=201)
GLOBAL = MemoryScope(ScopeKind.GLOBAL)
PROVENANCE = RunProvenance("test", "wp034")
DEFAULT_BUDGET = ContextBudget(10)
CAPABILITY_AVAILABLE = HandlerAvailability(capability=True)


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


def wp033_for(status: StepOutcomeStatus) -> PlanStepContextMaterializer:
    assessor = PlanStepEvidenceAssessor(
        cast(StepOutcomeEvaluator, StatusEvaluator(status))
    )
    evidence_transition = PlanStepEvidenceTransitionComposer(
        assessor=assessor,
        transition_decider=StepProgressTransitionDecider(
            clock=lambda: DECIDED,
            decision_id_factory=lambda: "transition-decision-1",
        ),
    )
    update_preparer = PlanStepProgressUpdatePreparer(
        evidence_transition_composer=evidence_transition,
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
    work = PlanStepWorkSubjectMaterializer(
        handling_preparation_composer=handling,
    )
    return PlanStepContextMaterializer(work_subject_materializer=work)


class RecordingWP033(PlanStepContextMaterializer):
    def __init__(
        self,
        delegate: PlanStepContextMaterializer,
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
                str,
                tuple[ContextCandidate, ...],
                ContextBudget,
                tuple[ContextUncertainty, ...],
                datetime,
            ]
        ] = []

    def materialize(
        self,
        plan: Plan,
        run: PlanRun,
        step_id: str,
        *,
        candidates: tuple[ContextCandidate, ...],
        budget: ContextBudget,
        uncertainties: tuple[ContextUncertainty, ...] = (),
        created_at: datetime,
    ) -> PlanStepContextMaterializationResult:
        self.calls.append(
            (plan, run, step_id, candidates, budget, uncertainties, created_at)
        )
        if self.error is not None:
            raise self.error
        if self.forced is not None:
            return cast(PlanStepContextMaterializationResult, self.forced)
        return self.delegate.materialize(
            plan,
            run,
            step_id,
            candidates=candidates,
            budget=budget,
            uncertainties=uncertainties,
            created_at=created_at,
        )


class RecordingOrchestrator(Orchestrator):
    def __init__(
        self,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        self._counter = 0
        super().__init__(
            clock=lambda: ORCHESTRATED,
            id_factory=self._next_id,
        )
        self.forced = forced
        self.error = error
        self.calls: list[OrchestrationInput] = []
        self.results: list[OrchestrationDecision] = []

    def _next_id(self) -> str:
        self._counter += 1
        return f"orchestration-decision-{self._counter}"

    def decide(self, orchestration_input: OrchestrationInput) -> OrchestrationDecision:
        self.calls.append(orchestration_input)
        if self.error is not None:
            raise self.error
        if self.forced is not None:
            result = cast(OrchestrationDecision, self.forced)
        else:
            result = super().decide(orchestration_input)
        self.results.append(result)
        return result


def candidate(
    candidate_id: str = "candidate-1",
    value: str = "context",
    *,
    key: str = "active_task",
    relevance: Relevance = Relevance.HIGH,
) -> ContextCandidate:
    return ContextCandidate(
        candidate_id=candidate_id,
        kind="task",
        key=key,
        value=value,
        evidence=ContextEvidence(
            EvidenceSource.CALLER,
            candidate_id,
            EpistemicStatus.DIRECT,
        ),
        scope=GLOBAL,
        relevance=relevance,
        freshness=Freshness.CURRENT,
    )


def selected_scenario(
    handling: HandlingKind | None = HandlingKind.CAPABILITY,
) -> tuple[Plan, PlanRun]:
    plan = make_plan(
        step("a"),
        step("b", depends_on=("a",), handling=handling),
    )
    return plan, active_with_evidence(plan, new_run(plan))


def canonical_wp033(
    *,
    handling: HandlingKind | None = HandlingKind.CAPABILITY,
    candidates: tuple[ContextCandidate, ...] = (),
    budget: ContextBudget = DEFAULT_BUDGET,
    uncertainties: tuple[ContextUncertainty, ...] = (),
) -> tuple[Plan, PlanRun, PlanStepContextMaterializationResult]:
    plan, run = selected_scenario(handling)
    result = wp033_for(StepOutcomeStatus.SATISFIED).materialize(
        plan,
        run,
        "a",
        candidates=candidates,
        budget=budget,
        uncertainties=uncertainties,
        created_at=CONTEXT_CREATED,
    )
    assert result.work_subject is not None
    assert result.context_snapshot is not None
    assert result.handling_preparation is not None
    return plan, run, result


def unsafe_wp033_result(
    source: PlanStepContextMaterializationResult,
    **changes: object,
) -> PlanStepContextMaterializationResult:
    result = object.__new__(PlanStepContextMaterializationResult)
    for name in (
        "assessment",
        "transition_decision",
        "progress_update",
        "advancement_result",
        "handling_preparation",
        "work_subject",
        "context_snapshot",
    ):
        object.__setattr__(result, name, changes.get(name, getattr(source, name)))
    return result


def unsafe_preparation(
    source: StepHandlingPreparationResult,
    **changes: object,
) -> StepHandlingPreparationResult:
    result = object.__new__(StepHandlingPreparationResult)
    for name in (
        "plan_id",
        "run_id",
        "observed_revision",
        "step_id",
        "status",
        "reason",
        "provenance",
        "handling_kind",
        "handling_need",
    ):
        object.__setattr__(result, name, changes.get(name, getattr(source, name)))
    return result


def unsafe_advancement(
    source: PlanRunProgressAdvanceResult,
    **changes: object,
) -> PlanRunProgressAdvanceResult:
    result = object.__new__(PlanRunProgressAdvanceResult)
    for name in (
        "source_update_id",
        "source_revision",
        "updated_run",
        "control_decision",
    ):
        object.__setattr__(result, name, changes.get(name, getattr(source, name)))
    return result


def compose_from(
    plan: Plan,
    run: PlanRun,
    delegated: PlanStepContextMaterializationResult,
    *,
    candidates: tuple[ContextCandidate, ...] = (),
    budget: ContextBudget = DEFAULT_BUDGET,
    uncertainties: tuple[ContextUncertainty, ...] = (),
    availability: HandlerAvailability = CAPABILITY_AVAILABLE,
    orchestrator: RecordingOrchestrator | None = None,
) -> tuple[
    PlanStepOrchestrationResult,
    RecordingWP033,
    RecordingOrchestrator,
]:
    wp033 = RecordingWP033(
        wp033_for(StepOutcomeStatus.SATISFIED),
        forced=delegated,
    )
    recorder = RecordingOrchestrator() if orchestrator is None else orchestrator
    result = PlanStepOrchestrationComposer(
        context_materializer=wp033,
        orchestrator=recorder,
    ).compose(
        plan,
        run,
        "a",
        candidates=candidates,
        budget=budget,
        uncertainties=uncertainties,
        created_at=CONTEXT_CREATED,
        availability=availability,
    )
    return result, wp033, recorder


def test_public_api_constructor_injection_and_signature() -> None:
    assert issubclass(
        PlanStepOrchestrationInvariantError,
        PlanStepOrchestrationError,
    )
    signature = inspect.signature(PlanStepOrchestrationComposer.compose)
    assert tuple(signature.parameters) == (
        "self",
        "plan",
        "run",
        "step_id",
        "candidates",
        "budget",
        "uncertainties",
        "created_at",
        "availability",
    )
    wp033 = RecordingWP033(wp033_for(StepOutcomeStatus.INDETERMINATE))
    orchestrator = RecordingOrchestrator()
    assert isinstance(
        PlanStepOrchestrationComposer(
            context_materializer=wp033,
            orchestrator=orchestrator,
        ),
        PlanStepOrchestrationComposer,
    )
    with pytest.raises(TypeError, match="context_materializer"):
        PlanStepOrchestrationComposer(context_materializer=cast(Any, object()))
    with pytest.raises(TypeError, match="orchestrator"):
        PlanStepOrchestrationComposer(orchestrator=cast(Any, object()))


@pytest.mark.parametrize(
    ("position", "invalid"),
    [
        (0, object()),
        (1, object()),
        (2, 7),
        (3, []),
        (3, (object(),)),
        (4, object()),
        (5, []),
        (5, (object(),)),
        (6, object()),
        (7, object()),
    ],
)
def test_invalid_inputs_fail_before_wp033(position: int, invalid: object) -> None:
    plan = make_plan(step("a"))
    run = new_run(plan)
    wp033 = RecordingWP033(wp033_for(StepOutcomeStatus.INDETERMINATE))
    orchestrator = RecordingOrchestrator()
    values: list[object] = [
        plan,
        run,
        "a",
        (),
        ContextBudget(0),
        (),
        CONTEXT_CREATED,
        HandlerAvailability(),
    ]
    values[position] = invalid

    with pytest.raises(TypeError):
        PlanStepOrchestrationComposer(
            context_materializer=wp033,
            orchestrator=orchestrator,
        ).compose(
            cast(Plan, values[0]),
            cast(PlanRun, values[1]),
            cast(str, values[2]),
            candidates=cast(tuple[ContextCandidate, ...], values[3]),
            budget=cast(ContextBudget, values[4]),
            uncertainties=cast(tuple[ContextUncertainty, ...], values[5]),
            created_at=cast(datetime, values[6]),
            availability=cast(HandlerAvailability, values[7]),
        )
    assert wp033.calls == []
    assert orchestrator.calls == []


def test_no_selected_work_calls_wp033_once_and_never_orchestrates() -> None:
    plan = make_plan(step("a"))
    run = active_with_evidence(plan, new_run(plan))
    delegated = wp033_for(StepOutcomeStatus.INDETERMINATE).materialize(
        plan,
        run,
        "a",
        candidates=(),
        budget=ContextBudget(0),
        created_at=CONTEXT_CREATED,
    )
    assert delegated.work_subject is None
    assert delegated.context_snapshot is None
    wp033 = RecordingWP033(wp033_for(StepOutcomeStatus.INDETERMINATE), forced=delegated)
    orchestrator = RecordingOrchestrator()
    before = run.to_data()

    result = PlanStepOrchestrationComposer(
        context_materializer=wp033,
        orchestrator=orchestrator,
    ).compose(
        plan,
        run,
        "a",
        candidates=(),
        budget=ContextBudget(0),
        created_at=CONTEXT_CREATED,
        availability=HandlerAvailability(capability=True),
    )

    assert len(wp033.calls) == 1
    assert wp033.calls[0][:3] == (plan, run, "a")
    assert orchestrator.calls == []
    assert result.orchestration_decision is None
    assert result.assessment is delegated.assessment
    assert result.transition_decision is delegated.transition_decision
    assert run.to_data() == before


@pytest.mark.parametrize(
    ("handling", "expected_status"),
    [
        (None, StepHandlingPreparationStatus.HANDLING_UNSPECIFIED),
        (HandlingKind.SYSTEM, StepHandlingPreparationStatus.INSUFFICIENT_DETAIL),
        (HandlingKind.MEMORY, StepHandlingPreparationStatus.INSUFFICIENT_DETAIL),
        (
            HandlingKind.INTELLIGENCE,
            StepHandlingPreparationStatus.INSUFFICIENT_DETAIL,
        ),
    ],
)
def test_nonprepared_selected_work_stops_without_orchestration(
    handling: HandlingKind | None,
    expected_status: StepHandlingPreparationStatus,
) -> None:
    plan, run, delegated = canonical_wp033(handling=handling)
    assert delegated.handling_preparation is not None
    assert delegated.handling_preparation.status is expected_status

    result, wp033, orchestrator = compose_from(plan, run, delegated)

    assert len(wp033.calls) == 1
    assert orchestrator.calls == []
    assert result.orchestration_decision is None
    assert result.work_subject is delegated.work_subject
    assert result.context_snapshot is delegated.context_snapshot
    assert result.handling_preparation is delegated.handling_preparation


def test_prepared_delegates_exact_artifacts_once_and_stops() -> None:
    candidates = (candidate(),)
    budget = ContextBudget(1)
    plan, run, delegated = canonical_wp033(candidates=candidates, budget=budget)
    preparation = delegated.handling_preparation
    assert preparation is not None
    assert preparation.status is StepHandlingPreparationStatus.PREPARED
    need = preparation.handling_need
    assert need is not None
    availability = HandlerAvailability(capability=True)

    result, wp033, orchestrator = compose_from(
        plan,
        run,
        delegated,
        candidates=candidates,
        budget=budget,
        availability=availability,
    )

    assert len(wp033.calls) == 1
    assert wp033.calls[0] == (
        plan,
        run,
        "a",
        candidates,
        budget,
        (),
        CONTEXT_CREATED,
    )
    assert len(orchestrator.calls) == 1
    orchestration_input = orchestrator.calls[0]
    assert orchestration_input.subject is delegated.work_subject
    assert orchestration_input.context is delegated.context_snapshot
    assert orchestration_input.needs == (need,)
    assert orchestration_input.needs[0] is need
    assert orchestration_input.availability is availability
    assert result.orchestration_decision is not None
    assert result.orchestration_decision is orchestrator.results[0]
    assert result.orchestration_decision.subject_id == delegated.work_subject.subject_id
    assert (
        result.orchestration_decision.context_snapshot_id
        == delegated.context_snapshot.snapshot_id
    )
    assert result.orchestration_decision.target is OrchestrationTarget.CAPABILITY

    assert result.assessment is delegated.assessment
    assert result.transition_decision is delegated.transition_decision
    assert result.progress_update is delegated.progress_update
    assert result.advancement_result is delegated.advancement_result
    assert result.handling_preparation is delegated.handling_preparation
    assert result.work_subject is delegated.work_subject
    assert result.context_snapshot is delegated.context_snapshot


def test_prepared_unavailable_handler_still_returns_unsatisfied_decision() -> None:
    plan, run, delegated = canonical_wp033()

    result, _, orchestrator = compose_from(
        plan,
        run,
        delegated,
        availability=HandlerAvailability(),
    )

    assert len(orchestrator.calls) == 1
    decision = result.orchestration_decision
    assert decision is not None
    assert decision.target is OrchestrationTarget.UNSATISFIED
    assert decision.reason is OrchestrationReason.NO_ADMISSIBLE_HANDLER
    preparation = delegated.handling_preparation
    assert preparation is not None
    assert decision.requirement is preparation.handling_need


def test_generic_capability_need_is_preserved_without_identifier_or_blockers() -> None:
    plan, run, delegated = canonical_wp033()
    preparation = delegated.handling_preparation
    assert preparation is not None
    need = preparation.handling_need
    assert need is not None
    assert need.kind is HandlingKind.CAPABILITY
    assert need.capability_id is None
    assert need.blockers == ()

    result, _, orchestrator = compose_from(plan, run, delegated)

    supplied = orchestrator.calls[0].needs[0]
    assert supplied is need
    assert supplied.capability_id is None
    assert supplied.blockers == ()
    assert result.orchestration_decision is not None
    assert result.orchestration_decision.requirement is need


def context_case(
    status: ResolutionStatus,
) -> tuple[
    tuple[ContextCandidate, ...],
    ContextBudget,
    tuple[ContextUncertainty, ...],
]:
    first = candidate("first", "one", key="first_key")
    second = candidate("second", "two", key="second_key")
    if status is ResolutionStatus.PARTIAL:
        return (
            (first,),
            ContextBudget(1),
            (
                ContextUncertainty(
                    "task",
                    "missing_detail",
                    GLOBAL,
                    UncertaintyReason.MISSING,
                ),
            ),
        )
    if status is ResolutionStatus.AMBIGUOUS:
        return (
            (first, second),
            ContextBudget(2),
            (
                ContextUncertainty(
                    "task",
                    "choice",
                    GLOBAL,
                    UncertaintyReason.MULTIPLE_PLAUSIBLE,
                    ("first", "second"),
                ),
            ),
        )
    return (
        (
            candidate("first", "one", key="shared"),
            candidate("second", "two", key="shared"),
        ),
        ContextBudget(2),
        (),
    )


@pytest.mark.parametrize(
    "status",
    [
        ResolutionStatus.PARTIAL,
        ResolutionStatus.AMBIGUOUS,
        ResolutionStatus.CONFLICTED,
    ],
)
def test_context_status_does_not_synthesize_blockers_or_clarification(
    status: ResolutionStatus,
) -> None:
    candidates, budget, uncertainties = context_case(status)
    plan, run, delegated = canonical_wp033(
        candidates=candidates,
        budget=budget,
        uncertainties=uncertainties,
    )
    assert delegated.context_snapshot is not None
    assert delegated.context_snapshot.status is status
    preparation = delegated.handling_preparation
    assert preparation is not None
    need = preparation.handling_need
    assert need is not None
    assert need.blockers == ()

    result, _, orchestrator = compose_from(
        plan,
        run,
        delegated,
        candidates=candidates,
        budget=budget,
        uncertainties=uncertainties,
    )

    assert len(orchestrator.calls) == 1
    assert orchestrator.calls[0].needs[0] is need
    assert orchestrator.calls[0].needs[0].blockers == ()
    assert result.orchestration_decision is not None
    assert result.orchestration_decision.target is OrchestrationTarget.CAPABILITY
    assert result.orchestration_decision.context_references == ()


def test_decision_is_bound_to_exact_snapshot_not_only_subject() -> None:
    plan, run, delegated = canonical_wp033()
    result, _, _ = compose_from(plan, run, delegated)
    decision = result.orchestration_decision
    subject = delegated.work_subject
    context = delegated.context_snapshot
    assert decision is not None
    assert subject is not None
    assert context is not None
    validate_orchestration_decision_current(decision, subject, context)

    replacement = ContextEngine().build(
        subject=subject,
        candidates=(),
        budget=context.budget,
        created_at=context.created_at,
    )
    assert replacement.subject is subject
    assert replacement.snapshot_id != context.snapshot_id
    with pytest.raises(StaleOrchestrationDecisionError):
        validate_orchestration_decision_current(decision, subject, replacement)


@pytest.mark.parametrize("mismatch", ["stale", "missing_need", "blockers"])
def test_malformed_prepared_handling_fails_before_wp017(mismatch: str) -> None:
    plan, run, delegated = canonical_wp033()
    preparation = delegated.handling_preparation
    assert preparation is not None
    need = preparation.handling_need
    assert need is not None
    if mismatch == "stale":
        malformed = unsafe_preparation(
            preparation,
            observed_revision=preparation.observed_revision - 1,
        )
    elif mismatch == "missing_need":
        malformed = unsafe_preparation(preparation, handling_need=None)
    else:
        blocker = ContextBlocker(
            "task",
            "missing_detail",
            GLOBAL,
            ContextBlockerKind.MISSING,
        )
        malformed_need = replace(need, blockers=(blocker,))
        malformed = unsafe_preparation(preparation, handling_need=malformed_need)
    forced = unsafe_wp033_result(delegated, handling_preparation=malformed)
    wp033 = RecordingWP033(wp033_for(StepOutcomeStatus.SATISFIED), forced=forced)
    orchestrator = RecordingOrchestrator()

    with pytest.raises(PlanStepOrchestrationInvariantError):
        PlanStepOrchestrationComposer(
            context_materializer=wp033,
            orchestrator=orchestrator,
        ).compose(
            plan,
            run,
            "a",
            candidates=(),
            budget=ContextBudget(10),
            created_at=CONTEXT_CREATED,
            availability=HandlerAvailability(capability=True),
        )
    assert len(wp033.calls) == 1
    assert orchestrator.calls == []


@pytest.mark.parametrize(
    "mismatch",
    [
        "type",
        "assessment_plan",
        "transition_step",
        "assessment_link",
        "update_shape",
        "update_revision",
        "advancement_source",
        "successor_revision",
        "control_revision",
        "missing_context",
        "context_owner",
        "context_budget",
        "subject_step",
        "preparation_step",
        "preparation_status",
        "context_status",
    ],
)
def test_malformed_wp033_result_fails_before_wp017(mismatch: str) -> None:
    plan, run, delegated = canonical_wp033()
    forced: object = delegated
    if mismatch == "type":
        forced = object()
    elif mismatch == "assessment_plan":
        forced = unsafe_wp033_result(
            delegated,
            assessment=replace(delegated.assessment, plan_id="foreign-plan"),
        )
    elif mismatch == "transition_step":
        forced = unsafe_wp033_result(
            delegated,
            transition_decision=replace(
                delegated.transition_decision,
                step_id="b",
            ),
        )
    elif mismatch == "assessment_link":
        forced = unsafe_wp033_result(
            delegated,
            transition_decision=replace(
                delegated.transition_decision,
                assessment_id="foreign-assessment",
            ),
        )
    elif mismatch == "update_shape":
        forced = unsafe_wp033_result(delegated, advancement_result=None)
    elif mismatch == "update_revision":
        assert delegated.progress_update is not None
        forced = unsafe_wp033_result(
            delegated,
            progress_update=replace(
                delegated.progress_update,
                expected_revision=run.revision + 1,
            ),
        )
    elif mismatch == "advancement_source":
        assert delegated.advancement_result is not None
        forced = unsafe_wp033_result(
            delegated,
            advancement_result=unsafe_advancement(
                delegated.advancement_result,
                source_update_id="foreign-update",
            ),
        )
    elif mismatch == "successor_revision":
        assert delegated.advancement_result is not None
        updated = replace(
            delegated.advancement_result.updated_run,
            revision=run.revision + 2,
        )
        forced = unsafe_wp033_result(
            delegated,
            advancement_result=unsafe_advancement(
                delegated.advancement_result,
                updated_run=updated,
            ),
        )
    elif mismatch == "control_revision":
        assert delegated.advancement_result is not None
        control = replace(
            delegated.advancement_result.control_decision,
            observed_revision=delegated.advancement_result.updated_run.revision + 1,
        )
        forced = unsafe_wp033_result(
            delegated,
            advancement_result=unsafe_advancement(
                delegated.advancement_result,
                control_decision=control,
            ),
        )
    elif mismatch == "missing_context":
        forced = unsafe_wp033_result(delegated, context_snapshot=None)
    elif mismatch == "context_owner":
        assert delegated.context_snapshot is not None
        assert delegated.work_subject is not None
        equivalent = WorkSubject(
            delegated.work_subject.kind,
            delegated.work_subject.reference,
        )
        assert equivalent == delegated.work_subject
        forced = unsafe_wp033_result(
            delegated,
            context_snapshot=replace(
                delegated.context_snapshot,
                subject=equivalent,
            ),
        )
    elif mismatch == "context_budget":
        assert delegated.context_snapshot is not None
        forced = unsafe_wp033_result(
            delegated,
            context_snapshot=replace(
                delegated.context_snapshot,
                budget=ContextBudget(11),
            ),
        )
    elif mismatch == "subject_step":
        assert delegated.work_subject is not None
        reference = delegated.work_subject.reference
        assert isinstance(reference, PlanStepWorkReference)
        foreign = WorkSubject(
            delegated.work_subject.kind,
            replace(reference, step_id="a"),
        )
        forced = unsafe_wp033_result(delegated, work_subject=foreign)
    elif mismatch == "preparation_step":
        assert delegated.handling_preparation is not None
        forced = unsafe_wp033_result(
            delegated,
            handling_preparation=unsafe_preparation(
                delegated.handling_preparation,
                step_id="a",
            ),
        )
    elif mismatch == "preparation_status":
        assert delegated.handling_preparation is not None
        forced = unsafe_wp033_result(
            delegated,
            handling_preparation=unsafe_preparation(
                delegated.handling_preparation,
                status="prepared",
            ),
        )
    else:
        assert delegated.context_snapshot is not None
        malformed_context = object.__new__(ContextSnapshot)
        for name in (
            "snapshot_id",
            "subject",
            "created_at",
            "budget",
            "items",
            "status",
            "uncertainties",
            "conflicts",
            "budget_excluded_ids",
        ):
            value: object = getattr(delegated.context_snapshot, name)
            if name == "status":
                value = "resolved"
            object.__setattr__(malformed_context, name, value)
        forced = unsafe_wp033_result(
            delegated,
            context_snapshot=malformed_context,
        )
    wp033 = RecordingWP033(
        wp033_for(StepOutcomeStatus.SATISFIED),
        forced=forced,
    )
    orchestrator = RecordingOrchestrator()

    with pytest.raises(PlanStepOrchestrationInvariantError):
        PlanStepOrchestrationComposer(
            context_materializer=wp033,
            orchestrator=orchestrator,
        ).compose(
            plan,
            run,
            "a",
            candidates=(),
            budget=ContextBudget(10),
            created_at=CONTEXT_CREATED,
            availability=HandlerAvailability(capability=True),
        )
    assert len(wp033.calls) == 1
    assert orchestrator.calls == []


@pytest.mark.parametrize(
    "mismatch",
    ["type", "subject", "snapshot", "need_ids", "requirement", "time", "blocker"],
)
def test_malformed_wp017_decision_is_rejected(mismatch: str) -> None:
    plan, run, delegated = canonical_wp033()
    subject = delegated.work_subject
    context = delegated.context_snapshot
    preparation = delegated.handling_preparation
    assert subject is not None
    assert context is not None
    assert preparation is not None
    need = preparation.handling_need
    assert need is not None
    canonical = Orchestrator(
        clock=lambda: ORCHESTRATED,
        id_factory=lambda: "canonical-orchestration",
    ).decide(
        OrchestrationInput(
            subject,
            context,
            (need,),
            HandlerAvailability(capability=True),
        )
    )
    forced: object = canonical
    if mismatch == "type":
        forced = object()
    elif mismatch == "subject":
        forced = replace(canonical, subject_id="foreign-subject")
    elif mismatch == "snapshot":
        forced = replace(canonical, context_snapshot_id="foreign-snapshot")
    elif mismatch == "need_ids":
        forced = replace(
            canonical,
            target=OrchestrationTarget.UNSATISFIED,
            reason=OrchestrationReason.NO_ADMISSIBLE_HANDLER,
            need_ids=("foreign-need",),
            requirement=None,
        )
    elif mismatch == "requirement":
        foreign_need = replace(need, capability_id="foreign-capability")
        forced = replace(canonical, requirement=foreign_need)
    elif mismatch == "time":
        forced = replace(
            canonical, created_at=context.created_at - timedelta(seconds=1)
        )
    else:
        blocker = ContextBlocker(
            "task",
            "missing_detail",
            GLOBAL,
            ContextBlockerKind.MISSING,
        )
        forced = OrchestrationDecision(
            decision_id="clarify-decision",
            subject_id=subject.subject_id,
            context_snapshot_id=context.snapshot_id,
            target=OrchestrationTarget.CLARIFY,
            reason=OrchestrationReason.MISSING_REQUIRED_INFORMATION,
            created_at=ORCHESTRATED,
            need_ids=(need.need_id,),
            requirement=need,
            context_references=(blocker,),
        )
    orchestrator = RecordingOrchestrator(forced=forced)

    with pytest.raises(PlanStepOrchestrationInvariantError):
        compose_from(plan, run, delegated, orchestrator=orchestrator)
    assert len(orchestrator.calls) == 1


def test_wp033_failure_propagates_exactly_without_wp017() -> None:
    plan = make_plan(step("a"))
    run = new_run(plan)
    failure = RuntimeError("wp033 failed")
    wp033 = RecordingWP033(
        wp033_for(StepOutcomeStatus.INDETERMINATE),
        error=failure,
    )
    orchestrator = RecordingOrchestrator()

    with pytest.raises(RuntimeError, match="wp033 failed") as raised:
        PlanStepOrchestrationComposer(
            context_materializer=wp033,
            orchestrator=orchestrator,
        ).compose(
            plan,
            run,
            "a",
            candidates=(),
            budget=ContextBudget(0),
            created_at=CONTEXT_CREATED,
            availability=HandlerAvailability(),
        )
    assert raised.value is failure
    assert len(wp033.calls) == 1
    assert orchestrator.calls == []


def test_wp017_failure_propagates_once_without_retry_or_none_conversion() -> None:
    plan, run, delegated = canonical_wp033()
    failure = RuntimeError("wp017 failed")
    orchestrator = RecordingOrchestrator(error=failure)

    with pytest.raises(RuntimeError, match="wp017 failed") as raised:
        compose_from(plan, run, delegated, orchestrator=orchestrator)
    assert raised.value is failure
    assert len(orchestrator.calls) == 1


def test_result_is_immutable_and_serialization_is_deterministic() -> None:
    plan, run, delegated = canonical_wp033()
    result, _, _ = compose_from(plan, run, delegated)
    assert result.orchestration_decision is not None
    first = result.to_data()
    second = result.to_data()
    assert first == second
    encoded = json.loads(json.dumps(first))
    assert encoded["orchestration_decision"]["target"] == "capability"
    assert "orchestration_input" not in encoded
    with pytest.raises(FrozenInstanceError):
        result.orchestration_decision = None  # type: ignore[misc]


def test_result_rejects_invalid_orchestration_existence_shapes() -> None:
    plan, run, prepared = canonical_wp033()
    with pytest.raises(PlanStepOrchestrationInvariantError):
        PlanStepOrchestrationResult(
            prepared.assessment,
            prepared.transition_decision,
            prepared.progress_update,
            prepared.advancement_result,
            prepared.handling_preparation,
            prepared.work_subject,
            prepared.context_snapshot,
            None,
        )

    _, _, unspecified = canonical_wp033(handling=None)
    assert unspecified.handling_preparation is not None
    assert (
        unspecified.handling_preparation.status
        is StepHandlingPreparationStatus.HANDLING_UNSPECIFIED
    )
    decision = cast(
        OrchestrationDecision,
        compose_from(plan, run, prepared)[0].orchestration_decision,
    )
    with pytest.raises(PlanStepOrchestrationInvariantError):
        PlanStepOrchestrationResult(
            unspecified.assessment,
            unspecified.transition_decision,
            unspecified.progress_update,
            unspecified.advancement_result,
            unspecified.handling_preparation,
            unspecified.work_subject,
            unspecified.context_snapshot,
            decision,
        )


def test_repeated_invocation_has_no_hidden_deduplication() -> None:
    plan, run, delegated = canonical_wp033()
    wp033 = RecordingWP033(
        wp033_for(StepOutcomeStatus.SATISFIED),
        forced=delegated,
    )
    orchestrator = RecordingOrchestrator()
    composer = PlanStepOrchestrationComposer(
        context_materializer=wp033,
        orchestrator=orchestrator,
    )

    first = composer.compose(
        plan,
        run,
        "a",
        candidates=(),
        budget=ContextBudget(10),
        created_at=CONTEXT_CREATED,
        availability=HandlerAvailability(capability=True),
    )
    second = composer.compose(
        plan,
        run,
        "a",
        candidates=(),
        budget=ContextBudget(10),
        created_at=CONTEXT_CREATED,
        availability=HandlerAvailability(capability=True),
    )

    assert len(wp033.calls) == len(orchestrator.calls) == 2
    assert first.work_subject is second.work_subject is delegated.work_subject
    assert (
        first.context_snapshot is second.context_snapshot is delegated.context_snapshot
    )
    assert first.orchestration_decision is not None
    assert second.orchestration_decision is not None
    assert (
        first.orchestration_decision.decision_id
        != second.orchestration_decision.decision_id
    )


def test_wp034_has_no_enrichment_discovery_execution_or_lower_authority() -> None:
    import iris.plan_step_orchestration.composer as module

    source = inspect.getsource(module)
    for forbidden in (
        "StepHandlingSpecification",
        "ContextBlocker(",
        "MemoryContextSource",
        "MemoryService",
        "CapabilityRuntime",
        "IntelligenceRuntime",
        "ExecutionCoordinator",
        "PlanStepExecutionBinder",
        "PlanRunReducer",
        "PlanRunController",
        "DeterministicOrchestrationPolicy",
        ".select(",
        "work_subject_from_plan_step",
        "ContextEngine(",
        "PlanStepHandlingPreparer",
        "PlanStepWorkSubjectMaterializer",
        "PlanStepProgressAdvancementComposer",
        "subprocess",
        "socket",
        "open(",
    ):
        assert forbidden not in source
