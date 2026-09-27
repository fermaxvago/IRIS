"""One-shot PlanRun control-decision and selection-policy tests."""

from __future__ import annotations

import builtins
import json
import socket
import subprocess
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

import iris.plan_control.controller as controller_module
from iris.plan_control import (
    ControlDecision,
    ControlDecisionKind,
    ControlProvenance,
    ControlReason,
    ExplicitPriorityStepSelectionPolicy,
    NonCandidateSelectedStepError,
    PlanControlInvariantError,
    PlanIdentityMismatchError,
    PlanRunController,
    PolicyContractViolationError,
    RunIdentityMismatchError,
    StaleControlDecisionError,
    StepSelectionRequest,
    StepSelectionResult,
    StepSelectionResultKind,
    UnknownSelectedStepError,
    validate_control_decision_current,
)
from iris.plan_runs import (
    PlanObservation,
    PlanRun,
    PlanRunFactory,
    PlanRunIdentityError,
    PlanRunReducer,
    RecordObservationUpdate,
    RunProvenance,
    StepAvailability,
    StepProgressState,
    StepProgressUpdate,
    derive_step_availability,
)
from iris.planning import Plan, PlanStep

NOW = datetime(2026, 9, 27, 18, tzinfo=UTC)
RUN_PROVENANCE = RunProvenance("test", "test-control", "tester")


def step(step_id: str, *, depends_on: tuple[str, ...] = ()) -> PlanStep:
    return PlanStep(
        step_id,
        f"Objective {step_id}",
        f"Expected {step_id}",
        depends_on,
    )


def plan(*steps: PlanStep, plan_id: str = "plan-1") -> Plan:
    return Plan(plan_id, "goal-1", (), steps)


def new_run(selected_plan: Plan, *, run_id: str = "run-1") -> PlanRun:
    return PlanRunFactory(
        clock=lambda: NOW,
        run_id_factory=lambda: run_id,
    ).create(selected_plan)


def next_time(run: PlanRun) -> datetime:
    return run.updated_at + timedelta(seconds=1)


def activate(selected_plan: Plan, run: PlanRun, step_id: str) -> PlanRun:
    return PlanRunReducer().apply(
        selected_plan,
        run,
        StepProgressUpdate(
            f"activate-{run.revision}-{step_id}",
            run.run_id,
            run.revision,
            next_time(run),
            RUN_PROVENANCE,
            step_id,
            StepProgressState.ACTIVE,
        ),
    )


def finish(
    selected_plan: Plan,
    run: PlanRun,
    step_id: str,
    state: StepProgressState = StepProgressState.SUCCEEDED,
) -> PlanRun:
    progress = next(item for item in run.step_progress if item.step_id == step_id)
    if progress.state is StepProgressState.NOT_STARTED:
        run = activate(selected_plan, run, step_id)
    instant = next_time(run)
    evidence_id = f"evidence-{run.revision}-{step_id}"
    observation = PlanObservation(
        evidence_id,
        run.run_id,
        "test",
        instant,
        "outcome",
        step_id,
        data={"verified": True},
    )
    run = PlanRunReducer().apply(
        selected_plan,
        run,
        RecordObservationUpdate(
            f"observe-{run.revision}-{step_id}",
            run.run_id,
            run.revision,
            instant,
            RUN_PROVENANCE,
            observation,
        ),
    )
    return PlanRunReducer().apply(
        selected_plan,
        run,
        StepProgressUpdate(
            f"finish-{run.revision}-{step_id}",
            run.run_id,
            run.revision,
            next_time(run),
            RUN_PROVENANCE,
            step_id,
            state,
            (evidence_id,),
        ),
    )


class RecordingPolicy:
    policy_id = "recording_policy"
    policy_version = "1"

    def __init__(self, result: StepSelectionResult) -> None:
        self.result = result
        self.requests: list[StepSelectionRequest] = []

    def select(self, request: StepSelectionRequest) -> StepSelectionResult:
        self.requests.append(request)
        return self.result


