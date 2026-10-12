"""WP057: contextualize only the exact selected successor and stop."""

from __future__ import annotations

import ast
import inspect
import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

import pytest

import iris.plan_step_execution_context_materialization_post_recording_composition as api
from iris.context import (
    ContextBudget,
    ContextConflict,
    ContextEngine,
    ContextSnapshot,
    ContextUncertainty,
    ResolutionStatus,
    UncertaintyReason,
)
from iris.orchestrator import HandlingKind
from iris.plan_control import ControlDecisionKind
from iris.plan_handling import StepHandlingPreparationStatus
from iris.plan_step_execution_work_subject_materialization_post_recording_composition import (
    PlanStepExecutionWorkSubjectMaterializationPostRecordingComposer as Upstream,
)
from iris.plan_step_execution_work_subject_materialization_post_recording_composition import (
    PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionResult as UpstreamResult,
)
from tests.test_context import GLOBAL, candidate
from tests.test_plan_step_execution_binding_post_recording_composition import operands
from tests.test_plan_step_execution_evidence_assessment_composition import unsafe_clone
from tests.test_plan_step_execution_handling_preparation_post_recording_composition import (
    canonical_wp054,
)
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
    RecordingWP055,
    selected,
)
from tests.test_plan_step_execution_work_subject_materialization_post_recording_composition import (
    invoke as invoke_wp056,
)

Composer = api.PlanStepExecutionContextMaterializationPostRecordingComposer
Result = api.PlanStepExecutionContextMaterializationPostRecordingCompositionResult
Invariant = (
    api.PlanStepExecutionContextMaterializationPostRecordingCompositionInvariantError
)
CONTEXT_TIME = datetime(2026, 10, 3, 0, 3, 38, tzinfo=UTC)


