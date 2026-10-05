"""WP048/C1: validated WP047 -> WP024 binding -> STOP.

Unsafe clones below are adversarial delegated artifacts, never reachability
evidence. Canonical CLARIFY is tested only within the WP024 domain.
"""

from __future__ import annotations

import ast
import inspect
import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import timedelta
from itertools import count
from pathlib import Path
from typing import Any, cast

import pytest

import iris.plan_step_execution_binding_post_recording_composition as api
import iris.plan_step_execution_binding_post_recording_composition.composer as module
from iris.context import ContextBudget, ContextUncertainty, UncertaintyReason
from iris.execution import ExecutionRequest
from iris.orchestrator import (
    ContextBlocker,
    ContextBlockerKind,
    HandlerAvailability,
    HandlingKind,
    OrchestrationReason,
    OrchestrationTarget,
)
from iris.plan_runs import StepProgressState
from iris.plan_step_execution_binding import (
    ExecutionBindingMismatchError,
    NonExecutableExecutionRequestError,
    PlanStepExecutionBinder,
    PlanStepExecutionBinding,
    StalePlanStepExecutionBindingError,
)
from iris.plan_step_execution_binding_post_recording_composition import (
    PlanStepExecutionBindingPostRecordingComposer as Composer,
)
from iris.plan_step_execution_binding_post_recording_composition import (
    PlanStepExecutionBindingPostRecordingCompositionInvariantError as Invariant,
)
from iris.plan_step_execution_binding_post_recording_composition import (
    PlanStepExecutionBindingPostRecordingCompositionResult as Result,
)
from iris.plan_step_execution_request_materialization_composition import (
    PlanStepExecutionRequestMaterializationComposer,
    PlanStepExecutionRequestMaterializationCompositionResult,
)
from iris.work_identity import WorkSubject
from tests.test_plan_step_execution_context_materialization_composition import (
    GLOBAL,
    POST_RECORDING_BUDGET,
    POST_RECORDING_CREATED,
    candidate,
)
from tests.test_plan_step_execution_evidence_assessment_composition import (
    BUDGET,
    CAPABILITY_AVAILABLE,
    CONTEXT_CREATED,
    capability_input,
    unsafe_clone,
)
from tests.test_plan_step_execution_orchestration_composition import (
    STEP_C_AVAILABLE,
    STEP_C_UNAVAILABLE,
)
from tests.test_plan_step_execution_request_materialization_composition import (
    REQUESTED,
    RecordingWP046,
    canonical_wp046,
    compose_from_wp046,
    no_subject_wp046,
)


