"""WP051: assess exact complete Step C evidence after canonical recording, then stop."""

from __future__ import annotations

import ast
import inspect
import json
from dataclasses import FrozenInstanceError, fields
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

import iris.plan_step_execution_evidence_assessment_post_recording_composition as api
from iris.execution import ExecutionStatus
from iris.orchestrator import HandlingKind
from iris.outcome_assessment import (
    ConservativeStepOutcomeEvaluator,
    StepOutcomeStatus,
)
from iris.plan_runs import (
    PlanObservation,
    PlanRunReducer,
    RecordObservationUpdate,
    StepProgressState,
)
from iris.plan_step_evidence_assessment import PlanStepEvidenceAssessor
from iris.plan_step_execution_binding_post_recording_composition import (
    PlanStepExecutionBindingPostRecordingComposer,
)
from iris.plan_step_execution_evidence_assessment_post_recording_composition import (
    PlanStepExecutionEvidenceAssessmentPostRecordingComposer as Composer,
)
from iris.plan_step_execution_evidence_assessment_post_recording_composition import (
    PlanStepExecutionEvidenceAssessmentPostRecordingCompositionInvariantError as Invariant,
)
from iris.plan_step_execution_evidence_assessment_post_recording_composition import (
    PlanStepExecutionEvidenceAssessmentPostRecordingCompositionResult as Result,
)
from iris.plan_step_execution_result_recording_post_recording_composition import (
    PlanStepExecutionResultRecordingPostRecordingComposer as Upstream,
)
from iris.plan_step_execution_result_recording_post_recording_composition import (
    PlanStepExecutionResultRecordingPostRecordingCompositionResult,
)
from tests.test_plan_step_execution_binding_post_recording_composition import (
    RecordingWP047,
    operands,
)
from tests.test_plan_step_execution_context_materialization_composition import (
    compose_from_wp044,
)
from tests.test_plan_step_execution_evidence_assessment_composition import (
    BASE,
    BUDGET,
    CAPABILITY_AVAILABLE,
    CONTEXT_CREATED,
    PROVENANCE,
    CapabilityHandler,
    RecordingAssessor,
    assessor_for,
    capability_input,
    compose_from,
    make_plan,
    new_run,
    real_recording_composer,
    record_fixture_observation,
    step,
    transition,
    unsafe_clone,
)
from tests.test_plan_step_execution_handling_preparation_composition import (
    compose_from_wp042,
)
from tests.test_plan_step_execution_orchestration_composition import (
    compose_from_wp045,
)
from tests.test_plan_step_execution_progress_advancement_composition import (
    compose_from_wp041,
)
from tests.test_plan_step_execution_progress_update_composition import (
    compose_from_wp040,
)
from tests.test_plan_step_execution_request_materialization_composition import (
    compose_from_wp046,
)
from tests.test_plan_step_execution_result_recording_post_recording_composition import (
    RecordingWP049,
    canonical_wp049,
    recorder_for,
)
from tests.test_plan_step_execution_result_recording_post_recording_composition import (
    invoke as invoke_wp050,
)
from tests.test_plan_step_execution_start_post_recording_composition import (
    invoke as invoke_wp049,
)
from tests.test_plan_step_execution_start_post_recording_composition import (
    runtime,
)
from tests.test_plan_step_execution_transition_decision_composition import (
    compose_from_wp039,
)
from tests.test_plan_step_execution_work_subject_materialization_composition import (
    compose_from_wp043,
)


class RecordingWP050(Upstream):
    def __init__(
        self,
        result: Any = None,
        *,
        error: Exception | None = None,
        delegate: Upstream | None = None,
    ) -> None:
        super().__init__(start_composer=RecordingWP049())
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


def canonical_wp050(
    *,
    handling: HandlingKind | None = HandlingKind.CAPABILITY,
    unavailable: bool = False,
    status: ExecutionStatus = ExecutionStatus.SUCCEEDED,
    observation_id: str = "aaa-execution-observation-c",
) -> tuple[Any, Any, PlanStepExecutionResultRecordingPostRecordingCompositionResult]:
    plan, run, wp049 = canonical_wp049(
        handling=handling,
        unavailable=unavailable,
        status=status,
    )
    recorder = recorder_for(wp049, observation_id=observation_id)
    result, _ = invoke_wp050(plan, run, wp049, recorder)
    return plan, run, result