class RecordingWP056(Upstream):
    def __init__(
        self, result: object = None, *, error: Exception | None = None
    ) -> None:
        super().__init__(handling_preparation_composer=RecordingWP055())
        self.result = result
        self.error = error
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def compose(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return self.result


class RecordingContextEngine(ContextEngine):
    def __init__(
        self, *, forced: object = None, error: Exception | None = None
    ) -> None:
        super().__init__()
        self.forced = forced
        self.error = error
        self.calls: list[dict[str, object]] = []
        self.results: list[ContextSnapshot] = []

    def build(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        snapshot = (
            super().build(**kwargs)
            if self.forced is None
            else cast(ContextSnapshot, self.forced)
        )
        self.results.append(snapshot)
        return snapshot


def selected_wp056(
    handling: HandlingKind | None = HandlingKind.CAPABILITY,
) -> tuple[Any, Any, UpstreamResult]:
    plan, run, wp055 = selected(handling)
    result, _, _ = invoke_wp056(plan, run, wp055)
    return plan, run, result


def call(
    plan: Any,
    run: Any,
    upstream_result: object,
    *,
    engine: RecordingContextEngine | None = None,
    upstream_error: Exception | None = None,
    **overrides: object,
) -> tuple[Result, RecordingWP056, RecordingContextEngine]:
    upstream = RecordingWP056(upstream_result, error=upstream_error)
    context_engine = engine or RecordingContextEngine()
    kwargs = (
        operands(upstream_result)
        if isinstance(upstream_result, UpstreamResult)
        else operands(selected_wp056()[2])
    )
    kwargs.update(
        successor_context_candidates=(),
        successor_context_budget=ContextBudget(2),
        successor_context_uncertainties=(),
        successor_context_created_at=CONTEXT_TIME,
    )
    kwargs.update(overrides)
    result = Composer(
        work_subject_materialization_composer=upstream,
        context_engine=context_engine,
    ).compose(plan, run, "a", **kwargs)
    return result, upstream, context_engine


def from_upstream(upstream: UpstreamResult, snapshot: ContextSnapshot | None) -> Result:
    return Result(
        **{
            field.name: getattr(upstream, field.name)
            for field in fields(UpstreamResult)
        },
        post_recording_execution_context_snapshot=snapshot,
    )


def test_public_contract_and_signature() -> None:
    assert api.__all__ == [
        "PlanStepExecutionContextMaterializationPostRecordingComposer",
        "PlanStepExecutionContextMaterializationPostRecordingCompositionResult",
        "PlanStepExecutionContextMaterializationPostRecordingCompositionError",
        "PlanStepExecutionContextMaterializationPostRecordingCompositionInvariantError",
    ]
    assert issubclass(Result, UpstreamResult)
    assert issubclass(
        Invariant,
        api.PlanStepExecutionContextMaterializationPostRecordingCompositionError,
    )
    parameters = list(inspect.signature(Composer.compose).parameters)
    assert parameters == list(inspect.signature(Upstream.compose).parameters) + [
        "successor_context_candidates",
        "successor_context_budget",
        "successor_context_uncertainties",
        "successor_context_created_at",
    ]
    assert list(inspect.signature(Composer).parameters) == [
        "work_subject_materialization_composer",
        "context_engine",
    ]
    with pytest.raises(TypeError):
        Composer(work_subject_materialization_composer=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Composer(
            work_subject_materialization_composer=RecordingWP056(),
            context_engine=object(),  # type: ignore[arg-type]
        )


def test_absent_advancement_preserves_upstream_and_skips_context() -> None:
    plan, run, wp053 = canonical_wp054_base(absent=True)
    wp054, _, _ = invoke_wp054(plan, run, wp053)
    wp055, _, _ = invoke_wp055(plan, run, wp054)
    wp056, _, _ = invoke_wp056(plan, run, wp055)
    marker = object()
    result, upstream, engine = call(
        plan,
        run,
        wp056,
        successor_context_candidates=marker,
        successor_context_budget=marker,
        successor_context_uncertainties=marker,
        successor_context_created_at=marker,
        post_recording_execution_input=marker,
    )
    assert len(upstream.calls) == 1
    assert upstream.calls[0][1]["post_recording_execution_input"] is marker
    assert engine.calls == []
    assert result.post_recording_execution_context_snapshot is None
    for field in fields(UpstreamResult):
        assert getattr(result, field.name) is getattr(wp056, field.name)
    assert result.to_data()["post_recording_execution_context_snapshot"] is None


@pytest.mark.parametrize(
    "kind",
    [
        ControlDecisionKind.ACTIVE_WORK_PENDING,
        ControlDecisionKind.SELECTION_UNRESOLVED,
        ControlDecisionKind.RUN_CANNOT_ADVANCE,
        ControlDecisionKind.RUN_STRUCTURALLY_COMPLETE,
    ],
)
def test_nonselected_control_skips_context(kind: ControlDecisionKind) -> None:
    plan, run, wp054 = canonical_wp054()
    advancement = wp054.post_recording_execution_advancement_result
    assert advancement is not None
    defensive = unsafe_clone(
        wp054,
        post_recording_execution_advancement_result=replace(
            advancement,
            control_decision=decision_for_kind(kind, advancement.updated_run),
        ),
    )
    wp055, _, _ = invoke_wp055(plan, run, defensive)
    wp056, _, _ = invoke_wp056(plan, run, wp055)
    result, _, engine = call(plan, run, wp056, successor_context_budget=object())
    assert result.post_recording_execution_context_snapshot is None
    assert engine.calls == []


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
def test_selected_context_preserves_identity_and_every_handling_status(
    handling: HandlingKind | None, status: StepHandlingPreparationStatus
) -> None:
    plan, run, wp056 = selected_wp056(handling)
    result, upstream, engine = call(plan, run, wp056)
    subject = wp056.post_recording_execution_work_subject
    snapshot = result.post_recording_execution_context_snapshot
    assert subject is not None and snapshot is not None
    assert len(upstream.calls) == len(engine.calls) == 1
    assert upstream.calls[0][0] == (plan, run, "a")
    forwarded = upstream.calls[0][1]
    expected = operands(wp056)
    assert forwarded.keys() == expected.keys()
    assert forwarded == expected
    assert engine.calls[0]["subject"] is subject
    assert engine.calls[0]["created_at"] is CONTEXT_TIME
    assert "request_id" not in engine.calls[0]
    assert snapshot is engine.results[0]
    assert snapshot.subject is subject
    assert snapshot.status is ResolutionStatus.RESOLVED
    assert wp056.post_recording_execution_handling_preparation.status is status
    assert result.post_recording_execution_handling_preparation is (
        wp056.post_recording_execution_handling_preparation
    )
    for field in fields(UpstreamResult):
        assert getattr(result, field.name) is getattr(wp056, field.name)
    assert (
        result.to_data()["post_recording_execution_context_snapshot"]
        == snapshot.to_data()
    )
    assert json.loads(json.dumps(result.to_data())) == result.to_data()
    with pytest.raises(FrozenInstanceError):
        result.post_recording_execution_context_snapshot = None  # type: ignore[misc]
    assert Result.__slots__ == ("post_recording_execution_context_snapshot",)


def test_successor_context_uses_only_new_inputs_and_exact_timestamp() -> None:
    plan, run, wp056 = selected_wp056()
    entry = candidate("fresh", "successor")
    candidates = (entry,)
    budget = ContextBudget(1)
    uncertainties: tuple[ContextUncertainty, ...] = ()
    offset = CONTEXT_TIME.astimezone(timezone(timedelta(hours=-6)))
    result, _, engine = call(
        plan,
        run,
        wp056,
        successor_context_candidates=candidates,
        successor_context_budget=budget,
        successor_context_uncertainties=uncertainties,
        successor_context_created_at=offset,
    )
    assert engine.calls[0]["candidates"] is candidates
    assert engine.calls[0]["budget"] is budget
    assert engine.calls[0]["uncertainties"] is uncertainties
    assert engine.calls[0]["created_at"] is offset
    assert result.post_recording_execution_context_snapshot.created_at == CONTEXT_TIME
    assert (
        result.post_recording_execution_context_snapshot.items[0].candidate_id
        == "fresh"
    )


def test_all_inherited_arguments_forwarded_by_identity() -> None:
    plan, run, wp056 = selected_wp056()
    supplied = operands(wp056)
    _, upstream, _ = call(plan, run, wp056, **supplied)
    forwarded = upstream.calls[0][1]
    assert forwarded.keys() == supplied.keys()
    assert all(forwarded[name] is value for name, value in supplied.items())


@pytest.mark.parametrize(
    "delta",
    [timedelta(seconds=-4), timedelta(seconds=-1), timedelta(0), timedelta(seconds=1)],
)
def test_temporal_boundaries(delta: timedelta) -> None:
    plan, run, wp056 = selected_wp056()
    instant = CONTEXT_TIME + delta
    engine = RecordingContextEngine()
    if delta < timedelta(0):
        with pytest.raises(Invariant):
            call(plan, run, wp056, engine=engine, successor_context_created_at=instant)
        assert engine.calls == []
    else:
        result, _, _ = call(
            plan, run, wp056, engine=engine, successor_context_created_at=instant
        )
        assert result.post_recording_execution_context_snapshot.created_at == instant


def test_context_before_execution_completion_rejected_independently() -> None:
    plan, run, wp056 = selected_wp056()
    start = wp056.post_recording_execution_start_result
    assert start is not None
    advancement = wp056.post_recording_execution_advancement_result
    assert advancement is not None
    later_start = unsafe_clone(
        start,
        execution_result=unsafe_clone(
            start.execution_result, completed_at=CONTEXT_TIME + timedelta(seconds=1)
        ),
    )
    forged = unsafe_clone(wp056, post_recording_execution_start_result=later_start)
    engine = RecordingContextEngine()
    with pytest.raises(Invariant):
        call(plan, run, forged, engine=engine)
    assert engine.calls == []


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("successor_context_candidates", object()),
        ("successor_context_budget", object()),
        ("successor_context_uncertainties", object()),
        ("successor_context_created_at", datetime(2026, 10, 3)),
    ],
)
def test_selected_inputs_fail_before_context_build(field: str, bad: object) -> None:
    plan, run, wp056 = selected_wp056()
    engine = RecordingContextEngine()
    with pytest.raises((TypeError, ValueError)):
        call(plan, run, wp056, engine=engine, **{field: bad})
    assert engine.calls == []


def test_all_canonical_context_statuses() -> None:
    plan, run, wp056 = selected_wp056()
    one = candidate("one", "v1", key="one")
    two = candidate("two", "v2", key="two")
    ambiguous = ContextUncertainty(
        "task", "question", GLOBAL, UncertaintyReason.MULTIPLE_PLAUSIBLE, ("one", "two")
    )
    missing = ContextUncertainty("task", "missing", GLOBAL, UncertaintyReason.MISSING)
    cases = [
        ((), (), ResolutionStatus.RESOLVED),
        ((), (missing,), ResolutionStatus.PARTIAL),
        ((one, two), (ambiguous,), ResolutionStatus.AMBIGUOUS),
        ((one, replace(two, key="one")), (), ResolutionStatus.CONFLICTED),
    ]
    for candidates, uncertainties, status in cases:
        result, _, _ = call(
            plan,
            run,
            wp056,
            successor_context_candidates=candidates,
            successor_context_uncertainties=uncertainties,
        )
        assert result.post_recording_execution_context_snapshot.status is status


@pytest.mark.parametrize(
    "change",
    [
        {"post_recording_execution_work_subject": None},
        {"post_recording_execution_recording_result": None},
        {"post_recording_execution_handling_preparation": None},
        {"post_recording_execution_advancement_result": None},
        {"post_recording_execution_progress_update": None},
    ],
)
def test_malformed_upstream_fails_before_context(change: dict[str, object]) -> None:
    plan, run, wp056 = selected_wp056()
    engine = RecordingContextEngine()
    with pytest.raises(Invariant):
        call(plan, run, unsafe_clone(wp056, **change), engine=engine)
    assert engine.calls == []


def test_foreign_and_stale_upstream_lineage_fails_before_context() -> None:
    plan, run, wp056 = selected_wp056()
    advancement = wp056.post_recording_execution_advancement_result
    subject = wp056.post_recording_execution_work_subject
    assert advancement is not None and subject is not None
    cases = (
        unsafe_clone(
            wp056,
            post_recording_execution_advancement_result=unsafe_clone(
                advancement,
                updated_run=unsafe_clone(advancement.updated_run, plan_id="foreign"),
            ),
        ),
        unsafe_clone(
            wp056,
            post_recording_execution_advancement_result=unsafe_clone(
                advancement,
                control_decision=unsafe_clone(
                    advancement.control_decision,
                    observed_revision=advancement.updated_run.revision - 1,
                ),
            ),
        ),
        unsafe_clone(
            wp056,
            post_recording_execution_work_subject=unsafe_clone(
                subject,
                reference=unsafe_clone(subject.reference, step_id="foreign"),
            ),
        ),
    )
    for forged in cases:
        engine = RecordingContextEngine()
        with pytest.raises(Invariant):
            call(plan, run, forged, engine=engine)
        assert engine.calls == []


def test_wrong_upstream_type_and_errors() -> None:
    plan, run, wp056 = selected_wp056()
    engine = RecordingContextEngine()
    with pytest.raises(Invariant):
        call(plan, run, object(), engine=engine)
    assert engine.calls == []
    error = RuntimeError("WP056 failed")
    with pytest.raises(RuntimeError) as caught:
        call(plan, run, wp056, engine=engine, upstream_error=error)
    assert caught.value is error and engine.calls == []


def test_context_error_propagates_once() -> None:
    plan, run, wp056 = selected_wp056()
    error = ValueError("WP016 failed")
    engine = RecordingContextEngine(error=error)
    with pytest.raises(ValueError) as caught:
        call(plan, run, wp056, engine=engine)
    assert caught.value is error and len(engine.calls) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"status": "forged"},
        {"created_at": CONTEXT_TIME + timedelta(seconds=1)},
        {"budget": ContextBudget(99)},
        {"items": (object(),)},
        {"budget_excluded_ids": ["forged"]},
    ],
)
def test_malformed_context_result_rejected(change: dict[str, object]) -> None:
    plan, run, wp056 = selected_wp056()
    subject = wp056.post_recording_execution_work_subject
    assert subject is not None
    good = ContextEngine().build(
        subject=subject, candidates=(), budget=ContextBudget(2), created_at=CONTEXT_TIME
    )
    engine = RecordingContextEngine(forced=unsafe_clone(good, **change))
    with pytest.raises(Invariant):
        call(plan, run, wp056, engine=engine)
    assert len(engine.calls) == 1


