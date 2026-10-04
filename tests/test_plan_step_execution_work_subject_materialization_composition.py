"""WP044 bounded post-recording selected-work identity materialization."""

from __future__ import annotations

import inspect
import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pytest

import iris.plan_step_execution_work_subject_materialization_composition as public_api
import iris.plan_step_execution_work_subject_materialization_composition.composer as composer_module
from iris.context import ContextBudget, ContextCandidate, ContextUncertainty
from iris.execution import CapabilityExecutionInput
from iris.execution.models import ExecutionInput
from iris.orchestrator import HandlerAvailability, HandlingKind
from iris.plan_control import ControlDecision, ControlDecisionKind
from iris.plan_runs import PlanRun, StepProgressState
from iris.plan_step_execution_handling_preparation_composition import (
    PlanStepExecutionHandlingPreparationComposer,
    PlanStepExecutionHandlingPreparationCompositionResult,
)
from iris.plan_step_execution_work_subject_materialization_composition import (
    PlanStepExecutionWorkSubjectMaterializationComposer,
    PlanStepExecutionWorkSubjectMaterializationCompositionError,
    PlanStepExecutionWorkSubjectMaterializationCompositionInvariantError,
    PlanStepExecutionWorkSubjectMaterializationCompositionResult,
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
from tests.test_plan_step_execution_evidence_assessment_composition import (
    BUDGET,
    CAPABILITY_AVAILABLE,
    CONTEXT_CREATED,
    capability_input,
    unsafe_clone,
)
from tests.test_plan_step_execution_handling_preparation_composition import (
    RecordingWP042,
    canonical_wp042,
    compose_from_wp042,
    no_advancement_wp042,
    with_control_kind,
)
from tests.test_plan_step_handling_preparation import record


class RecordingWP043(PlanStepExecutionHandlingPreparationComposer):
    def __init__(
        self,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__(progress_advancement_composer=RecordingWP042())
        self.forced = forced
        self.error = error
        self.calls: list[tuple[object, ...]] = []

    def compose(
        self,
        plan: Plan,
        run: PlanRun,
        step_id: str,
        *,
        candidates: tuple[ContextCandidate, ...],
        budget: ContextBudget,
        uncertainties: tuple[ContextUncertainty, ...] = (),
        created_at: datetime,
        availability: HandlerAvailability,
        execution_input: ExecutionInput | None = None,
    ) -> PlanStepExecutionHandlingPreparationCompositionResult:
        self.calls.append(
            (
                plan,
                run,
                step_id,
                candidates,
                budget,
                uncertainties,
                created_at,
                availability,
                execution_input,
            )
        )
        if self.error is not None:
            raise self.error
        return cast(
            PlanStepExecutionHandlingPreparationCompositionResult,
            self.forced,
        )


class RecordingAdapter:
    def __init__(
        self,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        self.forced = forced
        self.error = error
        self.calls: list[tuple[Plan, PlanRun, str]] = []
        self.results: list[WorkSubject] = []

    def __call__(self, plan: Plan, run: PlanRun, step_id: str) -> WorkSubject:
        self.calls.append((plan, run, step_id))
        if self.error is not None:
            raise self.error
        if self.forced is None:
            result = work_subject_from_plan_step(plan, run, step_id)
        else:
            result = cast(WorkSubject, self.forced)
        self.results.append(result)
        return result


def canonical_wp043(
    *,
    selected_handling: HandlingKind | None = HandlingKind.CAPABILITY,
) -> tuple[Plan, PlanRun, PlanStepExecutionHandlingPreparationCompositionResult]:
    plan, run, wp042 = canonical_wp042(selected_handling=selected_handling)
    result, _, _ = compose_from_wp042(plan, run, wp042)
    assert result.post_recording_advancement_result is not None
    assert result.post_recording_handling_preparation is not None
    assert (
        result.post_recording_advancement_result.control_decision.kind
        is ControlDecisionKind.STEP_SELECTED
    )
    return plan, run, result


def no_advancement_wp043() -> tuple[
    Plan,
    PlanRun,
    PlanStepExecutionHandlingPreparationCompositionResult,
]:
    plan, run, wp042 = no_advancement_wp042()
    result, _, _ = compose_from_wp042(plan, run, wp042)
    assert result.post_recording_advancement_result is None
    assert result.post_recording_handling_preparation is None
    return plan, run, result


def wp043_for_kind(
    kind: ControlDecisionKind,
) -> tuple[Plan, PlanRun, PlanStepExecutionHandlingPreparationCompositionResult]:
    plan, run, selected = canonical_wp042()
    wp042 = with_control_kind(selected, kind)
    result, _, _ = compose_from_wp042(plan, run, wp042)
    return plan, run, result


def compose_from_wp043(
    plan: Plan,
    run: PlanRun,
    delegated: object,
    *,
    adapter: RecordingAdapter | None = None,
    execution_input: CapabilityExecutionInput | None = None,
) -> tuple[
    PlanStepExecutionWorkSubjectMaterializationCompositionResult,
    RecordingWP043,
    RecordingAdapter,
]:
    wp043 = RecordingWP043(forced=delegated)
    actual_adapter = RecordingAdapter() if adapter is None else adapter
    supplied_input = capability_input() if execution_input is None else execution_input
    result = PlanStepExecutionWorkSubjectMaterializationComposer(
        handling_preparation_composer=wp043,
        work_subject_adapter=actual_adapter,
    ).compose(
        plan,
        run,
        "a",
        candidates=(),
        budget=BUDGET,
        created_at=CONTEXT_CREATED,
        availability=CAPABILITY_AVAILABLE,
        execution_input=supplied_input,
    )
    return result, wp043, actual_adapter


def test_public_api_constructor_signature_and_exact_exports() -> None:
    assert set(public_api.__all__) == {
        "PlanStepExecutionWorkSubjectMaterializationComposer",
        "PlanStepExecutionWorkSubjectMaterializationCompositionResult",
        "PlanStepExecutionWorkSubjectMaterializationCompositionError",
        "PlanStepExecutionWorkSubjectMaterializationCompositionInvariantError",
    }
    assert issubclass(
        PlanStepExecutionWorkSubjectMaterializationCompositionInvariantError,
        PlanStepExecutionWorkSubjectMaterializationCompositionError,
    )
    signature = inspect.signature(
        PlanStepExecutionWorkSubjectMaterializationComposer.compose
    )
    assert tuple(signature.parameters) == (
        "self",
        "plan",
        "run",
        "step_id",
        "candidates",
        "budget",
        "uncertainties",
        "created_at",
        "availability",
        "execution_input",
    )
    for forbidden in (
        "origin",
        "subject_id",
        "selected_step_id",
        "revision",
    ):
        assert forbidden not in signature.parameters
    with pytest.raises(TypeError, match="handling_preparation_composer"):
        PlanStepExecutionWorkSubjectMaterializationComposer()  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="handling_preparation_composer"):
        PlanStepExecutionWorkSubjectMaterializationComposer(
            handling_preparation_composer=cast(Any, object())
        )
    with pytest.raises(TypeError, match="work_subject_adapter"):
        PlanStepExecutionWorkSubjectMaterializationComposer(
            handling_preparation_composer=RecordingWP043(),
            work_subject_adapter=cast(Any, object()),
        )


@pytest.mark.parametrize(
    ("position", "invalid"),
    [
        (0, object()),
        (1, object()),
        (2, 7),
        (3, []),
        (3, (object(),)),
        (4, object()),
        (5, []),
        (5, (object(),)),
        (6, object()),
        (7, object()),
    ],
)
def test_invalid_inputs_fail_before_wp043(position: int, invalid: object) -> None:
    plan, run, delegated = no_advancement_wp043()
    wp043 = RecordingWP043(forced=delegated)
    values: list[object] = [
        plan,
        run,
        "a",
        (),
        BUDGET,
        (),
        CONTEXT_CREATED,
        CAPABILITY_AVAILABLE,
    ]
    values[position] = invalid
    with pytest.raises(TypeError):
        PlanStepExecutionWorkSubjectMaterializationComposer(
            handling_preparation_composer=wp043
        ).compose(
            cast(Plan, values[0]),
            cast(PlanRun, values[1]),
            cast(str, values[2]),
            candidates=cast(tuple[ContextCandidate, ...], values[3]),
            budget=cast(ContextBudget, values[4]),
            uncertainties=cast(tuple[ContextUncertainty, ...], values[5]),
            created_at=cast(datetime, values[6]),
            availability=cast(HandlerAvailability, values[7]),
        )
    assert wp043.calls == []


def test_exact_inputs_are_forwarded_to_wp043_once() -> None:
    plan, run, delegated = no_advancement_wp043()
    operation_input = capability_input()
    _, wp043, _ = compose_from_wp043(
        plan,
        run,
        delegated,
        execution_input=operation_input,
    )
    assert wp043.calls == [
        (
            plan,
            run,
            "a",
            (),
            BUDGET,
            (),
            CONTEXT_CREATED,
            CAPABILITY_AVAILABLE,
            operation_input,
        )
    ]


def test_no_advancement_preserves_wp043_and_skips_wp015() -> None:
    plan, run, delegated = no_advancement_wp043()
    result, wp043, adapter = compose_from_wp043(plan, run, delegated)
    assert len(wp043.calls) == 1
    assert adapter.calls == []
    assert result.post_recording_work_subject is None
    for item in fields(delegated):
        assert getattr(result, item.name) is getattr(delegated, item.name)


@pytest.mark.parametrize("kind", list(ControlDecisionKind))
def test_every_fresh_control_kind_has_exact_bounded_behavior(
    kind: ControlDecisionKind,
) -> None:
    plan, run, delegated = wp043_for_kind(kind)
    result, wp043, adapter = compose_from_wp043(plan, run, delegated)
    advancement = delegated.post_recording_advancement_result
    assert advancement is not None
    assert len(wp043.calls) == 1
    assert result.post_recording_advancement_result is advancement
    if kind is ControlDecisionKind.STEP_SELECTED:
        assert adapter.calls == [(plan, advancement.updated_run, "c")]
        assert adapter.calls[0][0] is plan
        assert adapter.calls[0][1] is advancement.updated_run
        assert result.post_recording_work_subject is adapter.results[0]
        assert result.post_recording_work_subject.origin is None
    else:
        assert adapter.calls == []
        assert result.post_recording_work_subject is None


@pytest.mark.parametrize(
    ("handling_kind", "status"),
    [
        (HandlingKind.CAPABILITY, "prepared"),
        (None, "handling_unspecified"),
        (HandlingKind.SYSTEM, "insufficient_detail"),
        (HandlingKind.MEMORY, "insufficient_detail"),
        (HandlingKind.INTELLIGENCE, "insufficient_detail"),
    ],
)
def test_all_handling_statuses_materialize_stable_identity(
    handling_kind: HandlingKind | None,
    status: str,
) -> None:
    plan, run, delegated = canonical_wp043(selected_handling=handling_kind)
    preparation = delegated.post_recording_handling_preparation
    assert preparation is not None
    assert preparation.status.value == status
    result, _, adapter = compose_from_wp043(plan, run, delegated)
    assert len(adapter.calls) == 1
    assert result.post_recording_handling_preparation is preparation
    assert result.post_recording_work_subject is adapter.results[0]


def test_inherited_and_post_recording_subjects_preserve_a_b_c_lineage() -> None:
    plan, run, delegated = canonical_wp043()
    result, _, _ = compose_from_wp043(plan, run, delegated)
    assert result.assessment.step_id == "a"
    assert result.work_subject is delegated.work_subject
    assert result.work_subject is not None
    assert isinstance(result.work_subject.reference, PlanStepWorkReference)
    assert result.work_subject.reference.step_id == "b"
    assert result.post_recording_progress_update is not None
    assert result.post_recording_progress_update.step_id == "b"
    assert result.post_recording_handling_preparation is not None
    assert result.post_recording_handling_preparation.step_id == "c"
    subject = result.post_recording_work_subject
    assert subject is not None
    assert isinstance(subject.reference, PlanStepWorkReference)
    assert subject.reference.step_id == "c"
    assert subject.reference.step_id != "a"
    assert subject.reference.step_id != result.post_recording_progress_update.step_id
    assert subject is not result.work_subject


def test_existing_currentness_authorities_are_both_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, run, delegated = canonical_wp043()
    control_calls: list[tuple[Plan, PlanRun, ControlDecision]] = []
    preparation_calls: list[tuple[Plan, PlanRun, object]] = []
    canonical_control = composer_module.validate_control_decision_current
    canonical_preparation = composer_module.validate_step_handling_preparation_current

    def control_spy(
        selected_plan: Plan,
        selected_run: PlanRun,
        decision: ControlDecision,
    ) -> None:
        control_calls.append((selected_plan, selected_run, decision))
        canonical_control(selected_plan, selected_run, decision)

    def preparation_spy(
        selected_plan: Plan,
        selected_run: PlanRun,
        preparation: object,
    ) -> None:
        preparation_calls.append((selected_plan, selected_run, preparation))
        canonical_preparation(selected_plan, selected_run, cast(Any, preparation))

    monkeypatch.setattr(
        composer_module, "validate_control_decision_current", control_spy
    )
    monkeypatch.setattr(
        composer_module,
        "validate_step_handling_preparation_current",
        preparation_spy,
    )
    compose_from_wp043(plan, run, delegated)
    advancement = delegated.post_recording_advancement_result
    preparation = delegated.post_recording_handling_preparation
    assert advancement is not None and preparation is not None
    assert control_calls == [
        (plan, advancement.updated_run, advancement.control_decision)
    ]
    assert preparation_calls == [(plan, advancement.updated_run, preparation)]


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_type",
        "source_plan",
        "source_run",
        "source_revision",
        "source_step",
        "presence",
        "successor_plan",
        "successor_run",
        "successor_revision",
        "control_plan",
        "control_run",
        "control_revision",
        "missing_selected_step",
        "missing_preparation",
        "preparation_plan",
        "preparation_run",
        "preparation_revision",
        "preparation_step",
    ],
)
def test_malformed_wp043_outputs_fail_before_wp015(mutation: str) -> None:
    plan, run, delegated = canonical_wp043()
    malformed: object = delegated
    advancement = delegated.post_recording_advancement_result
    preparation = delegated.post_recording_handling_preparation
    assert advancement is not None and preparation is not None
    if mutation == "wrong_type":
        malformed = object()
    elif mutation.startswith("source_"):
        assessment = delegated.assessment
        decision = delegated.transition_decision
        if mutation == "source_plan":
            assessment = replace(assessment, plan_id="foreign-plan")
            decision = replace(decision, plan_id="foreign-plan")
        elif mutation == "source_run":
            assessment = replace(assessment, run_id="foreign-run")
            decision = replace(decision, run_id="foreign-run")
        elif mutation == "source_revision":
            assessment = replace(assessment, run_revision=run.revision + 1)
            decision = replace(decision, observed_revision=run.revision + 1)
        else:
            assessment = replace(assessment, step_id="b")
            decision = replace(decision, step_id="b")
        malformed = unsafe_clone(
            delegated,
            assessment=assessment,
            transition_decision=decision,
        )
    elif mutation == "presence":
        malformed = unsafe_clone(
            delegated,
            post_recording_advancement_result=None,
        )
    elif mutation.startswith("successor_"):
        successor = advancement.updated_run
        name = mutation.removeprefix("successor_")
        field_name = {"plan": "plan_id", "run": "run_id"}.get(name, name)
        value: object = {
            "plan": "foreign-plan",
            "run": "foreign-run",
            "revision": successor.revision + 1,
        }[name]
        malformed = unsafe_clone(
            delegated,
            post_recording_advancement_result=unsafe_clone(
                advancement,
                updated_run=unsafe_clone(
                    successor,
                    **{field_name: value},
                ),
            ),
        )
    elif mutation.startswith("control_") or mutation == "missing_selected_step":
        control = advancement.control_decision
        if mutation == "control_plan":
            changed_control = unsafe_clone(control, plan_id="foreign-plan")
        elif mutation == "control_run":
            changed_control = unsafe_clone(control, run_id="foreign-run")
        elif mutation == "control_revision":
            changed_control = unsafe_clone(
                control,
                observed_revision=control.observed_revision + 1,
            )
        else:
            changed_control = unsafe_clone(control, selected_step_id=None)
        malformed = unsafe_clone(
            delegated,
            post_recording_advancement_result=unsafe_clone(
                advancement,
                control_decision=changed_control,
            ),
        )
    elif mutation == "missing_preparation":
        malformed = unsafe_clone(
            delegated,
            post_recording_handling_preparation=None,
        )
    else:
        field_name = mutation.removeprefix("preparation_")
        actual_name = {
            "plan": "plan_id",
            "run": "run_id",
            "revision": "observed_revision",
            "step": "step_id",
        }[field_name]
        value = {
            "plan": "foreign-plan",
            "run": "foreign-run",
            "revision": preparation.observed_revision + 1,
            "step": "b",
        }[field_name]
        malformed = unsafe_clone(
            delegated,
            post_recording_handling_preparation=unsafe_clone(
                preparation,
                **{actual_name: value},
            ),
        )
    adapter = RecordingAdapter()
    with pytest.raises(
        PlanStepExecutionWorkSubjectMaterializationCompositionInvariantError
    ):
        compose_from_wp043(plan, run, malformed, adapter=adapter)
    assert adapter.calls == []