def canonical_wp050_with_prior_evidence(
    *,
    step_c_observation_ids: tuple[str, ...],
    new_observation_id: str,
) -> tuple[Any, Any, PlanStepExecutionResultRecordingPostRecordingCompositionResult]:
    """Build the real bounded chain with prior C, other-Step, and Run evidence."""

    plan = make_plan(
        step("a"),
        step("b", depends_on=("a",), handling=HandlingKind.CAPABILITY),
        step("c", depends_on=("b",), handling=HandlingKind.CAPABILITY),
    )
    run = transition(plan, new_run(plan), "a", StepProgressState.ACTIVE)
    run = record_fixture_observation(
        plan,
        run,
        observation_id="evidence-a",
        step_id="a",
        offset=2,
    )
    for offset, observation_id in enumerate(step_c_observation_ids, start=3):
        run = record_fixture_observation(
            plan,
            run,
            observation_id=observation_id,
            step_id="c",
            offset=offset,
        )
    run = record_fixture_observation(
        plan,
        run,
        observation_id="bbb-other-step-evidence-b",
        step_id="b",
        offset=10,
    )
    run_level = PlanObservation(
        observation_id="ccc-run-level-evidence",
        run_id=run.run_id,
        step_id=None,
        source="test",
        source_reference="source-ccc-run-level-evidence",
        observed_at=BASE + timedelta(seconds=11),
        kind="verification",
        data={"verified": True},
    )
    run = PlanRunReducer().apply(
        plan,
        run,
        RecordObservationUpdate(
            update_id="record-ccc-run-level-evidence",
            run_id=run.run_id,
            expected_revision=run.revision,
            updated_at=run_level.observed_at,
            provenance=PROVENANCE,
            observation=run_level,
        ),
    )

    wp038 = real_recording_composer(CapabilityHandler()).compose(
        plan,
        run,
        "a",
        candidates=(),
        budget=BUDGET,
        created_at=CONTEXT_CREATED,
        availability=CAPABILITY_AVAILABLE,
        execution_input=capability_input(),
    )
    source_assessor, _ = assessor_for(StepOutcomeStatus.SATISFIED)
    wp039, _, _ = compose_from(
        plan,
        run,
        wp038,
        assessor=RecordingAssessor(source_assessor),
    )
    wp040, _, _ = compose_from_wp039(plan, run, wp039)
    wp041, _, _ = compose_from_wp040(plan, run, wp040)
    wp042, _, _ = compose_from_wp041(plan, run, wp041)
    wp043, _, _ = compose_from_wp042(plan, run, wp042)
    wp044, _, _ = compose_from_wp043(plan, run, wp043)
    wp045, _, _ = compose_from_wp044(plan, run, wp044)
    wp046, _, _ = compose_from_wp045(plan, run, wp045)
    wp047, _ = compose_from_wp046(
        plan,
        run,
        wp046,
        post_execution_input=capability_input(),
    )
    wp048 = PlanStepExecutionBindingPostRecordingComposer(
        request_materialization_composer=RecordingWP047(wp047)
    ).compose(plan, run, "a", **operands(wp047))
    wp049, _ = invoke_wp049(
        plan,
        run,
        wp048,
        runtime(wp048, CapabilityHandler()),
    )
    wp050, _ = invoke_wp050(
        plan,
        run,
        wp049,
        recorder_for(wp049, observation_id=new_observation_id),
    )
    return plan, run, wp050


def selected_state(result: Any) -> StepProgressState:
    recording = result.post_recording_execution_recording_result
    assert recording is not None
    return next(
        item.state
        for item in recording.recorded_run.step_progress
        if item.step_id == recording.step_id
    )


def deterministic_assessor(result: Any) -> RecordingAssessor:
    recording = result.post_recording_execution_recording_result
    assert recording is not None
    latest = max(item.observed_at for item in recording.recorded_run.observations)
    delegate = PlanStepEvidenceAssessor(
        ConservativeStepOutcomeEvaluator(
            clock=lambda: latest + timedelta(seconds=1),
            assessment_id_factory=lambda: "step-c-assessment-1",
        )
    )
    return RecordingAssessor(delegate)


