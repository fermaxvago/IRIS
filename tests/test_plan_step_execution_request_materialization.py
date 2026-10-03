"""WP035 bounded post-orchestration ExecutionRequest materialization."""

from __future__ import annotations

import inspect
import json
from dataclasses import FrozenInstanceError, dataclass, field, fields
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypeVar, cast

import pytest

from iris.capabilities import CapabilityInput
from iris.context import ContextBudget, ContextCandidate, ContextUncertainty
from iris.execution import CapabilityExecutionInput, ExecutionRequest
from iris.memory import MemoryScope, ScopeKind
from iris.orchestrator import (
    HandlerAvailability,
    HandlingKind,
    OrchestrationTarget,
    Orchestrator,
)
from iris.outcome_assessment import (
    StepOutcomeAssessment,
    StepOutcomeEvaluator,
    StepOutcomeStatus,
)
from iris.plan_handling import PlanStepHandlingPreparer, StepHandlingPreparationStatus
from iris.plan_run_advancement import PlanRunProgressAdvancer
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
from iris.plan_step_context_materialization import PlanStepContextMaterializer
from iris.plan_step_evidence_assessment import PlanStepEvidenceAssessor
from iris.plan_step_evidence_transition import PlanStepEvidenceTransitionComposer
from iris.plan_step_execution_request_materialization import (
    PlanStepExecutionRequestMaterializationError,
    PlanStepExecutionRequestMaterializationInvariantError,
    PlanStepExecutionRequestMaterializationResult,
    PlanStepExecutionRequestMaterializer,
)
from iris.plan_step_handling_preparation import PlanStepHandlingPreparationComposer
from iris.plan_step_orchestration import (
    PlanStepOrchestrationComposer,
    PlanStepOrchestrationResult,
)
from iris.plan_step_progress_advancement import PlanStepProgressAdvancementComposer
from iris.plan_step_progress_update_preparation import PlanStepProgressUpdatePreparer
from iris.plan_step_work_subject_materialization import (
    PlanStepWorkSubjectMaterializer,
)
from iris.planning import Plan, PlanStep
from iris.step_progress_transition import StepProgressTransitionDecider
from iris.step_progress_update_synthesis import StepProgressUpdateSynthesizer

BASE = datetime(2026, 10, 3, tzinfo=UTC)
ASSESSED = BASE + timedelta(seconds=100)
DECIDED = BASE + timedelta(seconds=101)
UPDATED = BASE + timedelta(seconds=102)
CONTEXT_CREATED = BASE + timedelta(seconds=200)
ORCHESTRATED = BASE + timedelta(seconds=201)
REQUESTED = BASE + timedelta(seconds=202)
PROVENANCE = RunProvenance("test", "wp035")
DEFAULT_BUDGET = ContextBudget(0)
CAPABILITY_AVAILABLE = HandlerAvailability(capability=True)
T = TypeVar("T")


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
            updated_at=run.updated_at + timedelta(seconds=1),
            provenance=PROVENANCE,
            step_id=step_id,
            new_state=state,
            evidence_ids=evidence_ids,
        ),
    )


