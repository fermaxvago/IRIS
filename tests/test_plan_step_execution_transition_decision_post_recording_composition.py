"""WP052: decide over exact Step C complete evidence, then stop without mutation."""

from __future__ import annotations

import ast
import inspect
import json
from dataclasses import FrozenInstanceError, fields
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

import iris.plan_step_execution_transition_decision_post_recording_composition as api
from iris.execution import ExecutionStatus
from iris.orchestrator import HandlingKind
from iris.outcome_assessment import StepOutcomeStatus
from iris.plan_runs import StepProgressState
from iris.plan_step_execution_evidence_assessment_post_recording_composition import (
    PlanStepExecutionEvidenceAssessmentPostRecordingComposer as Upstream,
)
from iris.plan_step_execution_evidence_assessment_post_recording_composition import (
    PlanStepExecutionEvidenceAssessmentPostRecordingCompositionResult,
)
from iris.plan_step_execution_result_recording_post_recording_composition import (
    PlanStepExecutionResultRecordingPostRecordingComposer,
)
from iris.plan_step_execution_transition_decision_post_recording_composition import (
    PlanStepExecutionTransitionDecisionPostRecordingComposer as Composer,
)
from iris.plan_step_execution_transition_decision_post_recording_composition import (
    PlanStepExecutionTransitionDecisionPostRecordingCompositionInvariantError as Invariant,
)
from iris.plan_step_execution_transition_decision_post_recording_composition import (
    PlanStepExecutionTransitionDecisionPostRecordingCompositionResult as Result,
)
from iris.step_progress_transition import (
    StepProgressTransitionAction,
    StepProgressTransitionDecider,
    StepProgressTransitionReason,
)
from tests.test_plan_step_execution_binding_post_recording_composition import operands
from tests.test_plan_step_execution_evidence_assessment_composition import (
    RecordingAssessor,
    assessor_for,
    unsafe_clone,
)
from tests.test_plan_step_execution_evidence_assessment_post_recording_composition import (
    RecordingWP050,
    canonical_wp050,
    canonical_wp050_with_prior_evidence,
    deterministic_assessor,
    selected_state,
)
from tests.test_plan_step_execution_evidence_assessment_post_recording_composition import (
    invoke as invoke_wp051,
)
from tests.test_plan_step_execution_result_recording_post_recording_composition import (
    RecordingWP049,
    canonical_wp049,
    recorder_for,
)

UNSET = object()


class RecordingWP051(Upstream):
    def __init__(
        self,
        result: Any = None,
        *,
        error: Exception | None = None,
        delegate: Upstream | None = None,
    ) -> None:
        super().__init__(recording_composer=RecordingWP050())
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


class RecordingDecider(StepProgressTransitionDecider):
    def __init__(
        self,
        *,
        decided_at: Any = None,
        forced: Any = UNSET,
        error: Exception | None = None,
        decision_ids: tuple[str, ...] = ("step-c-transition-decision-1",),
    ) -> None:
        identifiers = iter(decision_ids)
        super().__init__(
            clock=lambda: decided_at,
            decision_id_factory=lambda: next(identifiers),
        )
        self.forced = forced
        self.error = error
        self.calls: list[tuple[Any, ...]] = []
        self.results: list[Any] = []

    def decide(self, *args: Any) -> Any:
        self.calls.append(args)
        if self.error is not None:
            raise self.error
        result = super().decide(*args) if self.forced is UNSET else self.forced
        self.results.append(result)
        return result


def canonical_wp051(
    *,
    assessment_status: StepOutcomeStatus = StepOutcomeStatus.INDETERMINATE,
    execution_status: ExecutionStatus = ExecutionStatus.SUCCEEDED,
    unavailable: bool = False,
    handling: HandlingKind | None = HandlingKind.CAPABILITY,
) -> tuple[Any, Any, PlanStepExecutionEvidenceAssessmentPostRecordingCompositionResult]:
    plan, run, wp050 = canonical_wp050(
        handling=handling,
        unavailable=unavailable,
        status=execution_status,
    )
    recording = wp050.post_recording_execution_recording_result
    if recording is None:
        result, _ = invoke_wp051(plan, run, wp050)
        return plan, run, result
    latest = max(item.observed_at for item in recording.recorded_run.observations)
    assessor, _ = assessor_for(
        assessment_status,
        assessed_at=latest + timedelta(seconds=1),
        assessment_ids=["step-c-assessment-1"],
    )
    result, _ = invoke_wp051(
        plan,
        run,
        wp050,
        RecordingAssessor(assessor),
    )
    return plan, run, result


