"""WP060: exact optional WP024 successor binding and STOP."""

from __future__ import annotations

import ast
import inspect
import json
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from typing import Any, cast

import pytest

import iris.plan_step_execution_successor_binding_post_recording_composition as api
from iris.context import ContextBudget
from iris.execution import (
    CapabilityExecutionInput,
    IntelligenceExecutionInput,
    MemoryExecutionInput,
    SystemExecutionInput,
)
from iris.orchestrator import HandlerAvailability, HandlingKind, OrchestrationTarget
from iris.plan_runs import StepProgressState
from iris.plan_step_execution_binding import (
    PlanStepExecutionBinder,
    PlanStepExecutionBinding,
    StalePlanStepExecutionBindingError,
)
from iris.plan_step_execution_request_materialization_post_recording_composition import (
    PlanStepExecutionRequestMaterializationPostRecordingComposer as Upstream,
)
from iris.plan_step_execution_request_materialization_post_recording_composition import (
    PlanStepExecutionRequestMaterializationPostRecordingCompositionResult as UpstreamResult,
)
from tests.test_plan_step_execution_binding_post_recording_composition import operands
from tests.test_plan_step_execution_context_materialization_post_recording_composition import (
    CONTEXT_TIME,
)
from tests.test_plan_step_execution_evidence_assessment_composition import unsafe_clone
from tests.test_plan_step_execution_orchestration_post_recording_composition import (
    absent as wp058_absent,
)
from tests.test_plan_step_execution_orchestration_post_recording_composition import (
    canonical as wp058_canonical,
)
from tests.test_plan_step_execution_orchestration_post_recording_composition import (
    compose as compose_wp058,
)
from tests.test_plan_step_execution_request_materialization_post_recording_composition import (
    RecordingWP058,
    operational_variant,
)
from tests.test_plan_step_execution_request_materialization_post_recording_composition import (
    call as call_wp059,
)

Composer = api.PlanStepExecutionSuccessorBindingPostRecordingComposer
Result = api.PlanStepExecutionSuccessorBindingPostRecordingCompositionResult
Invariant = api.PlanStepExecutionSuccessorBindingPostRecordingCompositionInvariantError


class RecordingWP059(Upstream):
    def __init__(self, result: object, error: Exception | None = None) -> None:
        super().__init__(orchestration_composer=RecordingWP058(None))
        self.result = result
        self.error = error
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def compose(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return self.result


class RecordingBinder(PlanStepExecutionBinder):
    def __init__(self, forced: object = None, error: Exception | None = None) -> None:
        self.forced = forced
        self.error = error
        self.calls: list[tuple[object, object, object, object, object]] = []

    def bind(
        self,
        plan: Any,
        run: Any,
        control_decision: Any,
        preparation: Any,
        execution_request: Any,
    ) -> PlanStepExecutionBinding:
        self.calls.append((plan, run, control_decision, preparation, execution_request))
        if self.error is not None:
            raise self.error
        if self.forced is not None:
            return cast(PlanStepExecutionBinding, self.forced)
        return super().bind(plan, run, control_decision, preparation, execution_request)


def operational(
    kind: HandlingKind = HandlingKind.CAPABILITY,
) -> tuple[Any, Any, UpstreamResult, HandlerAvailability]:
    plan, run, wp058, availability = operational_variant(kind)
    operand = {
        HandlingKind.SYSTEM: SystemExecutionInput(),
        HandlingKind.MEMORY: MemoryExecutionInput(memory_id="mem-1"),
        HandlingKind.CAPABILITY: CapabilityExecutionInput(),
        HandlingKind.INTELLIGENCE: IntelligenceExecutionInput(
            content="analyze", resources=()
        ),
    }[kind]
    upstream, _ = call_wp059(
        plan,
        run,
        wp058,
        successor_input=operand,
        successor_orchestration_availability=availability,
    )
    return plan, run, upstream, availability


def invoke(
    plan: Any,
    run: Any,
    upstream: object,
    *,
    binder: RecordingBinder | None = None,
    upstream_error: Exception | None = None,
    availability: object = None,
    **overrides: object,
) -> tuple[Result, RecordingWP059, RecordingBinder]:
    wp059 = RecordingWP059(upstream, upstream_error)
    wp024 = binder if binder is not None else RecordingBinder()
    fallback = upstream if isinstance(upstream, UpstreamResult) else operational()[2]
    request = fallback.post_recording_execution_successor_request
    kwargs = operands(fallback)
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
        successor_execution_input=(
            None if request is None else request.execution_input
        ),
    )
    kwargs.update(overrides)
    result = Composer(
        request_materialization_composer=wp059, execution_binder=wp024
    ).compose(plan, run, "a", **kwargs)
    return result, wp059, wp024


