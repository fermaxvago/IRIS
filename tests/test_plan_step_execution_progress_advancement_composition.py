"""WP042 bounded post-recording progress-advancement composition."""

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
from iris.outcome_assessment import StepOutcomeStatus
from iris.plan_control import (
    ControlDecision,
    ControlDecisionKind,
    ControlProvenance,
    ControlReason,
)
from iris.plan_run_advancement import (
    PlanRunProgressAdvancementError,
    PlanRunProgressAdvancer,
    PlanRunProgressAdvanceResult,
)
from iris.plan_runs import PlanRun, StepProgressState, StepProgressUpdate
from iris.plan_step_execution_progress_advancement_composition import (
    PlanStepExecutionProgressAdvancementComposer,
    PlanStepExecutionProgressAdvancementCompositionError,
    PlanStepExecutionProgressAdvancementCompositionInvariantError,
    PlanStepExecutionProgressAdvancementCompositionResult,
)
from iris.plan_step_execution_progress_update_composition import (
    PlanStepExecutionProgressUpdateComposer,
    PlanStepExecutionProgressUpdateCompositionResult,
)
from iris.planning import Plan
from tests.test_plan_step_execution_evidence_assessment_composition import (
    BUDGET,
    CAPABILITY_AVAILABLE,
    CONTEXT_CREATED,
    capability_input,
    unsafe_clone,
)
from tests.test_plan_step_execution_progress_update_composition import (
    RecordingWP040,
    canonical_wp040,
    compose_from_wp040,
    no_decision_wp040,
)


class RecordingWP041(PlanStepExecutionProgressUpdateComposer):
    def __init__(
        self,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__(transition_decision_composer=RecordingWP040())
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
    ) -> PlanStepExecutionProgressUpdateCompositionResult:
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
        return cast(PlanStepExecutionProgressUpdateCompositionResult, self.forced)