def decider_for(result: Any, **kwargs: Any) -> RecordingDecider:
    recording = result.post_recording_execution_recording_result
    assessment = result.post_recording_execution_assessment
    assert recording is not None and assessment is not None
    decided_at = max(recording.recorded_run.updated_at, assessment.assessed_at)
    return RecordingDecider(decided_at=decided_at + timedelta(seconds=1), **kwargs)


def invoke(
    plan: Any,
    run: Any,
    result: Any,
    decider: StepProgressTransitionDecider | None = None,
    **overrides: Any,
) -> tuple[Result, RecordingWP051]:
    upstream = RecordingWP051(result)
    kwargs = operands(result)
    kwargs.update(overrides)
    output = Composer(
        evidence_assessment_composer=upstream,
        transition_decider=decider,
    ).compose(plan, run, "a", **kwargs)
    return output, upstream


def test_public_api_dependencies_and_exact_signatures() -> None:
    assert api.__all__ == [
        "PlanStepExecutionTransitionDecisionPostRecordingComposer",
        "PlanStepExecutionTransitionDecisionPostRecordingCompositionResult",
        "PlanStepExecutionTransitionDecisionPostRecordingCompositionError",
        "PlanStepExecutionTransitionDecisionPostRecordingCompositionInvariantError",
    ]
    assert issubclass(
        Invariant,
        api.PlanStepExecutionTransitionDecisionPostRecordingCompositionError,
    )
    assert issubclass(
        Result,
        PlanStepExecutionEvidenceAssessmentPostRecordingCompositionResult,
    )
    assert (
        inspect.signature(Composer.compose).parameters
        == inspect.signature(Upstream.compose).parameters
    )
    assert list(inspect.signature(Composer).parameters) == [
        "evidence_assessment_composer",
        "transition_decider",
    ]
    for bad in (None, object(), lambda: None):
        with pytest.raises(TypeError):
            Composer(evidence_assessment_composer=bad)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Composer(
            evidence_assessment_composer=RecordingWP051(),
            transition_decider=object(),  # type: ignore[arg-type]
        )


def test_no_step_c_assessment_preserves_wp051_and_skips_wp021() -> None:
    plan, run, result = canonical_wp051(handling=None)
    decider = RecordingDecider(decided_at=None)

    output, upstream = invoke(plan, run, result, decider)

    assert len(upstream.calls) == 1
    assert decider.calls == []
    assert output.post_recording_execution_assessment is None
    assert output.post_recording_execution_transition_decision is None
    for item in fields(
        PlanStepExecutionEvidenceAssessmentPostRecordingCompositionResult
    ):
        assert getattr(output, item.name) is getattr(result, item.name)


def test_exact_wp051_input_surface_is_forwarded_once() -> None:
    plan, run, result = canonical_wp051(handling=None)
    kwargs = operands(result)
    upstream = RecordingWP051(result)

    Composer(evidence_assessment_composer=upstream).compose(
        plan,
        run,
        "a",
        **kwargs,
    )

    assert len(upstream.calls) == 1
    positional, forwarded = upstream.calls[0]
    assert positional == (plan, run, "a")
    assert forwarded.keys() == kwargs.keys()
    for name, value in kwargs.items():
        assert forwarded[name] is value


def test_wp052_preserves_inherited_lazy_unreachable_input_validation() -> None:
    plan, run, wp049 = canonical_wp049(handling=None)
    recorder = recorder_for(wp049)
    actual_wp050 = PlanStepExecutionResultRecordingPostRecordingComposer(
        start_composer=RecordingWP049(wp049),
        result_recorder=recorder,
    )
    actual_wp051 = Upstream(recording_composer=actual_wp050)
    upstream = RecordingWP051(delegate=actual_wp051)
    kwargs = operands(wp049)
    invalid_unused_input = object()
    kwargs["post_recording_execution_input"] = invalid_unused_input

    output = Composer(evidence_assessment_composer=upstream).compose(
        plan,
        run,
        "a",
        **kwargs,
    )

    assert len(upstream.calls) == 1
    assert output.post_recording_execution_assessment is None
    assert output.post_recording_execution_transition_decision is None
    assert recorder.calls == []