def invoke(
    plan: Any,
    run: Any,
    result: Any,
    assessor: PlanStepEvidenceAssessor | None = None,
    **overrides: Any,
) -> tuple[Result, RecordingWP050]:
    upstream = RecordingWP050(result)
    kwargs = operands(result)
    kwargs.update(overrides)
    output = Composer(recording_composer=upstream, assessor=assessor).compose(
        plan,
        run,
        "a",
        **kwargs,
    )
    return output, upstream


def test_public_api_dependencies_and_exact_signature() -> None:
    assert api.__all__ == [
        "PlanStepExecutionEvidenceAssessmentPostRecordingComposer",
        "PlanStepExecutionEvidenceAssessmentPostRecordingCompositionResult",
        "PlanStepExecutionEvidenceAssessmentPostRecordingCompositionError",
        "PlanStepExecutionEvidenceAssessmentPostRecordingCompositionInvariantError",
    ]
    assert issubclass(
        Invariant,
        api.PlanStepExecutionEvidenceAssessmentPostRecordingCompositionError,
    )
    assert issubclass(
        Result,
        PlanStepExecutionResultRecordingPostRecordingCompositionResult,
    )
    assert (
        inspect.signature(Composer.compose).parameters
        == inspect.signature(Upstream.compose).parameters
    )
    assert list(inspect.signature(Composer).parameters) == [
        "recording_composer",
        "assessor",
    ]
    for bad in (None, object(), lambda: None):
        with pytest.raises(TypeError):
            Composer(recording_composer=bad)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Composer(recording_composer=RecordingWP050(), assessor=object())  # type: ignore[arg-type]


def test_no_step_c_recording_preserves_wp050_and_skips_assessor() -> None:
    plan, run, result = canonical_wp050(handling=None)
    assessor = RecordingAssessor(PlanStepEvidenceAssessor())

    output, upstream = invoke(plan, run, result, assessor)

    assert len(upstream.calls) == 1
    assert assessor.calls == []
    assert output.post_recording_execution_recording_result is None
    assert output.post_recording_execution_assessment is None
    for item in fields(PlanStepExecutionResultRecordingPostRecordingCompositionResult):
        assert getattr(output, item.name) is getattr(result, item.name)


def test_exact_wp050_input_surface_is_forwarded_once() -> None:
    plan, run, result = canonical_wp050(handling=None)
    kwargs = operands(result)
    upstream = RecordingWP050(result)

    Composer(recording_composer=upstream).compose(plan, run, "a", **kwargs)

    assert len(upstream.calls) == 1
    positional, forwarded = upstream.calls[0]
    assert positional == (plan, run, "a")
    assert forwarded.keys() == kwargs.keys()
    for name, value in kwargs.items():
        assert forwarded[name] is value


def test_wp051_preserves_wp050_lazy_unreachable_execution_input_validation() -> None:
    plan, run, wp049 = canonical_wp049(handling=None)
    recorder = recorder_for(wp049)
    actual_wp050 = Upstream(
        start_composer=RecordingWP049(wp049),
        result_recorder=recorder,
    )
    upstream = RecordingWP050(delegate=actual_wp050)
    invalid_unused_input = object()
    kwargs = operands(wp049)
    kwargs["post_recording_execution_input"] = invalid_unused_input

    output = Composer(recording_composer=upstream).compose(
        plan,
        run,
        "a",
        **kwargs,
    )

    assert len(upstream.calls) == 1
    assert output.post_recording_execution_recording_result is None
    assert output.post_recording_execution_assessment is None
    assert recorder.calls == []


def test_handler_unavailable_fact_is_assessed_without_activation() -> None:
    plan, run, result = canonical_wp050(unavailable=True)
    start = result.post_recording_execution_start_result
    recording = result.post_recording_execution_recording_result
    assert start is not None and start.active_run is None
    assert recording is not None
    assert selected_state(result) is StepProgressState.NOT_STARTED
    assessor = deterministic_assessor(result)

    output, upstream = invoke(plan, run, result, assessor)

    assessment = output.post_recording_execution_assessment
    assert len(upstream.calls) == 1
    assert assessor.calls == [(plan, recording.recorded_run, recording.step_id)]
    assert assessment is not None
    assert assessment.status is StepOutcomeStatus.INDETERMINATE
    assert assessment.run_revision == recording.recorded_run.revision
    assert selected_state(output) is StepProgressState.NOT_STARTED