class RecordingAdvancer(PlanRunProgressAdvancer):
    def __init__(
        self,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__()
        self.forced = forced
        self.error = error
        self.calls: list[tuple[Plan, PlanRun, StepProgressUpdate]] = []

    def advance(
        self,
        plan: Plan,
        run: PlanRun,
        update: StepProgressUpdate,
    ) -> PlanRunProgressAdvanceResult:
        self.calls.append((plan, run, update))
        if self.error is not None:
            raise self.error
        if self.forced is not None:
            return cast(PlanRunProgressAdvanceResult, self.forced)
        return super().advance(plan, run, update)


def canonical_wp041(
    *,
    status: StepOutcomeStatus = StepOutcomeStatus.SATISFIED,
    handler_available: bool = True,
) -> tuple[Plan, PlanRun, PlanStepExecutionProgressUpdateCompositionResult]:
    plan, source_run, wp040 = canonical_wp040(
        status=status,
        handler_available=handler_available,
    )
    result, _, _ = compose_from_wp040(plan, source_run, wp040)
    return plan, source_run, result


def no_update_wp041(
    *,
    decision_absent: bool,
) -> tuple[Plan, PlanRun, PlanStepExecutionProgressUpdateCompositionResult]:
    if decision_absent:
        plan, source_run, wp040 = no_decision_wp040()
    else:
        plan, source_run, wp040 = canonical_wp040(
            status=StepOutcomeStatus.NOT_SATISFIED
        )
    result, _, _ = compose_from_wp040(plan, source_run, wp040)
    assert result.post_recording_progress_update is None
    return plan, source_run, result


def compose_from_wp041(
    plan: Plan,
    run: PlanRun,
    delegated: object,
    *,
    advancer: RecordingAdvancer | None = None,
    execution_input: CapabilityExecutionInput | None = None,
) -> tuple[
    PlanStepExecutionProgressAdvancementCompositionResult,
    RecordingWP041,
    RecordingAdvancer,
]:
    wp041 = RecordingWP041(forced=delegated)
    actual_advancer = RecordingAdvancer() if advancer is None else advancer
    supplied_input = capability_input() if execution_input is None else execution_input
    result = PlanStepExecutionProgressAdvancementComposer(
        progress_update_composer=wp041,
        progress_advancer=actual_advancer,
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
    return result, wp041, actual_advancer


def canonical_advancement(
    plan: Plan,
    wp041: PlanStepExecutionProgressUpdateCompositionResult,
) -> PlanRunProgressAdvanceResult:
    recording = wp041.execution_recording_result
    update = wp041.post_recording_progress_update
    assert recording is not None and update is not None
    return PlanRunProgressAdvancer().advance(plan, recording.recorded_run, update)


def test_public_api_constructor_signature_immutability_and_serialization() -> None:
    assert issubclass(
        PlanStepExecutionProgressAdvancementCompositionInvariantError,
        PlanStepExecutionProgressAdvancementCompositionError,
    )
    signature = inspect.signature(PlanStepExecutionProgressAdvancementComposer.compose)
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
    with pytest.raises(TypeError, match="progress_update_composer"):
        PlanStepExecutionProgressAdvancementComposer()  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="progress_update_composer"):
        PlanStepExecutionProgressAdvancementComposer(
            progress_update_composer=cast(Any, object())
        )
    with pytest.raises(TypeError, match="progress_advancer"):
        PlanStepExecutionProgressAdvancementComposer(
            progress_update_composer=RecordingWP041(),
            progress_advancer=cast(Any, object()),
        )

    plan, run, delegated = canonical_wp041()
    result, _, _ = compose_from_wp041(plan, run, delegated)
    with pytest.raises(FrozenInstanceError):
        result.post_recording_advancement_result = None  # type: ignore[misc]
    assert json.loads(json.dumps(result.to_data())) == result.to_data()
    assert result.to_data()["post_recording_progress_update"] == (
        delegated.post_recording_progress_update.to_data()  # type: ignore[union-attr]
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
def test_invalid_inputs_fail_before_wp041(position: int, invalid: object) -> None:
    plan, run, delegated = no_update_wp041(decision_absent=True)
    wp041 = RecordingWP041(forced=delegated)
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
        PlanStepExecutionProgressAdvancementComposer(
            progress_update_composer=wp041
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
    assert wp041.calls == []


def test_exact_inputs_forwarded_to_wp041_once() -> None:
    plan, run, delegated = no_update_wp041(decision_absent=True)
    operation_input = capability_input()
    _, wp041, _ = compose_from_wp041(
        plan,
        run,
        delegated,
        execution_input=operation_input,
    )
    assert wp041.calls == [
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


@pytest.mark.parametrize("decision_absent", [True, False])
def test_no_update_preserves_wp041_and_skips_wp023(
    decision_absent: bool,
) -> None:
    plan, run, delegated = no_update_wp041(decision_absent=decision_absent)
    result, wp041, advancer = compose_from_wp041(plan, run, delegated)
    assert len(wp041.calls) == 1
    assert advancer.calls == []
    assert result.post_recording_progress_update is None
    assert result.post_recording_advancement_result is None
    for item in fields(delegated):
        assert getattr(result, item.name) is getattr(delegated, item.name)
    if decision_absent:
        assert result.post_recording_transition_decision is None
    else:
        assert result.post_recording_transition_decision is not None


def test_update_path_uses_exact_recorded_run_update_and_wp023_result_once() -> None:
    plan, source_run, delegated = canonical_wp041()
    recording = delegated.execution_recording_result
    update = delegated.post_recording_progress_update
    assert recording is not None and update is not None
    advancer = RecordingAdvancer()
    before = (plan.to_data(), source_run.to_data(), recording.recorded_run.to_data())

    result, wp041, actual_advancer = compose_from_wp041(
        plan,
        source_run,
        delegated,
        advancer=advancer,
    )

    assert len(wp041.calls) == 1
    assert actual_advancer.calls == [(plan, recording.recorded_run, update)]
    assert actual_advancer.calls[0][1] is not source_run
    assert actual_advancer.calls[0][1].revision > source_run.revision
    expected = canonical_advancement(plan, delegated)
    advancement = result.post_recording_advancement_result
    assert advancement is not None
    assert advancement.to_data() == expected.to_data()
    assert result.post_recording_progress_update is update
    assert (plan.to_data(), source_run.to_data(), recording.recorded_run.to_data()) == (
        before
    )


def test_exact_injected_wp023_result_identity_is_preserved() -> None:
    plan, source_run, delegated = canonical_wp041()
    exact = canonical_advancement(plan, delegated)
    result, _, advancer = compose_from_wp041(
        plan,
        source_run,
        delegated,
        advancer=RecordingAdvancer(forced=exact),
    )
    assert len(advancer.calls) == 1
    assert result.post_recording_advancement_result is exact


def test_successor_and_fresh_control_exact_postconditions() -> None:
    plan, source_run, delegated = canonical_wp041()
    recording = delegated.execution_recording_result
    update = delegated.post_recording_progress_update
    assert recording is not None and update is not None
    source = recording.recorded_run
    result, _, _ = compose_from_wp041(plan, source_run, delegated)
    advancement = result.post_recording_advancement_result
    assert advancement is not None
    updated = advancement.updated_run
    control = advancement.control_decision

    assert advancement.source_update_id == update.update_id
    assert advancement.source_revision == update.expected_revision == source.revision
    assert updated.plan_id == source.plan_id == plan.plan_id
    assert updated.run_id == source.run_id == update.run_id
    assert updated.goal_id == source.goal_id
    assert updated.revision == source.revision + 1
    assert updated.created_at == source.created_at
    assert updated.updated_at == update.updated_at
    assert updated.observations == source.observations
    assert updated.blockers == source.blockers
    source_progress = {item.step_id: item for item in source.step_progress}
    updated_progress = {item.step_id: item for item in updated.step_progress}
    assert source_progress.keys() == updated_progress.keys()
    target = updated_progress[update.step_id]
    assert target.state is update.new_state
    assert target.changed_at == update.updated_at
    assert target.evidence_ids == update.evidence_ids
    assert all(
        updated_progress[step_id] == progress
        for step_id, progress in source_progress.items()
        if step_id != update.step_id
    )
    assert control.plan_id == plan.plan_id
    assert control.run_id == updated.run_id
    assert control.observed_revision == updated.revision


def decision_for_kind(
    kind: ControlDecisionKind,
    run: PlanRun,
) -> ControlDecision:
    provenance = ControlProvenance("test.wp042.controller", "1")
    if kind is ControlDecisionKind.STEP_SELECTED:
        return ControlDecision(
            run.plan_id,
            run.run_id,
            run.revision,
            kind,
            ControlReason.ONLY_READY_STEP,
            provenance,
            candidate_step_ids=("c",),
            selected_step_id="c",
        )
    if kind is ControlDecisionKind.ACTIVE_WORK_PENDING:
        return ControlDecision(
            run.plan_id,
            run.run_id,
            run.revision,
            kind,
            ControlReason.ACTIVE_STEP_EXISTS,
            provenance,
            active_step_ids=("c",),
        )
    if kind is ControlDecisionKind.SELECTION_UNRESOLVED:
        return ControlDecision(
            run.plan_id,
            run.run_id,
            run.revision,
            kind,
            ControlReason.MULTIPLE_READY_UNRESOLVED,
            provenance,
            candidate_step_ids=("c", "d"),
        )
    reason = (
        ControlReason.RUN_CANNOT_ADVANCE
        if kind is ControlDecisionKind.RUN_CANNOT_ADVANCE
        else ControlReason.RUN_STRUCTURALLY_COMPLETE
    )
    return ControlDecision(
        run.plan_id,
        run.run_id,
        run.revision,
        kind,
        reason,
        provenance,
    )


@pytest.mark.parametrize("kind", list(ControlDecisionKind))
def test_all_control_decision_kinds_are_preserved_exactly_and_inertly(
    kind: ControlDecisionKind,
) -> None:
    plan, source_run, delegated = canonical_wp041()
    canonical = canonical_advancement(plan, delegated)
    decision = decision_for_kind(kind, canonical.updated_run)
    injected = replace(canonical, control_decision=decision)
    result, _, advancer = compose_from_wp041(
        plan,
        source_run,
        delegated,
        advancer=RecordingAdvancer(forced=injected),
    )
    advancement = result.post_recording_advancement_result
    assert len(advancer.calls) == 1
    assert advancement is injected
    assert advancement.control_decision is decision
    assert advancement.control_decision.kind is kind
    assert result.execution_request is delegated.execution_request
    assert result.execution_start_result is delegated.execution_start_result


def test_a_to_b_to_c_lineage_remains_distinct_and_c_is_inert() -> None:
    plan, source_run, delegated = canonical_wp041()
    canonical = canonical_advancement(plan, delegated)
    decision_c = decision_for_kind(
        ControlDecisionKind.STEP_SELECTED,
        canonical.updated_run,
    )
    injected = replace(canonical, control_decision=decision_c)
    result, _, _ = compose_from_wp041(
        plan,
        source_run,
        delegated,
        advancer=RecordingAdvancer(forced=injected),
    )
    assert result.assessment.step_id == "a"
    assert result.progress_update is not None
    assert result.progress_update.step_id == "a"
    assert result.post_recording_assessment is not None
    assert result.post_recording_assessment.step_id == "b"
    assert result.post_recording_progress_update is not None
    assert result.post_recording_progress_update.step_id == "b"
    advancement = result.post_recording_advancement_result
    assert advancement is not None
    assert advancement.control_decision.selected_step_id == "c"
    assert "c" not in {item.step_id for item in advancement.updated_run.step_progress}


@pytest.mark.parametrize(
    "mutation",
    ["wrong_type", "source", "presence", "recording", "update_revision"],
)
def test_malformed_wp041_output_fails_before_wp023(mutation: str) -> None:
    plan, source_run, delegated = canonical_wp041()
    recording = delegated.execution_recording_result
    update = delegated.post_recording_progress_update
    assert recording is not None and update is not None
    malformed: object = delegated
    if mutation == "wrong_type":
        malformed = object()
    elif mutation == "source":
        malformed = unsafe_clone(
            delegated,
            assessment=unsafe_clone(delegated.assessment, step_id="b"),
        )
    elif mutation == "presence":
        malformed = unsafe_clone(delegated, post_recording_progress_update=None)
    elif mutation == "recording":
        malformed = unsafe_clone(
            delegated,
            execution_recording_result=unsafe_clone(recording, step_id="a"),
        )
    else:
        malformed = unsafe_clone(
            delegated,
            post_recording_progress_update=unsafe_clone(
                update,
                expected_revision=update.expected_revision - 1,
            ),
        )
    advancer = RecordingAdvancer()
    with pytest.raises(PlanStepExecutionProgressAdvancementCompositionInvariantError):
        compose_from_wp041(
            plan,
            source_run,
            malformed,
            advancer=advancer,
        )
    assert advancer.calls == []


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_type",
        "source_update_id",
        "source_revision",
        "plan_id",
        "run_id",
        "goal_id",
        "revision",
        "created_at",
        "updated_at",
        "observations",
        "blockers",
        "progress_ids",
        "target",
        "unrelated",
        "control_plan",
        "control_run",
        "control_revision",
    ],
)
def test_malformed_wp023_output_becomes_wp042_invariant(mutation: str) -> None:
    plan, source_run, delegated = canonical_wp041()
    recording = delegated.execution_recording_result
    update = delegated.post_recording_progress_update
    assert recording is not None and update is not None
    canonical = canonical_advancement(plan, delegated)
    source = recording.recorded_run
    updated = canonical.updated_run
    control = canonical.control_decision
    malformed: object = canonical
    if mutation == "wrong_type":
        malformed = object()
    elif mutation == "source_update_id":
        malformed = unsafe_clone(canonical, source_update_id="other-update")
    elif mutation == "source_revision":
        malformed = unsafe_clone(canonical, source_revision=source.revision - 1)
    elif mutation == "plan_id":
        malformed = unsafe_clone(
            canonical,
            updated_run=unsafe_clone(updated, plan_id="other-plan"),
        )
    elif mutation == "run_id":
        malformed = unsafe_clone(
            canonical,
            updated_run=unsafe_clone(updated, run_id="other-run"),
        )
    elif mutation == "goal_id":
        malformed = unsafe_clone(
            canonical,
            updated_run=unsafe_clone(updated, goal_id="other-goal"),
        )
    elif mutation == "revision":
        malformed = unsafe_clone(
            canonical,
            updated_run=unsafe_clone(updated, revision=updated.revision + 1),
        )
    elif mutation == "created_at":
        malformed = unsafe_clone(
            canonical,
            updated_run=unsafe_clone(
                updated,
                created_at=updated.created_at + timedelta(seconds=1),
            ),
        )
    elif mutation == "updated_at":
        malformed = unsafe_clone(
            canonical,
            updated_run=unsafe_clone(
                updated,
                updated_at=updated.updated_at + timedelta(seconds=1),
            ),
        )
    elif mutation == "observations":
        malformed = unsafe_clone(
            canonical,
            updated_run=unsafe_clone(updated, observations=()),
        )
    elif mutation == "blockers":
        malformed = unsafe_clone(
            canonical,
            updated_run=unsafe_clone(updated, blockers=(object(),)),
        )
    elif mutation == "progress_ids":
        malformed = unsafe_clone(
            canonical,
            updated_run=unsafe_clone(
                updated,
                step_progress=updated.step_progress[:-1],
            ),
        )
    elif mutation == "target":
        progress = tuple(
            replace(item, state=StepProgressState.FAILED)
            if item.step_id == update.step_id
            else item
            for item in updated.step_progress
        )
        malformed = unsafe_clone(
            canonical,
            updated_run=unsafe_clone(updated, step_progress=progress),
        )
    elif mutation == "unrelated":
        progress = tuple(
            replace(item, changed_at=item.changed_at + timedelta(seconds=1))
            if item.step_id != update.step_id
            else item
            for item in updated.step_progress
        )
        malformed = unsafe_clone(
            canonical,
            updated_run=unsafe_clone(updated, step_progress=progress),
        )
    elif mutation == "control_plan":
        malformed = unsafe_clone(
            canonical,
            control_decision=unsafe_clone(control, plan_id="other-plan"),
        )
    elif mutation == "control_run":
        malformed = unsafe_clone(
            canonical,
            control_decision=unsafe_clone(control, run_id="other-run"),
        )
    else:
        malformed = unsafe_clone(
            canonical,
            control_decision=unsafe_clone(
                control,
                observed_revision=control.observed_revision + 1,
            ),
        )
    advancer = RecordingAdvancer(forced=malformed)
    with pytest.raises(PlanStepExecutionProgressAdvancementCompositionInvariantError):
        compose_from_wp041(
            plan,
            source_run,
            delegated,
            advancer=advancer,
        )
    assert len(advancer.calls) == 1


def test_wp041_and_wp023_errors_propagate_once_without_fallback() -> None:
    plan, source_run, delegated = canonical_wp041()
    upstream_error = RuntimeError("wp041 failed")
    wp041 = RecordingWP041(error=upstream_error)
    advancer = RecordingAdvancer()
    with pytest.raises(RuntimeError) as upstream_caught:
        PlanStepExecutionProgressAdvancementComposer(
            progress_update_composer=wp041,
            progress_advancer=advancer,
        ).compose(
            plan,
            source_run,
            "a",
            candidates=(),
            budget=BUDGET,
            created_at=CONTEXT_CREATED,
            availability=CAPABILITY_AVAILABLE,
        )
    assert upstream_caught.value is upstream_error
    assert len(wp041.calls) == 1
    assert advancer.calls == []

    advancement_error = PlanRunProgressAdvancementError("wp023 failed")
    failing_advancer = RecordingAdvancer(error=advancement_error)
    with pytest.raises(PlanRunProgressAdvancementError) as advancement_caught:
        compose_from_wp041(
            plan,
            source_run,
            delegated,
            advancer=failing_advancer,
        )
    assert advancement_caught.value is advancement_error
    assert len(failing_advancer.calls) == 1


def test_result_rejects_update_advancement_existence_violations() -> None:
    plan, source_run, delegated = canonical_wp041()
    result, _, _ = compose_from_wp041(plan, source_run, delegated)
    with pytest.raises(
        PlanStepExecutionProgressAdvancementCompositionInvariantError,
        match="both exist",
    ):
        unsafe_clone(result, post_recording_advancement_result=None).__post_init__()

    plan, source_run, no_update = no_update_wp041(decision_absent=False)
    exact = result.post_recording_advancement_result
    assert exact is not None
    with pytest.raises(
        PlanStepExecutionProgressAdvancementCompositionInvariantError,
        match="both exist",
    ):
        PlanStepExecutionProgressAdvancementCompositionResult(
            assessment=no_update.assessment,
            transition_decision=no_update.transition_decision,
            progress_update=no_update.progress_update,
            advancement_result=no_update.advancement_result,
            handling_preparation=no_update.handling_preparation,
            work_subject=no_update.work_subject,
            context_snapshot=no_update.context_snapshot,
            orchestration_decision=no_update.orchestration_decision,
            execution_request=no_update.execution_request,
            execution_binding=no_update.execution_binding,
            execution_start_result=no_update.execution_start_result,
            execution_recording_result=no_update.execution_recording_result,
            post_recording_assessment=no_update.post_recording_assessment,
            post_recording_transition_decision=(
                no_update.post_recording_transition_decision
            ),
            post_recording_progress_update=None,
            post_recording_advancement_result=exact,
        )


def test_repeated_invocations_do_not_claim_global_deduplication() -> None:
    plan, source_run, delegated = canonical_wp041()
    advancer = RecordingAdvancer()
    first, _, _ = compose_from_wp041(
        plan,
        source_run,
        delegated,
        advancer=advancer,
    )
    second, _, _ = compose_from_wp041(
        plan,
        source_run,
        delegated,
        advancer=advancer,
    )
    assert len(advancer.calls) == 2
    assert first.post_recording_advancement_result is not None
    assert second.post_recording_advancement_result is not None
    assert first.post_recording_advancement_result is not (
        second.post_recording_advancement_result
    )


def test_wp042_has_no_forbidden_authority_or_continuation_dependencies() -> None:
    source = (
        Path(__file__).parents[1]
        / "iris"
        / "plan_step_execution_progress_advancement_composition"
        / "composer.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "StepProgressUpdateSynthesizer",
        "PlanStepProgressUpdatePreparer",
        "PlanStepProgressAdvancementComposer",
        "PlanRunReducer",
        "PlanRunController",
        "PlanStepEvidenceAssessor",
        "PlanStepEvidenceTransitionComposer",
        "StepProgressTransitionDecider",
        "PlanStepHandlingPreparationComposer",
        "PlanStepWorkSubjectMaterializer",
        "PlanStepContextMaterializer",
        "PlanStepOrchestrationComposer",
        "PlanStepExecutionRequestMaterializer",
        "PlanStepExecutionBinder",
        "PlanStepExecutionStartCoordinator",
        "ExecutionCoordinator",
    ):
        assert forbidden not in source
