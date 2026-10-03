"""WP039 bounded post-recording complete-evidence assessment composition."""

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
from iris.plan_step_evidence_assessment import (
    PlanStepEvidenceAssessmentInvariantError,
    PlanStepEvidenceAssessor,
)
from iris.plan_step_evidence_transition import PlanStepEvidenceTransitionComposer
from iris.plan_step_execution_binding import PlanStepExecutionBinder
from iris.plan_step_execution_binding_composition import (
    PlanStepExecutionBindingComposer,
)
from iris.plan_step_execution_evidence_assessment_composition import (
    PlanStepExecutionEvidenceAssessmentComposer,
    PlanStepExecutionEvidenceAssessmentCompositionError,
    PlanStepExecutionEvidenceAssessmentCompositionInvariantError,
    PlanStepExecutionEvidenceAssessmentCompositionResult,
)
from iris.plan_step_execution_request_materialization import (
    PlanStepExecutionRequestMaterializer,
)
from iris.plan_step_execution_result_recording import (
    PlanStepExecutionResultRecorder,
)
from iris.plan_step_execution_result_recording_composition import (
    PlanStepExecutionResultRecordingComposer,
    PlanStepExecutionResultRecordingCompositionError,
    PlanStepExecutionResultRecordingCompositionResult,
)
from iris.plan_step_execution_start import (
    PlanStepExecutionInvocationError,
    PlanStepExecutionStartCoordinator,
)
from iris.plan_step_execution_start_composition import PlanStepExecutionStartComposer
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
POST_ASSESSED = BASE + timedelta(seconds=207)
PROVENANCE = RunProvenance("test", "wp039")
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

    @property
    def target(self) -> OrchestrationTarget:
        return OrchestrationTarget.CAPABILITY

    @property
    def handler_reference(self) -> str:
        return "handler.capability.wp039"

    def execute(self, request: ExecutionRequest) -> HandlerOutcome:
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
        ),
    )


def record_fixture_observation(
    plan: Plan,
    run: PlanRun,
    *,
    observation_id: str,
    step_id: str,
    offset: int,
) -> PlanRun:
    observation = PlanObservation(
        observation_id=observation_id,
        run_id=run.run_id,
        step_id=step_id,
        source="test",
        source_reference=f"source-{observation_id}",
        observed_at=BASE + timedelta(seconds=offset),
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
            updated_at=observation.observed_at,
            provenance=PROVENANCE,
            observation=observation,
        ),
    )


def selected_scenario(
    *,
    prior_b_evidence: bool = False,
    selected_handling: HandlingKind | None = HandlingKind.CAPABILITY,
) -> tuple[Plan, PlanRun]:
    plan = make_plan(
        step("a"),
        step("b", depends_on=("a",), handling=selected_handling),
    )
    run = transition(plan, new_run(plan), "a", StepProgressState.ACTIVE)
    run = record_fixture_observation(
        plan,
        run,
        observation_id="evidence-a",
        step_id="a",
        offset=2,
    )
    if prior_b_evidence:
        run = record_fixture_observation(
            plan,
            run,
            observation_id="a-prior-evidence-b",
            step_id="b",
            offset=3,
        )
    return plan, run


@dataclass
class FixedStatusEvaluator:
    status: StepOutcomeStatus
    assessed_at: datetime
    assessment_ids: list[str] = field(default_factory=lambda: ["post-assessment-1"])
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
        assessment_id = self.assessment_ids.pop(0)
        return StepOutcomeAssessment(
            assessment_id=assessment_id,
            plan_id=plan.plan_id,
            run_id=run.run_id,
            run_revision=run.revision,
            step_id=canonical_step.step_id,
            status=self.status,
            evidence_ids=tuple(item.observation_id for item in evidence),
            evaluator_reference="test.wp039.v1",
            assessed_at=self.assessed_at,
            details={"status": self.status.value},
        )


@dataclass
class SourceStatusEvaluator:
    status: StepOutcomeStatus

    def evaluate(
        self,
        plan: Plan,
        run: PlanRun,
        canonical_step: PlanStep,
        evidence: tuple[PlanObservation, ...],
    ) -> StepOutcomeAssessment:
        return StepOutcomeAssessment(
            assessment_id="source-assessment-1",
            plan_id=plan.plan_id,
            run_id=run.run_id,
            run_revision=run.revision,
            step_id=canonical_step.step_id,
            status=self.status,
            evidence_ids=tuple(item.observation_id for item in evidence),
            evaluator_reference="test.source.v1",
            assessed_at=ASSESSED,
            details={"status": self.status.value},
        )


