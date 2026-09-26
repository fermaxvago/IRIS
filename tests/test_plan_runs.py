"""PlanRun state, reducer, availability, and side-effect-boundary tests."""

from __future__ import annotations

import builtins
import json
import socket
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from iris.plan_runs import (
    AddBlockerUpdate,
    DuplicateRunIdentityError,
    ForeignEvidenceError,
    InvalidBlockerOperationError,
    InvalidStepTransitionError,
    PlanBlocker,
    PlanBlockerState,
    PlanObservation,
    PlanRun,
    PlanRunCondition,
    PlanRunFactory,
    PlanRunIdentityError,
    PlanRunInvariantError,
    PlanRunReducer,
    RecordObservationUpdate,
    ResolveBlockerUpdate,
    RunProvenance,
    StalePlanRunUpdateError,
    StepAvailability,
    StepProgress,
    StepProgressState,
    StepProgressUpdate,
    UnknownPlanStepError,
    derive_availability,
    derive_run_condition,
    derive_step_availability,
    validate_plan_run,
)
from iris.planning import Plan, PlanStep

NOW = datetime(2026, 9, 26, 12, tzinfo=UTC)
PROVENANCE = RunProvenance("controller", "controller-1", "user-1")


def step(step_id: str, *, depends_on: tuple[str, ...] = ()) -> PlanStep:
    return PlanStep(
        step_id=step_id,
        objective=f"Objective {step_id}",
        expected_outcome=f"Expected {step_id}",
        depends_on=depends_on,
    )


def chain_plan() -> Plan:
    return Plan(
        "plan-1",
        "goal-1",
        (),
        (step("a"), step("b", depends_on=("a",))),
    )


def fork_plan() -> Plan:
    return Plan(
        "plan-1",
        "goal-1",
        (),
        (
            step("a"),
            step("b", depends_on=("a",)),
            step("c", depends_on=("a",)),
        ),
    )


def diamond_plan() -> Plan:
    return Plan(
        "plan-1",
        "goal-1",
        (),
        (
            step("a"),
            step("b", depends_on=("a",)),
            step("c", depends_on=("a",)),
            step("d", depends_on=("b", "c")),
        ),
    )


def independent_plan() -> Plan:
    return Plan("plan-1", "goal-1", (), (step("a"), step("b")))


def new_run(plan: Plan | None = None, *, run_id: str = "run-1") -> PlanRun:
    selected = chain_plan() if plan is None else plan
    return PlanRunFactory(
        clock=lambda: NOW,
        run_id_factory=lambda: run_id,
    ).create(selected)


def update_time(run: PlanRun) -> datetime:
    return run.updated_at + timedelta(seconds=1)


def activate(
    plan: Plan, run: PlanRun, step_id: str, *, update_id: str | None = None
) -> PlanRun:
    return PlanRunReducer().apply(
        plan,
        run,
        StepProgressUpdate(
            update_id or f"update-{run.revision + 1}",
            run.run_id,
            run.revision,
            update_time(run),
            PROVENANCE,
            step_id,
            StepProgressState.ACTIVE,
        ),
    )


def record_observation(
    plan: Plan,
    run: PlanRun,
    step_id: str | None,
    *,
    observation_id: str | None = None,
) -> tuple[PlanRun, str]:
    instant = update_time(run)
    selected_id = observation_id or f"observation-{run.revision + 1}"
    observation = PlanObservation(
        observation_id=selected_id,
        run_id=run.run_id,
        step_id=step_id,
        source="test_adapter",
        source_reference="source-1",
        observed_at=instant,
        kind="test_evidence",
        data={"located": True, "items": ["b", "a"]},
    )
    result = PlanRunReducer().apply(
        plan,
        run,
        RecordObservationUpdate(
            f"update-{run.revision + 1}",
            run.run_id,
            run.revision,
            instant,
            PROVENANCE,
            observation,
        ),
    )
    return result, selected_id