@pytest.mark.parametrize(
    "mutation",
    ["wrong_type", "kind", "reference_type", "plan", "run", "step", "origin"],
)
def test_noncanonical_wp015_outputs_become_wp044_invariants(mutation: str) -> None:
    plan, run, delegated = canonical_wp043()
    advancement = delegated.post_recording_advancement_result
    assert advancement is not None
    canonical = work_subject_from_plan_step(plan, advancement.updated_run, "c")
    malformed: object = canonical
    if mutation == "wrong_type":
        malformed = object()
    elif mutation == "kind":
        malformed = unsafe_clone(canonical, kind=WorkSubjectKind.REQUEST)
    elif mutation == "reference_type":
        malformed = unsafe_clone(
            canonical,
            reference=RequestWorkReference("request-1"),
        )
    elif mutation == "plan":
        malformed = unsafe_clone(
            canonical,
            reference=PlanStepWorkReference("foreign-plan", run.run_id, "c"),
        )
    elif mutation == "run":
        malformed = unsafe_clone(
            canonical,
            reference=PlanStepWorkReference(plan.plan_id, "foreign-run", "c"),
        )
    elif mutation == "step":
        malformed = unsafe_clone(
            canonical,
            reference=PlanStepWorkReference(plan.plan_id, run.run_id, "b"),
        )
    else:
        malformed = unsafe_clone(
            canonical,
            origin=WorkOrigin("request", "request-1"),
        )
    adapter = RecordingAdapter(forced=malformed)
    with pytest.raises(
        PlanStepExecutionWorkSubjectMaterializationCompositionInvariantError
    ):
        compose_from_wp043(plan, run, delegated, adapter=adapter)
    assert len(adapter.calls) == 1