def test_handler_unavailable_produces_present_step_not_started_decision() -> None:
    plan, run, result = canonical_wp051(unavailable=True)
    recording = result.post_recording_execution_recording_result
    assessment = result.post_recording_execution_assessment
    assert recording is not None and assessment is not None
    assert selected_state(result) is StepProgressState.NOT_STARTED
    decider = decider_for(result)

    output, _ = invoke(plan, run, result, decider)

    decision = output.post_recording_execution_transition_decision
    assert decision is decider.results[0]
    assert decision.action is StepProgressTransitionAction.NO_TRANSITION
    assert decision.reason is StepProgressTransitionReason.STEP_NOT_STARTED
    assert decision.source_state is StepProgressState.NOT_STARTED
    assert selected_state(output) is StepProgressState.NOT_STARTED


@pytest.mark.parametrize(
    ("status", "action", "target", "reason"),
    [
        (
            StepOutcomeStatus.SATISFIED,
            StepProgressTransitionAction.TRANSITION,
            StepProgressState.SUCCEEDED,
            StepProgressTransitionReason.OUTCOME_SATISFIED,
        ),
        (
            StepOutcomeStatus.NOT_SATISFIED,
            StepProgressTransitionAction.NO_TRANSITION,
            None,
            StepProgressTransitionReason.OUTCOME_NOT_SATISFIED,
        ),
        (
            StepOutcomeStatus.INSUFFICIENT_EVIDENCE,
            StepProgressTransitionAction.NO_TRANSITION,
            None,
            StepProgressTransitionReason.INSUFFICIENT_EVIDENCE,
        ),
        (
            StepOutcomeStatus.INDETERMINATE,
            StepProgressTransitionAction.NO_TRANSITION,
            None,
            StepProgressTransitionReason.INDETERMINATE_OUTCOME,
        ),
    ],
)
def test_active_conservative_policy_is_preserved_without_application(
    status: StepOutcomeStatus,
    action: StepProgressTransitionAction,
    target: StepProgressState | None,
    reason: StepProgressTransitionReason,
) -> None:
    plan, run, result = canonical_wp051(assessment_status=status)
    recording = result.post_recording_execution_recording_result
    assert recording is not None
    before = recording.recorded_run.to_data()
    decider = decider_for(result)

    output, _ = invoke(plan, run, result, decider)

    decision = output.post_recording_execution_transition_decision
    assert decision is not None
    assert decision.action is action
    assert decision.target_state is target
    assert decision.reason is reason
    assert selected_state(output) is StepProgressState.ACTIVE
    assert recording.recorded_run.to_data() == before


@pytest.mark.parametrize(
    "execution_status",
    [ExecutionStatus.SUCCEEDED, ExecutionStatus.FAILED, ExecutionStatus.REJECTED],
)
def test_execution_status_does_not_directly_determine_transition(
    execution_status: ExecutionStatus,
) -> None:
    plan, run, result = canonical_wp051(execution_status=execution_status)
    assert result.post_recording_execution_assessment is not None
    assert (
        result.post_recording_execution_assessment.status
        is StepOutcomeStatus.INDETERMINATE
    )

    output, _ = invoke(plan, run, result, decider_for(result))

    decision = output.post_recording_execution_transition_decision
    assert decision is not None
    assert decision.action is StepProgressTransitionAction.NO_TRANSITION
    assert decision.reason is StepProgressTransitionReason.INDETERMINATE_OUTCOME
    assert selected_state(output) is StepProgressState.ACTIVE


def test_wp021_receives_exact_plan_run_step_and_assessment() -> None:
    plan, run, result = canonical_wp051()
    recording = result.post_recording_execution_recording_result
    assessment = result.post_recording_execution_assessment
    assert recording is not None and assessment is not None
    canonical_step = next(
        item for item in plan.steps if item.step_id == recording.step_id
    )
    decider = decider_for(result)

    output, _ = invoke(plan, run, result, decider)

    assert decider.calls == [(plan, recording.recorded_run, canonical_step, assessment)]
    decision = output.post_recording_execution_transition_decision
    assert decision is not None
    assert decision.plan_id == recording.plan_id == assessment.plan_id
    assert decision.run_id == recording.run_id == assessment.run_id
    assert decision.step_id == recording.step_id == assessment.step_id
    assert decision.assessment_id == assessment.assessment_id
    assert decision.observed_revision == recording.recorded_run.revision
    assert decision.observed_revision == assessment.run_revision