def terminal(
    plan: Plan,
    run: PlanRun,
    step_id: str,
    state: StepProgressState,
    evidence_id: str,
) -> PlanRun:
    return PlanRunReducer().apply(
        plan,
        run,
        StepProgressUpdate(
            f"update-{run.revision + 1}",
            run.run_id,
            run.revision,
            update_time(run),
            PROVENANCE,
            step_id,
            state,
            (evidence_id,),
        ),
    )


def finish(
    plan: Plan,
    run: PlanRun,
    step_id: str,
    state: StepProgressState = StepProgressState.SUCCEEDED,
) -> PlanRun:
    if next(item for item in run.step_progress if item.step_id == step_id).state is (
        StepProgressState.NOT_STARTED
    ):
        run = activate(plan, run, step_id)
    run, evidence_id = record_observation(plan, run, step_id)
    return terminal(plan, run, step_id, state, evidence_id)


def add_blocker(
    plan: Plan,
    run: PlanRun,
    step_id: str,
    *,
    blocker_id: str = "blocker-1",
) -> PlanRun:
    instant = update_time(run)
    blocker = PlanBlocker(
        blocker_id=blocker_id,
        run_id=run.run_id,
        step_id=step_id,
        kind="external_precondition",
        reason="Required external fact is unavailable.",
        provenance=PROVENANCE,
        created_at=instant,
    )
    return PlanRunReducer().apply(
        plan,
        run,
        AddBlockerUpdate(
            f"update-{run.revision + 1}",
            run.run_id,
            run.revision,
            instant,
            PROVENANCE,
            blocker,
        ),
    )


def progress(run: PlanRun, step_id: str) -> StepProgress:
    return next(item for item in run.step_progress if item.step_id == step_id)


def availability(plan: Plan, run: PlanRun, step_id: str) -> StepAvailability:
    return derive_step_availability(plan, run, step_id).availability


def test_initial_run_derives_ready_waiting_and_open() -> None:
    plan = fork_plan()
    run = new_run(plan)

    assert run.revision == 0
    assert all(
        item.state is StepProgressState.NOT_STARTED for item in run.step_progress
    )
    assert availability(plan, run, "a") is StepAvailability.READY
    assert availability(plan, run, "b") is StepAvailability.WAITING_DEPENDENCIES
    assert availability(plan, run, "c") is StepAvailability.WAITING_DEPENDENCIES
    assert derive_run_condition(plan, run).condition is PlanRunCondition.OPEN
    assert run.observations == ()
    assert run.blockers == ()


def test_activate_root_increments_revision_without_mutating_plan_or_old_run() -> None:
    plan = chain_plan()
    original_plan = plan.to_data()
    old = new_run(plan)

    new = activate(plan, old, "a")

    assert old.revision == 0
    assert progress(old, "a").state is StepProgressState.NOT_STARTED
    assert new.revision == 1
    assert progress(new, "a").state is StepProgressState.ACTIVE
    assert availability(plan, new, "a") is StepAvailability.ACTIVE
    assert new.run_id == old.run_id
    assert new.created_at == old.created_at
    assert plan.to_data() == original_plan


def test_observation_is_append_only_and_does_not_complete_active_step() -> None:
    plan = chain_plan()
    active = activate(plan, new_run(plan), "a")

    observed, observation_id = record_observation(plan, active, "a")

    assert active.observations == ()
    assert [item.observation_id for item in observed.observations] == [observation_id]
    assert progress(observed, "a").state is StepProgressState.ACTIVE
    assert observed.revision == active.revision + 1


def test_success_with_existing_evidence_releases_dependents() -> None:
    plan = fork_plan()
    run = activate(plan, new_run(plan), "a")
    run, evidence_id = record_observation(plan, run, "a")

    succeeded = terminal(plan, run, "a", StepProgressState.SUCCEEDED, evidence_id)

    assert progress(succeeded, "a").evidence_ids == (evidence_id,)
    assert availability(plan, succeeded, "a") is StepAvailability.TERMINAL
    assert availability(plan, succeeded, "b") is StepAvailability.READY
    assert availability(plan, succeeded, "c") is StepAvailability.READY


