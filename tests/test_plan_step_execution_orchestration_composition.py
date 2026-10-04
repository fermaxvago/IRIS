"""WP046 bounded post-recording selected-PlanStep orchestration."""

from __future__ import annotations

import inspect
import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime, timedelta
from itertools import count
from typing import Any, cast

import pytest

import iris.plan_step_execution_orchestration_composition as public_api
import iris.plan_step_execution_orchestration_composition.composer as composer_module
from iris.context import (
    ContextBudget,
    ContextCandidate,
    ContextUncertainty,
    ResolutionStatus,
    UncertaintyReason,
)
from iris.execution import CapabilityExecutionInput
from iris.execution.models import ExecutionInput
from iris.memory import MemoryScope, ScopeKind
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
)
from iris.plan_control import ControlDecisionKind
from iris.plan_handling import StepHandlingPreparationStatus
from iris.plan_runs import PlanRun, StepProgressState
from iris.plan_step_execution_context_materialization_composition import (
    PlanStepExecutionContextMaterializationComposer,
    PlanStepExecutionContextMaterializationCompositionResult,
)
from iris.plan_step_execution_orchestration_composition import (
    PlanStepExecutionOrchestrationComposer,
    PlanStepExecutionOrchestrationCompositionError,
    PlanStepExecutionOrchestrationCompositionInvariantError,
    PlanStepExecutionOrchestrationCompositionResult,
)
from iris.planning import Plan
from iris.work_identity import PlanStepWorkReference, WorkSubject
from tests.test_plan_step_execution_context_materialization_composition import (
    GLOBAL,
    POST_RECORDING_BUDGET,
    POST_RECORDING_CREATED,
    RecordingWP044,
    candidate,
    canonical_wp044,
    compose_from_wp044,
    no_subject_wp044,
)
from tests.test_plan_step_execution_evidence_assessment_composition import (
    BUDGET,
    CAPABILITY_AVAILABLE,
    CONTEXT_CREATED,
    capability_input,
    unsafe_clone,
)
from tests.test_plan_step_execution_work_subject_materialization_composition import (
    compose_from_wp043,
    wp043_for_kind,
)

ORCHESTRATED = POST_RECORDING_CREATED + timedelta(seconds=1)
STEP_C_AVAILABLE = HandlerAvailability(capability=True)
STEP_C_UNAVAILABLE = HandlerAvailability()


class RecordingWP045(PlanStepExecutionContextMaterializationComposer):
    def __init__(
        self,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__(work_subject_materialization_composer=RecordingWP044())
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
        post_recording_candidates: tuple[ContextCandidate, ...],
        post_recording_budget: ContextBudget,
        post_recording_uncertainties: tuple[ContextUncertainty, ...] = (),
        post_recording_created_at: datetime,
    ) -> PlanStepExecutionContextMaterializationCompositionResult:
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
                post_recording_candidates,
                post_recording_budget,
                post_recording_uncertainties,
                post_recording_created_at,
            )
        )
        if self.error is not None:
            raise self.error
        return cast(
            PlanStepExecutionContextMaterializationCompositionResult,
            self.forced,
        )


