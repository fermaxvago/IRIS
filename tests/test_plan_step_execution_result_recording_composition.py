"""WP038 bounded post-start PlanStep execution-result recording composition."""

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
from iris.execution import (
    CapabilityExecutionInput,
    ExecutionCoordinator,
    ExecutionFailure,
    ExecutionRequest,
    ExecutionStatus,
    HandlerOutcome,
)
from iris.execution.models import ExecutionInput
from iris.execution_observation import ExecutionObservationAdapter
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
from iris.plan_handling import PlanStepHandlingPreparer
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
from iris.plan_step_execution_binding import PlanStepExecutionBinder
from iris.plan_step_execution_binding_composition import (
    PlanStepExecutionBindingComposer,
)
from iris.plan_step_execution_request_materialization import (
    PlanStepExecutionRequestMaterializer,
)
from iris.plan_step_execution_result_recording import (
    PlanStepExecutionResultRecorder,
    PlanStepExecutionResultRecordingLineageError,
    PlanStepExecutionResultRecordingResult,
)
from iris.plan_step_execution_result_recording_composition import (
    PlanStepExecutionResultRecordingComposer,
    PlanStepExecutionResultRecordingCompositionError,
    PlanStepExecutionResultRecordingCompositionInvariantError,
    PlanStepExecutionResultRecordingCompositionResult,
)
from iris.plan_step_execution_start import (
    PlanStepExecutionInvocationError,
    PlanStepExecutionStartCoordinator,
    PlanStepExecutionStartResult,
)
from iris.plan_step_execution_start_composition import (
    PlanStepExecutionStartComposer,
    PlanStepExecutionStartCompositionError,
    PlanStepExecutionStartCompositionResult,
)
from iris.plan_step_handling_preparation import PlanStepHandlingPreparationComposer
from iris.plan_step_orchestration import PlanStepOrchestrationComposer
from iris.plan_step_progress_advancement import PlanStepProgressAdvancementComposer
from iris.plan_step_progress_update_preparation import (
    PlanStepProgressUpdatePreparer,
)
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
OBSERVED = BASE + timedelta(seconds=206)
PROVENANCE = RunProvenance("test", "wp038")
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
        return "handler.capability.wp038"

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


def make_plan(*steps: PlanStep) -> Plan:
    return Plan("plan-1", "goal-1", (), steps)