def active_with_evidence(plan: Plan, run: PlanRun) -> PlanRun:
    run = transition(plan, run, "a", StepProgressState.ACTIVE)
    observed_at = run.updated_at + timedelta(seconds=1)
    observation = PlanObservation(
        observation_id="evidence-a",
        run_id=run.run_id,
        step_id="a",
        source="test",
        source_reference="source-evidence-a",
        observed_at=observed_at,
        kind="verification",
        data={"verified": True},
    )
    return PlanRunReducer().apply(
        plan,
        run,
        RecordObservationUpdate(
            update_id="record-evidence-a",
            run_id=run.run_id,
            expected_revision=run.revision,
            updated_at=observed_at,
            provenance=PROVENANCE,
            observation=observation,
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


def wp034_for(status: StepOutcomeStatus) -> PlanStepOrchestrationComposer:
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
    work = PlanStepWorkSubjectMaterializer(handling_preparation_composer=handling)
    context = PlanStepContextMaterializer(work_subject_materializer=work)
    return PlanStepOrchestrationComposer(
        context_materializer=context,
        orchestrator=Orchestrator(
            clock=lambda: ORCHESTRATED,
            id_factory=lambda: "orchestration-decision-1",
        ),
    )


class RecordingWP034(PlanStepOrchestrationComposer):
    def __init__(
        self,
        delegate: PlanStepOrchestrationComposer,
        *,
        forced: object | None = None,
        error: Exception | None = None,
        events: list[str] | None = None,
    ) -> None:
        super().__init__()
        self.delegate = delegate
        self.forced = forced
        self.error = error
        self.events = events
        self.calls: list[tuple[object, ...]] = []

    def compose(
        self,
        plan: Plan,
        run: PlanRun,
        step_id: str,
        *,
        candidates: tuple[ContextCandidate, ...],
        budget: ContextBudget,
        uncertainties: tuple[ContextUncertainty, ...] = (),
        created_at: datetime,
        availability: HandlerAvailability,
    ) -> PlanStepOrchestrationResult:
        self.calls.append(
            (
                plan,
                run,
                step_id,
                candidates,
                budget,
                uncertainties,
                created_at,
                availability,
            )
        )
        if self.events is not None:
            self.events.append("wp034")
        if self.error is not None:
            raise self.error
        if self.forced is not None:
            return cast(PlanStepOrchestrationResult, self.forced)
        return self.delegate.compose(
            plan,
            run,
            step_id,
            candidates=candidates,
            budget=budget,
            uncertainties=uncertainties,
            created_at=created_at,
            availability=availability,
        )


def selected_scenario(
    handling: HandlingKind | None = HandlingKind.CAPABILITY,
) -> tuple[Plan, PlanRun]:
    plan = make_plan(step("a"), step("b", depends_on=("a",), handling=handling))
    return plan, active_with_evidence(plan, new_run(plan))


def canonical_wp034(
    *,
    handling: HandlingKind | None = HandlingKind.CAPABILITY,
    availability: HandlerAvailability = CAPABILITY_AVAILABLE,
    status: StepOutcomeStatus = StepOutcomeStatus.SATISFIED,
) -> tuple[Plan, PlanRun, PlanStepOrchestrationResult]:
    plan, run = selected_scenario(handling)
    result = wp034_for(status).compose(
        plan,
        run,
        "a",
        candidates=(),
        budget=DEFAULT_BUDGET,
        created_at=CONTEXT_CREATED,
        availability=availability,
    )
    return plan, run, result


def unsafe_result(
    source: PlanStepOrchestrationResult,
    **changes: object,
) -> PlanStepOrchestrationResult:
    result = object.__new__(PlanStepOrchestrationResult)
    for name in (
        "assessment",
        "transition_decision",
        "progress_update",
        "advancement_result",
        "handling_preparation",
        "work_subject",
        "context_snapshot",
        "orchestration_decision",
    ):
        object.__setattr__(result, name, changes.get(name, getattr(source, name)))
    return result


def unsafe_clone(source: T, **changes: object) -> T:
    result = object.__new__(type(source))
    for item in fields(cast(Any, source)):
        object.__setattr__(
            result,
            item.name,
            changes.get(item.name, getattr(source, item.name)),
        )
    return result


def materialize_from(
    plan: Plan,
    run: PlanRun,
    delegated: PlanStepOrchestrationResult,
    *,
    execution_input: object = None,
    clock: Any = lambda: REQUESTED,
    id_factory: Any = lambda: "execution-1",
    events: list[str] | None = None,
) -> tuple[
    PlanStepExecutionRequestMaterializationResult,
    RecordingWP034,
]:
    recorder = RecordingWP034(
        wp034_for(StepOutcomeStatus.SATISFIED),
        forced=delegated,
        events=events,
    )
    result = PlanStepExecutionRequestMaterializer(
        orchestration_composer=recorder,
        clock=clock,
        execution_id_factory=id_factory,
    ).materialize(
        plan,
        run,
        "a",
        candidates=(),
        budget=DEFAULT_BUDGET,
        created_at=CONTEXT_CREATED,
        availability=CAPABILITY_AVAILABLE,
        execution_input=cast(Any, execution_input),
    )
    return result, recorder


def capability_input() -> CapabilityExecutionInput:
    return CapabilityExecutionInput(
        CapabilityInput(payload={"command": "continue"}, metadata={"source": "test"})
    )


def test_public_api_signature_and_constructor_injection() -> None:
    assert issubclass(
        PlanStepExecutionRequestMaterializationInvariantError,
        PlanStepExecutionRequestMaterializationError,
    )
    signature = inspect.signature(PlanStepExecutionRequestMaterializer.materialize)
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
        "execution_input",
    )
    with pytest.raises(TypeError, match="orchestration_composer"):
        PlanStepExecutionRequestMaterializer(orchestration_composer=cast(Any, object()))
    with pytest.raises(TypeError, match="clock"):
        PlanStepExecutionRequestMaterializer(clock=cast(Any, object()))
    with pytest.raises(TypeError, match="execution_id_factory"):
        PlanStepExecutionRequestMaterializer(execution_id_factory=cast(Any, object()))


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
def test_invalid_inputs_fail_before_wp034(position: int, invalid: object) -> None:
    plan = make_plan(step("a"))
    run = new_run(plan)
    recorder = RecordingWP034(wp034_for(StepOutcomeStatus.INDETERMINATE))
    values: list[object] = [
        plan,
        run,
        "a",
        (),
        DEFAULT_BUDGET,
        (),
        CONTEXT_CREATED,
        CAPABILITY_AVAILABLE,
    ]
    values[position] = invalid
    with pytest.raises(TypeError):
        PlanStepExecutionRequestMaterializer(
            orchestration_composer=recorder
        ).materialize(
            cast(Plan, values[0]),
            cast(PlanRun, values[1]),
            cast(str, values[2]),
            candidates=cast(tuple[ContextCandidate, ...], values[3]),
            budget=cast(ContextBudget, values[4]),
            uncertainties=cast(tuple[ContextUncertainty, ...], values[5]),
            created_at=cast(datetime, values[6]),
            availability=cast(HandlerAvailability, values[7]),
        )
    assert recorder.calls == []


def test_no_decision_preserves_artifacts_and_does_not_consume_id_or_clock() -> None:
    plan, run, delegated = canonical_wp034(status=StepOutcomeStatus.INDETERMINATE)
    assert delegated.orchestration_decision is None
    id_calls: list[None] = []
    clock_calls: list[None] = []

    def unused_id() -> str:
        id_calls.append(None)
        return "unused"

    def unused_clock() -> datetime:
        clock_calls.append(None)
        return REQUESTED

    result, recorder = materialize_from(
        plan,
        run,
        delegated,
        id_factory=unused_id,
        clock=unused_clock,
    )

    assert len(recorder.calls) == 1
    assert recorder.calls[0][:3] == (plan, run, "a")
    assert result.execution_request is None
    assert id_calls == []
    assert clock_calls == []
    assert result.assessment is delegated.assessment
    assert result.transition_decision is delegated.transition_decision
    assert result.progress_update is delegated.progress_update
    assert result.advancement_result is delegated.advancement_result


@pytest.mark.parametrize(
    ("handling", "expected"),
    [
        (None, StepHandlingPreparationStatus.HANDLING_UNSPECIFIED),
        (HandlingKind.SYSTEM, StepHandlingPreparationStatus.INSUFFICIENT_DETAIL),
        (HandlingKind.MEMORY, StepHandlingPreparationStatus.INSUFFICIENT_DETAIL),
        (HandlingKind.INTELLIGENCE, StepHandlingPreparationStatus.INSUFFICIENT_DETAIL),
    ],
)
def test_nonprepared_selected_work_stops_without_request(
    handling: HandlingKind | None,
    expected: StepHandlingPreparationStatus,
) -> None:
    plan, run, delegated = canonical_wp034(handling=handling)
    assert delegated.handling_preparation is not None
    assert delegated.handling_preparation.status is expected
    result, _ = materialize_from(
        plan,
        run,
        delegated,
        id_factory=lambda: pytest.fail("ID factory must not run"),
        clock=lambda: pytest.fail("request clock must not run"),
    )
    assert result.execution_request is None
    assert result.work_subject is delegated.work_subject
    assert result.context_snapshot is delegated.context_snapshot
    assert result.orchestration_decision is None


def test_capability_request_preserves_exact_artifacts_input_and_call_order() -> None:
    plan, run, delegated = canonical_wp034()
    execution_input = capability_input()
    events: list[str] = []

    def next_id() -> str:
        events.append("id")
        return "execution-1"

    def request_clock() -> datetime:
        events.append("clock")
        return REQUESTED

    result, recorder = materialize_from(
        plan,
        run,
        delegated,
        execution_input=execution_input,
        id_factory=next_id,
        clock=request_clock,
        events=events,
    )

    assert len(recorder.calls) == 1
    assert events == ["wp034", "id", "clock"]
    request = result.execution_request
    assert isinstance(request, ExecutionRequest)
    assert request.subject is delegated.work_subject
    assert request.context is delegated.context_snapshot
    assert request.decision is delegated.orchestration_decision
    assert request.execution_input is execution_input
    assert request.execution_id == "execution-1"
    assert request.execution_id not in {
        request.subject.subject_id,
        request.context.snapshot_id,
        request.decision.decision_id,
    }
    assert result.orchestration_decision is delegated.orchestration_decision
    assert result.execution_request is request


@pytest.mark.parametrize("execution_input", [None, object()])
def test_capability_invalid_or_missing_input_preserves_wp018_rejection(
    execution_input: object,
) -> None:
    plan, run, delegated = canonical_wp034()
    with pytest.raises(TypeError, match="CapabilityExecutionInput"):
        materialize_from(
            plan,
            run,
            delegated,
            execution_input=execution_input,
        )


def test_generic_capability_need_is_not_enriched() -> None:
    plan, run, delegated = canonical_wp034()
    preparation = delegated.handling_preparation
    assert preparation is not None
    need = preparation.handling_need
    assert need is not None
    assert need.capability_id is None
    result, _ = materialize_from(
        plan,
        run,
        delegated,
        execution_input=capability_input(),
    )
    assert result.handling_preparation is preparation
    assert result.handling_preparation.handling_need is need
    assert need.capability_id is None


def test_unsatisfied_decision_materializes_real_terminal_request() -> None:
    plan, run, delegated = canonical_wp034(availability=HandlerAvailability())
    assert delegated.orchestration_decision is not None
    assert delegated.orchestration_decision.target is OrchestrationTarget.UNSATISFIED
    result, _ = materialize_from(plan, run, delegated)
    request = result.execution_request
    assert request is not None
    assert request.decision is delegated.orchestration_decision
    assert request.decision.target is OrchestrationTarget.UNSATISFIED
    assert request.execution_input is None


def test_unsatisfied_non_none_input_preserves_wp018_rejection() -> None:
    plan, run, delegated = canonical_wp034(availability=HandlerAvailability())
    with pytest.raises(ValueError, match="terminal decisions"):
        materialize_from(
            plan,
            run,
            delegated,
            execution_input=capability_input(),
        )


@pytest.mark.parametrize("request_time", [ORCHESTRATED, REQUESTED])
def test_equal_or_later_request_time_is_preserved(request_time: datetime) -> None:
    plan, run, delegated = canonical_wp034()
    result, _ = materialize_from(
        plan,
        run,
        delegated,
        execution_input=capability_input(),
        clock=lambda: request_time,
    )
    assert result.execution_request is not None
    assert result.execution_request.created_at == request_time


def test_request_time_before_decision_is_rejected_without_rewriting() -> None:
    plan, run, delegated = canonical_wp034()
    early = ORCHESTRATED - timedelta(microseconds=1)
    with pytest.raises(ValueError, match="predate"):
        materialize_from(
            plan,
            run,
            delegated,
            execution_input=capability_input(),
            clock=lambda: early,
        )


@pytest.mark.parametrize("collision", ["invalid", "subject", "context", "decision"])
def test_invalid_or_colliding_id_is_rejected_once_without_retry(
    collision: str,
) -> None:
    plan, run, delegated = canonical_wp034()
    calls: list[None] = []
    assert delegated.work_subject is not None
    assert delegated.context_snapshot is not None
    assert delegated.orchestration_decision is not None
    invalid_id = {
        "invalid": " ",
        "subject": delegated.work_subject.subject_id,
        "context": delegated.context_snapshot.snapshot_id,
        "decision": delegated.orchestration_decision.decision_id,
    }[collision]

    def factory() -> str:
        calls.append(None)
        return invalid_id

    with pytest.raises(ValueError):
        materialize_from(
            plan,
            run,
            delegated,
            execution_input=capability_input(),
            id_factory=factory,
        )
    assert len(calls) == 1


def test_wp034_exception_propagates_before_id_and_clock() -> None:
    plan, run = selected_scenario()
    error = RuntimeError("delegated failure")
    recorder = RecordingWP034(wp034_for(StepOutcomeStatus.SATISFIED), error=error)
    with pytest.raises(RuntimeError) as caught:
        PlanStepExecutionRequestMaterializer(
            orchestration_composer=recorder,
            execution_id_factory=lambda: pytest.fail("must not generate ID"),
            clock=lambda: pytest.fail("must not read clock"),
        ).materialize(
            plan,
            run,
            "a",
            candidates=(),
            budget=DEFAULT_BUDGET,
            created_at=CONTEXT_CREATED,
            availability=CAPABILITY_AVAILABLE,
            execution_input=capability_input(),
        )
    assert caught.value is error
    assert len(recorder.calls) == 1


def test_wrong_wp034_result_type_fails_before_id_and_clock() -> None:
    plan, run = selected_scenario()
    recorder = RecordingWP034(wp034_for(StepOutcomeStatus.SATISFIED), forced=object())
    with pytest.raises(
        PlanStepExecutionRequestMaterializationInvariantError,
        match="PlanStepOrchestrationResult",
    ):
        PlanStepExecutionRequestMaterializer(
            orchestration_composer=recorder,
            execution_id_factory=lambda: pytest.fail("must not generate ID"),
            clock=lambda: pytest.fail("must not read clock"),
        ).materialize(
            plan,
            run,
            "a",
            candidates=(),
            budget=DEFAULT_BUDGET,
            created_at=CONTEXT_CREATED,
            availability=CAPABILITY_AVAILABLE,
        )


def test_foreign_source_lineage_fails_before_id_and_clock() -> None:
    plan, run, delegated = canonical_wp034()
    assessment = delegated.assessment
    forged = object.__new__(StepOutcomeAssessment)
    for name in (
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
    ):
        object.__setattr__(
            forged,
            name,
            "foreign-plan" if name == "plan_id" else getattr(assessment, name),
        )
    malformed = unsafe_result(delegated, assessment=forged)
    with pytest.raises(PlanStepExecutionRequestMaterializationInvariantError):
        materialize_from(
            plan,
            run,
            malformed,
            id_factory=lambda: pytest.fail("must not generate ID"),
            clock=lambda: pytest.fail("must not read clock"),
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "advancement_source_update",
        "foreign_context_owner",
        "stale_decision",
        "foreign_need_lineage",
        "stale_preparation",
    ],
)
def test_causally_malformed_wp034_artifacts_fail_before_request(
    mutation: str,
) -> None:
    plan, run, delegated = canonical_wp034()
    changes: dict[str, object] = {}
    if mutation == "advancement_source_update":
        assert delegated.advancement_result is not None
        changes["advancement_result"] = unsafe_clone(
            delegated.advancement_result,
            source_update_id="foreign-update",
        )
    elif mutation == "foreign_context_owner":
        assert delegated.context_snapshot is not None
        changes["context_snapshot"] = unsafe_clone(
            delegated.context_snapshot,
            subject=object(),
        )
    elif mutation == "stale_decision":
        assert delegated.orchestration_decision is not None
        changes["orchestration_decision"] = unsafe_clone(
            delegated.orchestration_decision,
            context_snapshot_id="foreign-context",
        )
    elif mutation == "foreign_need_lineage":
        assert delegated.orchestration_decision is not None
        changes["orchestration_decision"] = unsafe_clone(
            delegated.orchestration_decision,
            need_ids=("foreign-need",),
        )
    else:
        assert delegated.handling_preparation is not None
        changes["handling_preparation"] = unsafe_clone(
            delegated.handling_preparation,
            observed_revision=delegated.handling_preparation.observed_revision - 1,
        )

    malformed = unsafe_result(delegated, **changes)
    with pytest.raises(PlanStepExecutionRequestMaterializationInvariantError):
        materialize_from(
            plan,
            run,
            malformed,
            id_factory=lambda: pytest.fail("must not generate ID"),
            clock=lambda: pytest.fail("must not read clock"),
        )