def test_exact_decision_is_preserved_and_result_is_frozen_serializable() -> None:
    plan, run, result = canonical_wp051()
    decider = decider_for(result)

    output, _ = invoke(plan, run, result, decider)
    decision = output.post_recording_execution_transition_decision

    assert decision is decider.results[0]
    for item in fields(
        PlanStepExecutionEvidenceAssessmentPostRecordingCompositionResult
    ):
        assert getattr(output, item.name) is getattr(result, item.name)
    assert decision is not output.transition_decision
    assert decision is not output.post_recording_transition_decision
    with pytest.raises(FrozenInstanceError):
        output.post_recording_execution_transition_decision = None  # type: ignore[misc]
    assert "__dict__" not in Result.__slots__
    assert output.to_data()["post_recording_execution_transition_decision"] == (
        decision.to_data()
    )
    assert json.dumps(output.to_data(), sort_keys=True) == json.dumps(
        output.to_data(), sort_keys=True
    )

    missing = unsafe_clone(
        output,
        post_recording_execution_transition_decision=None,
    )
    with pytest.raises(Invariant):
        Result.__post_init__(missing)


def test_wp051_error_propagates_unchanged_and_wp021_is_unused() -> None:
    error = RuntimeError("wp051 failed")
    upstream = RecordingWP051(error=error)
    decider = RecordingDecider(decided_at=None)
    plan, run, result = canonical_wp051(handling=None)

    with pytest.raises(RuntimeError) as raised:
        Composer(
            evidence_assessment_composer=upstream,
            transition_decider=decider,
        ).compose(plan, run, "a", **operands(result))

    assert raised.value is error
    assert len(upstream.calls) == 1
    assert decider.calls == []


def test_wp021_error_propagates_unchanged_without_retry() -> None:
    plan, run, result = canonical_wp051()
    error = RuntimeError("decision failed")
    decider = decider_for(result, error=error)

    with pytest.raises(RuntimeError) as raised:
        invoke(plan, run, result, decider)

    assert raised.value is error
    assert len(decider.calls) == 1


@pytest.mark.parametrize(
    "malformation",
    ["wrong_type", "missing_recording", "wrong_assessment", "missing_evidence"],
)
def test_malformed_wp051_result_fails_before_wp021(malformation: str) -> None:
    plan, run, result = canonical_wp051()
    assessment = result.post_recording_execution_assessment
    assert assessment is not None
    if malformation == "wrong_type":
        malformed: object = object()
    elif malformation == "missing_recording":
        malformed = unsafe_clone(
            result,
            post_recording_execution_recording_result=None,
        )
    elif malformation == "wrong_assessment":
        malformed = unsafe_clone(
            result,
            post_recording_execution_assessment=unsafe_clone(
                assessment,
                run_id="foreign-run",
            ),
        )
    else:
        malformed = unsafe_clone(
            result,
            post_recording_execution_assessment=unsafe_clone(
                assessment,
                evidence_ids=(),
            ),
        )
    decider = decider_for(result)
    upstream = RecordingWP051(malformed)

    with pytest.raises(Invariant):
        Composer(
            evidence_assessment_composer=upstream,
            transition_decider=decider,
        ).compose(plan, run, "a", **operands(result))

    assert decider.calls == []


def test_reordered_complete_evidence_is_rejected_before_wp021() -> None:
    plan, run, wp050 = canonical_wp050_with_prior_evidence(
        step_c_observation_ids=("aaa-prior-c", "ddd-prior-c"),
        new_observation_id="ccc-execution-observation-c",
    )
    wp051, _ = invoke_wp051(
        plan,
        run,
        wp050,
        deterministic_assessor(wp050),
    )
    assessment = wp051.post_recording_execution_assessment
    assert assessment is not None and len(assessment.evidence_ids) == 3
    malformed = unsafe_clone(
        wp051,
        post_recording_execution_assessment=unsafe_clone(
            assessment,
            evidence_ids=tuple(reversed(assessment.evidence_ids)),
        ),
    )
    decider = decider_for(wp051)

    with pytest.raises(Invariant):
        invoke(plan, run, malformed, decider)

    assert decider.calls == []


