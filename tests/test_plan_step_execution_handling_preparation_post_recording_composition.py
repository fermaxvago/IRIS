"""WP055: optionally prepare handling for the exact post-Step-C selection."""

from __future__ import annotations

import ast
import inspect
import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import pytest

import iris.plan_step_execution_handling_preparation_post_recording_composition as api
from iris.orchestrator import HandlingKind
from iris.outcome_assessment import StepOutcomeStatus
from iris.plan_control import ControlDecision, ControlDecisionKind
from iris.plan_handling import (
    PlanStepHandlingPreparer,
    SelectedStepNotReadyError,
    StaleStepHandlingPreparationError,
    StepHandlingPreparationResult,
    StepHandlingPreparationStatus,
    StepHandlingSpecification,
)
from iris.plan_runs import PlanRun, StepProgressState
from iris.plan_step_execution_binding_post_recording_composition import (
    PlanStepExecutionBindingPostRecordingComposer,
)
from iris.plan_step_execution_handling_preparation_post_recording_composition import (
    PlanStepExecutionHandlingPreparationPostRecordingComposer as Composer,
)
from iris.plan_step_execution_handling_preparation_post_recording_composition import (
    PlanStepExecutionHandlingPreparationPostRecordingCompositionInvariantError as Invariant,
)
from iris.plan_step_execution_handling_preparation_post_recording_composition import (
    PlanStepExecutionHandlingPreparationPostRecordingCompositionResult as Result,
)
from iris.plan_step_execution_progress_advancement_post_recording_composition import (
    PlanStepExecutionProgressAdvancementPostRecordingComposer as Upstream,
)
from iris.plan_step_execution_progress_advancement_post_recording_composition import (
    PlanStepExecutionProgressAdvancementPostRecordingCompositionResult as UpstreamResult,
)
from iris.planning import Plan
from tests.test_plan_step_execution_binding_post_recording_composition import (
    RecordingWP047,
    operands,
)
from tests.test_plan_step_execution_context_materialization_composition import (
    compose_from_wp044,
)
from tests.test_plan_step_execution_evidence_assessment_composition import (
    BUDGET,
    CAPABILITY_AVAILABLE,
    CONTEXT_CREATED,
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
from tests.test_plan_step_execution_evidence_assessment_post_recording_composition import (
    invoke as invoke_wp051,
)
from tests.test_plan_step_execution_handling_preparation_composition import (
    compose_from_wp042,
)
from tests.test_plan_step_execution_orchestration_composition import compose_from_wp045
from tests.test_plan_step_execution_progress_advancement_composition import (
    compose_from_wp041,
    decision_for_kind,
)
from tests.test_plan_step_execution_progress_advancement_post_recording_composition import (
    RecordingAdvancer,
    RecordingWP053,
)
from tests.test_plan_step_execution_progress_advancement_post_recording_composition import (
    canonical as canonical_wp054_base,
)
from tests.test_plan_step_execution_progress_advancement_post_recording_composition import (
    invoke as invoke_wp054,
)
from tests.test_plan_step_execution_progress_update_composition import (
    compose_from_wp040,
)
from tests.test_plan_step_execution_progress_update_post_recording_composition import (
    RecordingSynthesizer,
)
from tests.test_plan_step_execution_progress_update_post_recording_composition import (
    invoke as invoke_wp053,
)
from tests.test_plan_step_execution_request_materialization_composition import (
    compose_from_wp046,
)
from tests.test_plan_step_execution_result_recording_post_recording_composition import (
    invoke as invoke_wp050,
)
from tests.test_plan_step_execution_result_recording_post_recording_composition import (
    recorder_for,
)
from tests.test_plan_step_execution_start_post_recording_composition import (
    invoke as invoke_wp049,
)
from tests.test_plan_step_execution_start_post_recording_composition import runtime
from tests.test_plan_step_execution_transition_decision_composition import (
    compose_from_wp039,
)
from tests.test_plan_step_execution_transition_decision_post_recording_composition import (
    decider_for,
)
from tests.test_plan_step_execution_transition_decision_post_recording_composition import (
    invoke as invoke_wp052,
)
from tests.test_plan_step_execution_work_subject_materialization_composition import (
    compose_from_wp043,
)


class RecordingWP054(Upstream):
    def __init__(
        self,
        result: Any = None,
        *,
        error: Exception | None = None,
        delegate: Upstream | None = None,
    ) -> None:
        super().__init__(progress_update_composer=RecordingWP053())
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


class RecordingPreparer(PlanStepHandlingPreparer):
    def __init__(self, *, forced: Any = None, error: Exception | None = None) -> None:
        super().__init__()
        self.forced = forced
        self.error = error
        self.calls: list[tuple[Plan, PlanRun, ControlDecision, Any]] = []
        self.results: list[StepHandlingPreparationResult] = []

    def prepare(
        self,
        plan: Plan,
        run: PlanRun,
        decision: ControlDecision,
        specification: StepHandlingSpecification | None = None,
    ) -> StepHandlingPreparationResult:
        self.calls.append((plan, run, decision, specification))
        if self.error is not None:
            raise self.error
        result = (
            super().prepare(plan, run, decision, specification)
            if self.forced is None
            else cast(StepHandlingPreparationResult, self.forced)
        )
        self.results.append(result)
        return result


def canonical_wp054(
    *, selected_handling: HandlingKind | None = HandlingKind.CAPABILITY
) -> tuple[Plan, PlanRun, UpstreamResult]:
    """Build the real A/B/C chain so WP054 freshly selects Step D."""

    plan = make_plan(
        step("a"),
        step("b", depends_on=("a",), handling=HandlingKind.CAPABILITY),
        step("c", depends_on=("b",), handling=HandlingKind.CAPABILITY),
        step("d", depends_on=("c",), handling=selected_handling),
    )
    run = transition(plan, new_run(plan), "a", StepProgressState.ACTIVE)
    run = record_fixture_observation(
        plan,
        run,
        observation_id="evidence-a",
        step_id="a",
        offset=2,
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
        plan, run, wp038, assessor=RecordingAssessor(source_assessor)
    )
    wp040, _, _ = compose_from_wp039(plan, run, wp039)
    wp041, _, _ = compose_from_wp040(plan, run, wp040)
    wp042, _, _ = compose_from_wp041(plan, run, wp041)
    wp043, _, _ = compose_from_wp042(plan, run, wp042)
    wp044, _, _ = compose_from_wp043(plan, run, wp043)
    wp045, _, _ = compose_from_wp044(plan, run, wp044)
    wp046, _, _ = compose_from_wp045(plan, run, wp045)
    wp047, _ = compose_from_wp046(
        plan, run, wp046, post_execution_input=capability_input()
    )
    wp048 = PlanStepExecutionBindingPostRecordingComposer(
        request_materialization_composer=RecordingWP047(wp047)
    ).compose(plan, run, "a", **operands(wp047))
    wp049, _ = invoke_wp049(plan, run, wp048, runtime(wp048, CapabilityHandler()))
    wp050, _ = invoke_wp050(
        plan, run, wp049, recorder_for(wp049, observation_id="execution-c")
    )
    recording = wp050.post_recording_execution_recording_result
    assert recording is not None
    latest = max(item.observed_at for item in recording.recorded_run.observations)
    assessor, _ = assessor_for(
        StepOutcomeStatus.SATISFIED,
        assessed_at=latest + timedelta(seconds=1),
        assessment_ids=["assessment-c"],
    )
    wp051, _ = invoke_wp051(plan, run, wp050, RecordingAssessor(assessor))
    wp052, _ = invoke_wp052(plan, run, wp051, decider_for(wp051))
    wp053, _ = invoke_wp053(plan, run, wp052, RecordingSynthesizer(wp052))
    wp054, _, _ = invoke_wp054(plan, run, wp053, RecordingAdvancer())
    advancement = wp054.post_recording_execution_advancement_result
    assert advancement is not None
    assert advancement.control_decision.kind is ControlDecisionKind.STEP_SELECTED
    assert advancement.control_decision.selected_step_id == "d"
    return plan, run, wp054


def invoke(
    plan: Plan,
    run: PlanRun,
    upstream_result: Any,
    preparer: RecordingPreparer | None = None,
    **overrides: Any,
) -> tuple[Result, RecordingWP054, RecordingPreparer]:
    upstream = RecordingWP054(upstream_result)
    selected_preparer = preparer or RecordingPreparer()
    kwargs = (
        operands(upstream_result) if isinstance(upstream_result, UpstreamResult) else {}
    )
    kwargs.update(overrides)
    result = Composer(
        progress_advancement_composer=upstream,
        handling_preparer=selected_preparer,
    ).compose(plan, run, "a", **kwargs)
    return result, upstream, selected_preparer


def test_public_contract() -> None:
    assert api.__all__ == [
        "PlanStepExecutionHandlingPreparationPostRecordingComposer",
        "PlanStepExecutionHandlingPreparationPostRecordingCompositionResult",
        "PlanStepExecutionHandlingPreparationPostRecordingCompositionError",
        "PlanStepExecutionHandlingPreparationPostRecordingCompositionInvariantError",
    ]
    assert issubclass(
        Invariant, api.PlanStepExecutionHandlingPreparationPostRecordingCompositionError
    )
    assert issubclass(Result, UpstreamResult)
    assert (
        inspect.signature(Composer.compose).parameters
        == inspect.signature(Upstream.compose).parameters
    )
    assert list(inspect.signature(Composer).parameters) == [
        "progress_advancement_composer",
        "handling_preparer",
    ]
    with pytest.raises(TypeError):
        Composer(progress_advancement_composer=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Composer(
            progress_advancement_composer=RecordingWP054(), handling_preparer=object()
        )  # type: ignore[arg-type]


def test_no_advancement_skips_preparation_and_preserves_identity() -> None:
    plan, run, wp053 = canonical_wp054_base(absent=True)
    wp054, _, _ = invoke_wp054(plan, run, wp053, RecordingAdvancer())
    result, upstream, preparer = invoke(plan, run, wp054)
    assert len(upstream.calls) == 1
    assert preparer.calls == []
    assert result.post_recording_execution_advancement_result is None
    assert result.post_recording_execution_handling_preparation is None
    for item in fields(UpstreamResult):
        assert getattr(result, item.name) is getattr(wp054, item.name)


@pytest.mark.parametrize(
    "kind",
    [
        ControlDecisionKind.ACTIVE_WORK_PENDING,
        ControlDecisionKind.SELECTION_UNRESOLVED,
        ControlDecisionKind.RUN_CANNOT_ADVANCE,
        ControlDecisionKind.RUN_STRUCTURALLY_COMPLETE,
    ],
)
def test_non_selected_control_kinds_skip_preparation(kind: ControlDecisionKind) -> None:
    plan, run, wp054 = canonical_wp054()
    advancement = wp054.post_recording_execution_advancement_result
    assert advancement is not None
    defensive_control = decision_for_kind(kind, advancement.updated_run)
    defensive = unsafe_clone(
        wp054,
        post_recording_execution_advancement_result=replace(
            advancement, control_decision=defensive_control
        ),
    )
    result, _, preparer = invoke(plan, run, defensive)
    assert preparer.calls == []
    assert result.post_recording_execution_advancement_result is (
        defensive.post_recording_execution_advancement_result
    )
    assert result.post_recording_execution_handling_preparation is None


@pytest.mark.parametrize(
    ("handling", "status"),
    [
        (HandlingKind.CAPABILITY, StepHandlingPreparationStatus.PREPARED),
        (None, StepHandlingPreparationStatus.HANDLING_UNSPECIFIED),
        (HandlingKind.SYSTEM, StepHandlingPreparationStatus.INSUFFICIENT_DETAIL),
        (HandlingKind.MEMORY, StepHandlingPreparationStatus.INSUFFICIENT_DETAIL),
        (HandlingKind.INTELLIGENCE, StepHandlingPreparationStatus.INSUFFICIENT_DETAIL),
    ],
)
def test_selected_step_preserves_all_canonical_preparation_outcomes(
    handling: HandlingKind | None,
    status: StepHandlingPreparationStatus,
) -> None:
    plan, run, wp054 = canonical_wp054(selected_handling=handling)
    result, upstream, preparer = invoke(plan, run, wp054)
    advancement = wp054.post_recording_execution_advancement_result
    assert advancement is not None
    assert len(upstream.calls) == len(preparer.calls) == 1
    assert preparer.calls[0] == (
        plan,
        advancement.updated_run,
        advancement.control_decision,
        None,
    )
    preparation = result.post_recording_execution_handling_preparation
    assert preparation is preparer.results[0]
    assert preparation.status is status
    assert preparation.plan_id == plan.plan_id
    assert preparation.run_id == advancement.updated_run.run_id
    assert preparation.observed_revision == advancement.updated_run.revision
    assert preparation.step_id == advancement.control_decision.selected_step_id == "d"
    assert preparation is not result.handling_preparation
    assert preparation is not result.post_recording_handling_preparation
    for item in fields(UpstreamResult):
        assert getattr(result, item.name) is getattr(wp054, item.name)


def test_exact_forwarding_lazy_input_and_serialization() -> None:
    plan, run, wp054 = canonical_wp054()
    upstream = RecordingWP054(wp054)
    preparer = RecordingPreparer()
    kwargs = operands(wp054)
    marker = kwargs["post_recording_execution_input"]
    output = Composer(
        progress_advancement_composer=upstream, handling_preparer=preparer
    ).compose(plan, run, "a", **kwargs)
    args, forwarded = upstream.calls[0]
    assert args == (plan, run, "a")
    assert forwarded.keys() == kwargs.keys()
    assert all(forwarded[key] is value for key, value in kwargs.items())
    assert forwarded["post_recording_execution_input"] is marker
    with pytest.raises(FrozenInstanceError):
        output.post_recording_execution_handling_preparation = None  # type: ignore[misc]
    assert "__dict__" not in Result.__slots__
    data = output.to_data()
    assert all(data[key] == value for key, value in wp054.to_data().items())
    assert data["post_recording_execution_handling_preparation"] == (
        output.post_recording_execution_handling_preparation.to_data()
    )
    assert json.loads(json.dumps(data, sort_keys=True)) == data


def test_unreachable_post_recording_input_remains_lazily_unvalidated() -> None:
    plan, run, wp053 = canonical_wp054_base(absent=True)
    actual_wp054 = Upstream(progress_update_composer=RecordingWP053(wp053))
    upstream = RecordingWP054(delegate=actual_wp054)
    preparer = RecordingPreparer()
    marker = object()
    kwargs = operands(wp053)
    kwargs["post_recording_execution_input"] = marker
    output = Composer(
        progress_advancement_composer=upstream,
        handling_preparer=preparer,
    ).compose(plan, run, "a", **kwargs)
    assert len(upstream.calls) == 1
    assert upstream.calls[0][1]["post_recording_execution_input"] is marker
    assert output.post_recording_execution_advancement_result is None
    assert output.post_recording_execution_handling_preparation is None
    assert preparer.calls == []


@pytest.mark.parametrize(
    "change",
    [
        "wrong_type",
        "missing_recording",
        "wrong_update",
        "wrong_advancement_revision",
        "foreign_successor",
        "stale_control",
        "corrupt_inherited",
    ],
)
def test_malformed_wp054_fails_before_wp014(change: str) -> None:
    plan, run, wp054 = canonical_wp054()
    advancement = wp054.post_recording_execution_advancement_result
    update = wp054.post_recording_execution_progress_update
    assert advancement is not None and update is not None
    variants: dict[str, Any] = {
        "wrong_type": object(),
        "missing_recording": unsafe_clone(
            wp054, post_recording_execution_recording_result=None
        ),
        "wrong_update": unsafe_clone(
            wp054,
            post_recording_execution_progress_update=unsafe_clone(
                update, expected_revision=update.expected_revision + 1
            ),
        ),
        "wrong_advancement_revision": unsafe_clone(
            wp054,
            post_recording_execution_advancement_result=unsafe_clone(
                advancement, source_revision=advancement.source_revision + 1
            ),
        ),
        "foreign_successor": unsafe_clone(
            wp054,
            post_recording_execution_advancement_result=unsafe_clone(
                advancement,
                updated_run=unsafe_clone(advancement.updated_run, plan_id="foreign"),
            ),
        ),
        "stale_control": unsafe_clone(
            wp054,
            post_recording_execution_advancement_result=unsafe_clone(
                advancement,
                control_decision=unsafe_clone(
                    advancement.control_decision,
                    observed_revision=advancement.control_decision.observed_revision
                    - 1,
                ),
            ),
        ),
        "corrupt_inherited": unsafe_clone(
            wp054, assessment=unsafe_clone(wp054.assessment, plan_id="foreign")
        ),
    }
    preparer = RecordingPreparer()
    with pytest.raises(Invariant):
        invoke(plan, run, variants[change], preparer, **operands(wp054))
    assert preparer.calls == []


@pytest.mark.parametrize(
    "change",
    [
        "wrong_type",
        "plan",
        "run",
        "revision",
        "step",
        "status_reason",
        "need",
        "provenance",
        "handling_kind",
    ],
)
def test_malformed_wp014_return_fails_closed(change: str) -> None:
    plan, run, wp054 = canonical_wp054()
    advancement = wp054.post_recording_execution_advancement_result
    assert advancement is not None
    valid = PlanStepHandlingPreparer().prepare(
        plan, advancement.updated_run, advancement.control_decision
    )
    assert valid.handling_need is not None
    variants: dict[str, Any] = {
        "wrong_type": object(),
        "plan": unsafe_clone(valid, plan_id="foreign"),
        "run": unsafe_clone(valid, run_id="foreign"),
        "revision": unsafe_clone(valid, observed_revision=valid.observed_revision + 1),
        "step": unsafe_clone(valid, step_id="foreign"),
        "status_reason": unsafe_clone(valid, status="foreign"),
        "need": unsafe_clone(
            valid,
            handling_need=unsafe_clone(valid.handling_need, need_id="foreign"),
        ),
        "provenance": unsafe_clone(
            valid, provenance=unsafe_clone(valid.provenance, preparer_id="")
        ),
        "handling_kind": unsafe_clone(valid, handling_kind=HandlingKind.SYSTEM),
    }
    preparer = RecordingPreparer(forced=variants[change])
    with pytest.raises(Invariant):
        invoke(plan, run, wp054, preparer)
    assert len(preparer.calls) == 1


def test_errors_propagate_without_retry_or_partial_result() -> None:
    plan, run, wp054 = canonical_wp054()
    upstream_error = RuntimeError("WP054 failed")
    upstream = RecordingWP054(error=upstream_error)
    preparer = RecordingPreparer()
    with pytest.raises(RuntimeError) as raised:
        Composer(
            progress_advancement_composer=upstream,
            handling_preparer=preparer,
        ).compose(plan, run, "a", **operands(wp054))
    assert raised.value is upstream_error
    assert len(upstream.calls) == 1 and preparer.calls == []

    for error in (
        SelectedStepNotReadyError("not ready"),
        StaleStepHandlingPreparationError("stale"),
        RuntimeError("WP014 failed"),
    ):
        preparer = RecordingPreparer(error=error)
        with pytest.raises(type(error)) as raised:
            invoke(plan, run, wp054, preparer)
        assert raised.value is error
        assert len(preparer.calls) == 1


def test_presence_invariant_and_no_hidden_deduplication() -> None:
    plan, run, wp054 = canonical_wp054()
    upstream = RecordingWP054(wp054)
    preparer = RecordingPreparer()
    composer = Composer(
        progress_advancement_composer=upstream, handling_preparer=preparer
    )
    first = composer.compose(plan, run, "a", **operands(wp054))
    second = composer.compose(plan, run, "a", **operands(wp054))
    assert len(upstream.calls) == len(preparer.calls) == 2
    assert first.post_recording_execution_handling_preparation is preparer.results[0]
    assert second.post_recording_execution_handling_preparation is preparer.results[1]
    with pytest.raises(Invariant):
        replace(first, post_recording_execution_handling_preparation=None)


def test_no_forbidden_authority_imports_or_calls() -> None:
    package = Path(api.__file__).parent
    forbidden_modules = {
        "plan_runs.reducer",
        "plan_run_advancement",
        "execution_coordinator",
        "work_subject",
        "context_engine",
        "execution_binding",
    }
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        assert not any(
            any(fragment in module for fragment in forbidden_modules)
            for module in imports
        )
        attributes = {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        assert not {"apply", "advance", "decide", "execute", "start"} & attributes
