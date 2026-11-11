"""WP075: the installed CLI exposes one bounded, non-executable strategy."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

import iris.__main__ as cli
from iris.capabilities import CapabilityRuntime
from iris.core.request import Request
from iris.execution import ExecutionCoordinator
from iris.memory import MemoryScope, MemoryService, ScopeKind
from iris.plan_runs import PlanRunFactory
from iris.planning import (
    ConstraintKind,
    DeterministicPlanner,
    Goal,
    GoalProvenance,
    GoalScope,
    Plan,
    Planner,
    PlanningConstraint,
    PlanningContextRequirement,
    PlanningReason,
    PlanningRequest,
    PlanningResult,
    PlanningStatus,
)
from iris.planning.study_strategy import STUDY_OBJECTIVE, study_session_rule

NOW = datetime(2026, 11, 11, 12, tzinfo=UTC)


@dataclass
class RecordingPlanner:
    delegate: Planner
    calls: list[PlanningRequest] = field(default_factory=list)
    results: list[PlanningResult] = field(default_factory=list)

    def plan(self, request: PlanningRequest) -> PlanningResult:
        self.calls.append(request)
        result = self.delegate.plan(request)
        self.results.append(result)
        return result


@dataclass
class StubPlanner:
    make_result: Callable[[PlanningRequest], object]
    calls: list[PlanningRequest] = field(default_factory=list)

    def plan(self, request: PlanningRequest) -> PlanningResult:
        self.calls.append(request)
        return cast(PlanningResult, self.make_result(request))


def builtin_recorder() -> RecordingPlanner:
    return RecordingPlanner(
        DeterministicPlanner((study_session_rule(),), clock=lambda: NOW)
    )


def run(
    objective: str,
    *,
    planner: Planner | None = None,
    id_factory: Callable[[], str] | None = None,
) -> list[str]:
    output: list[str] = []
    cli.entrypoint(
        ["planificar", "--objetivo", objective],
        input_fn=lambda _: pytest.fail("planning must not prompt"),
        output_fn=output.append,
        planning_planner=planner,
        planning_clock=lambda: NOW,
        planning_id_factory=id_factory,
    )
    return output


def result(
    request: PlanningRequest,
    status: PlanningStatus,
    reason: PlanningReason,
    *,
    plan: Plan | None = None,
    missing: tuple[PlanningContextRequirement, ...] = (),
    conflicts: tuple[str, ...] = (),
) -> PlanningResult:
    return PlanningResult(
        planning_result_id="result-1",
        planning_request_id=request.planning_request_id,
        goal_id=request.goal.goal_id,
        status=status,
        reason=reason,
        created_at=NOW,
        plan=plan,
        missing_context=missing,
        constraint_conflicts=conflicts,
    )


def test_t075_01_production_entry_uses_the_only_builtin_study_rule() -> None:
    rule = study_session_rule()
    assert rule.objective == STUDY_OBJECTIVE
    assert len(rule.steps) == 4
    assert [step.step_id for step in rule.steps] == ["a", "b", "c", "d"]
    assert [step.depends_on for step in rule.steps] == [(), ("a",), ("b",), ("c",)]
    assert not rule.assumptions and not rule.required_context
    assert all(
        step.required_handling is None and not step.constraints for step in rule.steps
    )

    output: list[str] = []
    cli.entrypoint(
        ["planificar", "--objetivo", STUDY_OBJECTIVE], output_fn=output.append
    )
    assert any("Plan conceptual propuesto" in line for line in output)
    assert sum("Resultado esperado:" in line for line in output) == 4
    assert [
        line[0] for line in output if line.startswith(("a. ", "b. ", "c. ", "d. "))
    ] == ["a", "b", "c", "d"]
    assert any("No se ejecutó ninguna acción" in line for line in output)


def test_t075_02_unregistered_objective_evaluates_once_and_abstains() -> None:
    planner = builtin_recorder()
    output = run("Organizar una excursión", planner=planner)
    assert len(planner.calls) == len(planner.results) == 1
    assert planner.results[0].status is PlanningStatus.UNSATISFIABLE
    assert planner.results[0].reason is PlanningReason.NO_REGISTERED_STRATEGY
    assert planner.results[0].plan is None
    assert any("No hay una estrategia registrada" in line for line in output)
    assert any("no significa que sea imposible" in line for line in output)
    assert not any("Plan conceptual propuesto" in line for line in output)


@pytest.mark.parametrize(
    "arguments",
    [
        ["planificar"],
        ["planificar", "--objetivo", ""],
        ["planificar", "--objetivo", "   "],
        ["planificar", "--objetivo", "x" * 161],
        ["planificar", "--objetivo", "Tema\npráctica"],
        ["planificar", "--objetivo", "Tema\r"],
        ["planificar", "--objetivo", "Tema\tpráctica"],
        ["planificar", "--objetivo", "Tema\x1b[31m"],
        ["planificar", "--objetivo", "Tema\u202epráctica"],
        ["planificar", "--objetivo", STUDY_OBJECTIVE, "extra"],
        ["planificar", "--objetivo", STUDY_OBJECTIVE, "--objetivo", "otro"],
    ],
)
def test_t075_03_invalid_arguments_never_invoke_planner(
    arguments: list[str],
) -> None:
    planner = builtin_recorder()
    with pytest.raises(SystemExit) as exc:
        cli.entrypoint(arguments, planning_planner=planner)
    assert exc.value.code == 2
    assert not planner.calls


def test_t075_04_existing_exact_normalization_and_conservative_abstention() -> None:
    assert any(
        "Plan conceptual" in line
        for line in run("  pREPARAR   UNA  SESIÓN DE ESTUDIO  ")
    )
    assert any(
        "No hay una estrategia" in line for line in run("Preparar sesión de estudio")
    )


def test_t075_05_request_goal_and_planning_provenance_are_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identifiers = iter(
        ("request-1", "goal-1", "planning-1", "request-2", "goal-2", "planning-2")
    )
    planner = builtin_recorder()
    requests: list[Request] = []
    original_request = cli.Request

    def record_request(*args: object, **kwargs: object) -> Request:
        request = original_request(*args, **kwargs)
        requests.append(request)
        return request

    monkeypatch.setattr(cli, "Request", record_request)
    for _ in range(2):
        run(STUDY_OBJECTIVE, planner=planner, id_factory=lambda: next(identifiers))
    first, second = planner.calls
    assert [request.source for request in requests] == ["cli", "cli"]
    assert [request.content for request in requests] == [STUDY_OBJECTIVE] * 2
    assert [request.request_id for request in requests] == ["request-1", "request-2"]
    assert first.planning_request_id == "planning-1"
    assert first.goal.goal_id == "goal-1"
    assert first.goal.objective == STUDY_OBJECTIVE
    assert first.goal.scope == GoalScope(ScopeKind.TASK, "request-1")
    assert first.goal.provenance == GoalProvenance("request", "request-1", None)
    assert first.goal.constraints == first.goal.success_criteria == ()
    assert first.context is None and first.created_at == NOW
    assert second.planning_request_id == "planning-2"
    assert second.goal.scope.identifier == "request-2"
    assert second.goal.goal_id == "goal-2"
    assert (
        len(
            {first.planning_request_id, first.goal.goal_id, first.goal.scope.identifier}
        )
        == 3
    )


@pytest.mark.parametrize("foreign", ["request", "goal", "type"])
def test_t075_06_foreign_or_wrong_planner_result_never_renders_success(
    foreign: str,
) -> None:
    def make(request: PlanningRequest) -> object:
        if foreign == "type":
            return object()
        goal_id = "foreign-goal" if foreign == "goal" else request.goal.goal_id
        return PlanningResult(
            planning_result_id="result-1",
            planning_request_id=(
                "foreign-request"
                if foreign == "request"
                else request.planning_request_id
            ),
            goal_id=goal_id,
            status=PlanningStatus.PLAN_CREATED,
            reason=PlanningReason.DECOMPOSITION_CREATED,
            created_at=NOW,
            plan=Plan("plan-1", goal_id, (), study_session_rule().steps),
        )

    planner = StubPlanner(make)
    output: list[str] = []
    with pytest.raises(SystemExit) as exc:
        cli.entrypoint(
            ["planificar", "--objetivo", STUDY_OBJECTIVE],
            output_fn=output.append,
            planning_planner=planner,
            planning_clock=lambda: NOW,
        )
    assert "contrato de planificación inválido" in str(exc.value)
    assert len(planner.calls) == 1
    assert not output


@pytest.mark.parametrize(
    "status,reason,fragment",
    [
        (
            PlanningStatus.NO_PLAN_REQUIRED,
            PlanningReason.DECOMPOSITION_UNNECESSARY,
            "no confirma",
        ),
        (
            PlanningStatus.INSUFFICIENT_CONTEXT,
            PlanningReason.MISSING_REQUIRED_CONTEXT,
            "no se consultó",
        ),
        (
            PlanningStatus.UNSATISFIABLE,
            PlanningReason.NO_REGISTERED_STRATEGY,
            "No hay una estrategia",
        ),
    ],
)
def test_t075_07_valid_other_outcomes_are_rendered_truthfully(
    status: PlanningStatus, reason: PlanningReason, fragment: str
) -> None:
    def make(request: PlanningRequest) -> PlanningResult:
        missing = (
            (
                PlanningContextRequirement(
                    "task", "topic", MemoryScope(ScopeKind.GLOBAL)
                ),
            )
            if status is PlanningStatus.INSUFFICIENT_CONTEXT
            else ()
        )
        return result(request, status, reason, missing=missing)

    planner = StubPlanner(make)
    assert any(fragment in line for line in run(STUDY_OBJECTIVE, planner=planner))
    assert len(planner.calls) == 1


def test_t075_07_conflicting_constraints_require_supplied_constraints() -> None:
    conflicts = ("required_and_forbidden:time",)
    planner = StubPlanner(
        lambda request: result(
            request,
            PlanningStatus.UNSATISFIABLE,
            PlanningReason.CONFLICTING_CONSTRAINTS,
            conflicts=conflicts,
        )
    )
    with pytest.raises(SystemExit):
        run(STUDY_OBJECTIVE, planner=planner)

    goal = Goal(
        "goal-1",
        STUDY_OBJECTIVE,
        GoalScope(ScopeKind.TASK, "request-1"),
        GoalProvenance("request", "request-1", None),
        constraints=(
            PlanningConstraint(ConstraintKind.REQUIRE, "time", "morning"),
            PlanningConstraint(ConstraintKind.FORBID, "time", "morning"),
        ),
    )
    request = PlanningRequest("planning-1", goal, NOW)
    accepted = cli._validated_planning_result(planner.plan(request), request)
    output: list[str] = []
    cli._show_planning_result(request, accepted, output.append)
    assert any(
        "restricciones proporcionadas son incompatibles" in line for line in output
    )
    assert not any("Plan conceptual" in line for line in output)


def test_t075_08_planning_entry_does_not_invoke_operational_authorities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("planning invoked an operational authority")

    monkeypatch.setattr(cli, "OllamaProvider", forbidden)
    monkeypatch.setattr(CapabilityRuntime, "execute", forbidden)
    monkeypatch.setattr(ExecutionCoordinator, "execute", forbidden)
    monkeypatch.setattr(PlanRunFactory, "create", forbidden)
    monkeypatch.setattr(MemoryService, "get", forbidden)
    monkeypatch.setattr(MemoryService, "query", forbidden)
    monkeypatch.setattr(MemoryService, "store", forbidden)
    output = run(STUDY_OBJECTIVE)
    assert any("No se ejecutó ninguna acción" in line for line in output)


def test_t075_09_legacy_entry_still_uses_original_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    monkeypatch.setattr(cli, "main", lambda **kwargs: calls.append(kwargs))
    cli.entrypoint([])
    assert len(calls) == 1


def test_t075_10_module_and_installed_console_entry_work_without_ollama() -> None:
    executable = Path(sys.executable).with_name(
        "iris.exe" if os.name == "nt" else "iris"
    )
    assert executable.is_file()
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    for command in (
        [sys.executable, "-m", "iris", "planificar", "--objetivo", STUDY_OBJECTIVE],
        [str(executable), "planificar", "--objetivo", STUDY_OBJECTIVE],
    ):
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            env=environment,
        )
        assert completed.returncode == 0, completed.stderr
        assert "Plan conceptual propuesto" in completed.stdout
        assert completed.stdout.count("Resultado esperado:") == 4
        assert "No se ejecutó ninguna acción" in completed.stdout
    unsupported = subprocess.run(
        [sys.executable, "-m", "iris", "planificar", "--objetivo", "Objetivo ajeno"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        env=environment,
    )
    assert unsupported.returncode == 0
    assert "No hay una estrategia registrada" in unsupported.stdout