def binding_composer() -> PlanStepExecutionBindingComposer:
    assessor = PlanStepEvidenceAssessor(
        cast(
            StepOutcomeEvaluator,
            SourceStatusEvaluator(StepOutcomeStatus.SATISFIED),
        )
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


def real_recording_composer(
    handler: CapabilityHandler | None,
) -> PlanStepExecutionResultRecordingComposer:
    start = PlanStepExecutionStartComposer(
        binding_composer=binding_composer(),
        start_coordinator=start_coordinator(handler),
    )
    recorder = PlanStepExecutionResultRecorder(
        observation_adapter=ExecutionObservationAdapter(
            clock=lambda: OBSERVED,
            observation_id_factory=lambda: "execution-observation-1",
        ),
        update_id_factory=lambda: "record-execution-update-1",
    )
    return PlanStepExecutionResultRecordingComposer(
        start_composer=start,
        result_recorder=recorder,
    )


def canonical_wp038(
    *,
    handler_available: bool = True,
    outcome: HandlerOutcome | None = None,
    prior_b_evidence: bool = False,
) -> tuple[Plan, PlanRun, PlanStepExecutionResultRecordingCompositionResult]:
    plan, run = selected_scenario(prior_b_evidence=prior_b_evidence)
    handler = None
    if handler_available:
        handler = CapabilityHandler(
            outcome=HandlerOutcome(ExecutionStatus.SUCCEEDED)
            if outcome is None
            else outcome
        )
    result = real_recording_composer(handler).compose(
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


class RecordingWP038(PlanStepExecutionResultRecordingComposer):
    def __init__(
        self,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__(
            start_composer=PlanStepExecutionStartComposer(
                binding_composer=binding_composer(),
                start_coordinator=start_coordinator(None),
            )
        )
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
    ) -> PlanStepExecutionResultRecordingCompositionResult:
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
            return cast(
                PlanStepExecutionResultRecordingCompositionResult,
                self.forced,
            )
        return super().compose(
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


class RecordingAssessor(PlanStepEvidenceAssessor):
    def __init__(
        self,
        delegate: PlanStepEvidenceAssessor,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__()
        self.delegate = delegate
        self.forced = forced
        self.error = error
        self.calls: list[tuple[Plan, PlanRun, str]] = []

    def assess(
        self,
        plan: Plan,
        run: PlanRun,
        step_id: str,
    ) -> StepOutcomeAssessment:
        self.calls.append((plan, run, step_id))
        if self.error is not None:
            raise self.error
        if self.forced is not None:
            return cast(StepOutcomeAssessment, self.forced)
        return self.delegate.assess(plan, run, step_id)


def assessor_for(
    status: StepOutcomeStatus = StepOutcomeStatus.INDETERMINATE,
    *,
    assessed_at: datetime = POST_ASSESSED,
    assessment_ids: list[str] | None = None,
) -> tuple[PlanStepEvidenceAssessor, FixedStatusEvaluator]:
    evaluator = FixedStatusEvaluator(
        status,
        assessed_at,
        ["post-assessment-1"] if assessment_ids is None else assessment_ids,
    )
    assessor = PlanStepEvidenceAssessor(cast(StepOutcomeEvaluator, evaluator))
    return assessor, evaluator


def compose_from(
    plan: Plan,
    run: PlanRun,
    delegated: PlanStepExecutionResultRecordingCompositionResult,
    *,
    assessor: RecordingAssessor | None = None,
    execution_input: CapabilityExecutionInput | None = None,
) -> tuple[
    PlanStepExecutionEvidenceAssessmentCompositionResult,
    RecordingWP038,
    RecordingAssessor,
]:
    wp038 = RecordingWP038(forced=delegated)
    if assessor is None:
        canonical_assessor, _ = assessor_for()
        assessor = RecordingAssessor(canonical_assessor)
    supplied_input = capability_input() if execution_input is None else execution_input
    result = PlanStepExecutionEvidenceAssessmentComposer(
        recording_composer=wp038,
        assessor=assessor,
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
    return result, wp038, assessor


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
        PlanStepExecutionEvidenceAssessmentCompositionInvariantError,
        PlanStepExecutionEvidenceAssessmentCompositionError,
    )
    signature = inspect.signature(PlanStepExecutionEvidenceAssessmentComposer.compose)
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
    with pytest.raises(TypeError, match="recording_composer"):
        PlanStepExecutionEvidenceAssessmentComposer()  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="recording_composer"):
        PlanStepExecutionEvidenceAssessmentComposer(
            recording_composer=cast(Any, object())
        )
    with pytest.raises(TypeError, match="assessor"):
        PlanStepExecutionEvidenceAssessmentComposer(
            recording_composer=real_recording_composer(None),
            assessor=cast(Any, object()),
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
def test_invalid_inputs_fail_before_wp038(position: int, invalid: object) -> None:
    plan, run = selected_scenario()
    wp038 = RecordingWP038()
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
        PlanStepExecutionEvidenceAssessmentComposer(recording_composer=wp038).compose(
            cast(Plan, values[0]),
            cast(PlanRun, values[1]),
            cast(str, values[2]),
            candidates=cast(tuple[ContextCandidate, ...], values[3]),
            budget=cast(ContextBudget, values[4]),
            uncertainties=cast(tuple[ContextUncertainty, ...], values[5]),
            created_at=cast(datetime, values[6]),
            availability=cast(HandlerAvailability, values[7]),
        )
    assert wp038.calls == []


def test_no_recording_preserves_inherited_assessment_and_skips_wp027() -> None:
    plan, run = selected_scenario(selected_handling=None)
    no_recording = real_recording_composer(None).compose(
        plan,
        run,
        "a",
        candidates=(),
        budget=BUDGET,
        created_at=CONTEXT_CREATED,
        availability=HandlerAvailability(capability=False),
        execution_input=None,
    )
    assert no_recording.execution_recording_result is None
    assessor, _ = assessor_for()
    recording_assessor = RecordingAssessor(assessor)
    result, wp038, recorded_assessor = compose_from(
        plan,
        run,
        no_recording,
        assessor=recording_assessor,
        execution_input=capability_input(),
    )
    assert len(wp038.calls) == 1
    assert recorded_assessor.calls == []
    assert result.post_recording_assessment is None
    assert result.assessment is no_recording.assessment
    for item in fields(no_recording):
        assert getattr(result, item.name) is getattr(no_recording, item.name)


def test_exact_inputs_are_forwarded_to_wp038_once() -> None:
    plan, run = selected_scenario(selected_handling=None)
    no_recording = real_recording_composer(None).compose(
        plan,
        run,
        "a",
        candidates=(),
        budget=BUDGET,
        created_at=CONTEXT_CREATED,
        availability=HandlerAvailability(capability=False),
    )
    operation_input = capability_input()
    _, wp038, _ = compose_from(plan, run, no_recording, execution_input=operation_input)
    assert wp038.calls == [
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


def test_handler_unavailable_is_assessed_on_exact_recorded_run() -> None:
    plan, source_run, delegated = canonical_wp038(handler_available=False)
    recording = delegated.execution_recording_result
    start = delegated.execution_start_result
    assert recording is not None and start is not None
    assert start.active_run is None
    assert selected_state(recording.recorded_run) is StepProgressState.NOT_STARTED
    result, _, assessor = compose_from(plan, source_run, delegated)
    assert assessor.calls == [(plan, recording.recorded_run, "b")]
    post = result.post_recording_assessment
    assert post is not None
    assert recording.observation_id in post.evidence_ids
    assert post.status is StepOutcomeStatus.INDETERMINATE


@pytest.mark.parametrize(
    ("outcome", "status"),
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
def test_invoked_statuses_share_one_assessment_path_without_progress_mapping(
    outcome: HandlerOutcome,
    status: ExecutionStatus,
) -> None:
    plan, source_run, delegated = canonical_wp038(outcome=outcome)
    recording = delegated.execution_recording_result
    start = delegated.execution_start_result
    assert recording is not None and start is not None and start.active_run is not None
    assert recording.observation.data["status"] == status.value
    result, _, assessor = compose_from(plan, source_run, delegated)
    assert assessor.calls == [(plan, recording.recorded_run, recording.step_id)]
    assert result.post_recording_assessment is not None
    assert result.post_recording_assessment.status is StepOutcomeStatus.INDETERMINATE
    assert selected_state(recording.recorded_run) is StepProgressState.ACTIVE


def test_processed_a_and_post_recording_b_remain_distinct() -> None:
    plan, source_run, delegated = canonical_wp038()
    recording = delegated.execution_recording_result
    assert recording is not None
    result, _, assessor = compose_from(plan, source_run, delegated)
    assert delegated.assessment.step_id == "a"
    assert recording.step_id == "b"
    assert assessor.calls == [(plan, recording.recorded_run, "b")]
    assert result.assessment is delegated.assessment
    assert result.assessment.step_id == "a"
    assert result.post_recording_assessment is not None
    assert result.post_recording_assessment.step_id == "b"


def test_wp027_receives_complete_prior_and_new_step_evidence() -> None:
    plan, source_run, delegated = canonical_wp038(prior_b_evidence=True)
    recording = delegated.execution_recording_result
    assert recording is not None
    canonical_assessor, evaluator = assessor_for()
    result, _, _ = compose_from(
        plan,
        source_run,
        delegated,
        assessor=RecordingAssessor(canonical_assessor),
    )
    assert len(evaluator.calls) == 1
    evidence = evaluator.calls[0][3]
    assert tuple(item.observation_id for item in evidence) == (
        "a-prior-evidence-b",
        recording.observation_id,
    )
    assert result.post_recording_assessment is not None
    assert result.post_recording_assessment.evidence_ids == tuple(
        sorted(("a-prior-evidence-b", recording.observation_id))
    )


@pytest.mark.parametrize(
    "status",
    [
        StepOutcomeStatus.SATISFIED,
        StepOutcomeStatus.NOT_SATISFIED,
        StepOutcomeStatus.INDETERMINATE,
    ],
)
def test_replaceable_valid_evaluator_status_is_preserved(
    status: StepOutcomeStatus,
) -> None:
    plan, source_run, delegated = canonical_wp038()
    canonical_assessor, _ = assessor_for(status)
    result, _, _ = compose_from(
        plan,
        source_run,
        delegated,
        assessor=RecordingAssessor(canonical_assessor),
    )
    assert result.post_recording_assessment is not None
    assert result.post_recording_assessment.status is status


def test_wp038_error_propagates_unchanged_before_wp027() -> None:
    plan, run = selected_scenario()
    error = PlanStepExecutionResultRecordingCompositionError("WP038 failed")
    wp038 = RecordingWP038(error=error)
    assessor, _ = assessor_for()
    recording_assessor = RecordingAssessor(assessor)
    with pytest.raises(PlanStepExecutionResultRecordingCompositionError) as caught:
        PlanStepExecutionEvidenceAssessmentComposer(
            recording_composer=wp038,
            assessor=recording_assessor,
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
    assert len(wp038.calls) == 1
    assert recording_assessor.calls == []


def test_post_active_invocation_error_propagates_without_assessment() -> None:
    plan, source_run, delegated = canonical_wp038()
    start = delegated.execution_start_result
    assert start is not None and start.active_run is not None
    error = PlanStepExecutionInvocationError(
        "handler exploded",
        active_run=start.active_run,
        activation_update_id=start.activation_update_id or "missing",
        execution_id=start.execution_id,
    )
    wp038 = RecordingWP038(error=error)
    canonical_assessor, _ = assessor_for()
    assessor = RecordingAssessor(canonical_assessor)
    with pytest.raises(PlanStepExecutionInvocationError) as caught:
        PlanStepExecutionEvidenceAssessmentComposer(
            recording_composer=wp038,
            assessor=assessor,
        ).compose(
            plan,
            source_run,
            "a",
            candidates=(),
            budget=BUDGET,
            created_at=CONTEXT_CREATED,
            availability=CAPABILITY_AVAILABLE,
            execution_input=capability_input(),
        )
    assert caught.value is error
    assert caught.value.active_run is start.active_run
    assert assessor.calls == []


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_type",
        "foreign_source",
        "presence_mismatch",
        "foreign_recording_plan",
        "foreign_recorded_run",
        "foreign_observation_step",
        "non_execution_observation",
        "observation_missing_from_run",
    ],
)
def test_malformed_wp038_output_fails_before_wp027(mutation: str) -> None:
    plan, source_run, delegated = canonical_wp038()
    recording = delegated.execution_recording_result
    assert recording is not None
    malformed: object = delegated
    if mutation == "wrong_type":
        malformed = object()
    elif mutation == "foreign_source":
        malformed = unsafe_clone(
            delegated,
            assessment=unsafe_clone(delegated.assessment, plan_id="foreign-plan"),
        )
    elif mutation == "presence_mismatch":
        malformed = unsafe_clone(delegated, execution_start_result=None)
    elif mutation == "foreign_recording_plan":
        malformed = unsafe_clone(
            delegated,
            execution_recording_result=unsafe_clone(recording, plan_id="foreign-plan"),
        )
    elif mutation == "foreign_recorded_run":
        malformed = unsafe_clone(
            delegated,
            execution_recording_result=unsafe_clone(
                recording,
                recorded_run=unsafe_clone(recording.recorded_run, run_id="foreign-run"),
            ),
        )
    elif mutation == "foreign_observation_step":
        malformed = unsafe_clone(
            delegated,
            execution_recording_result=unsafe_clone(
                recording,
                observation=unsafe_clone(recording.observation, step_id="a"),
            ),
        )
    elif mutation == "non_execution_observation":
        malformed = unsafe_clone(
            delegated,
            execution_recording_result=unsafe_clone(
                recording,
                observation=unsafe_clone(recording.observation, source="test"),
            ),
        )
    else:
        malformed = unsafe_clone(
            delegated,
            execution_recording_result=unsafe_clone(
                recording,
                recorded_run=unsafe_clone(
                    recording.recorded_run,
                    observations=tuple(
                        item
                        for item in recording.recorded_run.observations
                        if item is not recording.observation
                    ),
                ),
            ),
        )
    wp038 = RecordingWP038(forced=malformed)
    canonical_assessor, _ = assessor_for()
    assessor = RecordingAssessor(canonical_assessor)
    with pytest.raises(PlanStepExecutionEvidenceAssessmentCompositionInvariantError):
        PlanStepExecutionEvidenceAssessmentComposer(
            recording_composer=wp038,
            assessor=assessor,
        ).compose(
            plan,
            source_run,
            "a",
            candidates=(),
            budget=BUDGET,
            created_at=CONTEXT_CREATED,
            availability=CAPABILITY_AVAILABLE,
            execution_input=capability_input(),
        )
    assert assessor.calls == []


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_type",
        "plan_id",
        "run_id",
        "run_revision",
        "step_id",
        "missing_observation",
    ],
)
def test_malformed_wp027_output_becomes_wp039_invariant(mutation: str) -> None:
    plan, source_run, delegated = canonical_wp038(prior_b_evidence=True)
    recording = delegated.execution_recording_result
    assert recording is not None
    canonical_assessor, _ = assessor_for()
    canonical = canonical_assessor.assess(plan, recording.recorded_run, "b")
    malformed: object = canonical
    if mutation == "wrong_type":
        malformed = object()
    elif mutation in {"plan_id", "run_id", "step_id"}:
        malformed = unsafe_clone(canonical, **{mutation: f"foreign-{mutation}"})
    elif mutation == "run_revision":
        malformed = unsafe_clone(canonical, run_revision=canonical.run_revision + 1)
    else:
        malformed = unsafe_clone(
            canonical,
            evidence_ids=("a-prior-evidence-b",),
        )
    assessor = RecordingAssessor(canonical_assessor, forced=malformed)
    with pytest.raises(PlanStepExecutionEvidenceAssessmentCompositionInvariantError):
        compose_from(plan, source_run, delegated, assessor=assessor)
    assert len(assessor.calls) == 1


def test_wp027_error_propagates_once_without_fabricated_assessment() -> None:
    plan, source_run, delegated = canonical_wp038()
    error = PlanStepEvidenceAssessmentInvariantError("evaluator failed")
    canonical_assessor, _ = assessor_for()
    assessor = RecordingAssessor(canonical_assessor, error=error)
    with pytest.raises(PlanStepEvidenceAssessmentInvariantError) as caught:
        compose_from(plan, source_run, delegated, assessor=assessor)
    assert caught.value is error
    assert len(assessor.calls) == 1


def test_wp039_does_not_require_assessment_after_recorded_run_updated_at() -> None:
    plan, source_run, delegated = canonical_wp038()
    recording = delegated.execution_recording_result
    assert recording is not None
    later_updated_run = unsafe_clone(
        recording.recorded_run,
        updated_at=POST_ASSESSED + timedelta(seconds=30),
    )
    later_recording = unsafe_clone(recording, recorded_run=later_updated_run)
    delegated = unsafe_clone(
        delegated,
        execution_recording_result=later_recording,
    )
    canonical_assessor, _ = assessor_for(assessed_at=POST_ASSESSED)
    result, _, _ = compose_from(
        plan,
        source_run,
        delegated,
        assessor=RecordingAssessor(canonical_assessor),
    )
    assert result.post_recording_assessment is not None
    assert result.post_recording_assessment.assessed_at < later_updated_run.updated_at


def test_repeated_calls_create_independent_assessments_without_deduplication() -> None:
    plan, source_run, delegated = canonical_wp038()
    canonical_assessor, evaluator = assessor_for(
        assessment_ids=["post-assessment-1", "post-assessment-2"]
    )
    assessor = RecordingAssessor(canonical_assessor)
    wp038 = RecordingWP038(forced=delegated)
    composer = PlanStepExecutionEvidenceAssessmentComposer(
        recording_composer=wp038,
        assessor=assessor,
    )
    results = [
        composer.compose(
            plan,
            source_run,
            "a",
            candidates=(),
            budget=BUDGET,
            created_at=CONTEXT_CREATED,
            availability=CAPABILITY_AVAILABLE,
            execution_input=capability_input(),
        )
        for _ in range(2)
    ]
    assert len(wp038.calls) == 2
    assert len(assessor.calls) == 2
    assert len(evaluator.calls) == 2
    assert results[0].post_recording_assessment is not None
    assert results[1].post_recording_assessment is not None
    assert (
        results[0].post_recording_assessment.assessment_id
        != results[1].post_recording_assessment.assessment_id
    )


def test_exact_wp038_artifacts_and_wp027_assessment_are_preserved() -> None:
    plan, source_run, delegated = canonical_wp038()
    recording = delegated.execution_recording_result
    assert recording is not None
    canonical_assessor, _ = assessor_for()
    expected = canonical_assessor.assess(plan, recording.recorded_run, "b")
    result, _, _ = compose_from(
        plan,
        source_run,
        delegated,
        assessor=RecordingAssessor(canonical_assessor, forced=expected),
    )
    for item in fields(delegated):
        assert getattr(result, item.name) is getattr(delegated, item.name)
    assert result.assessment is delegated.assessment
    assert result.post_recording_assessment is expected
    assert result.post_recording_assessment is not result.assessment


def test_result_is_immutable_serializable_and_enforces_presence() -> None:
    plan, source_run, delegated = canonical_wp038()
    result, _, _ = compose_from(plan, source_run, delegated)
    assert result.to_data() == result.to_data()
    json.dumps(result.to_data())
    assert result.post_recording_assessment is not None
    assert result.to_data()["assessment"] == delegated.assessment.to_data()
    assert result.to_data()["post_recording_assessment"] == (
        result.post_recording_assessment.to_data()
    )
    with pytest.raises(FrozenInstanceError):
        result.post_recording_assessment = None  # type: ignore[misc]
    kwargs = {item.name: getattr(delegated, item.name) for item in fields(delegated)}
    with pytest.raises(PlanStepExecutionEvidenceAssessmentCompositionInvariantError):
        PlanStepExecutionEvidenceAssessmentCompositionResult(
            **kwargs,
            post_recording_assessment=None,
        )


def test_wp039_has_no_forbidden_authority_dependencies() -> None:
    source = Path(
        "iris/plan_step_execution_evidence_assessment_composition/composer.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "PlanStepEvidenceTransitionComposer",
        "StepProgressTransitionDecider",
        "PlanRunReducer",
        "PlanRunController",
        "StepProgressUpdateSynthesizer",
        "PlanStepProgressAdvancementComposer",
        "ExecutionCoordinator",
        "PlanStepExecutionInvocationError",
    ):
        assert forbidden not in source