class ExplodingPolicy:
    policy_id = "exploding_policy"
    policy_version = "1"

    def select(self, request: StepSelectionRequest) -> StepSelectionResult:
        raise AssertionError(f"policy must not be called: {request}")


def test_structurally_complete_returns_terminal_control_decision() -> None:
    selected_plan = plan(step("a"), step("b", depends_on=("a",)))
    run = finish(selected_plan, new_run(selected_plan), "a")
    run = finish(selected_plan, run, "b")

    decision = PlanRunController().decide(selected_plan, run)

    assert decision.kind is ControlDecisionKind.RUN_STRUCTURALLY_COMPLETE
    assert decision.reason is ControlReason.RUN_STRUCTURALLY_COMPLETE
    assert decision.selected_step_id is None
    assert decision.candidate_step_ids == ()
    assert decision.active_step_ids == ()


def test_one_active_returns_pending_without_selection() -> None:
    selected_plan = plan(step("a"))
    run = activate(selected_plan, new_run(selected_plan), "a")

    decision = PlanRunController().decide(selected_plan, run)

    assert decision.kind is ControlDecisionKind.ACTIVE_WORK_PENDING
    assert decision.active_step_ids == ("a",)
    assert decision.selected_step_id is None


def test_active_precedes_ready_and_policy_is_not_called() -> None:
    selected_plan = plan(step("a"), step("b"), step("c"))
    run = activate(selected_plan, new_run(selected_plan), "a")

    decision = PlanRunController(selection_policy=ExplodingPolicy()).decide(
        selected_plan, run
    )

    assert decision.kind is ControlDecisionKind.ACTIVE_WORK_PENDING
    assert decision.active_step_ids == ("a",)
    assert decision.candidate_step_ids == ("b", "c")


def test_multiple_active_steps_are_pending_not_invalid() -> None:
    selected_plan = plan(step("a"), step("b"))
    run = activate(selected_plan, new_run(selected_plan), "a")
    run = activate(selected_plan, run, "b")

    decision = PlanRunController().decide(selected_plan, run)

    assert decision.kind is ControlDecisionKind.ACTIVE_WORK_PENDING
    assert decision.active_step_ids == ("a", "b")


def test_dependency_failure_returns_cannot_advance_without_recovery() -> None:
    selected_plan = plan(step("a"), step("b", depends_on=("a",)))
    run = finish(
        selected_plan,
        new_run(selected_plan),
        "a",
        StepProgressState.FAILED,
    )

    decision = PlanRunController().decide(selected_plan, run)

    assert decision.kind is ControlDecisionKind.RUN_CANNOT_ADVANCE
    assert decision.reason is ControlReason.RUN_CANNOT_ADVANCE
    assert "goal" not in decision.reason.value


def test_one_ready_is_selected_without_calling_policy_or_activating() -> None:
    selected_plan = plan(step("a"))
    run = new_run(selected_plan)
    before = run.to_data()

    decision = PlanRunController(selection_policy=ExplodingPolicy()).decide(
        selected_plan, run
    )

    assert decision.kind is ControlDecisionKind.STEP_SELECTED
    assert decision.reason is ControlReason.ONLY_READY_STEP
    assert decision.selected_step_id == "a"
    assert decision.candidate_step_ids == ("a",)
    assert run.to_data() == before
    assert run.revision == 0
    assert run.step_progress[0].state is StepProgressState.NOT_STARTED
    assert (
        derive_step_availability(selected_plan, run, "a").availability
        is StepAvailability.READY
    )


def test_multiple_ready_policy_selects_and_records_all_candidates() -> None:
    selected_plan = plan(step("b"), step("a"))
    run = new_run(selected_plan)
    policy = RecordingPolicy(
        StepSelectionResult(
            StepSelectionResultKind.SELECTED,
            "test_choice",
            "b",
        )
    )

    decision = PlanRunController(selection_policy=policy).decide(selected_plan, run)

    assert decision.kind is ControlDecisionKind.STEP_SELECTED
    assert decision.reason is ControlReason.POLICY_SELECTED
    assert decision.selected_step_id == "b"
    assert decision.candidate_step_ids == ("a", "b")
    assert policy.requests[0].candidate_step_ids == ("a", "b")
    assert decision.provenance.policy_id == "recording_policy"