def test_wrong_context_return_type_and_budget_overflow_rejected() -> None:
    plan, run, wp056 = selected_wp056()
    subject = wp056.post_recording_execution_work_subject
    assert subject is not None
    with pytest.raises(Invariant):
        call(plan, run, wp056, engine=RecordingContextEngine(forced=object()))
    items = tuple(
        candidate(f"candidate-{index}", index, key=f"key_{index}").to_item()
        for index in range(3)
    )
    good = ContextEngine().build(
        subject=subject, candidates=(), budget=ContextBudget(2), created_at=CONTEXT_TIME
    )
    with pytest.raises(Invariant):
        call(
            plan,
            run,
            wp056,
            engine=RecordingContextEngine(forced=unsafe_clone(good, items=items)),
        )


def test_foreign_context_evidence_and_conflicts_rejected() -> None:
    plan, run, wp056 = selected_wp056()
    subject = wp056.post_recording_execution_work_subject
    assert subject is not None
    good = ContextEngine().build(
        subject=subject, candidates=(), budget=ContextBudget(2), created_at=CONTEXT_TIME
    )
    foreign = candidate("foreign", "value")
    item = foreign.to_item()
    conflict = ContextConflict(
        "task",
        "active_task",
        GLOBAL,
        ("foreign", "another"),
        (foreign.evidence, candidate("another", "other").evidence),
    )
    cases = (
        unsafe_clone(good, items=(item,)),
        unsafe_clone(good, budget_excluded_ids=("foreign",)),
        unsafe_clone(good, status=ResolutionStatus.CONFLICTED, conflicts=(conflict,)),
    )
    for snapshot in cases:
        with pytest.raises(Invariant):
            call(plan, run, wp056, engine=RecordingContextEngine(forced=snapshot))