class RecordingOrchestrator(Orchestrator):
    def __init__(
        self,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        identifiers = count(1)
        super().__init__(
            clock=lambda: ORCHESTRATED,
            id_factory=lambda: f"wp046-decision-{next(identifiers)}",
        )
        self.forced = forced
        self.error = error
        self.calls: list[OrchestrationInput] = []
        self.results: list[OrchestrationDecision] = []

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


def canonical_wp045(
    *,
    selected_handling: HandlingKind | None = HandlingKind.CAPABILITY,
    post_candidates: tuple[ContextCandidate, ...] = (),
    post_budget: ContextBudget = POST_RECORDING_BUDGET,
    post_uncertainties: tuple[ContextUncertainty, ...] = (),
) -> tuple[Plan, PlanRun, PlanStepExecutionContextMaterializationCompositionResult]:
    plan, run, delegated = canonical_wp044(selected_handling=selected_handling)
    result, _, _ = compose_from_wp044(
        plan,
        run,
        delegated,
        post_candidates=post_candidates,
        post_budget=post_budget,
        post_uncertainties=post_uncertainties,
    )
    return plan, run, result


def no_subject_wp045() -> tuple[
    Plan,
    PlanRun,
    PlanStepExecutionContextMaterializationCompositionResult,
]:
    plan, run, delegated = no_subject_wp044()
    result, _, _ = compose_from_wp044(plan, run, delegated)
    assert result.post_recording_work_subject is None
    return plan, run, result


def compose_from_wp045(
    plan: Plan,
    run: PlanRun,
    delegated: object,
    *,
    orchestrator: RecordingOrchestrator | None = None,
    inherited_candidates: tuple[ContextCandidate, ...] = (),
    inherited_budget: ContextBudget = BUDGET,
    inherited_uncertainties: tuple[ContextUncertainty, ...] = (),
    inherited_created_at: datetime = CONTEXT_CREATED,
    inherited_availability: HandlerAvailability = CAPABILITY_AVAILABLE,
    execution_input: CapabilityExecutionInput | None = None,
    post_candidates: tuple[ContextCandidate, ...] = (),
    post_budget: ContextBudget = POST_RECORDING_BUDGET,
    post_uncertainties: tuple[ContextUncertainty, ...] = (),
    post_created_at: datetime = POST_RECORDING_CREATED,
    post_availability: HandlerAvailability = STEP_C_AVAILABLE,
) -> tuple[
    PlanStepExecutionOrchestrationCompositionResult,
    RecordingWP045,
    RecordingOrchestrator,
]:
    wp045 = RecordingWP045(forced=delegated)
    actual_orchestrator = (
        RecordingOrchestrator() if orchestrator is None else orchestrator
    )
    supplied_input = capability_input() if execution_input is None else execution_input
    result = PlanStepExecutionOrchestrationComposer(
        context_materialization_composer=wp045,
        orchestrator=actual_orchestrator,
    ).compose(
        plan,
        run,
        "a",
        candidates=inherited_candidates,
        budget=inherited_budget,
        uncertainties=inherited_uncertainties,
        created_at=inherited_created_at,
        availability=inherited_availability,
        execution_input=supplied_input,
        post_recording_candidates=post_candidates,
        post_recording_budget=post_budget,
        post_recording_uncertainties=post_uncertainties,
        post_recording_created_at=post_created_at,
        post_recording_availability=post_availability,
    )
    return result, wp045, actual_orchestrator


def test_public_api_constructor_signature_and_exact_exports() -> None:
    assert set(public_api.__all__) == {
        "PlanStepExecutionOrchestrationComposer",
        "PlanStepExecutionOrchestrationCompositionResult",
        "PlanStepExecutionOrchestrationCompositionError",
        "PlanStepExecutionOrchestrationCompositionInvariantError",
    }
    assert issubclass(
        PlanStepExecutionOrchestrationCompositionInvariantError,
        PlanStepExecutionOrchestrationCompositionError,
    )
    assert tuple(
        inspect.signature(PlanStepExecutionOrchestrationComposer.compose).parameters
    ) == (
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
        "post_recording_candidates",
        "post_recording_budget",
        "post_recording_uncertainties",
        "post_recording_created_at",
        "post_recording_availability",
    )
    with pytest.raises(TypeError, match="context_materialization_composer"):
        PlanStepExecutionOrchestrationComposer()  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="context_materialization_composer"):
        PlanStepExecutionOrchestrationComposer(
            context_materialization_composer=cast(Any, object())
        )
    with pytest.raises(TypeError, match="orchestrator"):
        PlanStepExecutionOrchestrationComposer(
            context_materialization_composer=RecordingWP045(),
            orchestrator=cast(Any, object()),
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
        (8, object()),
        (9, []),
        (9, (object(),)),
        (10, object()),
        (11, []),
        (11, (object(),)),
        (12, object()),
        (13, object()),
    ],
)
def test_invalid_direct_inputs_fail_before_wp045(
    position: int,
    invalid: object,
) -> None:
    plan, run, delegated = no_subject_wp045()
    wp045 = RecordingWP045(forced=delegated)
    values: list[object] = [
        plan,
        run,
        "a",
        (),
        BUDGET,
        (),
        CONTEXT_CREATED,
        CAPABILITY_AVAILABLE,
        capability_input(),
        (),
        POST_RECORDING_BUDGET,
        (),
        POST_RECORDING_CREATED,
        STEP_C_AVAILABLE,
    ]
    values[position] = invalid
    with pytest.raises(TypeError):
        PlanStepExecutionOrchestrationComposer(
            context_materialization_composer=wp045
        ).compose(
            cast(Plan, values[0]),
            cast(PlanRun, values[1]),
            cast(str, values[2]),
            candidates=cast(tuple[ContextCandidate, ...], values[3]),
            budget=cast(ContextBudget, values[4]),
            uncertainties=cast(tuple[ContextUncertainty, ...], values[5]),
            created_at=cast(datetime, values[6]),
            availability=cast(HandlerAvailability, values[7]),
            execution_input=cast(ExecutionInput, values[8]),
            post_recording_candidates=cast(tuple[ContextCandidate, ...], values[9]),
            post_recording_budget=cast(ContextBudget, values[10]),
            post_recording_uncertainties=cast(
                tuple[ContextUncertainty, ...], values[11]
            ),
            post_recording_created_at=cast(datetime, values[12]),
            post_recording_availability=cast(HandlerAvailability, values[13]),
        )
    assert wp045.calls == []