def new_run(plan: Plan) -> PlanRun:
    return PlanRunFactory(clock=lambda: BASE, run_id_factory=lambda: "run-1").create(
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


def selected_scenario(
    handling: HandlingKind | None = HandlingKind.CAPABILITY,
) -> tuple[Plan, PlanRun]:
    plan = make_plan(step("a"), step("b", depends_on=("a",), handling=handling))
    run = transition(plan, new_run(plan), "a", StepProgressState.ACTIVE)
    observation = PlanObservation(
        observation_id="evidence-a",
        run_id=run.run_id,
        step_id="a",
        source="test",
        source_reference="source-evidence-a",
        observed_at=run.updated_at + timedelta(seconds=1),
        kind="verification",
        data={"verified": True},
    )
    run = PlanRunReducer().apply(
        plan,
        run,
        RecordObservationUpdate(
            update_id="record-evidence-a",
            run_id=run.run_id,
            expected_revision=run.revision,
            updated_at=observation.observed_at,
            provenance=PROVENANCE,
            observation=observation,
        ),
    )
    return plan, run


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


def binding_composer(status: StepOutcomeStatus) -> PlanStepExecutionBindingComposer:
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


def start_coordinator(
    handler: CapabilityHandler | None,
) -> PlanStepExecutionStartCoordinator:
    handlers = () if handler is None else (handler,)
    return PlanStepExecutionStartCoordinator(
        ExecutionCoordinator(
            handlers,
            clock=ClockSequence(ATTEMPT_STARTED, START_BOUNDARY, COMPLETED),
        ),
        update_id_factory=lambda: "activation-update-1",
    )


def capability_input() -> CapabilityExecutionInput:
    return CapabilityExecutionInput(
        CapabilityInput(payload={"command": "continue"}, metadata={"source": "test"})
    )


def canonical_wp037(
    *,
    handling: HandlingKind | None = HandlingKind.CAPABILITY,
    outcome: HandlerOutcome | None = None,
    handler_available: bool = True,
    assessment_status: StepOutcomeStatus = StepOutcomeStatus.SATISFIED,
) -> tuple[Plan, PlanRun, PlanStepExecutionStartCompositionResult]:
    plan, run = selected_scenario(handling)
    handler = None
    if handler_available:
        handler = CapabilityHandler(
            outcome=HandlerOutcome(ExecutionStatus.SUCCEEDED)
            if outcome is None
            else outcome
        )
    result = PlanStepExecutionStartComposer(
        binding_composer=binding_composer(assessment_status),
        start_coordinator=start_coordinator(handler),
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
    return plan, run, result


def deterministic_recorder() -> PlanStepExecutionResultRecorder:
    return PlanStepExecutionResultRecorder(
        observation_adapter=ExecutionObservationAdapter(
            clock=lambda: OBSERVED,
            observation_id_factory=lambda: "execution-observation-1",
        ),
        update_id_factory=lambda: "record-execution-update-1",
    )


class RecordingWP037(PlanStepExecutionStartComposer):
    def __init__(
        self,
        delegate: PlanStepExecutionStartComposer,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__(start_coordinator=start_coordinator(None))
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
        execution_input: ExecutionInput | None = None,
    ) -> PlanStepExecutionStartCompositionResult:
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
            return cast(PlanStepExecutionStartCompositionResult, self.forced)
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


class RecordingWP026(PlanStepExecutionResultRecorder):
    def __init__(
        self,
        delegate: PlanStepExecutionResultRecorder,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__()
        self.delegate = delegate
        self.forced = forced
        self.error = error
        self.calls: list[tuple[Plan, PlanRun, PlanStepExecutionStartResult]] = []

    def record(
        self,
        plan: Plan,
        run: PlanRun,
        start_result: PlanStepExecutionStartResult,
    ) -> PlanStepExecutionResultRecordingResult:
        self.calls.append((plan, run, start_result))
        if self.error is not None:
            raise self.error
        if self.forced is not None:
            return cast(PlanStepExecutionResultRecordingResult, self.forced)
        return self.delegate.record(plan, run, start_result)


def real_start_composer(
    handler: CapabilityHandler | None,
    *,
    handling: HandlingKind | None = HandlingKind.CAPABILITY,
) -> PlanStepExecutionStartComposer:
    return PlanStepExecutionStartComposer(
        binding_composer=binding_composer(StepOutcomeStatus.SATISFIED),
        start_coordinator=start_coordinator(handler),
    )


def compose_from(
    plan: Plan,
    run: PlanRun,
    delegated: PlanStepExecutionStartCompositionResult,
    *,
    recorder: RecordingWP026 | None = None,
    execution_input: CapabilityExecutionInput | None = None,
) -> tuple[
    PlanStepExecutionResultRecordingCompositionResult,
    RecordingWP037,
    RecordingWP026,
]:
    wp037 = RecordingWP037(real_start_composer(None), forced=delegated)
    wp026 = RecordingWP026(deterministic_recorder()) if recorder is None else recorder
    supplied_input = capability_input() if execution_input is None else execution_input
    result = PlanStepExecutionResultRecordingComposer(
        start_composer=wp037,
        result_recorder=wp026,
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
    return result, wp037, wp026


def unsafe_clone(artifact: T, **changes: object) -> T:
    result = object.__new__(type(artifact))
    for item in fields(cast(Any, artifact)):
        object.__setattr__(
            result,
            item.name,
            changes.get(item.name, getattr(artifact, item.name)),
        )
    return result


def selected_state(run: PlanRun, step_id: str = "b") -> StepProgressState:
    return next(item.state for item in run.step_progress if item.step_id == step_id)


def test_public_api_constructor_and_signature() -> None:
    assert issubclass(
        PlanStepExecutionResultRecordingCompositionInvariantError,
        PlanStepExecutionResultRecordingCompositionError,
    )
    signature = inspect.signature(PlanStepExecutionResultRecordingComposer.compose)
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
    with pytest.raises(TypeError, match="start_composer"):
        PlanStepExecutionResultRecordingComposer()  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="start_composer"):
        PlanStepExecutionResultRecordingComposer(start_composer=cast(Any, object()))
    with pytest.raises(TypeError, match="result_recorder"):
        PlanStepExecutionResultRecordingComposer(
            start_composer=real_start_composer(None),
            result_recorder=cast(Any, object()),
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
def test_invalid_inputs_fail_before_wp037(position: int, invalid: object) -> None:
    plan, run = selected_scenario()
    wp037 = RecordingWP037(real_start_composer(None))
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
        PlanStepExecutionResultRecordingComposer(start_composer=wp037).compose(
            cast(Plan, values[0]),
            cast(PlanRun, values[1]),
            cast(str, values[2]),
            candidates=cast(tuple[ContextCandidate, ...], values[3]),
            budget=cast(ContextBudget, values[4]),
            uncertainties=cast(tuple[ContextUncertainty, ...], values[5]),
            created_at=cast(datetime, values[6]),
            availability=cast(HandlerAvailability, values[7]),
        )
    assert wp037.calls == []


@pytest.mark.parametrize("handling", [None, HandlingKind.SYSTEM])
def test_no_start_calls_wp037_once_and_wp026_zero(
    handling: HandlingKind | None,
) -> None:
    plan, run, delegated = canonical_wp037(handling=handling)
    assert delegated.execution_start_result is None
    result, wp037, wp026 = compose_from(plan, run, delegated)
    assert len(wp037.calls) == 1
    assert wp026.calls == []
    assert result.execution_recording_result is None
    assert result.execution_start_result is None
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
        "execution_start_result",
    ):
        assert getattr(result, name) is getattr(delegated, name)


def test_exact_inputs_are_forwarded_to_wp037_once() -> None:
    plan, run, delegated = canonical_wp037(handling=None)
    operation_input = capability_input()
    _, wp037, _ = compose_from(plan, run, delegated, execution_input=operation_input)
    assert wp037.calls == [
        (
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
    ]


def test_no_start_still_rejects_malformed_advancement_before_wp026() -> None:
    plan, run, delegated = canonical_wp037(handling=None)
    assert delegated.execution_start_result is None
    assert delegated.advancement_result is not None
    malformed = unsafe_clone(
        delegated,
        advancement_result=unsafe_clone(
            delegated.advancement_result,
            updated_run=unsafe_clone(
                delegated.advancement_result.updated_run,
                revision=run.revision + 5,
            ),
        ),
    )
    wp037 = RecordingWP037(real_start_composer(None), forced=malformed)
    wp026 = RecordingWP026(deterministic_recorder())
    with pytest.raises(PlanStepExecutionResultRecordingCompositionInvariantError):
        PlanStepExecutionResultRecordingComposer(
            start_composer=wp037,
            result_recorder=wp026,
        ).compose(
            plan,
            run,
            "a",
            candidates=(),
            budget=BUDGET,
            created_at=CONTEXT_CREATED,
            availability=CAPABILITY_AVAILABLE,
        )
    assert wp026.calls == []


def test_handler_unavailable_records_against_exact_pre_activation_run() -> None:
    plan, source_run, delegated = canonical_wp037(handler_available=False)
    start = delegated.execution_start_result
    advancement = delegated.advancement_result
    assert start is not None and start.active_run is None
    assert advancement is not None
    pre_activation = advancement.updated_run
    result, _, wp026 = compose_from(plan, source_run, delegated)
    assert wp026.calls == [(plan, pre_activation, start)]
    recording = result.execution_recording_result
    assert recording is not None
    assert recording.recorded_from_revision == pre_activation.revision
    assert recording.recorded_run.revision == pre_activation.revision + 1
    assert selected_state(pre_activation) is StepProgressState.NOT_STARTED
    assert selected_state(recording.recorded_run) is StepProgressState.NOT_STARTED
    assert recording.observation.source_reference == start.execution_id
    assert recording.observation.data["status"] == ExecutionStatus.REJECTED.value
    assert source_run.revision + 1 == pre_activation.revision
    assert recording.recorded_run.revision == source_run.revision + 2


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (HandlerOutcome(ExecutionStatus.SUCCEEDED), ExecutionStatus.SUCCEEDED),
        (
            HandlerOutcome(
                ExecutionStatus.FAILED,
                failure=ExecutionFailure("handler_failed", "handler failed"),
            ),
            ExecutionStatus.FAILED,
        ),
        (
            HandlerOutcome(
                ExecutionStatus.REJECTED,
                failure=ExecutionFailure("handler_rejected", "handler rejected"),
            ),
            ExecutionStatus.REJECTED,
        ),
    ],
)
def test_all_invoked_statuses_record_exact_active_run_without_progress_mapping(
    outcome: HandlerOutcome,
    expected: ExecutionStatus,
) -> None:
    plan, source_run, delegated = canonical_wp037(outcome=outcome)
    start = delegated.execution_start_result
    advancement = delegated.advancement_result
    assert start is not None and start.active_run is not None
    assert advancement is not None
    active_run = start.active_run
    result, _, wp026 = compose_from(plan, source_run, delegated)
    assert wp026.calls == [(plan, active_run, start)]
    recording = result.execution_recording_result
    assert recording is not None
    assert recording.observation.data["status"] == expected.value
    assert selected_state(active_run) is StepProgressState.ACTIVE
    assert selected_state(recording.recorded_run) is StepProgressState.ACTIVE
    assert recording.recorded_run.step_progress == active_run.step_progress
    assert active_run.revision == advancement.updated_run.revision + 1
    assert recording.recorded_run.revision == active_run.revision + 1
    assert recording.recorded_run.revision == source_run.revision + 3


def test_processed_step_a_records_fresh_selected_step_b() -> None:
    plan, source_run, delegated = canonical_wp037()
    assert delegated.assessment.step_id == "a"
    assert delegated.execution_request is not None
    assert delegated.execution_binding is not None
    assert delegated.execution_start_result is not None
    result, _, _ = compose_from(plan, source_run, delegated)
    recording = result.execution_recording_result
    assert delegated.execution_request.subject.reference.step_id == "b"  # type: ignore[union-attr]
    assert delegated.execution_binding.step_id == "b"
    assert delegated.execution_start_result.step_id == "b"
    assert recording is not None
    assert recording.step_id == "b"
    assert recording.observation.step_id == "b"


def test_wp037_error_propagates_unchanged_before_wp026() -> None:
    plan, run = selected_scenario()
    error = PlanStepExecutionStartCompositionError("delegated start failure")
    wp037 = RecordingWP037(real_start_composer(None), error=error)
    wp026 = RecordingWP026(deterministic_recorder())
    with pytest.raises(PlanStepExecutionStartCompositionError) as caught:
        PlanStepExecutionResultRecordingComposer(
            start_composer=wp037,
            result_recorder=wp026,
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
    assert len(wp037.calls) == 1
    assert wp026.calls == []


def test_post_active_invocation_error_propagates_without_recording() -> None:
    plan, run, canonical = canonical_wp037()
    assert canonical.execution_start_result is not None
    assert canonical.execution_start_result.active_run is not None
    error = PlanStepExecutionInvocationError(
        "handler exploded",
        active_run=canonical.execution_start_result.active_run,
        activation_update_id=canonical.execution_start_result.activation_update_id
        or "missing",
        execution_id=canonical.execution_start_result.execution_id,
    )
    wp037 = RecordingWP037(real_start_composer(None), error=error)
    wp026 = RecordingWP026(deterministic_recorder())
    with pytest.raises(PlanStepExecutionInvocationError) as caught:
        PlanStepExecutionResultRecordingComposer(
            start_composer=wp037,
            result_recorder=wp026,
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
    assert caught.value.active_run is canonical.execution_start_result.active_run
    assert caught.value.activation_update_id == "activation-update-1"
    assert caught.value.execution_id == "execution-1"
    assert wp026.calls == []


def test_wp026_failure_propagates_without_retry_or_success_result() -> None:
    plan, run, delegated = canonical_wp037()
    error = PlanStepExecutionResultRecordingLineageError("recording rejected")
    recorder = RecordingWP026(deterministic_recorder(), error=error)
    with pytest.raises(PlanStepExecutionResultRecordingLineageError) as caught:
        compose_from(plan, run, delegated, recorder=recorder)
    assert caught.value is error
    assert len(recorder.calls) == 1


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_type",
        "foreign_source",
        "presence_mismatch",
        "wrong_successor_revision",
        "wrong_start_step",
        "wrong_start_execution",
    ],
)
def test_malformed_wp037_output_fails_before_wp026(mutation: str) -> None:
    plan, run, delegated = canonical_wp037()
    malformed: object = delegated
    if mutation == "wrong_type":
        malformed = object()
    elif mutation == "foreign_source":
        malformed = unsafe_clone(
            delegated,
            assessment=unsafe_clone(delegated.assessment, plan_id="foreign-plan"),
        )
    elif mutation == "presence_mismatch":
        malformed = unsafe_clone(delegated, execution_binding=None)
    elif mutation == "wrong_successor_revision":
        assert delegated.advancement_result is not None
        malformed = unsafe_clone(
            delegated,
            advancement_result=unsafe_clone(
                delegated.advancement_result,
                updated_run=unsafe_clone(
                    delegated.advancement_result.updated_run,
                    revision=run.revision + 5,
                ),
            ),
        )
    elif mutation == "wrong_start_step":
        assert delegated.execution_start_result is not None
        malformed = unsafe_clone(
            delegated,
            execution_start_result=unsafe_clone(
                delegated.execution_start_result, step_id="a"
            ),
        )
    else:
        assert delegated.execution_start_result is not None
        malformed = unsafe_clone(
            delegated,
            execution_start_result=unsafe_clone(
                delegated.execution_start_result, execution_id="foreign-execution"
            ),
        )
    wp037 = RecordingWP037(real_start_composer(None), forced=malformed)
    wp026 = RecordingWP026(deterministic_recorder())
    with pytest.raises(PlanStepExecutionResultRecordingCompositionInvariantError):
        PlanStepExecutionResultRecordingComposer(
            start_composer=wp037,
            result_recorder=wp026,
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
    assert wp026.calls == []


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_type",
        "foreign_plan",
        "wrong_revision",
        "wrong_step",
        "wrong_execution",
        "wrong_observation_source",
        "mutated_progress",
        "extra_observation",
    ],
)
def test_malformed_wp026_output_becomes_wp038_invariant(mutation: str) -> None:
    plan, run, delegated = canonical_wp037()
    start = delegated.execution_start_result
    assert start is not None and start.active_run is not None
    canonical = deterministic_recorder().record(plan, start.active_run, start)
    malformed: object = canonical
    if mutation == "wrong_type":
        malformed = object()
    elif mutation == "foreign_plan":
        malformed = unsafe_clone(canonical, plan_id="foreign-plan")
    elif mutation == "wrong_revision":
        malformed = unsafe_clone(
            canonical, recorded_from_revision=start.active_run.revision + 1
        )
    elif mutation == "wrong_step":
        malformed = unsafe_clone(canonical, step_id="a")
    elif mutation == "wrong_execution":
        malformed = unsafe_clone(canonical, execution_id="foreign-execution")
    elif mutation == "wrong_observation_source":
        malformed = unsafe_clone(
            canonical,
            observation=unsafe_clone(canonical.observation, source="test"),
        )
    elif mutation == "mutated_progress":
        malformed = unsafe_clone(
            canonical,
            recorded_run=unsafe_clone(
                canonical.recorded_run,
                step_progress=tuple(reversed(canonical.recorded_run.step_progress)),
            ),
        )
    else:
        malformed = unsafe_clone(
            canonical,
            recorded_run=unsafe_clone(
                canonical.recorded_run,
                observations=(
                    *canonical.recorded_run.observations,
                    canonical.observation,
                ),
            ),
        )
    recorder = RecordingWP026(deterministic_recorder(), forced=malformed)
    with pytest.raises(PlanStepExecutionResultRecordingCompositionInvariantError):
        compose_from(plan, run, delegated, recorder=recorder)
    assert len(recorder.calls) == 1


def test_all_wp037_artifacts_and_exact_wp026_result_are_preserved() -> None:
    plan, run, delegated = canonical_wp037()
    start = delegated.execution_start_result
    assert start is not None and start.active_run is not None
    expected = deterministic_recorder().record(plan, start.active_run, start)
    result, _, _ = compose_from(
        plan,
        run,
        delegated,
        recorder=RecordingWP026(deterministic_recorder(), forced=expected),
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
        "execution_start_result",
    ):
        assert getattr(result, name) is getattr(delegated, name)
    assert result.execution_recording_result is expected
    assert result.execution_recording_result.recorded_run is expected.recorded_run
    assert result.execution_recording_result.observation is expected.observation


def test_inputs_are_unchanged_and_result_is_immutable_serializable() -> None:
    plan, run, delegated = canonical_wp037()
    plan_before = plan.to_data()
    run_before = run.to_data()
    delegated_before = delegated.to_data()
    result, _, _ = compose_from(plan, run, delegated)
    assert plan.to_data() == plan_before
    assert run.to_data() == run_before
    assert delegated.to_data() == delegated_before
    assert result.to_data() == result.to_data()
    json.dumps(result.to_data())
    assert result.execution_recording_result is not None
    assert result.to_data()["execution_recording_result"] == (
        result.execution_recording_result.to_data()
    )
    with pytest.raises(FrozenInstanceError):
        result.execution_recording_result = None  # type: ignore[misc]


def test_result_model_rejects_both_presence_mismatches() -> None:
    plan, run, delegated = canonical_wp037()
    start = delegated.execution_start_result
    assert start is not None and start.active_run is not None
    recording = deterministic_recorder().record(plan, start.active_run, start)
    kwargs = {
        item.name: getattr(delegated, item.name)
        for item in fields(delegated)
        if item.name != "execution_start_result"
    }
    with pytest.raises(PlanStepExecutionResultRecordingCompositionInvariantError):
        PlanStepExecutionResultRecordingCompositionResult(
            **kwargs,
            execution_start_result=start,
            execution_recording_result=None,
        )
    _, _, no_start = canonical_wp037(handling=None)
    no_start_kwargs = {
        item.name: getattr(no_start, item.name)
        for item in fields(no_start)
        if item.name != "execution_start_result"
    }
    with pytest.raises(PlanStepExecutionResultRecordingCompositionInvariantError):
        PlanStepExecutionResultRecordingCompositionResult(
            **no_start_kwargs,
            execution_start_result=None,
            execution_recording_result=recording,
        )


def test_wp038_has_no_forbidden_authority_dependencies() -> None:
    source = Path(
        "iris/plan_step_execution_result_recording_composition/composer.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "ExecutionCoordinator",
        "ExecutionObservationAdapter",
        "PlanRunReducer",
        "RecordObservationUpdate",
        "StepOutcomeEvaluator",
        "StepProgressTransitionDecider",
        "PlanRunController",
        "PlanStepExecutionInvocationError",
        "PlanStepEvidenceAssessor",
    ):
        assert forbidden not in source
