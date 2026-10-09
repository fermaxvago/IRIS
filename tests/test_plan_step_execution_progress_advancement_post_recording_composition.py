"""WP054: one optional WP023 advancement of the exact Step C update."""

from __future__ import annotations

import ast
import inspect
import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

import iris.plan_step_execution_progress_advancement_post_recording_composition as api
from iris.outcome_assessment import StepOutcomeStatus
from iris.plan_control import ControlDecision, ControlDecisionKind, ControlReason
from iris.plan_run_advancement import PlanRunProgressAdvancer
from iris.plan_runs import (
    ForeignEvidenceError,
    InvalidStepTransitionError,
    StalePlanRunUpdateError,
    StepProgressState,
)
from iris.plan_step_execution_progress_advancement_post_recording_composition import (
    PlanStepExecutionProgressAdvancementPostRecordingComposer as Composer,
)
from iris.plan_step_execution_progress_advancement_post_recording_composition import (
    PlanStepExecutionProgressAdvancementPostRecordingCompositionInvariantError as Invariant,
)
from iris.plan_step_execution_progress_advancement_post_recording_composition import (
    PlanStepExecutionProgressAdvancementPostRecordingCompositionResult as Result,
)
from iris.plan_step_execution_progress_update_post_recording_composition import (
    PlanStepExecutionProgressUpdatePostRecordingComposer as Upstream,
)
from iris.plan_step_execution_progress_update_post_recording_composition import (
    PlanStepExecutionProgressUpdatePostRecordingCompositionResult as UpstreamResult,
)
from tests.test_plan_step_execution_binding_post_recording_composition import operands
from tests.test_plan_step_execution_evidence_assessment_composition import unsafe_clone
from tests.test_plan_step_execution_progress_update_post_recording_composition import (
    RecordingSynthesizer,
    RecordingWP052,
    scenario,
)
from tests.test_plan_step_execution_progress_update_post_recording_composition import (
    invoke as invoke_wp053,
)


class RecordingWP053(Upstream):
    def __init__(
        self,
        result: Any = None,
        *,
        error: Exception | None = None,
        delegate: Upstream | None = None,
    ) -> None:
        super().__init__(transition_decision_composer=RecordingWP052())
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


class RecordingAdvancer(PlanRunProgressAdvancer):
    def __init__(self, *, forced: Any = None, error: Exception | None = None) -> None:
        super().__init__()
        self.forced = forced
        self.error = error
        self.calls: list[tuple[Any, Any, Any]] = []
        self.results: list[Any] = []

    def advance(self, plan: Any, run: Any, update: Any) -> Any:
        self.calls.append((plan, run, update))
        if self.error is not None:
            raise self.error
        result = (
            super().advance(plan, run, update) if self.forced is None else self.forced
        )
        self.results.append(result)
        return result


def canonical(
    *,
    status: StepOutcomeStatus = StepOutcomeStatus.SATISFIED,
    unavailable: bool = False,
    absent: bool = False,
) -> tuple[Any, Any, UpstreamResult]:
    plan, run, wp052 = (
        scenario(status=status, unavailable=unavailable, handling=None)
        if absent
        else scenario(status=status, unavailable=unavailable)
    )
    synthesizer = None if absent or unavailable else RecordingSynthesizer(wp052)
    wp053, _ = invoke_wp053(plan, run, wp052, synthesizer)
    return plan, run, wp053


def invoke(
    plan: Any,
    run: Any,
    upstream_result: Any,
    advancer: RecordingAdvancer | None = None,
    **overrides: Any,
) -> tuple[Result, RecordingWP053, RecordingAdvancer]:
    upstream = RecordingWP053(upstream_result)
    selected_advancer = advancer or RecordingAdvancer()
    kwargs = (
        operands(upstream_result) if isinstance(upstream_result, UpstreamResult) else {}
    )
    kwargs.update(overrides)
    result = Composer(
        progress_update_composer=upstream,
        progress_advancer=selected_advancer,
    ).compose(plan, run, "a", **kwargs)
    return result, upstream, selected_advancer