def test_wp045_invoked_once_with_exact_inputs_and_availability_separation() -> None:
    inherited_candidate = candidate("step-b", "B", key="step_b")
    post_candidate = candidate("step-c", "C", key="step_c")
    inherited_uncertainty = ContextUncertainty(
        "task", "missing_b", GLOBAL, UncertaintyReason.MISSING
    )
    post_uncertainty = ContextUncertainty(
        "task", "missing_c", GLOBAL, UncertaintyReason.MISSING
    )
    inherited_budget = ContextBudget(1)
    post_budget = ContextBudget(2)
    inherited_availability = HandlerAvailability(system=True)
    post_availability = HandlerAvailability(capability=True)
    operation_input = capability_input()
    plan, run, delegated = canonical_wp045(
        post_candidates=(post_candidate,),
        post_budget=post_budget,
        post_uncertainties=(post_uncertainty,),
    )
    result, wp045, orchestrator = compose_from_wp045(
        plan,
        run,
        delegated,
        inherited_candidates=(inherited_candidate,),
        inherited_budget=inherited_budget,
        inherited_uncertainties=(inherited_uncertainty,),
        inherited_created_at=CONTEXT_CREATED,
        inherited_availability=inherited_availability,
        execution_input=operation_input,
        post_candidates=(post_candidate,),
        post_budget=post_budget,
        post_uncertainties=(post_uncertainty,),
        post_created_at=POST_RECORDING_CREATED,
        post_availability=post_availability,
    )
    assert wp045.calls == [
        (
            plan,
            run,
            "a",
            (inherited_candidate,),
            inherited_budget,
            (inherited_uncertainty,),
            CONTEXT_CREATED,
            inherited_availability,
            operation_input,
            (post_candidate,),
            post_budget,
            (post_uncertainty,),
            POST_RECORDING_CREATED,
        )
    ]
    assert len(orchestrator.calls) == 1
    assert orchestrator.calls[0].availability is post_availability
    assert orchestrator.calls[0].availability is not inherited_availability
    assert result.post_recording_orchestration_decision is not None