def test_policy_unresolved_is_valid_abstention() -> None:
    selected_plan = plan(step("a"), step("b"))
    policy = RecordingPolicy(
        StepSelectionResult(
            StepSelectionResultKind.UNRESOLVED,
            "insufficient_priority",
        )
    )

    decision = PlanRunController(selection_policy=policy).decide(
        selected_plan, new_run(selected_plan)
    )

    assert decision.kind is ControlDecisionKind.SELECTION_UNRESOLVED
    assert decision.reason is ControlReason.MULTIPLE_READY_UNRESOLVED
    assert decision.selected_step_id is None
    assert decision.candidate_step_ids == ("a", "b")


def test_no_policy_with_multiple_ready_is_unresolved_without_fallback() -> None:
    selected_plan = plan(step("z"), step("a"))

    decision = PlanRunController().decide(selected_plan, new_run(selected_plan))

    assert decision.kind is ControlDecisionKind.SELECTION_UNRESOLVED
    assert decision.candidate_step_ids == ("a", "z")
    assert decision.provenance.policy_id is None


def test_policy_selecting_unknown_step_is_rejected() -> None:
    selected_plan = plan(step("a"), step("b"))
    policy = RecordingPolicy(
        StepSelectionResult(StepSelectionResultKind.SELECTED, "bad_choice", "x")
    )

    with pytest.raises(UnknownSelectedStepError, match="unknown step x"):
        PlanRunController(selection_policy=policy).decide(
            selected_plan, new_run(selected_plan)
        )


def test_policy_selecting_known_non_candidate_is_rejected() -> None:
    selected_plan = plan(
        step("a"),
        step("b"),
        step("c", depends_on=("a",)),
    )
    policy = RecordingPolicy(
        StepSelectionResult(StepSelectionResultKind.SELECTED, "bad_choice", "c")
    )

    with pytest.raises(NonCandidateSelectedStepError, match="non-candidate step c"):
        PlanRunController(selection_policy=policy).decide(
            selected_plan, new_run(selected_plan)
        )


def test_non_result_policy_output_is_contract_violation() -> None:
    class MalformedPolicy:
        policy_id = "malformed_policy"
        policy_version = "1"

        def select(self, request: StepSelectionRequest) -> Any:
            return {"selected_step_id": request.candidate_step_ids[0]}

    selected_plan = plan(step("a"), step("b"))
    with pytest.raises(PolicyContractViolationError, match="StepSelectionResult"):
        PlanRunController(selection_policy=MalformedPolicy()).decide(
            selected_plan, new_run(selected_plan)
        )


def test_invalid_policy_provenance_is_contract_violation() -> None:
    class BadProvenancePolicy:
        policy_id = " bad "
        policy_version = "1"

        def select(self, request: StepSelectionRequest) -> StepSelectionResult:
            raise AssertionError(request)

    selected_plan = plan(step("a"), step("b"))
    with pytest.raises(PolicyContractViolationError, match="provenance"):
        PlanRunController(selection_policy=BadProvenancePolicy()).decide(
            selected_plan, new_run(selected_plan)
        )


def test_explicit_priority_selects_unique_highest() -> None:
    selected_plan = plan(step("a"), step("b"))
    policy = ExplicitPriorityStepSelectionPolicy({"a": 10, "b": 20})

    decision = PlanRunController(selection_policy=policy).decide(
        selected_plan, new_run(selected_plan)
    )

    assert decision.kind is ControlDecisionKind.STEP_SELECTED
    assert decision.selected_step_id == "b"


def test_tied_explicit_priority_abstains_without_alphabetical_fallback() -> None:
    selected_plan = plan(step("a"), step("b"))
    policy = ExplicitPriorityStepSelectionPolicy({"a": 20, "b": 20})

    decision = PlanRunController(selection_policy=policy).decide(
        selected_plan, new_run(selected_plan)
    )

    assert decision.kind is ControlDecisionKind.SELECTION_UNRESOLVED
    assert decision.selected_step_id is None


