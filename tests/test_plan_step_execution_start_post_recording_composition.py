"""WP049: validated WP048 -> WP025 -> exact start result -> STOP.

Unsafe clones are explicitly adversarial, noncanonical boundary returns. They
prove fail-closed validation, never canonical reachability. Handlers only record
in-memory calls; these tests do not perform external execution.
"""

from __future__ import annotations

import ast
import inspect
import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

import iris.plan_step_execution_start.coordinator as start_module
import iris.plan_step_execution_start_post_recording_composition as api
from iris.execution import (
    ExecutionCoordinator,
    ExecutionFailure,
    ExecutionStatus,
    HandlerOutcome,
)
from iris.orchestrator import HandlerAvailability, HandlingKind, OrchestrationTarget
from iris.plan_runs import PlanRunInvariantError, StepProgressState
from iris.plan_step_execution_binding import StalePlanStepExecutionBindingError
from iris.plan_step_execution_binding_post_recording_composition import (
    PlanStepExecutionBindingPostRecordingComposer,
    PlanStepExecutionBindingPostRecordingCompositionResult,
)
from iris.plan_step_execution_start import (
    PlanStepExecutionInvocationError,
    PlanStepExecutionStartCoordinator,
    PlanStepExecutionStartGenerationError,
    PlanStepExecutionStartResult,
)
from iris.plan_step_execution_start_post_recording_composition import (
    PlanStepExecutionStartPostRecordingComposer as Composer,
)
from iris.plan_step_execution_start_post_recording_composition import (
    PlanStepExecutionStartPostRecordingCompositionInvariantError as Invariant,
)
from iris.plan_step_execution_start_post_recording_composition import (
    PlanStepExecutionStartPostRecordingCompositionResult as Result,
)
from tests.test_plan_step_execution_binding_post_recording_composition import (
    RecordingWP047,
    operands,
    scenario,
)
from tests.test_plan_step_execution_evidence_assessment_composition import unsafe_clone
from tests.test_plan_step_execution_start import CountingReducer
from tests.test_plan_step_execution_start_composition import (
    CapabilityHandler,
    ClockSequence,
)


