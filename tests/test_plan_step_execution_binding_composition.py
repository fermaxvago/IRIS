"""WP036 bounded post-request PlanStep execution binding composition."""

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
from iris.plan_step_execution_binding import (
    NonExecutableExecutionRequestError,
    PlanStepExecutionBinder,
    PlanStepExecutionBinding,
    PlanStepExecutionBindingInvariantError,
)
from iris.plan_step_execution_binding_composition import (
    PlanStepExecutionBindingComposer,
    PlanStepExecutionBindingCompositionError,
    PlanStepExecutionBindingCompositionInvariantError,
    PlanStepExecutionBindingCompositionResult,
)
from iris.plan_step_execution_request_materialization import (
    PlanStepExecutionRequestMaterializationResult,
    PlanStepExecutionRequestMaterializer,
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
PROVENANCE = RunProvenance("test", "wp036")
BUDGET = ContextBudget(0)
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


def wp035_for(status: StepOutcomeStatus) -> PlanStepExecutionRequestMaterializer:
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
    return PlanStepExecutionRequestMaterializer(
        orchestration_composer=orchestration,
        clock=lambda: REQUESTED,
        execution_id_factory=lambda: "execution-1",
    )


class RecordingWP035(PlanStepExecutionRequestMaterializer):
    def __init__(
        self,
        delegate: PlanStepExecutionRequestMaterializer,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__()
        self.delegate = delegate
        self.forced = forced
        self.error = error
        self.calls: list[tuple[object, ...]] = []

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
        availability: HandlerAvailability,
        execution_input: Any = None,
    ) -> PlanStepExecutionRequestMaterializationResult:
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
            return cast(PlanStepExecutionRequestMaterializationResult, self.forced)
        return self.delegate.materialize(
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


class RecordingBinder(PlanStepExecutionBinder):
    def __init__(
        self,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        self.forced = forced
        self.error = error
        self.calls: list[tuple[object, ...]] = []

    def bind(
        self,
        plan: Plan,
        run: PlanRun,
        control_decision: Any,
        preparation: Any,
        execution_request: ExecutionRequest,
    ) -> PlanStepExecutionBinding:
        self.calls.append((plan, run, control_decision, preparation, execution_request))
        if self.error is not None:
            raise self.error
        if self.forced is not None:
            return cast(PlanStepExecutionBinding, self.forced)
        return super().bind(
            plan,
            run,
            control_decision,
            preparation,
            execution_request,
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


def canonical_wp035(
    *,
    handling: HandlingKind | None = HandlingKind.CAPABILITY,
    availability: HandlerAvailability = CAPABILITY_AVAILABLE,
    status: StepOutcomeStatus = StepOutcomeStatus.SATISFIED,
    execution_input: Any = None,
) -> tuple[Plan, PlanRun, PlanStepExecutionRequestMaterializationResult]:
    plan, run = selected_scenario(handling)
    if execution_input is None and availability.capability:
        execution_input = capability_input()
    result = wp035_for(status).materialize(
        plan,
        run,
        "a",
        candidates=(),
        budget=BUDGET,
        created_at=CONTEXT_CREATED,
        availability=availability,
        execution_input=execution_input,
    )
    return plan, run, result


def unsafe_result(
    source: PlanStepExecutionRequestMaterializationResult,
    **changes: object,
) -> PlanStepExecutionRequestMaterializationResult:
    result = object.__new__(PlanStepExecutionRequestMaterializationResult)
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
    delegated: PlanStepExecutionRequestMaterializationResult,
    *,
    binder: RecordingBinder | None = None,
) -> tuple[
    PlanStepExecutionBindingCompositionResult,
    RecordingWP035,
    RecordingBinder,
]:
    recorder = RecordingWP035(wp035_for(StepOutcomeStatus.SATISFIED), forced=delegated)
    recording_binder = RecordingBinder() if binder is None else binder
    result = PlanStepExecutionBindingComposer(
        request_materializer=recorder,
        execution_binder=recording_binder,
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
    return result, recorder, recording_binder


def test_public_api_signature_and_constructor_injection() -> None:
    assert issubclass(
        PlanStepExecutionBindingCompositionInvariantError,
        PlanStepExecutionBindingCompositionError,
    )
    signature = inspect.signature(PlanStepExecutionBindingComposer.compose)
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
    with pytest.raises(TypeError, match="request_materializer"):
        PlanStepExecutionBindingComposer(request_materializer=cast(Any, object()))
    with pytest.raises(TypeError, match="execution_binder"):
        PlanStepExecutionBindingComposer(execution_binder=cast(Any, object()))


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
def test_invalid_inputs_fail_before_wp035(position: int, invalid: object) -> None:
    plan, run = selected_scenario()
    recorder = RecordingWP035(wp035_for(StepOutcomeStatus.SATISFIED))
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
        PlanStepExecutionBindingComposer(request_materializer=recorder).compose(
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
    ("handling", "status"),
    [
        (None, StepHandlingPreparationStatus.HANDLING_UNSPECIFIED),
        (HandlingKind.SYSTEM, StepHandlingPreparationStatus.INSUFFICIENT_DETAIL),
    ],
)
def test_no_request_stops_without_binding(
    handling: HandlingKind | None,
    status: StepHandlingPreparationStatus,
) -> None:
    plan, run, delegated = canonical_wp035(handling=handling)
    assert delegated.execution_request is None
    assert delegated.handling_preparation is not None
    assert delegated.handling_preparation.status is status
    result, recorder, binder = compose_from(plan, run, delegated)
    assert len(recorder.calls) == 1
    assert recorder.calls[0][:8] == (
        plan,
        run,
        "a",
        (),
        BUDGET,
        (),
        CONTEXT_CREATED,
        CAPABILITY_AVAILABLE,
    )
    assert binder.calls == []
    assert result.execution_request is None
    assert result.execution_binding is None
    assert result.assessment is delegated.assessment
    assert result.handling_preparation is delegated.handling_preparation


def test_no_advancement_stops_without_binding() -> None:
    plan, run, delegated = canonical_wp035(status=StepOutcomeStatus.INDETERMINATE)
    assert delegated.advancement_result is None
    result, _, binder = compose_from(plan, run, delegated)
    assert binder.calls == []
    assert result.execution_binding is None
    assert result.progress_update is delegated.progress_update


def test_success_uses_exact_successor_lineage_and_selected_step() -> None:
    plan, source_run, delegated = canonical_wp035()
    assert delegated.advancement_result is not None
    assert delegated.execution_request is not None
    successor = delegated.advancement_result.updated_run
    control = delegated.advancement_result.control_decision
    preparation = delegated.handling_preparation
    request = delegated.execution_request
    result, recorder, binder = compose_from(plan, source_run, delegated)

    assert len(recorder.calls) == 1
    assert len(binder.calls) == 1
    assert binder.calls[0] == (plan, successor, control, preparation, request)
    assert binder.calls[0][1] is successor
    assert binder.calls[0][1] is not source_run
    binding = result.execution_binding
    assert binding is not None
    assert source_run.revision + 1 == successor.revision
    assert binding.observed_revision == successor.revision
    assert delegated.assessment.step_id == "a"
    assert control.selected_step_id == "b"
    assert binding.step_id == "b"
    assert binding.execution_id == request.execution_id
    assert binding.subject_id == request.subject.subject_id
    assert binding.context_snapshot_id == request.context.snapshot_id
    assert binding.orchestration_decision_id == request.decision.decision_id


def test_all_wp035_artifacts_and_exact_wp024_binding_are_preserved() -> None:
    plan, run, delegated = canonical_wp035()
    assert delegated.execution_request is not None
    assert delegated.advancement_result is not None
    expected = PlanStepExecutionBinder().bind(
        plan,
        delegated.advancement_result.updated_run,
        delegated.advancement_result.control_decision,
        cast(Any, delegated.handling_preparation),
        delegated.execution_request,
    )
    binder = RecordingBinder(forced=expected)
    result, _, _ = compose_from(plan, run, delegated, binder=binder)
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
    ):
        assert getattr(result, name) is getattr(delegated, name)
    assert result.execution_binding is expected


def test_unsatisfied_request_reaches_wp024_and_exact_error_propagates() -> None:
    plan, run, delegated = canonical_wp035(
        availability=HandlerAvailability(), execution_input=None
    )
    assert delegated.execution_request is not None
    assert delegated.orchestration_decision is not None
    assert delegated.orchestration_decision.target is OrchestrationTarget.UNSATISFIED
    recorder = RecordingWP035(wp035_for(StepOutcomeStatus.SATISFIED), forced=delegated)
    binder = RecordingBinder()
    with pytest.raises(NonExecutableExecutionRequestError):
        PlanStepExecutionBindingComposer(
            request_materializer=recorder,
            execution_binder=binder,
        ).compose(
            plan,
            run,
            "a",
            candidates=(),
            budget=BUDGET,
            created_at=CONTEXT_CREATED,
            availability=HandlerAvailability(),
        )
    assert len(recorder.calls) == 1
    assert len(binder.calls) == 1
    assert binder.calls[0][-1] is delegated.execution_request


def test_clarify_controlled_request_reaches_wp024_and_is_not_suppressed() -> None:
    plan, run, delegated = canonical_wp035(
        availability=HandlerAvailability(), execution_input=None
    )
    assert delegated.orchestration_decision is not None
    assert delegated.execution_request is not None
    decision = unsafe_clone(
        delegated.orchestration_decision,
        target=OrchestrationTarget.CLARIFY,
    )
    request = unsafe_clone(delegated.execution_request, decision=decision)
    controlled = unsafe_result(
        delegated,
        orchestration_decision=decision,
        execution_request=request,
    )
    recorder = RecordingWP035(wp035_for(StepOutcomeStatus.SATISFIED), forced=controlled)
    binder = RecordingBinder()
    with pytest.raises(NonExecutableExecutionRequestError):
        PlanStepExecutionBindingComposer(
            request_materializer=recorder,
            execution_binder=binder,
        ).compose(
            plan,
            run,
            "a",
            candidates=(),
            budget=BUDGET,
            created_at=CONTEXT_CREATED,
            availability=HandlerAvailability(),
        )
    assert len(binder.calls) == 1
    assert binder.calls[0][-1] is request


def test_wp035_exception_propagates_and_binder_is_unused() -> None:
    plan, run = selected_scenario()
    error = RuntimeError("delegated failure")
    recorder = RecordingWP035(wp035_for(StepOutcomeStatus.SATISFIED), error=error)
    binder = RecordingBinder()
    with pytest.raises(RuntimeError) as caught:
        PlanStepExecutionBindingComposer(
            request_materializer=recorder,
            execution_binder=binder,
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
    assert binder.calls == []


def test_wrong_wp035_type_fails_before_binder() -> None:
    plan, run = selected_scenario()
    recorder = RecordingWP035(wp035_for(StepOutcomeStatus.SATISFIED), forced=object())
    binder = RecordingBinder()
    with pytest.raises(
        PlanStepExecutionBindingCompositionInvariantError,
        match="PlanStepExecutionRequestMaterializationResult",
    ):
        PlanStepExecutionBindingComposer(
            request_materializer=recorder,
            execution_binder=binder,
        ).compose(
            plan,
            run,
            "a",
            candidates=(),
            budget=BUDGET,
            created_at=CONTEXT_CREATED,
            availability=CAPABILITY_AVAILABLE,
        )
    assert binder.calls == []


@pytest.mark.parametrize(
    "mutation",
    [
        "foreign_source",
        "wrong_advancement_update",
        "foreign_context_owner",
        "stale_decision",
        "foreign_request_subject",
        "missing_preparation",
    ],
)
def test_malformed_wp035_lineage_fails_before_binder(mutation: str) -> None:
    plan, run, delegated = canonical_wp035()
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
    else:
        changes["handling_preparation"] = None
    malformed = unsafe_result(delegated, **changes)
    binder = RecordingBinder()
    with pytest.raises(PlanStepExecutionBindingCompositionInvariantError):
        compose_from(plan, run, malformed, binder=binder)
    assert binder.calls == []


def test_wp024_error_propagates_exactly_without_retry() -> None:
    plan, run, delegated = canonical_wp035()
    error = PlanStepExecutionBindingInvariantError("binder failure")
    binder = RecordingBinder(error=error)
    with pytest.raises(PlanStepExecutionBindingInvariantError) as caught:
        compose_from(plan, run, delegated, binder=binder)
    assert caught.value is error
    assert len(binder.calls) == 1


def test_malformed_wp024_return_becomes_wp036_invariant() -> None:
    plan, run, delegated = canonical_wp035()
    with pytest.raises(
        PlanStepExecutionBindingCompositionInvariantError,
        match="PlanStepExecutionBinding",
    ):
        compose_from(plan, run, delegated, binder=RecordingBinder(forced=object()))


def test_foreign_wp024_binding_becomes_wp036_invariant() -> None:
    plan, run, delegated = canonical_wp035()
    assert delegated.advancement_result is not None
    assert delegated.handling_preparation is not None
    assert delegated.execution_request is not None
    binding = PlanStepExecutionBinder().bind(
        plan,
        delegated.advancement_result.updated_run,
        delegated.advancement_result.control_decision,
        delegated.handling_preparation,
        delegated.execution_request,
    )
    foreign = unsafe_clone(binding, execution_id="foreign-execution")
    with pytest.raises(PlanStepExecutionBindingCompositionInvariantError):
        compose_from(plan, run, delegated, binder=RecordingBinder(forced=foreign))


def test_result_is_immutable_and_serialization_is_deterministic() -> None:
    plan, run, delegated = canonical_wp035()
    result, _, _ = compose_from(plan, run, delegated)
    assert result.to_data() == result.to_data()
    json.dumps(result.to_data())
    assert result.execution_binding is not None
    assert result.to_data()["execution_binding"] == result.execution_binding.to_data()
    with pytest.raises(FrozenInstanceError):
        result.execution_binding = None  # type: ignore[misc]


def test_result_model_rejects_presence_mismatch() -> None:
    _, _, delegated = canonical_wp035()
    with pytest.raises(PlanStepExecutionBindingCompositionInvariantError):
        PlanStepExecutionBindingCompositionResult(
            assessment=delegated.assessment,
            transition_decision=delegated.transition_decision,
            progress_update=delegated.progress_update,
            advancement_result=delegated.advancement_result,
            handling_preparation=delegated.handling_preparation,
            work_subject=delegated.work_subject,
            context_snapshot=delegated.context_snapshot,
            orchestration_decision=delegated.orchestration_decision,
            execution_request=delegated.execution_request,
            execution_binding=None,
        )


def test_wp036_has_no_execution_or_duplicate_policy_dependencies() -> None:
    source = Path("iris/plan_step_execution_binding_composition/composer.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "ExecutionCoordinator",
        "PlanStepExecutionStarter",
        "PlanRunReducer",
        "_EXECUTABLE_TARGETS",
        "derive_step_availability",
        "StepProgressState",
        "OrchestrationTarget",
        "ExecutionResult",
    ):
        assert forbidden not in source
