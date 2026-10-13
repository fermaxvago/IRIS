"""WP058: one optional exact successor WP017 decision, then STOP."""

from __future__ import annotations

import ast
import inspect
import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import timedelta, timezone
from pathlib import Path
from typing import Any, cast

import pytest

import iris.plan_step_execution_orchestration_post_recording_composition as api
from iris.context import (
    ContextBudget,
    ContextUncertainty,
    ResolutionStatus,
    UncertaintyReason,
)
from iris.orchestrator import (
    HandlerAvailability,
    HandlingKind,
    OrchestrationDecision,
    OrchestrationInput,
    OrchestrationTarget,
    Orchestrator,
)
from iris.plan_control import ControlDecisionKind
from iris.plan_handling import StepHandlingPreparationStatus
from iris.plan_step_execution_context_materialization_post_recording_composition import (
    PlanStepExecutionContextMaterializationPostRecordingComposer as Upstream,
)
from iris.plan_step_execution_context_materialization_post_recording_composition import (
    PlanStepExecutionContextMaterializationPostRecordingCompositionResult as UpstreamResult,
)
from tests.test_context import GLOBAL, candidate
from tests.test_plan_step_execution_binding_post_recording_composition import operands
from tests.test_plan_step_execution_context_materialization_post_recording_composition import (
    CONTEXT_TIME,
    RecordingWP056,
    selected_wp056,
)
from tests.test_plan_step_execution_context_materialization_post_recording_composition import (
    call as call_wp057,
)
from tests.test_plan_step_execution_evidence_assessment_composition import unsafe_clone
from tests.test_plan_step_execution_handling_preparation_post_recording_composition import (
    invoke as invoke_wp055,
)
from tests.test_plan_step_execution_progress_advancement_composition import (
    decision_for_kind,
)
from tests.test_plan_step_execution_progress_advancement_post_recording_composition import (
    canonical as canonical_wp054_base,
)
from tests.test_plan_step_execution_progress_advancement_post_recording_composition import (
    invoke as invoke_wp054,
)
from tests.test_plan_step_execution_work_subject_materialization_post_recording_composition import (
    invoke as invoke_wp056,
)

Composer = api.PlanStepExecutionOrchestrationPostRecordingComposer
Result = api.PlanStepExecutionOrchestrationPostRecordingCompositionResult
Invariant = api.PlanStepExecutionOrchestrationPostRecordingCompositionInvariantError