class RecordingWP047(PlanStepExecutionRequestMaterializationComposer):
    def __init__(self, result: object = None, error: Exception | None = None):
        super().__init__(orchestration_composer=RecordingWP046())
        self.result = result
        self.error = error
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def compose(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return self.result


class RecordingBinder(PlanStepExecutionBinder):
    def __init__(self, *, forced: object = None, error: Exception | None = None):
        self.forced = forced
        self.error = error
        self.calls: list[tuple[Any, ...]] = []
        self.results: list[PlanStepExecutionBinding] = []
        self.raised: list[Exception] = []

    def bind(self, *args: Any) -> Any:
        self.calls.append(args)
        try:
            if self.error is not None:
                raise self.error
            result = self.forced if self.forced is not None else super().bind(*args)
        except Exception as exc:
            self.raised.append(exc)
            raise
        self.results.append(cast(PlanStepExecutionBinding, result))
        return result


def scenario(
    *,
    handling: HandlingKind | None = HandlingKind.CAPABILITY,
    terminal: bool = False,
    absent: bool = False,
) -> tuple[Any, Any, Any]:
    if absent:
        plan, run, upstream = no_subject_wp046()
    else:
        plan, run, upstream = canonical_wp046(
            selected_handling=handling,
            post_availability=STEP_C_UNAVAILABLE if terminal else STEP_C_AVAILABLE,
        )
    supplied = (
        capability_input()
        if not terminal and upstream.post_recording_orchestration_decision is not None
        else None
    )
    result, _ = compose_from_wp046(
        plan,
        run,
        upstream,
        post_execution_input=supplied,
        post_availability=STEP_C_UNAVAILABLE if terminal else STEP_C_AVAILABLE,
    )
    return plan, run, result


def operands(result: Any) -> dict[str, Any]:
    request = result.post_recording_execution_request
    return dict(
        candidates=(),
        budget=BUDGET,
        uncertainties=(),
        created_at=CONTEXT_CREATED,
        availability=CAPABILITY_AVAILABLE,
        execution_input=capability_input(),
        post_recording_candidates=(),
        post_recording_budget=POST_RECORDING_BUDGET,
        post_recording_uncertainties=(),
        post_recording_created_at=POST_RECORDING_CREATED,
        post_recording_availability=STEP_C_AVAILABLE,
        post_recording_execution_input=None
        if request is None
        else request.execution_input,
    )


def invoke(
    plan: Any,
    run: Any,
    upstream: RecordingWP047,
    binder: RecordingBinder,
    kwargs: dict[str, Any],
) -> Result:
    return Composer(
        request_materialization_composer=upstream,
        execution_binder=binder,
    ).compose(plan, run, "a", **kwargs)


def test_public_api_and_signatures() -> None:
    assert set(api.__all__) == {
        "PlanStepExecutionBindingPostRecordingComposer",
        "PlanStepExecutionBindingPostRecordingCompositionResult",
        "PlanStepExecutionBindingPostRecordingCompositionError",
        "PlanStepExecutionBindingPostRecordingCompositionInvariantError",
    }
    assert issubclass(
        Invariant, api.PlanStepExecutionBindingPostRecordingCompositionError
    )
    assert issubclass(Result, PlanStepExecutionRequestMaterializationCompositionResult)
    assert tuple(inspect.signature(Composer).parameters) == (
        "request_materialization_composer",
        "execution_binder",
    )
    actual = inspect.signature(Composer.compose)
    expected = inspect.signature(
        PlanStepExecutionRequestMaterializationComposer.compose
    )
    assert actual.parameters == expected.parameters
    with pytest.raises(TypeError):
        Composer()  # type: ignore[call-arg]
    for dependency in (None, object()):
        with pytest.raises(TypeError):
            Composer(request_materialization_composer=dependency)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Composer(
            request_materialization_composer=RecordingWP047(), execution_binder=object()
        )  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("name", "invalid"),
    [
        ("plan", object()),
        ("run", object()),
        ("step_id", 7),
        ("candidates", []),
        ("candidates", (object(),)),
        ("budget", object()),
        ("uncertainties", []),
        ("uncertainties", (object(),)),
        ("created_at", object()),
        ("availability", object()),
        ("execution_input", object()),
        ("post_recording_candidates", []),
        ("post_recording_candidates", (object(),)),
        ("post_recording_budget", object()),
        ("post_recording_uncertainties", []),
        ("post_recording_uncertainties", (object(),)),
        ("post_recording_created_at", object()),
        ("post_recording_availability", object()),
    ],
)
def test_direct_input_rejected_before_delegation(name: str, invalid: Any) -> None:
    plan, run, result = scenario(absent=True)
    kwargs = dict(plan=plan, run=run, step_id="a", **operands(result))
    kwargs[name] = invalid
    upstream, binder = RecordingWP047(result), RecordingBinder()
    with pytest.raises(TypeError):
        Composer(
            request_materialization_composer=upstream, execution_binder=binder
        ).compose(**kwargs)
    assert upstream.calls == binder.calls == []


@pytest.mark.parametrize("case", ["absent", "unspecified", "insufficient"])
def test_absence_skips_binder_preserves_artifacts_and_unused_input(case: str) -> None:
    plan, run, delegated = scenario(
        absent=case == "absent",
        handling=None if case == "unspecified" else HandlingKind.SYSTEM,
    )
    kwargs = operands(delegated)
    kwargs["post_recording_execution_input"] = object()  # unused, WP047-owned semantics
    upstream, binder = RecordingWP047(delegated), RecordingBinder()
    result = invoke(plan, run, upstream, binder, kwargs)
    assert len(upstream.calls) == 1
    assert binder.calls == []
    assert result.post_recording_execution_binding is None
    assert result.to_data()["post_recording_execution_binding"] is None
    for item in fields(delegated):
        assert getattr(result, item.name) is getattr(delegated, item.name)


