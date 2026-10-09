"""WP053: synthesize one inert Step C update from exact WP052 lineage."""

from __future__ import annotations

import ast
import inspect
import json
from dataclasses import FrozenInstanceError, fields
from datetime import timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

import iris.plan_step_execution_progress_update_post_recording_composition as api
from iris.execution import ExecutionStatus
from iris.orchestrator import HandlingKind
from iris.outcome_assessment import StepOutcomeStatus
from iris.plan_runs import RunProvenance, StepProgressState
from iris.plan_step_execution_evidence_assessment_post_recording_composition import (
    PlanStepExecutionEvidenceAssessmentPostRecordingComposer,
)
from iris.plan_step_execution_progress_update_post_recording_composition import (
    PlanStepExecutionProgressUpdatePostRecordingComposer as Composer,
)
from iris.plan_step_execution_progress_update_post_recording_composition import (
    PlanStepExecutionProgressUpdatePostRecordingCompositionInvariantError as Invariant,
)
from iris.plan_step_execution_progress_update_post_recording_composition import (
    PlanStepExecutionProgressUpdatePostRecordingCompositionResult as Result,
)
from iris.plan_step_execution_result_recording_post_recording_composition import (
    PlanStepExecutionResultRecordingPostRecordingComposer,
)
from iris.plan_step_execution_transition_decision_post_recording_composition import (
    PlanStepExecutionTransitionDecisionPostRecordingComposer as Upstream,
)
from iris.plan_step_execution_transition_decision_post_recording_composition import (
    PlanStepExecutionTransitionDecisionPostRecordingCompositionResult,
)
from iris.step_progress_transition import (
    StepProgressTransitionAction,
    StepProgressTransitionReason,
)
from iris.step_progress_update_synthesis import StepProgressUpdateSynthesizer
from tests.test_plan_step_execution_binding_post_recording_composition import operands
from tests.test_plan_step_execution_evidence_assessment_composition import (
    RecordingAssessor,
    assessor_for,
    unsafe_clone,
)
from tests.test_plan_step_execution_evidence_assessment_post_recording_composition import (
    canonical_wp050_with_prior_evidence,
)
from tests.test_plan_step_execution_evidence_assessment_post_recording_composition import (
    invoke as invoke_wp051,
)
from tests.test_plan_step_execution_progress_update_composition import (
    RecordingSynthesizer as WP041Synthesizer,
)
from tests.test_plan_step_execution_result_recording_post_recording_composition import (
    RecordingWP049,
    canonical_wp049,
    recorder_for,
)
from tests.test_plan_step_execution_transition_decision_post_recording_composition import (
    RecordingWP051,
    canonical_wp051,
    decider_for,
)
from tests.test_plan_step_execution_transition_decision_post_recording_composition import (
    invoke as invoke_wp052,
)