class RecordingWP048(PlanStepExecutionBindingPostRecordingComposer):
    def __init__(self, result: Any = None, error: Exception | None = None):
        super().__init__(request_materialization_composer=RecordingWP047())
        self.result = result
        self.error = error
        self.calls: list[Any] = []

    def compose(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return self.result


UNSET = object()


class RecordingStart(PlanStepExecutionStartCoordinator):
    def __init__(
        self, delegate: PlanStepExecutionStartCoordinator, *, forced: Any = UNSET
    ):
        self.delegate = delegate
        self.forced = forced
        self.calls: list[Any] = []
        self.results: list[Any] = []
        self.errors: list[Exception] = []

    def start(self, *args: Any) -> Any:
        self.calls.append(args)
        try:
            result = self.delegate.start(*args) if self.forced is UNSET else self.forced
        except Exception as exc:
            self.errors.append(exc)
            raise
        self.results.append(result)
        return result


def canonical_wp048(**kwargs: Any) -> tuple[Any, Any, Any]:
    plan, run, request_result = scenario(**kwargs)
    result = PlanStepExecutionBindingPostRecordingComposer(
        request_materialization_composer=RecordingWP047(request_result)
    ).compose(plan, run, "a", **operands(request_result))
    return plan, run, result


def runtime(result: Any, handler: Any = None, **kwargs: Any) -> RecordingStart:
    request = result.post_recording_execution_request or result.execution_request
    assert request is not None
    start = request.created_at + timedelta(seconds=1)
    coordinator = PlanStepExecutionStartCoordinator(
        ExecutionCoordinator(
            () if handler is None else (handler,),
            clock=ClockSequence(
                start, start + timedelta(seconds=1), start + timedelta(seconds=2)
            ),
        ),
        update_id_factory=lambda: "activation-c",
        **kwargs,
    )
    return RecordingStart(coordinator)


def invoke(
    plan: Any, run: Any, result: Any, coordinator: Any, **overrides: Any
) -> tuple[Any, Any]:
    upstream = RecordingWP048(result)
    kwargs = operands(result)
    kwargs.update(overrides)
    output = Composer(binding_composer=upstream, start_coordinator=coordinator).compose(
        plan, run, "a", **kwargs
    )
    return output, upstream


def test_public_surface_and_dependency_contract() -> None:
    assert api.__all__ == [
        "PlanStepExecutionStartPostRecordingComposer",
        "PlanStepExecutionStartPostRecordingCompositionResult",
        "PlanStepExecutionStartPostRecordingCompositionError",
        "PlanStepExecutionStartPostRecordingCompositionInvariantError",
    ]
    assert issubclass(
        Invariant, api.PlanStepExecutionStartPostRecordingCompositionError
    )
    assert issubclass(Result, PlanStepExecutionBindingPostRecordingCompositionResult)
    assert (
        inspect.signature(Composer.compose).parameters
        == inspect.signature(
            PlanStepExecutionBindingPostRecordingComposer.compose
        ).parameters
    )
    assert list(inspect.signature(Composer).parameters) == [
        "binding_composer",
        "start_coordinator",
    ]
    for name in ("binding_composer", "start_coordinator"):
        assert (
            inspect.signature(Composer).parameters[name].default
            is inspect.Parameter.empty
        )
    for bad in (None, object(), lambda: None):
        with pytest.raises(TypeError):
            Composer(
                binding_composer=bad,
                start_coordinator=PlanStepExecutionStartCoordinator(
                    ExecutionCoordinator()
                ),
            )
        with pytest.raises(TypeError):
            Composer(binding_composer=RecordingWP048(), start_coordinator=bad)


@pytest.mark.parametrize(
    "name,value",
    [
        ("plan", None),
        ("run", None),
        ("step_id", 1),
        ("candidates", []),
        ("candidates", (object(),)),
        ("budget", None),
        ("uncertainties", []),
        ("uncertainties", (object(),)),
        ("created_at", None),
        ("availability", None),
        ("execution_input", object()),
        ("post_recording_candidates", []),
        ("post_recording_candidates", (object(),)),
        ("post_recording_budget", None),
        ("post_recording_uncertainties", []),
        ("post_recording_uncertainties", (object(),)),
        ("post_recording_created_at", None),
        ("post_recording_availability", None),
    ],
)
def test_independent_direct_types_fail_before_upstream(name: str, value: Any) -> None:
    plan, run, result = canonical_wp048()
    start = runtime(result)
    upstream = RecordingWP048(result)
    kwargs = dict(plan=plan, run=run, step_id="a", **operands(result))
    kwargs[name] = value
    with pytest.raises(TypeError):
        Composer(binding_composer=upstream, start_coordinator=start).compose(**kwargs)
    assert upstream.calls == start.calls == []


@pytest.mark.parametrize("case", ["absent", "unspecified", "insufficient"])
def test_absence_preserves_all_artifacts_without_start_or_unused_input_validation(
    case: str,
) -> None:
    kwargs = (
        {"absent": True}
        if case == "absent"
        else {"handling": None if case == "unspecified" else HandlingKind.SYSTEM}
    )
    plan, run, result = canonical_wp048(**kwargs)
    start = RecordingStart(PlanStepExecutionStartCoordinator(ExecutionCoordinator()))
    output, upstream = invoke(
        plan, run, result, start, post_recording_execution_input=object()
    )
    assert len(upstream.calls) == 1
    assert start.calls == []
    assert output.post_recording_execution_request is None
    assert output.post_recording_execution_binding is None
    assert output.post_recording_execution_start_result is None
    for field in fields(result):
        assert getattr(output, field.name) is getattr(result, field.name)


def test_exact_forwarding_and_exact_c_pre_activation_operands() -> None:
    plan, run, result = canonical_wp048()
    handler = CapabilityHandler()
    start = runtime(result, handler)
    kwargs = operands(result)
    kwargs["availability"] = HandlerAvailability()
    kwargs["post_recording_availability"] = HandlerAvailability(capability=True)
    upstream = RecordingWP048(result)
    output = Composer(binding_composer=upstream, start_coordinator=start).compose(
        plan, run, "a", **kwargs
    )
    assert len(upstream.calls) == len(start.calls) == len(handler.calls) == 1
    assert upstream.calls[0][0] == (plan, run, "a")
    for key, value in kwargs.items():
        assert upstream.calls[0][1][key] is value
    pre = result.post_recording_advancement_result.updated_run
    expected = (
        plan,
        pre,
        result.post_recording_execution_binding,
        result.post_recording_execution_request,
    )
    assert all(
        actual is wanted
        for actual, wanted in zip(start.calls[0], expected, strict=True)
    )
    assert pre is not run
    assert pre is not result.execution_start_result.active_run
    assert pre is not result.execution_recording_result.recorded_run
    assert output.post_recording_execution_start_result is start.results[0]
    for field in fields(result):
        assert getattr(output, field.name) is getattr(result, field.name)
    assert output.execution_request is not output.post_recording_execution_request
    assert output.execution_binding is not output.post_recording_execution_binding
    assert (
        output.execution_start_result
        is not output.post_recording_execution_start_result
    )
    assert (
        output.assessment.step_id,
        output.execution_binding.step_id,
        output.post_recording_execution_binding.step_id,
    ) == ("a", "b", "c")


def test_real_handler_unavailable_is_a_start_result_without_activation() -> None:
    plan, run, result = canonical_wp048()
    start = runtime(result)
    output, _ = invoke(plan, run, result, start)
    actual = output.post_recording_execution_start_result
    assert actual is start.results[0]
    assert actual.active_run is None and actual.activation_update_id is None
    assert actual.execution_result.status is ExecutionStatus.REJECTED
    assert actual.execution_result.handler_reference is None
    assert actual.execution_result.failure.code == "handler_unavailable"
    assert (
        actual.execution_result.started_at
        > result.post_recording_execution_request.created_at
    )
    assert (
        next(
            p
            for p in result.post_recording_advancement_result.updated_run.step_progress
            if p.step_id == "c"
        ).state
        is StepProgressState.NOT_STARTED
    )
    assert len(start.calls) == 1


@pytest.mark.parametrize(
    "status",
    [ExecutionStatus.SUCCEEDED, ExecutionStatus.FAILED, ExecutionStatus.REJECTED],
)
def test_activated_outcomes_remain_active_and_do_not_record(
    status: ExecutionStatus,
) -> None:
    plan, run, result = canonical_wp048()
    pre = result.post_recording_advancement_result.updated_run
    before = (plan.to_data(), run.to_data(), pre.to_data())
    outcome = HandlerOutcome(
        status,
        failure=None
        if status is ExecutionStatus.SUCCEEDED
        else ExecutionFailure("handler_outcome", "test"),
    )
    handler = CapabilityHandler(outcome=outcome)
    reducer = CountingReducer()
    start = runtime(result, handler, reducer=reducer)
    output, _ = invoke(plan, run, result, start)
    actual = output.post_recording_execution_start_result
    active = actual.active_run
    assert actual.execution_result.status is status
    assert active.revision == pre.revision + 1
    selected = next(p for p in active.step_progress if p.step_id == "c")
    assert selected.state is StepProgressState.ACTIVE
    assert selected.changed_at > actual.execution_result.started_at
    assert selected.changed_at == active.updated_at
    assert active.observations == pre.observations
    assert active.blockers == pre.blockers
    assert tuple(p for p in active.step_progress if p.step_id != "c") == tuple(
        p for p in pre.step_progress if p.step_id != "c"
    )
    assert before == (plan.to_data(), run.to_data(), pre.to_data())
    assert len(reducer.calls) == len(handler.calls) == len(start.calls) == 1
    assert output.execution_recording_result is result.execution_recording_result


def test_wp048_error_propagates_unchanged_without_start() -> None:
    plan, run, result = canonical_wp048()
    error = RuntimeError("upstream canonical failure")
    upstream = RecordingWP048(error=error)
    start = runtime(result, CapabilityHandler())
    with pytest.raises(RuntimeError) as caught:
        Composer(binding_composer=upstream, start_coordinator=start).compose(
            plan, run, "a", **operands(result)
        )
    assert caught.value is error
    assert len(upstream.calls) == 1 and start.calls == []


@pytest.mark.parametrize(
    "failure_kind", ["gate_stale", "initial_stale", "clock", "update_id", "reducer"]
)
def test_real_pre_activation_failures_propagate_without_handler_or_retry(
    failure_kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, run, result = canonical_wp048()
    handler = CapabilityHandler()
    request = result.post_recording_execution_request
    reducer_error = PlanRunInvariantError("activation rejected")
    reducer = CountingReducer(
        error=reducer_error if failure_kind == "reducer" else None
    )
    clocks = (
        request.created_at + timedelta(seconds=1),
        request.created_at
        if failure_kind == "clock"
        else request.created_at + timedelta(seconds=2),
    )
    real = PlanStepExecutionStartCoordinator(
        ExecutionCoordinator((handler,), clock=ClockSequence(*clocks)),
        reducer=reducer,
        update_id_factory=lambda: "" if failure_kind == "update_id" else "activation-c",
    )
    stale = StalePlanStepExecutionBindingError("canonical currentness failure")
    original = start_module.validate_plan_step_execution_binding_current
    calls: list[Any] = []

    def currentness(*args: Any) -> None:
        calls.append(args)
        if failure_kind == "initial_stale" or (
            failure_kind == "gate_stale" and len(calls) == 2
        ):
            raise stale
        original(*args)

    monkeypatch.setattr(
        start_module, "validate_plan_step_execution_binding_current", currentness
    )
    start = RecordingStart(real)
    with pytest.raises(
        (
            StalePlanStepExecutionBindingError,
            ValueError,
            PlanStepExecutionStartGenerationError,
            PlanRunInvariantError,
        )
    ) as caught:
        invoke(plan, run, result, start)
    assert caught.value is start.errors[0]
    if "stale" in failure_kind:
        assert caught.value is stale
    if failure_kind == "reducer":
        assert caught.value is reducer_error
    assert len(start.calls) == 1 and handler.calls == []
    assert len(calls) == (1 if failure_kind in {"initial_stale", "clock"} else 2)


@pytest.mark.parametrize("failure_kind", ["handler", "completion"])
def test_post_activation_error_keeps_committed_lineage_no_rollback(
    failure_kind: str,
) -> None:
    plan, run, result = canonical_wp048()
    defect = RuntimeError("handler exploded")
    handler = CapabilityHandler(error=defect if failure_kind == "handler" else None)
    request = result.post_recording_execution_request
    reducer = CountingReducer()
    real = PlanStepExecutionStartCoordinator(
        ExecutionCoordinator(
            (handler,),
            clock=ClockSequence(
                request.created_at + timedelta(seconds=1),
                request.created_at + timedelta(seconds=2),
                request.created_at,
            ),
        ),
        reducer=reducer,
        update_id_factory=lambda: "activation-c",
    )
    start = RecordingStart(real)
    with pytest.raises(PlanStepExecutionInvocationError) as caught:
        invoke(plan, run, result, start)
    error = caught.value
    assert error is start.errors[0]
    assert error.execution_id == request.execution_id
    assert error.activation_update_id == "activation-c"
    assert (
        error.active_run.revision
        == result.post_recording_advancement_result.updated_run.revision + 1
    )
    assert (
        next(p for p in error.active_run.step_progress if p.step_id == "c").state
        is StepProgressState.ACTIVE
    )
    if failure_kind == "handler":
        assert error.__cause__ is defect
    else:
        assert isinstance(error.__cause__, ValueError)
    assert len(handler.calls) == len(reducer.calls) == len(start.calls) == 1
    assert start.results == []


@pytest.mark.parametrize(
    "path,value",
    [
        ("assessment.plan_id", "foreign"),
        ("assessment.run_id", "foreign"),
        ("assessment.run_revision", 999),
        ("assessment.step_id", "c"),
        ("post_recording_assessment.run_revision", 999),
        ("post_recording_transition_decision.observed_revision", 999),
        ("post_recording_progress_update.expected_revision", 999),
        ("post_recording_advancement_result.source_update_id", "foreign"),
        ("post_recording_advancement_result.updated_run.plan_id", "foreign"),
        ("post_recording_advancement_result.updated_run.goal_id", "foreign"),
        ("post_recording_advancement_result.updated_run.revision", 999),
        ("post_recording_advancement_result.control_decision.observed_revision", 999),
        ("post_recording_advancement_result.control_decision.selected_step_id", "b"),
        ("post_recording_handling_preparation.step_id", "b"),
        ("post_recording_handling_preparation.observed_revision", 999),
        ("post_recording_work_subject.reference.step_id", "b"),
        ("post_recording_work_subject.reference.run_id", "foreign"),
        ("post_recording_context_snapshot.subject", object()),
        ("post_recording_context_snapshot", None),
        ("post_recording_orchestration_decision.need_ids", ("foreign",)),
        ("post_recording_orchestration_decision.context_snapshot_id", "foreign"),
        ("post_recording_execution_request.subject", object()),
        ("post_recording_execution_request.decision", object()),
        ("post_recording_execution_binding.plan_id", "foreign"),
        ("post_recording_execution_binding.run_id", "foreign"),
        ("post_recording_execution_binding.observed_revision", 999),
        ("post_recording_execution_binding.step_id", "b"),
        ("post_recording_execution_binding.execution_id", "foreign"),
        ("post_recording_execution_binding.subject_id", "foreign"),
        ("post_recording_execution_binding.context_snapshot_id", "foreign"),
        ("post_recording_execution_binding.orchestration_decision_id", "foreign"),
        ("post_recording_execution_binding.handling_need_id", "foreign"),
        ("post_recording_execution_binding", None),
        ("post_recording_execution_request", None),
    ],
)
def test_adversarial_upstream_lineage_fails_before_any_wp025(
    path: str, value: Any
) -> None:
    plan, run, result = canonical_wp048()
    kwargs = operands(result)
    bad = mutate_path(result, path, value)
    handler = CapabilityHandler()
    start = runtime(result, handler)
    with pytest.raises(Invariant):
        Composer(binding_composer=RecordingWP048(bad), start_coordinator=start).compose(
            plan, run, "a", **kwargs
        )
    assert start.calls == handler.calls == []


def mutate_path(artifact: Any, path: str, value: Any) -> Any:
    """Deliberately bypass constructors only for adversarial boundary tests."""
    first, _, remaining = path.partition(".")
    return unsafe_clone(
        artifact,
        **{
            first: mutate_path(getattr(artifact, first), remaining, value)
            if remaining
            else value
        },
    )


@pytest.mark.parametrize(
    "bad",
    [
        None,
        object(),
        object.__new__(PlanStepExecutionBindingPostRecordingCompositionResult),
    ],
)
def test_noncanonical_upstream_type_or_incomplete_shape_fails_closed(bad: Any) -> None:
    plan, run, result = canonical_wp048()
    start = runtime(result)
    with pytest.raises(Invariant):
        Composer(binding_composer=RecordingWP048(bad), start_coordinator=start).compose(
            plan, run, "a", **operands(result)
        )
    assert start.calls == []


@pytest.mark.parametrize(
    "path,value",
    [
        ("plan_id", "foreign"),
        ("run_id", "foreign"),
        ("source_revision", 999),
        ("source_revision", True),
        ("step_id", "b"),
        ("execution_id", "foreign"),
        ("execution_result", object()),
        ("execution_result.execution_id", "foreign"),
        ("execution_result.subject_id", "foreign"),
        ("execution_result.decision_id", "foreign"),
        ("execution_result.context_snapshot_id", "foreign"),
        ("execution_result.target", OrchestrationTarget.SYSTEM),
        ("execution_result.decision_reason", "wrong"),
        ("execution_result.status", "SUCCEEDED"),
        ("active_run.plan_id", "foreign"),
        ("active_run.run_id", "foreign"),
        ("active_run.goal_id", "foreign"),
        ("active_run.revision", 999),
        ("active_run.observations", ()),
        ("active_run.step_progress", ()),
        ("activation_update_id", None),
        ("activation_update_id", ""),
        ("active_run", None),
        ("execution_result.handler_reference", None),
    ],
)
def test_adversarial_successful_wp025_return_is_invariant(
    path: str, value: Any
) -> None:
    plan, run, result = canonical_wp048()
    real = runtime(result, CapabilityHandler())
    canonical = real.start(
        plan,
        result.post_recording_advancement_result.updated_run,
        result.post_recording_execution_binding,
        result.post_recording_execution_request,
    )
    bad = mutate_path(canonical, path, value)
    spy = RecordingStart(real.delegate, forced=bad)
    with pytest.raises(Invariant):
        invoke(plan, run, result, spy)
    assert len(spy.calls) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("activation_update_id", "invented"),
        ("execution_result.failure", None),
        ("execution_result.failure.code", "other"),
        ("execution_result.status", ExecutionStatus.FAILED),
        ("execution_result.handler_reference", "foreign"),
    ],
)
def test_nonactivated_return_must_be_canonical_unavailability(
    field: str, value: Any
) -> None:
    plan, run, result = canonical_wp048()
    real = runtime(result)
    canonical = real.start(
        plan,
        result.post_recording_advancement_result.updated_run,
        result.post_recording_execution_binding,
        result.post_recording_execution_request,
    )
    with pytest.raises(Invariant):
        invoke(
            plan,
            run,
            result,
            RecordingStart(real.delegate, forced=mutate_path(canonical, field, value)),
        )


