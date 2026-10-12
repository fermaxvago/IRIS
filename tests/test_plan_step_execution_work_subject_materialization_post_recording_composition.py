"""WP056: materialize one exact successor identity and stop."""

from __future__ import annotations

import ast
import inspect
import json
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
from typing import Any, cast

import pytest

import iris.plan_step_execution_work_subject_materialization_post_recording_composition as api
from iris.orchestrator import HandlingKind
from iris.plan_control import ControlDecisionKind
from iris.plan_handling import StepHandlingPreparationStatus
from iris.plan_runs import PlanRun
from iris.plan_step_execution_handling_preparation_post_recording_composition import (
    PlanStepExecutionHandlingPreparationPostRecordingComposer as Upstream,
)
from iris.plan_step_execution_handling_preparation_post_recording_composition import (
    PlanStepExecutionHandlingPreparationPostRecordingCompositionInvariantError as UpstreamInvariant,
)
from iris.plan_step_execution_handling_preparation_post_recording_composition import (
    PlanStepExecutionHandlingPreparationPostRecordingCompositionResult as UpstreamResult,
)
from iris.plan_step_execution_progress_advancement_post_recording_composition import (
    PlanStepExecutionProgressAdvancementPostRecordingComposer as WP054,
)
from iris.planning import Plan
from iris.work_identity import (
    PlanStepWorkReference,
    RequestWorkReference,
    WorkOrigin,
    WorkSubject,
    WorkSubjectKind,
    work_subject_from_plan_step,
)
from tests.test_plan_step_execution_binding_post_recording_composition import operands
from tests.test_plan_step_execution_evidence_assessment_composition import unsafe_clone
from tests.test_plan_step_execution_handling_preparation_post_recording_composition import (
    RecordingWP054,
    canonical_wp054,
)
from tests.test_plan_step_execution_handling_preparation_post_recording_composition import (
    invoke as invoke_wp055,
)
from tests.test_plan_step_execution_progress_advancement_composition import (
    decision_for_kind,
)
from tests.test_plan_step_execution_progress_advancement_post_recording_composition import (
    RecordingWP053,
)
from tests.test_plan_step_execution_progress_advancement_post_recording_composition import (
    canonical as canonical_wp054_base,
)
from tests.test_plan_step_execution_progress_advancement_post_recording_composition import (
    invoke as invoke_wp054,
)

Composer = api.PlanStepExecutionWorkSubjectMaterializationPostRecordingComposer
Result = api.PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionResult
Invariant = api.PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionInvariantError


class RecordingWP055(Upstream):
    def __init__(
        self,
        result: object = None,
        *,
        error: Exception | None = None,
        delegate: Upstream | None = None,
    ) -> None:
        super().__init__(progress_advancement_composer=RecordingWP054())
        self.result = result
        self.error = error
        self.delegate = delegate
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def compose(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        if self.delegate is not None:
            return self.delegate.compose(*args, **kwargs)
        return self.result


class RecordingAdapter:
    def __init__(
        self, *, forced: object = None, error: Exception | None = None
    ) -> None:
        self.forced = forced
        self.error = error
        self.calls: list[tuple[Plan, PlanRun, str]] = []
        self.results: list[WorkSubject] = []

    def __call__(self, plan: Plan, run: PlanRun, step_id: str) -> WorkSubject:
        self.calls.append((plan, run, step_id))
        if self.error is not None:
            raise self.error
        result = (
            work_subject_from_plan_step(plan, run, step_id)
            if self.forced is None
            else cast(WorkSubject, self.forced)
        )
        self.results.append(result)
        return result


def selected(
    handling: HandlingKind | None = HandlingKind.CAPABILITY,
) -> tuple[Plan, PlanRun, UpstreamResult]:
    plan, run, wp054 = canonical_wp054(selected_handling=handling)
    wp055, _, _ = invoke_wp055(plan, run, wp054)
    assert wp055.post_recording_execution_handling_preparation is not None
    return plan, run, wp055


def invoke(
    plan: Plan,
    run: PlanRun,
    delegated: object,
    *,
    adapter: RecordingAdapter | None = None,
    **overrides: object,
) -> tuple[Result, RecordingWP055, RecordingAdapter]:
    upstream = RecordingWP055(delegated)
    selected_adapter = adapter or RecordingAdapter()
    kwargs = operands(delegated) if isinstance(delegated, UpstreamResult) else {}
    kwargs.update(overrides)
    result = Composer(
        handling_preparation_composer=upstream,
        work_subject_adapter=selected_adapter,
    ).compose(plan, run, "a", **kwargs)
    return result, upstream, selected_adapter


def result_from(upstream: UpstreamResult, subject: WorkSubject | None) -> Result:
    return Result(
        **{item.name: getattr(upstream, item.name) for item in fields(UpstreamResult)},
        post_recording_execution_work_subject=subject,
    )


def test_public_contract() -> None:
    assert api.__all__ == [
        "PlanStepExecutionWorkSubjectMaterializationPostRecordingComposer",
        "PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionResult",
        "PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionError",
        "PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionInvariantError",
    ]
    assert issubclass(Result, UpstreamResult)
    assert issubclass(
        Invariant,
        api.PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionError,
    )
    assert (
        inspect.signature(Composer.compose).parameters
        == inspect.signature(Upstream.compose).parameters
    )
    assert list(inspect.signature(Composer).parameters) == [
        "handling_preparation_composer",
        "work_subject_adapter",
    ]
    with pytest.raises(TypeError):
        Composer(handling_preparation_composer=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Composer(
            handling_preparation_composer=RecordingWP055(),
            work_subject_adapter=object(),  # type: ignore[arg-type]
        )


def test_absent_advancement_skips_adapter_and_preserves_all_fields() -> None:
    plan, run, wp053 = canonical_wp054_base(absent=True)
    wp054, _, _ = invoke_wp054(plan, run, wp053)
    wp055, _, _ = invoke_wp055(plan, run, wp054)
    result, upstream, adapter = invoke(plan, run, wp055)
    assert len(upstream.calls) == 1
    assert adapter.calls == []
    assert result.post_recording_execution_work_subject is None
    for item in fields(UpstreamResult):
        assert getattr(result, item.name) is getattr(wp055, item.name)
    assert result.to_data()["post_recording_execution_work_subject"] is None


@pytest.mark.parametrize(
    "kind",
    [
        ControlDecisionKind.ACTIVE_WORK_PENDING,
        ControlDecisionKind.SELECTION_UNRESOLVED,
        ControlDecisionKind.RUN_CANNOT_ADVANCE,
        ControlDecisionKind.RUN_STRUCTURALLY_COMPLETE,
    ],
)
def test_nonselected_control_skips_adapter(kind: ControlDecisionKind) -> None:
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
    result, upstream, adapter = invoke(plan, run, wp055)
    assert len(upstream.calls) == 1
    assert adapter.calls == []
    assert result.post_recording_execution_work_subject is None
    assert result.post_recording_execution_advancement_result is (
        wp055.post_recording_execution_advancement_result
    )


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
def test_selected_materializes_regardless_of_preparation_status(
    handling: HandlingKind | None, status: StepHandlingPreparationStatus
) -> None:
    plan, run, wp055 = selected(handling)
    kwargs = operands(wp055)
    upstream = RecordingWP055(wp055)
    adapter = RecordingAdapter()
    result = Composer(
        handling_preparation_composer=upstream,
        work_subject_adapter=adapter,
    ).compose(plan, run, "a", **kwargs)
    advancement = wp055.post_recording_execution_advancement_result
    assert advancement is not None
    assert len(upstream.calls) == len(adapter.calls) == 1
    args, forwarded = upstream.calls[0]
    assert args == (plan, run, "a")
    assert forwarded.keys() == kwargs.keys()
    assert all(forwarded[key] is value for key, value in kwargs.items())
    assert adapter.calls[0][0] is plan
    assert adapter.calls[0][1] is advancement.updated_run
    assert adapter.calls[0][2] == advancement.control_decision.selected_step_id == "d"
    subject = result.post_recording_execution_work_subject
    assert subject is adapter.results[0]
    assert subject.kind is WorkSubjectKind.PLAN_STEP
    assert isinstance(subject.reference, PlanStepWorkReference)
    assert subject.reference.plan_id == plan.plan_id
    assert subject.reference.run_id == advancement.updated_run.run_id
    assert subject.reference.step_id == "d"
    assert subject.origin is None
    assert subject is not result.work_subject
    assert subject is not result.post_recording_work_subject
    assert result.post_recording_execution_handling_preparation.status is status
    for item in fields(UpstreamResult):
        assert getattr(result, item.name) is getattr(wp055, item.name)
    with pytest.raises(FrozenInstanceError):
        result.post_recording_execution_work_subject = None  # type: ignore[misc]
    assert "__dict__" not in Result.__slots__
    data = result.to_data()
    assert all(data[key] == value for key, value in wp055.to_data().items())
    assert data["post_recording_execution_work_subject"] == subject.to_data()
    assert json.loads(json.dumps(data, sort_keys=True)) == data
    assert result.to_data() == data


def test_default_adapter_and_stable_identity_ignore_revision() -> None:
    plan, run, wp055 = selected()
    output = Composer(handling_preparation_composer=RecordingWP055(wp055)).compose(
        plan, run, "a", **operands(wp055)
    )
    advancement = wp055.post_recording_execution_advancement_result
    assert advancement is not None
    subject = output.post_recording_execution_work_subject
    assert subject is not None
    earlier_revision_subject = work_subject_from_plan_step(
        plan, run, advancement.control_decision.selected_step_id or ""
    )
    assert subject is not earlier_revision_subject
    assert subject.subject_id == earlier_revision_subject.subject_id
    assert subject.reference.to_data().keys() == {"plan_id", "run_id", "step_id"}


@pytest.mark.parametrize(
    "change",
    [
        "wrong_type",
        "foreign_plan",
        "foreign_run",
        "wrong_processed_step",
        "missing_preparation",
        "stale_preparation",
        "stale_control",
        "wrong_advancement_revision",
        "missing_recording",
        "corrupt_inherited",
    ],
)
def test_malformed_upstream_fails_before_adapter(change: str) -> None:
    plan, run, wp055 = selected()
    advancement = wp055.post_recording_execution_advancement_result
    preparation = wp055.post_recording_execution_handling_preparation
    assert advancement is not None and preparation is not None
    variants: dict[str, object] = {
        "wrong_type": object(),
        "foreign_plan": unsafe_clone(
            wp055, assessment=unsafe_clone(wp055.assessment, plan_id="foreign")
        ),
        "foreign_run": unsafe_clone(
            wp055, assessment=unsafe_clone(wp055.assessment, run_id="foreign")
        ),
        "missing_preparation": unsafe_clone(
            wp055, post_recording_execution_handling_preparation=None
        ),
        "stale_preparation": unsafe_clone(
            wp055,
            post_recording_execution_handling_preparation=unsafe_clone(
                preparation, observed_revision=preparation.observed_revision - 1
            ),
        ),
        "stale_control": unsafe_clone(
            wp055,
            post_recording_execution_advancement_result=unsafe_clone(
                advancement,
                control_decision=unsafe_clone(
                    advancement.control_decision,
                    observed_revision=advancement.control_decision.observed_revision
                    - 1,
                ),
            ),
        ),
        "wrong_advancement_revision": unsafe_clone(
            wp055,
            post_recording_execution_advancement_result=unsafe_clone(
                advancement, source_revision=advancement.source_revision + 1
            ),
        ),
        "missing_recording": unsafe_clone(
            wp055, post_recording_execution_recording_result=None
        ),
        "corrupt_inherited": unsafe_clone(
            wp055,
            post_recording_execution_progress_update=unsafe_clone(
                wp055.post_recording_execution_progress_update, expected_revision=-1
            ),
        ),
    }
    delegated = variants.get(change, wp055)
    upstream = RecordingWP055(delegated)
    adapter = RecordingAdapter()
    with pytest.raises(Invariant):
        Composer(
            handling_preparation_composer=upstream, work_subject_adapter=adapter
        ).compose(
            plan,
            run,
            "foreign" if change == "wrong_processed_step" else "a",
            **operands(wp055),
        )
    assert len(upstream.calls) == 1
    assert adapter.calls == []


@pytest.mark.parametrize(
    "change",
    [
        "wrong_type",
        "wrong_kind",
        "wrong_reference_type",
        "foreign_plan",
        "foreign_run",
        "wrong_step",
        "non_none_origin",
        "forged_subject_id",
        "invalid_reference",
    ],
)
def test_malformed_adapter_return_fails_closed(change: str) -> None:
    plan, run, wp055 = selected()
    advancement = wp055.post_recording_execution_advancement_result
    assert advancement is not None
    canonical = work_subject_from_plan_step(plan, advancement.updated_run, "d")
    reference = canonical.reference
    assert isinstance(reference, PlanStepWorkReference)
    variants: dict[str, object] = {
        "wrong_type": object(),
        "wrong_kind": unsafe_clone(canonical, kind=WorkSubjectKind.REQUEST),
        "wrong_reference_type": unsafe_clone(
            canonical, reference=RequestWorkReference("request-x")
        ),
        "foreign_plan": unsafe_clone(
            canonical, reference=replace(reference, plan_id="foreign")
        ),
        "foreign_run": unsafe_clone(
            canonical, reference=replace(reference, run_id="foreign")
        ),
        "wrong_step": unsafe_clone(
            canonical, reference=replace(reference, step_id="c")
        ),
        "non_none_origin": unsafe_clone(
            canonical, origin=WorkOrigin("request", "root")
        ),
        "forged_subject_id": unsafe_clone(canonical, subject_id="forged"),
        "invalid_reference": unsafe_clone(
            canonical, reference=unsafe_clone(reference, step_id=" ")
        ),
    }
    adapter = RecordingAdapter(forced=variants[change])
    with pytest.raises(Invariant):
        invoke(plan, run, wp055, adapter=adapter)
    assert len(adapter.calls) == 1


def test_direct_result_presence_and_alias_invariants() -> None:
    plan, run, wp055 = selected()
    with pytest.raises(Invariant):
        result_from(wp055, None)
    with pytest.raises(Invariant):
        result_from(wp055, wp055.post_recording_work_subject)
    result, _, _ = invoke(plan, run, wp055)
    assert result.post_recording_execution_work_subject is not None
    with pytest.raises(UpstreamInvariant):
        result_from(
            unsafe_clone(wp055, post_recording_execution_handling_preparation=None),
            result.post_recording_execution_work_subject,
        )


def test_errors_and_repeated_invocations() -> None:
    plan, run, wp055 = selected()
    error = RuntimeError("upstream failure")
    upstream = RecordingWP055(error=error)
    adapter = RecordingAdapter()
    composer = Composer(
        handling_preparation_composer=upstream, work_subject_adapter=adapter
    )
    with pytest.raises(RuntimeError) as caught:
        composer.compose(plan, run, "a", **operands(wp055))
    assert caught.value is error
    assert len(upstream.calls) == 1 and adapter.calls == []

    adapter_error = ValueError("identity failed")
    bad_adapter = RecordingAdapter(error=adapter_error)
    with pytest.raises(Invariant) as caught:
        invoke(plan, run, wp055, adapter=bad_adapter)
    assert caught.value.__cause__ is adapter_error
    assert len(bad_adapter.calls) == 1

    good_upstream = RecordingWP055(wp055)
    good_adapter = RecordingAdapter()
    good_composer = Composer(
        handling_preparation_composer=good_upstream,
        work_subject_adapter=good_adapter,
    )
    first = good_composer.compose(plan, run, "a", **operands(wp055))
    second = good_composer.compose(plan, run, "a", **operands(wp055))
    assert len(good_upstream.calls) == len(good_adapter.calls) == 2
    assert (
        first.post_recording_execution_work_subject
        is not second.post_recording_execution_work_subject
    )
    assert (
        first.post_recording_execution_work_subject
        == second.post_recording_execution_work_subject
    )


def test_unreachable_input_remains_lazily_unvalidated() -> None:
    plan, run, wp053 = canonical_wp054_base(absent=True)
    actual_wp054 = WP054(progress_update_composer=RecordingWP053(wp053))
    actual_wp055 = Upstream(progress_advancement_composer=actual_wp054)
    upstream = RecordingWP055(delegate=actual_wp055)
    adapter = RecordingAdapter()
    marker = object()
    kwargs = operands(wp053)
    kwargs["post_recording_execution_input"] = marker
    result = Composer(
        handling_preparation_composer=upstream, work_subject_adapter=adapter
    ).compose(plan, run, "a", **kwargs)
    assert len(upstream.calls) == 1
    assert upstream.calls[0][1]["post_recording_execution_input"] is marker
    assert result.post_recording_execution_work_subject is None
    assert adapter.calls == []


def test_no_forbidden_authority_imports_or_calls() -> None:
    package = Path(api.__file__).parent
    source = (package / "composer.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    forbidden = {
        "PlanRunReducer",
        "PlanRunController",
        "PlanRunProgressAdvancer",
        "PlanStepHandlingPreparer",
        "ContextEngine",
        "Orchestrator",
        "ExecutionCoordinator",
        "PlanStepExecutionStartCoordinator",
    }
    assert not (imports & forbidden)
    assert "for " not in inspect.getsource(Composer.compose)
    assert "while " not in inspect.getsource(Composer.compose)
