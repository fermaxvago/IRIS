"""WP076: one manifest owns discovery, exact selection and planner rules."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

import iris.__main__ as cli
from iris.core.request import Request
from iris.memory import ScopeKind
from iris.planning import (
    DeterministicPlanner,
    PlanningReason,
    PlanningRequest,
    PlanningResult,
    PlanningStatus,
)
from iris.planning.strategy_manifest import (
    StrategyDescriptor,
    StrategyManifest,
    built_in_manifest,
)
from iris.planning.study_strategy import STUDY_OBJECTIVE, study_session_rule

NOW = datetime(2026, 11, 11, tzinfo=UTC)


class RecordingPlanner:
    def __init__(self) -> None:
        self.delegate = DeterministicPlanner(
            built_in_manifest().rules, clock=lambda: NOW
        )
        self.calls: list[PlanningRequest] = []

    def plan(self, request: PlanningRequest) -> PlanningResult:
        self.calls.append(request)
        return self.delegate.plan(request)


def run(*args: str, planner: RecordingPlanner | None = None) -> list[str]:
    output: list[str] = []
    cli.entrypoint(
        ["planificar", *args],
        output_fn=output.append,
        planning_planner=planner,
        planning_clock=lambda: NOW,
        planning_id_factory=iter(("request-1", "goal-1", "planning-1")).__next__,
    )
    return output


def test_discovery_lists_only_valid_registered_strategy_without_planning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    planner = RecordingPlanner()
    monkeypatch.setattr(cli, "Request", lambda **_: pytest.fail("Request constructed"))
    monkeypatch.setattr(
        cli, "PlanningRequest", lambda **_: pytest.fail("PlanningRequest constructed")
    )
    output = run("--listar", planner=planner)
    assert len(output) == 1
    assert "estudio" in output[0] and STUDY_OBJECTIVE in output[0]
    assert "Preparación conceptual" in output[0]
    assert planner.calls == []


def test_exact_selection_preserves_literal_input_and_derived_goal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[Request] = []
    original = cli.Request

    def record(**kwargs: object) -> Request:
        value = original(**kwargs)
        requests.append(value)
        return value

    monkeypatch.setattr(cli, "Request", record)
    planner = RecordingPlanner()
    output = run("--estrategia", "estudio", planner=planner)
    assert len(planner.calls) == len(requests) == 1
    request = requests[0]
    planning = planner.calls[0]
    assert request.content == "estudio" and request.source == "cli"
    assert dict(request.metadata) == {
        "input_mode": "strategy_id",
        "strategy_id": "estudio",
    }
    assert planning.goal.objective == STUDY_OBJECTIVE
    assert planning.goal.scope.kind is ScopeKind.TASK
    assert planning.goal.scope.identifier == request.request_id
    assert planning.goal.provenance.source_id == request.request_id
    assert planning.goal.provenance.actor is None
    assert planning.context is None
    assert planning.goal.constraints == planning.goal.success_criteria == ()
    assert (
        len({request.request_id, planning.goal.goal_id, planning.planning_request_id})
        == 3
    )
    assert output[0] == "Estrategia seleccionada: estudio"
    assert sum("Resultado esperado:" in line for line in output) == 4
    assert any("No se ejecutó ninguna acción" in line for line in output)


@pytest.mark.parametrize(
    "args",
    [
        (),
        ("--estrategia", "desconocida"),
        ("--estrategia", "Estudio"),
        ("--estrategia", ""),
        ("--estrategia", "estudio", "--estrategia", "estudio"),
        ("--listar", "--listar"),
        ("--listar", "--objetivo", STUDY_OBJECTIVE),
        ("--estrategia", "estudio", "--objetivo", STUDY_OBJECTIVE),
        ("--objetivo", STUDY_OBJECTIVE, "--objetivo", STUDY_OBJECTIVE),
        ("--listar", "extra"),
        ("--objetivo", "x" * 161),
    ],
)
def test_invalid_modes_never_plan(args: tuple[str, ...]) -> None:
    planner = RecordingPlanner()
    with pytest.raises(SystemExit) as error:
        run(*args, planner=planner)
    assert error.value.code == 2
    assert not planner.calls


@pytest.mark.parametrize(
    "bad_id", ["", "Estudio", "1estudio", "estudio-dos", "é", "estudio\n"]
)
def test_manifest_rejects_invalid_identifiers(bad_id: str) -> None:
    with pytest.raises(ValueError):
        StrategyDescriptor(bad_id, "Descripción válida", study_session_rule())


def test_manifest_rejects_duplicate_ids_objectives_and_bad_descriptions() -> None:
    first = built_in_manifest().entries[0]
    assert built_in_manifest().rules == (first.rule,)
    with pytest.raises(ValueError):
        StrategyManifest(())
    with pytest.raises(ValueError):
        StrategyManifest((first, first))
    with pytest.raises(ValueError):
        StrategyManifest(
            (
                first,
                StrategyDescriptor(
                    "otro",
                    "Otro",
                    replace(first.rule, objective="  PREPARAR UNA SESIÓN DE ESTUDIO  "),
                ),
            )
        )
    for bad in ("", "  ", "Línea\nsegunda", "\x1b[31m", " \u202e"):
        with pytest.raises(ValueError):
            StrategyDescriptor("otro", bad, first.rule)
    with pytest.raises(ValueError):
        StrategyDescriptor("otro", "Válido", object())  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        StrategyManifest((object(),))  # type: ignore[arg-type]
    altered_rule = study_session_rule()
    object.__setattr__(altered_rule, "objective", "")
    with pytest.raises(ValueError):
        StrategyDescriptor("otro", "Válido", altered_rule)
    other = StrategyDescriptor(
        "aaa", "Otro objetivo", replace(first.rule, objective="Otro objetivo")
    )
    assert [
        entry.strategy_id for entry in StrategyManifest((first, other)).entries
    ] == ["aaa", "estudio"]


@pytest.mark.parametrize(
    "kind", ["foreign", "steps", "assumptions", "abstention", "wrong_type"]
)
def test_selected_result_rejects_wrong_strategy_or_identity(kind: str) -> None:
    class AdversarialPlanner:
        def plan(self, request: PlanningRequest) -> PlanningResult:
            valid = DeterministicPlanner(
                built_in_manifest().rules, clock=lambda: NOW
            ).plan(request)
            assert valid.plan is not None
            if kind == "foreign":
                return replace(valid, planning_request_id="foreign")
            if kind == "abstention":
                return PlanningResult(
                    "result",
                    request.planning_request_id,
                    request.goal.goal_id,
                    PlanningStatus.UNSATISFIABLE,
                    PlanningReason.NO_REGISTERED_STRATEGY,
                    NOW,
                )
            if kind == "wrong_type":
                return object()  # type: ignore[return-value]
            plan = (
                replace(valid.plan, steps=valid.plan.steps[:1])
                if kind == "steps"
                else replace(valid.plan, assumptions=("unexpected",))
            )
            return replace(valid, plan=plan)

    output: list[str] = []
    with pytest.raises(SystemExit):
        cli.entrypoint(
            ["planificar", "--estrategia", "estudio"],
            planning_planner=AdversarialPlanner(),
            planning_clock=lambda: NOW,
            output_fn=output.append,
        )
    assert not output


def test_objective_mode_remains_exact_and_unknown_objective_abstains() -> None:
    assert any("Plan conceptual" in line for line in run("--objetivo", STUDY_OBJECTIVE))
    assert any(
        "No hay una estrategia registrada" in line
        for line in run("--objetivo", "Otro objetivo")
    )


def test_discovery_and_selection_do_not_use_operational_authorities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from iris.capabilities import CapabilityRuntime
    from iris.execution import ExecutionCoordinator
    from iris.memory import MemoryService
    from iris.plan_runs import PlanRunFactory

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("planning reached an operational authority")

    monkeypatch.setattr(cli, "OllamaProvider", forbidden)
    monkeypatch.setattr(CapabilityRuntime, "execute", forbidden)
    monkeypatch.setattr(ExecutionCoordinator, "execute", forbidden)
    monkeypatch.setattr(PlanRunFactory, "create", forbidden)
    monkeypatch.setattr(MemoryService, "get", forbidden)
    monkeypatch.setattr(MemoryService, "query", forbidden)
    monkeypatch.setattr(MemoryService, "store", forbidden)
    assert run("--listar")
    assert run("--estrategia", "estudio")


def test_real_module_and_installed_entrypoints() -> None:
    executable = Path(sys.executable).with_name(
        "iris.exe" if os.name == "nt" else "iris"
    )
    assert executable.is_file()
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    for prefix in ([sys.executable, "-m", "iris"], [str(executable)]):
        for mode, expected in (
            (["--listar"], "estudio"),
            (["--estrategia", "estudio"], "Plan conceptual propuesto"),
        ):
            result = subprocess.run(
                [*prefix, "planificar", *mode],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                check=False,
            )
            assert result.returncode == 0, result.stderr
            assert expected in result.stdout