def test_exact_forwarding_all_operands_and_exact_binder_lineage() -> None:
    plan, run, delegated = scenario()
    kwargs = operands(delegated)
    kwargs.update(
        candidates=(candidate("step-b-only", "B", key="b"),),
        uncertainties=(
            ContextUncertainty("task", "b", GLOBAL, UncertaintyReason.MISSING),
        ),
        post_recording_candidates=(candidate("step-c-only", "C", key="c"),),
        post_recording_uncertainties=(
            ContextUncertainty("task", "c", GLOBAL, UncertaintyReason.MISSING),
        ),
        availability=HandlerAvailability(system=True),
        post_recording_availability=HandlerAvailability(capability=True),
    )
    upstream, binder = RecordingWP047(delegated), RecordingBinder()
    result = invoke(plan, run, upstream, binder, kwargs)
    assert len(upstream.calls) == len(binder.calls) == 1
    args, forwarded = upstream.calls[0]
    assert args[0] is plan and args[1] is run and args[2] == "a"
    assert forwarded.keys() == kwargs.keys()
    for key, value in kwargs.items():
        assert forwarded[key] is value
    advancement = delegated.post_recording_advancement_result
    expected = (
        plan,
        advancement.updated_run,
        advancement.control_decision,
        delegated.post_recording_handling_preparation,
        delegated.post_recording_execution_request,
    )
    assert all(
        actual is exact for actual, exact in zip(binder.calls[0], expected, strict=True)
    )
    assert binder.calls[0][1] is not run
    assert binder.calls[0][1] is not delegated.advancement_result.updated_run
    assert binder.calls[0][1] is not delegated.execution_recording_result.recorded_run
    assert result.post_recording_execution_binding is binder.results[0]
    for item in fields(delegated):
        assert getattr(result, item.name) is getattr(delegated, item.name)


def test_binding_all_identifiers_and_no_state_mutation() -> None:
    plan, run, delegated = scenario()
    advancement = delegated.post_recording_advancement_result
    successor = advancement.updated_run
    before = (plan.to_data(), run.to_data(), successor.to_data())
    result = invoke(
        plan, run, RecordingWP047(delegated), RecordingBinder(), operands(delegated)
    )
    binding = result.post_recording_execution_binding
    request = result.post_recording_execution_request
    assert binding is not None and request is not None
    assert binding.to_data() == {
        "plan_id": plan.plan_id,
        "run_id": successor.run_id,
        "observed_revision": successor.revision,
        "step_id": advancement.control_decision.selected_step_id,
        "execution_id": request.execution_id,
        "subject_id": request.subject.subject_id,
        "context_snapshot_id": request.context.snapshot_id,
        "orchestration_decision_id": request.decision.decision_id,
        "handling_need_id": delegated.post_recording_handling_preparation.handling_need.need_id,
    }
    assert result.execution_binding is delegated.execution_binding
    assert result.execution_binding is not binding
    assert result.execution_binding.execution_id != binding.execution_id
    assert result.assessment.step_id == "a"
    assert result.execution_binding.step_id == "b"
    assert binding.step_id == "c"
    assert (
        next(s.state for s in successor.step_progress if s.step_id == binding.step_id)
        is StepProgressState.NOT_STARTED
    )
    assert before == (plan.to_data(), run.to_data(), successor.to_data())


