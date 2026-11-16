"""WP081: production conceptual review strategies and CLI boundaries."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from iris.planning import DeterministicPlanner
from iris.planning.review_strategies import (
    COMPATIBILITY_OBJECTIVE,
    SECURITY_OBJECTIVE,
    compatibility_review_rule,
    security_review_rule,
)
from iris.planning.strategy_manifest import built_in_manifest
from iris.planning.study_strategy import study_session_rule

IDS = ("revision_compatibilidad", "revision_seguridad")
OBJECTIVES = (COMPATIBILITY_OBJECTIVE, SECURITY_OBJECTIVE)


def invoke(
    *args: str, input_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "iris", "planificar", *args],
        input=input_text,
        text=True,
        capture_output=True,
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        check=False,
    )


def test_production_manifest_is_exact_and_conceptual() -> None:
    manifest = built_in_manifest()
    assert tuple(entry.strategy_id for entry in manifest.entries) == (
        "estudio",
        *IDS,
    )
    assert len({entry.rule.objective.casefold() for entry in manifest.entries}) == 3
    assert manifest.entries[0].rule == study_session_rule()
    assert manifest.rules == tuple(entry.rule for entry in manifest.entries)
    assert manifest.resolve(IDS[0]).rule == compatibility_review_rule()
    assert manifest.resolve(IDS[1]).rule == security_review_rule()
    assert manifest.entries[1].rule.steps != manifest.entries[2].rule.steps
    for entry, objective in zip(manifest.entries[1:], OBJECTIVES, strict=True):
        rule = entry.rule
        assert rule.objective == objective
        assert rule.assumptions == rule.required_context == ()
        assert tuple(step.step_id for step in rule.steps) == ("a", "b", "c", "d")
        assert tuple(step.depends_on for step in rule.steps) == (
            (),
            ("a",),
            ("b",),
            ("c",),
        )
        assert all(
            step.objective
            and step.expected_outcome
            and step.required_handling is None
            and step.constraints == ()
            for step in rule.steps
        )
    DeterministicPlanner(manifest.rules)


@pytest.mark.parametrize(
    "strategy_id,objective", tuple(zip(IDS, OBJECTIVES, strict=True))
)
def test_installed_strategy_and_objective_json(
    strategy_id: str, objective: str
) -> None:
    for mode in (("--estrategia", strategy_id), ("--objetivo", objective)):
        result = invoke(*mode, "--formato", "json")
        assert result.returncode == 0 and result.stderr == ""
        document = json.loads(result.stdout)
        assert set(document) == {
            "format_version",
            "input",
            "planning_request",
            "planning_result",
        }
        assert document["format_version"] == "1.0"
        assert document["planning_request"]["goal"]["objective"] == objective
        assert document["planning_result"]["status"] == "plan_created"
        steps = document["planning_result"]["plan"]["steps"]
        assert [step["step_id"] for step in steps] == list("abcd")
        assert [step["depends_on"] for step in steps] == [[], ["a"], ["b"], ["c"]]
        assert all(step["required_handling"] is None for step in steps)
    normalized = invoke(
        "--objetivo", "  " + objective.upper() + "  ", "--formato", "json"
    )
    assert normalized.returncode == 0
    assert json.loads(normalized.stdout)["planning_result"]["status"] == "plan_created"


def test_installed_catalog_and_requirements() -> None:
    catalog = invoke("--listar", "--formato", "json")
    assert catalog.returncode == 0 and catalog.stderr == ""
    data = json.loads(catalog.stdout)
    assert set(data) == {"format_version", "document_type", "strategies"}
    assert [entry["strategy_id"] for entry in data["strategies"]] == ["estudio", *IDS]
    for strategy_id, objective in zip(IDS, OBJECTIVES, strict=True):
        result = invoke("--requisitos", strategy_id, "--formato", "json")
        assert result.returncode == 0 and result.stderr == ""
        requirements = json.loads(result.stdout)
        assert set(requirements) == {
            "format_version",
            "document_type",
            "strategy_id",
            "objective",
            "required_context",
        }
        assert requirements["objective"] == objective
        assert requirements["required_context"] == []


def test_installed_console_script_selects_review_strategy() -> None:
    command = Path(sys.executable).parent / ("iris.exe" if os.name == "nt" else "iris")
    result = subprocess.run(
        [str(command), "planificar", "--estrategia", IDS[0], "--formato", "json"],
        text=True,
        capture_output=True,
        cwd=Path(__file__).resolve().parents[1],
        check=False,
    )
    assert result.returncode == 0 and result.stderr == ""
    assert json.loads(result.stdout)["planning_result"]["status"] == "plan_created"


@pytest.mark.parametrize("strategy_id", IDS)
def test_context_rejected_before_reading_stdin(strategy_id: str) -> None:
    result = invoke(
        "--estrategia",
        strategy_id,
        "--contexto-stdin",
        "--formato",
        "json",
        input_text="private-marker",
    )
    assert result.returncode == 2 and result.stdout == ""
    assert "private-marker" not in result.stderr


def test_invalid_selection_and_unknown_objective_keep_existing_semantics() -> None:
    for args in (
        ("--estrategia", "revision_desconocida", "--formato", "json"),
        ("--estrategia", IDS[0], "--listar", "--formato", "json"),
    ):
        result = invoke(*args)
        assert result.returncode == 2 and result.stdout == ""
    result = invoke("--objetivo", "Objetivo no registrado", "--formato", "json")
    assert result.returncode == 0 and result.stderr == ""
    data = json.loads(result.stdout)
    assert data["planning_result"]["status"] == "unsatisfiable"
    assert data["planning_result"]["reason"] == "no_registered_strategy"
    assert data["planning_result"]["plan"] is None