def test_no_post_recording_subject_skips_wp017_and_preserves_wp045() -> None:
    plan, run, delegated = no_subject_wp045()
    result, wp045, orchestrator = compose_from_wp045(plan, run, delegated)
    assert len(wp045.calls) == 1
    assert orchestrator.calls == []
    assert result.post_recording_orchestration_decision is None
    for item in fields(delegated):
        assert getattr(result, item.name) is getattr(delegated, item.name)


def test_nonselecting_fresh_control_skips_wp017_without_fallback() -> None:
    plan, run, wp043 = wp043_for_kind(ControlDecisionKind.ACTIVE_WORK_PENDING)
    wp044, _, _ = compose_from_wp043(plan, run, wp043)
    delegated, _, _ = compose_from_wp044(plan, run, wp044)
    assert delegated.post_recording_advancement_result is not None
    assert delegated.post_recording_work_subject is None

    result, _, orchestrator = compose_from_wp045(plan, run, delegated)

    assert orchestrator.calls == []
    assert result.post_recording_orchestration_decision is None
    assert (
        result.post_recording_advancement_result
        is delegated.post_recording_advancement_result
    )


@pytest.mark.parametrize(
    ("handling", "status"),
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
def test_non_prepared_handling_preserves_real_subject_and_context_without_wp017(
    handling: HandlingKind | None,
    status: StepHandlingPreparationStatus,
) -> None:
    plan, run, delegated = canonical_wp045(selected_handling=handling)
    assert delegated.post_recording_work_subject is not None
    assert delegated.post_recording_context_snapshot is not None
    assert delegated.post_recording_handling_preparation is not None
    assert delegated.post_recording_handling_preparation.status is status

    result, _, orchestrator = compose_from_wp045(plan, run, delegated)

    assert orchestrator.calls == []
    assert result.post_recording_work_subject is delegated.post_recording_work_subject
    assert (
        result.post_recording_context_snapshot
        is delegated.post_recording_context_snapshot
    )
    assert result.post_recording_orchestration_decision is None


def test_prepared_path_invokes_wp017_once_with_exact_step_c_artifacts() -> None:
    plan, run, delegated = canonical_wp045()
    preparation = delegated.post_recording_handling_preparation
    subject = delegated.post_recording_work_subject
    context = delegated.post_recording_context_snapshot
    assert preparation is not None
    assert subject is not None
    assert context is not None
    need = preparation.handling_need
    assert need is not None
    post_availability = HandlerAvailability(capability=True)

    result, _, orchestrator = compose_from_wp045(
        plan,
        run,
        delegated,
        post_availability=post_availability,
    )

    assert len(orchestrator.calls) == 1
    supplied = orchestrator.calls[0]
    assert supplied.subject is subject
    assert supplied.context is context
    assert supplied.needs == (need,)
    assert supplied.needs[0] is need
    assert supplied.availability is post_availability
    decision = result.post_recording_orchestration_decision
    assert decision is not None
    assert decision.target is OrchestrationTarget.CAPABILITY
    assert decision.reason is OrchestrationReason.EXPLICIT_CAPABILITY_HANDLING
    assert decision.requirement is need


def _context_case(
    status: ResolutionStatus,
) -> tuple[
    tuple[ContextCandidate, ...],
    ContextBudget,
    tuple[ContextUncertainty, ...],
]:
    first = candidate("first", "one", key="first")
    second = candidate("second", "two", key="second")
    if status is ResolutionStatus.RESOLVED:
        return (first,), ContextBudget(1), ()
    if status is ResolutionStatus.PARTIAL:
        return (
            (first,),
            ContextBudget(1),
            (ContextUncertainty("task", "missing", GLOBAL, UncertaintyReason.MISSING),),
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
            candidate("conflict-a", "a", key="shared"),
            candidate("conflict-b", "b", key="shared"),
        ),
        ContextBudget(2),
        (),
    )