@pytest.mark.parametrize(
    "field",
    [
        "progress_update",
        "advancement_result",
        "work_subject",
        "context_snapshot",
        "orchestration_decision",
    ],
)
def test_malformed_optional_lineage_fails_before_request(field: str) -> None:
    plan, run, delegated = canonical_wp034()
    malformed = unsafe_result(delegated, **{field: None})
    with pytest.raises(PlanStepExecutionRequestMaterializationInvariantError):
        materialize_from(
            plan,
            run,
            malformed,
            id_factory=lambda: pytest.fail("must not generate ID"),
            clock=lambda: pytest.fail("must not read clock"),
        )


def test_repeated_invocations_create_distinct_requests_without_mutation() -> None:
    plan, run, delegated = canonical_wp034()
    ids = iter(("execution-1", "execution-2"))
    recorder = RecordingWP034(wp034_for(StepOutcomeStatus.SATISFIED), forced=delegated)
    materializer = PlanStepExecutionRequestMaterializer(
        orchestration_composer=recorder,
        clock=lambda: REQUESTED,
        execution_id_factory=lambda: next(ids),
    )
    execution_input = capability_input()
    kwargs = {
        "candidates": (),
        "budget": DEFAULT_BUDGET,
        "created_at": CONTEXT_CREATED,
        "availability": CAPABILITY_AVAILABLE,
        "execution_input": execution_input,
    }
    first = materializer.materialize(plan, run, "a", **kwargs)  # type: ignore[arg-type]
    second = materializer.materialize(plan, run, "a", **kwargs)  # type: ignore[arg-type]
    assert len(recorder.calls) == 2
    assert first.execution_request is not None
    assert second.execution_request is not None
    assert first.execution_request.execution_id == "execution-1"
    assert second.execution_request.execution_id == "execution-2"
    assert first.execution_request is not second.execution_request
    assert first.execution_request.execution_id == "execution-1"


