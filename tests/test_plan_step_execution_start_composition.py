"""WP037 bounded post-binding PlanStep execution-start composition."""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass, field, fields
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypeVar, cast

import pytest

from iris.capabilities import CapabilityInput
from iris.context import ContextBudget, ContextCandidate, ContextUncertainty
from iris.execution import (
    CapabilityExecutionInput,
    ExecutionCoordinator,
    ExecutionFailure,
    ExecutionRequest,
    ExecutionStatus,
    HandlerOutcome,
)
from iris.orchestrator import (
    HandlerAvailability,
    HandlingKind,
    OrchestrationReason,
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
from iris.plan_step_execution_binding import (
    PlanStepExecutionBinder,
    PlanStepExecutionBinding,
    StalePlanStepExecutionBindingError,
)
from iris.plan_step_execution_binding_composition import (
    PlanStepExecutionBindingComposer,
    PlanStepExecutionBindingCompositionError,
    PlanStepExecutionBindingCompositionResult,
)
from iris.plan_step_execution_request_materialization import (
    PlanStepExecutionRequestMaterializer,
)
from iris.plan_step_execution_start import (
    PlanStepExecutionInvocationError,
    PlanStepExecutionStartCoordinator,
    PlanStepExecutionStartResult,
)
from iris.plan_step_execution_start_composition import (
    PlanStepExecutionStartComposer,
    PlanStepExecutionStartCompositionError,
    PlanStepExecutionStartCompositionInvariantError,
    PlanStepExecutionStartCompositionResult,
)
from iris.plan_step_handling_preparation import PlanStepHandlingPreparationComposer
from iris.plan_step_orchestration import PlanStepOrchestrationComposer
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
ATTEMPT_STARTED = BASE + timedelta(seconds=203)
START_BOUNDARY = BASE + timedelta(seconds=204)
COMPLETED = BASE + timedelta(seconds=205)
PROVENANCE = RunProvenance("test", "wp037")
BUDGET = ContextBudget(0)
CAPABILITY_AVAILABLE = HandlerAvailability(capability=True)
T = TypeVar("T")


class ClockSequence:
    def __init__(self, *values: datetime) -> None:
        self._values = iter(values)

    def __call__(self) -> datetime:
        return next(self._values)


@dataclass
class CapabilityHandler:
    outcome: HandlerOutcome = field(
        default_factory=lambda: HandlerOutcome(ExecutionStatus.SUCCEEDED)
    )
    error: Exception | None = None
    calls: list[ExecutionRequest] = field(default_factory=list)

    @property
    def target(self) -> OrchestrationTarget:
        return OrchestrationTarget.CAPABILITY

    @property
    def handler_reference(self) -> str:
        return "handler.capability.recording"

    def execute(self, request: ExecutionRequest) -> HandlerOutcome:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return self.outcome


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

    def evaluate(
        self,
        plan: Plan,
        run: PlanRun,
        canonical_step: PlanStep,
        evidence: tuple[PlanObservation, ...],
    ) -> StepOutcomeAssessment:
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


def wp036_for(status: StepOutcomeStatus) -> PlanStepExecutionBindingComposer:
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
    orchestration = PlanStepOrchestrationComposer(
        context_materializer=context,
        orchestrator=Orchestrator(
            clock=lambda: ORCHESTRATED,
            id_factory=lambda: "orchestration-decision-1",
        ),
    )
    request = PlanStepExecutionRequestMaterializer(
        orchestration_composer=orchestration,
        clock=lambda: REQUESTED,
        execution_id_factory=lambda: "execution-1",
    )
    return PlanStepExecutionBindingComposer(
        request_materializer=request,
        execution_binder=PlanStepExecutionBinder(),
    )


class RecordingWP036(PlanStepExecutionBindingComposer):
    def __init__(
        self,
        delegate: PlanStepExecutionBindingComposer,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__()
        self.delegate = delegate
        self.forced = forced
        self.error = error
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
        execution_input: Any = None,
    ) -> PlanStepExecutionBindingCompositionResult:
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
                execution_input,
            )
        )
        if self.error is not None:
            raise self.error
        if self.forced is not None:
            return cast(PlanStepExecutionBindingCompositionResult, self.forced)
        return self.delegate.compose(
            plan,
            run,
            step_id,
            candidates=candidates,
            budget=budget,
            uncertainties=uncertainties,
            created_at=created_at,
            availability=availability,
            execution_input=execution_input,
        )


