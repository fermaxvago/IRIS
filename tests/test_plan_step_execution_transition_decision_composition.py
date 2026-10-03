"""WP040 bounded post-assessment transition-decision composition."""

from __future__ import annotations

import inspect
import json
from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

from iris.context import ContextBudget, ContextCandidate, ContextUncertainty
from iris.execution import CapabilityExecutionInput, ExecutionFailure, ExecutionStatus
from iris.execution.models import ExecutionInput, HandlerOutcome
from iris.orchestrator import HandlerAvailability
from iris.outcome_assessment import StepOutcomeAssessment, StepOutcomeStatus
from iris.plan_runs import PlanRun, StepProgressState
from iris.plan_step_execution_evidence_assessment_composition import (
    PlanStepExecutionEvidenceAssessmentComposer,
    PlanStepExecutionEvidenceAssessmentCompositionError,
    PlanStepExecutionEvidenceAssessmentCompositionResult,
)
from iris.plan_step_execution_start import PlanStepExecutionInvocationError
from iris.plan_step_execution_transition_decision_composition import (
    PlanStepExecutionTransitionDecisionComposer,
    PlanStepExecutionTransitionDecisionCompositionError,
    PlanStepExecutionTransitionDecisionCompositionInvariantError,
    PlanStepExecutionTransitionDecisionCompositionResult,
)
from iris.planning import Plan, PlanStep
from iris.step_progress_transition import (
    StepProgressTransitionAction,
    StepProgressTransitionDecider,
    StepProgressTransitionDecision,
    StepProgressTransitionError,
    StepProgressTransitionReason,
)
from tests.test_plan_step_execution_evidence_assessment_composition import (
    BUDGET,
    CAPABILITY_AVAILABLE,
    CONTEXT_CREATED,
    POST_ASSESSED,
    RecordingAssessor,
    RecordingWP038,
    assessor_for,
    canonical_wp038,
    capability_input,
    compose_from,
    real_recording_composer,
    selected_scenario,
    selected_state,
    unsafe_clone,
)

DECIDED = POST_ASSESSED + timedelta(seconds=1)


class RecordingWP039(PlanStepExecutionEvidenceAssessmentComposer):
    def __init__(
        self,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__(recording_composer=RecordingWP038())
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
    ) -> PlanStepExecutionEvidenceAssessmentCompositionResult:
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
        if self.forced is not None:
            return cast(
                PlanStepExecutionEvidenceAssessmentCompositionResult,
                self.forced,
            )
        return super().compose(
            plan,
            run,
            step_id,
            candidates=candidates,
            budget=budget,
            uncertainties=uncertainties,
            created_at=created_at,
            availability=availability,
            execution_input=execution_input,
        )


class RecordingDecider(StepProgressTransitionDecider):
    def __init__(
        self,
        *,
        forced: object | None = None,
        error: Exception | None = None,
        ids: list[str] | None = None,
    ) -> None:
        decision_ids = iter(["post-transition-1"] if ids is None else ids)
        super().__init__(
            clock=lambda: DECIDED,
            decision_id_factory=lambda: next(decision_ids),
        )
        self.forced = forced
        self.error = error
        self.calls: list[tuple[Plan, PlanRun, PlanStep, StepOutcomeAssessment]] = []

    def decide(
        self,
        plan: Plan,
        run: PlanRun,
        step: PlanStep,
        assessment: StepOutcomeAssessment,
    ) -> StepProgressTransitionDecision:
        self.calls.append((plan, run, step, assessment))
        if self.error is not None:
            raise self.error
        if self.forced is not None:
            return cast(StepProgressTransitionDecision, self.forced)
        return super().decide(plan, run, step, assessment)


def canonical_wp039(
    *,
    handler_available: bool = True,
    outcome: HandlerOutcome | None = None,
    status: StepOutcomeStatus = StepOutcomeStatus.INDETERMINATE,
) -> tuple[Plan, PlanRun, PlanStepExecutionEvidenceAssessmentCompositionResult]:
    plan, source_run, wp038 = canonical_wp038(
        handler_available=handler_available,
        outcome=outcome,
    )
    canonical_assessor, _ = assessor_for(status)
    result, _, _ = compose_from(
        plan,
        source_run,
        wp038,
        assessor=RecordingAssessor(canonical_assessor),
    )
    return plan, source_run, result


