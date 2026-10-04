"""WP047 bounded post-recording ExecutionRequest materialization."""

from __future__ import annotations

import inspect
import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime, timedelta
from itertools import count
from typing import Any, cast

import pytest

import iris.plan_step_execution_request_materialization_composition as public_api
import iris.plan_step_execution_request_materialization_composition.composer as composer_module
from iris.context import (
    ContextBudget,
    ContextCandidate,
    ContextUncertainty,
    ResolutionStatus,
)
from iris.execution import CapabilityExecutionInput, ExecutionRequest
from iris.execution.models import ExecutionInput
from iris.orchestrator import HandlerAvailability, HandlingKind, OrchestrationTarget
from iris.plan_runs import PlanRun, StepProgressState
from iris.plan_step_execution_orchestration_composition import (
    PlanStepExecutionOrchestrationComposer,
    PlanStepExecutionOrchestrationCompositionResult,
)
from iris.plan_step_execution_request_materialization_composition import (
    PlanStepExecutionRequestMaterializationComposer,
    PlanStepExecutionRequestMaterializationCompositionError,
    PlanStepExecutionRequestMaterializationCompositionInvariantError,
    PlanStepExecutionRequestMaterializationCompositionResult,
)
from iris.planning import Plan
from tests.test_plan_step_execution_context_materialization_composition import (
    POST_RECORDING_BUDGET,
    POST_RECORDING_CREATED,
)
from tests.test_plan_step_execution_evidence_assessment_composition import (
    BUDGET,
    CAPABILITY_AVAILABLE,
    CONTEXT_CREATED,
    capability_input,
    unsafe_clone,
)
from tests.test_plan_step_execution_orchestration_composition import (
    ORCHESTRATED,
    STEP_C_AVAILABLE,
    STEP_C_UNAVAILABLE,
    RecordingWP045,
    _context_case,
    canonical_wp045,
    compose_from_wp045,
    no_subject_wp045,
)

REQUESTED = ORCHESTRATED + timedelta(seconds=1)


class RecordingWP046(PlanStepExecutionOrchestrationComposer):
    def __init__(
        self,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__(context_materialization_composer=RecordingWP045())
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
        post_recording_availability: HandlerAvailability,
    ) -> PlanStepExecutionOrchestrationCompositionResult:
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
                post_recording_availability,
            )
        )
        if self.error is not None:
            raise self.error
        return cast(PlanStepExecutionOrchestrationCompositionResult, self.forced)


def canonical_wp046(
    *,
    selected_handling: HandlingKind | None = HandlingKind.CAPABILITY,
    post_availability: HandlerAvailability = STEP_C_AVAILABLE,
    post_candidates: tuple[ContextCandidate, ...] = (),
    post_budget: ContextBudget = POST_RECORDING_BUDGET,
    post_uncertainties: tuple[ContextUncertainty, ...] = (),
) -> tuple[Plan, PlanRun, PlanStepExecutionOrchestrationCompositionResult]:
    plan, run, delegated = canonical_wp045(
        selected_handling=selected_handling,
        post_candidates=post_candidates,
        post_budget=post_budget,
        post_uncertainties=post_uncertainties,
    )
    result, _, _ = compose_from_wp045(
        plan,
        run,
        delegated,
        post_candidates=post_candidates,
        post_budget=post_budget,
        post_uncertainties=post_uncertainties,
        post_availability=post_availability,
    )
    return plan, run, result


def no_subject_wp046() -> tuple[
    Plan,
    PlanRun,
    PlanStepExecutionOrchestrationCompositionResult,
]:
    plan, run, delegated = no_subject_wp045()
    result, _, _ = compose_from_wp045(plan, run, delegated)
    assert result.post_recording_orchestration_decision is None
    return plan, run, result


