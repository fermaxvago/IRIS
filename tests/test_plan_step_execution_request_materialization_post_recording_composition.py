"""WP059: one optional successor WP018 request, never execution."""

from __future__ import annotations

import ast
import inspect
import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

import iris.plan_step_execution_request_materialization_post_recording_composition as api
from iris.capabilities import CapabilityInput
from iris.context import ContextBudget
from iris.execution import (
    CapabilityExecutionInput,
    ExecutionRequest,
    IntelligenceExecutionInput,
    MemoryExecutionInput,
    SystemExecutionInput,
)
from iris.intelligence.routing import IntelligenceNeed
from iris.memory import MemoryQuery
from iris.orchestrator import (
    HandlerAvailability,
    HandlingKind,
    HandlingNeed,
    MemoryOperation,
    OrchestrationReason,
    OrchestrationTarget,
)
from iris.plan_handling import StepHandlingPreparationReason
from iris.plan_step_execution_orchestration_post_recording_composition import (
    PlanStepExecutionOrchestrationPostRecordingComposer as Upstream,
)
from iris.plan_step_execution_orchestration_post_recording_composition import (
    PlanStepExecutionOrchestrationPostRecordingCompositionResult as UpstreamResult,
)
from iris.router import RouteTarget
from tests.test_plan_step_execution_binding_post_recording_composition import operands
from tests.test_plan_step_execution_context_materialization_post_recording_composition import (
    CONTEXT_TIME,
)
from tests.test_plan_step_execution_evidence_assessment_composition import unsafe_clone
from tests.test_plan_step_execution_orchestration_post_recording_composition import (
    RecordingWP057,
)
from tests.test_plan_step_execution_orchestration_post_recording_composition import (
    absent as wp058_absent,
)
from tests.test_plan_step_execution_orchestration_post_recording_composition import (
    canonical as wp058_canonical,
)
from tests.test_plan_step_execution_orchestration_post_recording_composition import (
    compose as compose_wp058,
)

Composer = api.PlanStepExecutionRequestMaterializationPostRecordingComposer
Result = api.PlanStepExecutionRequestMaterializationPostRecordingCompositionResult
Invariant = (
    api.PlanStepExecutionRequestMaterializationPostRecordingCompositionInvariantError
)