def test_missing_explicit_priority_abstains() -> None:
    selected_plan = plan(step("a"), step("b"))
    policy = ExplicitPriorityStepSelectionPolicy({"a": 20})

    decision = PlanRunController(selection_policy=policy).decide(
        selected_plan, new_run(selected_plan)
    )

    assert decision.kind is ControlDecisionKind.SELECTION_UNRESOLVED


def test_policy_configuration_is_copied_and_immutable() -> None:
    source = {"a": 10, "b": 20}
    policy = ExplicitPriorityStepSelectionPolicy(source)
    source["a"] = 100

    assert dict(policy.priorities) == {"a": 10, "b": 20}
    with pytest.raises(TypeError):
        policy.priorities["a"] = 100  # type: ignore[index]


def test_selection_request_rejects_empty_singleton_and_duplicate_candidates() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        StepSelectionRequest("plan-1", "run-1", 0, ())
    with pytest.raises(ValueError, match="at least 2"):
        StepSelectionRequest("plan-1", "run-1", 0, ("a",))
    with pytest.raises(ValueError, match="distinct"):
        StepSelectionRequest("plan-1", "run-1", 0, ("a", "a"))


def test_selection_result_enforces_selected_id_shape() -> None:
    with pytest.raises(PlanControlInvariantError, match="requires"):
        StepSelectionResult(StepSelectionResultKind.SELECTED, "chosen")
    with pytest.raises(PlanControlInvariantError, match="cannot contain"):
        StepSelectionResult(
            StepSelectionResultKind.UNRESOLVED,
            "tie",
            "a",
        )


def test_decision_enforces_kind_reason_and_selected_id_shape() -> None:
    provenance = ControlProvenance("controller")
    with pytest.raises(PlanControlInvariantError, match="requires selected"):
        ControlDecision(
            "plan-1",
            "run-1",
            0,
            ControlDecisionKind.STEP_SELECTED,
            ControlReason.ONLY_READY_STEP,
            provenance,
            ("a",),
        )
    with pytest.raises(PlanControlInvariantError, match="incompatible reason"):
        ControlDecision(
            "plan-1",
            "run-1",
            0,
            ControlDecisionKind.RUN_CANNOT_ADVANCE,
            ControlReason.RUN_STRUCTURALLY_COMPLETE,
            provenance,
        )


def test_candidate_and_active_ids_are_sorted_for_serialization_not_priority() -> None:
    decision = ControlDecision(
        "plan-1",
        "run-1",
        0,
        ControlDecisionKind.ACTIVE_WORK_PENDING,
        ControlReason.ACTIVE_STEP_EXISTS,
        ControlProvenance("controller"),
        ("z", "a"),
        None,
        ("d", "b"),
    )

    assert decision.candidate_step_ids == ("a", "z")
    assert decision.active_step_ids == ("b", "d")
    assert decision.to_data()["candidate_step_ids"] == ["a", "z"]


def test_negative_and_boolean_revisions_are_rejected() -> None:
    with pytest.raises(ValueError, match="nonnegative"):
        StepSelectionRequest("plan-1", "run-1", -1, ("a", "b"))
    with pytest.raises(TypeError, match="integer"):
        StepSelectionRequest("plan-1", "run-1", True, ("a", "b"))


def test_control_provenance_requires_policy_id_for_policy_version() -> None:
    with pytest.raises(ValueError, match="requires policy_id"):
        ControlProvenance("controller", policy_version="1")


def test_decision_validation_accepts_current_decision() -> None:
    selected_plan = plan(step("a"))
    run = new_run(selected_plan)
    decision = PlanRunController().decide(selected_plan, run)

    assert validate_control_decision_current(selected_plan, run, decision) is None


def test_stale_decision_is_rejected_without_recalculation() -> None:
    selected_plan = plan(step("a"))
    old_run = new_run(selected_plan)
    decision = PlanRunController().decide(selected_plan, old_run)
    current_run = activate(selected_plan, old_run, "a")

    with pytest.raises(StaleControlDecisionError, match="current revision is 1"):
        validate_control_decision_current(selected_plan, current_run, decision)