def test_real_wp047_unsatisfied_reaches_binder_once_and_exact_error_propagates() -> (
    None
):
    plan, run, wp046 = canonical_wp046(post_availability=STEP_C_UNAVAILABLE)
    # Real WP047 constructs a canonical terminal request inside WP048.
    upstream = PlanStepExecutionRequestMaterializationComposer(
        orchestration_composer=RecordingWP046(forced=wp046),
        clock=lambda: REQUESTED,
        execution_id_factory=lambda: "step-c-terminal",
    )
    binder = RecordingBinder()
    kwargs = dict(
        candidates=(),
        budget=BUDGET,
        created_at=CONTEXT_CREATED,
        availability=CAPABILITY_AVAILABLE,
        execution_input=capability_input(),
        post_recording_candidates=(),
        post_recording_budget=POST_RECORDING_BUDGET,
        post_recording_created_at=POST_RECORDING_CREATED,
        post_recording_availability=STEP_C_UNAVAILABLE,
        post_recording_execution_input=None,
    )
    with pytest.raises(NonExecutableExecutionRequestError) as caught:
        Composer(
            request_materialization_composer=upstream, execution_binder=binder
        ).compose(plan, run, "a", **kwargs)
    assert len(binder.calls) == len(binder.raised) == 1
    assert caught.value is binder.raised[0]
    request = binder.calls[0][-1]
    assert isinstance(request, ExecutionRequest)
    assert request.decision is wp046.post_recording_orchestration_decision
    assert request.decision.target is OrchestrationTarget.UNSATISFIED
    assert request.decision.reason is OrchestrationReason.NO_ADMISSIBLE_HANDLER
    assert request.execution_input is None
    assert binder.results == []


@pytest.mark.parametrize("references", [False, True])
def test_adversarial_noncanonical_clarify_lineage_rejected_before_binder(
    references: bool,
) -> None:
    plan, run, delegated = scenario(terminal=True)
    # Deliberate contract violation, NOT canonical WP047 reachability.
    decision = delegated.post_recording_orchestration_decision
    blocker = ContextBlocker("task", "missing", GLOBAL, ContextBlockerKind.MISSING)
    forged_decision = unsafe_clone(
        decision,
        target=OrchestrationTarget.CLARIFY,
        reason=OrchestrationReason.MISSING_REQUIRED_INFORMATION,
        context_references=(blocker,) if references else (),
    )
    forged_request = unsafe_clone(
        delegated.post_recording_execution_request, decision=forged_decision
    )
    forged = unsafe_clone(
        delegated,
        post_recording_orchestration_decision=forged_decision,
        post_recording_execution_request=forged_request,
    )
    binder = RecordingBinder()
    with pytest.raises(Invariant):
        invoke(plan, run, RecordingWP047(forged), binder, operands(delegated))
    assert binder.calls == []


def test_wp024_canonical_clarify_domain_regression() -> None:
    # This is the independent WP024 domain, not a WP047/Step C reachability claim.
    from iris.work_identity import PlanStepWorkReference
    from tests.test_plan_step_execution_binding import execution_for, valid_inputs

    plan, run, control, preparation, _ = valid_inputs()
    request = execution_for(
        PlanStepWorkReference(plan.plan_id, run.run_id, preparation.step_id),
        preparation.handling_need,
        target=OrchestrationTarget.CLARIFY,
    )
    request.decision.__post_init__()
    request.__post_init__()
    binder = RecordingBinder()
    with pytest.raises(NonExecutableExecutionRequestError) as caught:
        binder.bind(plan, run, control, preparation, request)
    assert caught.value is binder.raised[0]
    assert len(binder.calls) == 1


def test_upstream_failure_propagates_unchanged() -> None:
    plan, run, delegated = scenario()
    failure = RuntimeError("upstream failure")
    upstream, binder = RecordingWP047(error=failure), RecordingBinder()
    with pytest.raises(RuntimeError) as caught:
        invoke(plan, run, upstream, binder, operands(delegated))
    assert caught.value is failure
    assert len(upstream.calls) == 1
    assert binder.calls == []


@pytest.mark.parametrize(
    "failure",
    [
        ExecutionBindingMismatchError("foreign"),
        StalePlanStepExecutionBindingError("stale"),
        NonExecutableExecutionRequestError("terminal"),
        RuntimeError("injected failure"),
    ],
)
def test_binder_error_propagates_exactly_without_retry(failure: Exception) -> None:
    plan, run, delegated = scenario()
    upstream, binder = RecordingWP047(delegated), RecordingBinder(error=failure)
    with pytest.raises(type(failure)) as caught:
        invoke(plan, run, upstream, binder, operands(delegated))
    assert caught.value is failure
    assert len(upstream.calls) == len(binder.calls) == 1