def test_terminal_transition_without_evidence_is_rejected() -> None:
    run = activate(chain_plan(), new_run(), "a")
    with pytest.raises(ValueError, match="requires evidence"):
        StepProgressUpdate(
            "update-terminal",
            run.run_id,
            run.revision,
            update_time(run),
            PROVENANCE,
            "a",
            StepProgressState.SUCCEEDED,
        )


def test_failed_root_blocks_dependents_without_fabricating_blockers() -> None:
    plan = fork_plan()
    run = finish(plan, new_run(plan), "a", StepProgressState.FAILED)

    assert availability(plan, run, "a") is StepAvailability.TERMINAL
    assert availability(plan, run, "b") is StepAvailability.BLOCKED
    assert availability(plan, run, "c") is StepAvailability.BLOCKED
    assert derive_step_availability(plan, run, "b").failed_dependency_ids == ("a",)
    assert run.blockers == ()


def test_independent_branch_keeps_run_open_after_other_branch_fails() -> None:
    plan = independent_plan()
    run = finish(plan, new_run(plan), "a", StepProgressState.FAILED)

    assert availability(plan, run, "b") is StepAvailability.READY
    assert derive_run_condition(plan, run).condition is PlanRunCondition.OPEN


def test_dependency_failure_can_make_run_unable_to_advance() -> None:
    plan = chain_plan()
    run = finish(plan, new_run(plan), "a", StepProgressState.FAILED)

    result = derive_run_condition(plan, run)
    assert availability(plan, run, "b") is StepAvailability.BLOCKED
    assert result.condition is PlanRunCondition.CANNOT_ADVANCE
    assert "goal" not in result.to_data()


def test_all_succeeded_is_structurally_complete_not_goal_satisfaction() -> None:
    plan = chain_plan()
    run = finish(plan, new_run(plan), "a")
    run = finish(plan, run, "b")

    result = derive_run_condition(plan, run)
    assert result.condition is PlanRunCondition.STRUCTURALLY_COMPLETE
    assert set(result.to_data()) == {"run_id", "revision", "condition"}


def test_explicit_blocker_blocks_then_resolution_restores_ready() -> None:
    plan = chain_plan()
    initial = new_run(plan)
    blocked = add_blocker(plan, initial, "a")

    assert progress(blocked, "a").state is StepProgressState.NOT_STARTED
    assert availability(plan, blocked, "a") is StepAvailability.BLOCKED
    assert blocked.blockers[0].state is PlanBlockerState.ACTIVE

    resolved = PlanRunReducer().apply(
        plan,
        blocked,
        ResolveBlockerUpdate(
            "update-resolve",
            blocked.run_id,
            blocked.revision,
            update_time(blocked),
            PROVENANCE,
            "blocker-1",
        ),
    )
    assert blocked.blockers[0].state is PlanBlockerState.ACTIVE
    assert resolved.blockers[0].state is PlanBlockerState.RESOLVED
    assert availability(plan, resolved, "a") is StepAvailability.READY


def test_blocker_cannot_be_added_to_active_or_terminal_step() -> None:
    plan = chain_plan()
    active = activate(plan, new_run(plan), "a")
    instant = update_time(active)
    blocker = PlanBlocker(
        "blocker-active",
        active.run_id,
        "a",
        "external_precondition",
        "Too late to block initiation.",
        PROVENANCE,
        instant,
    )
    with pytest.raises(InvalidBlockerOperationError, match="NOT_STARTED"):
        PlanRunReducer().apply(
            plan,
            active,
            AddBlockerUpdate(
                "update-block-active",
                active.run_id,
                active.revision,
                instant,
                PROVENANCE,
                blocker,
            ),
        )


def test_dependency_ordering_rejects_activation_before_ready() -> None:
    plan = chain_plan()
    run = new_run(plan)
    with pytest.raises(InvalidStepTransitionError, match="waiting_dependencies"):
        activate(plan, run, "b")
    assert run.revision == 0


@pytest.mark.parametrize(
    "terminal_state", [StepProgressState.SUCCEEDED, StepProgressState.FAILED]
)
def test_terminal_states_cannot_be_reopened(terminal_state: StepProgressState) -> None:
    plan = chain_plan()
    run = finish(plan, new_run(plan), "a", terminal_state)
    with pytest.raises(InvalidStepTransitionError, match="illegal transition"):
        activate(plan, run, "a")