def test_decision_for_wrong_run_is_rejected() -> None:
    selected_plan = plan(step("a"))
    first = new_run(selected_plan, run_id="run-1")
    second = new_run(selected_plan, run_id="run-2")
    decision = PlanRunController().decide(selected_plan, first)

    with pytest.raises(RunIdentityMismatchError, match="different PlanRun"):
        validate_control_decision_current(selected_plan, second, decision)


def test_decision_for_wrong_plan_is_rejected() -> None:
    first_plan = plan(step("a"), plan_id="plan-1")
    second_plan = plan(step("a"), plan_id="plan-2")
    decision = PlanRunController().decide(first_plan, new_run(first_plan))
    foreign = replace(decision, plan_id="plan-1")

    with pytest.raises(PlanIdentityMismatchError, match="different Plan"):
        validate_control_decision_current(
            second_plan,
            new_run(second_plan),
            foreign,
        )


def test_decide_is_deterministic_and_models_serialize_stably() -> None:
    selected_plan = plan(step("b"), step("a"))
    run = new_run(selected_plan)
    policy = ExplicitPriorityStepSelectionPolicy({"a": 1, "b": 2})
    controller = PlanRunController(selection_policy=policy)

    first = controller.decide(selected_plan, run)
    second = controller.decide(selected_plan, run)

    assert first == second
    assert json.dumps(first.to_data(), sort_keys=True) == json.dumps(
        second.to_data(), sort_keys=True
    )


def test_public_models_are_frozen() -> None:
    request = StepSelectionRequest("plan-1", "run-1", 0, ("a", "b"))
    result = StepSelectionResult(
        StepSelectionResultKind.SELECTED,
        "test_choice",
        "a",
    )
    decision = ControlDecision(
        "plan-1",
        "run-1",
        0,
        ControlDecisionKind.STEP_SELECTED,
        ControlReason.POLICY_SELECTED,
        ControlProvenance("controller", policy_id="policy"),
        ("a", "b"),
        "a",
    )
    with pytest.raises(FrozenInstanceError):
        request.observed_revision = 1  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.reason = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        decision.observed_revision = 1  # type: ignore[misc]


def test_controller_delegates_plan_run_validation_to_wp012() -> None:
    selected_plan = plan(step("a"))
    inconsistent = replace(new_run(selected_plan), goal_id="goal-other")

    with pytest.raises(PlanRunIdentityError, match="different Goal"):
        PlanRunController().decide(selected_plan, inconsistent)


def test_controller_uses_canonical_wp012_projections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_plan = plan(step("a"))
    run = new_run(selected_plan)
    calls = {"availability": 0, "condition": 0}
    original_availability = controller_module.derive_availability
    original_condition = controller_module.derive_run_condition

    def availability_spy(observed_plan: Plan, observed_run: PlanRun):
        calls["availability"] += 1
        return original_availability(observed_plan, observed_run)

    def condition_spy(observed_plan: Plan, observed_run: PlanRun):
        calls["condition"] += 1
        return original_condition(observed_plan, observed_run)

    monkeypatch.setattr(controller_module, "derive_availability", availability_spy)
    monkeypatch.setattr(controller_module, "derive_run_condition", condition_spy)

    PlanRunController().decide(selected_plan, run)

    assert calls == {"availability": 1, "condition": 1}


def test_controller_has_no_filesystem_network_subprocess_or_runtime_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_plan = plan(step("a"))
    run = new_run(selected_plan)

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError(f"unexpected side effect: {args}, {kwargs}")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)

    decision = PlanRunController().decide(selected_plan, run)

    assert decision.kind is ControlDecisionKind.STEP_SELECTED


def test_decision_does_not_copy_plan_or_run_payloads() -> None:
    selected_plan = plan(step("a"))
    decision = PlanRunController().decide(selected_plan, new_run(selected_plan))

    serialized = decision.to_data()
    assert "plan" not in serialized
    assert "run" not in serialized
    assert "execution_request" not in serialized
    assert "handling_need" not in serialized