@pytest.mark.parametrize(
    "bad", [None, object(), object.__new__(PlanStepExecutionStartResult)]
)
def test_bad_start_return_type_or_shape_is_invariant(bad: Any) -> None:
    plan, run, result = canonical_wp048()
    spy = RecordingStart(runtime(result).delegate, forced=bad)
    with pytest.raises(Invariant):
        invoke(plan, run, result, spy)
    assert len(spy.calls) == 1


def test_frozen_slots_serialization_presence_and_repeated_invocation() -> None:
    plan, run, result = canonical_wp048()
    output, _ = invoke(plan, run, result, runtime(result))
    assert not hasattr(output, "__dict__")
    assert Result.__slots__ == ("post_recording_execution_start_result",)
    with pytest.raises(FrozenInstanceError):
        output.post_recording_execution_start_result = None
    with pytest.raises(Invariant):
        replace(output, post_recording_execution_start_result=None)
    data = output.to_data()
    assert json.dumps(data) == json.dumps(output.to_data())
    assert (
        data.pop("post_recording_execution_start_result")
        == output.post_recording_execution_start_result.to_data()
    )
    assert data == result.to_data()
    absent_plan, absent_run, absent = canonical_wp048(handling=None)
    empty, _ = invoke(absent_plan, absent_run, absent, runtime(absent))
    with pytest.raises(Invariant):
        replace(
            empty,
            post_recording_execution_start_result=output.post_recording_execution_start_result,
        )
    upstream = RecordingWP048(result)
    # A canonical clock can return equal times; WP049 adds no deduplication.
    handler = CapabilityHandler()
    real = PlanStepExecutionStartCoordinator(
        ExecutionCoordinator(
            (handler,),
            clock=lambda: (
                result.post_recording_execution_request.created_at
                + timedelta(seconds=10)
            ),
        )
    )
    spy = RecordingStart(real)
    composer = Composer(binding_composer=upstream, start_coordinator=spy)
    for _ in range(2):
        composer.compose(plan, run, "a", **operands(result))
    assert len(upstream.calls) == len(spy.calls) == len(handler.calls) == 2


