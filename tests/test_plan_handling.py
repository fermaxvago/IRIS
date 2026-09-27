"""Declarative PlanStep handling-preparation boundary tests."""

from __future__ import annotations

import builtins
import json
import socket
import subprocess
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

import iris.plan_handling.preparer as preparer_module
from iris.intelligence.routing import IntelligenceNeed
from iris.orchestrator import HandlingKind, HandlingNeed, MemoryOperation
from iris.plan_control import (
    ControlDecision,
    ControlDecisionKind,
    ControlProvenance,
    ControlReason,
    PlanRunController,
    StaleControlDecisionError,
)
from iris.plan_handling import (
    InvalidControlDecisionKindError,
    PlanHandlingInvariantError,
    PlanStepHandlingPreparer,
    PreparationPlanIdentityError,
    PreparationRunIdentityError,
    SelectedStepNotReadyError,
    SpecificationKindMismatchError,
    SpecificationStepMismatchError,
    StaleStepHandlingPreparationError,
    StepHandlingPreparationProvenance,
    StepHandlingPreparationReason,
    StepHandlingPreparationResult,
    StepHandlingPreparationStatus,
    StepHandlingSpecification,
    UnexpectedStepHandlingSpecificationError,
    UnknownSelectedPlanStepError,
    validate_step_handling_preparation_current,
)
from iris.plan_runs import (
    AddBlockerUpdate,
    PlanBlocker,
    PlanObservation,
    PlanRun,
    PlanRunFactory,
    PlanRunReducer,
    RecordObservationUpdate,
    RunProvenance,
    StepAvailability,
    StepProgressState,
    StepProgressUpdate,
    derive_step_availability,
)
from iris.planning import Plan, PlanStep
from iris.router import RouteTarget

NOW = datetime(2026, 9, 27, 20, tzinfo=UTC)
RUN_PROVENANCE = RunProvenance("test", "test-plan-handling", "tester")
PREPARATION_PROVENANCE = StepHandlingPreparationProvenance("test_preparer", "1")


def step(
    step_id: str,
    *,
    handling: HandlingKind | None = None,
    depends_on: tuple[str, ...] = (),
) -> PlanStep:
    return PlanStep(
        step_id,
        f"Objective {step_id}",
        f"Expected {step_id}",
        depends_on,
        handling,
    )


def plan(*steps: PlanStep, plan_id: str = "plan-1") -> Plan:
    return Plan(plan_id, "goal-1", (), steps)


def new_run(selected_plan: Plan, *, run_id: str = "run-1") -> PlanRun:
    return PlanRunFactory(
        clock=lambda: NOW,
        run_id_factory=lambda: run_id,
    ).create(selected_plan)


def selected_decision(
    selected_plan: Plan,
    run: PlanRun,
    step_id: str,
) -> ControlDecision:
    return ControlDecision(
        selected_plan.plan_id,
        run.run_id,
        run.revision,
        ControlDecisionKind.STEP_SELECTED,
        ControlReason.ONLY_READY_STEP,
        ControlProvenance("test_controller", "1"),
        (step_id,),
        step_id,
    )


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


def observe(selected_plan: Plan, run: PlanRun) -> PlanRun:
    observation = PlanObservation(
        f"observation-{run.revision}",
        run.run_id,
        "test",
        next_time(run),
        "run_note",
        None,
        data={"revision_only": True},
    )
    return PlanRunReducer().apply(
        selected_plan,
        run,
        RecordObservationUpdate(
            f"observe-{run.revision}",
            run.run_id,
            run.revision,
            next_time(run),
            RUN_PROVENANCE,
            observation,
        ),
    )


def block(selected_plan: Plan, run: PlanRun, step_id: str) -> PlanRun:
    blocker = PlanBlocker(
        f"blocker-{step_id}",
        run.run_id,
        step_id,
        "external_precondition",
        "Explicit test blocker.",
        RUN_PROVENANCE,
        next_time(run),
    )
    return PlanRunReducer().apply(
        selected_plan,
        run,
        AddBlockerUpdate(
            f"block-{run.revision}-{step_id}",
            run.run_id,
            run.revision,
            next_time(run),
            RUN_PROVENANCE,
            blocker,
        ),
    )