class RecordingWP052(Upstream):
    def __init__(
        self,
        result: Any = None,
        *,
        error: Exception | None = None,
        delegate: Upstream | None = None,
    ) -> None:
        super().__init__(evidence_assessment_composer=RecordingWP051())
        self.result = result
        self.error = error
        self.delegate = delegate
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def compose(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        if self.delegate is not None:
            return self.delegate.compose(*args, **kwargs)
        return self.result


class RecordingSynthesizer(StepProgressUpdateSynthesizer):
    def __init__(
        self,
        result: Any,
        *,
        forced: Any = None,
        error: Exception | None = None,
        update_ids: tuple[str, ...] = ("step-c-update-1",),
    ) -> None:
        recording = result.post_recording_execution_recording_result
        decision = result.post_recording_execution_transition_decision
        assert recording is not None and decision is not None
        timestamp = max(recording.recorded_run.updated_at, decision.decided_at)
        identifiers = iter(update_ids)
        super().__init__(
            clock=lambda: timestamp,
            update_id_factory=lambda: next(identifiers),
        )
        self.forced = forced
        self.error = error
        self.calls: list[tuple[Any, ...]] = []
        self.results: list[Any] = []

    def synthesize(self, *args: Any) -> Any:
        self.calls.append(args)
        if self.error is not None:
            raise self.error
        output = self.forced if self.forced is not None else super().synthesize(*args)
        self.results.append(output)
        return output


def scenario(
    *,
    status: StepOutcomeStatus = StepOutcomeStatus.SATISFIED,
    execution_status: ExecutionStatus = ExecutionStatus.SUCCEEDED,
    unavailable: bool = False,
    handling: HandlingKind | None = HandlingKind.CAPABILITY,
) -> tuple[Any, Any, PlanStepExecutionTransitionDecisionPostRecordingCompositionResult]:
    plan, run, wp051 = canonical_wp051(
        assessment_status=status,
        execution_status=execution_status,
        unavailable=unavailable,
        handling=handling,
    )
    decider = (
        None
        if wp051.post_recording_execution_assessment is None
        else decider_for(wp051)
    )
    wp052, _ = invoke_wp052(plan, run, wp051, decider)
    return plan, run, wp052


def invoke(
    plan: Any,
    run: Any,
    upstream_result: Any,
    synthesizer: StepProgressUpdateSynthesizer | None = None,
    **overrides: Any,
) -> tuple[Result, RecordingWP052]:
    upstream = RecordingWP052(upstream_result)
    kwargs = operands(upstream_result)
    kwargs.update(overrides)
    output = Composer(
        transition_decision_composer=upstream,
        progress_update_synthesizer=synthesizer,
    ).compose(plan, run, "a", **kwargs)
    return output, upstream


def test_public_contract_and_constructor() -> None:
    assert api.__all__ == [
        "PlanStepExecutionProgressUpdatePostRecordingComposer",
        "PlanStepExecutionProgressUpdatePostRecordingCompositionResult",
        "PlanStepExecutionProgressUpdatePostRecordingCompositionError",
        "PlanStepExecutionProgressUpdatePostRecordingCompositionInvariantError",
    ]
    assert issubclass(
        Invariant, api.PlanStepExecutionProgressUpdatePostRecordingCompositionError
    )
    assert issubclass(
        Result, PlanStepExecutionTransitionDecisionPostRecordingCompositionResult
    )
    assert (
        inspect.signature(Composer.compose).parameters
        == inspect.signature(Upstream.compose).parameters
    )
    assert list(inspect.signature(Composer).parameters) == [
        "transition_decision_composer",
        "progress_update_synthesizer",
    ]
    for invalid in (None, object()):
        with pytest.raises(TypeError):
            Composer(transition_decision_composer=invalid)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Composer(
            transition_decision_composer=RecordingWP052(),
            progress_update_synthesizer=object(),  # type: ignore[arg-type]
        )


def test_absent_decision_skips_synthesis_and_preserves_identity() -> None:
    plan, run, upstream_result = scenario(handling=None)
    synth = WP041Synthesizer()
    output, upstream = invoke(plan, run, upstream_result, synth)
    assert len(upstream.calls) == 1
    assert synth.calls == []
    assert output.post_recording_execution_transition_decision is None
    assert output.post_recording_execution_progress_update is None
    for field in fields(
        PlanStepExecutionTransitionDecisionPostRecordingCompositionResult
    ):
        assert getattr(output, field.name) is getattr(upstream_result, field.name)


@pytest.mark.parametrize(
    ("status", "unavailable"),
    [
        (StepOutcomeStatus.INDETERMINATE, False),
        (StepOutcomeStatus.NOT_SATISFIED, False),
        (StepOutcomeStatus.INSUFFICIENT_EVIDENCE, False),
        (StepOutcomeStatus.SATISFIED, True),
    ],
)
def test_present_no_transition_skips_synthesis(
    status: StepOutcomeStatus, unavailable: bool
) -> None:
    plan, run, upstream_result = scenario(status=status, unavailable=unavailable)
    synth = WP041Synthesizer()
    output, _ = invoke(plan, run, upstream_result, synth)
    assert synth.calls == []
    assert output.post_recording_execution_transition_decision is (
        upstream_result.post_recording_execution_transition_decision
    )
    assert output.post_recording_execution_progress_update is None
    assert output.post_recording_execution_transition_decision.action is (
        StepProgressTransitionAction.NO_TRANSITION
    )
    if unavailable:
        assert output.post_recording_execution_transition_decision.reason is (
            StepProgressTransitionReason.STEP_NOT_STARTED
        )
        recording = output.post_recording_execution_recording_result
        assert recording is not None
        assert (
            next(
                item.state
                for item in recording.recorded_run.step_progress
                if item.step_id == recording.step_id
            )
            is StepProgressState.NOT_STARTED
        )


def test_exact_forwarding_and_actionable_step_c_lineage() -> None:
    plan, run, upstream_result = scenario()
    synth = RecordingSynthesizer(upstream_result)
    kwargs = operands(upstream_result)
    upstream = RecordingWP052(upstream_result)
    output = Composer(
        transition_decision_composer=upstream,
        progress_update_synthesizer=synth,
    ).compose(plan, run, "a", **kwargs)
    assert len(upstream.calls) == 1
    positional, forwarded = upstream.calls[0]
    assert positional == (plan, run, "a")
    assert forwarded.keys() == kwargs.keys()
    for name, value in kwargs.items():
        assert forwarded[name] is value
    recording = upstream_result.post_recording_execution_recording_result
    assessment = upstream_result.post_recording_execution_assessment
    decision = upstream_result.post_recording_execution_transition_decision
    assert recording is not None and assessment is not None and decision is not None
    assert synth.calls == [(plan, recording.recorded_run, assessment, decision)]
    update = output.post_recording_execution_progress_update
    assert update is synth.results[0]
    assert update.run_id == recording.recorded_run.run_id
    assert update.expected_revision == recording.recorded_run.revision
    assert update.step_id == recording.step_id
    assert update.new_state is decision.target_state is StepProgressState.SUCCEEDED
    assert update.evidence_ids == assessment.evidence_ids
    assert update.provenance == RunProvenance(
        source_type="step_progress_transition", source_id=decision.decision_id
    )
    assert update.updated_at == decision.decided_at
    assert update is not output.progress_update
    assert update is not output.post_recording_progress_update
    for field in fields(
        PlanStepExecutionTransitionDecisionPostRecordingCompositionResult
    ):
        assert getattr(output, field.name) is getattr(upstream_result, field.name)
    assert (
        recording.recorded_run
        is upstream_result.post_recording_execution_recording_result.recorded_run
    )


@pytest.mark.parametrize(
    "execution_status",
    [ExecutionStatus.SUCCEEDED, ExecutionStatus.FAILED, ExecutionStatus.REJECTED],
)
def test_execution_status_does_not_control_synthesis(
    execution_status: ExecutionStatus,
) -> None:
    plan, run, upstream_result = scenario(execution_status=execution_status)
    synth = RecordingSynthesizer(upstream_result)
    output, _ = invoke(plan, run, upstream_result, synth)
    assert len(synth.calls) == 1
    assert output.post_recording_execution_progress_update is synth.results[0]
    assert (
        output.post_recording_execution_transition_decision.action
        is StepProgressTransitionAction.TRANSITION
    )


def test_result_is_frozen_slotted_and_serializes_exact_inheritance() -> None:
    plan, run, upstream_result = scenario()
    output, _ = invoke(
        plan, run, upstream_result, RecordingSynthesizer(upstream_result)
    )
    with pytest.raises(FrozenInstanceError):
        output.post_recording_execution_progress_update = None  # type: ignore[misc]
    assert "__dict__" not in Result.__slots__
    inherited = upstream_result.to_data()
    data = output.to_data()
    assert {key: data[key] for key in inherited} == inherited
    assert data["post_recording_execution_progress_update"] == (
        output.post_recording_execution_progress_update.to_data()
    )
    assert json.loads(json.dumps(data, sort_keys=True)) == data
    assert json.dumps(data, sort_keys=True) == json.dumps(
        output.to_data(), sort_keys=True
    )


def test_lazy_unreachable_step_c_input_is_forwarded_unchanged() -> None:
    plan, run, wp049 = canonical_wp049(handling=None)
    wp050 = PlanStepExecutionResultRecordingPostRecordingComposer(
        start_composer=RecordingWP049(wp049), result_recorder=recorder_for(wp049)
    )
    wp051 = PlanStepExecutionEvidenceAssessmentPostRecordingComposer(
        recording_composer=wp050
    )
    wp052 = Upstream(evidence_assessment_composer=wp051)
    upstream = RecordingWP052(delegate=wp052)
    invalid_unused = object()
    kwargs = operands(wp049)
    kwargs["post_recording_execution_input"] = invalid_unused
    output = Composer(transition_decision_composer=upstream).compose(
        plan, run, "a", **kwargs
    )
    assert len(upstream.calls) == 1
    assert upstream.calls[0][1]["post_recording_execution_input"] is invalid_unused
    assert output.post_recording_execution_progress_update is None


def test_complete_step_c_evidence_is_bound_in_canonical_order() -> None:
    plan, run, wp050 = canonical_wp050_with_prior_evidence(
        step_c_observation_ids=("aaa-prior-c", "ddd-prior-c"),
        new_observation_id="ccc-execution-observation-c",
    )
    recording = wp050.post_recording_execution_recording_result
    assert recording is not None
    latest = max(item.observed_at for item in recording.recorded_run.observations)
    assessor, _ = assessor_for(
        StepOutcomeStatus.SATISFIED,
        assessed_at=latest + timedelta(seconds=1),
        assessment_ids=["step-c-assessment-1"],
    )
    wp051, _ = invoke_wp051(plan, run, wp050, RecordingAssessor(assessor))
    wp052, _ = invoke_wp052(plan, run, wp051, decider_for(wp051))
    output, _ = invoke(plan, run, wp052, RecordingSynthesizer(wp052))
    update = output.post_recording_execution_progress_update
    assert update is not None
    expected = tuple(
        item.observation_id
        for item in recording.recorded_run.observations
        if item.step_id == recording.step_id
    )
    assert expected == ("aaa-prior-c", "ccc-execution-observation-c", "ddd-prior-c")
    assert update.evidence_ids == expected


def test_upstream_and_synthesizer_errors_propagate_without_retry() -> None:
    plan, run, upstream_result = scenario()
    error = RuntimeError("upstream failed")
    upstream = RecordingWP052(error=error)
    synth = RecordingSynthesizer(upstream_result)
    with pytest.raises(RuntimeError) as raised:
        Composer(
            transition_decision_composer=upstream,
            progress_update_synthesizer=synth,
        ).compose(plan, run, "a", **operands(upstream_result))
    assert raised.value is error
    assert len(upstream.calls) == 1 and synth.calls == []

    error = RuntimeError("synthesis failed")
    synth = RecordingSynthesizer(upstream_result, error=error)
    with pytest.raises(RuntimeError) as raised:
        invoke(plan, run, upstream_result, synth)
    assert raised.value is error
    assert len(synth.calls) == 1


@pytest.mark.parametrize(
    "malformation",
    [
        "wrong_type",
        "missing_assessment",
        "wrong_decision",
        "wrong_recording",
        "incomplete_evidence",
    ],
)
def test_malformed_wp052_fails_before_synthesis(malformation: str) -> None:
    plan, run, upstream_result = scenario()
    assessment = upstream_result.post_recording_execution_assessment
    decision = upstream_result.post_recording_execution_transition_decision
    recording = upstream_result.post_recording_execution_recording_result
    assert assessment is not None and decision is not None and recording is not None
    if malformation == "wrong_type":
        malformed: Any = object()
    elif malformation == "missing_assessment":
        malformed = unsafe_clone(
            upstream_result, post_recording_execution_assessment=None
        )
    elif malformation == "wrong_decision":
        malformed = unsafe_clone(
            upstream_result,
            post_recording_execution_transition_decision=unsafe_clone(
                decision, assessment_id="foreign-assessment"
            ),
        )
    elif malformation == "wrong_recording":
        malformed = unsafe_clone(
            upstream_result,
            post_recording_execution_recording_result=unsafe_clone(
                recording, run_id="foreign-run"
            ),
        )
    else:
        malformed = unsafe_clone(
            upstream_result,
            post_recording_execution_assessment=unsafe_clone(
                assessment, evidence_ids=()
            ),
        )
    synth = RecordingSynthesizer(upstream_result)
    upstream = RecordingWP052(malformed)
    with pytest.raises(Invariant):
        Composer(
            transition_decision_composer=upstream,
            progress_update_synthesizer=synth,
        ).compose(plan, run, "a", **operands(upstream_result))
    assert len(upstream.calls) == 1 and synth.calls == []


@pytest.mark.parametrize(
    ("field_name", "replacement"),
    [
        ("run_id", "foreign-run"),
        ("expected_revision", 999),
        ("step_id", "foreign-step"),
        ("new_state", StepProgressState.FAILED),
        ("evidence_ids", ("other-evidence",)),
        ("update_id", " bad-id "),
    ],
)
def test_malformed_update_lineage_is_rejected(
    field_name: str, replacement: Any
) -> None:
    plan, run, upstream_result = scenario()
    decision = upstream_result.post_recording_execution_transition_decision
    recording = upstream_result.post_recording_execution_recording_result
    assessment = upstream_result.post_recording_execution_assessment
    assert decision is not None and recording is not None and assessment is not None
    canonical = RecordingSynthesizer(upstream_result).synthesize(
        plan, recording.recorded_run, assessment, decision
    )
    forged = unsafe_clone(canonical, **{field_name: replacement})
    synth = RecordingSynthesizer(upstream_result, forced=forged)
    with pytest.raises(Invariant):
        invoke(plan, run, upstream_result, synth)
    assert len(synth.calls) == 1


@pytest.mark.parametrize(
    "provenance",
    [
        RunProvenance(source_type="other", source_id="step-c-transition-decision-1"),
        RunProvenance(source_type="step_progress_transition", source_id="other"),
        RunProvenance(
            source_type="step_progress_transition",
            source_id="step-c-transition-decision-1",
            actor="other",
        ),
    ],
)
def test_malformed_provenance_is_rejected(provenance: RunProvenance) -> None:
    plan, run, upstream_result = scenario()
    recording = upstream_result.post_recording_execution_recording_result
    assessment = upstream_result.post_recording_execution_assessment
    decision = upstream_result.post_recording_execution_transition_decision
    assert recording is not None and assessment is not None and decision is not None
    canonical = RecordingSynthesizer(upstream_result).synthesize(
        plan, recording.recorded_run, assessment, decision
    )
    with pytest.raises(Invariant):
        invoke(
            plan,
            run,
            upstream_result,
            RecordingSynthesizer(
                upstream_result, forced=unsafe_clone(canonical, provenance=provenance)
            ),
        )


@pytest.mark.parametrize("boundary", ["run", "decision"])
def test_predating_timestamp_is_rejected(boundary: str) -> None:
    plan, run, upstream_result = scenario()
    recording = upstream_result.post_recording_execution_recording_result
    assessment = upstream_result.post_recording_execution_assessment
    decision = upstream_result.post_recording_execution_transition_decision
    assert recording is not None and assessment is not None and decision is not None
    canonical = RecordingSynthesizer(upstream_result).synthesize(
        plan, recording.recorded_run, assessment, decision
    )
    timestamp = (
        recording.recorded_run.updated_at if boundary == "run" else decision.decided_at
    ) - timedelta(microseconds=1)
    with pytest.raises(Invariant):
        invoke(
            plan,
            run,
            upstream_result,
            RecordingSynthesizer(
                upstream_result, forced=unsafe_clone(canonical, updated_at=timestamp)
            ),
        )


def test_wrong_type_and_noncanonical_model_are_rejected_without_repair() -> None:
    plan, run, upstream_result = scenario()
    recording = upstream_result.post_recording_execution_recording_result
    assessment = upstream_result.post_recording_execution_assessment
    decision = upstream_result.post_recording_execution_transition_decision
    assert recording is not None and assessment is not None and decision is not None
    canonical = RecordingSynthesizer(upstream_result).synthesize(
        plan, recording.recorded_run, assessment, decision
    )
    for forged in (
        object(),
        unsafe_clone(canonical, evidence_ids=list(canonical.evidence_ids)),
        unsafe_clone(canonical, update_id=assessment.assessment_id),
        unsafe_clone(
            canonical,
            updated_at=canonical.updated_at.astimezone(timezone(timedelta(hours=1))),
        ),
    ):
        with pytest.raises(Invariant):
            invoke(
                plan,
                run,
                upstream_result,
                RecordingSynthesizer(upstream_result, forced=forged),
            )


def test_presence_equivalence_and_distinct_earlier_updates() -> None:
    plan, run, upstream_result = scenario()
    result, _ = invoke(
        plan, run, upstream_result, RecordingSynthesizer(upstream_result)
    )
    with pytest.raises(Invariant):
        Result.__post_init__(
            unsafe_clone(result, post_recording_execution_progress_update=None)
        )
    no_plan, no_run, abstention = scenario(status=StepOutcomeStatus.INDETERMINATE)
    abstention_result, _ = invoke(no_plan, no_run, abstention)
    update = result.post_recording_execution_progress_update
    assert update is not None
    with pytest.raises(Invariant):
        Result.__post_init__(
            unsafe_clone(
                abstention_result,
                post_recording_execution_progress_update=update,
            )
        )
    assert no_plan is not None and no_run is not None
    # The inherited WP041 result rejects a foreign earlier update first.
    with pytest.raises(RuntimeError):
        Result.__post_init__(
            unsafe_clone(result, post_recording_progress_update=update)
        )


def test_repeated_invocations_are_independent() -> None:
    plan, run, upstream_result = scenario()
    synth = RecordingSynthesizer(
        upstream_result, update_ids=("step-c-update-1", "step-c-update-2")
    )
    upstream = RecordingWP052(upstream_result)
    composer = Composer(
        transition_decision_composer=upstream,
        progress_update_synthesizer=synth,
    )
    kwargs = operands(upstream_result)
    first = composer.compose(plan, run, "a", **kwargs)
    second = composer.compose(plan, run, "a", **kwargs)
    assert len(upstream.calls) == len(synth.calls) == 2
    assert first.post_recording_execution_progress_update is not (
        second.post_recording_execution_progress_update
    )
    assert first.post_recording_execution_progress_update.update_id != (
        second.post_recording_execution_progress_update.update_id
    )


def test_package_has_no_reducer_execution_or_continuation_authority() -> None:
    package = Path(api.__file__).parent
    forbidden = {
        "PlanRunReducer",
        "PlanRunController",
        "PlanRunProgressAdvancer",
        "StepProgressTransitionDecider",
        "StepOutcomeEvaluator",
        "ExecutionCoordinator",
    }
    for source in package.glob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        assert imported.isdisjoint(forbidden)
        assert not any(
            isinstance(node, (ast.For, ast.While)) for node in ast.walk(tree)
        )