@pytest.mark.parametrize(
    "mismatch",
    [
        "type",
        "incomplete",
        "source_plan",
        "source_run",
        "source_revision",
        "source_step",
        "missing_advancement",
        "successor_type",
        "stale_control",
        "foreign_control",
        "preparation_step",
        "preparation_need",
        "subject_step",
        "subject_origin",
        "context_identity",
        "context_missing",
        "context_budget",
        "context_time",
        "decision_subject",
        "decision_type",
        "decision_time",
        "decision_need",
        "request_missing",
        "request_subject",
        "request_decision",
        "request_time",
        "request_input",
        "request_id_collision",
    ],
)
def test_malformed_upstream_fails_before_binder(mismatch: str) -> None:
    plan, run, delegated = scenario()
    kwargs = operands(delegated)
    a = delegated.post_recording_advancement_result
    p = delegated.post_recording_handling_preparation
    s = delegated.post_recording_work_subject
    c = delegated.post_recording_context_snapshot
    d = delegated.post_recording_orchestration_decision
    q = delegated.post_recording_execution_request
    changes: dict[str, Any] = {}
    forced: Any = delegated
    if mismatch == "type":
        forced = object()
    elif mismatch == "incomplete":
        forced = object.__new__(type(delegated))
    elif mismatch.startswith("source_"):
        key = {
            "source_plan": "plan_id",
            "source_run": "run_id",
            "source_revision": "run_revision",
            "source_step": "step_id",
        }[mismatch]
        changes["assessment"] = unsafe_clone(
            delegated.assessment,
            **{
                key: 999 if key == "run_revision" else "foreign",
            },
        )
    elif mismatch == "missing_advancement":
        changes["post_recording_advancement_result"] = None
    elif mismatch == "successor_type":
        changes["post_recording_advancement_result"] = unsafe_clone(
            a, updated_run=object()
        )
    elif mismatch in ("stale_control", "foreign_control"):
        changes["post_recording_advancement_result"] = unsafe_clone(
            a,
            control_decision=unsafe_clone(
                a.control_decision,
                **(
                    {"observed_revision": 999}
                    if mismatch == "stale_control"
                    else {"run_id": "foreign"}
                ),
            ),
        )
    elif mismatch == "preparation_step":
        changes["post_recording_handling_preparation"] = unsafe_clone(p, step_id="a")
    elif mismatch == "preparation_need":
        changes["post_recording_handling_preparation"] = unsafe_clone(
            p,
            handling_need=replace(p.handling_need, need_id="foreign"),
        )
    elif mismatch == "subject_step":
        changes["post_recording_work_subject"] = WorkSubject(
            s.kind, replace(s.reference, step_id="a")
        )
    elif mismatch == "subject_origin":
        changes["post_recording_work_subject"] = unsafe_clone(s, origin=object())
    elif mismatch == "context_identity":
        changes["post_recording_context_snapshot"] = replace(
            c, subject=WorkSubject(s.kind, s.reference)
        )
    elif mismatch == "context_missing":
        changes["post_recording_context_snapshot"] = None
    elif mismatch == "context_budget":
        changes["post_recording_context_snapshot"] = replace(c, budget=ContextBudget(9))
    elif mismatch == "context_time":
        changes["post_recording_context_snapshot"] = replace(
            c, created_at=c.created_at - timedelta(seconds=1)
        )
    elif mismatch.startswith("decision_"):
        changes["post_recording_orchestration_decision"] = (
            object()
            if mismatch == "decision_type"
            else unsafe_clone(
                d,
                **{
                    "decision_subject": {"subject_id": "foreign"},
                    "decision_time": {
                        "created_at": c.created_at - timedelta(seconds=1)
                    },
                    "decision_need": {"need_ids": ("foreign",)},
                }[mismatch],
            )
        )
    elif mismatch == "request_missing":
        changes["post_recording_execution_request"] = None
    elif mismatch == "request_subject":
        changes["post_recording_execution_request"] = unsafe_clone(
            q, subject=WorkSubject(s.kind, s.reference)
        )
    elif mismatch == "request_decision":
        changes["post_recording_execution_request"] = unsafe_clone(
            q, decision=replace(d)
        )
    elif mismatch == "request_time":
        changes["post_recording_execution_request"] = unsafe_clone(
            q, created_at=d.created_at - timedelta(seconds=1)
        )
    elif mismatch == "request_input":
        changes["post_recording_execution_request"] = unsafe_clone(
            q, execution_input=object()
        )
    else:
        changes["post_recording_execution_request"] = unsafe_clone(
            q, execution_id=delegated.execution_request.execution_id
        )
    if changes:
        forced = unsafe_clone(delegated, **changes)
    upstream, binder = RecordingWP047(forced), RecordingBinder()
    with pytest.raises(Invariant):
        invoke(plan, run, upstream, binder, kwargs)
    assert len(upstream.calls) == 1
    assert binder.calls == []