class RecordingWP058(Upstream):
    def __init__(self, result: object, error: Exception | None = None) -> None:
        super().__init__(context_materialization_composer=RecordingWP057(None))
        self.result = result
        self.error = error
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def compose(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return self.result


def prepared() -> tuple[Any, Any, UpstreamResult]:
    plan, run, wp057 = wp058_canonical()
    result, _, _ = compose_wp058(plan, run, wp057)
    return plan, run, result


def operational_variant(
    kind: HandlingKind,
) -> tuple[Any, Any, UpstreamResult, HandlerAvailability]:
    plan, run, original = prepared()
    if kind is HandlingKind.CAPABILITY:
        return plan, run, original, HandlerAvailability(capability=True)
    plan = replace(
        plan,
        steps=tuple(
            replace(step, required_handling=kind) if step.step_id == "d" else step
            for step in plan.steps
        ),
    )
    preparation = original.post_recording_execution_handling_preparation
    decision = original.post_recording_execution_orchestration_decision
    assert preparation is not None and decision is not None
    old_need = preparation.handling_need
    assert old_need is not None
    details: dict[str, object] = {}
    if kind is HandlingKind.SYSTEM:
        details["system_route"] = RouteTarget.SYSTEM_STATUS
    elif kind is HandlingKind.MEMORY:
        details["memory_operation"] = MemoryOperation.RECALL
    elif kind is HandlingKind.INTELLIGENCE:
        details["intelligence_need"] = IntelligenceNeed()
    need = HandlingNeed(old_need.need_id, kind, **details)
    reason = {
        HandlingKind.SYSTEM: OrchestrationReason.DETERMINISTIC_SYSTEM_HANDLING,
        HandlingKind.MEMORY: OrchestrationReason.EXPLICIT_MEMORY_OPERATION,
        HandlingKind.INTELLIGENCE: OrchestrationReason.INTELLIGENCE_REQUIRED,
    }[kind]
    new_preparation = replace(
        preparation,
        reason=StepHandlingPreparationReason.SPECIFICATION_COMPLETED_HANDLING,
        handling_kind=kind,
        handling_need=need,
    )
    new_decision = replace(
        decision,
        target=OrchestrationTarget(kind.value),
        reason=reason,
        requirement=need,
    )
    upstream = unsafe_clone(
        original,
        post_recording_execution_handling_preparation=new_preparation,
        post_recording_execution_orchestration_decision=new_decision,
    )
    availability = HandlerAvailability(**{kind.value: True})
    return plan, run, upstream, availability


def call(
    plan: Any,
    run: Any,
    upstream: object,
    *,
    successor_input: object = None,
    clock: Any = None,
    execution_id_factory: Any = None,
    upstream_error: Exception | None = None,
    **overrides: object,
) -> tuple[Result, RecordingWP058]:
    wp058 = RecordingWP058(upstream, upstream_error)
    fallback = upstream if isinstance(upstream, UpstreamResult) else prepared()[2]
    kwargs = operands(fallback)
    kwargs.update(
        successor_context_candidates=(),
        successor_context_budget=ContextBudget(2),
        successor_context_uncertainties=(),
        successor_context_created_at=CONTEXT_TIME,
        successor_orchestration_availability=HandlerAvailability(capability=True),
        successor_execution_input=successor_input,
    )
    kwargs.update(overrides)
    decision = (
        upstream.post_recording_execution_orchestration_decision
        if isinstance(upstream, UpstreamResult)
        else None
    )
    default_time = (
        CONTEXT_TIME if decision is None else decision.created_at + timedelta(seconds=1)
    )
    composer = Composer(
        orchestration_composer=wp058,
        clock=(lambda: default_time) if clock is None else clock,
        execution_id_factory=(
            (lambda: "wp059-execution")
            if execution_id_factory is None
            else execution_id_factory
        ),
    )
    return composer.compose(plan, run, "a", **kwargs), wp058


def test_public_contract_and_constructor() -> None:
    assert api.__all__ == [
        "PlanStepExecutionRequestMaterializationPostRecordingComposer",
        "PlanStepExecutionRequestMaterializationPostRecordingCompositionResult",
        "PlanStepExecutionRequestMaterializationPostRecordingCompositionError",
        "PlanStepExecutionRequestMaterializationPostRecordingCompositionInvariantError",
    ]
    assert issubclass(Result, UpstreamResult)
    assert issubclass(
        Invariant,
        api.PlanStepExecutionRequestMaterializationPostRecordingCompositionError,
    )
    assert list(inspect.signature(Composer.compose).parameters) == [
        *inspect.signature(Upstream.compose).parameters,
        "successor_execution_input",
    ]
    assert (
        inspect.signature(Composer.compose)
        .parameters["successor_execution_input"]
        .default
        is None
    )
    with pytest.raises(TypeError):
        Composer(orchestration_composer=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Composer(orchestration_composer=RecordingWP058(None), clock=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Composer(
            orchestration_composer=RecordingWP058(None),
            execution_id_factory=object(),
        )  # type: ignore[arg-type]


def test_operational_request_exact_lineage_forwarding_and_serialization() -> None:
    plan, run, upstream = prepared()
    operand = CapabilityExecutionInput()
    calls = {"clock": 0, "id": 0}

    def now() -> Any:
        calls["clock"] += 1
        return upstream.post_recording_execution_orchestration_decision.created_at

    def new_id() -> str:
        calls["id"] += 1
        return "successor-execution"

    result, wp058 = call(
        plan,
        run,
        upstream,
        successor_input=operand,
        clock=now,
        execution_id_factory=new_id,
    )
    assert len(wp058.calls) == 1
    assert wp058.calls[0][0] == (plan, run, "a")
    assert wp058.calls[0][0][0] is plan and wp058.calls[0][0][1] is run
    assert "successor_execution_input" not in wp058.calls[0][1]
    assert calls == {"clock": 1, "id": 1}
    request = result.post_recording_execution_successor_request
    assert isinstance(request, ExecutionRequest)
    assert request.subject is upstream.post_recording_execution_work_subject
    assert request.context is upstream.post_recording_execution_context_snapshot
    assert request.decision is upstream.post_recording_execution_orchestration_decision
    assert request.execution_input is operand
    assert request.created_at == request.decision.created_at
    assert all(
        getattr(result, field.name) is getattr(upstream, field.name)
        for field in fields(UpstreamResult)
    )
    assert (
        result.to_data()["post_recording_execution_successor_request"]
        == request.to_trace()
    )
    assert result.to_data() == result.to_data()
    json.dumps(result.to_data())
    with pytest.raises(FrozenInstanceError):
        result.post_recording_execution_successor_request = None  # type: ignore[misc]
    assert not hasattr(result, "__dict__")


@pytest.mark.parametrize(
    ("kind", "operand"),
    [
        (HandlingKind.SYSTEM, SystemExecutionInput()),
        (HandlingKind.MEMORY, MemoryExecutionInput(memory_id="mem-1")),
        (HandlingKind.CAPABILITY, CapabilityExecutionInput()),
        (
            HandlingKind.INTELLIGENCE,
            IntelligenceExecutionInput(content="analyze", resources=()),
        ),
    ],
)
def test_every_operational_target_uses_canonical_wp018_input(
    kind: HandlingKind, operand: object
) -> None:
    plan, run, upstream, availability = operational_variant(kind)
    result, wp058 = call(
        plan,
        run,
        upstream,
        successor_input=operand,
        successor_orchestration_availability=availability,
    )
    assert len(wp058.calls) == 1
    request = result.post_recording_execution_successor_request
    assert request is not None
    assert request.decision.target is OrchestrationTarget(kind.value)
    assert request.execution_input is operand


@pytest.mark.parametrize(
    "kind", [HandlingKind.SYSTEM, HandlingKind.MEMORY, HandlingKind.INTELLIGENCE]
)
def test_wrong_target_input_is_not_coerced(kind: HandlingKind) -> None:
    plan, run, upstream, availability = operational_variant(kind)
    with pytest.raises(TypeError):
        call(
            plan,
            run,
            upstream,
            successor_input=CapabilityExecutionInput(),
            successor_orchestration_availability=availability,
        )


def test_memory_operand_rules_are_delegated_to_wp018() -> None:
    plan, run, upstream, availability = operational_variant(HandlingKind.MEMORY)
    for invalid in [
        MemoryExecutionInput(),
        MemoryExecutionInput(memory_id="mem-1", query=MemoryQuery()),
    ]:
        with pytest.raises(ValueError):
            call(
                plan,
                run,
                upstream,
                successor_input=invalid,
                successor_orchestration_availability=availability,
            )


@pytest.mark.parametrize(
    "kind", [None, HandlingKind.SYSTEM, HandlingKind.MEMORY, HandlingKind.INTELLIGENCE]
)
def test_nonprepared_handling_abstains_without_input_or_clock(
    kind: HandlingKind | None,
) -> None:
    plan, run, wp057 = wp058_canonical(kind)
    upstream, _, _ = compose_wp058(plan, run, wp057)
    assert upstream.post_recording_execution_orchestration_decision is None
    result, _ = call(
        plan,
        run,
        upstream,
        successor_input=object(),
        clock=lambda: (_ for _ in ()).throw(AssertionError("clock called")),
        execution_id_factory=lambda: (_ for _ in ()).throw(AssertionError("id called")),
        successor_orchestration_availability=object(),
    )
    assert result.post_recording_execution_successor_request is None


def test_absence_preserves_lazy_validation_and_skips_clock_and_id() -> None:
    plan, run, wp057 = wp058_absent()
    upstream, _, _ = compose_wp058(plan, run, wp057)
    marker = object()

    def forbidden() -> Any:
        raise AssertionError("unreachable request dependency was invoked")

    result, wp058 = call(
        plan,
        run,
        upstream,
        successor_input=marker,
        clock=forbidden,
        execution_id_factory=forbidden,
        post_recording_execution_input=marker,
        successor_context_candidates=marker,
        successor_context_budget=marker,
        successor_context_created_at=marker,
        successor_orchestration_availability=marker,
    )
    assert len(wp058.calls) == 1
    assert wp058.calls[0][1]["post_recording_execution_input"] is marker
    assert result.post_recording_execution_successor_request is None
    assert result.to_data()["post_recording_execution_successor_request"] is None


def test_terminal_unsatisfied_is_real_decision_but_no_request() -> None:
    plan, run, wp057 = wp058_canonical()
    upstream, _, _ = compose_wp058(plan, run, wp057, availability=HandlerAvailability())
    assert (
        upstream.post_recording_execution_orchestration_decision.target
        is OrchestrationTarget.UNSATISFIED
    )
    result, _ = call(
        plan,
        run,
        upstream,
        successor_input=object(),
        clock=lambda: (_ for _ in ()).throw(AssertionError("clock called")),
        execution_id_factory=lambda: (_ for _ in ()).throw(AssertionError("id called")),
        successor_orchestration_availability=HandlerAvailability(),
    )
    assert (
        result.post_recording_execution_orchestration_decision
        is upstream.post_recording_execution_orchestration_decision
    )
    assert result.post_recording_execution_successor_request is None


@pytest.mark.parametrize("successor_input", [None, object()])
def test_bad_operational_input_fails_explicitly(successor_input: object) -> None:
    plan, run, upstream = prepared()
    with pytest.raises((TypeError, ValueError)):
        call(plan, run, upstream, successor_input=successor_input)


def test_bad_factory_identifier_fails_without_retry() -> None:
    plan, run, upstream = prepared()
    calls = 0

    def bad_id() -> str:
        nonlocal calls
        calls += 1
        return " "

    with pytest.raises(Invariant, match="noncanonical identifier"):
        call(
            plan,
            run,
            upstream,
            successor_input=CapabilityExecutionInput(),
            execution_id_factory=bad_id,
            clock=lambda: (_ for _ in ()).throw(AssertionError("clock called")),
        )
    assert calls == 1


@pytest.mark.parametrize("collision", ["execution-1", "step-c-execution-1"])
def test_inherited_execution_id_collision_fails_closed(collision: str) -> None:
    plan, run, upstream = prepared()
    with pytest.raises(Invariant, match="collides"):
        call(
            plan,
            run,
            upstream,
            successor_input=CapabilityExecutionInput(),
            execution_id_factory=lambda: collision,
        )


@pytest.mark.parametrize("identity", ["subject", "context", "decision"])
def test_successor_identity_collision_fails_closed(identity: str) -> None:
    plan, run, upstream = prepared()
    decision = upstream.post_recording_execution_orchestration_decision
    ids = {
        "subject": upstream.post_recording_execution_work_subject.subject_id,
        "context": upstream.post_recording_execution_context_snapshot.snapshot_id,
        "decision": decision.decision_id,
    }
    with pytest.raises(Invariant, match="collides"):
        call(
            plan,
            run,
            upstream,
            successor_input=CapabilityExecutionInput(),
            execution_id_factory=lambda: ids[identity],
        )


def test_clock_must_be_utc_and_not_predate_decision() -> None:
    plan, run, upstream = prepared()
    decision_time = upstream.post_recording_execution_orchestration_decision.created_at
    for timestamp, error in [
        (decision_time - timedelta(seconds=1), ValueError),
        (decision_time.replace(tzinfo=None), ValueError),
        (decision_time.astimezone(timezone(timedelta(hours=-6))), Invariant),
    ]:
        with pytest.raises(error):
            call(
                plan,
                run,
                upstream,
                successor_input=CapabilityExecutionInput(),
                clock=lambda timestamp=timestamp: timestamp,
            )


def test_dependency_failures_propagate_without_retry() -> None:
    plan, run, upstream = prepared()
    failure = RuntimeError("dependency failed")
    wp058 = RecordingWP058(upstream, failure)
    composer = Composer(orchestration_composer=wp058)
    kwargs = operands(upstream)
    kwargs.update(
        successor_context_candidates=(),
        successor_context_budget=ContextBudget(2),
        successor_context_created_at=CONTEXT_TIME,
        successor_orchestration_availability=HandlerAvailability(capability=True),
    )
    with pytest.raises(RuntimeError) as raised:
        composer.compose(plan, run, "a", **kwargs)
    assert raised.value is failure and len(wp058.calls) == 1
    for dependency in ["clock", "execution_id_factory"]:
        injected = {dependency: lambda: (_ for _ in ()).throw(failure)}
        with pytest.raises(RuntimeError) as raised:
            call(
                plan,
                run,
                upstream,
                successor_input=CapabilityExecutionInput(),
                **injected,
            )
        assert raised.value is failure


def test_malformed_upstream_fails_before_request_dependencies() -> None:
    plan, run, upstream = prepared()
    for malformed in [
        object(),
        unsafe_clone(upstream, post_recording_execution_work_subject=None),
        unsafe_clone(upstream, post_recording_execution_orchestration_decision=None),
        unsafe_clone(upstream, post_recording_execution_context_snapshot=None),
        unsafe_clone(upstream, post_recording_execution_handling_preparation=None),
    ]:
        with pytest.raises(Invariant):
            call(
                plan,
                run,
                malformed,
                successor_input=CapabilityExecutionInput(),
                clock=lambda: (_ for _ in ()).throw(AssertionError("clock called")),
                execution_id_factory=lambda: (_ for _ in ()).throw(
                    AssertionError("id called")
                ),
            )


def test_direct_forged_result_fails_presence_and_request_identity() -> None:
    plan, run, upstream = prepared()
    with pytest.raises(Invariant):
        Result(
            **{
                field.name: getattr(upstream, field.name)
                for field in fields(UpstreamResult)
            },
            post_recording_execution_successor_request=None,
        )
    valid, _ = call(plan, run, upstream, successor_input=CapabilityExecutionInput())
    request = valid.post_recording_execution_successor_request
    assert request is not None
    foreign = replace(request, subject=replace(request.subject))
    with pytest.raises(Invariant):
        replace(valid, post_recording_execution_successor_request=foreign)
    forged = unsafe_clone(request, execution_id="execution-1")
    with pytest.raises(Invariant):
        replace(valid, post_recording_execution_successor_request=forged)
    forged_time = unsafe_clone(
        request, created_at=request.created_at.astimezone(timezone(timedelta(hours=-6)))
    )
    with pytest.raises(Invariant):
        replace(valid, post_recording_execution_successor_request=forged_time)


def test_nested_noncanonical_input_is_rejected_without_repair() -> None:
    plan, run, upstream = prepared()
    result, _ = call(plan, run, upstream, successor_input=CapabilityExecutionInput())
    request = result.post_recording_execution_successor_request
    assert request is not None
    invocation = CapabilityInput()
    malformed_invocation = unsafe_clone(invocation, payload={"bad": "mutable"})
    malformed_input = unsafe_clone(
        CapabilityExecutionInput(), invocation=malformed_invocation
    )
    forged = unsafe_clone(request, execution_input=malformed_input)
    with pytest.raises(Invariant):
        replace(result, post_recording_execution_successor_request=forged)
    assert isinstance(malformed_invocation.payload, dict)


def test_repeated_calls_are_independent() -> None:
    plan, run, upstream = prepared()
    first, _ = call(plan, run, upstream, successor_input=CapabilityExecutionInput())
    second, _ = call(plan, run, upstream, successor_input=CapabilityExecutionInput())
    assert (
        first.post_recording_execution_successor_request
        is not second.post_recording_execution_successor_request
    )


def test_forbidden_authorities_are_absent() -> None:
    package = Path(
        "iris/plan_step_execution_request_materialization_post_recording_composition"
    )
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in package.glob("*.py")
    )
    tree = ast.parse(source)
    imports = [
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    ]
    assert not any(
        forbidden in module
        for module in imports
        for forbidden in (
            "plan_step_execution_binding",
            "plan_step_execution_start",
            "plan_run_reducer",
            "plan_run_advancement",
            "plan_step_execution_result_recording",
        )
    )
