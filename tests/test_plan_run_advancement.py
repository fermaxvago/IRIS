"""Bounded PlanRun progress advancement tests for WP023."""

from __future__ import annotations

import builtins
import json
import socket
import subprocess
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

import iris.plan_run_advancement.advancer as advancer_module
from iris.plan_control import (
    ControlDecision,
    ControlDecisionKind,
    ExplicitPriorityStepSelectionPolicy,
    PlanControlInvariantError,
    PlanIdentityMismatchError,
    PlanRunController,
    StaleControlDecisionError,
)
from iris.plan_run_advancement import (
    PlanRunProgressAdvanceInvariantError,
    PlanRunProgressAdvancementError,
    PlanRunProgressAdvancer,
    PlanRunProgressAdvanceResult,
)
from iris.plan_runs import (
    ForeignEvidenceError,
    InvalidStepTransitionError,
    PlanObservation,
    PlanRun,
    PlanRunFactory,
    PlanRunReducer,
    RecordObservationUpdate,
    RunProvenance,
    StalePlanRunUpdateError,
    StepProgressState,
    StepProgressUpdate,
)
from iris.planning import Plan, PlanStep

BASE = datetime(2026, 9, 29, 16, tzinfo=UTC)
PROVENANCE = RunProvenance("test", "wp023", "tester")


def step(step_id: str, *, depends_on: tuple[str, ...] = ()) -> PlanStep:
    return PlanStep(
        step_id,
        f"Objective {step_id}",
        f"Expected {step_id}",
        depends_on,
    )


def make_plan(*steps: PlanStep, plan_id: str = "plan-1") -> Plan:
    return Plan(plan_id, "goal-1", (), steps)


def new_run(plan: Plan, *, run_id: str = "run-1") -> PlanRun:
    return PlanRunFactory(
        clock=lambda: BASE,
        run_id_factory=lambda: run_id,
    ).create(plan)


def later(run: PlanRun) -> datetime:
    return run.updated_at + timedelta(seconds=1)


def progress_update(
    run: PlanRun,
    step_id: str,
    state: StepProgressState,
    *,
    evidence_ids: tuple[str, ...] = (),
    update_id: str | None = None,
) -> StepProgressUpdate:
    return StepProgressUpdate(
        update_id or f"update-{run.revision}-{step_id}-{state.value}",
        run.run_id,
        run.revision,
        later(run),
        PROVENANCE,
        step_id,
        state,
        evidence_ids,
    )


def apply_progress(
    plan: Plan,
    run: PlanRun,
    step_id: str,
    state: StepProgressState,
) -> PlanRun:
    return PlanRunReducer().apply(plan, run, progress_update(run, step_id, state))


def record_evidence(
    plan: Plan,
    run: PlanRun,
    step_id: str,
    *,
    evidence_id: str | None = None,
) -> tuple[PlanRun, str]:
    selected_id = evidence_id or f"evidence-{run.revision}-{step_id}"
    observed_at = later(run)
    observation = PlanObservation(
        observation_id=selected_id,
        run_id=run.run_id,
        source="test",
        observed_at=observed_at,
        kind="outcome",
        step_id=step_id,
        data={"verified": True},
    )
    updated = PlanRunReducer().apply(
        plan,
        run,
        RecordObservationUpdate(
            f"record-{selected_id}",
            run.run_id,
            run.revision,
            observed_at,
            PROVENANCE,
            observation,
        ),
    )
    return updated, selected_id


def active_with_evidence(plan: Plan, run: PlanRun, step_id: str) -> tuple[PlanRun, str]:
    run = apply_progress(plan, run, step_id, StepProgressState.ACTIVE)
    return record_evidence(plan, run, step_id)


def finish_update(
    run: PlanRun,
    step_id: str,
    evidence_id: str,
    *,
    state: StepProgressState = StepProgressState.SUCCEEDED,
    update_id: str = "terminal-update",
) -> StepProgressUpdate:
    return progress_update(
        run,
        step_id,
        state,
        evidence_ids=(evidence_id,),
        update_id=update_id,
    )


class RecordingController(PlanRunController):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.runs: list[PlanRun] = []

    def decide(self, plan: Plan, run: PlanRun) -> ControlDecision:
        self.runs.append(run)
        return super().decide(plan, run)


class FailingController(PlanRunController):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def decide(self, plan: Plan, run: PlanRun) -> ControlDecision:
        self.calls += 1
        raise PlanControlInvariantError("injected controller failure")