@pytest.mark.parametrize("status", list(ResolutionStatus))
def test_context_status_remains_inert_orchestration_input(
    status: ResolutionStatus,
) -> None:
    candidates, budget, uncertainties = _context_case(status)
    plan, run, delegated = canonical_wp045(
        post_candidates=candidates,
        post_budget=budget,
        post_uncertainties=uncertainties,
    )
    context = delegated.post_recording_context_snapshot
    assert context is not None
    assert context.status is status

    result, _, orchestrator = compose_from_wp045(
        plan,
        run,
        delegated,
        post_candidates=candidates,
        post_budget=budget,
        post_uncertainties=uncertainties,
    )

    assert len(orchestrator.calls) == 1
    assert orchestrator.calls[0].context is context
    assert orchestrator.calls[0].needs[0].blockers == ()
    assert result.post_recording_orchestration_decision is not None
    assert (
        result.post_recording_orchestration_decision.target
        is OrchestrationTarget.CAPABILITY
    )


def test_unavailable_capability_preserves_real_unsatisfied_decision() -> None:
    plan, run, delegated = canonical_wp045()
    result, _, orchestrator = compose_from_wp045(
        plan,
        run,
        delegated,
        post_availability=STEP_C_UNAVAILABLE,
    )
    assert len(orchestrator.calls) == 1
    decision = result.post_recording_orchestration_decision
    assert decision is not None
    assert decision.target is OrchestrationTarget.UNSATISFIED
    assert decision.reason is OrchestrationReason.NO_ADMISSIBLE_HANDLER


@pytest.mark.parametrize(
    "mismatch",
    [
        "type",
        "source_plan",
        "stale_control",
        "preparation_step",
        "subject_step",
        "context_owner",
        "missing_context",
        "context_budget",
        "context_status",
    ],
)
def test_malformed_wp045_result_fails_before_wp017(mismatch: str) -> None:
    plan, run, delegated = canonical_wp045()
    forced: object = delegated
    advancement = delegated.post_recording_advancement_result
    preparation = delegated.post_recording_handling_preparation
    subject = delegated.post_recording_work_subject
    context = delegated.post_recording_context_snapshot
    assert advancement is not None
    assert preparation is not None
    assert subject is not None
    assert context is not None
    if mismatch == "type":
        forced = object()
    elif mismatch == "source_plan":
        forced = unsafe_clone(
            delegated,
            assessment=replace(delegated.assessment, plan_id="foreign-plan"),
        )
    elif mismatch == "stale_control":
        forced = unsafe_clone(
            delegated,
            post_recording_advancement_result=unsafe_clone(
                advancement,
                control_decision=unsafe_clone(
                    advancement.control_decision,
                    observed_revision=advancement.control_decision.observed_revision
                    + 1,
                ),
            ),
        )
    elif mismatch == "preparation_step":
        forced = unsafe_clone(
            delegated,
            post_recording_handling_preparation=unsafe_clone(preparation, step_id="a"),
        )
    elif mismatch == "subject_step":
        reference = subject.reference
        assert isinstance(reference, PlanStepWorkReference)
        forced = unsafe_clone(
            delegated,
            post_recording_work_subject=WorkSubject(
                subject.kind, replace(reference, step_id="a")
            ),
        )
    elif mismatch == "context_owner":
        equivalent = WorkSubject(subject.kind, subject.reference)
        assert equivalent == subject and equivalent is not subject
        forced = unsafe_clone(
            delegated,
            post_recording_context_snapshot=replace(context, subject=equivalent),
        )
    elif mismatch == "missing_context":
        forced = unsafe_clone(delegated, post_recording_context_snapshot=None)
    elif mismatch == "context_budget":
        forced = unsafe_clone(
            delegated,
            post_recording_context_snapshot=replace(
                context, budget=ContextBudget(context.budget.max_items + 1)
            ),
        )
    else:
        forced = unsafe_clone(
            delegated,
            post_recording_context_snapshot=unsafe_clone(context, status="resolved"),
        )
    orchestrator = RecordingOrchestrator()
    with pytest.raises(PlanStepExecutionOrchestrationCompositionInvariantError):
        compose_from_wp045(
            plan,
            run,
            forced,
            orchestrator=orchestrator,
        )
    assert orchestrator.calls == []