def finish(selected_plan: Plan, run: PlanRun, step_id: str) -> PlanRun:
    run = activate(selected_plan, run, step_id)
    observation_id = f"evidence-{step_id}"
    observation = PlanObservation(
        observation_id,
        run.run_id,
        "test",
        next_time(run),
        "step_outcome",
        step_id,
        data={"succeeded": True},
    )
    run = PlanRunReducer().apply(
        selected_plan,
        run,
        RecordObservationUpdate(
            f"observe-{run.revision}-{step_id}",
            run.run_id,
            run.revision,
            next_time(run),
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
            StepProgressState.SUCCEEDED,
            (observation_id,),
        ),
    )


def prepare(
    handling: HandlingKind | None,
    specification: StepHandlingSpecification | None = None,
) -> tuple[Plan, PlanRun, ControlDecision, StepHandlingPreparationResult]:
    selected_plan = plan(step("a", handling=handling))
    run = new_run(selected_plan)
    decision = PlanRunController().decide(selected_plan, run)
    result = PlanStepHandlingPreparer().prepare(
        selected_plan, run, decision, specification
    )
    return selected_plan, run, decision, result


def test_stale_control_decision_is_rejected_before_preparation() -> None:
    selected_plan = plan(step("a", handling=HandlingKind.CAPABILITY))
    run = new_run(selected_plan)
    decision = PlanRunController().decide(selected_plan, run)
    changed = activate(selected_plan, run, "a")

    with pytest.raises(StaleControlDecisionError):
        PlanStepHandlingPreparer().prepare(selected_plan, changed, decision)


def test_non_selected_control_decision_is_invalid_usage() -> None:
    selected_plan = plan(step("a"), step("b"))
    run = new_run(selected_plan)
    decision = PlanRunController().decide(selected_plan, run)

    with pytest.raises(InvalidControlDecisionKindError):
        PlanStepHandlingPreparer().prepare(selected_plan, run, decision)


def test_unknown_selected_step_is_rejected() -> None:
    selected_plan = plan(step("a", handling=HandlingKind.CAPABILITY))
    run = new_run(selected_plan)

    with pytest.raises(UnknownSelectedPlanStepError):
        PlanStepHandlingPreparer().prepare(
            selected_plan,
            run,
            selected_decision(selected_plan, run, "unknown"),
        )


@pytest.mark.parametrize("state", ["active", "blocked", "waiting", "terminal"])
def test_selected_step_must_still_be_ready(state: str) -> None:
    if state == "waiting":
        selected_plan = plan(
            step("a", handling=HandlingKind.CAPABILITY),
            step(
                "b",
                handling=HandlingKind.CAPABILITY,
                depends_on=("a",),
            ),
        )
        run = new_run(selected_plan)
        selected_id = "b"
    else:
        selected_plan = plan(step("a", handling=HandlingKind.CAPABILITY))
        run = new_run(selected_plan)
        if state == "active":
            run = activate(selected_plan, run, "a")
        elif state == "blocked":
            run = block(selected_plan, run, "a")
        else:
            run = finish(selected_plan, run, "a")
        selected_id = "a"

    with pytest.raises(SelectedStepNotReadyError):
        PlanStepHandlingPreparer().prepare(
            selected_plan,
            run,
            selected_decision(selected_plan, run, selected_id),
        )


def test_required_handling_none_is_explicit_abstention() -> None:
    _, _, _, result = prepare(None)

    assert result.status is StepHandlingPreparationStatus.HANDLING_UNSPECIFIED
    assert result.reason is StepHandlingPreparationReason.HANDLING_NOT_DECLARED
    assert result.handling_kind is None
    assert result.handling_need is None


def test_capability_without_specification_prepares_generic_need() -> None:
    _, _, _, result = prepare(HandlingKind.CAPABILITY)

    assert result.status is StepHandlingPreparationStatus.PREPARED
    assert result.reason is StepHandlingPreparationReason.CAPABILITY_KIND_SUFFICIENT
    assert result.handling_kind is HandlingKind.CAPABILITY
    assert result.handling_need is not None
    assert result.handling_need.kind is HandlingKind.CAPABILITY
    assert result.handling_need.capability_id is None
    assert result.handling_need.blockers == ()


def test_capability_specification_preserves_explicit_identity() -> None:
    specification = StepHandlingSpecification(
        "a", HandlingKind.CAPABILITY, capability_id="capability.alpha"
    )
    _, _, _, result = prepare(HandlingKind.CAPABILITY, specification)

    assert result.handling_need is not None
    assert result.handling_need.capability_id == "capability.alpha"
    assert (
        result.reason is StepHandlingPreparationReason.SPECIFICATION_COMPLETED_HANDLING
    )