def test_stale_update_is_rejected_without_mutation() -> None:
    plan = chain_plan()
    run = activate(plan, new_run(plan), "a")
    stale = StepProgressUpdate(
        "update-stale",
        run.run_id,
        run.revision - 1,
        update_time(run),
        PROVENANCE,
        "b",
        StepProgressState.ACTIVE,
    )
    before = run.to_data()
    with pytest.raises(StalePlanRunUpdateError, match="current revision"):
        PlanRunReducer().apply(plan, run, stale)
    assert run.to_data() == before


def test_update_for_wrong_run_is_rejected() -> None:
    plan = chain_plan()
    run = new_run(plan)
    update = StepProgressUpdate(
        "update-wrong-run",
        "run-foreign",
        run.revision,
        update_time(run),
        PROVENANCE,
        "a",
        StepProgressState.ACTIVE,
    )
    with pytest.raises(PlanRunIdentityError, match="different PlanRun"):
        PlanRunReducer().apply(plan, run, update)


def test_unknown_step_update_is_rejected() -> None:
    plan = chain_plan()
    run = new_run(plan)
    update = StepProgressUpdate(
        "update-unknown-step",
        run.run_id,
        run.revision,
        update_time(run),
        PROVENANCE,
        "unknown",
        StepProgressState.ACTIVE,
    )
    with pytest.raises(UnknownPlanStepError, match="unknown"):
        PlanRunReducer().apply(plan, run, update)


def test_foreign_or_missing_evidence_is_rejected() -> None:
    plan = chain_plan()
    active = activate(plan, new_run(plan), "a")
    update = StepProgressUpdate(
        "update-foreign-evidence",
        active.run_id,
        active.revision,
        update_time(active),
        PROVENANCE,
        "a",
        StepProgressState.SUCCEEDED,
        ("observation-from-other-run",),
    )
    with pytest.raises(ForeignEvidenceError, match="unknown evidence"):
        PlanRunReducer().apply(plan, active, update)


def test_recording_observation_for_foreign_run_is_rejected() -> None:
    plan = chain_plan()
    run = new_run(plan)
    instant = update_time(run)
    foreign = PlanObservation(
        "observation-foreign",
        "run-foreign",
        "test_adapter",
        instant,
        "test_evidence",
        step_id="a",
    )
    update = RecordObservationUpdate(
        "update-foreign-observation",
        run.run_id,
        run.revision,
        instant,
        PROVENANCE,
        foreign,
    )
    with pytest.raises(PlanRunIdentityError, match="different PlanRun"):
        PlanRunReducer().apply(plan, run, update)


def test_new_revision_and_public_models_are_immutable() -> None:
    plan = chain_plan()
    old = new_run(plan)
    new = activate(plan, old, "a")

    with pytest.raises(FrozenInstanceError):
        new.revision = 99  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        new.step_progress[0].state = StepProgressState.FAILED  # type: ignore[misc]
    assert old.revision == 0
    assert new.revision == 1


def test_multiple_roots_are_all_ready_without_selection() -> None:
    plan = independent_plan()
    run = new_run(plan)
    results = derive_availability(plan, run)
    assert [(item.step_id, item.availability) for item in results] == [
        ("a", StepAvailability.READY),
        ("b", StepAvailability.READY),
    ]
    assert not hasattr(run, "current_step")
    assert not hasattr(run, "next_step")


def test_diamond_dependencies_release_only_after_all_prerequisites_succeed() -> None:
    plan = diamond_plan()
    run = new_run(plan)
    run = finish(plan, run, "a")
    assert availability(plan, run, "b") is StepAvailability.READY
    assert availability(plan, run, "c") is StepAvailability.READY
    assert availability(plan, run, "d") is StepAvailability.WAITING_DEPENDENCIES

    run = finish(plan, run, "b")
    assert availability(plan, run, "d") is StepAvailability.WAITING_DEPENDENCIES
    run = finish(plan, run, "c")
    assert availability(plan, run, "d") is StepAvailability.READY