class RecordingStartCoordinator(PlanStepExecutionStartCoordinator):
    def __init__(
        self,
        delegate: PlanStepExecutionStartCoordinator,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__(ExecutionCoordinator())
        self.delegate = delegate
        self.forced = forced
        self.error = error
        self.calls: list[tuple[object, ...]] = []

    def start(
        self,
        plan: Plan,
        run: PlanRun,
        binding: PlanStepExecutionBinding,
        execution_request: ExecutionRequest,
    ) -> PlanStepExecutionStartResult:
        self.calls.append((plan, run, binding, execution_request))
        if self.error is not None:
            raise self.error
        if self.forced is not None:
            return cast(PlanStepExecutionStartResult, self.forced)
        return self.delegate.start(plan, run, binding, execution_request)


def start_coordinator(
    handler: CapabilityHandler | None,
    *,
    update_id_factory: Callable[[], str] = lambda: "activation-update-1",
) -> PlanStepExecutionStartCoordinator:
    handlers = () if handler is None else (handler,)
    return PlanStepExecutionStartCoordinator(
        ExecutionCoordinator(
            handlers,
            clock=ClockSequence(ATTEMPT_STARTED, START_BOUNDARY, COMPLETED),
        ),
        update_id_factory=update_id_factory,
    )


def selected_scenario(
    handling: HandlingKind | None = HandlingKind.CAPABILITY,
) -> tuple[Plan, PlanRun]:
    plan = make_plan(step("a"), step("b", depends_on=("a",), handling=handling))
    return plan, active_with_evidence(plan, new_run(plan))


def capability_input() -> CapabilityExecutionInput:
    return CapabilityExecutionInput(
        CapabilityInput(payload={"command": "continue"}, metadata={"source": "test"})
    )


def canonical_wp036(
    *,
    handling: HandlingKind | None = HandlingKind.CAPABILITY,
    status: StepOutcomeStatus = StepOutcomeStatus.SATISFIED,
) -> tuple[Plan, PlanRun, PlanStepExecutionBindingCompositionResult]:
    plan, run = selected_scenario(handling)
    result = wp036_for(status).compose(
        plan,
        run,
        "a",
        candidates=(),
        budget=BUDGET,
        created_at=CONTEXT_CREATED,
        availability=CAPABILITY_AVAILABLE,
        execution_input=capability_input(),
    )
    return plan, run, result


def unsafe_result(
    source: PlanStepExecutionBindingCompositionResult,
    **changes: object,
) -> PlanStepExecutionBindingCompositionResult:
    result = object.__new__(PlanStepExecutionBindingCompositionResult)
    for name in (
        "assessment",
        "transition_decision",
        "progress_update",
        "advancement_result",
        "handling_preparation",
        "work_subject",
        "context_snapshot",
        "orchestration_decision",
        "execution_request",
        "execution_binding",
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


def compose_from(
    plan: Plan,
    run: PlanRun,
    delegated: PlanStepExecutionBindingCompositionResult,
    *,
    coordinator: RecordingStartCoordinator,
    execution_input: CapabilityExecutionInput | None = None,
) -> tuple[
    PlanStepExecutionStartCompositionResult,
    RecordingWP036,
    RecordingStartCoordinator,
]:
    recorder = RecordingWP036(wp036_for(StepOutcomeStatus.SATISFIED), forced=delegated)
    supplied_input = capability_input() if execution_input is None else execution_input
    result = PlanStepExecutionStartComposer(
        binding_composer=recorder,
        start_coordinator=coordinator,
    ).compose(
        plan,
        run,
        "a",
        candidates=(),
        budget=BUDGET,
        created_at=CONTEXT_CREATED,
        availability=CAPABILITY_AVAILABLE,
        execution_input=supplied_input,
    )
    return result, recorder, coordinator


def test_public_api_constructor_and_signature() -> None:
    assert issubclass(
        PlanStepExecutionStartCompositionInvariantError,
        PlanStepExecutionStartCompositionError,
    )
    signature = inspect.signature(PlanStepExecutionStartComposer.compose)
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
    with pytest.raises(TypeError, match="start_coordinator"):
        PlanStepExecutionStartComposer()  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="start_coordinator"):
        PlanStepExecutionStartComposer(start_coordinator=cast(Any, object()))
    with pytest.raises(TypeError, match="binding_composer"):
        PlanStepExecutionStartComposer(
            start_coordinator=start_coordinator(None),
            binding_composer=cast(Any, object()),
        )


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
def test_invalid_inputs_fail_before_wp036(position: int, invalid: object) -> None:
    plan, run = selected_scenario()
    recorder = RecordingWP036(wp036_for(StepOutcomeStatus.SATISFIED))
    values: list[object] = [
        plan,
        run,
        "a",
        (),
        BUDGET,
        (),
        CONTEXT_CREATED,
        CAPABILITY_AVAILABLE,
    ]
    values[position] = invalid
    with pytest.raises(TypeError):
        PlanStepExecutionStartComposer(
            binding_composer=recorder,
            start_coordinator=start_coordinator(None),
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
    assert recorder.calls == []


@pytest.mark.parametrize(
    ("handling", "expected"),
    [
        (None, StepHandlingPreparationStatus.HANDLING_UNSPECIFIED),
        (HandlingKind.SYSTEM, StepHandlingPreparationStatus.INSUFFICIENT_DETAIL),
    ],
)
def test_no_binding_preserves_wp036_and_never_calls_wp025(
    handling: HandlingKind | None,
    expected: StepHandlingPreparationStatus,
) -> None:
    plan, run, delegated = canonical_wp036(handling=handling)
    assert delegated.execution_binding is None
    assert delegated.handling_preparation is not None
    assert delegated.handling_preparation.status is expected
    coordinator = RecordingStartCoordinator(start_coordinator(None))
    operation_input = capability_input()
    result, recorder, recorded_start = compose_from(
        plan,
        run,
        delegated,
        coordinator=coordinator,
        execution_input=operation_input,
    )
    assert len(recorder.calls) == 1
    assert recorder.calls[0] == (
        plan,
        run,
        "a",
        (),
        BUDGET,
        (),
        CONTEXT_CREATED,
        CAPABILITY_AVAILABLE,
        operation_input,
    )
    assert recorded_start.calls == []
    assert result.execution_start_result is None
    assert result.execution_binding is None
    for name in (
        "assessment",
        "transition_decision",
        "progress_update",
        "advancement_result",
        "handling_preparation",
        "work_subject",
        "context_snapshot",
        "orchestration_decision",
        "execution_request",
        "execution_binding",
    ):
        assert getattr(result, name) is getattr(delegated, name)


def test_no_advancement_stops_without_wp025() -> None:
    plan, run, delegated = canonical_wp036(status=StepOutcomeStatus.INDETERMINATE)
    coordinator = RecordingStartCoordinator(start_coordinator(None))
    result, _, _ = compose_from(plan, run, delegated, coordinator=coordinator)
    assert result.execution_start_result is None
    assert coordinator.calls == []


def test_wp036_error_propagates_unchanged_before_wp025() -> None:
    plan, run = selected_scenario()
    error = PlanStepExecutionBindingCompositionError("delegated failure")
    recorder = RecordingWP036(wp036_for(StepOutcomeStatus.SATISFIED), error=error)
    coordinator = RecordingStartCoordinator(start_coordinator(None))
    with pytest.raises(PlanStepExecutionBindingCompositionError) as caught:
        PlanStepExecutionStartComposer(
            binding_composer=recorder,
            start_coordinator=coordinator,
        ).compose(
            plan,
            run,
            "a",
            candidates=(),
            budget=BUDGET,
            created_at=CONTEXT_CREATED,
            availability=CAPABILITY_AVAILABLE,
            execution_input=capability_input(),
        )
    assert caught.value is error
    assert len(recorder.calls) == 1
    assert coordinator.calls == []


def test_wrong_wp036_type_fails_before_wp025() -> None:
    plan, run = selected_scenario()
    recorder = RecordingWP036(wp036_for(StepOutcomeStatus.SATISFIED), forced=object())
    coordinator = RecordingStartCoordinator(start_coordinator(None))
    with pytest.raises(
        PlanStepExecutionStartCompositionInvariantError,
        match="PlanStepExecutionBindingCompositionResult",
    ):
        PlanStepExecutionStartComposer(
            binding_composer=recorder,
            start_coordinator=coordinator,
        ).compose(
            plan,
            run,
            "a",
            candidates=(),
            budget=BUDGET,
            created_at=CONTEXT_CREATED,
            availability=CAPABILITY_AVAILABLE,
        )
    assert coordinator.calls == []


@pytest.mark.parametrize(
    "mutation",
    [
        "foreign_source",
        "wrong_advancement_update",
        "foreign_context_owner",
        "stale_decision",
        "foreign_request_subject",
        "foreign_binding_execution",
        "missing_request",
    ],
)
def test_malformed_wp036_lineage_fails_before_wp025(mutation: str) -> None:
    plan, run, delegated = canonical_wp036()
    changes: dict[str, object] = {}
    if mutation == "foreign_source":
        changes["assessment"] = unsafe_clone(
            delegated.assessment, plan_id="foreign-plan"
        )
    elif mutation == "wrong_advancement_update":
        assert delegated.advancement_result is not None
        changes["advancement_result"] = unsafe_clone(
            delegated.advancement_result, source_update_id="foreign-update"
        )
    elif mutation == "foreign_context_owner":
        assert delegated.context_snapshot is not None
        changes["context_snapshot"] = unsafe_clone(
            delegated.context_snapshot, subject=object()
        )
    elif mutation == "stale_decision":
        assert delegated.orchestration_decision is not None
        changes["orchestration_decision"] = unsafe_clone(
            delegated.orchestration_decision, context_snapshot_id="foreign-context"
        )
    elif mutation == "foreign_request_subject":
        assert delegated.execution_request is not None
        changes["execution_request"] = unsafe_clone(
            delegated.execution_request, subject=object()
        )
    elif mutation == "foreign_binding_execution":
        assert delegated.execution_binding is not None
        changes["execution_binding"] = unsafe_clone(
            delegated.execution_binding, execution_id="foreign-execution"
        )
    else:
        changes["execution_request"] = None
    malformed = unsafe_result(delegated, **changes)
    coordinator = RecordingStartCoordinator(start_coordinator(None))
    with pytest.raises(PlanStepExecutionStartCompositionInvariantError):
        compose_from(plan, run, malformed, coordinator=coordinator)
    assert coordinator.calls == []


def test_binding_present_passes_exact_n_plus_one_lineage_to_wp025() -> None:
    plan, source_run, delegated = canonical_wp036()
    assert delegated.advancement_result is not None
    assert delegated.execution_binding is not None
    assert delegated.execution_request is not None
    pre_activation = delegated.advancement_result.updated_run
    recorder = RecordingStartCoordinator(start_coordinator(CapabilityHandler()))
    result, wp036, recorded_start = compose_from(
        plan, source_run, delegated, coordinator=recorder
    )
    assert len(wp036.calls) == 1
    assert len(recorded_start.calls) == 1
    assert recorded_start.calls[0] == (
        plan,
        pre_activation,
        delegated.execution_binding,
        delegated.execution_request,
    )
    assert recorded_start.calls[0][1] is pre_activation
    assert recorded_start.calls[0][1] is not source_run
    start = result.execution_start_result
    assert start is not None
    assert source_run.revision + 1 == pre_activation.revision
    assert start.source_revision == pre_activation.revision
    assert start.active_run is not None
    assert start.active_run.revision == pre_activation.revision + 1
    assert delegated.assessment.step_id == "a"
    assert delegated.execution_binding.step_id == "b"
    assert start.step_id == "b"


def test_handler_unavailable_preserves_exact_nonactivated_result() -> None:
    plan, run, delegated = canonical_wp036()
    assert delegated.advancement_result is not None
    assert delegated.execution_binding is not None
    assert delegated.execution_request is not None
    expected = start_coordinator(None).start(
        plan,
        delegated.advancement_result.updated_run,
        delegated.execution_binding,
        delegated.execution_request,
    )
    recorder = RecordingStartCoordinator(start_coordinator(None), forced=expected)
    result, _, _ = compose_from(plan, run, delegated, coordinator=recorder)
    start = result.execution_start_result
    assert start is expected
    assert start.active_run is None
    assert start.activation_update_id is None
    assert start.execution_result.status is ExecutionStatus.REJECTED
    assert start.execution_result.handler_reference is None
    assert start.execution_result.started_at == ATTEMPT_STARTED
    assert start.execution_result.failure is not None
    assert start.execution_result.failure.code == "handler_unavailable"
    assert len(recorder.calls) == 1


@pytest.mark.parametrize(
    "outcome",
    [
        HandlerOutcome(ExecutionStatus.SUCCEEDED),
        HandlerOutcome(
            ExecutionStatus.FAILED,
            failure=ExecutionFailure("handler_failed", "handler failed"),
        ),
        HandlerOutcome(
            ExecutionStatus.REJECTED,
            failure=ExecutionFailure("handler_rejected", "handler rejected"),
        ),
    ],
)
def test_all_invoked_statuses_preserve_active_run_and_exact_result(
    outcome: HandlerOutcome,
) -> None:
    plan, source_run, delegated = canonical_wp036()
    handler = CapabilityHandler(outcome=outcome)
    real_start = start_coordinator(handler)
    assert delegated.advancement_result is not None
    assert delegated.execution_binding is not None
    assert delegated.execution_request is not None
    expected = real_start.start(
        plan,
        delegated.advancement_result.updated_run,
        delegated.execution_binding,
        delegated.execution_request,
    )
    recorder = RecordingStartCoordinator(real_start, forced=expected)
    result, _, _ = compose_from(plan, source_run, delegated, coordinator=recorder)
    start = result.execution_start_result
    assert start is expected
    assert start.active_run is not None
    assert start.execution_result.status is outcome.status
    assert start.active_run.revision == start.source_revision + 1
    progress = next(
        item for item in start.active_run.step_progress if item.step_id == "b"
    )
    assert progress.state is StepProgressState.ACTIVE


def test_active_run_preserves_non_target_progress_observations_and_blockers() -> None:
    plan, run, delegated = canonical_wp036()
    assert delegated.advancement_result is not None
    pre_activation = delegated.advancement_result.updated_run
    result, _, _ = compose_from(
        plan,
        run,
        delegated,
        coordinator=RecordingStartCoordinator(start_coordinator(CapabilityHandler())),
    )
    start = result.execution_start_result
    assert start is not None
    assert start.active_run is not None
    active = start.active_run
    assert (active.plan_id, active.run_id, active.goal_id) == (
        pre_activation.plan_id,
        pre_activation.run_id,
        pre_activation.goal_id,
    )
    assert active.revision == pre_activation.revision + 1
    assert tuple(item for item in active.step_progress if item.step_id != "b") == tuple(
        item for item in pre_activation.step_progress if item.step_id != "b"
    )
    assert active.observations == pre_activation.observations
    assert active.blockers == pre_activation.blockers


@pytest.mark.parametrize(
    "mutation",
    [
        "plan_id",
        "run_id",
        "source_revision",
        "step_id",
        "execution_id",
        "subject_id",
        "decision_id",
        "context_snapshot_id",
        "target",
        "decision_reason",
    ],
)
def test_malformed_wp025_result_lineage_becomes_wp037_invariant(
    mutation: str,
) -> None:
    plan, run, delegated = canonical_wp036()
    assert delegated.advancement_result is not None
    assert delegated.execution_binding is not None
    assert delegated.execution_request is not None
    canonical = start_coordinator(CapabilityHandler()).start(
        plan,
        delegated.advancement_result.updated_run,
        delegated.execution_binding,
        delegated.execution_request,
    )
    changes: dict[str, object] = {}
    if mutation in {
        "plan_id",
        "run_id",
        "step_id",
        "execution_id",
    }:
        changes[mutation] = f"foreign-{mutation}"
    elif mutation == "source_revision":
        changes[mutation] = canonical.source_revision + 1
    else:
        execution_changes: dict[str, object] = {}
        if mutation in {
            "subject_id",
            "decision_id",
            "context_snapshot_id",
        }:
            execution_changes[mutation] = f"foreign-{mutation}"
        elif mutation == "target":
            execution_changes[mutation] = OrchestrationTarget.SYSTEM
        else:
            execution_changes[mutation] = OrchestrationReason.NO_ADMISSIBLE_HANDLER
        changes["execution_result"] = unsafe_clone(
            canonical.execution_result, **execution_changes
        )
    malformed = unsafe_clone(canonical, **changes)
    coordinator = RecordingStartCoordinator(
        start_coordinator(CapabilityHandler()), forced=malformed
    )
    with pytest.raises(PlanStepExecutionStartCompositionInvariantError):
        compose_from(plan, run, delegated, coordinator=coordinator)
    assert len(coordinator.calls) == 1


def test_malformed_active_run_content_becomes_wp037_invariant() -> None:
    plan, run, delegated = canonical_wp036()
    assert delegated.advancement_result is not None
    assert delegated.execution_binding is not None
    assert delegated.execution_request is not None
    canonical = start_coordinator(CapabilityHandler()).start(
        plan,
        delegated.advancement_result.updated_run,
        delegated.execution_binding,
        delegated.execution_request,
    )
    assert canonical.active_run is not None
    malformed_run = unsafe_clone(canonical.active_run, observations=())
    malformed = unsafe_clone(canonical, active_run=malformed_run)
    with pytest.raises(PlanStepExecutionStartCompositionInvariantError):
        compose_from(
            plan,
            run,
            delegated,
            coordinator=RecordingStartCoordinator(
                start_coordinator(CapabilityHandler()), forced=malformed
            ),
        )


def test_pre_activation_wp025_error_propagates_unchanged_without_retry() -> None:
    plan, run, delegated = canonical_wp036()
    error = StalePlanStepExecutionBindingError("stale before start")
    coordinator = RecordingStartCoordinator(
        start_coordinator(CapabilityHandler()), error=error
    )
    with pytest.raises(StalePlanStepExecutionBindingError) as caught:
        compose_from(plan, run, delegated, coordinator=coordinator)
    assert caught.value is error
    assert len(coordinator.calls) == 1


def test_post_activation_invocation_error_preserves_active_run_and_propagates() -> None:
    plan, run, delegated = canonical_wp036()
    defect = RuntimeError("handler exploded")
    handler = CapabilityHandler(error=defect)
    coordinator = RecordingStartCoordinator(start_coordinator(handler))
    with pytest.raises(PlanStepExecutionInvocationError) as caught:
        compose_from(plan, run, delegated, coordinator=coordinator)
    error = caught.value
    assert delegated.advancement_result is not None
    assert delegated.execution_request is not None
    assert error.active_run.revision == (
        delegated.advancement_result.updated_run.revision + 1
    )
    progress = next(
        item for item in error.active_run.step_progress if item.step_id == "b"
    )
    assert progress.state is StepProgressState.ACTIVE
    assert error.activation_update_id == "activation-update-1"
    assert error.execution_id == delegated.execution_request.execution_id
    assert error.__cause__ is defect
    assert len(coordinator.calls) == 1
    assert len(handler.calls) == 1


def test_all_wp036_artifacts_and_exact_wp025_result_are_preserved() -> None:
    plan, run, delegated = canonical_wp036()
    assert delegated.advancement_result is not None
    assert delegated.execution_binding is not None
    assert delegated.execution_request is not None
    expected = start_coordinator(CapabilityHandler()).start(
        plan,
        delegated.advancement_result.updated_run,
        delegated.execution_binding,
        delegated.execution_request,
    )
    result, _, _ = compose_from(
        plan,
        run,
        delegated,
        coordinator=RecordingStartCoordinator(
            start_coordinator(CapabilityHandler()), forced=expected
        ),
    )
    for name in (
        "assessment",
        "transition_decision",
        "progress_update",
        "advancement_result",
        "handling_preparation",
        "work_subject",
        "context_snapshot",
        "orchestration_decision",
        "execution_request",
        "execution_binding",
    ):
        assert getattr(result, name) is getattr(delegated, name)
    assert result.execution_start_result is expected


def test_result_is_immutable_serializable_and_rejects_presence_mismatch() -> None:
    plan, run, delegated = canonical_wp036()
    result, _, _ = compose_from(
        plan,
        run,
        delegated,
        coordinator=RecordingStartCoordinator(start_coordinator(CapabilityHandler())),
    )
    assert result.to_data() == result.to_data()
    json.dumps(result.to_data())
    assert result.execution_start_result is not None
    assert result.to_data()["execution_start_result"] == (
        result.execution_start_result.to_data()
    )
    with pytest.raises(FrozenInstanceError):
        result.execution_start_result = None  # type: ignore[misc]
    with pytest.raises(PlanStepExecutionStartCompositionInvariantError):
        PlanStepExecutionStartCompositionResult(
            assessment=delegated.assessment,
            transition_decision=delegated.transition_decision,
            progress_update=delegated.progress_update,
            advancement_result=delegated.advancement_result,
            handling_preparation=delegated.handling_preparation,
            work_subject=delegated.work_subject,
            context_snapshot=delegated.context_snapshot,
            orchestration_decision=delegated.orchestration_decision,
            execution_request=delegated.execution_request,
            execution_binding=delegated.execution_binding,
            execution_start_result=None,
        )

    _, _, no_binding = canonical_wp036(handling=None)
    assert no_binding.execution_binding is None
    assert result.execution_start_result is not None
    with pytest.raises(PlanStepExecutionStartCompositionInvariantError):
        PlanStepExecutionStartCompositionResult(
            assessment=no_binding.assessment,
            transition_decision=no_binding.transition_decision,
            progress_update=no_binding.progress_update,
            advancement_result=no_binding.advancement_result,
            handling_preparation=no_binding.handling_preparation,
            work_subject=no_binding.work_subject,
            context_snapshot=no_binding.context_snapshot,
            orchestration_decision=no_binding.orchestration_decision,
            execution_request=no_binding.execution_request,
            execution_binding=no_binding.execution_binding,
            execution_start_result=result.execution_start_result,
        )


def test_wp037_has_no_forbidden_authority_dependencies() -> None:
    source = Path("iris/plan_step_execution_start_composition/composer.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "ExecutionCoordinator",
        "PlanRunReducer",
        "PlanStepExecutionResultRecorder",
        "ExecutionObservationAdapter",
        "_EXECUTABLE_TARGETS",
        "_TERMINAL_TARGETS",
        "PlanStepExecutionInvocationError",
    ):
        assert forbidden not in source