@pytest.mark.parametrize(
    ("kind", "reason"),
    [
        (HandlingKind.SYSTEM, StepHandlingPreparationReason.SYSTEM_ROUTE_REQUIRED),
        (HandlingKind.MEMORY, StepHandlingPreparationReason.MEMORY_OPERATION_REQUIRED),
        (
            HandlingKind.INTELLIGENCE,
            StepHandlingPreparationReason.INTELLIGENCE_NEED_REQUIRED,
        ),
    ],
)
def test_declared_kind_without_required_detail_abstains(
    kind: HandlingKind,
    reason: StepHandlingPreparationReason,
) -> None:
    _, _, _, result = prepare(kind)

    assert result.status is StepHandlingPreparationStatus.INSUFFICIENT_DETAIL
    assert result.reason is reason
    assert result.handling_kind is kind
    assert result.handling_need is None


@pytest.mark.parametrize(
    ("kind", "specification", "field", "expected"),
    [
        (
            HandlingKind.SYSTEM,
            StepHandlingSpecification(
                "a", HandlingKind.SYSTEM, system_route=RouteTarget.SYSTEM_STATUS
            ),
            "system_route",
            RouteTarget.SYSTEM_STATUS,
        ),
        (
            HandlingKind.MEMORY,
            StepHandlingSpecification(
                "a", HandlingKind.MEMORY, memory_operation=MemoryOperation.RECALL
            ),
            "memory_operation",
            MemoryOperation.RECALL,
        ),
        (
            HandlingKind.INTELLIGENCE,
            StepHandlingSpecification(
                "a", HandlingKind.INTELLIGENCE, intelligence_need=IntelligenceNeed()
            ),
            "intelligence_need",
            IntelligenceNeed(),
        ),
    ],
)
def test_complete_specification_prepares_exact_handling_need(
    kind: HandlingKind,
    specification: StepHandlingSpecification,
    field: str,
    expected: object,
) -> None:
    _, _, _, result = prepare(kind, specification)

    assert result.status is StepHandlingPreparationStatus.PREPARED
    assert result.reason is (
        StepHandlingPreparationReason.SPECIFICATION_COMPLETED_HANDLING
    )
    assert result.handling_need is not None
    assert result.handling_need.kind is kind
    assert getattr(result.handling_need, field) == expected
    assert result.handling_need.blockers == ()


def test_specification_step_mismatch_is_rejected() -> None:
    selected_plan = plan(step("a", handling=HandlingKind.CAPABILITY))
    run = new_run(selected_plan)
    decision = PlanRunController().decide(selected_plan, run)
    specification = StepHandlingSpecification("b", HandlingKind.CAPABILITY)

    with pytest.raises(SpecificationStepMismatchError):
        PlanStepHandlingPreparer().prepare(selected_plan, run, decision, specification)


def test_specification_kind_mismatch_is_rejected() -> None:
    selected_plan = plan(step("a", handling=HandlingKind.MEMORY))
    run = new_run(selected_plan)
    decision = PlanRunController().decide(selected_plan, run)
    specification = StepHandlingSpecification(
        "a", HandlingKind.INTELLIGENCE, intelligence_need=IntelligenceNeed()
    )

    with pytest.raises(SpecificationKindMismatchError):
        PlanStepHandlingPreparer().prepare(selected_plan, run, decision, specification)


@pytest.mark.parametrize(
    "constructor",
    [
        lambda: StepHandlingSpecification("a", HandlingKind.SYSTEM),
        lambda: StepHandlingSpecification("a", HandlingKind.MEMORY),
        lambda: StepHandlingSpecification("a", HandlingKind.INTELLIGENCE),
        lambda: StepHandlingSpecification(
            "a",
            HandlingKind.MEMORY,
            memory_operation=MemoryOperation.RECALL,
            capability_id="wrong-subsystem",
        ),
        lambda: StepHandlingSpecification(
            "a", HandlingKind.SYSTEM, system_route=RouteTarget.UNKNOWN
        ),
    ],
)
def test_malformed_or_cross_subsystem_specification_is_rejected(
    constructor: Any,
) -> None:
    with pytest.raises(ValueError):
        constructor()