def test_duplicate_observation_and_blocker_ids_are_rejected() -> None:
    plan = chain_plan()
    run, observation_id = record_observation(plan, new_run(plan), "a")
    instant = update_time(run)
    duplicate_observation = replace(run.observations[0], observed_at=instant)
    with pytest.raises(DuplicateRunIdentityError, match="duplicate observation"):
        PlanRunReducer().apply(
            plan,
            run,
            RecordObservationUpdate(
                "update-duplicate-observation",
                run.run_id,
                run.revision,
                instant,
                PROVENANCE,
                duplicate_observation,
            ),
        )
    assert observation_id == run.observations[0].observation_id

    blocked = add_blocker(plan, run, "a")
    blocker_time = update_time(blocked)
    duplicate_blocker = replace(blocked.blockers[0], created_at=blocker_time)
    with pytest.raises(DuplicateRunIdentityError, match="duplicate blocker"):
        PlanRunReducer().apply(
            plan,
            blocked,
            AddBlockerUpdate(
                "update-duplicate-blocker",
                blocked.run_id,
                blocked.revision,
                blocker_time,
                PROVENANCE,
                duplicate_blocker,
            ),
        )


def test_missing_duplicate_and_unknown_progress_are_invalid() -> None:
    plan = chain_plan()
    run = new_run(plan)
    with pytest.raises(PlanRunInvariantError, match="identities must be unique"):
        replace(run, step_progress=(run.step_progress[0], run.step_progress[0]))

    missing = replace(run, step_progress=(run.step_progress[0],))
    with pytest.raises(PlanRunInvariantError, match="missing progress"):
        validate_plan_run(plan, missing)

    unknown = replace(
        run,
        step_progress=run.step_progress
        + (StepProgress("unknown", StepProgressState.NOT_STARTED, NOW),),
    )
    with pytest.raises(PlanRunInvariantError, match="unknown progress"):
        validate_plan_run(plan, unknown)


def test_inconsistent_plan_and_goal_identities_are_rejected() -> None:
    plan = chain_plan()
    run = new_run(plan)
    with pytest.raises(PlanRunIdentityError, match="different Plan"):
        validate_plan_run(plan, replace(run, plan_id="plan-other"))
    with pytest.raises(PlanRunIdentityError, match="different Goal"):
        validate_plan_run(plan, replace(run, goal_id="goal-other"))
    with pytest.raises(PlanRunInvariantError, match="identity must differ"):
        replace(run, run_id=run.plan_id)


def test_revision_and_timestamps_are_validated_and_normalized() -> None:
    plan = chain_plan()
    offset = timezone(timedelta(hours=-6))
    run = PlanRunFactory(
        clock=lambda: NOW.astimezone(offset),
        run_id_factory=lambda: "run-offset",
    ).create(plan)
    assert run.created_at.tzinfo is UTC
    assert run.revision == 0

    with pytest.raises(ValueError, match="timezone-aware"):
        PlanRunFactory(
            clock=lambda: datetime(2026, 9, 26, 12),
            run_id_factory=lambda: "run-naive",
        ).create(plan)
    with pytest.raises(PlanRunInvariantError, match="nonnegative"):
        replace(run, revision=-1)

    update = StepProgressUpdate(
        "update-old-time",
        run.run_id,
        run.revision,
        run.updated_at - timedelta(seconds=1),
        PROVENANCE,
        "a",
        StepProgressState.ACTIVE,
    )
    with pytest.raises(PlanRunInvariantError, match="cannot predate"):
        PlanRunReducer().apply(plan, run, update)