def test_result_is_immutable_and_serialization_is_deterministic() -> None:
    plan, run, delegated = canonical_wp034()
    result, _ = materialize_from(
        plan,
        run,
        delegated,
        execution_input=capability_input(),
    )
    assert result.to_data() == result.to_data()
    json.dumps(result.to_data())
    assert result.to_data()["execution_request"] == result.execution_request.to_trace()  # type: ignore[union-attr]
    with pytest.raises(FrozenInstanceError):
        result.execution_request = None  # type: ignore[misc]


def test_result_model_rejects_request_presence_mismatch_and_foreign_identity() -> None:
    plan, run, delegated = canonical_wp034()
    with pytest.raises(PlanStepExecutionRequestMaterializationInvariantError):
        PlanStepExecutionRequestMaterializationResult(
            assessment=delegated.assessment,
            transition_decision=delegated.transition_decision,
            progress_update=delegated.progress_update,
            advancement_result=delegated.advancement_result,
            handling_preparation=delegated.handling_preparation,
            work_subject=delegated.work_subject,
            context_snapshot=delegated.context_snapshot,
            orchestration_decision=delegated.orchestration_decision,
            execution_request=None,
        )

    valid, _ = materialize_from(
        plan,
        run,
        delegated,
        execution_input=capability_input(),
    )
    request = valid.execution_request
    assert request is not None
    foreign = object.__new__(ExecutionRequest)
    object.__setattr__(foreign, "execution_id", "execution-foreign")
    object.__setattr__(foreign, "subject", object())
    object.__setattr__(foreign, "context", request.context)
    object.__setattr__(foreign, "decision", request.decision)
    object.__setattr__(foreign, "created_at", REQUESTED)
    object.__setattr__(foreign, "execution_input", request.execution_input)
    with pytest.raises(PlanStepExecutionRequestMaterializationInvariantError):
        PlanStepExecutionRequestMaterializationResult(
            assessment=delegated.assessment,
            transition_decision=delegated.transition_decision,
            progress_update=delegated.progress_update,
            advancement_result=delegated.advancement_result,
            handling_preparation=delegated.handling_preparation,
            work_subject=delegated.work_subject,
            context_snapshot=delegated.context_snapshot,
            orchestration_decision=delegated.orchestration_decision,
            execution_request=foreign,
        )


def test_wp035_has_no_forbidden_authority_dependencies() -> None:
    source = Path(
        "iris/plan_step_execution_request_materialization/materializer.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "ExecutionCoordinator",
        "PlanStepExecutionBinder",
        "PlanStepExecutionStarter",
        "PlanRunReducer",
        "PlanRunController",
        "StepHandlingSpecification",
        "ContextBlocker",
    ):
        assert forbidden not in source


def test_execution_input_alias_is_not_added_to_execution_public_exports() -> None:
    import iris.execution as execution

    assert "ExecutionInput" not in execution.__all__
    assert not hasattr(execution, "ExecutionInput")


def test_context_scope_fixture_remains_canonical() -> None:
    assert MemoryScope(ScopeKind.GLOBAL).kind is ScopeKind.GLOBAL