class RecordingWP057(Upstream):
    def __init__(self, result: object, error: Exception | None = None) -> None:
        super().__init__(work_subject_materialization_composer=RecordingWP056())
        self.result = result
        self.error = error
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def compose(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return self.result


class RecordingOrchestrator(Orchestrator):
    def __init__(self, forced: object = None, error: Exception | None = None) -> None:
        super().__init__(clock=lambda: CONTEXT_TIME + timedelta(seconds=1))
        self.forced = forced
        self.error = error
        self.calls: list[OrchestrationInput] = []

    def decide(self, orchestration_input: OrchestrationInput) -> OrchestrationDecision:
        self.calls.append(orchestration_input)
        if self.error is not None:
            raise self.error
        if self.forced is not None:
            return cast(OrchestrationDecision, self.forced)
        return super().decide(orchestration_input)


def canonical(
    handling: HandlingKind | None = HandlingKind.CAPABILITY,
) -> tuple[Any, Any, UpstreamResult]:
    plan, run, wp056 = selected_wp056(handling)
    wp057, _, _ = call_wp057(plan, run, wp056)
    return plan, run, wp057


def absent() -> tuple[Any, Any, UpstreamResult]:
    plan, run, wp053 = canonical_wp054_base(absent=True)
    wp054, _, _ = invoke_wp054(plan, run, wp053)
    wp055, _, _ = invoke_wp055(plan, run, wp054)
    wp056, _, _ = invoke_wp056(plan, run, wp055)
    wp057, _, _ = call_wp057(plan, run, wp056)
    return plan, run, wp057


def nonselected(kind: ControlDecisionKind) -> tuple[Any, Any, UpstreamResult]:
    plan, run, wp053 = canonical_wp054_base()
    wp054, _, _ = invoke_wp054(plan, run, wp053)
    advancement = wp054.post_recording_execution_advancement_result
    assert advancement is not None
    forged = unsafe_clone(
        wp054,
        post_recording_execution_advancement_result=replace(
            advancement,
            control_decision=decision_for_kind(kind, advancement.updated_run),
        ),
    )
    wp055, _, _ = invoke_wp055(plan, run, forged)
    wp056, _, _ = invoke_wp056(plan, run, wp055)
    wp057, _, _ = call_wp057(plan, run, wp056)
    return plan, run, wp057


def compose(
    plan: Any,
    run: Any,
    upstream_result: object,
    *,
    availability: object = None,
    orchestrator: RecordingOrchestrator | None = None,
    upstream_error: Exception | None = None,
    **overrides: object,
) -> tuple[Result, RecordingWP057, RecordingOrchestrator]:
    wp057 = RecordingWP057(upstream_result, upstream_error)
    wp017 = orchestrator or RecordingOrchestrator()
    kwargs = operands(
        upstream_result
        if isinstance(upstream_result, UpstreamResult)
        else canonical()[2]
    )
    kwargs.update(
        successor_context_candidates=(),
        successor_context_budget=ContextBudget(2),
        successor_context_uncertainties=(),
        successor_context_created_at=CONTEXT_TIME,
        successor_orchestration_availability=(
            HandlerAvailability(capability=True)
            if availability is None
            else availability
        ),
    )
    kwargs.update(overrides)
    result = Composer(
        context_materialization_composer=wp057, orchestrator=wp017
    ).compose(plan, run, "a", **kwargs)
    return result, wp057, wp017


def test_public_surface_and_exact_signature() -> None:
    assert api.__all__ == [
        "PlanStepExecutionOrchestrationPostRecordingComposer",
        "PlanStepExecutionOrchestrationPostRecordingCompositionResult",
        "PlanStepExecutionOrchestrationPostRecordingCompositionError",
        "PlanStepExecutionOrchestrationPostRecordingCompositionInvariantError",
    ]
    assert issubclass(Result, UpstreamResult)
    assert issubclass(
        Invariant, api.PlanStepExecutionOrchestrationPostRecordingCompositionError
    )
    assert list(inspect.signature(Composer.compose).parameters) == [
        *inspect.signature(Upstream.compose).parameters,
        "successor_orchestration_availability",
    ]
    with pytest.raises(TypeError):
        Composer(context_materialization_composer=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Composer(
            context_materialization_composer=RecordingWP057(None), orchestrator=object()
        )  # type: ignore[arg-type]


def test_absent_successor_skips_orchestration_and_preserves_lazy_inputs() -> None:
    plan, run, upstream = absent()
    marker = object()
    result, wp057, wp017 = compose(
        plan,
        run,
        upstream,
        availability=marker,
        post_recording_execution_input=marker,
        successor_context_candidates=marker,
        successor_context_budget=marker,
        successor_context_created_at=marker,
    )
    assert len(wp057.calls) == 1 and wp017.calls == []
    assert wp057.calls[0][1]["post_recording_execution_input"] is marker
    assert "successor_orchestration_availability" not in wp057.calls[0][1]
    assert result.post_recording_execution_orchestration_decision is None
    assert result.to_data()["post_recording_execution_orchestration_decision"] is None
    for field in fields(UpstreamResult):
        assert getattr(result, field.name) is getattr(upstream, field.name)


@pytest.mark.parametrize(
    "kind",
    [
        ControlDecisionKind.ACTIVE_WORK_PENDING,
        ControlDecisionKind.SELECTION_UNRESOLVED,
        ControlDecisionKind.RUN_CANNOT_ADVANCE,
        ControlDecisionKind.RUN_STRUCTURALLY_COMPLETE,
    ],
)
def test_nonselected_successor_skips_orchestration(kind: ControlDecisionKind) -> None:
    plan, run, upstream = nonselected(kind)
    result, _, wp017 = compose(plan, run, upstream, availability=object())
    assert wp017.calls == []
    assert result.post_recording_execution_orchestration_decision is None


@pytest.mark.parametrize(
    "handling",
    [None, HandlingKind.SYSTEM, HandlingKind.MEMORY, HandlingKind.INTELLIGENCE],
)
def test_non_prepared_successor_abstains(handling: HandlingKind | None) -> None:
    plan, run, upstream = canonical(handling)
    preparation = upstream.post_recording_execution_handling_preparation
    assert preparation is not None
    assert preparation.status is not StepHandlingPreparationStatus.PREPARED
    result, _, wp017 = compose(plan, run, upstream, availability=object())
    assert result.post_recording_execution_orchestration_decision is None
    assert wp017.calls == []


def test_prepared_successor_exact_forwarding_and_serialization() -> None:
    plan, run, upstream = canonical()
    supplied = operands(upstream)
    result, wp057, wp017 = compose(plan, run, upstream, **supplied)
    assert len(wp057.calls) == len(wp017.calls) == 1
    forwarded = wp057.calls[0][1]
    assert forwarded.keys() == supplied.keys() | {
        "successor_context_candidates",
        "successor_context_budget",
        "successor_context_uncertainties",
        "successor_context_created_at",
    }
    assert all(forwarded[name] is value for name, value in supplied.items())
    passed = wp017.calls[0]
    assert passed.subject is upstream.post_recording_execution_work_subject
    assert passed.context is upstream.post_recording_execution_context_snapshot
    assert (
        passed.needs[0]
        is upstream.post_recording_execution_handling_preparation.handling_need
    )
    decision = result.post_recording_execution_orchestration_decision
    assert decision is not None and decision.target is OrchestrationTarget.CAPABILITY
    assert decision.requirement is passed.needs[0]
    assert (
        result.to_data()["post_recording_execution_orchestration_decision"]
        == decision.to_trace()
    )
    assert json.loads(json.dumps(result.to_data())) == result.to_data()
    for field in fields(UpstreamResult):
        assert getattr(result, field.name) is getattr(upstream, field.name)
    with pytest.raises(FrozenInstanceError):
        result.post_recording_execution_orchestration_decision = None  # type: ignore[misc]
    assert Result.__slots__ == ("post_recording_execution_orchestration_decision",)


def test_unavailable_handler_is_real_unsatisfied_decision() -> None:
    plan, run, upstream = canonical()
    result, _, wp017 = compose(plan, run, upstream, availability=HandlerAvailability())
    assert len(wp017.calls) == 1
    assert (
        result.post_recording_execution_orchestration_decision.target
        is OrchestrationTarget.UNSATISFIED
    )


def test_prepared_branch_rejects_noncanonical_availability_before_wp017() -> None:
    plan, run, upstream = canonical()
    for bad in (
        object(),
        unsafe_clone(HandlerAvailability(capability=True), capability_ids=["cap"]),
    ):
        wp017 = RecordingOrchestrator()
        with pytest.raises((TypeError, ValueError)):
            compose(plan, run, upstream, availability=bad, orchestrator=wp017)
        assert wp017.calls == []


@pytest.mark.parametrize(
    ("status", "candidates", "uncertainties"),
    [
        (ResolutionStatus.RESOLVED, (), ()),
        (
            ResolutionStatus.PARTIAL,
            (),
            (ContextUncertainty("task", "missing", GLOBAL, UncertaintyReason.MISSING),),
        ),
        (
            ResolutionStatus.AMBIGUOUS,
            (candidate("one", "v1", key="one"), candidate("two", "v2", key="two")),
            (
                ContextUncertainty(
                    "task",
                    "question",
                    GLOBAL,
                    UncertaintyReason.MULTIPLE_PLAUSIBLE,
                    ("one", "two"),
                ),
            ),
        ),
        (
            ResolutionStatus.CONFLICTED,
            (candidate("one", "v1", key="same"), candidate("two", "v2", key="same")),
            (),
        ),
    ],
)
def test_context_resolution_does_not_gate_orchestration(
    status: ResolutionStatus,
    candidates: tuple[object, ...],
    uncertainties: tuple[ContextUncertainty, ...],
) -> None:
    plan, run, wp056 = selected_wp056()
    upstream, _, _ = call_wp057(
        plan,
        run,
        wp056,
        successor_context_candidates=candidates,
        successor_context_uncertainties=uncertainties,
    )
    assert upstream.post_recording_execution_context_snapshot.status is status
    result, _, wp017 = compose(
        plan,
        run,
        upstream,
        successor_context_candidates=candidates,
        successor_context_uncertainties=uncertainties,
    )
    assert len(wp017.calls) == 1
    assert result.post_recording_execution_orchestration_decision is not None


def test_malformed_upstream_fails_before_orchestration() -> None:
    plan, run, upstream = canonical()
    preparation = upstream.post_recording_execution_handling_preparation
    assert preparation is not None
    cases = (
        object(),
        unsafe_clone(upstream, post_recording_execution_context_snapshot=None),
        unsafe_clone(upstream, post_recording_execution_work_subject=None),
        unsafe_clone(upstream, post_recording_execution_handling_preparation=None),
        unsafe_clone(upstream, post_recording_execution_recording_result=None),
        unsafe_clone(
            upstream,
            post_recording_execution_handling_preparation=unsafe_clone(
                preparation, run_id="foreign"
            ),
        ),
    )
    for forged in cases:
        wp017 = RecordingOrchestrator()
        with pytest.raises(Invariant):
            compose(plan, run, forged, orchestrator=wp017)
        assert wp017.calls == []


@pytest.mark.parametrize(
    "change",
    [
        {"subject_id": "foreign"},
        {"context_snapshot_id": "foreign"},
        {"need_ids": ("foreign",)},
        {"created_at": CONTEXT_TIME - timedelta(seconds=1)},
        {
            "created_at": (CONTEXT_TIME + timedelta(seconds=1)).astimezone(
                timezone(timedelta(hours=-6))
            )
        },
        {"context_references": [object()]},
        {"target": "system"},
    ],
)
def test_forged_wp017_decisions_rejected(change: dict[str, object]) -> None:
    plan, run, upstream = canonical()
    good, _, _ = compose(plan, run, upstream)
    decision = good.post_recording_execution_orchestration_decision
    assert decision is not None
    wp017 = RecordingOrchestrator(forced=unsafe_clone(decision, **change))
    with pytest.raises(Invariant):
        compose(plan, run, upstream, orchestrator=wp017)
    assert len(wp017.calls) == 1


def test_copied_requirement_and_unavailable_operational_target_rejected() -> None:
    plan, run, upstream = canonical()
    good, _, _ = compose(plan, run, upstream)
    decision = good.post_recording_execution_orchestration_decision
    assert decision is not None and decision.requirement is not None
    copied = replace(decision.requirement)
    for forged, availability in (
        (
            unsafe_clone(decision, requirement=copied),
            HandlerAvailability(capability=True),
        ),
        (decision, HandlerAvailability()),
    ):
        with pytest.raises(Invariant):
            compose(
                plan,
                run,
                upstream,
                availability=availability,
                orchestrator=RecordingOrchestrator(forced=forged),
            )


def test_error_propagation_and_no_retry() -> None:
    plan, run, upstream = canonical()
    upstream_error = RuntimeError("WP057 failed")
    wp017 = RecordingOrchestrator()
    with pytest.raises(RuntimeError) as caught:
        compose(plan, run, upstream, upstream_error=upstream_error, orchestrator=wp017)
    assert caught.value is upstream_error and wp017.calls == []
    decision_error = RuntimeError("WP017 failed")
    wp017 = RecordingOrchestrator(error=decision_error)
    with pytest.raises(RuntimeError) as caught:
        compose(plan, run, upstream, orchestrator=wp017)
    assert caught.value is decision_error and len(wp017.calls) == 1


def test_result_presence_invariant_and_no_forbidden_authorities() -> None:
    plan, run, upstream = canonical()
    good, _, _ = compose(plan, run, upstream)
    with pytest.raises(Invariant):
        replace(good, post_recording_execution_orchestration_decision=None)
    tree = ast.parse(Path(inspect.getfile(Composer)).read_text(encoding="utf-8"))
    imports = [
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    ]
    assert not any(
        any(
            word in module
            for word in (
                "plan_run_advancement",
                "plan_runs.reducer",
                "execution_start",
                "execution_request",
                "execution_binding",
                "persistence",
            )
        )
        for module in imports
    )