def test_blocker_resolution_rejects_unknown_and_already_resolved() -> None:
    plan = chain_plan()
    run = new_run(plan)
    with pytest.raises(InvalidBlockerOperationError, match="unknown blocker"):
        PlanRunReducer().apply(
            plan,
            run,
            ResolveBlockerUpdate(
                "update-resolve-unknown",
                run.run_id,
                run.revision,
                update_time(run),
                PROVENANCE,
                "missing",
            ),
        )

    blocked = add_blocker(plan, run, "a")
    resolved = PlanRunReducer().apply(
        plan,
        blocked,
        ResolveBlockerUpdate(
            "update-resolve-once",
            blocked.run_id,
            blocked.revision,
            update_time(blocked),
            PROVENANCE,
            "blocker-1",
        ),
    )
    with pytest.raises(InvalidBlockerOperationError, match="already resolved"):
        PlanRunReducer().apply(
            plan,
            resolved,
            ResolveBlockerUpdate(
                "update-resolve-twice",
                resolved.run_id,
                resolved.revision,
                update_time(resolved),
                PROVENANCE,
                "blocker-1",
            ),
        )


def test_evidence_scope_must_be_run_scoped_or_match_step() -> None:
    plan = independent_plan()
    run = activate(plan, new_run(plan), "a")
    run, evidence_id = record_observation(plan, run, "b")
    with pytest.raises(ForeignEvidenceError, match="another step"):
        terminal(plan, run, "a", StepProgressState.SUCCEEDED, evidence_id)

    run_scoped, run_evidence = record_observation(plan, run, None)
    succeeded = terminal(
        plan,
        run_scoped,
        "a",
        StepProgressState.SUCCEEDED,
        run_evidence,
    )
    assert progress(succeeded, "a").state is StepProgressState.SUCCEEDED


def test_serialization_is_json_compatible_and_deterministically_ordered() -> None:
    plan = independent_plan()
    run = new_run(plan)
    run, _ = record_observation(plan, run, "b", observation_id="observation-z")
    run, _ = record_observation(plan, run, "a", observation_id="observation-a")
    run = add_blocker(plan, run, "b", blocker_id="blocker-z")
    run = add_blocker(plan, run, "a", blocker_id="blocker-a")

    data = run.to_data()
    encoded = json.dumps(data, sort_keys=True)
    assert [item["step_id"] for item in data["step_progress"]] == ["a", "b"]
    assert [item["observation_id"] for item in data["observations"]] == [
        "observation-a",
        "observation-z",
    ]
    assert [item["blocker_id"] for item in data["blockers"]] == [
        "blocker-a",
        "blocker-z",
    ]
    assert json.dumps(run.to_data(), sort_keys=True) == encoded


def test_terminal_and_active_availability_always_take_precedence() -> None:
    plan = chain_plan()
    active = activate(plan, new_run(plan), "a")
    assert availability(plan, active, "a") is StepAvailability.ACTIVE
    terminal_run = finish(plan, new_run(plan), "a")
    assert availability(plan, terminal_run, "a") is StepAvailability.TERMINAL


def test_explicit_blocker_precedes_dependency_failure_and_waiting() -> None:
    plan = chain_plan()
    run = add_blocker(plan, new_run(plan), "b")
    blocked_waiting = derive_step_availability(plan, run, "b")
    assert blocked_waiting.availability is StepAvailability.BLOCKED
    assert blocked_waiting.explicit_blocker_ids == ("blocker-1",)
    assert blocked_waiting.pending_dependency_ids == ("a",)

    run = finish(plan, run, "a", StepProgressState.FAILED)
    failed = derive_step_availability(plan, run, "b")
    assert failed.availability is StepAvailability.BLOCKED
    assert failed.explicit_blocker_ids == ("blocker-1",)
    assert failed.failed_dependency_ids == ("a",)


def test_not_started_ready_step_may_be_declared_failed_with_evidence() -> None:
    plan = chain_plan()
    run = new_run(plan)
    run, evidence_id = record_observation(plan, run, "a")
    failed = terminal(plan, run, "a", StepProgressState.FAILED, evidence_id)
    assert progress(failed, "a").state is StepProgressState.FAILED