def no_assessment_wp039() -> tuple[
    Plan, PlanRun, PlanStepExecutionEvidenceAssessmentCompositionResult
]:
    plan, run = selected_scenario(selected_handling=None)
    wp038 = real_recording_composer(None).compose(
        plan,
        run,
        "a",
        candidates=(),
        budget=BUDGET,
        created_at=CONTEXT_CREATED,
        availability=HandlerAvailability(capability=False),
    )
    result, _, _ = compose_from(plan, run, wp038)
    assert result.post_recording_assessment is None
    return plan, run, result


def compose_from_wp039(
    plan: Plan,
    run: PlanRun,
    delegated: object,
    *,
    decider: RecordingDecider | None = None,
    execution_input: CapabilityExecutionInput | None = None,
) -> tuple[
    PlanStepExecutionTransitionDecisionCompositionResult,
    RecordingWP039,
    RecordingDecider,
]:
    wp039 = RecordingWP039(forced=delegated)
    actual_decider = RecordingDecider() if decider is None else decider
    supplied_input = capability_input() if execution_input is None else execution_input
    result = PlanStepExecutionTransitionDecisionComposer(
        evidence_assessment_composer=wp039,
        transition_decider=actual_decider,
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
    return result, wp039, actual_decider


def test_public_api_constructor_signature_immutability_and_serialization() -> None:
    assert issubclass(
        PlanStepExecutionTransitionDecisionCompositionInvariantError,
        PlanStepExecutionTransitionDecisionCompositionError,
    )
    signature = inspect.signature(PlanStepExecutionTransitionDecisionComposer.compose)
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
    with pytest.raises(TypeError, match="evidence_assessment_composer"):
        PlanStepExecutionTransitionDecisionComposer()  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="evidence_assessment_composer"):
        PlanStepExecutionTransitionDecisionComposer(
            evidence_assessment_composer=cast(Any, object())
        )
    with pytest.raises(TypeError, match="transition_decider"):
        PlanStepExecutionTransitionDecisionComposer(
            evidence_assessment_composer=RecordingWP039(),
            transition_decider=cast(Any, object()),
        )

    plan, run, delegated = canonical_wp039()
    result, _, _ = compose_from_wp039(plan, run, delegated)
    with pytest.raises(FrozenInstanceError):
        result.post_recording_transition_decision = None  # type: ignore[misc]
    assert json.loads(json.dumps(result.to_data())) == result.to_data()
    assert result.to_data()["assessment"] == delegated.assessment.to_data()
    assert result.to_data()["post_recording_assessment"] == (
        delegated.post_recording_assessment.to_data()  # type: ignore[union-attr]
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
def test_invalid_inputs_fail_before_wp039(position: int, invalid: object) -> None:
    plan, run, _ = no_assessment_wp039()
    wp039 = RecordingWP039()
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
        PlanStepExecutionTransitionDecisionComposer(
            evidence_assessment_composer=wp039
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
    assert wp039.calls == []


def test_no_assessment_preserves_wp039_and_skips_decider() -> None:
    plan, run, delegated = no_assessment_wp039()
    result, wp039, decider = compose_from_wp039(plan, run, delegated)
    assert len(wp039.calls) == 1
    assert decider.calls == []
    assert result.post_recording_assessment is None
    assert result.post_recording_transition_decision is None
    for item in fields(delegated):
        assert getattr(result, item.name) is getattr(delegated, item.name)


def test_exact_inputs_forwarded_to_wp039_once() -> None:
    plan, run, delegated = no_assessment_wp039()
    operation_input = capability_input()
    _, wp039, _ = compose_from_wp039(
        plan,
        run,
        delegated,
        execution_input=operation_input,
    )
    assert wp039.calls == [
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


def test_assessment_branch_uses_exact_recorded_run_step_and_assessment_once() -> None:
    plan, source_run, delegated = canonical_wp039()
    recording = delegated.execution_recording_result
    assessment = delegated.post_recording_assessment
    assert recording is not None and assessment is not None
    result, wp039, decider = compose_from_wp039(plan, source_run, delegated)
    assert len(wp039.calls) == 1
    assert decider.calls == [
        (
            plan,
            recording.recorded_run,
            plan.steps[1],
            assessment,
        )
    ]
    assert result.post_recording_assessment is assessment
    assert result.post_recording_transition_decision is not None
    assert (
        result.post_recording_transition_decision is not delegated.transition_decision
    )


def test_processed_a_and_post_recording_b_decision_remain_distinct() -> None:
    plan, source_run, delegated = canonical_wp039()
    result, _, decider = compose_from_wp039(plan, source_run, delegated)
    post = result.post_recording_transition_decision
    assert delegated.assessment.step_id == "a"
    assert delegated.transition_decision.step_id == "a"
    assert delegated.post_recording_assessment is not None
    assert delegated.post_recording_assessment.step_id == "b"
    assert decider.calls[0][2] is plan.steps[1]
    assert post is not None and post.step_id == "b"
    assert post.assessment_id == delegated.post_recording_assessment.assessment_id
    assert result.assessment is delegated.assessment
    assert result.transition_decision is delegated.transition_decision


def test_handler_unavailable_still_produces_exact_no_transition_decision() -> None:
    plan, source_run, delegated = canonical_wp039(handler_available=False)
    recording = delegated.execution_recording_result
    assert recording is not None
    assert selected_state(recording.recorded_run) is StepProgressState.NOT_STARTED
    result, _, decider = compose_from_wp039(plan, source_run, delegated)
    decision = result.post_recording_transition_decision
    assert len(decider.calls) == 1
    assert decision is not None
    assert decision.action is StepProgressTransitionAction.NO_TRANSITION
    assert decision.reason is StepProgressTransitionReason.STEP_NOT_STARTED
    assert result.progress_update is delegated.progress_update


@pytest.mark.parametrize(
    "outcome",
    [
        HandlerOutcome(ExecutionStatus.SUCCEEDED),
        HandlerOutcome(
            ExecutionStatus.FAILED,
            failure=ExecutionFailure("handler_failed", "failed"),
        ),
        HandlerOutcome(
            ExecutionStatus.REJECTED,
            failure=ExecutionFailure("handler_rejected", "rejected"),
        ),
    ],
)
def test_invoked_execution_statuses_share_one_decision_path(
    outcome: HandlerOutcome,
) -> None:
    plan, source_run, delegated = canonical_wp039(outcome=outcome)
    recording = delegated.execution_recording_result
    assert recording is not None
    before = recording.recorded_run.to_data()
    result, _, decider = compose_from_wp039(plan, source_run, delegated)
    assert len(decider.calls) == 1
    assert result.post_recording_transition_decision is not None
    assert result.post_recording_transition_decision.action is (
        StepProgressTransitionAction.NO_TRANSITION
    )
    assert recording.recorded_run.to_data() == before
    assert selected_state(recording.recorded_run) is StepProgressState.ACTIVE


@pytest.mark.parametrize(
    ("status", "expected_action"),
    [
        (StepOutcomeStatus.SATISFIED, StepProgressTransitionAction.TRANSITION),
        (
            StepOutcomeStatus.NOT_SATISFIED,
            StepProgressTransitionAction.NO_TRANSITION,
        ),
    ],
)
def test_transition_and_no_transition_decisions_are_both_preserved(
    status: StepOutcomeStatus,
    expected_action: StepProgressTransitionAction,
) -> None:
    plan, source_run, delegated = canonical_wp039(status=status)
    result, _, decider = compose_from_wp039(plan, source_run, delegated)
    decision = result.post_recording_transition_decision
    assert len(decider.calls) == 1
    assert decision is not None and decision.action is expected_action
    assert result.progress_update is delegated.progress_update
    assert result.advancement_result is delegated.advancement_result


@pytest.mark.parametrize(
    "mutation",
    ["wrong_type", "source", "presence", "recording", "assessment"],
)
def test_malformed_wp039_output_fails_before_decider(mutation: str) -> None:
    plan, source_run, delegated = canonical_wp039()
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
    elif mutation == "presence":
        malformed = unsafe_clone(delegated, post_recording_assessment=None)
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
    wp039 = RecordingWP039(forced=malformed)
    decider = RecordingDecider()
    with pytest.raises(PlanStepExecutionTransitionDecisionCompositionInvariantError):
        PlanStepExecutionTransitionDecisionComposer(
            evidence_assessment_composer=wp039,
            transition_decider=decider,
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
    assert decider.calls == []


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_type",
        "plan_id",
        "run_id",
        "revision",
        "step_id",
        "assessment_id",
        "source_state",
    ],
)
def test_malformed_decider_output_becomes_wp040_invariant(mutation: str) -> None:
    plan, source_run, delegated = canonical_wp039()
    recording = delegated.execution_recording_result
    assessment = delegated.post_recording_assessment
    assert recording is not None and assessment is not None
    canonical = RecordingDecider().decide(
        plan,
        recording.recorded_run,
        plan.steps[1],
        assessment,
    )
    malformed: object = canonical
    if mutation == "wrong_type":
        malformed = object()
    elif mutation in {"plan_id", "run_id", "step_id", "assessment_id"}:
        malformed = unsafe_clone(canonical, **{mutation: f"foreign-{mutation}"})
    elif mutation == "revision":
        malformed = unsafe_clone(
            canonical,
            observed_revision=canonical.observed_revision - 1,
        )
    else:
        malformed = unsafe_clone(
            canonical,
            source_state=StepProgressState.NOT_STARTED,
        )
    decider = RecordingDecider(forced=malformed)
    with pytest.raises(PlanStepExecutionTransitionDecisionCompositionInvariantError):
        compose_from_wp039(plan, source_run, delegated, decider=decider)
    assert len(decider.calls) == 1


def test_wp039_error_and_post_active_invocation_error_propagate_without_decision() -> (
    None
):
    plan, source_run, delegated = canonical_wp039()
    errors: list[Exception] = [
        PlanStepExecutionEvidenceAssessmentCompositionError("wp039 failed")
    ]
    start = delegated.execution_start_result
    assert start is not None and start.active_run is not None
    errors.append(
        PlanStepExecutionInvocationError(
            "handler exploded",
            active_run=start.active_run,
            activation_update_id=start.activation_update_id or "activation",
            execution_id=start.execution_id,
        )
    )
    for error in errors:
        wp039 = RecordingWP039(error=error)
        decider = RecordingDecider()
        with pytest.raises(type(error)) as caught:
            PlanStepExecutionTransitionDecisionComposer(
                evidence_assessment_composer=wp039,
                transition_decider=decider,
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
        assert caught.value is error
        assert len(wp039.calls) == 1
        assert decider.calls == []


def test_decider_error_propagates_once_without_fallback() -> None:
    plan, source_run, delegated = canonical_wp039()
    error = StepProgressTransitionError("decision failed")
    decider = RecordingDecider(error=error)
    with pytest.raises(StepProgressTransitionError) as caught:
        compose_from_wp039(plan, source_run, delegated, decider=decider)
    assert caught.value is error
    assert len(decider.calls) == 1


def test_exact_artifact_preservation_and_presence_invariant() -> None:
    plan, source_run, delegated = canonical_wp039()
    result, _, _ = compose_from_wp039(plan, source_run, delegated)
    for item in fields(delegated):
        assert getattr(result, item.name) is getattr(delegated, item.name)
    assert result.post_recording_assessment is delegated.post_recording_assessment
    with pytest.raises(PlanStepExecutionTransitionDecisionCompositionInvariantError):
        unsafe_clone(result, post_recording_transition_decision=None).__post_init__()


def test_wp040_has_no_forbidden_authority_dependencies() -> None:
    source = (
        Path(__file__).parents[1]
        / "iris"
        / "plan_step_execution_transition_decision_composition"
        / "composer.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "PlanStepEvidenceTransitionComposer",
        "PlanStepEvidenceAssessor",
        "StepProgressUpdateSynthesizer",
        "PlanStepProgressUpdatePreparer",
        "PlanRunReducer",
        "PlanRunController",
        "PlanStepProgressAdvancementComposer",
        "ExecutionCoordinator",
    ):
        assert forbidden not in source