@pytest.mark.parametrize(
    "field",
    [
        "type",
        "incomplete",
        "plan_id",
        "run_id",
        "observed_revision",
        "step_id",
        "execution_id",
        "subject_id",
        "context_snapshot_id",
        "orchestration_decision_id",
        "handling_need_id",
        "malformed_revision",
        "inherited",
    ],
)
def test_malformed_binder_result_is_wp048_invariant(field: str) -> None:
    plan, run, delegated = scenario()
    a = delegated.post_recording_advancement_result
    canonical = PlanStepExecutionBinder().bind(
        plan,
        a.updated_run,
        a.control_decision,
        delegated.post_recording_handling_preparation,
        delegated.post_recording_execution_request,
    )
    if field == "type":
        forced: object = object()
    elif field == "incomplete":
        forced = object.__new__(PlanStepExecutionBinding)
    elif field == "inherited":
        forced = delegated.execution_binding
    else:
        key = "observed_revision" if field == "malformed_revision" else field
        value = (
            True
            if field == "malformed_revision"
            else 999
            if field == "observed_revision"
            else "foreign"
        )
        forced = unsafe_clone(canonical, **{key: value})
    binder = RecordingBinder(forced=forced)
    with pytest.raises(Invariant):
        invoke(plan, run, RecordingWP047(delegated), binder, operands(delegated))
    assert len(binder.calls) == 1


def test_successful_presence_invariant_both_directions() -> None:
    plan, run, delegated = scenario()
    successful = invoke(
        plan, run, RecordingWP047(delegated), RecordingBinder(), operands(delegated)
    )
    with pytest.raises(Invariant):
        replace(successful, post_recording_execution_binding=None)
    _, _, absent = scenario(absent=True)
    with pytest.raises(Invariant):
        Result(
            **{f.name: getattr(absent, f.name) for f in fields(absent)},
            post_recording_execution_binding=successful.post_recording_execution_binding,
        )


def test_frozen_slots_and_stable_serialization() -> None:
    plan, run, delegated = scenario()
    result = invoke(
        plan, run, RecordingWP047(delegated), RecordingBinder(), operands(delegated)
    )
    assert not hasattr(result, "__dict__")
    with pytest.raises(FrozenInstanceError):
        result.post_recording_execution_binding = None  # type: ignore[misc]
    data = result.to_data()
    assert data == result.to_data()
    assert json.loads(json.dumps(data)) == data
    binding_data = data.pop("post_recording_execution_binding")
    assert data == delegated.to_data()
    assert binding_data == result.post_recording_execution_binding.to_data()


def test_impossible_context_causality_rejected_before_binder() -> None:
    plan, run, delegated = scenario()
    early = delegated.execution_start_result.execution_result.completed_at - timedelta(
        microseconds=1
    )
    context = replace(delegated.post_recording_context_snapshot, created_at=early)
    request = replace(delegated.post_recording_execution_request, context=context)
    forged = unsafe_clone(
        delegated,
        post_recording_context_snapshot=context,
        post_recording_execution_request=request,
    )
    kwargs = operands(delegated)
    kwargs["post_recording_created_at"] = early
    binder = RecordingBinder()
    with pytest.raises(Invariant, match="predates"):
        invoke(plan, run, RecordingWP047(forged), binder, kwargs)
    assert binder.calls == []


