"""WP079: faithful, read-only JSON strategy discovery."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

import iris.__main__ as cli
import iris.planning.discovery_json as discovery
from iris.memory.models import MemoryScope, ScopeKind
from iris.planning import DeterministicPlanner, PlanningContextRequirement, PlanningRule
from iris.planning.strategy_manifest import (
    StrategyDescriptor,
    StrategyManifest,
    built_in_manifest,
)
from iris.planning.study_strategy import STUDY_OBJECTIVE


def run(*args: str, manifest: StrategyManifest | None = None) -> dict[str, object]:
    output: list[str] = []
    cli.entrypoint(
        ["planificar", *args, "--formato", "json"],
        output_fn=output.append,
        planning_manifest=manifest,
    )
    assert len(output) == 1
    return cast(dict[str, object], json.loads(output[0]))


def synthetic_manifest() -> StrategyManifest:
    requirements = (
        PlanningContextRequirement("task", "topic", MemoryScope(ScopeKind.GLOBAL)),
        PlanningContextRequirement(
            "task", "deadline", MemoryScope(ScopeKind.TASK, "request-1")
        ),
    )
    return StrategyManifest(
        (
            StrategyDescriptor(
                "zeta",
                "Descripción sintética",
                PlanningRule("Objetivo Z", required_context=requirements),
            ),
            StrategyDescriptor("alfa", "Descripción A", PlanningRule("Objetivo A")),
        )
    )


def test_production_catalog_and_requirements() -> None:
    catalog = run("--listar")
    assert catalog == {
        "format_version": "1.0",
        "document_type": "strategy_catalog",
        "strategies": [
            {
                "strategy_id": "estudio",
                "description": built_in_manifest().entries[0].description,
                "objective": STUDY_OBJECTIVE,
            }
        ],
    }
    assert run("--requisitos", "estudio") == {
        "format_version": "1.0",
        "document_type": "strategy_requirements",
        "strategy_id": "estudio",
        "objective": STUDY_OBJECTIVE,
        "required_context": [],
    }


def test_synthetic_catalog_and_requirements_are_complete_and_ordered() -> None:
    manifest = synthetic_manifest()
    catalog = run("--listar", manifest=manifest)
    assert [item["strategy_id"] for item in catalog["strategies"]] == ["alfa", "zeta"]
    assert catalog["strategies"][1] == {
        "strategy_id": "zeta",
        "description": "Descripción sintética",
        "objective": "Objetivo Z",
    }
    requirements = run("--requisitos", "zeta", manifest=manifest)
    assert requirements["required_context"] == [
        item.to_data() for item in manifest.resolve("zeta").rule.required_context
    ]
    assert requirements["required_context"] == [
        {
            "kind": "task",
            "key": "topic",
            "scope": {"kind": "global", "identifier": None},
        },
        {
            "kind": "task",
            "key": "deadline",
            "scope": {"kind": "task", "identifier": "request-1"},
        },
    ]


@pytest.mark.parametrize("mutation", ["kind", "key", "scope_kind", "scope_id"])
def test_mutated_canonical_nested_state_fails_closed(mutation: str) -> None:
    manifest = synthetic_manifest()
    item = manifest.resolve("zeta").rule.required_context[0]
    if mutation == "kind":
        object.__setattr__(item, "kind", "BAD")
    elif mutation == "key":
        object.__setattr__(item, "key", "bad key")
    elif mutation == "scope_kind":
        object.__setattr__(item.scope, "kind", "wrong")
    else:
        object.__setattr__(item.scope, "identifier", "wrong")
    output: list[str] = []
    with pytest.raises(SystemExit):
        cli.entrypoint(
            ["planificar", "--requisitos", "zeta", "--formato", "json"],
            output_fn=output.append,
            planning_manifest=manifest,
        )
    assert output == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("strategy_id", "fake"),
        ("description", "Autonomous execution strategy."),
        ("objective", "Execute arbitrary tasks."),
        ("format_version", "2.0"),
        ("document_type", "other"),
        ("strategy_id", 1),
    ],
)
def test_catalog_public_falsification_is_rejected(
    monkeypatch: pytest.MonkeyPatch, field: str, value: object
) -> None:
    original = discovery._catalog_data

    def false_data(manifest: StrategyManifest) -> dict[str, object]:
        data = original(manifest)
        if field in ("format_version", "document_type"):
            data[field] = value
        else:
            data["strategies"][0][field] = value
        return data

    monkeypatch.setattr(discovery, "_catalog_data", false_data)
    with pytest.raises(ValueError):
        discovery.catalog_json_document(built_in_manifest())


@pytest.mark.parametrize("tampering", ["extra", "missing", "array", "cardinality"])
def test_catalog_public_shape_is_exact(
    monkeypatch: pytest.MonkeyPatch, tampering: str
) -> None:
    original = discovery._catalog_data

    def false_data(manifest: StrategyManifest) -> dict[str, object]:
        data = original(manifest)
        if tampering == "extra":
            data["private_metadata"] = "hidden"
        elif tampering == "missing":
            data.pop("document_type")
        elif tampering == "array":
            data["strategies"] = "estudio"
        else:
            data["strategies"].append(data["strategies"][0])
        return data

    monkeypatch.setattr(discovery, "_catalog_data", false_data)
    with pytest.raises(ValueError):
        discovery.catalog_json_document(built_in_manifest())


@pytest.mark.parametrize(
    "tampering",
    [
        "id",
        "objective",
        "kind",
        "key",
        "scope",
        "order",
        "extra",
        "missing",
        "null",
        "type",
    ],
)
def test_requirements_public_falsification_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tampering: str
) -> None:
    original = discovery._requirements_data

    def false_data(descriptor: StrategyDescriptor) -> dict[str, object]:
        data = original(descriptor)
        reqs = data["required_context"]
        if tampering == "id":
            data["strategy_id"] = "wrong"
        elif tampering == "objective":
            data["objective"] = "wrong"
        elif tampering == "kind":
            reqs[0]["kind"] = "other"
        elif tampering == "key":
            reqs[0]["key"] = "other"
        elif tampering == "scope":
            reqs[0]["scope"]["identifier"] = "wrong"
        elif tampering == "order":
            reqs.reverse()
        elif tampering == "extra":
            reqs[0]["extra"] = "leak"
        elif tampering == "missing":
            reqs[0].pop("key")
        elif tampering == "null":
            data["objective"] = None
        else:
            data["required_context"] = object()
        return data

    monkeypatch.setattr(discovery, "_requirements_data", false_data)
    with pytest.raises(ValueError):
        discovery.requirements_json_document(synthetic_manifest(), "zeta")


def test_discovery_does_not_evaluate_planning_or_construct_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("Request", "Goal", "PlanningRequest", "PlanningResult"):
        monkeypatch.setattr(
            cli, name, lambda *_, **__: pytest.fail("Planning state constructed")
        )
    monkeypatch.setattr(
        DeterministicPlanner,
        "plan",
        lambda *_, **__: pytest.fail("Planning evaluated"),
    )
    run("--listar")
    run("--requisitos", "estudio")


@pytest.mark.parametrize(
    "args",
    [
        ("--requisitos", "desconocida", "--formato", "json"),
        ("--listar", "--formato", "json", "--formato", "json"),
        ("--listar", "--formato", "xml"),
        ("--listar", "--requisitos", "estudio", "--formato", "json"),
    ],
)
def test_cli_errors_are_usage_errors_with_empty_stdout(
    args: tuple[str, ...], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as error:
        cli.entrypoint(["planificar", *args])
    assert error.value.code == 2
    assert capsys.readouterr().out == ""


def test_serialization_failure_emits_no_partial_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(discovery.json, "dumps", lambda *_, **__: 1 / 0)
    output: list[str] = []
    with pytest.raises(SystemExit) as error:
        cli.entrypoint(
            ["planificar", "--listar", "--formato", "json"], output_fn=output.append
        )
    assert "JSON" in str(error.value)
    assert output == []


def test_serializer_must_return_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(discovery.json, "dumps", lambda *_, **__: 123)
    with pytest.raises(ValueError):
        discovery.catalog_json_document(built_in_manifest())


def test_invalid_manifest_and_representation_emit_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = built_in_manifest()
    object.__setattr__(manifest.entries[0], "description", "")
    output: list[str] = []
    with pytest.raises(SystemExit):
        cli.entrypoint(
            ["planificar", "--listar", "--formato", "json"],
            planning_manifest=manifest,
            output_fn=output.append,
        )
    assert output == []
    monkeypatch.setattr(discovery, "_catalog_data", lambda _: {"bad": "data"})
    with pytest.raises(SystemExit):
        cli.entrypoint(
            ["planificar", "--listar", "--formato", "json"],
            output_fn=output.append,
        )
    assert output == []


@pytest.mark.parametrize(
    "prefix",
    [
        [sys.executable, "-m", "iris"],
        [
            str(
                Path(sys.executable).parent
                / ("iris.exe" if os.name == "nt" else "iris")
            )
        ],
    ],
)
def test_independent_subprocess_consumer(prefix: list[str]) -> None:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    root = Path(__file__).resolve().parents[1]
    catalog = subprocess.run(
        [*prefix, "planificar", "--listar", "--formato", "json"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert catalog.stderr == ""
    data = json.loads(catalog.stdout)
    assert data["strategies"][0]["objective"] == STUDY_OBJECTIVE
    strategy_id = data["strategies"][0]["strategy_id"]
    requirements = subprocess.run(
        [*prefix, "planificar", "--requisitos", strategy_id, "--formato", "json"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert requirements.stderr == ""
    assert json.loads(requirements.stdout)["required_context"] == []


def test_valid_control_characters_are_json_encoded() -> None:
    manifest = StrategyManifest(
        (StrategyDescriptor("control", "Unicode válido", PlanningRule("Tema\nuno")),)
    )
    serialized = discovery.catalog_json_document(manifest)
    assert "\\n" in serialized
    assert json.loads(serialized)["strategies"][0]["objective"] == "Tema\nuno"