def compose_from_wp046(
    plan: Plan,
    run: PlanRun,
    delegated: object,
    *,
    inherited_candidates: tuple[ContextCandidate, ...] = (),
    inherited_budget: ContextBudget = BUDGET,
    inherited_uncertainties: tuple[ContextUncertainty, ...] = (),
    inherited_created_at: datetime = CONTEXT_CREATED,
    inherited_availability: HandlerAvailability = CAPABILITY_AVAILABLE,
    inherited_execution_input: CapabilityExecutionInput | None = None,
    post_candidates: tuple[ContextCandidate, ...] = (),
    post_budget: ContextBudget = POST_RECORDING_BUDGET,
    post_uncertainties: tuple[ContextUncertainty, ...] = (),
    post_created_at: datetime = POST_RECORDING_CREATED,
    post_availability: HandlerAvailability = STEP_C_AVAILABLE,
    post_execution_input: object = None,
    clock: Any = lambda: REQUESTED,
    id_factory: Any = lambda: "step-c-execution-1",
) -> tuple[
    PlanStepExecutionRequestMaterializationCompositionResult,
    RecordingWP046,
]:
    wp046 = RecordingWP046(forced=delegated)
    supplied_input = (
        capability_input()
        if inherited_execution_input is None
        else inherited_execution_input
    )
    result = PlanStepExecutionRequestMaterializationComposer(
        orchestration_composer=wp046,
        clock=clock,
        execution_id_factory=id_factory,
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
        post_recording_execution_input=cast(Any, post_execution_input),
    )
    return result, wp046