class ForeignDecisionController(PlanRunController):
    def decide(self, plan: Plan, run: PlanRun) -> ControlDecision:
        return replace(super().decide(plan, run), plan_id="foreign-plan")


class StaleDecisionController(PlanRunController):
    def decide(self, plan: Plan, run: PlanRun) -> ControlDecision:
        return replace(super().decide(plan, run), observed_revision=run.revision - 1)


def test_public_api_activation_advances_once_and_recontrols_once() -> None:
    plan = make_plan(step("a"))
    run = new_run(plan)
    update = progress_update(run, "a", StepProgressState.ACTIVE)
    before = (plan.to_data(), run.to_data(), update.to_data())

    result = PlanRunProgressAdvancer().advance(plan, run, update)

    assert isinstance(result, PlanRunProgressAdvanceResult)
    assert isinstance(
        PlanRunProgressAdvanceInvariantError("x"),
        PlanRunProgressAdvancementError,
    )
    assert result.source_update_id == update.update_id
    assert result.source_revision == update.expected_revision == run.revision
    assert result.updated_run.revision == run.revision + 1
    assert result.control_decision.kind is ControlDecisionKind.ACTIVE_WORK_PENDING
    assert result.control_decision.active_step_ids == ("a",)
    assert result.control_decision.observed_revision == result.updated_run.revision
    assert (plan.to_data(), run.to_data(), update.to_data()) == before


@pytest.mark.parametrize("position", range(3))
def test_wrong_input_types_fail_before_reduction(position: int) -> None:
    plan = make_plan(step("a"))
    run = new_run(plan)
    update = progress_update(run, "a", StepProgressState.ACTIVE)
    arguments: list[object] = [plan, run, update]
    arguments[position] = object()

    with pytest.raises(TypeError):
        PlanRunProgressAdvancer().advance(*arguments)  # type: ignore[arg-type]


def test_constructor_rejects_non_controller() -> None:
    with pytest.raises(TypeError):
        PlanRunProgressAdvancer(controller=object())  # type: ignore[arg-type]


def test_completion_unlocks_exactly_one_dependency_without_activating_it() -> None:
    plan = make_plan(step("a"), step("b", depends_on=("a",)))
    run, evidence_id = active_with_evidence(plan, new_run(plan), "a")

    result = PlanRunProgressAdvancer().advance(
        plan, run, finish_update(run, "a", evidence_id)
    )

    assert result.control_decision.kind is ControlDecisionKind.STEP_SELECTED
    assert result.control_decision.selected_step_id == "b"
    progress = {item.step_id: item.state for item in result.updated_run.step_progress}
    assert progress == {
        "a": StepProgressState.SUCCEEDED,
        "b": StepProgressState.NOT_STARTED,
    }


def test_final_step_completion_is_structural_not_goal_completion() -> None:
    plan = make_plan(step("a"))
    run, evidence_id = active_with_evidence(plan, new_run(plan), "a")

    result = PlanRunProgressAdvancer().advance(
        plan, run, finish_update(run, "a", evidence_id)
    )

    assert result.control_decision.kind is ControlDecisionKind.RUN_STRUCTURALLY_COMPLETE
    assert "goal" not in result.control_decision.reason.value


def test_remaining_active_work_precedes_ready_candidates() -> None:
    plan = make_plan(step("a"), step("b"), step("c"))
    run = new_run(plan)
    run = apply_progress(plan, run, "a", StepProgressState.ACTIVE)
    run = apply_progress(plan, run, "b", StepProgressState.ACTIVE)
    run, evidence_id = record_evidence(plan, run, "a")

    result = PlanRunProgressAdvancer().advance(
        plan, run, finish_update(run, "a", evidence_id)
    )

    assert result.control_decision.kind is ControlDecisionKind.ACTIVE_WORK_PENDING
    assert result.control_decision.active_step_ids == ("b",)
    assert result.control_decision.candidate_step_ids == ("c",)


def test_failure_that_blocks_dependency_returns_cannot_advance() -> None:
    plan = make_plan(step("a"), step("b", depends_on=("a",)))
    run, evidence_id = active_with_evidence(plan, new_run(plan), "a")

    result = PlanRunProgressAdvancer().advance(
        plan,
        run,
        finish_update(
            run,
            "a",
            evidence_id,
            state=StepProgressState.FAILED,
        ),
    )

    assert result.control_decision.kind is ControlDecisionKind.RUN_CANNOT_ADVANCE