def test_public_updates_have_stable_json_compatible_serialization() -> None:
    plan = chain_plan()
    run = new_run(plan)
    instant = update_time(run)
    observation = PlanObservation(
        "observation-1",
        run.run_id,
        "test_adapter",
        instant,
        "test_evidence",
        data={"z": 2, "a": 1},
    )
    update = RecordObservationUpdate(
        "update-1",
        run.run_id,
        run.revision,
        instant,
        PROVENANCE,
        observation,
    )
    assert json.loads(json.dumps(update.to_data()))["operation"] == (
        "record_observation"
    )
    assert list(update.to_data()["observation"]["data"]) == ["a", "z"]


def test_multiple_runs_of_one_plan_remain_independent() -> None:
    plan = chain_plan()
    first = new_run(plan, run_id="run-1")
    second = new_run(plan, run_id="run-2")

    advanced = activate(plan, first, "a")

    assert advanced.run_id == "run-1"
    assert progress(advanced, "a").state is StepProgressState.ACTIVE
    assert progress(second, "a").state is StepProgressState.NOT_STARTED
    assert second.revision == 0


def test_unknown_observation_and_blocker_steps_are_rejected() -> None:
    plan = chain_plan()
    run = new_run(plan)
    instant = update_time(run)
    unknown_observation = PlanObservation(
        "observation-unknown-step",
        run.run_id,
        "test_adapter",
        instant,
        "test_evidence",
        step_id="unknown",
    )
    with pytest.raises(UnknownPlanStepError, match="unknown"):
        PlanRunReducer().apply(
            plan,
            run,
            RecordObservationUpdate(
                "update-unknown-observation",
                run.run_id,
                run.revision,
                instant,
                PROVENANCE,
                unknown_observation,
            ),
        )

    unknown_blocker = PlanBlocker(
        "blocker-unknown-step",
        run.run_id,
        "unknown",
        "external_precondition",
        "Unknown step cannot be targeted.",
        PROVENANCE,
        instant,
    )
    with pytest.raises(UnknownPlanStepError, match="unknown"):
        PlanRunReducer().apply(
            plan,
            run,
            AddBlockerUpdate(
                "update-unknown-blocker",
                run.run_id,
                run.revision,
                instant,
                PROVENANCE,
                unknown_blocker,
            ),
        )


def test_blocker_timestamp_must_match_its_atomic_update() -> None:
    plan = chain_plan()
    run = new_run(plan)
    update_instant = update_time(run)
    blocker = PlanBlocker(
        "blocker-time",
        run.run_id,
        "a",
        "external_precondition",
        "Timestamp mismatch.",
        PROVENANCE,
        run.updated_at,
    )
    with pytest.raises(InvalidBlockerOperationError, match="equal update"):
        PlanRunReducer().apply(
            plan,
            run,
            AddBlockerUpdate(
                "update-blocker-time",
                run.run_id,
                run.revision,
                update_instant,
                PROVENANCE,
                blocker,
            ),
        )


def test_same_explicit_inputs_reduce_to_semantically_equal_snapshots() -> None:
    plan = chain_plan()
    run = new_run(plan)
    update = StepProgressUpdate(
        "update-deterministic",
        run.run_id,
        run.revision,
        update_time(run),
        PROVENANCE,
        "a",
        StepProgressState.ACTIVE,
    )
    first = PlanRunReducer().apply(plan, run, update)
    second = PlanRunReducer().apply(plan, run, update)
    assert first == second
    assert first.to_data() == second.to_data()


def test_blocked_root_has_cannot_advance_without_implying_failure() -> None:
    plan = chain_plan()
    run = add_blocker(plan, new_run(plan), "a")
    condition = derive_run_condition(plan, run)
    assert condition.condition is PlanRunCondition.CANNOT_ADVANCE
    assert all(
        item.state is StepProgressState.NOT_STARTED for item in run.step_progress
    )


def test_no_side_effects_or_cross_subsystem_runtime_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = chain_plan()

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("PlanRun state must not perform external I/O")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    run = new_run(plan)
    updated = activate(plan, run, "a")

    assert updated.revision == 1
    for forbidden_field in (
        "execution_request",
        "execution_result",
        "context_snapshot",
        "memory_records",
        "selected_handler",
        "provider",
        "attempts",
        "checkpoint",
    ):
        assert not hasattr(updated, forbidden_field)