def test_nested_context_corruption_rejected_without_repair() -> None:
    plan, run, wp056 = selected_wp056()
    subject = wp056.post_recording_execution_work_subject
    assert subject is not None
    entry = candidate("real", "value")
    good = ContextEngine().build(
        subject=subject,
        candidates=(entry,),
        budget=ContextBudget(2),
        created_at=CONTEXT_TIME,
    )
    item = good.items[0]
    broken_item = unsafe_clone(item, value=object())
    broken_evidence = unsafe_clone(item.evidence, reference=" ")
    for snapshot in (
        unsafe_clone(good, items=(broken_item,)),
        unsafe_clone(good, items=(unsafe_clone(item, evidence=broken_evidence),)),
    ):
        with pytest.raises(Invariant):
            call(
                plan,
                run,
                wp056,
                engine=RecordingContextEngine(forced=snapshot),
                successor_context_candidates=(entry,),
            )


def test_uncertainty_corruption_and_supplied_uncertainty_omission() -> None:
    plan, run, wp056 = selected_wp056()
    subject = wp056.post_recording_execution_work_subject
    assert subject is not None
    missing = ContextUncertainty("task", "missing", GLOBAL, UncertaintyReason.MISSING)
    good = ContextEngine().build(
        subject=subject,
        candidates=(),
        budget=ContextBudget(2),
        uncertainties=(missing,),
        created_at=CONTEXT_TIME,
    )
    forged = (
        unsafe_clone(good, uncertainties=()),
        unsafe_clone(
            good,
            uncertainties=(unsafe_clone(missing, candidate_ids=["foreign"]),),
        ),
    )
    for snapshot in forged:
        with pytest.raises(Invariant):
            call(
                plan,
                run,
                wp056,
                engine=RecordingContextEngine(forced=snapshot),
                successor_context_uncertainties=(missing,),
            )