def test_adapter_failure_is_wrapped_and_wp043_error_propagates() -> None:
    plan, run, delegated = canonical_wp043()
    adapter_failure = RuntimeError("wp015 failed")
    failing_adapter = RecordingAdapter(error=adapter_failure)
    with pytest.raises(
        PlanStepExecutionWorkSubjectMaterializationCompositionInvariantError
    ) as adapter_caught:
        compose_from_wp043(plan, run, delegated, adapter=failing_adapter)
    assert adapter_caught.value.__cause__ is adapter_failure
    assert len(failing_adapter.calls) == 1

    upstream_failure = RuntimeError("wp043 failed")
    wp043 = RecordingWP043(error=upstream_failure)
    adapter = RecordingAdapter()
    with pytest.raises(RuntimeError) as upstream_caught:
        PlanStepExecutionWorkSubjectMaterializationComposer(
            handling_preparation_composer=wp043,
            work_subject_adapter=adapter,
        ).compose(
            plan,
            run,
            "a",
            candidates=(),
            budget=BUDGET,
            created_at=CONTEXT_CREATED,
            availability=CAPABILITY_AVAILABLE,
        )
    assert upstream_caught.value is upstream_failure
    assert len(wp043.calls) == 1
    assert adapter.calls == []


def test_identity_excludes_revision_and_is_deterministic() -> None:
    plan, run, delegated = canonical_wp043()
    result, _, _ = compose_from_wp043(plan, run, delegated)
    advancement = delegated.post_recording_advancement_result
    subject = result.post_recording_work_subject
    assert advancement is not None and subject is not None
    successor = advancement.updated_run
    later = record(plan, successor, "c", "later-c")
    later_subject = work_subject_from_plan_step(plan, later, "c")
    assert successor.revision != later.revision
    assert subject == later_subject
    assert subject.subject_id == later_subject.subject_id
    assert "revision" not in subject.reference.to_data()