def test_multiple_ready_without_policy_remains_unresolved() -> None:
    plan = make_plan(
        step("a"),
        step("b", depends_on=("a",)),
        step("c", depends_on=("a",)),
    )
    run, evidence_id = active_with_evidence(plan, new_run(plan), "a")

    result = PlanRunProgressAdvancer().advance(
        plan, run, finish_update(run, "a", evidence_id)
    )

    assert result.control_decision.kind is ControlDecisionKind.SELECTION_UNRESOLVED
    assert result.control_decision.candidate_step_ids == ("b", "c")


def test_injected_controller_policy_exclusively_selects_multiple_ready() -> None:
    plan = make_plan(
        step("a"),
        step("b", depends_on=("a",)),
        step("c", depends_on=("a",)),
    )
    run, evidence_id = active_with_evidence(plan, new_run(plan), "a")
    controller = PlanRunController(
        controller_id="configured-controller",
        controller_version="9",
        selection_policy=ExplicitPriorityStepSelectionPolicy({"b": 1, "c": 2}),
    )

    result = PlanRunProgressAdvancer(controller=controller).advance(
        plan, run, finish_update(run, "a", evidence_id)
    )

    assert result.control_decision.kind is ControlDecisionKind.STEP_SELECTED
    assert result.control_decision.selected_step_id == "c"
    assert result.control_decision.provenance.controller_id == "configured-controller"
    assert result.control_decision.provenance.policy_id == "explicit_priority"


def test_stale_update_propagates_and_prevents_controller() -> None:
    plan = make_plan(step("a"))
    run = apply_progress(plan, new_run(plan), "a", StepProgressState.ACTIVE)
    stale = replace(
        progress_update(run, "a", StepProgressState.FAILED, evidence_ids=("x",)),
        expected_revision=run.revision - 1,
    )
    controller = RecordingController()

    with pytest.raises(StalePlanRunUpdateError):
        PlanRunProgressAdvancer(controller=controller).advance(plan, run, stale)
    assert controller.runs == []


def test_illegal_transition_propagates_and_prevents_controller() -> None:
    plan = make_plan(step("a"))
    run, evidence_id = record_evidence(plan, new_run(plan), "a")
    invalid = progress_update(
        run,
        "a",
        StepProgressState.SUCCEEDED,
        evidence_ids=(evidence_id,),
    )
    controller = RecordingController()

    with pytest.raises(InvalidStepTransitionError):
        PlanRunProgressAdvancer(controller=controller).advance(plan, run, invalid)
    assert controller.runs == []


def test_foreign_terminal_evidence_propagates_and_prevents_controller() -> None:
    plan = make_plan(step("a"))
    run = apply_progress(plan, new_run(plan), "a", StepProgressState.ACTIVE)
    invalid = finish_update(run, "a", "missing-evidence")
    controller = RecordingController()

    with pytest.raises(ForeignEvidenceError):
        PlanRunProgressAdvancer(controller=controller).advance(plan, run, invalid)
    assert controller.runs == []


def test_controller_failure_propagates_after_local_reduction_without_mutation() -> None:
    plan = make_plan(step("a"))
    run = new_run(plan)
    before = run.to_data()
    controller = FailingController()

    with pytest.raises(PlanControlInvariantError, match="injected"):
        PlanRunProgressAdvancer(controller=controller).advance(
            plan, run, progress_update(run, "a", StepProgressState.ACTIVE)
        )
    assert controller.calls == 1
    assert run.to_data() == before


@pytest.mark.parametrize(
    ("controller", "error"),
    [
        (ForeignDecisionController(), PlanIdentityMismatchError),
        (StaleDecisionController(), StaleControlDecisionError),
    ],
)
def test_resulting_controller_decision_is_validated_current(
    controller: PlanRunController, error: type[Exception]
) -> None:
    plan = make_plan(step("a"))
    run = new_run(plan)

    with pytest.raises(error):
        PlanRunProgressAdvancer(controller=controller).advance(
            plan, run, progress_update(run, "a", StepProgressState.ACTIVE)
        )