def test_public_contract() -> None:
    assert api.__all__ == [
        "PlanStepExecutionProgressAdvancementPostRecordingComposer",
        "PlanStepExecutionProgressAdvancementPostRecordingCompositionResult",
        "PlanStepExecutionProgressAdvancementPostRecordingCompositionError",
        "PlanStepExecutionProgressAdvancementPostRecordingCompositionInvariantError",
    ]
    assert issubclass(
        Invariant, api.PlanStepExecutionProgressAdvancementPostRecordingCompositionError
    )
    assert issubclass(Result, UpstreamResult)
    assert (
        inspect.signature(Composer.compose).parameters
        == inspect.signature(Upstream.compose).parameters
    )
    assert list(inspect.signature(Composer).parameters) == [
        "progress_update_composer",
        "progress_advancer",
    ]
    with pytest.raises(TypeError):
        Composer(progress_update_composer=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Composer(progress_update_composer=RecordingWP053(), progress_advancer=object())  # type: ignore[arg-type]


@pytest.mark.parametrize("branch", ["absent", "no_transition", "handler_unavailable"])
def test_no_step_c_update_skips_advancement(branch: str) -> None:
    plan, run, wp053 = canonical(
        absent=branch == "absent",
        unavailable=branch == "handler_unavailable",
        status=StepOutcomeStatus.INDETERMINATE
        if branch == "no_transition"
        else StepOutcomeStatus.SATISFIED,
    )
    result, upstream, advancer = invoke(plan, run, wp053)
    assert len(upstream.calls) == 1
    assert advancer.calls == []
    assert result.post_recording_execution_progress_update is None
    assert result.post_recording_execution_advancement_result is None
    for item in fields(UpstreamResult):
        assert getattr(result, item.name) is getattr(wp053, item.name)


def test_exact_forwarding_and_successor_integrity() -> None:
    plan, run, wp053 = canonical()
    kwargs = operands(wp053)
    result, upstream, advancer = invoke(plan, run, wp053, **kwargs)
    assert len(upstream.calls) == 1
    args, forwarded = upstream.calls[0]
    assert args == (plan, run, "a")
    assert forwarded.keys() == kwargs.keys()
    assert all(forwarded[key] is value for key, value in kwargs.items())
    recording = wp053.post_recording_execution_recording_result
    update = wp053.post_recording_execution_progress_update
    assert recording is not None and update is not None
    assert len(advancer.calls) == 1
    assert advancer.calls[0][0] is plan
    assert advancer.calls[0][1] is recording.recorded_run
    assert advancer.calls[0][2] is update
    advancement = result.post_recording_execution_advancement_result
    assert advancement is advancer.results[0]
    assert advancement.source_update_id == update.update_id
    assert advancement.source_revision == recording.recorded_run.revision
    successor = advancement.updated_run
    assert successor.revision == recording.recorded_run.revision + 1
    assert successor.plan_id == plan.plan_id
    assert successor.run_id == recording.recorded_run.run_id
    assert successor.goal_id == recording.recorded_run.goal_id
    assert successor.created_at == recording.recorded_run.created_at
    assert successor.updated_at == update.updated_at
    assert run.revision < recording.recorded_run.revision < successor.revision
    assert successor.observations == recording.recorded_run.observations
    assert successor.blockers == recording.recorded_run.blockers
    target = next(
        item for item in successor.step_progress if item.step_id == update.step_id
    )
    assert target.state is update.new_state is StepProgressState.SUCCEEDED
    assert target.changed_at == update.updated_at
    assert target.evidence_ids == update.evidence_ids
    assert advancement.control_decision.observed_revision == successor.revision
    for item in fields(UpstreamResult):
        assert getattr(result, item.name) is getattr(wp053, item.name)
    with pytest.raises(FrozenInstanceError):
        result.post_recording_execution_advancement_result = None  # type: ignore[misc]
    assert "__dict__" not in Result.__slots__
    data = result.to_data()
    assert all(data[key] == value for key, value in wp053.to_data().items())
    assert data["post_recording_execution_advancement_result"] == advancement.to_data()
    assert json.loads(json.dumps(data, sort_keys=True)) == data


def test_result_presence_invariant_and_independent_calls() -> None:
    plan, run, wp053 = canonical()
    upstream = RecordingWP053(wp053)
    advancer = RecordingAdvancer()
    composer = Composer(progress_update_composer=upstream, progress_advancer=advancer)
    first = composer.compose(plan, run, "a", **operands(wp053))
    second = composer.compose(plan, run, "a", **operands(wp053))
    assert len(upstream.calls) == len(advancer.calls) == 2
    assert first.post_recording_execution_advancement_result is advancer.results[0]
    assert second.post_recording_execution_advancement_result is advancer.results[1]
    with pytest.raises(Invariant):
        replace(first, post_recording_execution_advancement_result=None)

    absent_plan, absent_run, absent = canonical(absent=True)
    absent_result, _, _ = invoke(absent_plan, absent_run, absent)
    with pytest.raises(Invariant):
        replace(
            absent_result,
            post_recording_execution_advancement_result=(
                first.post_recording_execution_advancement_result
            ),
        )


def test_lazy_unreachable_input_is_forwarded() -> None:
    plan, run, wp052 = scenario(handling=None)
    actual_wp053 = Upstream(transition_decision_composer=RecordingWP052(wp052))
    upstream = RecordingWP053(delegate=actual_wp053)
    advancer = RecordingAdvancer()
    marker = object()
    kwargs = operands(wp052)
    kwargs["post_recording_execution_input"] = marker
    output = Composer(
        progress_update_composer=upstream, progress_advancer=advancer
    ).compose(plan, run, "a", **kwargs)
    assert len(upstream.calls) == 1
    assert upstream.calls[0][1]["post_recording_execution_input"] is marker
    assert output.post_recording_execution_advancement_result is None
    assert advancer.calls == []


@pytest.mark.parametrize(
    ("kind", "reason", "candidates", "selected", "active"),
    [
        (
            ControlDecisionKind.STEP_SELECTED,
            ControlReason.ONLY_READY_STEP,
            ("b",),
            "b",
            (),
        ),
        (
            ControlDecisionKind.ACTIVE_WORK_PENDING,
            ControlReason.ACTIVE_STEP_EXISTS,
            (),
            None,
            ("b",),
        ),
        (
            ControlDecisionKind.SELECTION_UNRESOLVED,
            ControlReason.MULTIPLE_READY_UNRESOLVED,
            ("a", "b"),
            None,
            (),
        ),
        (
            ControlDecisionKind.RUN_CANNOT_ADVANCE,
            ControlReason.RUN_CANNOT_ADVANCE,
            (),
            None,
            (),
        ),
        (
            ControlDecisionKind.RUN_STRUCTURALLY_COMPLETE,
            ControlReason.RUN_STRUCTURALLY_COMPLETE,
            (),
            None,
            (),
        ),
    ],
)
def test_structurally_valid_control_kinds_are_preserved(
    kind: ControlDecisionKind,
    reason: ControlReason,
    candidates: tuple[str, ...],
    selected: str | None,
    active: tuple[str, ...],
) -> None:
    # These are domain-valid defensive returns, not claims of reachability for
    # every kind from this particular canonical successor Run.
    plan, run, wp053 = canonical()
    recording = wp053.post_recording_execution_recording_result
    update = wp053.post_recording_execution_progress_update
    assert recording is not None and update is not None
    base = PlanRunProgressAdvancer().advance(plan, recording.recorded_run, update)
    control = ControlDecision(
        plan_id=plan.plan_id,
        run_id=base.updated_run.run_id,
        observed_revision=base.updated_run.revision,
        kind=kind,
        reason=reason,
        provenance=base.control_decision.provenance,
        candidate_step_ids=candidates,
        selected_step_id=selected,
        active_step_ids=active,
    )
    forced = unsafe_clone(base, control_decision=control)
    output, _, _ = invoke(plan, run, wp053, RecordingAdvancer(forced=forced))
    assert output.post_recording_execution_advancement_result is forced
    assert (
        output.post_recording_execution_advancement_result.control_decision is control
    )


@pytest.mark.parametrize(
    "change",
    [
        "wrong_type",
        "missing_recording",
        "wrong_revision",
        "wrong_update",
        "wrong_source",
    ],
)
def test_malformed_wp053_fails_before_wp023(change: str) -> None:
    plan, run, wp053 = canonical()
    recording = wp053.post_recording_execution_recording_result
    update = wp053.post_recording_execution_progress_update
    assert recording is not None and update is not None
    malformed: Any = {
        "wrong_type": object(),
        "missing_recording": unsafe_clone(
            wp053, post_recording_execution_recording_result=None
        ),
        "wrong_revision": unsafe_clone(
            wp053,
            post_recording_execution_progress_update=unsafe_clone(
                update, expected_revision=update.expected_revision + 1
            ),
        ),
        "wrong_update": unsafe_clone(
            wp053,
            post_recording_execution_progress_update=unsafe_clone(
                update, step_id="foreign"
            ),
        ),
        "wrong_source": unsafe_clone(
            wp053, assessment=unsafe_clone(wp053.assessment, plan_id="foreign")
        ),
    }[change]
    advancer = RecordingAdvancer()
    with pytest.raises(Invariant):
        invoke(plan, run, malformed, advancer, **operands(wp053))
    assert advancer.calls == []


@pytest.mark.parametrize(
    "change",
    [
        "wrong_type",
        "source_update",
        "source_revision",
        "plan",
        "run",
        "goal",
        "revision",
        "created_at",
        "updated_at",
        "observations",
        "observation_replaced",
        "blockers",
        "target",
        "target_time",
        "target_evidence",
        "foreign_progress",
        "unrelated_progress",
        "noncanonical_progress",
        "control_plan",
        "control_run",
        "control_revision",
        "control_kind",
        "control_provenance",
    ],
)
def test_malformed_wp023_return_fails_closed(change: str) -> None:
    plan, run, wp053 = canonical()
    recording = wp053.post_recording_execution_recording_result
    update = wp053.post_recording_execution_progress_update
    assert recording is not None and update is not None
    base = PlanRunProgressAdvancer().advance(plan, recording.recorded_run, update)
    successor = base.updated_run
    target = next(
        item for item in successor.step_progress if item.step_id == update.step_id
    )
    unrelated = next(
        item for item in successor.step_progress if item.step_id != update.step_id
    )
    variants: dict[str, Any] = {
        "wrong_type": object(),
        "source_update": unsafe_clone(base, source_update_id="foreign"),
        "source_revision": unsafe_clone(base, source_revision=base.source_revision + 1),
        "plan": unsafe_clone(
            base, updated_run=unsafe_clone(successor, plan_id="foreign")
        ),
        "run": unsafe_clone(
            base, updated_run=unsafe_clone(successor, run_id="foreign")
        ),
        "goal": unsafe_clone(
            base, updated_run=unsafe_clone(successor, goal_id="foreign")
        ),
        "revision": unsafe_clone(
            base, updated_run=unsafe_clone(successor, revision=successor.revision + 1)
        ),
        "created_at": unsafe_clone(
            base,
            updated_run=unsafe_clone(
                successor, created_at=successor.created_at - timedelta(seconds=1)
            ),
        ),
        "updated_at": unsafe_clone(
            base,
            updated_run=unsafe_clone(
                successor, updated_at=successor.updated_at + timedelta(seconds=1)
            ),
        ),
        "observations": unsafe_clone(
            base, updated_run=unsafe_clone(successor, observations=())
        ),
        "observation_replaced": unsafe_clone(
            base,
            updated_run=unsafe_clone(
                successor,
                observations=(unsafe_clone(successor.observations[0]),)
                + successor.observations[1:],
            ),
        ),
        "blockers": unsafe_clone(
            base, updated_run=unsafe_clone(successor, blockers=(object(),))
        ),
        "target": unsafe_clone(
            base,
            updated_run=unsafe_clone(
                successor,
                step_progress=tuple(
                    unsafe_clone(item, state=StepProgressState.ACTIVE)
                    if item.step_id == update.step_id
                    else item
                    for item in successor.step_progress
                ),
            ),
        ),
        "target_time": unsafe_clone(
            base,
            updated_run=unsafe_clone(
                successor,
                step_progress=tuple(
                    unsafe_clone(
                        item, changed_at=item.changed_at - timedelta(seconds=1)
                    )
                    if item is target
                    else item
                    for item in successor.step_progress
                ),
            ),
        ),
        "target_evidence": unsafe_clone(
            base,
            updated_run=unsafe_clone(
                successor,
                step_progress=tuple(
                    unsafe_clone(item, evidence_ids=("foreign-evidence",))
                    if item is target
                    else item
                    for item in successor.step_progress
                ),
            ),
        ),
        "foreign_progress": unsafe_clone(
            base,
            updated_run=unsafe_clone(
                successor,
                step_progress=tuple(
                    unsafe_clone(item, step_id="foreign")
                    if item.step_id == update.step_id
                    else item
                    for item in successor.step_progress
                ),
            ),
        ),
        "unrelated_progress": unsafe_clone(
            base,
            updated_run=unsafe_clone(
                successor,
                step_progress=tuple(
                    unsafe_clone(
                        item, changed_at=item.changed_at + timedelta(seconds=1)
                    )
                    if item is unrelated
                    else item
                    for item in successor.step_progress
                ),
            ),
        ),
        "noncanonical_progress": unsafe_clone(
            base,
            updated_run=unsafe_clone(
                successor,
                step_progress=tuple(
                    unsafe_clone(item, evidence_ids=[*item.evidence_ids])
                    if item is target
                    else item
                    for item in successor.step_progress
                ),
            ),
        ),
        "control_plan": unsafe_clone(
            base,
            control_decision=unsafe_clone(base.control_decision, plan_id="foreign"),
        ),
        "control_run": unsafe_clone(
            base, control_decision=unsafe_clone(base.control_decision, run_id="foreign")
        ),
        "control_revision": unsafe_clone(
            base,
            control_decision=unsafe_clone(
                base.control_decision,
                observed_revision=base.control_decision.observed_revision - 1,
            ),
        ),
        "control_kind": unsafe_clone(
            base, control_decision=unsafe_clone(base.control_decision, kind="foreign")
        ),
        "control_provenance": unsafe_clone(
            base,
            control_decision=unsafe_clone(
                base.control_decision,
                provenance=unsafe_clone(
                    base.control_decision.provenance, controller_id=""
                ),
            ),
        ),
    }
    advancer = RecordingAdvancer(forced=variants[change])
    with pytest.raises(Invariant):
        invoke(plan, run, wp053, advancer)
    assert len(advancer.calls) == 1


def test_errors_propagate_without_retry() -> None:
    plan, run, wp053 = canonical()
    error = RuntimeError("WP053 failed")
    upstream = RecordingWP053(error=error)
    advancer = RecordingAdvancer()
    with pytest.raises(RuntimeError) as raised:
        Composer(progress_update_composer=upstream, progress_advancer=advancer).compose(
            plan, run, "a", **operands(wp053)
        )
    assert raised.value is error
    assert len(upstream.calls) == 1 and advancer.calls == []

    error = RuntimeError("WP023 failed")
    advancer = RecordingAdvancer(error=error)
    with pytest.raises(RuntimeError) as raised:
        invoke(plan, run, wp053, advancer)
    assert raised.value is error
    assert len(advancer.calls) == 1


@pytest.mark.parametrize(
    "error_type",
    [StalePlanRunUpdateError, InvalidStepTransitionError, ForeignEvidenceError],
)
def test_canonical_wp023_errors_propagate_unchanged(
    error_type: type[Exception],
) -> None:
    plan, run, wp053 = canonical()
    error = error_type("canonical WP023 rejection")
    advancer = RecordingAdvancer(error=error)
    with pytest.raises(error_type) as raised:
        invoke(plan, run, wp053, advancer)
    assert raised.value is error
    assert len(advancer.calls) == 1


def test_no_forbidden_authority_imports_or_calls() -> None:
    package = Path(api.__file__).parent
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = [
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        ]
        assert not any(
            "reducer" in name or "execution_coordinator" in name for name in imports
        )
        names = {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        assert "synthesize" not in names
        assert "decide" not in names
        assert "apply" not in names