@pytest.mark.parametrize("shape", ["duplicates", "list", "unsorted", "bool_revision"])
def test_run_shapes_are_rejected_without_normalizing_or_starting(shape: str) -> None:
    plan, run, result = canonical_wp048()
    pre = result.post_recording_advancement_result.updated_run
    if shape == "duplicates":
        bad_run = unsafe_clone(
            pre, step_progress=pre.step_progress + (pre.step_progress[-1],)
        )
    elif shape == "list":
        bad_run = unsafe_clone(pre, step_progress=list(pre.step_progress))
    elif shape == "unsorted":
        bad_run = unsafe_clone(pre, step_progress=tuple(reversed(pre.step_progress)))
    else:
        bad_run = unsafe_clone(pre, revision=True)
    bad = mutate_path(result, "post_recording_advancement_result.updated_run", bad_run)
    original_progress = bad_run.step_progress
    start = runtime(result, CapabilityHandler())
    with pytest.raises(Invariant):
        invoke(plan, run, bad, start)
    assert start.calls == []
    assert bad_run.step_progress is original_progress


@pytest.mark.parametrize(
    "shape",
    [
        "created_at",
        "unrelated_progress",
        "target_state",
        "target_evidence",
        "target_time",
        "activation_after_completion",
    ],
)
def test_activation_cannot_change_unrelated_state_or_invent_timing(shape: str) -> None:
    plan, run, result = canonical_wp048()
    start = runtime(result, CapabilityHandler())
    canonical = start.start(
        plan,
        result.post_recording_advancement_result.updated_run,
        result.post_recording_execution_binding,
        result.post_recording_execution_request,
    )
    active = canonical.active_run
    if shape == "created_at":
        bad_run = unsafe_clone(
            active, created_at=active.created_at - timedelta(seconds=1)
        )
    elif shape == "activation_after_completion":
        late = canonical.execution_result.completed_at + timedelta(seconds=1)
        bad_run = unsafe_clone(
            active,
            updated_at=late,
            step_progress=tuple(
                unsafe_clone(p, changed_at=late) if p.step_id == "c" else p
                for p in active.step_progress
            ),
        )
    else:
        changes = (
            {"state": StepProgressState.SUCCEEDED}
            if shape == "target_state"
            else {"evidence_ids": ("invented",)}
            if shape == "target_evidence"
            else {"changed_at": active.updated_at - timedelta(seconds=1)}
        )
        target = "a" if shape == "unrelated_progress" else "c"
        bad_run = unsafe_clone(
            active,
            step_progress=tuple(
                unsafe_clone(p, **changes) if p.step_id == target else p
                for p in active.step_progress
            ),
        )
    spy = RecordingStart(
        start.delegate, forced=unsafe_clone(canonical, active_run=bad_run)
    )
    with pytest.raises(Invariant):
        invoke(plan, run, result, spy)
    assert len(spy.calls) == 1