def test_reducer_and_controller_are_each_called_once_and_controller_gets_n_plus_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = make_plan(step("a"))
    run = new_run(plan)
    update = progress_update(run, "a", StepProgressState.ACTIVE)
    original_apply = PlanRunReducer.apply
    reducer_calls: list[tuple[Plan, PlanRun, StepProgressUpdate]] = []

    def counted_apply(
        reducer: PlanRunReducer,
        supplied_plan: Plan,
        supplied_run: PlanRun,
        supplied_update: StepProgressUpdate,
    ) -> PlanRun:
        reducer_calls.append((supplied_plan, supplied_run, supplied_update))
        return original_apply(reducer, supplied_plan, supplied_run, supplied_update)

    monkeypatch.setattr(advancer_module.PlanRunReducer, "apply", counted_apply)
    controller = RecordingController()

    result = PlanRunProgressAdvancer(controller=controller).advance(plan, run, update)

    assert reducer_calls == [(plan, run, update)]
    assert controller.runs == [result.updated_run]
    assert controller.runs[0] is result.updated_run
    assert controller.runs[0] is not run


def test_unexpected_reducer_revision_is_owned_advancement_invariant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = make_plan(step("a"))
    run = new_run(plan)
    controller = RecordingController()
    monkeypatch.setattr(
        advancer_module.PlanRunReducer,
        "apply",
        lambda _self, _plan, supplied_run, _update: supplied_run,
    )

    with pytest.raises(PlanRunProgressAdvanceInvariantError):
        PlanRunProgressAdvancer(controller=controller).advance(
            plan, run, progress_update(run, "a", StepProgressState.ACTIVE)
        )
    assert controller.runs == []


def test_result_is_frozen_and_serializes_stably() -> None:
    plan = make_plan(step("a"))
    run = new_run(plan)
    result = PlanRunProgressAdvancer().advance(
        plan, run, progress_update(run, "a", StepProgressState.ACTIVE)
    )

    with pytest.raises(FrozenInstanceError):
        result.source_revision = 99  # type: ignore[misc]
    assert result.to_data() == result.to_data()
    assert json.loads(json.dumps(result.to_data())) == result.to_data()


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"source_update_id": " "}, PlanRunProgressAdvanceInvariantError),
        ({"source_revision": -1}, PlanRunProgressAdvanceInvariantError),
        ({"source_revision": True}, TypeError),
        ({"updated_run": object()}, TypeError),
        ({"control_decision": object()}, TypeError),
    ],
)
def test_result_rejects_invalid_field_contracts(
    changes: dict[str, object], error: type[Exception]
) -> None:
    plan = make_plan(step("a"))
    run = new_run(plan)
    valid = PlanRunProgressAdvancer().advance(
        plan, run, progress_update(run, "a", StepProgressState.ACTIVE)
    )
    fields: dict[str, object] = {
        "source_update_id": valid.source_update_id,
        "source_revision": valid.source_revision,
        "updated_run": valid.updated_run,
        "control_decision": valid.control_decision,
    }
    fields.update(changes)

    with pytest.raises(error):
        PlanRunProgressAdvanceResult(**fields)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "decision_change",
    [
        {"plan_id": "foreign-plan"},
        {"run_id": "foreign-run"},
        {"observed_revision": 0},
    ],
)
def test_result_rejects_inconsistent_decision_lineage(
    decision_change: dict[str, object],
) -> None:
    plan = make_plan(step("a"))
    run = new_run(plan)
    valid = PlanRunProgressAdvancer().advance(
        plan, run, progress_update(run, "a", StepProgressState.ACTIVE)
    )

    with pytest.raises(PlanRunProgressAdvanceInvariantError):
        replace(
            valid, control_decision=replace(valid.control_decision, **decision_change)
        )


def test_result_rejects_updated_run_not_one_revision_after_source() -> None:
    plan = make_plan(step("a"))
    run = new_run(plan)
    valid = PlanRunProgressAdvancer().advance(
        plan, run, progress_update(run, "a", StepProgressState.ACTIVE)
    )

    with pytest.raises(PlanRunProgressAdvanceInvariantError):
        replace(valid, source_revision=valid.source_revision + 1)


def test_two_calls_are_deterministic_and_claim_no_exactly_once() -> None:
    plan = make_plan(step("a"))
    run = new_run(plan)
    update = progress_update(run, "a", StepProgressState.ACTIVE)

    first = PlanRunProgressAdvancer().advance(plan, run, update)
    second = PlanRunProgressAdvancer().advance(plan, run, update)

    assert first == second
    assert first.updated_run.revision == second.updated_run.revision == 1
    assert run.revision == 0


def test_default_advancement_performs_no_external_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = make_plan(step("a"))
    run = new_run(plan)
    update = progress_update(run, "a", StepProgressState.ACTIVE)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("external I/O is outside WP023")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)

    result = PlanRunProgressAdvancer().advance(plan, run, update)

    assert result.control_decision.kind is ControlDecisionKind.ACTIVE_WORK_PENDING
