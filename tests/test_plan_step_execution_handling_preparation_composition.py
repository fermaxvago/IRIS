"""WP043 bounded post-recording handling-preparation composition."""

from __future__ import annotations

import inspect
import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pytest

import iris.plan_step_execution_handling_preparation_composition as public_api
import iris.plan_step_execution_handling_preparation_composition.composer as composer_module
from iris.context import ContextBudget, ContextCandidate, ContextUncertainty
from iris.execution import CapabilityExecutionInput
from iris.execution.models import ExecutionInput
from iris.orchestrator import HandlerAvailability, HandlingKind
from iris.outcome_assessment import StepOutcomeStatus
from iris.plan_control import ControlDecision, ControlDecisionKind
from iris.plan_handling import (
    PlanHandlingError,
    PlanStepHandlingPreparer,
    StepHandlingPreparationResult,
    StepHandlingPreparationStatus,
    StepHandlingSpecification,
)
from iris.plan_runs import PlanRun, StepProgressState
from iris.plan_step_execution_handling_preparation_composition import (
    PlanStepExecutionHandlingPreparationComposer,
    PlanStepExecutionHandlingPreparationCompositionError,
    PlanStepExecutionHandlingPreparationCompositionInvariantError,
    PlanStepExecutionHandlingPreparationCompositionResult,
)
from iris.plan_step_execution_progress_advancement_composition import (
    PlanStepExecutionProgressAdvancementComposer,
    PlanStepExecutionProgressAdvancementCompositionResult,
)
from iris.planning import Plan
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
from tests.test_plan_step_execution_progress_advancement_composition import (
    RecordingWP041,
    compose_from_wp041,
    decision_for_kind,
    no_update_wp041,
)
from tests.test_plan_step_execution_progress_update_composition import (
    compose_from_wp040,
)
from tests.test_plan_step_execution_transition_decision_composition import (
    compose_from_wp039,
)


class RecordingWP042(PlanStepExecutionProgressAdvancementComposer):
    def __init__(
        self,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__(progress_update_composer=RecordingWP041())
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
    ) -> PlanStepExecutionProgressAdvancementCompositionResult:
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
            PlanStepExecutionProgressAdvancementCompositionResult,
            self.forced,
        )


