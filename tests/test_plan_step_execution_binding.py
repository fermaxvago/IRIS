"""PlanStep execution-lineage binding and strict pre-activation boundaries."""

from __future__ import annotations

import builtins
import json
import socket
import subprocess
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from iris.context import ContextBudget, ContextEngine
from iris.execution import ExecutionCoordinator, ExecutionRequest, SystemExecutionInput
from iris.memory import MemoryScope, ScopeKind
from iris.orchestrator import (
    ContextBlocker,
    ContextBlockerKind,
    HandlerAvailability,
    HandlingKind,
    HandlingNeed,
    OrchestrationDecision,
    OrchestrationInput,
    OrchestrationReason,
    OrchestrationTarget,
    Orchestrator,
)
from iris.plan_control import (
    ControlDecision,
    ControlDecisionKind,
    ControlProvenance,
    ControlReason,
    PlanRunController,
    StaleControlDecisionError,
)
from iris.plan_handling import (
    PlanStepHandlingPreparer,
    StaleStepHandlingPreparationError,
    StepHandlingPreparationResult,
    StepHandlingPreparationStatus,
    StepHandlingSpecification,
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
    StepProgressState,
    StepProgressUpdate,
)
from iris.plan_step_execution_binding import (
    ExecutionBindingMismatchError,
    NonBindableControlDecisionError,
    NonBindableHandlingPreparationError,
    NonExecutableExecutionRequestError,
    PlanStepExecutionBinder,
    PlanStepExecutionBinding,
    PlanStepExecutionBindingInvariantError,
    StalePlanStepExecutionBindingError,
    validate_plan_step_execution_binding_current,
)
from iris.planning import Plan, PlanStep
from iris.router import RouteTarget
from iris.work_identity import (
    PlanStepWorkReference,
    RequestWorkReference,
    WorkSubject,
    WorkSubjectKind,
)

NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)
DECIDED = NOW + timedelta(seconds=1)
PROVENANCE = RunProvenance("test", "wp024", "tester")