def test_public_api_signature_and_constructor() -> None:
    assert api.__all__ == [
        "PlanStepExecutionSuccessorBindingPostRecordingComposer",
        "PlanStepExecutionSuccessorBindingPostRecordingCompositionResult",
        "PlanStepExecutionSuccessorBindingPostRecordingCompositionError",
        "PlanStepExecutionSuccessorBindingPostRecordingCompositionInvariantError",
    ]
    assert issubclass(Result, UpstreamResult)
    assert issubclass(
        Invariant, api.PlanStepExecutionSuccessorBindingPostRecordingCompositionError
    )
    assert inspect.signature(Composer.compose) == inspect.signature(
        Upstream.compose
    ).replace(return_annotation=inspect.signature(Composer.compose).return_annotation)
    with pytest.raises(TypeError):
        Composer(request_materialization_composer=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Composer(
            request_materialization_composer=RecordingWP059(None),
            execution_binder=object(),
        )  # type: ignore[arg-type]
    Composer(request_materialization_composer=RecordingWP059(None))


@pytest.mark.parametrize(
    "kind",
    [
        HandlingKind.SYSTEM,
        HandlingKind.MEMORY,
        HandlingKind.CAPABILITY,
        HandlingKind.INTELLIGENCE,
    ],
)
def test_exact_operational_binding_and_preservation(kind: HandlingKind) -> None:
    plan, run, upstream, availability = operational(kind)
    result, wp059, binder = invoke(plan, run, upstream, availability=availability)
    assert len(wp059.calls) == 1 and len(binder.calls) == 1
    assert wp059.calls[0][0][0] is plan and wp059.calls[0][0][1] is run
    assert wp059.calls[0][0][2] == "a"
    assert (
        wp059.calls[0][1]["successor_execution_input"]
        is upstream.post_recording_execution_successor_request.execution_input
    )
    advancement = upstream.post_recording_execution_advancement_result
    preparation = upstream.post_recording_execution_handling_preparation
    request = upstream.post_recording_execution_successor_request
    assert advancement is not None and preparation is not None and request is not None
    forwarded = binder.calls[0]
    assert forwarded[0] is plan
    assert forwarded[1] is advancement.updated_run
    assert forwarded[2] is advancement.control_decision
    assert forwarded[3] is preparation
    assert forwarded[4] is request
    binding = result.post_recording_execution_successor_binding
    assert isinstance(binding, PlanStepExecutionBinding)
    assert binding.to_data() == {
        "plan_id": advancement.updated_run.plan_id,
        "run_id": advancement.updated_run.run_id,
        "observed_revision": advancement.updated_run.revision,
        "step_id": advancement.control_decision.selected_step_id,
        "execution_id": request.execution_id,
        "subject_id": request.subject.subject_id,
        "orchestration_decision_id": request.decision.decision_id,
        "context_snapshot_id": request.context.snapshot_id,
        "handling_need_id": preparation.handling_need.need_id,
    }
    assert request.decision.target is OrchestrationTarget(kind.value)
    assert all(
        getattr(result, field.name) is getattr(upstream, field.name)
        for field in fields(UpstreamResult)
    )
    assert (
        result.to_data()["post_recording_execution_successor_binding"]
        == binding.to_data()
    )
    assert result.to_data() == result.to_data()
    json.dumps(result.to_data())
    assert run.revision == upstream.assessment.run_revision
    with pytest.raises(FrozenInstanceError):
        result.post_recording_execution_successor_binding = None  # type: ignore[misc]
    assert not hasattr(result, "__dict__")


def test_every_wp059_argument_is_forwarded_by_identity() -> None:
    plan, run, upstream, availability = operational()
    request = upstream.post_recording_execution_successor_request
    assert request is not None
    kwargs = operands(upstream)
    kwargs.update(
        successor_context_candidates=(),
        successor_context_budget=ContextBudget(2),
        successor_context_uncertainties=(),
        successor_context_created_at=CONTEXT_TIME,
        successor_orchestration_availability=availability,
        successor_execution_input=request.execution_input,
    )
    wp059 = RecordingWP059(upstream)
    Composer(request_materialization_composer=wp059).compose(plan, run, "a", **kwargs)
    assert len(wp059.calls) == 1
    forwarded_args, forwarded_kwargs = wp059.calls[0]
    assert forwarded_args[0] is plan and forwarded_args[1] is run
    assert forwarded_args[2] == "a"
    assert forwarded_kwargs.keys() == kwargs.keys()
    assert all(forwarded_kwargs[key] is value for key, value in kwargs.items())


def test_absent_successor_preserves_unreachable_lazy_inputs() -> None:
    plan, run, wp057 = wp058_absent()
    wp058, _, _ = compose_wp058(plan, run, wp057)
    wp059, _ = call_wp059(plan, run, wp058)
    marker = object()
    result, upstream, binder = invoke(
        plan,
        run,
        wp059,
        post_recording_execution_input=marker,
        successor_context_candidates=marker,
        successor_context_budget=marker,
        successor_context_created_at=marker,
        successor_orchestration_availability=marker,
        successor_execution_input=marker,
    )
    assert len(upstream.calls) == 1 and binder.calls == []
    assert upstream.calls[0][1]["successor_execution_input"] is marker
    assert result.post_recording_execution_successor_binding is None


@pytest.mark.parametrize(
    "kind", [None, HandlingKind.SYSTEM, HandlingKind.MEMORY, HandlingKind.INTELLIGENCE]
)
def test_nonprepared_successor_has_no_binding(kind: HandlingKind | None) -> None:
    plan, run, wp057 = wp058_canonical(kind)
    wp058, _, _ = compose_wp058(plan, run, wp057)
    wp059, _ = call_wp059(plan, run, wp058)
    result, _, binder = invoke(
        plan, run, wp059, successor_execution_input=object(), availability=object()
    )
    assert result.post_recording_execution_successor_binding is None
    assert binder.calls == []


def test_real_unsatisfied_decision_abstains() -> None:
    plan, run, wp057 = wp058_canonical()
    wp058, _, _ = compose_wp058(plan, run, wp057, availability=HandlerAvailability())
    wp059, _ = call_wp059(
        plan, run, wp058, successor_orchestration_availability=HandlerAvailability()
    )
    result, _, binder = invoke(
        plan,
        run,
        wp059,
        availability=HandlerAvailability(),
        successor_execution_input=object(),
    )
    assert (
        result.post_recording_execution_orchestration_decision.target
        is OrchestrationTarget.UNSATISFIED
    )
    assert result.post_recording_execution_successor_binding is None
    assert binder.calls == []


@pytest.mark.parametrize(
    ("field_name", "wrong"),
    [
        ("plan_id", "foreign-plan"),
        ("run_id", "foreign-run"),
        ("observed_revision", 8),
        ("step_id", "foreign-step"),
        ("execution_id", "foreign-execution"),
        ("subject_id", "foreign-subject"),
        ("orchestration_decision_id", "foreign-decision"),
        ("context_snapshot_id", "foreign-context"),
        ("handling_need_id", "foreign-need"),
    ],
)
def test_nine_field_forgery_fails_closed(field_name: str, wrong: object) -> None:
    plan, run, upstream, availability = operational()
    advancement = upstream.post_recording_execution_advancement_result
    preparation = upstream.post_recording_execution_handling_preparation
    request = upstream.post_recording_execution_successor_request
    assert advancement is not None and preparation is not None and request is not None
    canonical = PlanStepExecutionBinder().bind(
        plan,
        advancement.updated_run,
        advancement.control_decision,
        preparation,
        request,
    )
    forged = unsafe_clone(canonical, **{field_name: wrong})
    binder = RecordingBinder(forced=forged)
    with pytest.raises(Invariant):
        invoke(plan, run, upstream, availability=availability, binder=binder)
    assert len(binder.calls) == 1
    with pytest.raises(Invariant):
        Result(
            **{
                field.name: getattr(upstream, field.name)
                for field in fields(UpstreamResult)
            },
            post_recording_execution_successor_binding=forged,
        )


def test_wrong_type_and_noncanonical_binding_are_rejected() -> None:
    plan, run, upstream, availability = operational()
    for forced in [
        object(),
        unsafe_clone(
            PlanStepExecutionBinding(
                plan_id="p",
                run_id="r",
                observed_revision=0,
                step_id="s",
                execution_id="e",
                subject_id="sub",
                orchestration_decision_id="d",
                context_snapshot_id="c",
                handling_need_id="n",
            ),
            observed_revision=True,
        ),
    ]:
        binder = RecordingBinder(forced=forced)
        with pytest.raises(Invariant):
            invoke(plan, run, upstream, availability=availability, binder=binder)
        assert len(binder.calls) == 1


def test_earlier_binding_reuse_is_rejected() -> None:
    plan, run, upstream, availability = operational()
    prior = upstream.post_recording_execution_binding
    assert prior is not None
    binder = RecordingBinder(forced=prior)
    with pytest.raises(Invariant):
        invoke(plan, run, upstream, availability=availability, binder=binder)
    assert len(binder.calls) == 1


def test_malformed_wp059_lineage_fails_before_binding() -> None:
    plan, run, upstream, availability = operational()
    for malformed in [
        object(),
        unsafe_clone(upstream, post_recording_execution_successor_request=None),
        unsafe_clone(upstream, post_recording_execution_advancement_result=None),
        unsafe_clone(upstream, post_recording_execution_handling_preparation=None),
        unsafe_clone(upstream, post_recording_execution_work_subject=None),
        unsafe_clone(upstream, post_recording_execution_context_snapshot=None),
    ]:
        binder = RecordingBinder()
        with pytest.raises(Invariant):
            invoke(plan, run, malformed, availability=availability, binder=binder)
        assert binder.calls == []


@pytest.mark.parametrize(
    "state",
    [StepProgressState.ACTIVE, StepProgressState.SUCCEEDED, StepProgressState.FAILED],
)
def test_selected_successor_lifecycle_corruption_fails_before_binding(
    state: StepProgressState,
) -> None:
    plan, run, upstream, availability = operational()
    advancement = upstream.post_recording_execution_advancement_result
    assert advancement is not None
    successor = advancement.updated_run
    altered_progress = tuple(
        unsafe_clone(progress, state=state)
        if progress.step_id == advancement.control_decision.selected_step_id
        else progress
        for progress in successor.step_progress
    )
    forged_run = unsafe_clone(successor, step_progress=altered_progress)
    forged_advancement = unsafe_clone(advancement, updated_run=forged_run)
    forged_upstream = unsafe_clone(
        upstream, post_recording_execution_advancement_result=forged_advancement
    )
    binder = RecordingBinder()
    with pytest.raises(Invariant):
        invoke(plan, run, forged_upstream, availability=availability, binder=binder)
    assert binder.calls == []


def test_stale_or_foreign_successor_lineage_fails_before_binding() -> None:
    plan, run, upstream, availability = operational()
    advancement = upstream.post_recording_execution_advancement_result
    preparation = upstream.post_recording_execution_handling_preparation
    assert advancement is not None and preparation is not None
    forged_cases = [
        unsafe_clone(
            upstream,
            post_recording_execution_advancement_result=unsafe_clone(
                advancement,
                updated_run=unsafe_clone(advancement.updated_run, revision=99),
            ),
        ),
        unsafe_clone(
            upstream,
            post_recording_execution_advancement_result=unsafe_clone(
                advancement,
                updated_run=unsafe_clone(advancement.updated_run, run_id="foreign-run"),
            ),
        ),
        unsafe_clone(
            upstream,
            post_recording_execution_advancement_result=unsafe_clone(
                advancement,
                control_decision=unsafe_clone(
                    advancement.control_decision, selected_step_id="foreign-step"
                ),
            ),
        ),
        unsafe_clone(
            upstream,
            post_recording_execution_advancement_result=unsafe_clone(
                advancement,
                control_decision=unsafe_clone(
                    advancement.control_decision, observed_revision=0
                ),
            ),
        ),
        unsafe_clone(
            upstream,
            post_recording_execution_handling_preparation=unsafe_clone(
                preparation, observed_revision=0
            ),
        ),
    ]
    for forged in forged_cases:
        binder = RecordingBinder()
        with pytest.raises(Invariant):
            invoke(plan, run, forged, availability=availability, binder=binder)
        assert binder.calls == []
    for foreign_plan, foreign_run in [
        (unsafe_clone(plan, plan_id="foreign-plan"), run),
        (plan, unsafe_clone(run, run_id="foreign-run")),
    ]:
        binder = RecordingBinder()
        with pytest.raises(Invariant):
            invoke(
                foreign_plan,
                foreign_run,
                upstream,
                availability=availability,
                binder=binder,
            )
        assert binder.calls == []


def test_clarify_artifact_is_unreachable_and_rejected_upstream() -> None:
    # WP058 PREPARED needs have no blockers; canonical CLARIFY requires references.
    plan, run, upstream, availability = operational()
    decision = upstream.post_recording_execution_orchestration_decision
    assert decision is not None
    forged = unsafe_clone(
        upstream,
        post_recording_execution_orchestration_decision=unsafe_clone(
            decision, target=OrchestrationTarget.CLARIFY
        ),
        post_recording_execution_successor_request=None,
    )
    binder = RecordingBinder()
    with pytest.raises(Invariant):
        invoke(plan, run, forged, availability=availability, binder=binder)
    assert binder.calls == []


def test_input_identity_mismatch_fails_before_binding() -> None:
    plan, run, upstream, availability = operational()
    binder = RecordingBinder()
    with pytest.raises(Invariant):
        invoke(
            plan,
            run,
            upstream,
            availability=availability,
            binder=binder,
            successor_execution_input=CapabilityExecutionInput(),
        )
    assert binder.calls == []


def test_dependency_errors_propagate_once() -> None:
    plan, run, upstream, availability = operational()
    failure = RuntimeError("delegated failure")
    wp059 = RecordingWP059(upstream, failure)
    kwargs = operands(upstream)
    kwargs.update(
        successor_context_candidates=(),
        successor_context_budget=ContextBudget(2),
        successor_context_created_at=CONTEXT_TIME,
        successor_orchestration_availability=availability,
        successor_execution_input=upstream.post_recording_execution_successor_request.execution_input,
    )
    binder = RecordingBinder()
    with pytest.raises(RuntimeError) as raised:
        Composer(
            request_materialization_composer=wp059, execution_binder=binder
        ).compose(plan, run, "a", **kwargs)
    assert raised.value is failure and len(wp059.calls) == 1 and binder.calls == []
    binder = RecordingBinder(error=failure)
    with pytest.raises(RuntimeError) as raised:
        invoke(plan, run, upstream, availability=availability, binder=binder)
    assert raised.value is failure and len(binder.calls) == 1
    domain_failure = StalePlanStepExecutionBindingError("successor is stale")
    binder = RecordingBinder(error=domain_failure)
    with pytest.raises(StalePlanStepExecutionBindingError) as raised:
        invoke(plan, run, upstream, availability=availability, binder=binder)
    assert raised.value is domain_failure and len(binder.calls) == 1


def test_direct_result_rejects_wrong_presence() -> None:
    plan, run, upstream, _ = operational()
    with pytest.raises(Invariant):
        Result(
            **{
                field.name: getattr(upstream, field.name)
                for field in fields(UpstreamResult)
            },
            post_recording_execution_successor_binding=None,
        )
    assert (
        plan.plan_id
        == upstream.post_recording_execution_advancement_result.updated_run.plan_id
    )
    assert (
        run.run_id
        == upstream.post_recording_execution_advancement_result.updated_run.run_id
    )


def test_repeated_invocations_have_no_hidden_deduplication() -> None:
    plan, run, upstream, availability = operational()
    binder = RecordingBinder()
    first, _, _ = invoke(plan, run, upstream, availability=availability, binder=binder)
    second, _, _ = invoke(plan, run, upstream, availability=availability, binder=binder)
    assert len(binder.calls) == 2
    assert (
        first.post_recording_execution_successor_binding
        is not second.post_recording_execution_successor_binding
    )


def test_no_forbidden_authority_imports() -> None:
    package = Path(
        "iris/plan_step_execution_successor_binding_post_recording_composition"
    )
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in package.glob("*.py")
    )
    tree = ast.parse(source)
    imports = [
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    ]
    assert not any(
        forbidden in module
        for module in imports
        for forbidden in (
            "plan_step_execution_start",
            "execution.coordinator",
            "plan_run_reducer",
            "plan_run_advancement",
            "plan_step_execution_request_materialization.composer",
        )
    )
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not names.intersection(
        {
            "ExecutionRequest",
            "ContextEngine",
            "Orchestrator",
            "PlanRunReducer",
            "PlanRunController",
            "uuid4",
        }
    )