def test_public_api_constructor_signature_and_exact_exports() -> None:
    assert set(public_api.__all__) == {
        "PlanStepExecutionRequestMaterializationComposer",
        "PlanStepExecutionRequestMaterializationCompositionResult",
        "PlanStepExecutionRequestMaterializationCompositionError",
        "PlanStepExecutionRequestMaterializationCompositionInvariantError",
    }
    assert issubclass(
        PlanStepExecutionRequestMaterializationCompositionInvariantError,
        PlanStepExecutionRequestMaterializationCompositionError,
    )
    assert tuple(
        inspect.signature(
            PlanStepExecutionRequestMaterializationComposer.compose
        ).parameters
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
        "post_recording_execution_input",
    )
    with pytest.raises(TypeError, match="orchestration_composer"):
        PlanStepExecutionRequestMaterializationComposer()  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="orchestration_composer"):
        PlanStepExecutionRequestMaterializationComposer(
            orchestration_composer=cast(Any, object())
        )
    with pytest.raises(TypeError, match="clock"):
        PlanStepExecutionRequestMaterializationComposer(
            orchestration_composer=RecordingWP046(), clock=cast(Any, object())
        )
    with pytest.raises(TypeError, match="execution_id_factory"):
        PlanStepExecutionRequestMaterializationComposer(
            orchestration_composer=RecordingWP046(),
            execution_id_factory=cast(Any, object()),
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
def test_invalid_direct_inputs_fail_before_wp046(
    position: int,
    invalid: object,
) -> None:
    plan, run, delegated = no_subject_wp046()
    wp046 = RecordingWP046(forced=delegated)
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
        PlanStepExecutionRequestMaterializationComposer(
            orchestration_composer=wp046
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
    assert wp046.calls == []


def test_wp046_invoked_once_with_exact_inputs_and_step_c_input_separate() -> None:
    plan, run, delegated = canonical_wp046()
    inherited_input = capability_input()
    step_c_input = capability_input()
    inherited_availability = HandlerAvailability(system=True)
    post_availability = HandlerAvailability(capability=True)
    result, wp046 = compose_from_wp046(
        plan,
        run,
        delegated,
        inherited_availability=inherited_availability,
        inherited_execution_input=inherited_input,
        post_availability=post_availability,
        post_execution_input=step_c_input,
    )
    assert len(wp046.calls) == 1
    assert wp046.calls[0][7] is inherited_availability
    assert wp046.calls[0][8] is inherited_input
    assert wp046.calls[0][13] is post_availability
    assert all(item is not step_c_input for item in wp046.calls[0])
    assert result.post_recording_execution_request is not None
    assert result.post_recording_execution_request.execution_input is step_c_input


def test_no_decision_skips_id_and_clock_and_preserves_exact_wp046() -> None:
    plan, run, delegated = no_subject_wp046()
    result, wp046 = compose_from_wp046(
        plan,
        run,
        delegated,
        post_execution_input=object(),
        id_factory=lambda: pytest.fail("ID factory must not run"),
        clock=lambda: pytest.fail("request clock must not run"),
    )
    assert len(wp046.calls) == 1
    assert result.post_recording_execution_request is None
    for item in fields(delegated):
        assert getattr(result, item.name) is getattr(delegated, item.name)


@pytest.mark.parametrize(
    ("handling", "status"),
    [
        (None, "handling_unspecified"),
        (HandlingKind.SYSTEM, "insufficient_detail"),
    ],
)
def test_nonprepared_step_c_preserves_real_artifacts_without_request(
    handling: HandlingKind | None,
    status: str,
) -> None:
    plan, run, delegated = canonical_wp046(selected_handling=handling)
    assert delegated.post_recording_work_subject is not None
    assert delegated.post_recording_context_snapshot is not None
    assert delegated.post_recording_handling_preparation is not None
    assert delegated.post_recording_handling_preparation.status.value == status
    assert delegated.post_recording_orchestration_decision is None
    result, _ = compose_from_wp046(
        plan,
        run,
        delegated,
        id_factory=lambda: pytest.fail("ID factory must not run"),
        clock=lambda: pytest.fail("request clock must not run"),
    )
    assert result.post_recording_execution_request is None
    assert result.post_recording_work_subject is delegated.post_recording_work_subject
    assert (
        result.post_recording_context_snapshot
        is delegated.post_recording_context_snapshot
    )


def test_capability_request_preserves_exact_artifacts_and_call_cardinality() -> None:
    plan, run, delegated = canonical_wp046()
    step_c_input = capability_input()
    id_calls: list[None] = []
    clock_calls: list[None] = []

    def next_id() -> str:
        id_calls.append(None)
        return "step-c-execution"

    def request_clock() -> datetime:
        clock_calls.append(None)
        return REQUESTED

    result, _ = compose_from_wp046(
        plan,
        run,
        delegated,
        post_execution_input=step_c_input,
        id_factory=next_id,
        clock=request_clock,
    )
    request = result.post_recording_execution_request
    assert isinstance(request, ExecutionRequest)
    assert id_calls == [None]
    assert clock_calls == [None]
    assert request.subject is delegated.post_recording_work_subject
    assert request.context is delegated.post_recording_context_snapshot
    assert request.decision is delegated.post_recording_orchestration_decision
    assert request.execution_input is step_c_input
    assert request.execution_id == "step-c-execution"
    assert request is result.post_recording_execution_request


@pytest.mark.parametrize("bad_input", [None, object()])
def test_capability_invalid_input_preserves_wp018_error(bad_input: object) -> None:
    plan, run, delegated = canonical_wp046()
    with pytest.raises(TypeError, match="CapabilityExecutionInput"):
        compose_from_wp046(
            plan,
            run,
            delegated,
            post_execution_input=bad_input,
        )


def test_unavailable_capability_materializes_real_terminal_request() -> None:
    plan, run, delegated = canonical_wp046(post_availability=STEP_C_UNAVAILABLE)
    decision = delegated.post_recording_orchestration_decision
    assert decision is not None
    assert decision.target is OrchestrationTarget.UNSATISFIED
    result, _ = compose_from_wp046(
        plan,
        run,
        delegated,
        post_availability=STEP_C_UNAVAILABLE,
    )
    request = result.post_recording_execution_request
    assert request is not None
    assert request.decision is decision
    assert request.execution_input is None


def test_terminal_decision_with_non_none_input_preserves_wp018_error() -> None:
    plan, run, delegated = canonical_wp046(post_availability=STEP_C_UNAVAILABLE)
    with pytest.raises(ValueError, match="terminal decisions"):
        compose_from_wp046(
            plan,
            run,
            delegated,
            post_availability=STEP_C_UNAVAILABLE,
            post_execution_input=capability_input(),
        )


@pytest.mark.parametrize("request_time", [ORCHESTRATED, REQUESTED])
def test_equal_or_later_request_time_is_accepted(request_time: datetime) -> None:
    plan, run, delegated = canonical_wp046()
    result, _ = compose_from_wp046(
        plan,
        run,
        delegated,
        post_execution_input=capability_input(),
        clock=lambda: request_time,
    )
    assert result.post_recording_execution_request is not None
    assert result.post_recording_execution_request.created_at == request_time


def test_request_time_before_decision_preserves_wp018_error() -> None:
    plan, run, delegated = canonical_wp046()
    with pytest.raises(ValueError, match="predate"):
        compose_from_wp046(
            plan,
            run,
            delegated,
            post_execution_input=capability_input(),
            clock=lambda: ORCHESTRATED - timedelta(microseconds=1),
        )


def test_step_c_execution_id_must_not_reuse_inherited_step_b_id() -> None:
    plan, run, delegated = canonical_wp046()
    inherited = delegated.execution_request
    assert inherited is not None
    with pytest.raises(
        PlanStepExecutionRequestMaterializationCompositionInvariantError,
        match="must not reuse",
    ):
        compose_from_wp046(
            plan,
            run,
            delegated,
            post_execution_input=capability_input(),
            id_factory=lambda: inherited.execution_id,
        )


def test_wp046_exception_propagates_unchanged_before_id_and_clock() -> None:
    plan, run, _ = no_subject_wp046()
    failure = RuntimeError("wp046 failed")
    wp046 = RecordingWP046(error=failure)
    with pytest.raises(RuntimeError, match="wp046 failed") as raised:
        PlanStepExecutionRequestMaterializationComposer(
            orchestration_composer=wp046,
            execution_id_factory=lambda: pytest.fail("must not generate ID"),
            clock=lambda: pytest.fail("must not read clock"),
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
    assert len(wp046.calls) == 1


@pytest.mark.parametrize(
    "mismatch",
    ["type", "source", "missing_decision", "context_budget", "context_time"],
)
def test_malformed_wp046_result_fails_before_request_materialization(
    mismatch: str,
) -> None:
    plan, run, delegated = canonical_wp046()
    forced: object = delegated
    if mismatch == "type":
        forced = object()
    elif mismatch == "source":
        forced = unsafe_clone(
            delegated,
            assessment=replace(delegated.assessment, plan_id="foreign-plan"),
        )
    elif mismatch == "missing_decision":
        forced = unsafe_clone(delegated, post_recording_orchestration_decision=None)
    else:
        context = delegated.post_recording_context_snapshot
        assert context is not None
        changed_context = replace(
            context,
            budget=(
                ContextBudget(context.budget.max_items + 1)
                if mismatch == "context_budget"
                else context.budget
            ),
            created_at=(
                context.created_at + timedelta(seconds=1)
                if mismatch == "context_time"
                else context.created_at
            ),
        )
        decision = delegated.post_recording_orchestration_decision
        assert decision is not None
        forced = unsafe_clone(
            delegated,
            post_recording_context_snapshot=changed_context,
            post_recording_orchestration_decision=replace(
                decision,
                context_snapshot_id=changed_context.snapshot_id,
                created_at=max(decision.created_at, changed_context.created_at),
            ),
        )
    with pytest.raises(
        PlanStepExecutionRequestMaterializationCompositionInvariantError
    ):
        compose_from_wp046(
            plan,
            run,
            forced,
            post_execution_input=capability_input(),
            id_factory=lambda: pytest.fail("must not generate ID"),
            clock=lambda: pytest.fail("must not read clock"),
        )


@pytest.mark.parametrize("status", list(ResolutionStatus))
def test_context_status_introduces_no_wp047_policy(status: ResolutionStatus) -> None:
    candidates, budget, uncertainties = _context_case(status)
    plan, run, delegated = canonical_wp046(
        post_candidates=candidates,
        post_budget=budget,
        post_uncertainties=uncertainties,
    )
    assert delegated.post_recording_context_snapshot is not None
    assert delegated.post_recording_context_snapshot.status is status
    result, _ = compose_from_wp046(
        plan,
        run,
        delegated,
        post_candidates=candidates,
        post_budget=budget,
        post_uncertainties=uncertainties,
        post_execution_input=capability_input(),
    )
    assert result.post_recording_execution_request is not None


def test_a_b_c_artifacts_remain_distinct_and_step_c_stays_inert() -> None:
    plan, run, delegated = canonical_wp046()
    source_run_data = run.to_data()
    result, _ = compose_from_wp046(
        plan,
        run,
        delegated,
        post_execution_input=capability_input(),
    )
    request = result.post_recording_execution_request
    assert request is not None
    assert request is not result.execution_request
    assert request.execution_id != result.execution_request.execution_id  # type: ignore[union-attr]
    assert (
        result.post_recording_orchestration_decision
        is not result.orchestration_decision
    )
    advancement = result.post_recording_advancement_result
    assert advancement is not None
    selected = advancement.control_decision.selected_step_id
    assert selected is not None
    progress = {item.step_id: item for item in advancement.updated_run.step_progress}
    assert progress[selected].state is StepProgressState.NOT_STARTED
    assert run.to_data() == source_run_data


def test_result_is_immutable_exact_and_deterministically_serializable() -> None:
    plan, run, delegated = canonical_wp046()
    result, _ = compose_from_wp046(
        plan,
        run,
        delegated,
        post_execution_input=capability_input(),
    )
    for item in fields(delegated):
        assert getattr(result, item.name) is getattr(delegated, item.name)
    first = result.to_data()
    assert first == result.to_data()
    encoded = json.loads(json.dumps(first))
    assert encoded["post_recording_execution_request"]["execution_id"] == (
        "step-c-execution-1"
    )
    with pytest.raises(FrozenInstanceError):
        result.post_recording_execution_request = None  # type: ignore[misc]


def test_result_rejects_contradictory_request_existence_and_identity() -> None:
    plan, run, delegated = canonical_wp046()
    with pytest.raises(
        PlanStepExecutionRequestMaterializationCompositionInvariantError
    ):
        PlanStepExecutionRequestMaterializationCompositionResult(
            **{item.name: getattr(delegated, item.name) for item in fields(delegated)},
            post_recording_execution_request=None,
        )

    result, _ = compose_from_wp046(
        plan,
        run,
        delegated,
        post_execution_input=capability_input(),
    )
    request = result.post_recording_execution_request
    assert request is not None
    foreign = unsafe_clone(request, subject=delegated.work_subject)
    with pytest.raises(
        PlanStepExecutionRequestMaterializationCompositionInvariantError
    ):
        PlanStepExecutionRequestMaterializationCompositionResult(
            **{item.name: getattr(delegated, item.name) for item in fields(delegated)},
            post_recording_execution_request=foreign,
        )


def test_repeated_invocations_create_fresh_requests_without_deduplication() -> None:
    plan, run, delegated = canonical_wp046()
    identifiers = count(1)
    wp046 = RecordingWP046(forced=delegated)
    composer = PlanStepExecutionRequestMaterializationComposer(
        orchestration_composer=wp046,
        clock=lambda: REQUESTED,
        execution_id_factory=lambda: f"step-c-execution-{next(identifiers)}",
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
        "post_recording_execution_input": capability_input(),
    }
    first = composer.compose(plan, run, "a", **kwargs)  # type: ignore[arg-type]
    second = composer.compose(plan, run, "a", **kwargs)  # type: ignore[arg-type]
    assert len(wp046.calls) == 2
    assert first.post_recording_execution_request is not None
    assert second.post_recording_execution_request is not None
    assert (
        first.post_recording_execution_request.execution_id
        != second.post_recording_execution_request.execution_id
    )


def test_wp047_has_no_forbidden_authority_or_continuation_dependency() -> None:
    source = inspect.getsource(composer_module)
    for forbidden in (
        "PlanStepExecutionRequestMaterializer",
        "PlanStepOrchestrationComposer",
        "PlanStepExecutionBinder",
        "PlanStepExecutionBinding",
        "PlanStepExecutionStartCoordinator",
        "ExecutionCoordinator",
        "CapabilityRuntime",
        "IntelligenceRuntime",
        "PlanRunReducer",
        "PlanRunController",
        "handler_registry",
        "subprocess",
        "socket",
        "while ",
    ):
        assert forbidden not in source