@pytest.mark.parametrize("has_request", [False, True])
def test_real_wp047_owns_unused_or_invalid_step_c_input(has_request: bool) -> None:
    plan, run, wp046 = canonical_wp046() if has_request else no_subject_wp046()
    wp047 = PlanStepExecutionRequestMaterializationComposer(
        orchestration_composer=RecordingWP046(forced=wp046),
        clock=lambda: REQUESTED,
        execution_id_factory=lambda: "step-c-real-wp047",
    )
    _, _, absent = scenario(absent=True)
    kwargs = operands(absent)
    kwargs["post_recording_execution_input"] = object()
    binder = RecordingBinder()
    composer = Composer(request_materialization_composer=wp047, execution_binder=binder)
    if has_request:
        with pytest.raises(TypeError, match="CapabilityExecutionInput"):
            composer.compose(plan, run, "a", **kwargs)
    else:
        result = composer.compose(plan, run, "a", **kwargs)
        assert result.post_recording_execution_binding is None
    assert binder.calls == []


def test_default_binder_and_repeated_fresh_requests_no_deduplication() -> None:
    plan, run, wp046 = canonical_wp046()
    ids = count(1)
    wp047 = PlanStepExecutionRequestMaterializationComposer(
        orchestration_composer=RecordingWP046(forced=wp046),
        clock=lambda: REQUESTED,
        execution_id_factory=lambda: f"wp048-c-{next(ids)}",
    )
    _, _, delegated = scenario()
    kwargs = operands(delegated)
    composer = Composer(request_materialization_composer=wp047)
    first = composer.compose(plan, run, "a", **kwargs)
    second = composer.compose(plan, run, "a", **kwargs)
    assert (
        first.post_recording_execution_binding.execution_id
        != second.post_recording_execution_binding.execution_id
    )


def test_binding_currentness_validator_used(monkeypatch: pytest.MonkeyPatch) -> None:
    plan, run, delegated = scenario()
    calls = []
    original = module.validate_plan_step_execution_binding_current

    def spy(*args: Any) -> None:
        calls.append(args)
        original(*args)

    monkeypatch.setattr(module, "validate_plan_step_execution_binding_current", spy)
    binder = RecordingBinder()
    result = invoke(plan, run, RecordingWP047(delegated), binder, operands(delegated))
    assert len(calls) == 1
    assert calls[0][0] is plan
    assert calls[0][1] is delegated.post_recording_advancement_result.updated_run
    assert calls[0][2] is result.post_recording_execution_binding


def test_no_forbidden_behavior_or_duplicate_bindability_policy() -> None:
    package = Path(module.__file__).parent
    source = "\n".join(p.read_text(encoding="utf-8") for p in package.glob("*.py"))
    for forbidden in (
        "plan_step_execution_binding_composition",
        "PlanStepExecutionStartCoordinator",
        "ExecutionCoordinator",
        "PlanRunReducer",
        "PlanRunController",
        "CapabilityRuntime",
        "IntelligenceRuntime",
        "ExecutionResult(",
        "StepProgressUpdate(",
        "ExecutionRequest(",
        "Orchestrator(",
        "_EXECUTABLE_TARGETS",
        "OrchestrationTarget",
        "NonExecutableExecutionRequestError",
        "derive_step_availability",
        "StepAvailability",
        "StepProgressState",
        "subprocess",
        "socket",
        "Continuation",
        "execution_id_factory",
        "clock",
    ):
        assert forbidden not in source
    tree = ast.parse(inspect.getsource(module))
    assert not any(isinstance(n, (ast.While, ast.AsyncFor)) for n in ast.walk(tree))
    compose = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "compose"
    )
    calls = [n for n in ast.walk(compose) if isinstance(n, ast.Call)]
    assert (
        sum(
            isinstance(n.func, ast.Attribute) and n.func.attr == "compose"
            for n in calls
        )
        == 1
    )
    assert (
        sum(isinstance(n.func, ast.Attribute) and n.func.attr == "bind" for n in calls)
        == 1
    )