@pytest.mark.parametrize(
    "execution_status",
    [ExecutionStatus.SUCCEEDED, ExecutionStatus.FAILED, ExecutionStatus.REJECTED],
)
def test_activated_statuses_follow_same_assessment_path(
    execution_status: ExecutionStatus,
) -> None:
    plan, run, result = canonical_wp050(status=execution_status)
    recording = result.post_recording_execution_recording_result
    assert recording is not None
    assert selected_state(result) is StepProgressState.ACTIVE
    before = recording.recorded_run.to_data()
    assessor = deterministic_assessor(result)

    output, _ = invoke(plan, run, result, assessor)

    assessment = output.post_recording_execution_assessment
    assert assessment is not None
    assert assessment.status is StepOutcomeStatus.INDETERMINATE
    assert assessor.calls == [(plan, recording.recorded_run, recording.step_id)]
    assert output.post_recording_execution_recording_result is recording
    assert recording.recorded_run.to_data() == before
    assert selected_state(output) is StepProgressState.ACTIVE


@pytest.mark.parametrize("status", list(StepOutcomeStatus))
def test_replaceable_evaluator_status_is_preserved_exactly(
    status: StepOutcomeStatus,
) -> None:
    plan, run, result = canonical_wp050()
    recording = result.post_recording_execution_recording_result
    assert recording is not None
    latest = max(item.observed_at for item in recording.recorded_run.observations)
    delegate, evaluator = assessor_for(
        status,
        assessed_at=latest + timedelta(seconds=1),
    )
    assessor = RecordingAssessor(delegate)

    output, _ = invoke(plan, run, result, assessor)

    assessment = output.post_recording_execution_assessment
    assert assessment is not None
    assert assessment.status is status
    assert assessment is not output.post_recording_assessment
    assert len(evaluator.calls) == 1


@pytest.mark.parametrize(
    ("prior_ids", "new_id", "expected_ids"),
    [
        (
            ("ddd-prior-c",),
            "aaa-execution-observation-c",
            ("aaa-execution-observation-c", "ddd-prior-c"),
        ),
        (
            ("aaa-prior-c", "ddd-prior-c"),
            "ccc-execution-observation-c",
            ("aaa-prior-c", "ccc-execution-observation-c", "ddd-prior-c"),
        ),
        (
            ("aaa-prior-c",),
            "ddd-execution-observation-c",
            ("aaa-prior-c", "ddd-execution-observation-c"),
        ),
    ],
)
def test_complete_step_evidence_uses_canonical_before_between_after_order(
    prior_ids: tuple[str, ...],
    new_id: str,
    expected_ids: tuple[str, ...],
) -> None:
    plan, run, result = canonical_wp050_with_prior_evidence(
        step_c_observation_ids=prior_ids,
        new_observation_id=new_id,
    )
    recording = result.post_recording_execution_recording_result
    assert recording is not None
    assessor = deterministic_assessor(result)

    output, _ = invoke(plan, run, result, assessor)

    assessment = output.post_recording_execution_assessment
    assert assessment is not None
    assert assessor.calls == [(plan, recording.recorded_run, recording.step_id)]
    assert assessment.evidence_ids == expected_ids
    assert (
        tuple(
            observation.observation_id
            for observation in recording.recorded_run.observations
            if observation.step_id == recording.step_id
        )
        == expected_ids
    )
    assert "bbb-other-step-evidence-b" not in assessment.evidence_ids
    assert "ccc-run-level-evidence" not in assessment.evidence_ids


