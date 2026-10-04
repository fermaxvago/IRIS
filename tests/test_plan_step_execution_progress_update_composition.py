"""WP041 bounded post-decision progress-update composition."""

from __future__ import annotations

import inspect
import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

from iris.context import ContextBudget, ContextCandidate, ContextUncertainty
from iris.execution import CapabilityExecutionInput
from iris.execution.models import ExecutionInput
from iris.orchestrator import HandlerAvailability
from iris.outcome_assessment import StepOutcomeAssessment, StepOutcomeStatus
from iris.plan_runs import PlanRun, RunProvenance, StepProgressState, StepProgressUpdate
from iris.plan_step_execution_progress_update_composition import (
    PlanStepExecutionProgressUpdateComposer,
    PlanStepExecutionProgressUpdateCompositionError,
    PlanStepExecutionProgressUpdateCompositionInvariantError,
    PlanStepExecutionProgressUpdateCompositionResult,
)
from iris.plan_step_execution_transition_decision_composition import (
    PlanStepExecutionTransitionDecisionComposer,
    PlanStepExecutionTransitionDecisionCompositionResult,
)
from iris.planning import Plan
from iris.step_progress_transition import (
    StepProgressTransitionAction,
    StepProgressTransitionDecision,
)
from iris.step_progress_update_synthesis import (
    StepProgressUpdateGenerationError,
    StepProgressUpdateSynthesizer,
)
from tests.test_plan_step_execution_evidence_assessment_composition import (
    BUDGET,
    CAPABILITY_AVAILABLE,
    CONTEXT_CREATED,
    capability_input,
    unsafe_clone,
)
from tests.test_plan_step_execution_transition_decision_composition import (
    DECIDED,
    RecordingWP039,
    canonical_wp039,
    compose_from_wp039,
    no_assessment_wp039,
)

UPDATED = DECIDED + timedelta(seconds=1)


class RecordingWP040(PlanStepExecutionTransitionDecisionComposer):
    def __init__(
        self,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__(evidence_assessment_composer=RecordingWP039())
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
    ) -> PlanStepExecutionTransitionDecisionCompositionResult:
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
            PlanStepExecutionTransitionDecisionCompositionResult,
            self.forced,
        )


class RecordingSynthesizer(StepProgressUpdateSynthesizer):
    def __init__(
        self,
        *,
        forced: object | None = None,
        error: Exception | None = None,
        update_ids: list[str] | None = None,
    ) -> None:
        ids = iter(["post-progress-update-1"] if update_ids is None else update_ids)
        super().__init__(clock=lambda: UPDATED, update_id_factory=lambda: next(ids))
        self.forced = forced
        self.error = error
        self.calls: list[
            tuple[
                Plan,
                PlanRun,
                StepOutcomeAssessment,
                StepProgressTransitionDecision,
            ]
        ] = []

    def synthesize(
        self,
        plan: Plan,
        run: PlanRun,
        assessment: StepOutcomeAssessment,
        decision: StepProgressTransitionDecision,
    ) -> StepProgressUpdate:
        self.calls.append((plan, run, assessment, decision))
        if self.error is not None:
            raise self.error
        if self.forced is not None:
            return cast(StepProgressUpdate, self.forced)
        return super().synthesize(plan, run, assessment, decision)


def canonical_wp040(
    *,
    status: StepOutcomeStatus = StepOutcomeStatus.SATISFIED,
    handler_available: bool = True,
) -> tuple[Plan, PlanRun, PlanStepExecutionTransitionDecisionCompositionResult]:
    plan, source_run, wp039 = canonical_wp039(
        status=status,
        handler_available=handler_available,
    )
    result, _, _ = compose_from_wp039(plan, source_run, wp039)
    return plan, source_run, result


def no_decision_wp040() -> tuple[
    Plan, PlanRun, PlanStepExecutionTransitionDecisionCompositionResult
]:
    plan, source_run, wp039 = no_assessment_wp039()
    result, _, _ = compose_from_wp039(plan, source_run, wp039)
    assert result.post_recording_transition_decision is None
    return plan, source_run, result