class RecordingHandlingPreparer(PlanStepHandlingPreparer):
    def __init__(
        self,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__()
        self.forced = forced
        self.error = error
        self.calls: list[
            tuple[
                Plan,
                PlanRun,
                ControlDecision,
                StepHandlingSpecification | None,
            ]
        ] = []
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
        if self.forced is None:
            result = super().prepare(plan, run, decision, specification)
        else:
            result = cast(StepHandlingPreparationResult, self.forced)
        self.results.append(result)
        return result


def canonical_wp042(
    *,
    selected_handling: HandlingKind | None = HandlingKind.CAPABILITY,
) -> tuple[Plan, PlanRun, PlanStepExecutionProgressAdvancementCompositionResult]:
    selected_plan = make_plan(
        step("a"),
        step("b", depends_on=("a",), handling=HandlingKind.CAPABILITY),
        step("c", depends_on=("b",), handling=selected_handling),
    )
    source_run = transition(
        selected_plan,
        new_run(selected_plan),
        "a",
        StepProgressState.ACTIVE,
    )
    source_run = record_fixture_observation(
        selected_plan,
        source_run,
        observation_id="evidence-a",
        step_id="a",
        offset=2,
    )
    wp038 = real_recording_composer(CapabilityHandler()).compose(
        selected_plan,
        source_run,
        "a",
        candidates=(),
        budget=BUDGET,
        created_at=CONTEXT_CREATED,
        availability=CAPABILITY_AVAILABLE,
        execution_input=capability_input(),
    )
    canonical_assessor, _ = assessor_for(StepOutcomeStatus.SATISFIED)
    wp039, _, _ = compose_from(
        selected_plan,
        source_run,
        wp038,
        assessor=RecordingAssessor(canonical_assessor),
    )
    wp040, _, _ = compose_from_wp039(selected_plan, source_run, wp039)
    wp041, _, _ = compose_from_wp040(selected_plan, source_run, wp040)
    wp042, _, _ = compose_from_wp041(selected_plan, source_run, wp041)
    advancement = wp042.post_recording_advancement_result
    assert advancement is not None
    assert advancement.control_decision.kind is ControlDecisionKind.STEP_SELECTED
    assert advancement.control_decision.selected_step_id == "c"
    return selected_plan, source_run, wp042


def no_advancement_wp042() -> tuple[
    Plan,
    PlanRun,
    PlanStepExecutionProgressAdvancementCompositionResult,
]:
    plan, run, wp041 = no_update_wp041(decision_absent=False)
    result, _, _ = compose_from_wp041(plan, run, wp041)
    assert result.post_recording_advancement_result is None
    return plan, run, result


def with_control_kind(
    progress: PlanStepExecutionProgressAdvancementCompositionResult,
    kind: ControlDecisionKind,
) -> PlanStepExecutionProgressAdvancementCompositionResult:
    advancement = progress.post_recording_advancement_result
    assert advancement is not None
    control = decision_for_kind(kind, advancement.updated_run)
    return unsafe_clone(
        progress,
        post_recording_advancement_result=replace(
            advancement,
            control_decision=control,
        ),
    )


def compose_from_wp042(
    plan: Plan,
    run: PlanRun,
    delegated: object,
    *,
    handling: RecordingHandlingPreparer | None = None,
    execution_input: CapabilityExecutionInput | None = None,
) -> tuple[
    PlanStepExecutionHandlingPreparationCompositionResult,
    RecordingWP042,
    RecordingHandlingPreparer,
]:
    wp042 = RecordingWP042(forced=delegated)
    actual_handling = RecordingHandlingPreparer() if handling is None else handling
    supplied_input = capability_input() if execution_input is None else execution_input
    result = PlanStepExecutionHandlingPreparationComposer(
        progress_advancement_composer=wp042,
        handling_preparer=actual_handling,
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
    return result, wp042, actual_handling


def test_public_api_constructor_signature_and_exact_exports() -> None:
    assert set(public_api.__all__) == {
        "PlanStepExecutionHandlingPreparationComposer",
        "PlanStepExecutionHandlingPreparationCompositionResult",
        "PlanStepExecutionHandlingPreparationCompositionError",
        "PlanStepExecutionHandlingPreparationCompositionInvariantError",
    }
    assert issubclass(
        PlanStepExecutionHandlingPreparationCompositionInvariantError,
        PlanStepExecutionHandlingPreparationCompositionError,
    )
    signature = inspect.signature(PlanStepExecutionHandlingPreparationComposer.compose)
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
    assert "specification" not in signature.parameters
    with pytest.raises(TypeError, match="progress_advancement_composer"):
        PlanStepExecutionHandlingPreparationComposer()  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="progress_advancement_composer"):
        PlanStepExecutionHandlingPreparationComposer(
            progress_advancement_composer=cast(Any, object())
        )
    with pytest.raises(TypeError, match="handling_preparer"):
        PlanStepExecutionHandlingPreparationComposer(
            progress_advancement_composer=RecordingWP042(),
            handling_preparer=cast(Any, object()),
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
def test_invalid_inputs_fail_before_wp042(position: int, invalid: object) -> None:
    plan, run, delegated = no_advancement_wp042()
    wp042 = RecordingWP042(forced=delegated)
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
        PlanStepExecutionHandlingPreparationComposer(
            progress_advancement_composer=wp042
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
    assert wp042.calls == []


def test_exact_inputs_are_forwarded_to_wp042_once() -> None:
    plan, run, delegated = no_advancement_wp042()
    operation_input = capability_input()
    _, wp042, _ = compose_from_wp042(
        plan,
        run,
        delegated,
        execution_input=operation_input,
    )
    assert wp042.calls == [
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


def test_no_advancement_preserves_wp042_and_skips_wp014() -> None:
    plan, run, delegated = no_advancement_wp042()
    result, wp042, handling = compose_from_wp042(plan, run, delegated)
    assert len(wp042.calls) == 1
    assert handling.calls == []
    assert result.post_recording_handling_preparation is None
    for item in fields(delegated):
        assert getattr(result, item.name) is getattr(delegated, item.name)


@pytest.mark.parametrize("kind", list(ControlDecisionKind))
def test_every_fresh_control_kind_has_exact_bounded_behavior(
    kind: ControlDecisionKind,
) -> None:
    plan, run, selected = canonical_wp042()
    delegated = with_control_kind(selected, kind)
    result, wp042, handling = compose_from_wp042(plan, run, delegated)
    advancement = delegated.post_recording_advancement_result
    assert advancement is not None
    assert len(wp042.calls) == 1
    assert result.post_recording_advancement_result is advancement
    if kind is ControlDecisionKind.STEP_SELECTED:
        assert len(handling.calls) == 1
        call = handling.calls[0]
        assert call[0] is plan
        assert call[1] is advancement.updated_run
        assert call[2] is advancement.control_decision
        assert call[3] is None
        assert result.post_recording_handling_preparation is handling.results[0]
    else:
        assert handling.calls == []
        assert result.post_recording_handling_preparation is None


@pytest.mark.parametrize(
    ("handling_kind", "status"),
    [
        (HandlingKind.CAPABILITY, StepHandlingPreparationStatus.PREPARED),
        (None, StepHandlingPreparationStatus.HANDLING_UNSPECIFIED),
        (HandlingKind.SYSTEM, StepHandlingPreparationStatus.INSUFFICIENT_DETAIL),
        (HandlingKind.MEMORY, StepHandlingPreparationStatus.INSUFFICIENT_DETAIL),
        (
            HandlingKind.INTELLIGENCE,
            StepHandlingPreparationStatus.INSUFFICIENT_DETAIL,
        ),
    ],
)
def test_all_wp014_statuses_are_preserved_without_specification(
    handling_kind: HandlingKind | None,
    status: StepHandlingPreparationStatus,
) -> None:
    plan, run, delegated = canonical_wp042(selected_handling=handling_kind)
    result, _, handling = compose_from_wp042(plan, run, delegated)
    assert len(handling.calls) == 1
    assert handling.calls[0][3] is None
    assert result.post_recording_handling_preparation is handling.results[0]
    assert result.post_recording_handling_preparation.status is status


def test_inherited_and_post_recording_preparations_preserve_a_b_c_lineage() -> None:
    plan, run, delegated = canonical_wp042()
    result, _, _ = compose_from_wp042(plan, run, delegated)
    assert result.assessment.step_id == "a"
    assert result.handling_preparation is delegated.handling_preparation
    assert result.handling_preparation is not None
    assert result.handling_preparation.step_id == "b"
    assert result.post_recording_progress_update is not None
    assert result.post_recording_progress_update.step_id == "b"
    assert result.post_recording_handling_preparation is not None
    assert result.post_recording_handling_preparation.step_id == "c"
    assert result.post_recording_handling_preparation is not (
        result.handling_preparation
    )
    assert result.post_recording_handling_preparation.step_id != "a"


def test_existing_control_currentness_authority_is_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, run, delegated = canonical_wp042()
    calls: list[tuple[Plan, PlanRun, ControlDecision]] = []
    canonical = composer_module.validate_control_decision_current

    def spy(
        selected_plan: Plan,
        selected_run: PlanRun,
        decision: ControlDecision,
    ) -> None:
        calls.append((selected_plan, selected_run, decision))
        canonical(selected_plan, selected_run, decision)

    monkeypatch.setattr(composer_module, "validate_control_decision_current", spy)
    compose_from_wp042(plan, run, delegated)
    advancement = delegated.post_recording_advancement_result
    assert advancement is not None
    assert calls == [(plan, advancement.updated_run, advancement.control_decision)]


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
    ],
)
def test_malformed_wp042_outputs_fail_before_wp014(mutation: str) -> None:
    plan, run, delegated = canonical_wp042()
    malformed: object = delegated
    advancement = delegated.post_recording_advancement_result
    assert advancement is not None
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
        field_name = mutation.removeprefix("successor_")
        actual_name = {"plan": "plan_id", "run": "run_id"}.get(
            field_name,
            field_name,
        )
        value: object = {
            "plan": "foreign-plan",
            "run": "foreign-run",
            "revision": successor.revision + 1,
        }[field_name]
        malformed = unsafe_clone(
            delegated,
            post_recording_advancement_result=unsafe_clone(
                advancement,
                updated_run=unsafe_clone(
                    successor,
                    **{actual_name: value},
                ),
            ),
        )
    else:
        control = advancement.control_decision
        field_name = mutation.removeprefix("control_")
        actual_name = {
            "plan": "plan_id",
            "run": "run_id",
            "revision": "observed_revision",
        }[field_name]
        value = {
            "plan": "foreign-plan",
            "run": "foreign-run",
            "revision": control.observed_revision + 1,
        }[field_name]
        malformed = unsafe_clone(
            delegated,
            post_recording_advancement_result=unsafe_clone(
                advancement,
                control_decision=unsafe_clone(
                    control,
                    **{actual_name: value},
                ),
            ),
        )
    handling = RecordingHandlingPreparer()
    with pytest.raises(PlanStepExecutionHandlingPreparationCompositionInvariantError):
        compose_from_wp042(plan, run, malformed, handling=handling)
    assert handling.calls == []


@pytest.mark.parametrize(
    "mutation",
    ["wrong_type", "plan", "run", "revision", "step", "need_identity"],
)
def test_malformed_wp014_outputs_become_wp043_invariants(mutation: str) -> None:
    plan, run, delegated = canonical_wp042()
    advancement = delegated.post_recording_advancement_result
    assert advancement is not None
    canonical = PlanStepHandlingPreparer().prepare(
        plan,
        advancement.updated_run,
        advancement.control_decision,
    )
    malformed: object = canonical
    if mutation == "wrong_type":
        malformed = object()
    elif mutation == "plan":
        malformed = replace(canonical, plan_id="foreign-plan")
    elif mutation == "run":
        malformed = replace(canonical, run_id="foreign-run")
    elif mutation == "revision":
        malformed = replace(
            canonical,
            observed_revision=canonical.observed_revision + 1,
        )
    elif mutation == "step":
        malformed = replace(canonical, step_id="b")
    else:
        assert canonical.handling_need is not None
        malformed = replace(
            canonical,
            handling_need=replace(
                canonical.handling_need,
                need_id="noncanonical-need",
            ),
        )
    handling = RecordingHandlingPreparer(forced=malformed)
    with pytest.raises(PlanStepExecutionHandlingPreparationCompositionInvariantError):
        compose_from_wp042(plan, run, delegated, handling=handling)
    assert len(handling.calls) == 1


def test_wp042_and_wp014_errors_propagate_exactly_without_fallback() -> None:
    plan, run, delegated = canonical_wp042()
    upstream_failure = RuntimeError("wp042 failed")
    wp042 = RecordingWP042(error=upstream_failure)
    handling = RecordingHandlingPreparer()
    with pytest.raises(RuntimeError) as upstream_caught:
        PlanStepExecutionHandlingPreparationComposer(
            progress_advancement_composer=wp042,
            handling_preparer=handling,
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
    assert len(wp042.calls) == 1
    assert handling.calls == []

    handling_failure = PlanHandlingError("wp014 failed")
    failing_handling = RecordingHandlingPreparer(error=handling_failure)
    with pytest.raises(PlanHandlingError) as handling_caught:
        compose_from_wp042(
            plan,
            run,
            delegated,
            handling=failing_handling,
        )
    assert handling_caught.value is handling_failure
    assert len(failing_handling.calls) == 1


def test_result_immutability_deterministic_serialization_and_exact_identity() -> None:
    plan, run, delegated = canonical_wp042()
    result, _, handling = compose_from_wp042(plan, run, delegated)
    preparation = result.post_recording_handling_preparation
    assert preparation is handling.results[0]
    for item in fields(delegated):
        assert getattr(result, item.name) is getattr(delegated, item.name)
    with pytest.raises(FrozenInstanceError):
        result.post_recording_handling_preparation = None  # type: ignore[misc]
    assert json.loads(json.dumps(result.to_data())) == result.to_data()
    assert result.to_data()["post_recording_handling_preparation"] == (
        preparation.to_data()  # type: ignore[union-attr]
    )


def test_result_rejects_optional_shape_violations() -> None:
    plan, run, selected = canonical_wp042()
    advancement = selected.post_recording_advancement_result
    assert advancement is not None
    preparation = PlanStepHandlingPreparer().prepare(
        plan,
        advancement.updated_run,
        advancement.control_decision,
    )
    with pytest.raises(PlanStepExecutionHandlingPreparationCompositionInvariantError):
        unsafe_clone(
            PlanStepExecutionHandlingPreparationComposer._result(
                selected,
                preparation,
            ),
            post_recording_handling_preparation=None,
        ).__post_init__()

    nonselecting = with_control_kind(
        selected,
        ControlDecisionKind.RUN_STRUCTURALLY_COMPLETE,
    )
    with pytest.raises(PlanStepExecutionHandlingPreparationCompositionInvariantError):
        PlanStepExecutionHandlingPreparationComposer._result(
            nonselecting,
            preparation,
        )


def test_result_rejects_reusing_inherited_preparation_as_post_recording() -> None:
    _, _, selected = canonical_wp042()
    assert selected.handling_preparation is not None
    with pytest.raises(
        PlanStepExecutionHandlingPreparationCompositionInvariantError,
        match="distinct artifacts",
    ):
        PlanStepExecutionHandlingPreparationComposer._result(
            selected,
            selected.handling_preparation,
        )


def test_repeated_invocations_have_no_hidden_deduplication() -> None:
    plan, run, delegated = canonical_wp042()
    wp042 = RecordingWP042(forced=delegated)
    handling = RecordingHandlingPreparer()
    composer = PlanStepExecutionHandlingPreparationComposer(
        progress_advancement_composer=wp042,
        handling_preparer=handling,
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
    assert len(wp042.calls) == len(handling.calls) == 2
    assert first.post_recording_handling_preparation == (
        second.post_recording_handling_preparation
    )
    assert first.post_recording_advancement_result is (
        second.post_recording_advancement_result
    )


def test_freshly_selected_step_remains_not_started_and_preparation_is_inert() -> None:
    plan, run, delegated = canonical_wp042()
    before = (plan.to_data(), run.to_data())
    result, _, _ = compose_from_wp042(plan, run, delegated)
    advancement = result.post_recording_advancement_result
    preparation = result.post_recording_handling_preparation
    assert advancement is not None and preparation is not None
    selected = advancement.control_decision.selected_step_id
    progress = next(
        item
        for item in advancement.updated_run.step_progress
        if item.step_id == selected
    )
    assert selected == "c"
    assert progress.state is StepProgressState.NOT_STARTED
    assert preparation.status is StepHandlingPreparationStatus.PREPARED
    assert (plan.to_data(), run.to_data()) == before


def test_wp043_has_no_forbidden_authority_or_continuation_dependencies() -> None:
    source = (
        Path(__file__).parents[1]
        / "iris"
        / "plan_step_execution_handling_preparation_composition"
        / "composer.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "PlanStepHandlingPreparationComposer",
        "PlanStepProgressAdvancementComposer",
        "PlanStepProgressUpdatePreparer",
        "PlanRunProgressAdvancer",
        "PlanRunReducer",
        "PlanRunController",
        "PlanStepEvidenceAssessor",
        "StepProgressTransitionDecider",
        "StepProgressUpdateSynthesizer",
        "StepHandlingSpecification",
        "PlanStepWorkSubjectMaterializer",
        "PlanStepContextMaterializer",
        "PlanStepOrchestrationComposer",
        "PlanStepExecutionRequestMaterializer",
        "PlanStepExecutionBinder",
        "PlanStepExecutionStartCoordinator",
        "ExecutionCoordinator",
    ):
        assert forbidden not in source