@pytest.mark.parametrize(
    "mutation",
    ["missing", "extra", "replaced", "wrong_order"],
)
def test_incomplete_or_wrongly_ordered_evidence_basis_fails_closed(
    mutation: str,
) -> None:
    plan, run, result = canonical_wp050_with_prior_evidence(
        step_c_observation_ids=("aaa-prior-c", "ddd-prior-c"),
        new_observation_id="ccc-execution-observation-c",
    )
    recording = result.post_recording_execution_recording_result
    assert recording is not None
    canonical_assessor = deterministic_assessor(result)
    valid = canonical_assessor.delegate.assess(  # type: ignore[attr-defined]
        plan,
        recording.recorded_run,
        recording.step_id,
    )
    if mutation == "missing":
        evidence_ids = valid.evidence_ids[:-1]
    elif mutation == "extra":
        evidence_ids = (*valid.evidence_ids, "unrelated-extra-evidence")
    elif mutation == "replaced":
        evidence_ids = (
            valid.evidence_ids[0],
            "replacement-evidence",
            valid.evidence_ids[2],
        )
    else:
        evidence_ids = tuple(reversed(valid.evidence_ids))
    malformed = unsafe_clone(valid, evidence_ids=evidence_ids)
    assessor = RecordingAssessor(PlanStepEvidenceAssessor(), forced=malformed)

    with pytest.raises(Invariant):
        invoke(plan, run, result, assessor)

    assert len(assessor.calls) == 1


def test_wrong_assessor_return_type_becomes_wp051_invariant_error() -> None:
    plan, run, result = canonical_wp050()
    assessor = RecordingAssessor(PlanStepEvidenceAssessor(), forced=object())

    with pytest.raises(Invariant):
        invoke(plan, run, result, assessor)

    assert len(assessor.calls) == 1


def test_exact_assessment_is_preserved_and_result_is_immutable_serializable() -> None:
    plan, run, result = canonical_wp050()
    recording = result.post_recording_execution_recording_result
    assert recording is not None
    canonical_assessor = deterministic_assessor(result)
    exact_assessment = canonical_assessor.delegate.assess(  # type: ignore[attr-defined]
        plan,
        recording.recorded_run,
        recording.step_id,
    )
    assessor = RecordingAssessor(
        PlanStepEvidenceAssessor(),
        forced=exact_assessment,
    )

    output, _ = invoke(plan, run, result, assessor)
    assessment = output.post_recording_execution_assessment

    assert assessment is exact_assessment
    with pytest.raises(FrozenInstanceError):
        output.post_recording_execution_assessment = None  # type: ignore[misc]
    assert "__dict__" not in Result.__slots__
    assert json.dumps(output.to_data(), sort_keys=True) == json.dumps(
        output.to_data(), sort_keys=True
    )

    missing = unsafe_clone(output, post_recording_execution_assessment=None)
    with pytest.raises(Invariant):
        Result.__post_init__(missing)


def test_wp050_error_propagates_unchanged_and_assessor_is_unused() -> None:
    error = RuntimeError("wp050 failed")
    upstream = RecordingWP050(error=error)
    assessor = RecordingAssessor(PlanStepEvidenceAssessor())
    plan, run, result = canonical_wp050(handling=None)

    with pytest.raises(RuntimeError) as raised:
        Composer(recording_composer=upstream, assessor=assessor).compose(
            plan,
            run,
            "a",
            **operands(result),
        )

    assert raised.value is error
    assert len(upstream.calls) == 1
    assert assessor.calls == []


def test_wp027_error_propagates_unchanged_without_retry() -> None:
    plan, run, result = canonical_wp050()
    error = RuntimeError("assessment failed")
    assessor = RecordingAssessor(PlanStepEvidenceAssessor(), error=error)

    with pytest.raises(RuntimeError) as raised:
        invoke(plan, run, result, assessor)

    assert raised.value is error
    assert len(assessor.calls) == 1


@pytest.mark.parametrize(
    ("field_name", "replacement"),
    [
        ("plan_id", "foreign-plan"),
        ("run_id", "foreign-run"),
        ("run_revision", 999),
        ("step_id", "b"),
    ],
)
def test_malformed_assessment_lineage_fails_closed(
    field_name: str,
    replacement: object,
) -> None:
    plan, run, result = canonical_wp050()
    canonical_assessor = deterministic_assessor(result)
    recording = result.post_recording_execution_recording_result
    assert recording is not None
    valid = canonical_assessor.delegate.assess(  # type: ignore[attr-defined]
        plan,
        recording.recorded_run,
        recording.step_id,
    )
    malformed = unsafe_clone(valid, **{field_name: replacement})
    assessor = RecordingAssessor(
        PlanStepEvidenceAssessor(),
        forced=malformed,
    )

    with pytest.raises(Invariant):
        invoke(plan, run, result, assessor)

    assert len(assessor.calls) == 1