@pytest.mark.parametrize(
    ("field_name", "replacement"),
    [
        ("plan_id", "foreign-plan"),
        ("run_id", "foreign-run"),
        ("step_id", "foreign-step"),
        ("observed_revision", 999),
        ("assessment_id", "foreign-assessment"),
        ("source_state", StepProgressState.NOT_STARTED),
    ],
)
def test_contradictory_decision_lineage_fails_closed(
    field_name: str,
    replacement: object,
) -> None:
    plan, run, result = canonical_wp051()
    canonical_decider = decider_for(result)
    recording = result.post_recording_execution_recording_result
    assessment = result.post_recording_execution_assessment
    assert recording is not None and assessment is not None
    step = next(item for item in plan.steps if item.step_id == recording.step_id)
    valid = canonical_decider.decide(
        plan,
        recording.recorded_run,
        step,
        assessment,
    )
    malformed = unsafe_clone(valid, **{field_name: replacement})
    decider = decider_for(result, forced=malformed)

    with pytest.raises(Invariant):
        invoke(plan, run, result, decider)

    assert len(decider.calls) == 1


@pytest.mark.parametrize("boundary", ["assessment", "run"])
def test_decision_timestamp_contract_is_enforced(boundary: str) -> None:
    plan, run, result = canonical_wp051()
    recording = result.post_recording_execution_recording_result
    assessment = result.post_recording_execution_assessment
    assert recording is not None and assessment is not None
    canonical_decider = decider_for(result)
    step = next(item for item in plan.steps if item.step_id == recording.step_id)
    valid = canonical_decider.decide(
        plan,
        recording.recorded_run,
        step,
        assessment,
    )
    if boundary == "assessment":
        decided_at = assessment.assessed_at - timedelta(microseconds=1)
    else:
        decided_at = recording.recorded_run.updated_at - timedelta(microseconds=1)
    malformed = unsafe_clone(valid, decided_at=decided_at)

    with pytest.raises(Invariant):
        invoke(plan, run, result, decider_for(result, forced=malformed))


def test_wrong_or_internally_forged_decision_fails_closed() -> None:
    plan, run, result = canonical_wp051(assessment_status=StepOutcomeStatus.SATISFIED)
    recording = result.post_recording_execution_recording_result
    assessment = result.post_recording_execution_assessment
    assert recording is not None and assessment is not None
    canonical_decider = decider_for(result)
    step = next(item for item in plan.steps if item.step_id == recording.step_id)
    valid = canonical_decider.decide(
        plan,
        recording.recorded_run,
        step,
        assessment,
    )
    forged = unsafe_clone(valid, target_state=None)

    with pytest.raises(Invariant):
        invoke(plan, run, result, decider_for(result, forced=forged))
    with pytest.raises(Invariant):
        invoke(plan, run, result, decider_for(result, forced=object()))


def test_repeated_invocations_have_no_hidden_deduplication() -> None:
    plan, run, result = canonical_wp051()
    recording = result.post_recording_execution_recording_result
    assessment = result.post_recording_execution_assessment
    assert recording is not None and assessment is not None
    decided_at = max(recording.recorded_run.updated_at, assessment.assessed_at)
    decider = RecordingDecider(
        decided_at=decided_at + timedelta(seconds=1),
        decision_ids=("step-c-transition-1", "step-c-transition-2"),
    )
    upstream = RecordingWP051(result)
    composer = Composer(
        evidence_assessment_composer=upstream,
        transition_decider=decider,
    )
    kwargs = operands(result)

    first = composer.compose(plan, run, "a", **kwargs)
    second = composer.compose(plan, run, "a", **kwargs)

    assert len(upstream.calls) == 2
    assert len(decider.calls) == 2
    assert first.post_recording_execution_transition_decision is not None
    assert second.post_recording_execution_transition_decision is not None
    assert (
        first.post_recording_execution_transition_decision.decision_id
        != second.post_recording_execution_transition_decision.decision_id
    )


def test_package_has_no_mutation_execution_or_continuation_authority() -> None:
    package = Path(api.__file__).parent
    forbidden = {
        "PlanRunReducer",
        "PlanRunProgressAdvancer",
        "StepProgressUpdate",
        "StepProgressUpdateSynthesizer",
        "PlanRunController",
        "ExecutionCoordinator",
        "PlanStepExecutionStartCoordinator",
        "PlanStepExecutionResultRecorder",
        "RecordObservationUpdate",
    }
    for source_path in package.glob("*.py"):
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        imports = {
            alias.name.rsplit(".", 1)[-1]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        assert forbidden.isdisjoint(names | imports)
        assert "Step D" not in source
        assert "retry" not in source.lower()
        assert "recursive" not in source.lower()
        assert not any(
            isinstance(node, (ast.For, ast.While)) for node in ast.walk(tree)
        )

    composer_tree = ast.parse((package / "composer.py").read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(composer_tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    assert sum(node.func.attr == "compose" for node in calls) == 1
    assert sum(node.func.attr == "decide" for node in calls) == 1
