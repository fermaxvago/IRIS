"""WP077: disclose real requirements and validate context-aware results."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import iris.__main__ as cli
from iris.context import (
    ContextBudget,
    ContextEvidence,
    ContextItem,
    ContextSnapshot,
    EvidenceSource,
    Freshness,
    Relevance,
    ResolutionStatus,
)
from iris.memory import EpistemicStatus, MemoryScope, ScopeKind
from iris.planning import (
    ConstraintKind,
    DeterministicPlanner,
    Goal,
    GoalProvenance,
    GoalScope,
    Plan,
    PlanningConstraint,
    PlanningContextRequirement,
    PlanningReason,
    PlanningRequest,
    PlanningResult,
    PlanningRule,
    PlanningStatus,
    PlanStep,
)
from iris.planning.strategy_manifest import (
    StrategyDescriptor,
    StrategyManifest,
    built_in_manifest,
)
from iris.work_identity import (
    RequestWorkReference,
    WorkOrigin,
    WorkSubject,
    WorkSubjectKind,
)

NOW = datetime(2026, 11, 12, 12, tzinfo=UTC)
GLOBAL = MemoryScope(ScopeKind.GLOBAL)
TASK = MemoryScope(ScopeKind.TASK, "task-1")
A = PlanningContextRequirement("task", "topic", GLOBAL)
B = PlanningContextRequirement("task", "materials", TASK)
STEPS = (PlanStep("a", "Delimitar el tema.", "Tema identificado."),)


def descriptor(
    *,
    required: tuple[PlanningContextRequirement, ...] = (A, B),
    steps: tuple[PlanStep, ...] = STEPS,
) -> StrategyDescriptor:
    return StrategyDescriptor(
        "sintetica",
        "Estrategia de prueba con contexto explícito.",
        PlanningRule("Preparar tema sintético", steps=steps, required_context=required),
    )


def snapshot(
    *requirements: PlanningContextRequirement,
    request_id: str = "request-1",
) -> ContextSnapshot:
    items = tuple(
        ContextItem(
            candidate_id=f"item-{index}",
            kind=requirement.kind,
            key=requirement.key,
            value=f"private-value-{index}",
            evidence=ContextEvidence(
                EvidenceSource.CALLER, "synthetic-test", EpistemicStatus.DIRECT
            ),
            scope=requirement.scope,
            relevance=Relevance.REQUIRED,
            freshness=Freshness.CURRENT,
        )
        for index, requirement in enumerate(requirements)
    )
    return ContextSnapshot(
        snapshot_id="snapshot-1",
        subject=WorkSubject(
            WorkSubjectKind.REQUEST,
            RequestWorkReference(request_id),
            WorkOrigin("request", request_id),
        ),
        created_at=NOW - timedelta(seconds=1),
        budget=ContextBudget(len(items)),
        items=items,
        status=ResolutionStatus.RESOLVED,
    )


def request(
    selected: StrategyDescriptor,
    context: ContextSnapshot | None = None,
    *,
    constraints: tuple[PlanningConstraint, ...] = (),
) -> PlanningRequest:
    goal = Goal(
        "goal-1",
        selected.rule.objective,
        GoalScope(ScopeKind.TASK, "request-1"),
        GoalProvenance("request", "request-1", None),
        constraints=constraints,
    )
    return PlanningRequest("planning-1", goal, NOW, context)


def evaluate(
    selected: StrategyDescriptor, planning_request: PlanningRequest
) -> PlanningResult:
    value = DeterministicPlanner(
        (selected.rule,), clock=lambda: NOW, plan_id_factory=lambda: "plan-1"
    ).plan(planning_request)
    accepted = cli._validated_planning_result(value, planning_request)
    cli._validated_selected_result(accepted, planning_request, selected)
    return accepted


def test_builtin_disclosure_is_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "Request", lambda **_: pytest.fail("Request constructed"))
    monkeypatch.setattr(cli, "Goal", lambda **_: pytest.fail("Goal constructed"))
    monkeypatch.setattr(
        cli, "PlanningRequest", lambda **_: pytest.fail("PlanningRequest constructed")
    )
    monkeypatch.setattr(
        DeterministicPlanner, "plan", lambda *_: pytest.fail("Planner invoked")
    )
    output: list[str] = []
    cli.entrypoint(["planificar", "--requisitos", "estudio"], output_fn=output.append)
    assert output == [
        "Estrategia: estudio",
        "Objetivo: Preparar una sesión de estudio",
        "Requisitos de contexto: ninguno.",
    ]
    assert built_in_manifest().entries[0].rule.required_context == ()


def test_synthetic_disclosure_preserves_kind_key_scope_and_order() -> None:
    selected = descriptor()
    output: list[str] = []
    cli.entrypoint(
        ["planificar", "--requisitos", "sintetica"],
        output_fn=output.append,
        planning_manifest=StrategyManifest((selected,)),
    )
    assert output == [
        "Estrategia: sintetica",
        "Objetivo: Preparar tema sintético",
        "Requisitos de contexto:",
        "- kind=task, key=topic, scope=global",
        "- kind=task, key=materials, scope=task:task-1",
    ]
    assert [entry.strategy_id for entry in built_in_manifest().entries] == ["estudio"]


@pytest.mark.parametrize(
    "arguments",
    [
        ["--requisitos", "desconocida"],
        ["--requisitos", ""],
        ["--requisitos", "Estudio"],
        ["--requisitos", "estudio", "--requisitos", "estudio"],
        ["--requisitos", "estudio", "--listar"],
        ["--requisitos", "estudio", "--estrategia", "estudio"],
        ["--requisitos", "estudio", "--objetivo", "Preparar una sesión de estudio"],
        ["--requisitos", "estudio", "extra"],
        [],
    ],
)
def test_invalid_requirement_mode_never_plans(arguments: list[str]) -> None:
    class ForbiddenPlanner:
        def plan(self, _request: PlanningRequest) -> PlanningResult:
            pytest.fail("Planner invoked")

    with pytest.raises(SystemExit) as error:
        cli.entrypoint(["planificar", *arguments], planning_planner=ForbiddenPlanner())
    assert error.value.code == 2


def test_unknown_requirement_id_creates_no_planning_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "Request", lambda **_: pytest.fail("Request constructed"))
    monkeypatch.setattr(cli, "Goal", lambda **_: pytest.fail("Goal constructed"))
    monkeypatch.setattr(
        cli, "PlanningRequest", lambda **_: pytest.fail("PlanningRequest constructed")
    )
    monkeypatch.setattr(
        DeterministicPlanner, "plan", lambda *_: pytest.fail("Planner invoked")
    )
    with pytest.raises(SystemExit) as error:
        cli.entrypoint(["planificar", "--requisitos", "desconocida"])
    assert error.value.code == 2


def test_all_missing_and_partial_context_are_exact() -> None:
    selected = descriptor()
    missing_all = evaluate(selected, request(selected))
    assert missing_all.status is PlanningStatus.INSUFFICIENT_CONTEXT
    assert missing_all.reason is PlanningReason.MISSING_REQUIRED_CONTEXT
    assert missing_all.missing_context == selected.rule.required_context
    assert missing_all.plan is None

    partial = evaluate(selected, request(selected, snapshot(A)))
    assert partial.missing_context == (B,)
    assert partial.plan is None
    output: list[str] = []
    cli._show_planning_result(request(selected, snapshot(A)), partial, output.append)
    assert any("key=materials, scope=task:task-1" in line for line in output)
    assert not any("private-value" in line for line in output)
    assert not any("key=topic" in line for line in output)


def test_complete_context_accepts_plan_and_no_step_result() -> None:
    selected = descriptor()
    complete = request(selected, snapshot(A, B))
    result = evaluate(selected, complete)
    assert result.status is PlanningStatus.PLAN_CREATED
    assert result.reason is PlanningReason.DECOMPOSITION_CREATED
    assert result.plan is not None and result.plan.steps == selected.rule.steps
    assert result.missing_context == ()

    no_steps = descriptor(steps=())
    no_step_result = evaluate(no_steps, request(no_steps, snapshot(A, B)))
    assert no_step_result.status is PlanningStatus.NO_PLAN_REQUIRED
    assert no_step_result.reason is PlanningReason.DECOMPOSITION_UNNECESSARY
    assert no_step_result.plan is None and no_step_result.missing_context == ()


def test_scope_mismatch_and_resolved_status_do_not_imply_sufficiency() -> None:
    selected = descriptor()
    wrong_scope = PlanningContextRequirement("task", "materials", GLOBAL)
    result = evaluate(selected, request(selected, snapshot(A, wrong_scope)))
    assert result.missing_context == (B,)
    assert snapshot(A).status is ResolutionStatus.RESOLVED


def test_foreign_context_owner_is_rejected() -> None:
    with pytest.raises(ValueError, match="provenance"):
        request(descriptor(), snapshot(A, request_id="other-request"))


def test_no_requirements_still_produce_study_plan() -> None:
    selected = built_in_manifest().entries[0]
    planning_request = request(selected)
    result = evaluate(selected, planning_request)
    assert result.status is PlanningStatus.PLAN_CREATED
    assert result.plan is not None and len(result.plan.steps) == 4
    fabricated = PlanningResult(
        "result-2",
        planning_request.planning_request_id,
        planning_request.goal.goal_id,
        PlanningStatus.INSUFFICIENT_CONTEXT,
        PlanningReason.MISSING_REQUIRED_CONTEXT,
        NOW,
        missing_context=(A,),
    )
    with pytest.raises(ValueError):
        cli._validated_selected_result(fabricated, planning_request, selected)


@pytest.mark.parametrize(
    "tampering",
    [
        "foreign_request",
        "foreign_goal",
        "fabricated_missing",
        "omitted_missing",
        "wrong_scope",
        "unexpected_plan",
        "wrong_status",
        "wrong_reason",
        "noncanonical",
    ],
)
def test_adversarial_missing_result_fails_before_display(tampering: str) -> None:
    selected = descriptor()
    original_request = request(selected, snapshot(A))
    valid = evaluate(selected, original_request)
    assert valid.missing_context == (B,)
    if tampering == "foreign_request":
        invalid: object = replace(valid, planning_request_id="other-planning")
    elif tampering == "foreign_goal":
        invalid = replace(valid, goal_id="other-goal")
    elif tampering == "fabricated_missing":
        invalid = replace(valid, missing_context=(A, B))
    elif tampering == "omitted_missing":
        invalid = replace(valid, missing_context=(A,))
    elif tampering == "wrong_scope":
        invalid = replace(
            valid,
            missing_context=(PlanningContextRequirement("task", "materials", GLOBAL),),
        )
    elif tampering == "unexpected_plan":
        invalid = PlanningResult(
            "result-2",
            original_request.planning_request_id,
            original_request.goal.goal_id,
            PlanningStatus.PLAN_CREATED,
            PlanningReason.DECOMPOSITION_CREATED,
            NOW,
            plan=Plan("plan-2", original_request.goal.goal_id, (), STEPS),
        )
    elif tampering == "wrong_status":
        invalid = PlanningResult(
            "result-2",
            original_request.planning_request_id,
            original_request.goal.goal_id,
            PlanningStatus.NO_PLAN_REQUIRED,
            PlanningReason.DECOMPOSITION_UNNECESSARY,
            NOW,
        )
    elif tampering == "wrong_reason":
        invalid = PlanningResult(
            "result-2",
            original_request.planning_request_id,
            original_request.goal.goal_id,
            PlanningStatus.UNSATISFIABLE,
            PlanningReason.NO_REGISTERED_STRATEGY,
            NOW,
        )
    else:
        invalid = object()
    with pytest.raises(ValueError):
        accepted = cli._validated_planning_result(invalid, original_request)
        cli._validated_selected_result(accepted, original_request, selected)


def test_complete_context_rejects_fabricated_missing_and_wrong_steps() -> None:
    selected = descriptor()
    planning_request = request(selected, snapshot(A, B))
    valid = evaluate(selected, planning_request)
    assert valid.plan is not None
    fabricated = PlanningResult(
        "result-2",
        planning_request.planning_request_id,
        planning_request.goal.goal_id,
        PlanningStatus.INSUFFICIENT_CONTEXT,
        PlanningReason.MISSING_REQUIRED_CONTEXT,
        NOW,
        missing_context=(A,),
    )
    with pytest.raises(ValueError):
        cli._validated_selected_result(fabricated, planning_request, selected)
    for invalid in (
        replace(
            valid,
            plan=replace(valid.plan, steps=STEPS + (PlanStep("b", "Extra", "Extra"),)),
        ),
        replace(valid, plan=replace(valid.plan, assumptions=("invented",))),
    ):
        with pytest.raises(ValueError):
            cli._validated_selected_result(invalid, planning_request, selected)


def test_conflicting_constraints_take_precedence_over_missing_context() -> None:
    selected = descriptor()
    conflicts = (
        PlanningConstraint(ConstraintKind.REQUIRE, "time", "morning"),
        PlanningConstraint(ConstraintKind.FORBID, "time", "morning"),
    )
    planning_request = request(selected, constraints=conflicts)
    result = evaluate(selected, planning_request)
    assert result.status is PlanningStatus.UNSATISFIABLE
    assert result.reason is PlanningReason.CONFLICTING_CONSTRAINTS
    assert result.constraint_conflicts == ("required_and_forbidden:time",)
    fabricated = PlanningResult(
        "result-2",
        planning_request.planning_request_id,
        planning_request.goal.goal_id,
        PlanningStatus.INSUFFICIENT_CONTEXT,
        PlanningReason.MISSING_REQUIRED_CONTEXT,
        NOW,
        missing_context=(A, B),
    )
    with pytest.raises(ValueError):
        cli._validated_selected_result(fabricated, planning_request, selected)


def test_synthetic_selected_cli_shows_only_missing_identities() -> None:
    selected = descriptor()
    output: list[str] = []
    cli.entrypoint(
        ["planificar", "--estrategia", "sintetica"],
        output_fn=output.append,
        planning_manifest=StrategyManifest((selected,)),
        planning_clock=lambda: NOW,
    )
    assert sum("scope=" in line for line in output) == 2
    assert not any("private-value" in line for line in output)
    assert not any("Plan conceptual propuesto" in line for line in output)


def test_requirement_display_escapes_control_characters() -> None:
    item = PlanningContextRequirement("task", "topic", GLOBAL)
    object.__setattr__(item, "key", "topic\x1b[31m")
    safe = cli._format_planning_requirement(item)
    assert "\x1b" not in safe
    assert "\\x1b" in safe


def test_requirement_disclosure_does_not_use_operational_authorities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from iris.capabilities import CapabilityRuntime
    from iris.execution import ExecutionCoordinator
    from iris.memory import MemoryService
    from iris.plan_runs import PlanRunFactory

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Planning disclosure reached an operational authority")

    monkeypatch.setattr(cli, "OllamaProvider", forbidden)
    monkeypatch.setattr(CapabilityRuntime, "execute", forbidden)
    monkeypatch.setattr(ExecutionCoordinator, "execute", forbidden)
    monkeypatch.setattr(PlanRunFactory, "create", forbidden)
    monkeypatch.setattr(MemoryService, "get", forbidden)
    monkeypatch.setattr(MemoryService, "query", forbidden)
    monkeypatch.setattr(MemoryService, "store", forbidden)
    cli.entrypoint(["planificar", "--requisitos", "estudio"])
    cli.entrypoint(["planificar", "--estrategia", "estudio"])


def test_module_and_installed_requirement_entrypoints() -> None:
    executable = Path(sys.executable).with_name(
        "iris.exe" if os.name == "nt" else "iris"
    )
    assert executable.is_file()
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    for command in (
        [sys.executable, "-m", "iris", "planificar", "--requisitos", "estudio"],
        [str(executable), "planificar", "--requisitos", "estudio"],
    ):
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=environment,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        assert "Requisitos de contexto: ninguno." in completed.stdout
        assert "Plan conceptual propuesto" not in completed.stdout