def test_malformed_wp050_result_fails_before_assessment() -> None:
    plan, run, result = canonical_wp050()
    malformed = unsafe_clone(
        result,
        post_recording_execution_recording_result=None,
    )
    assessor = deterministic_assessor(result)
    upstream = RecordingWP050(malformed)

    with pytest.raises(Invariant):
        Composer(recording_composer=upstream, assessor=assessor).compose(
            plan,
            run,
            "a",
            **operands(result),
        )

    assert assessor.calls == []


@pytest.mark.parametrize("malformation", ["wrong_type", "foreign_plan", "foreign_run"])
def test_foreign_or_wrong_wp050_return_fails_before_assessment(
    malformation: str,
) -> None:
    plan, run, result = canonical_wp050()
    recording = result.post_recording_execution_recording_result
    assert recording is not None
    if malformation == "wrong_type":
        malformed: object = object()
    elif malformation == "foreign_plan":
        foreign_recording = unsafe_clone(recording, plan_id="foreign-plan")
        malformed = unsafe_clone(
            result,
            post_recording_execution_recording_result=foreign_recording,
        )
    else:
        foreign_recording = unsafe_clone(recording, run_id="foreign-run")
        malformed = unsafe_clone(
            result,
            post_recording_execution_recording_result=foreign_recording,
        )
    assessor = deterministic_assessor(result)
    upstream = RecordingWP050(malformed)

    with pytest.raises(Invariant):
        Composer(recording_composer=upstream, assessor=assessor).compose(
            plan,
            run,
            "a",
            **operands(result),
        )

    assert assessor.calls == []


def test_assessment_predating_latest_step_evidence_fails_closed() -> None:
    plan, run, result = canonical_wp050()
    recording = result.post_recording_execution_recording_result
    assert recording is not None
    canonical_assessor = deterministic_assessor(result)
    valid = canonical_assessor.delegate.assess(  # type: ignore[attr-defined]
        plan,
        recording.recorded_run,
        recording.step_id,
    )
    latest = max(
        observation.observed_at
        for observation in recording.recorded_run.observations
        if observation.step_id == recording.step_id
    )
    malformed = unsafe_clone(valid, assessed_at=latest - timedelta(microseconds=1))
    assessor = RecordingAssessor(PlanStepEvidenceAssessor(), forced=malformed)

    with pytest.raises(Invariant):
        invoke(plan, run, result, assessor)

    assert len(assessor.calls) == 1


def test_repeated_invocations_have_no_hidden_deduplication() -> None:
    plan, run, result = canonical_wp050()
    recording = result.post_recording_execution_recording_result
    assert recording is not None
    latest = max(item.observed_at for item in recording.recorded_run.observations)
    ids = iter(("step-c-assessment-1", "step-c-assessment-2"))
    assessor = RecordingAssessor(
        PlanStepEvidenceAssessor(
            ConservativeStepOutcomeEvaluator(
                clock=lambda: latest + timedelta(seconds=1),
                assessment_id_factory=lambda: next(ids),
            )
        )
    )
    upstream = RecordingWP050(result)
    composer = Composer(recording_composer=upstream, assessor=assessor)
    kwargs = operands(result)

    first = composer.compose(plan, run, "a", **kwargs)
    second = composer.compose(plan, run, "a", **kwargs)

    assert len(upstream.calls) == 2
    assert len(assessor.calls) == 2
    assert first.post_recording_execution_assessment is not None
    assert second.post_recording_execution_assessment is not None
    assert (
        first.post_recording_execution_assessment.assessment_id
        != second.post_recording_execution_assessment.assessment_id
    )


def test_package_has_no_transition_mutation_or_continuation_authority() -> None:
    package = Path(api.__file__).parent
    forbidden = {
        "StepProgressTransitionDecider",
        "PlanRunReducer",
        "PlanRunProgressAdvancer",
        "StepProgressUpdateSynthesizer",
        "PlanRunController",
        "RecordObservationUpdate",
        "PlanStepExecutionStartCoordinator",
        "PlanStepExecutionResultRecorder",
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
        assert "plan_step_execution_evidence_assessment_composition" not in source
        assert "observations[-1]" not in source
        assert "observations[:-1]" not in source
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
    assert sum(node.func.attr == "assess" for node in calls) == 1