def test_result_immutability_serialization_and_exact_artifact_identity() -> None:
    plan, run, delegated = canonical_wp043()
    result, _, adapter = compose_from_wp043(plan, run, delegated)
    subject = result.post_recording_work_subject
    assert subject is adapter.results[0]
    for item in fields(delegated):
        assert getattr(result, item.name) is getattr(delegated, item.name)
    with pytest.raises(FrozenInstanceError):
        result.post_recording_work_subject = None  # type: ignore[misc]
    assert json.loads(json.dumps(result.to_data())) == result.to_data()
    assert result.to_data()["post_recording_work_subject"] == (
        subject.to_data()  # type: ignore[union-attr]
    )


def test_result_rejects_optional_shape_and_subject_reuse() -> None:
    plan, run, selected = canonical_wp043()
    advancement = selected.post_recording_advancement_result
    assert advancement is not None
    subject = work_subject_from_plan_step(plan, advancement.updated_run, "c")
    valid = PlanStepExecutionWorkSubjectMaterializationComposer._result(
        selected,
        subject,
    )
    with pytest.raises(
        PlanStepExecutionWorkSubjectMaterializationCompositionInvariantError
    ):
        unsafe_clone(valid, post_recording_work_subject=None).__post_init__()

    _, _, nonselecting = wp043_for_kind(ControlDecisionKind.RUN_STRUCTURALLY_COMPLETE)
    with pytest.raises(
        PlanStepExecutionWorkSubjectMaterializationCompositionInvariantError
    ):
        PlanStepExecutionWorkSubjectMaterializationComposer._result(
            nonselecting,
            subject,
        )

    inherited = selected.work_subject
    assert inherited is not None
    with pytest.raises(
        PlanStepExecutionWorkSubjectMaterializationCompositionInvariantError,
        match="distinct artifacts",
    ):
        PlanStepExecutionWorkSubjectMaterializationComposer._result(
            selected,
            inherited,
        )