def test_specification_rejects_invalid_typed_detail() -> None:
    with pytest.raises(TypeError):
        StepHandlingSpecification(
            "a",
            HandlingKind.MEMORY,
            memory_operation="recall",  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError):
        StepHandlingSpecification(
            "a",
            HandlingKind.INTELLIGENCE,
            intelligence_need=object(),  # type: ignore[arg-type]
        )


def test_prepared_result_requires_need_and_nonprepared_forbids_need() -> None:
    with pytest.raises(PlanHandlingInvariantError):
        StepHandlingPreparationResult(
            "plan-1",
            "run-1",
            0,
            "a",
            StepHandlingPreparationStatus.PREPARED,
            StepHandlingPreparationReason.CAPABILITY_KIND_SUFFICIENT,
            PREPARATION_PROVENANCE,
            HandlingKind.CAPABILITY,
        )

    need = HandlingNeed("need-1", HandlingKind.CAPABILITY)
    with pytest.raises(PlanHandlingInvariantError):
        StepHandlingPreparationResult(
            "plan-1",
            "run-1",
            0,
            "a",
            StepHandlingPreparationStatus.INSUFFICIENT_DETAIL,
            StepHandlingPreparationReason.SYSTEM_ROUTE_REQUIRED,
            PREPARATION_PROVENANCE,
            HandlingKind.SYSTEM,
            need,
        )


def test_preparer_does_not_mutate_or_activate_plan_run() -> None:
    selected_plan = plan(step("a", handling=HandlingKind.CAPABILITY))
    run = new_run(selected_plan)
    decision = PlanRunController().decide(selected_plan, run)
    plan_before = selected_plan.to_data()
    run_before = run.to_data()

    result = PlanStepHandlingPreparer().prepare(selected_plan, run, decision)

    assert result.status is StepHandlingPreparationStatus.PREPARED
    assert selected_plan.to_data() == plan_before
    assert run.to_data() == run_before
    assert run.revision == 0
    assert run.step_progress[0].state is StepProgressState.NOT_STARTED
    assert (
        derive_step_availability(selected_plan, run, "a").availability
        is StepAvailability.READY
    )


def test_repeat_is_semantically_identical_with_stable_serialization() -> None:
    specification = StepHandlingSpecification(
        "a", HandlingKind.CAPABILITY, capability_id="capability.alpha"
    )
    selected_plan = plan(step("a", handling=HandlingKind.CAPABILITY))
    run = new_run(selected_plan)
    decision = PlanRunController().decide(selected_plan, run)
    preparer = PlanStepHandlingPreparer()

    first = preparer.prepare(selected_plan, run, decision, specification)
    second = preparer.prepare(selected_plan, run, decision, specification)

    assert first == second
    assert first.handling_need == second.handling_need
    assert json.dumps(first.to_data(), sort_keys=True) == json.dumps(
        second.to_data(), sort_keys=True
    )


def test_need_identity_changes_with_revision_plan_run_and_step() -> None:
    first_plan = plan(step("a", handling=HandlingKind.CAPABILITY))
    first_run = new_run(first_plan)
    first = PlanStepHandlingPreparer().prepare(
        first_plan,
        first_run,
        PlanRunController().decide(first_plan, first_run),
    )
    assert first.handling_need is not None

    revised_run = observe(first_plan, first_run)
    revised = PlanStepHandlingPreparer().prepare(
        first_plan,
        revised_run,
        PlanRunController().decide(first_plan, revised_run),
    )
    other_run = new_run(first_plan, run_id="run-2")
    run_result = PlanStepHandlingPreparer().prepare(
        first_plan,
        other_run,
        PlanRunController().decide(first_plan, other_run),
    )
    other_plan = plan(step("a", handling=HandlingKind.CAPABILITY), plan_id="plan-2")
    plan_run = new_run(other_plan)
    plan_result = PlanStepHandlingPreparer().prepare(
        other_plan,
        plan_run,
        PlanRunController().decide(other_plan, plan_run),
    )
    step_plan = plan(step("b", handling=HandlingKind.CAPABILITY))
    step_run = new_run(step_plan)
    step_result = PlanStepHandlingPreparer().prepare(
        step_plan,
        step_run,
        PlanRunController().decide(step_plan, step_run),
    )

    identities = {
        result.handling_need.need_id
        for result in (first, revised, run_result, plan_result, step_result)
        if result.handling_need is not None
    }
    assert len(identities) == 5