def compose_from_wp040(
    plan: Plan,
    run: PlanRun,
    delegated: object,
    *,
    synthesizer: RecordingSynthesizer | None = None,
    execution_input: CapabilityExecutionInput | None = None,
) -> tuple[
    PlanStepExecutionProgressUpdateCompositionResult,
    RecordingWP040,
    RecordingSynthesizer,
]:
    wp040 = RecordingWP040(forced=delegated)
    actual_synthesizer = RecordingSynthesizer() if synthesizer is None else synthesizer
    supplied_input = capability_input() if execution_input is None else execution_input
    result = PlanStepExecutionProgressUpdateComposer(
        transition_decision_composer=wp040,
        progress_update_synthesizer=actual_synthesizer,
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
    return result, wp040, actual_synthesizer


def test_public_api_constructor_signature_immutability_and_serialization() -> None:
    assert issubclass(
        PlanStepExecutionProgressUpdateCompositionInvariantError,
        PlanStepExecutionProgressUpdateCompositionError,
    )
    signature = inspect.signature(PlanStepExecutionProgressUpdateComposer.compose)
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
    with pytest.raises(TypeError, match="transition_decision_composer"):
        PlanStepExecutionProgressUpdateComposer()  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="transition_decision_composer"):
        PlanStepExecutionProgressUpdateComposer(
            transition_decision_composer=cast(Any, object())
        )
    with pytest.raises(TypeError, match="progress_update_synthesizer"):
        PlanStepExecutionProgressUpdateComposer(
            transition_decision_composer=RecordingWP040(),
            progress_update_synthesizer=cast(Any, object()),
        )

    plan, run, delegated = canonical_wp040()
    result, _, _ = compose_from_wp040(plan, run, delegated)
    with pytest.raises(FrozenInstanceError):
        result.post_recording_progress_update = None  # type: ignore[misc]
    assert json.loads(json.dumps(result.to_data())) == result.to_data()
    assert result.to_data()["post_recording_transition_decision"] == (
        delegated.post_recording_transition_decision.to_data()  # type: ignore[union-attr]
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
def test_invalid_inputs_fail_before_wp040(position: int, invalid: object) -> None:
    plan, run, delegated = no_decision_wp040()
    wp040 = RecordingWP040(forced=delegated)
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
        PlanStepExecutionProgressUpdateComposer(
            transition_decision_composer=wp040
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
    assert wp040.calls == []


def test_exact_inputs_forwarded_to_wp040_once() -> None:
    plan, run, delegated = no_decision_wp040()
    operation_input = capability_input()
    _, wp040, _ = compose_from_wp040(
        plan,
        run,
        delegated,
        execution_input=operation_input,
    )
    assert wp040.calls == [
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


def test_no_decision_preserves_wp040_and_skips_wp022() -> None:
    plan, run, delegated = no_decision_wp040()
    result, wp040, synthesizer = compose_from_wp040(plan, run, delegated)
    assert len(wp040.calls) == 1
    assert synthesizer.calls == []
    assert result.post_recording_transition_decision is None
    assert result.post_recording_progress_update is None
    for item in fields(delegated):
        assert getattr(result, item.name) is getattr(delegated, item.name)


@pytest.mark.parametrize(
    ("status", "handler_available"),
    [
        (StepOutcomeStatus.NOT_SATISFIED, True),
        (StepOutcomeStatus.INDETERMINATE, True),
        (StepOutcomeStatus.INDETERMINATE, False),
    ],
)
def test_explicit_no_transition_is_preserved_without_wp022(
    status: StepOutcomeStatus,
    handler_available: bool,
) -> None:
    plan, run, delegated = canonical_wp040(
        status=status,
        handler_available=handler_available,
    )
    result, _, synthesizer = compose_from_wp040(plan, run, delegated)
    decision = delegated.post_recording_transition_decision
    assert decision is not None
    assert decision.action is StepProgressTransitionAction.NO_TRANSITION
    assert result.post_recording_transition_decision is decision
    assert result.post_recording_progress_update is None
    assert synthesizer.calls == []


def test_transition_synthesizes_once_from_exact_wp040_artifacts_and_stops() -> None:
    plan, source_run, delegated = canonical_wp040()
    recording = delegated.execution_recording_result
    assessment = delegated.post_recording_assessment
    decision = delegated.post_recording_transition_decision
    assert recording is not None and assessment is not None and decision is not None
    before = (plan.to_data(), source_run.to_data(), recording.recorded_run.to_data())

    result, wp040, synthesizer = compose_from_wp040(plan, source_run, delegated)

    assert len(wp040.calls) == 1
    assert synthesizer.calls == [(plan, recording.recorded_run, assessment, decision)]
    assert result.post_recording_assessment is assessment
    assert result.post_recording_transition_decision is decision
    assert result.post_recording_progress_update is not None
    assert result.post_recording_progress_update is not delegated.progress_update
    assert (plan.to_data(), source_run.to_data(), recording.recorded_run.to_data()) == (
        before
    )


def test_processed_a_and_post_recording_b_update_remain_distinct() -> None:
    plan, source_run, delegated = canonical_wp040()
    result, _, _ = compose_from_wp040(plan, source_run, delegated)
    update = result.post_recording_progress_update
    assert delegated.assessment.step_id == "a"
    assert delegated.transition_decision.step_id == "a"
    assert delegated.progress_update is not None
    assert delegated.progress_update.step_id == "a"
    assert delegated.post_recording_assessment is not None
    assert delegated.post_recording_assessment.step_id == "b"
    assert delegated.post_recording_transition_decision is not None
    assert delegated.post_recording_transition_decision.step_id == "b"
    assert update is not None and update.step_id == "b"
    assert result.progress_update is delegated.progress_update


@pytest.mark.parametrize(
    "mutation",
    ["wrong_type", "source", "decision_presence", "recording", "assessment"],
)
def test_malformed_wp040_output_fails_before_wp022(mutation: str) -> None:
    plan, source_run, delegated = canonical_wp040()
    recording = delegated.execution_recording_result
    assessment = delegated.post_recording_assessment
    assert recording is not None and assessment is not None
    malformed: object = delegated
    if mutation == "wrong_type":
        malformed = object()
    elif mutation == "source":
        malformed = unsafe_clone(
            delegated,
            assessment=unsafe_clone(delegated.assessment, step_id="b"),
        )
    elif mutation == "decision_presence":
        malformed = unsafe_clone(
            delegated,
            post_recording_transition_decision=None,
        )
    elif mutation == "recording":
        malformed = unsafe_clone(
            delegated,
            execution_recording_result=unsafe_clone(recording, step_id="a"),
        )
    else:
        malformed = unsafe_clone(
            delegated,
            post_recording_assessment=unsafe_clone(assessment, run_revision=0),
        )
    synthesizer = RecordingSynthesizer()
    with pytest.raises(PlanStepExecutionProgressUpdateCompositionInvariantError):
        compose_from_wp040(
            plan,
            source_run,
            malformed,
            synthesizer=synthesizer,
        )
    assert synthesizer.calls == []


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_type",
        "run_id",
        "revision",
        "step_id",
        "target",
        "evidence",
        "provenance",
        "actor",
    ],
)
def test_malformed_wp022_output_becomes_wp041_invariant(mutation: str) -> None:
    plan, source_run, delegated = canonical_wp040()
    recording = delegated.execution_recording_result
    assessment = delegated.post_recording_assessment
    decision = delegated.post_recording_transition_decision
    assert recording is not None and assessment is not None and decision is not None
    canonical = RecordingSynthesizer().synthesize(
        plan,
        recording.recorded_run,
        assessment,
        decision,
    )
    malformed: object = canonical
    if mutation == "wrong_type":
        malformed = object()
    elif mutation == "run_id":
        malformed = replace(canonical, run_id="other-run")
    elif mutation == "revision":
        malformed = replace(
            canonical, expected_revision=canonical.expected_revision + 1
        )
    elif mutation == "step_id":
        malformed = replace(canonical, step_id="a")
    elif mutation == "target":
        malformed = replace(canonical, new_state=StepProgressState.FAILED)
    elif mutation == "evidence":
        malformed = replace(canonical, evidence_ids=("other-evidence",))
    elif mutation == "provenance":
        malformed = replace(
            canonical,
            provenance=RunProvenance("other", decision.decision_id),
        )
    else:
        malformed = replace(
            canonical,
            provenance=RunProvenance(
                "step_progress_transition",
                decision.decision_id,
                "actor-1",
            ),
        )
    synthesizer = RecordingSynthesizer(forced=malformed)
    with pytest.raises(PlanStepExecutionProgressUpdateCompositionInvariantError):
        compose_from_wp040(
            plan,
            source_run,
            delegated,
            synthesizer=synthesizer,
        )
    assert len(synthesizer.calls) == 1


def test_upstream_and_wp022_errors_propagate_without_fallback_or_retry() -> None:
    plan, source_run, delegated = canonical_wp040()
    upstream_error = RuntimeError("wp040 failed")
    wp040 = RecordingWP040(error=upstream_error)
    synthesizer = RecordingSynthesizer()
    with pytest.raises(RuntimeError) as upstream_caught:
        PlanStepExecutionProgressUpdateComposer(
            transition_decision_composer=wp040,
            progress_update_synthesizer=synthesizer,
        ).compose(
            plan,
            source_run,
            "a",
            candidates=(),
            budget=BUDGET,
            created_at=CONTEXT_CREATED,
            availability=CAPABILITY_AVAILABLE,
            execution_input=capability_input(),
        )
    assert upstream_caught.value is upstream_error
    assert len(wp040.calls) == 1
    assert synthesizer.calls == []

    synthesis_error = StepProgressUpdateGenerationError("wp022 failed")
    failing_synthesizer = RecordingSynthesizer(error=synthesis_error)
    with pytest.raises(StepProgressUpdateGenerationError) as synthesis_caught:
        compose_from_wp040(
            plan,
            source_run,
            delegated,
            synthesizer=failing_synthesizer,
        )
    assert synthesis_caught.value is synthesis_error
    assert len(failing_synthesizer.calls) == 1


def test_result_rejects_action_update_equivalence_violations() -> None:
    plan, source_run, transition = canonical_wp040()
    result, _, _ = compose_from_wp040(plan, source_run, transition)
    with pytest.raises(
        PlanStepExecutionProgressUpdateCompositionInvariantError,
        match="if and only if",
    ):
        unsafe_clone(result, post_recording_progress_update=None).__post_init__()

    plan, source_run, no_transition = canonical_wp040(
        status=StepOutcomeStatus.NOT_SATISFIED
    )
    with pytest.raises(
        PlanStepExecutionProgressUpdateCompositionInvariantError,
        match="if and only if",
    ):
        unsafe_clone(
            result,
            post_recording_assessment=no_transition.post_recording_assessment,
            post_recording_transition_decision=(
                no_transition.post_recording_transition_decision
            ),
        ).__post_init__()


def test_repeated_invocations_are_not_globally_deduplicated() -> None:
    plan, source_run, delegated = canonical_wp040()
    synthesizer = RecordingSynthesizer(
        update_ids=["post-progress-update-1", "post-progress-update-2"]
    )
    first, _, _ = compose_from_wp040(
        plan,
        source_run,
        delegated,
        synthesizer=synthesizer,
    )
    second, _, _ = compose_from_wp040(
        plan,
        source_run,
        delegated,
        synthesizer=synthesizer,
    )
    assert first.post_recording_progress_update is not None
    assert second.post_recording_progress_update is not None
    assert first.post_recording_progress_update.update_id != (
        second.post_recording_progress_update.update_id
    )
    assert len(synthesizer.calls) == 2


def test_wp041_has_no_forbidden_authority_dependencies() -> None:
    source = (
        Path(__file__).parents[1]
        / "iris"
        / "plan_step_execution_progress_update_composition"
        / "composer.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "PlanStepEvidenceAssessor",
        "PlanStepEvidenceTransitionComposer",
        "StepProgressTransitionDecider",
        "PlanStepProgressUpdatePreparer",
        "PlanRunProgressAdvancer",
        "PlanRunReducer",
        "PlanRunController",
        "PlanStepProgressAdvancementComposer",
        "ExecutionCoordinator",
    ):
        assert forbidden not in source