@pytest.mark.parametrize(
    "mismatch",
    ["type", "subject", "snapshot", "need_ids", "requirement", "time", "blocker"],
)
def test_malformed_wp017_decision_is_rejected(mismatch: str) -> None:
    plan, run, delegated = canonical_wp045()
    subject = delegated.post_recording_work_subject
    context = delegated.post_recording_context_snapshot
    preparation = delegated.post_recording_handling_preparation
    assert subject is not None
    assert context is not None
    assert preparation is not None
    need = preparation.handling_need
    assert need is not None
    canonical = Orchestrator(
        clock=lambda: ORCHESTRATED,
        id_factory=lambda: "canonical-wp046-decision",
    ).decide(OrchestrationInput(subject, context, (need,), STEP_C_AVAILABLE))
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
        forced = replace(canonical, requirement=replace(need, capability_id="other"))
    elif mismatch == "time":
        forced = replace(
            canonical,
            created_at=context.created_at - timedelta(seconds=1),
        )
    else:
        blocker = ContextBlocker(
            "task",
            "missing",
            MemoryScope(ScopeKind.GLOBAL),
            ContextBlockerKind.MISSING,
        )
        forced = OrchestrationDecision(
            decision_id="foreign-blocker-decision",
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
    with pytest.raises(PlanStepExecutionOrchestrationCompositionInvariantError):
        compose_from_wp045(plan, run, delegated, orchestrator=orchestrator)
    assert len(orchestrator.calls) == 1


def test_wp045_failure_propagates_exactly_without_wp017() -> None:
    plan, run, _ = no_subject_wp045()
    failure = RuntimeError("wp045 failed")
    wp045 = RecordingWP045(error=failure)
    orchestrator = RecordingOrchestrator()
    with pytest.raises(RuntimeError, match="wp045 failed") as raised:
        PlanStepExecutionOrchestrationComposer(
            context_materialization_composer=wp045,
            orchestrator=orchestrator,
        ).compose(
            plan,
            run,
            "a",
            candidates=(),
            budget=BUDGET,
            created_at=CONTEXT_CREATED,
            availability=CAPABILITY_AVAILABLE,
            execution_input=capability_input(),
            post_recording_candidates=(),
            post_recording_budget=POST_RECORDING_BUDGET,
            post_recording_created_at=POST_RECORDING_CREATED,
            post_recording_availability=STEP_C_AVAILABLE,
        )
    assert raised.value is failure
    assert len(wp045.calls) == 1
    assert orchestrator.calls == []


def test_wp017_failure_propagates_once_without_retry_or_none_conversion() -> None:
    plan, run, delegated = canonical_wp045()
    failure = RuntimeError("wp017 failed")
    orchestrator = RecordingOrchestrator(error=failure)
    with pytest.raises(RuntimeError, match="wp017 failed") as raised:
        compose_from_wp045(plan, run, delegated, orchestrator=orchestrator)
    assert raised.value is failure
    assert len(orchestrator.calls) == 1


def test_a_b_c_artifacts_remain_distinct_and_step_c_stays_inert() -> None:
    plan, run, delegated = canonical_wp045()
    source_run_data = run.to_data()
    result, _, _ = compose_from_wp045(plan, run, delegated)
    assert result.orchestration_decision is delegated.orchestration_decision
    assert result.post_recording_orchestration_decision is not None
    assert (
        result.post_recording_orchestration_decision
        is not result.orchestration_decision
    )
    advancement = result.post_recording_advancement_result
    assert advancement is not None
    selected_step_id = advancement.control_decision.selected_step_id
    assert selected_step_id is not None
    progress = {item.step_id: item for item in advancement.updated_run.step_progress}[
        selected_step_id
    ]
    assert progress.state is StepProgressState.NOT_STARTED
    assert run.to_data() == source_run_data


def test_result_is_immutable_exact_and_deterministically_serializable() -> None:
    plan, run, delegated = canonical_wp045()
    result, _, orchestrator = compose_from_wp045(plan, run, delegated)
    for item in fields(delegated):
        assert getattr(result, item.name) is getattr(delegated, item.name)
    assert result.post_recording_orchestration_decision is not None
    assert result.post_recording_orchestration_decision is orchestrator.results[0]
    first = result.to_data()
    second = result.to_data()
    assert first == second
    encoded = json.loads(json.dumps(first))
    assert encoded["post_recording_orchestration_decision"]["target"] == "capability"
    assert "orchestration_input" not in encoded
    with pytest.raises(FrozenInstanceError):
        result.post_recording_orchestration_decision = None  # type: ignore[misc]


def test_result_rejects_contradictory_orchestration_existence_shapes() -> None:
    plan, run, prepared = canonical_wp045()
    with pytest.raises(PlanStepExecutionOrchestrationCompositionInvariantError):
        PlanStepExecutionOrchestrationCompositionResult(
            **{item.name: getattr(prepared, item.name) for item in fields(prepared)},
            post_recording_orchestration_decision=None,
        )

    _, _, unspecified = canonical_wp045(selected_handling=None)
    decision = compose_from_wp045(plan, run, prepared)[0]
    assert decision.post_recording_orchestration_decision is not None
    with pytest.raises(PlanStepExecutionOrchestrationCompositionInvariantError):
        PlanStepExecutionOrchestrationCompositionResult(
            **{
                item.name: getattr(unspecified, item.name)
                for item in fields(unspecified)
            },
            post_recording_orchestration_decision=(
                decision.post_recording_orchestration_decision
            ),
        )


def test_repeated_invocation_has_no_hidden_deduplication() -> None:
    plan, run, delegated = canonical_wp045()
    wp045 = RecordingWP045(forced=delegated)
    orchestrator = RecordingOrchestrator()
    composer = PlanStepExecutionOrchestrationComposer(
        context_materialization_composer=wp045,
        orchestrator=orchestrator,
    )
    kwargs = {
        "candidates": (),
        "budget": BUDGET,
        "created_at": CONTEXT_CREATED,
        "availability": CAPABILITY_AVAILABLE,
        "execution_input": capability_input(),
        "post_recording_candidates": (),
        "post_recording_budget": POST_RECORDING_BUDGET,
        "post_recording_created_at": POST_RECORDING_CREATED,
        "post_recording_availability": STEP_C_AVAILABLE,
    }
    first = composer.compose(plan, run, "a", **kwargs)  # type: ignore[arg-type]
    second = composer.compose(plan, run, "a", **kwargs)  # type: ignore[arg-type]
    assert len(wp045.calls) == len(orchestrator.calls) == 2
    assert first.post_recording_orchestration_decision is not None
    assert second.post_recording_orchestration_decision is not None
    assert (
        first.post_recording_orchestration_decision.decision_id
        != second.post_recording_orchestration_decision.decision_id
    )


def test_wp046_has_no_forbidden_authority_or_continuation_dependency() -> None:
    source = inspect.getsource(composer_module)
    for forbidden in (
        "PlanStepOrchestrationComposer",
        "StepHandlingSpecification",
        "ContextBlocker(",
        "MemoryContextSource",
        "MemoryService",
        "CapabilityRuntime",
        "IntelligenceRuntime",
        "ExecutionCoordinator",
        "PlanStepExecutionBinder",
        "PlanStepExecutionStartCoordinator",
        "PlanRunReducer",
        "PlanRunController",
        "DeterministicOrchestrationPolicy",
        ".select(",
        "ExecutionRequest",
        "subprocess",
        "socket",
        "open(",
        "while ",
    ):
        assert forbidden not in source
