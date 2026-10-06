"""WP050/C1: record the exact Step C fact, never interpret or continue it.

Unsafe clones are noncanonical adversarial returns only. WP049 may already have
executed before WP050 validates; these tests promise fail-closed RECORDING, not
absence of prior side effects. All test handlers only change in-memory state.
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

import iris.plan_step_execution_result_recording_post_recording_composition as api
from iris.execution import (
    ExecutionCoordinator,
    ExecutionFailure,
    ExecutionOutput,
    ExecutionStatus,
    HandlerOutcome,
)
from iris.execution_observation import (
    ExecutionObservationAdapter,
    ExecutionObservationIdentityError,
)
from iris.orchestrator import HandlerAvailability, HandlingKind
from iris.plan_runs import PlanRunInvariantError, StepProgressState
from iris.plan_step_execution_result_recording import (
    PlanStepExecutionResultRecorder,
    PlanStepExecutionResultRecordingGenerationError,
    PlanStepExecutionResultRecordingLineageError,
    PlanStepExecutionResultRecordingResult,
)
from iris.plan_step_execution_result_recording_post_recording_composition import (
    PlanStepExecutionResultRecordingPostRecordingComposer as Composer,
)
from iris.plan_step_execution_result_recording_post_recording_composition import (
    PlanStepExecutionResultRecordingPostRecordingCompositionInvariantError as Invariant,
)
from iris.plan_step_execution_result_recording_post_recording_composition import (
    PlanStepExecutionResultRecordingPostRecordingCompositionResult as Result,
)
from iris.plan_step_execution_start import (
    PlanStepExecutionInvocationError,
    PlanStepExecutionStartCoordinator,
)
from iris.plan_step_execution_start_post_recording_composition import (
    PlanStepExecutionStartPostRecordingComposer as Upstream,
)
from iris.plan_step_execution_start_post_recording_composition import (
    PlanStepExecutionStartPostRecordingCompositionResult,
)
from tests.test_plan_step_execution_binding_post_recording_composition import operands
from tests.test_plan_step_execution_evidence_assessment_composition import unsafe_clone
from tests.test_plan_step_execution_start import CountingReducer
from tests.test_plan_step_execution_start_composition import CapabilityHandler
from tests.test_plan_step_execution_start_post_recording_composition import (
    RecordingWP048,
    canonical_wp048,
    mutate_path,
    runtime,
)
from tests.test_plan_step_execution_start_post_recording_composition import (
    invoke as invoke_wp049,
)

UNSET = object()


class RecordingWP049(Upstream):
    def __init__(
        self,
        result: Any = None,
        *,
        error: Exception | None = None,
        delegate: Any = None,
        transform: Any = None,
    ):
        super().__init__(
            binding_composer=RecordingWP048(),
            start_coordinator=PlanStepExecutionStartCoordinator(ExecutionCoordinator()),
        )
        self.result = result
        self.error = error
        self.delegate = delegate
        self.transform = transform
        self.calls: list[Any] = []
        self.errors: list[Exception] = []
        self.returned: list[Any] = []

    def compose(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        try:
            if self.error is not None:
                raise self.error
            result = (
                self.result
                if self.delegate is None
                else self.delegate.compose(*args, **kwargs)
            )
        except Exception as exc:
            self.errors.append(exc)
            raise
        self.returned.append(result)
        return result if self.transform is None else self.transform(result)


class RecordingRecorder(PlanStepExecutionResultRecorder):
    def __init__(
        self,
        *,
        observed_at: Any = None,
        observation_id: str = "aaa-execution-observation-c",
        forced: Any = UNSET,
        error: Exception | None = None,
    ):
        super().__init__(
            observation_adapter=ExecutionObservationAdapter(
                clock=lambda: observed_at,
                observation_id_factory=lambda: observation_id,
            ),
            update_id_factory=lambda: "record-update-c",
        )
        self.forced = forced
        self.error = error
        self.calls: list[Any] = []
        self.results: list[Any] = []
        self.errors: list[Exception] = []

    def record(self, *args: Any) -> Any:
        self.calls.append(args)
        try:
            if self.error is not None:
                raise self.error
            result = super().record(*args) if self.forced is UNSET else self.forced
        except Exception as exc:
            self.errors.append(exc)
            raise
        self.results.append(result)
        return result


def canonical_wp049(
    *,
    absent: bool = False,
    handling: Any = HandlingKind.CAPABILITY,
    unavailable: bool = False,
    status: ExecutionStatus = ExecutionStatus.SUCCEEDED,
) -> tuple[Any, Any, Any]:
    plan, run, binding = canonical_wp048(absent=absent, handling=handling)
    handler = (
        None
        if unavailable
        else CapabilityHandler(
            outcome=HandlerOutcome(
                status,
                failure=None
                if status is ExecutionStatus.SUCCEEDED
                else ExecutionFailure("handler_outcome", "test"),
            ),
        )
    )
    start = (
        runtime(binding, handler)
        if binding.execution_request is not None
        else PlanStepExecutionStartCoordinator(ExecutionCoordinator())
    )
    result, _ = invoke_wp049(plan, run, binding, start)
    return plan, run, result


def recorder_for(result: Any, **kwargs: Any) -> RecordingRecorder:
    start = result.post_recording_execution_start_result
    return RecordingRecorder(
        observed_at=None
        if start is None
        else start.execution_result.completed_at + timedelta(seconds=1),
        **kwargs,
    )


def invoke(
    plan: Any, run: Any, result: Any, recorder: Any, **overrides: Any
) -> tuple[Any, RecordingWP049]:
    upstream = RecordingWP049(result)
    kwargs = operands(result)
    kwargs.update(overrides)
    output = Composer(start_composer=upstream, result_recorder=recorder).compose(
        plan, run, "a", **kwargs
    )
    return output, upstream


def test_public_api_signature_dependencies_and_default() -> None:
    assert api.__all__ == [
        "PlanStepExecutionResultRecordingPostRecordingComposer",
        "PlanStepExecutionResultRecordingPostRecordingCompositionResult",
        "PlanStepExecutionResultRecordingPostRecordingCompositionError",
        "PlanStepExecutionResultRecordingPostRecordingCompositionInvariantError",
    ]
    assert issubclass(
        Invariant, api.PlanStepExecutionResultRecordingPostRecordingCompositionError
    )
    assert issubclass(Result, PlanStepExecutionStartPostRecordingCompositionResult)
    assert (
        inspect.signature(Composer.compose).parameters
        == inspect.signature(Upstream.compose).parameters
    )
    assert list(inspect.signature(Composer).parameters) == [
        "start_composer",
        "result_recorder",
    ]
    for bad in (None, object(), lambda: None):
        with pytest.raises(TypeError):
            Composer(start_composer=bad)
    with pytest.raises(TypeError):
        Composer(start_composer=RecordingWP049(), result_recorder=object())
    plan, run, result = canonical_wp049(unavailable=True)
    output = Composer(start_composer=RecordingWP049(result)).compose(
        plan, run, "a", **operands(result)
    )
    assert output.post_recording_execution_recording_result is not None


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
def test_direct_invalid_input_fails_before_wp049(name: str, value: Any) -> None:
    plan, run, result = canonical_wp049()
    upstream = RecordingWP049(result)
    recorder = recorder_for(result)
    kwargs = dict(plan=plan, run=run, step_id="a", **operands(result))
    kwargs[name] = value
    with pytest.raises(TypeError):
        Composer(start_composer=upstream, result_recorder=recorder).compose(**kwargs)
    assert upstream.calls == recorder.calls == []


@pytest.mark.parametrize("case", ["no_subject", "unspecified", "insufficient"])
def test_absence_preserves_exact_artifacts_and_unused_input(case: str) -> None:
    kwargs = (
        {"absent": True}
        if case == "no_subject"
        else {"handling": None if case == "unspecified" else HandlingKind.SYSTEM}
    )
    plan, run, result = canonical_wp049(**kwargs)
    recorder = recorder_for(result)
    output, upstream = invoke(
        plan, run, result, recorder, post_recording_execution_input=object()
    )
    assert len(upstream.calls) == 1 and recorder.calls == []
    assert output.post_recording_execution_recording_result is None
    for item in fields(result):
        assert getattr(output, item.name) is getattr(result, item.name)


def test_absence_does_not_hide_malformed_source_lineage() -> None:
    plan, run, result = canonical_wp049(handling=None)
    bad = mutate_path(result, "assessment.plan_id", "foreign")
    recorder = recorder_for(result)
    with pytest.raises(Invariant):
        invoke(plan, run, bad, recorder)
    assert recorder.calls == []


def test_exact_input_forwarding_and_artifact_preservation() -> None:
    plan, run, result = canonical_wp049()
    kwargs = operands(result)
    kwargs["availability"] = HandlerAvailability()
    kwargs["post_recording_availability"] = HandlerAvailability(capability=True)
    upstream = RecordingWP049(result)
    recorder = recorder_for(result)
    output = Composer(start_composer=upstream, result_recorder=recorder).compose(
        plan, run, "a", **kwargs
    )
    assert len(upstream.calls) == len(recorder.calls) == 1
    assert upstream.calls[0][0] == (plan, run, "a")
    for key, value in kwargs.items():
        assert upstream.calls[0][1][key] is value
    for item in fields(result):
        assert getattr(output, item.name) is getattr(result, item.name)
    assert output.post_recording_execution_recording_result is recorder.results[0]
    assert (
        output.execution_recording_result
        is not output.post_recording_execution_recording_result
    )
    assert output.execution_recording_result.step_id == "b"
    assert output.post_recording_execution_recording_result.step_id == "c"


@pytest.mark.parametrize(
    "unavailable,status",
    [
        (True, ExecutionStatus.REJECTED),
        (False, ExecutionStatus.SUCCEEDED),
        (False, ExecutionStatus.FAILED),
        (False, ExecutionStatus.REJECTED),
    ],
)
def test_real_outcomes_use_exact_base_and_preserve_progress(
    unavailable: bool, status: ExecutionStatus
) -> None:
    plan, run, result = canonical_wp049(unavailable=unavailable, status=status)
    start = result.post_recording_execution_start_result
    pre = result.post_recording_advancement_result.updated_run
    base = pre if unavailable else start.active_run
    before = base.to_data()
    recorder = recorder_for(result)
    output, _ = invoke(plan, run, result, recorder)
    assert len(recorder.calls) == 1
    assert all(
        actual is wanted
        for actual, wanted in zip(recorder.calls[0], (plan, base, start), strict=True)
    )
    recording = output.post_recording_execution_recording_result
    assert recording.recorded_from_revision == base.revision
    assert recording.recorded_run.revision == base.revision + 1
    assert recording.recorded_run.revision == pre.revision + (1 if unavailable else 2)
    assert recording.recorded_run.step_progress == base.step_progress
    selected = next(p for p in recording.recorded_run.step_progress if p.step_id == "c")
    assert selected.state is (
        StepProgressState.NOT_STARTED if unavailable else StepProgressState.ACTIVE
    )
    assert recording.observation.data["status"] == status.value
    assert recording.observation.source == "execution"
    assert recording.observation.source_reference == start.execution_id
    assert recording.observation.kind == "execution_result"
    assert any(o is recording.observation for o in recording.recorded_run.observations)
    assert base.to_data() == before
    if unavailable:
        assert start.active_run is None and start.activation_update_id is None
        assert start.execution_result.failure.code == "handler_unavailable"
    else:
        assert recorder.calls[0][1] is not pre


@pytest.mark.parametrize("position", ["before", "between", "after"])
def test_c1_real_canonical_observation_can_sort_anywhere(position: str) -> None:
    plan, run, result = canonical_wp049()
    base = result.post_recording_execution_start_result.active_run
    prior_ids = [o.observation_id for o in base.observations]
    assert len(prior_ids) >= 2
    new_id = {
        "before": "aaa-execution-observation",
        "between": prior_ids[0] + "-middle",
        "after": "zzz-execution-observation",
    }[position]
    recorder = recorder_for(result, observation_id=new_id)
    output, _ = invoke(plan, run, result, recorder)
    recording = output.post_recording_execution_recording_result
    observations = recording.recorded_run.observations
    ids = [o.observation_id for o in observations]
    assert ids == sorted(prior_ids + [new_id])
    index = ids.index(new_id)
    assert (
        index == 0
        if position == "before"
        else index == len(ids) - 1
        if position == "after"
        else 0 < index < len(ids) - 1
    )
    assert observations[index] is recording.observation
    assert len(observations) == len(base.observations) + 1
    for prior in base.observations:
        assert any(item is prior for item in observations)


@pytest.mark.parametrize(
    "path,value",
    [
        ("assessment.plan_id", "foreign"),
        ("assessment.run_id", "foreign"),
        ("assessment.step_id", "c"),
        ("assessment.run_revision", 999),
        ("post_recording_progress_update.expected_revision", 999),
        ("post_recording_advancement_result.updated_run.run_id", "foreign"),
        ("post_recording_advancement_result.control_decision.observed_revision", 999),
        ("post_recording_handling_preparation.step_id", "b"),
        ("post_recording_work_subject.reference.step_id", "b"),
        ("post_recording_context_snapshot.subject", object()),
        ("post_recording_execution_request.subject", object()),
        ("post_recording_execution_binding.execution_id", "foreign"),
        ("post_recording_execution_start_result.execution_id", "foreign"),
        ("post_recording_execution_start_result.source_revision", 999),
        ("post_recording_execution_start_result.active_run.goal_id", "foreign"),
        ("post_recording_execution_start_result.active_run.revision", 999),
        (
            "post_recording_execution_start_result.execution_result.subject_id",
            "foreign",
        ),
        ("post_recording_execution_start_result.active_run", None),
        ("post_recording_execution_start_result", None),
    ],
)
def test_adversarial_wp049_return_rejected_before_recording(
    path: str, value: Any
) -> None:
    plan, run, result = canonical_wp049()
    kwargs = operands(result)
    recorder = recorder_for(result)
    bad = mutate_path(result, path, value)
    with pytest.raises(Invariant):
        Composer(start_composer=RecordingWP049(bad), result_recorder=recorder).compose(
            plan, run, "a", **kwargs
        )
    assert recorder.calls == []


@pytest.mark.parametrize(
    "bad",
    [
        None,
        object(),
        object.__new__(PlanStepExecutionStartPostRecordingCompositionResult),
    ],
)
def test_wrong_or_incomplete_upstream_return(bad: Any) -> None:
    plan, run, result = canonical_wp049()
    recorder = recorder_for(result)
    with pytest.raises(Invariant):
        Composer(start_composer=RecordingWP049(bad), result_recorder=recorder).compose(
            plan, run, "a", **operands(result)
        )
    assert recorder.calls == []


@pytest.mark.parametrize(
    "path,value",
    [
        ("plan_id", "foreign"),
        ("run_id", "foreign"),
        ("step_id", "b"),
        ("execution_id", "foreign"),
        ("recorded_from_revision", 999),
        ("recorded_from_revision", True),
        ("observation_id", "foreign"),
        ("record_update_id", ""),
        ("recorded_run.plan_id", "foreign"),
        ("recorded_run.run_id", "foreign"),
        ("recorded_run.goal_id", "foreign"),
        ("recorded_run.revision", 999),
        ("recorded_run.step_progress", ()),
        ("observation.source", "other"),
        ("observation.source_reference", "foreign"),
        ("observation.kind", "other"),
        ("observation.run_id", "foreign"),
        ("observation.step_id", "b"),
        ("observation", object()),
    ],
)
def test_adversarial_wp026_return_rejected(path: str, value: Any) -> None:
    plan, run, result = canonical_wp049()
    start = result.post_recording_execution_start_result
    valid = recorder_for(result).record(plan, start.active_run, start)
    bad = mutate_path(valid, path, value)
    recorder = recorder_for(result, forced=bad)
    with pytest.raises(Invariant):
        invoke(plan, run, result, recorder)
    assert len(recorder.calls) == 1


@pytest.mark.parametrize(
    "case",
    [
        "missing_prior",
        "equal_replacement_prior",
        "changed_prior",
        "extra_unrelated",
        "missing_exact_new",
        "equal_replacement_new",
        "duplicate_identity",
        "unsorted",
        "changed_progress",
        "changed_blockers",
        "changed_facts",
        "wrong_new_lineage",
    ],
)
def test_c1_adversarial_observation_and_state_changes_rejected(case: str) -> None:
    plan, run, result = canonical_wp049()
    start = result.post_recording_execution_start_result
    base = start.active_run
    recording = recorder_for(result).record(plan, base, start)
    recorded = recording.recorded_run
    observation = recording.observation
    prior = base.observations[0]
    observations = recorded.observations
    if case == "missing_prior":
        bad_run = unsafe_clone(
            recorded, observations=tuple(o for o in observations if o is not prior)
        )
    elif case in {"equal_replacement_prior", "changed_prior"}:
        replacement = unsafe_clone(
            prior, **({"data": {"forged": True}} if case == "changed_prior" else {})
        )
        bad_run = unsafe_clone(
            recorded,
            observations=tuple(replacement if o is prior else o for o in observations),
        )
    elif case == "extra_unrelated":
        extra = replace(
            observation,
            observation_id="zzz-unrelated",
            source_reference="foreign-execution",
        )
        bad_run = replace(recorded, observations=(*observations, extra))
    elif case == "missing_exact_new":
        bad_run = unsafe_clone(recorded, observations=base.observations)
    elif case == "equal_replacement_new":
        bad_run = unsafe_clone(
            recorded,
            observations=tuple(
                unsafe_clone(o) if o is observation else o for o in observations
            ),
        )
    elif case == "duplicate_identity":
        bad_run = unsafe_clone(recorded, observations=observations + (prior,))
    elif case == "unsorted":
        bad_run = unsafe_clone(recorded, observations=tuple(reversed(observations)))
    elif case == "changed_progress":
        bad_run = unsafe_clone(
            recorded,
            step_progress=tuple(
                unsafe_clone(p, changed_at=p.changed_at + timedelta(microseconds=1))
                if p.step_id == "c"
                else p
                for p in recorded.step_progress
            ),
        )
    elif case == "changed_blockers":
        bad_run = unsafe_clone(recorded, blockers=(object(),))
    else:
        altered = replace(
            observation,
            **(
                {"data": {**observation.data, "status": "invented"}}
                if case == "changed_facts"
                else {"source_reference": "foreign"}
            ),
        )
        bad_run = replace(
            recorded,
            observations=tuple(
                altered if o is observation else o for o in observations
            ),
        )
        recording = unsafe_clone(recording, observation=altered)
    bad = unsafe_clone(recording, recorded_run=bad_run)
    recorder = recorder_for(result, forced=bad)
    with pytest.raises(Invariant):
        invoke(plan, run, result, recorder)
    assert len(recorder.calls) == 1


@pytest.mark.parametrize(
    "bad", [None, object(), object.__new__(PlanStepExecutionResultRecordingResult)]
)
def test_wrong_or_incomplete_recorder_return(bad: Any) -> None:
    plan, run, result = canonical_wp049()
    recorder = recorder_for(result, forced=bad)
    with pytest.raises(Invariant):
        invoke(plan, run, result, recorder)
    assert len(recorder.calls) == 1


def test_upstream_error_propagates_exactly() -> None:
    plan, run, result = canonical_wp049()
    error = RuntimeError("WP049 failure")
    upstream = RecordingWP049(error=error)
    recorder = recorder_for(result)
    with pytest.raises(RuntimeError) as caught:
        Composer(start_composer=upstream, result_recorder=recorder).compose(
            plan, run, "a", **operands(result)
        )
    assert caught.value is error
    assert len(upstream.calls) == 1 and recorder.calls == []


def live_pipeline(*, handler_error: Exception | None = None) -> tuple[Any, ...]:
    plan, run, binding = canonical_wp048()
    handler = CapabilityHandler(error=handler_error)
    reducer = CountingReducer()
    start = runtime(binding, handler, reducer=reducer)
    delegate = Upstream(
        binding_composer=RecordingWP048(binding), start_coordinator=start
    )
    return plan, run, binding, handler, reducer, start, delegate


def test_real_post_activation_invocation_error_is_not_recorded_or_rolled_back() -> None:
    defect = RuntimeError("handler effect then failure")
    plan, run, binding, handler, reducer, start, delegate = live_pipeline(
        handler_error=defect
    )
    upstream = RecordingWP049(delegate=delegate)
    recorder = RecordingRecorder()
    with pytest.raises(PlanStepExecutionInvocationError) as caught:
        Composer(start_composer=upstream, result_recorder=recorder).compose(
            plan, run, "a", **operands(binding)
        )
    error = caught.value
    assert error is start.errors[0] is upstream.errors[0]
    assert error.__cause__ is defect
    assert error.activation_update_id == "activation-c"
    assert error.execution_id == binding.post_recording_execution_request.execution_id
    assert (
        error.active_run.revision
        == binding.post_recording_advancement_result.updated_run.revision + 1
    )
    assert (
        next(p for p in error.active_run.step_progress if p.step_id == "c").state
        is StepProgressState.ACTIVE
    )
    assert (
        len(handler.calls)
        == len(reducer.calls)
        == len(start.calls)
        == len(upstream.calls)
        == 1
    )
    assert recorder.calls == []


@pytest.mark.parametrize(
    "error",
    [
        PlanStepExecutionResultRecordingLineageError("lineage failure"),
        PlanStepExecutionResultRecordingGenerationError("identity failure"),
        PlanRunInvariantError("recording reduction failed"),
    ],
)
def test_recording_failure_after_execution_never_reruns_handler(
    error: Exception,
) -> None:
    plan, run, binding, handler, reducer, start, delegate = live_pipeline()
    upstream = RecordingWP049(delegate=delegate)
    recorder = RecordingRecorder(error=error)
    with pytest.raises(type(error)) as caught:
        Composer(start_composer=upstream, result_recorder=recorder).compose(
            plan, run, "a", **operands(binding)
        )
    assert caught.value is error is recorder.errors[0]
    assert (
        len(upstream.calls)
        == len(recorder.calls)
        == len(handler.calls)
        == len(reducer.calls)
        == 1
    )
    assert recorder.calls[0][1] is start.results[0].active_run
    assert (
        next(
            p for p in start.results[0].active_run.step_progress if p.step_id == "c"
        ).state
        is StepProgressState.ACTIVE
    )


def test_malformed_return_after_execution_prevents_recording_not_prior_effects() -> (
    None
):
    plan, run, binding, handler, reducer, start, delegate = live_pipeline()
    upstream = RecordingWP049(
        delegate=delegate,
        transform=lambda result: mutate_path(
            result, "post_recording_execution_start_result.execution_id", "foreign"
        ),
    )
    recorder = RecordingRecorder()
    with pytest.raises(Invariant):
        Composer(start_composer=upstream, result_recorder=recorder).compose(
            plan, run, "a", **operands(binding)
        )
    assert recorder.calls == []
    assert len(handler.calls) == len(reducer.calls) == len(start.calls) == 1
    assert start.results[0].active_run is not None  # execution already happened


def test_presence_frozen_slots_serialization_and_no_deduplication() -> None:
    plan, run, result = canonical_wp049()
    output, _ = invoke(plan, run, result, recorder_for(result))
    assert not hasattr(output, "__dict__")
    assert Result.__slots__ == ("post_recording_execution_recording_result",)
    with pytest.raises(FrozenInstanceError):
        output.post_recording_execution_recording_result = None
    with pytest.raises(Invariant):
        replace(output, post_recording_execution_recording_result=None)
    data = output.to_data()
    assert json.dumps(data) == json.dumps(output.to_data())
    assert (
        data.pop("post_recording_execution_recording_result")
        == output.post_recording_execution_recording_result.to_data()
    )
    assert data == result.to_data()
    absent_plan, absent_run, absent = canonical_wp049(handling=None)
    empty, _ = invoke(absent_plan, absent_run, absent, recorder_for(absent))
    with pytest.raises(Invariant):
        replace(
            empty,
            post_recording_execution_recording_result=output.post_recording_execution_recording_result,
        )
    upstream = RecordingWP049(result)
    recorder = recorder_for(result)
    composer = Composer(start_composer=upstream, result_recorder=recorder)
    for _ in range(2):
        composer.compose(plan, run, "a", **operands(result))
    assert len(upstream.calls) == len(recorder.calls) == 2


def test_nested_execution_facts_are_preserved_without_interpretation() -> None:
    plan, run, binding = canonical_wp048()
    outcome = HandlerOutcome(
        ExecutionStatus.SUCCEEDED,
        output=ExecutionOutput(
            value={"items": [1, {"ok": True}]}, reference="output-c"
        ),
        metadata={"details": ["raw", {"count": 2}]},
    )
    result, _ = invoke_wp049(
        plan, run, binding, runtime(binding, CapabilityHandler(outcome=outcome))
    )
    output, _ = invoke(plan, run, result, recorder_for(result))
    data = output.post_recording_execution_recording_result.observation.to_data()[
        "data"
    ]
    assert data["output"] == outcome.output.to_data()
    assert data["metadata"] == {"details": ["raw", {"count": 2}]}
    assert (
        output.post_recording_execution_recording_result.recorded_run.step_progress
        == result.post_recording_execution_start_result.active_run.step_progress
    )


def test_real_adapter_timing_failure_after_execution_propagates_without_retry() -> None:
    plan, run, binding, handler, reducer, start, delegate = live_pipeline()
    upstream = RecordingWP049(delegate=delegate)
    recorder = RecordingRecorder(
        observed_at=binding.post_recording_execution_request.created_at
    )
    with pytest.raises(ExecutionObservationIdentityError) as caught:
        Composer(start_composer=upstream, result_recorder=recorder).compose(
            plan, run, "a", **operands(binding)
        )
    assert caught.value is recorder.errors[0]
    assert (
        len(upstream.calls)
        == len(recorder.calls)
        == len(handler.calls)
        == len(reducer.calls)
        == 1
    )
    assert recorder.results == []
    assert start.results[0].active_run is not None


def test_authority_boundaries_and_no_positional_append_policy() -> None:
    folder = Path(
        "iris/plan_step_execution_result_recording_post_recording_composition"
    )
    trees = [ast.parse(p.read_text(encoding="utf-8")) for p in folder.glob("*.py")]
    forbidden = {
        "ExecutionCoordinator",
        "ExecutionObservationAdapter",
        "PlanRunReducer",
        "RecordObservationUpdate",
        "StepOutcomeEvaluator",
        "PlanStepEvidenceAssessor",
        "StepProgressTransitionDecider",
        "PlanRunController",
        "PlanStepExecutionStartCoordinator",
        "StepProgressUpdateSynthesizer",
        "PlanRunProgressAdvancer",
    }
    for tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not forbidden.intersection(alias.name for alias in node.names)
                assert node.module not in {"subprocess", "socket", "requests", "httpx"}
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {
                    "execute",
                    "commit_start",
                    "start",
                    "apply",
                    "assess",
                    "advance",
                    "decide",
                }
            assert not isinstance(node, (ast.While, ast.AsyncFor))
    composer = ast.parse((folder / "composer.py").read_text(encoding="utf-8"))
    calls = [
        n.func.attr
        for n in ast.walk(composer)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    ]
    assert calls.count("compose") == calls.count("record") == 1
    source = (folder / "models.py").read_text(encoding="utf-8")
    assert "observations[:-1]" not in source
    assert "observations[-1]" not in source