def step(
    step_id: str,
    *,
    handling: HandlingKind | None = HandlingKind.SYSTEM,
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


def prepared_for(
    selected_plan: Plan,
    run: PlanRun,
    step_id: str,
) -> StepHandlingPreparationResult:
    return PlanStepHandlingPreparer().prepare(
        selected_plan,
        run,
        selected_decision(selected_plan, run, step_id),
        StepHandlingSpecification(
            step_id,
            HandlingKind.SYSTEM,
            system_route=RouteTarget.SYSTEM_STATUS,
        ),
    )


def execution_for(
    reference: PlanStepWorkReference | RequestWorkReference,
    need: HandlingNeed,
    *,
    target: OrchestrationTarget = OrchestrationTarget.SYSTEM,
    execution_id: str = "execution-1",
) -> ExecutionRequest:
    kind = (
        WorkSubjectKind.PLAN_STEP
        if isinstance(reference, PlanStepWorkReference)
        else WorkSubjectKind.REQUEST
    )
    subject = WorkSubject(kind, reference)
    context = ContextEngine().build(
        subject=subject,
        candidates=(),
        budget=ContextBudget(0),
        created_at=NOW,
    )
    if target is OrchestrationTarget.UNSATISFIED:
        decision = OrchestrationDecision(
            "orchestration-1",
            subject.subject_id,
            context.snapshot_id,
            target,
            OrchestrationReason.COMPOSITE_HANDLING_REQUIRED,
            DECIDED,
            ("need-a", "need-b"),
        )
        execution_input = None
    elif target is OrchestrationTarget.CLARIFY:
        blocker = ContextBlocker(
            "task",
            "active",
            MemoryScope(ScopeKind.GLOBAL),
            ContextBlockerKind.MISSING,
        )
        decision = OrchestrationDecision(
            "orchestration-1",
            subject.subject_id,
            context.snapshot_id,
            target,
            OrchestrationReason.MISSING_REQUIRED_INFORMATION,
            DECIDED,
            ("need-a",),
            context_references=(blocker,),
        )
        execution_input = None
    else:
        decision = Orchestrator(
            clock=lambda: DECIDED,
            id_factory=lambda: "orchestration-1",
        ).decide(
            OrchestrationInput(
                subject,
                context,
                (need,),
                HandlerAvailability(system=True),
            )
        )
        execution_input = SystemExecutionInput()
    return ExecutionRequest(
        execution_id,
        subject,
        context,
        decision,
        DECIDED,
        execution_input,
    )


def valid_inputs() -> tuple[
    Plan,
    PlanRun,
    ControlDecision,
    StepHandlingPreparationResult,
    ExecutionRequest,
]:
    selected_plan = plan(step("a"))
    run = new_run(selected_plan)
    control = PlanRunController().decide(selected_plan, run)
    preparation = prepared_for(selected_plan, run, "a")
    assert preparation.handling_need is not None
    execution = execution_for(
        PlanStepWorkReference(selected_plan.plan_id, run.run_id, "a"),
        preparation.handling_need,
    )
    return selected_plan, run, control, preparation, execution


def observe_run(selected_plan: Plan, run: PlanRun) -> PlanRun:
    observed_at = run.updated_at + timedelta(seconds=1)
    observation = PlanObservation(
        f"observation-{run.revision}",
        run.run_id,
        "test",
        observed_at,
        "run_note",
        None,
    )
    return PlanRunReducer().apply(
        selected_plan,
        run,
        RecordObservationUpdate(
            f"record-{run.revision}",
            run.run_id,
            run.revision,
            observed_at,
            PROVENANCE,
            observation,
        ),
    )


def activate(selected_plan: Plan, run: PlanRun, step_id: str) -> PlanRun:
    return PlanRunReducer().apply(
        selected_plan,
        run,
        StepProgressUpdate(
            f"activate-{run.revision}",
            run.run_id,
            run.revision,
            run.updated_at + timedelta(seconds=1),
            PROVENANCE,
            step_id,
            StepProgressState.ACTIVE,
        ),
    )


def finish(
    selected_plan: Plan,
    run: PlanRun,
    step_id: str,
    state: StepProgressState,
) -> PlanRun:
    active = activate(selected_plan, run, step_id)
    observed_at = active.updated_at + timedelta(seconds=1)
    evidence_id = f"evidence-{state.value}"
    observation = PlanObservation(
        evidence_id,
        active.run_id,
        "test",
        observed_at,
        "step_outcome",
        step_id,
    )
    observed = PlanRunReducer().apply(
        selected_plan,
        active,
        RecordObservationUpdate(
            f"record-{state.value}",
            active.run_id,
            active.revision,
            observed_at,
            PROVENANCE,
            observation,
        ),
    )
    return PlanRunReducer().apply(
        selected_plan,
        observed,
        StepProgressUpdate(
            f"finish-{state.value}",
            observed.run_id,
            observed.revision,
            observed.updated_at + timedelta(seconds=1),
            PROVENANCE,
            step_id,
            state,
            (evidence_id,),
        ),
    )


def test_happy_path_returns_exact_compact_lineage_without_mutation() -> None:
    selected_plan, run, control, preparation, execution = valid_inputs()
    before = (
        selected_plan.to_data(),
        run.to_data(),
        control.to_data(),
        preparation.to_data(),
        execution.to_trace(),
    )

    binding = PlanStepExecutionBinder().bind(
        selected_plan, run, control, preparation, execution
    )

    assert binding == PlanStepExecutionBinding(
        selected_plan.plan_id,
        run.run_id,
        run.revision,
        "a",
        execution.execution_id,
        execution.subject.subject_id,
        execution.decision.decision_id,
        execution.context.snapshot_id,
        preparation.handling_need.need_id,  # type: ignore[union-attr]
    )
    assert before == (
        selected_plan.to_data(),
        run.to_data(),
        control.to_data(),
        preparation.to_data(),
        execution.to_trace(),
    )


@pytest.mark.parametrize("position", range(5))
def test_bind_rejects_wrong_input_types_before_composition(position: int) -> None:
    values: list[Any] = list(valid_inputs())
    values[position] = object()

    with pytest.raises(TypeError):
        PlanStepExecutionBinder().bind(*values)


def test_stale_control_error_remains_owned_by_plan_control() -> None:
    selected_plan, run, control, preparation, execution = valid_inputs()
    changed = observe_run(selected_plan, run)

    with pytest.raises(StaleControlDecisionError):
        PlanStepExecutionBinder().bind(
            selected_plan, changed, control, preparation, execution
        )


def test_non_selected_control_outcome_is_non_bindable() -> None:
    selected_plan = plan(step("a"), step("b"))
    run = new_run(selected_plan)
    control = PlanRunController().decide(selected_plan, run)
    _, _, _, preparation, execution = valid_inputs()
    assert control.kind is ControlDecisionKind.SELECTION_UNRESOLVED

    with pytest.raises(NonBindableControlDecisionError):
        PlanStepExecutionBinder().bind(
            selected_plan, run, control, preparation, execution
        )


def test_stale_preparation_error_remains_owned_by_plan_handling() -> None:
    selected_plan, run, _, preparation, execution = valid_inputs()
    changed = observe_run(selected_plan, run)
    current_control = PlanRunController().decide(selected_plan, changed)

    with pytest.raises(StaleStepHandlingPreparationError):
        PlanStepExecutionBinder().bind(
            selected_plan,
            changed,
            current_control,
            preparation,
            execution,
        )


@pytest.mark.parametrize(
    "handling",
    [None, HandlingKind.SYSTEM],
    ids=["handling-unspecified", "insufficient-detail"],
)
def test_non_prepared_handling_outcomes_are_non_bindable(
    handling: HandlingKind | None,
) -> None:
    selected_plan = plan(step("a", handling=handling))
    run = new_run(selected_plan)
    control = PlanRunController().decide(selected_plan, run)
    preparation = PlanStepHandlingPreparer().prepare(
        selected_plan,
        run,
        control,
    )
    _, _, _, valid_preparation, execution = valid_inputs()
    assert preparation.status in {
        StepHandlingPreparationStatus.HANDLING_UNSPECIFIED,
        StepHandlingPreparationStatus.INSUFFICIENT_DETAIL,
    }
    assert valid_preparation.handling_need is not None

    with pytest.raises(NonBindableHandlingPreparationError):
        PlanStepExecutionBinder().bind(
            selected_plan,
            run,
            control,
            preparation,
            execution,
        )


def test_selected_and_prepared_step_mismatch_is_rejected() -> None:
    selected_plan = plan(step("a"), step("b"))
    run = new_run(selected_plan)
    control_a = selected_decision(selected_plan, run, "a")
    preparation_b = prepared_for(selected_plan, run, "b")
    assert preparation_b.handling_need is not None
    execution_b = execution_for(
        PlanStepWorkReference(selected_plan.plan_id, run.run_id, "b"),
        preparation_b.handling_need,
    )

    with pytest.raises(ExecutionBindingMismatchError, match="selected and prepared"):
        PlanStepExecutionBinder().bind(
            selected_plan,
            run,
            control_a,
            preparation_b,
            execution_b,
        )


def test_request_root_subject_is_rejected() -> None:
    selected_plan, run, control, preparation, _ = valid_inputs()
    assert preparation.handling_need is not None
    execution = execution_for(
        RequestWorkReference("request-1"),
        preparation.handling_need,
    )

    with pytest.raises(ExecutionBindingMismatchError, match="PLAN_STEP"):
        PlanStepExecutionBinder().bind(
            selected_plan, run, control, preparation, execution
        )


@pytest.mark.parametrize(
    "reference",
    [
        PlanStepWorkReference("other-plan", "run-1", "a"),
        PlanStepWorkReference("plan-1", "other-run", "a"),
        PlanStepWorkReference("plan-1", "run-1", "b"),
    ],
)
def test_execution_subject_plan_run_and_step_must_match(
    reference: PlanStepWorkReference,
) -> None:
    selected_plan, run, control, preparation, _ = valid_inputs()
    assert preparation.handling_need is not None
    execution = execution_for(reference, preparation.handling_need)

    with pytest.raises(ExecutionBindingMismatchError, match="reference"):
        PlanStepExecutionBinder().bind(
            selected_plan, run, control, preparation, execution
        )


@pytest.mark.parametrize(
    "different",
    [
        lambda need: replace(need, need_id="different-need"),
        lambda need: replace(need, system_route=RouteTarget.CLI_HELP),
    ],
    ids=["identity", "content"],
)
def test_handling_need_requires_exact_semantic_equality(different: Any) -> None:
    selected_plan, run, control, preparation, _ = valid_inputs()
    assert preparation.handling_need is not None
    other_need = different(preparation.handling_need)
    execution = execution_for(
        PlanStepWorkReference(selected_plan.plan_id, run.run_id, "a"),
        other_need,
    )

    with pytest.raises(ExecutionBindingMismatchError, match="HandlingNeed"):
        PlanStepExecutionBinder().bind(
            selected_plan, run, control, preparation, execution
        )


@pytest.mark.parametrize(
    "target",
    [OrchestrationTarget.CLARIFY, OrchestrationTarget.UNSATISFIED],
)
def test_terminal_orchestration_request_is_not_executable(
    target: OrchestrationTarget,
) -> None:
    selected_plan, run, control, preparation, _ = valid_inputs()
    assert preparation.handling_need is not None
    execution = execution_for(
        PlanStepWorkReference(selected_plan.plan_id, run.run_id, "a"),
        preparation.handling_need,
        target=target,
    )

    with pytest.raises(NonExecutableExecutionRequestError):
        PlanStepExecutionBinder().bind(
            selected_plan, run, control, preparation, execution
        )


def test_revision_change_makes_binding_stale_even_when_step_remains_ready() -> None:
    selected_plan, run, control, preparation, execution = valid_inputs()
    binding = PlanStepExecutionBinder().bind(
        selected_plan, run, control, preparation, execution
    )
    changed = observe_run(selected_plan, run)

    with pytest.raises(StalePlanStepExecutionBindingError, match="revision"):
        validate_plan_step_execution_binding_current(
            selected_plan,
            changed,
            binding,
        )


def test_currentness_rejects_blocked_step_even_with_matching_revision() -> None:
    selected_plan, run, control, preparation, execution = valid_inputs()
    binding = PlanStepExecutionBinder().bind(
        selected_plan, run, control, preparation, execution
    )
    blocked_at = run.updated_at + timedelta(seconds=1)
    blocker = PlanBlocker(
        "blocker-a",
        run.run_id,
        "a",
        "external_precondition",
        "Waiting for an external condition.",
        PROVENANCE,
        blocked_at,
    )
    blocked = PlanRunReducer().apply(
        selected_plan,
        run,
        AddBlockerUpdate(
            "add-blocker",
            run.run_id,
            run.revision,
            blocked_at,
            PROVENANCE,
            blocker,
        ),
    )

    with pytest.raises(StalePlanStepExecutionBindingError, match="not READY"):
        validate_plan_step_execution_binding_current(
            selected_plan,
            blocked,
            replace(binding, observed_revision=blocked.revision),
        )


@pytest.mark.parametrize(
    "state",
    [StepProgressState.ACTIVE, StepProgressState.SUCCEEDED, StepProgressState.FAILED],
)
def test_currentness_rejects_active_and_terminal_steps(
    state: StepProgressState,
) -> None:
    selected_plan, run, control, preparation, execution = valid_inputs()
    binding = PlanStepExecutionBinder().bind(
        selected_plan, run, control, preparation, execution
    )
    changed = (
        activate(selected_plan, run, "a")
        if state is StepProgressState.ACTIVE
        else finish(selected_plan, run, "a", state)
    )

    with pytest.raises(StalePlanStepExecutionBindingError, match="NOT_STARTED"):
        validate_plan_step_execution_binding_current(
            selected_plan,
            changed,
            replace(binding, observed_revision=changed.revision),
        )


def test_currentness_validates_binding_identity_and_types() -> None:
    selected_plan, run, control, preparation, execution = valid_inputs()
    binding = PlanStepExecutionBinder().bind(
        selected_plan, run, control, preparation, execution
    )
    validate_plan_step_execution_binding_current(selected_plan, run, binding)

    with pytest.raises(TypeError):
        validate_plan_step_execution_binding_current(selected_plan, run, object())  # type: ignore[arg-type]
    with pytest.raises(PlanStepExecutionBindingInvariantError, match="Plan"):
        validate_plan_step_execution_binding_current(
            selected_plan,
            run,
            replace(binding, plan_id="other-plan"),
        )
    with pytest.raises(PlanStepExecutionBindingInvariantError, match="PlanRun"):
        validate_plan_step_execution_binding_current(
            selected_plan,
            run,
            replace(binding, run_id="other-run"),
        )


def test_binding_model_invariants_serialization_and_immutability() -> None:
    selected_plan, run, control, preparation, execution = valid_inputs()
    binding = PlanStepExecutionBinder().bind(
        selected_plan, run, control, preparation, execution
    )

    assert json.loads(json.dumps(binding.to_data())) == binding.to_data()
    assert tuple(binding.to_data()) == (
        "plan_id",
        "run_id",
        "observed_revision",
        "step_id",
        "execution_id",
        "subject_id",
        "orchestration_decision_id",
        "context_snapshot_id",
        "handling_need_id",
    )
    with pytest.raises(FrozenInstanceError):
        binding.step_id = "other"  # type: ignore[misc]
    with pytest.raises(PlanStepExecutionBindingInvariantError):
        replace(binding, execution_id=" ")
    with pytest.raises(TypeError):
        replace(binding, observed_revision=True)
    with pytest.raises(PlanStepExecutionBindingInvariantError):
        replace(binding, observed_revision=-1)


def test_repeated_binding_is_deterministic() -> None:
    inputs = valid_inputs()

    assert PlanStepExecutionBinder().bind(*inputs) == PlanStepExecutionBinder().bind(
        *inputs
    )


def test_binding_performs_no_reducer_handler_or_external_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = valid_inputs()

    def forbidden(*_args: object, **_kwargs: object) -> Any:
        raise AssertionError("forbidden side effect")

    monkeypatch.setattr(PlanRunReducer, "apply", forbidden)
    monkeypatch.setattr(ExecutionCoordinator, "execute", forbidden)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)

    binding = PlanStepExecutionBinder().bind(*inputs)

    assert binding.step_id == "a"
    assert not hasattr(binding, "authorized")
    assert not hasattr(binding, "handler_reference")
    assert not hasattr(binding, "step_progress_update")