def test_success_uses_wp025_currentness_before_resolution_and_again_at_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, run, result = canonical_wp048()
    calls: list[Any] = []
    original = start_module.validate_plan_step_execution_binding_current

    def record(*args: Any) -> None:
        calls.append(args)
        original(*args)

    monkeypatch.setattr(
        start_module, "validate_plan_step_execution_binding_current", record
    )
    invoke(plan, run, result, runtime(result, CapabilityHandler()))
    assert len(calls) == 2
    for arguments in calls:
        assert arguments[0] is plan
        assert arguments[1] is result.post_recording_advancement_result.updated_run
        assert arguments[2] is result.post_recording_execution_binding


def test_forbidden_authorities_and_no_step_identity_inequality() -> None:
    folder = Path("iris/plan_step_execution_start_post_recording_composition")
    source = "\n".join(p.read_text(encoding="utf-8") for p in folder.glob("*.py"))
    for forbidden in (
        "ExecutionCoordinator",
        "PlanRunReducer",
        "StepProgressUpdate(",
        "PlanStepExecutionBinder",
        "PlanStepExecutionResultRecorder",
        "ExecutionObservationAdapter",
        "PlanStepExecutionRecordingComposer",
        "PlanStepExecutionStartComposer",
        "Orchestrator",
        "_EXECUTABLE_TARGETS",
        "_TERMINAL_TARGETS",
        "OrchestrationTarget",
        "handler.execute",
        "commit_start(",
        "uuid4",
        "datetime.now",
        "subprocess",
        "socket",
        "Continuation",
        "AgentLoop",
    ):
        assert forbidden not in source
    tree = ast.parse((folder / "composer.py").read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert (
        sum(
            isinstance(n.func, ast.Attribute) and n.func.attr == "compose"
            for n in calls
        )
        == 1
    )
    assert (
        sum(isinstance(n.func, ast.Attribute) and n.func.attr == "start" for n in calls)
        == 1
    )
    assert not any(isinstance(n, (ast.While, ast.AsyncFor)) for n in ast.walk(tree))
    # No invented inequality between inherited Step B and freshly selected Step C IDs.
    assert "self.execution_binding.step_id" not in source
    assert (
        "PlanStepExecutionInvocationError" not in source
    )  # not caught/translated locally