def test_foreign_equal_owner_and_alias_rejected() -> None:
    plan, run, wp056 = selected_wp056()
    subject = wp056.post_recording_execution_work_subject
    assert subject is not None
    good = ContextEngine().build(
        subject=subject, candidates=(), budget=ContextBudget(2), created_at=CONTEXT_TIME
    )
    owner_copy = replace(subject)
    assert owner_copy == subject and owner_copy is not subject
    for snapshot in (
        unsafe_clone(good, subject=owner_copy),
        unsafe_clone(good, subject=wp056.work_subject),
        wp056.context_snapshot,
        wp056.post_recording_context_snapshot,
    ):
        with pytest.raises(Invariant):
            call(plan, run, wp056, engine=RecordingContextEngine(forced=snapshot))


def test_direct_result_presence_and_owner_validation() -> None:
    plan, run, wp056 = selected_wp056()
    subject = wp056.post_recording_execution_work_subject
    assert subject is not None
    good = ContextEngine().build(
        subject=subject, candidates=(), budget=ContextBudget(2), created_at=CONTEXT_TIME
    )
    assert from_upstream(wp056, good).post_recording_execution_context_snapshot is good
    with pytest.raises(Invariant):
        from_upstream(wp056, None)
    with pytest.raises(Invariant):
        from_upstream(wp056, unsafe_clone(good, subject=replace(subject)))


def test_repeated_builds_have_no_deduplication() -> None:
    plan, run, wp056 = selected_wp056()
    upstream = RecordingWP056(wp056)
    engine = RecordingContextEngine()
    composer = Composer(
        work_subject_materialization_composer=upstream, context_engine=engine
    )
    kwargs = operands(wp056)
    kwargs.update(
        successor_context_candidates=(),
        successor_context_budget=ContextBudget(2),
        successor_context_created_at=CONTEXT_TIME,
    )
    first = composer.compose(plan, run, "a", **kwargs)
    second = composer.compose(plan, run, "a", **kwargs)
    assert len(upstream.calls) == len(engine.calls) == 2
    assert first.post_recording_execution_context_snapshot.snapshot_id != (
        second.post_recording_execution_context_snapshot.snapshot_id
    )


def test_no_forbidden_authority_imports() -> None:
    package = Path(inspect.getfile(Composer)).parent
    names = set()
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                names.add(node.module)
    forbidden = (
        "plan_run_reducer",
        "plan_run_control",
        "orchestrator.engine",
        "execution_runtime",
        "plan_step_execution_binding",
        "memory.store",
    )
    assert not any(any(token in name for token in forbidden) for name in names)