def test_repeated_invocation_has_no_hidden_deduplication_claim() -> None:
    plan, run, delegated = canonical_wp043()
    wp043 = RecordingWP043(forced=delegated)
    adapter = RecordingAdapter()
    composer = PlanStepExecutionWorkSubjectMaterializationComposer(
        handling_preparation_composer=wp043,
        work_subject_adapter=adapter,
    )
    first = composer.compose(
        plan,
        run,
        "a",
        candidates=(),
        budget=BUDGET,
        created_at=CONTEXT_CREATED,
        availability=CAPABILITY_AVAILABLE,
    )
    second = composer.compose(
        plan,
        run,
        "a",
        candidates=(),
        budget=BUDGET,
        created_at=CONTEXT_CREATED,
        availability=CAPABILITY_AVAILABLE,
    )
    assert len(wp043.calls) == len(adapter.calls) == 2
    assert first.post_recording_work_subject == second.post_recording_work_subject
    assert first.post_recording_work_subject is adapter.results[0]
    assert second.post_recording_work_subject is adapter.results[1]
    assert adapter.results[0] is not adapter.results[1]


def test_selected_step_c_remains_not_started_and_subject_is_inert() -> None:
    plan, run, delegated = canonical_wp043()
    before = (plan.to_data(), run.to_data())
    result, _, _ = compose_from_wp043(plan, run, delegated)
    advancement = result.post_recording_advancement_result
    subject = result.post_recording_work_subject
    assert advancement is not None and subject is not None
    selected = advancement.control_decision.selected_step_id
    progress = next(
        item
        for item in advancement.updated_run.step_progress
        if item.step_id == selected
    )
    assert selected == "c"
    assert progress.state is StepProgressState.NOT_STARTED
    assert subject.kind is WorkSubjectKind.PLAN_STEP
    assert subject.origin is None
    assert (plan.to_data(), run.to_data()) == before


def test_wp044_has_no_forbidden_authority_or_continuation_dependencies() -> None:
    source = (
        Path(__file__).parents[1]
        / "iris"
        / "plan_step_execution_work_subject_materialization_composition"
        / "composer.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "PlanStepWorkSubjectMaterializer",
        "PlanStepHandlingPreparationComposer",
        "PlanStepProgressAdvancementComposer",
        "PlanRunProgressAdvancer",
        "PlanRunReducer",
        "PlanRunController",
        "ContextEngine",
        "ContextSnapshot",
        "Orchestrator",
        "OrchestrationDecision",
        "ExecutionRequest",
        "PlanStepExecutionBinder",
        "PlanStepExecutionStartCoordinator",
        "ExecutionCoordinator",
        "WorkSubjectFactory",
        "WorkIdentityService",
        "PlanStepIdentityResolver",
    ):
        assert forbidden not in source