def test_current_result_validation_and_stale_rejection() -> None:
    selected_plan, run, _, result = prepare(HandlingKind.CAPABILITY)

    validate_step_handling_preparation_current(selected_plan, run, result)

    with pytest.raises(StaleStepHandlingPreparationError):
        validate_step_handling_preparation_current(
            selected_plan, observe(selected_plan, run), result
        )


def test_result_validation_rejects_wrong_plan_and_run() -> None:
    selected_plan, run, _, result = prepare(HandlingKind.CAPABILITY)
    other_plan = plan(step("a", handling=HandlingKind.CAPABILITY), plan_id="plan-2")
    other_run = new_run(selected_plan, run_id="run-2")

    with pytest.raises(PreparationPlanIdentityError):
        validate_step_handling_preparation_current(
            other_plan, new_run(other_plan), result
        )
    with pytest.raises(PreparationRunIdentityError):
        validate_step_handling_preparation_current(selected_plan, other_run, result)


def test_result_validator_rejects_noncanonical_need_identity() -> None:
    selected_plan, run, _, result = prepare(HandlingKind.CAPABILITY)
    assert result.handling_need is not None
    forged = replace(
        result,
        handling_need=replace(result.handling_need, need_id="forged"),
    )

    with pytest.raises(PlanHandlingInvariantError):
        validate_step_handling_preparation_current(selected_plan, run, forged)


def test_specification_cannot_override_undeclared_handling() -> None:
    selected_plan = plan(step("a"))
    run = new_run(selected_plan)
    decision = PlanRunController().decide(selected_plan, run)
    specification = StepHandlingSpecification("a", HandlingKind.CAPABILITY)

    with pytest.raises(UnexpectedStepHandlingSpecificationError):
        PlanStepHandlingPreparer().prepare(selected_plan, run, decision, specification)


def test_public_models_are_immutable_and_validate_identity_fields() -> None:
    specification = StepHandlingSpecification("a", HandlingKind.CAPABILITY)
    provenance = StepHandlingPreparationProvenance("preparer", "1")
    _, _, _, result = prepare(HandlingKind.CAPABILITY, specification)

    with pytest.raises(FrozenInstanceError):
        specification.step_id = "b"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        provenance.preparer_id = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.observed_revision = 4  # type: ignore[misc]
    with pytest.raises(ValueError):
        StepHandlingSpecification("", HandlingKind.CAPABILITY)
    with pytest.raises(ValueError):
        StepHandlingPreparationProvenance(" ")
    with pytest.raises(ValueError):
        replace(result, observed_revision=-1)


def test_preparer_delegates_to_wp012_and_wp013_public_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_plan = plan(step("a", handling=HandlingKind.CAPABILITY))
    run = new_run(selected_plan)
    decision = PlanRunController().decide(selected_plan, run)
    calls = {"run": 0, "decision": 0, "availability": 0}
    validate_run = preparer_module.validate_plan_run  # type: ignore[attr-defined]
    validate_decision = preparer_module.validate_control_decision_current  # type: ignore[attr-defined]
    derive = preparer_module.derive_step_availability  # type: ignore[attr-defined]

    def run_spy(selected: Plan, selected_run: PlanRun) -> None:
        calls["run"] += 1
        validate_run(selected, selected_run)

    def decision_spy(
        selected: Plan, selected_run: PlanRun, selected_decision: ControlDecision
    ) -> None:
        calls["decision"] += 1
        validate_decision(selected, selected_run, selected_decision)

    def availability_spy(selected: Plan, selected_run: PlanRun, step_id: str) -> Any:
        calls["availability"] += 1
        return derive(selected, selected_run, step_id)

    monkeypatch.setattr(preparer_module, "validate_plan_run", run_spy)
    monkeypatch.setattr(
        preparer_module, "validate_control_decision_current", decision_spy
    )
    monkeypatch.setattr(preparer_module, "derive_step_availability", availability_spy)

    PlanStepHandlingPreparer().prepare(selected_plan, run, decision)

    assert calls == {"run": 1, "decision": 1, "availability": 1}


def test_preparation_performs_no_filesystem_network_or_subprocess_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_plan = plan(step("a", handling=HandlingKind.CAPABILITY))
    run = new_run(selected_plan)
    decision = PlanRunController().decide(selected_plan, run)

    def forbidden(*args: object, **kwargs: object) -> Any:
        raise AssertionError(f"forbidden side effect: {args!r} {kwargs!r}")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)

    result = PlanStepHandlingPreparer().prepare(selected_plan, run, decision)

    assert result.status is StepHandlingPreparationStatus.PREPARED
