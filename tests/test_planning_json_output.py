"""WP078: public JSON 1.0 is one validated Planning evaluation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

import iris.__main__ as cli
import iris.planning.public_json as public_json
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
from iris.core.request import Request
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
from iris.planning.study_strategy import STUDY_OBJECTIVE
from iris.work_identity import (
    RequestWorkReference,
    WorkOrigin,
    WorkSubject,
    WorkSubjectKind,
)

NOW = datetime(2026, 11, 14, tzinfo=UTC)


class RecordingPlanner:
    def __init__(self, rules: tuple[PlanningRule, ...] | None = None) -> None:
        self.delegate = DeterministicPlanner(
            built_in_manifest().rules if rules is None else rules,
            clock=lambda: NOW,
            plan_id_factory=lambda: "plan-1",
            result_id_factory=lambda: "result-1",
        )
        self.calls: list[PlanningRequest] = []

    def plan(self, request: PlanningRequest) -> PlanningResult:
        self.calls.append(request)
        return self.delegate.plan(request)


def run_json(
    *arguments: str,
    planner: object | None = None,
    manifest: StrategyManifest | None = None,
) -> tuple[dict[str, object], str]:
    output: list[str] = []
    cli.entrypoint(
        ["planificar", *arguments, "--formato", "json"],
        output_fn=output.append,
        planning_planner=cast(RecordingPlanner | None, planner),
        planning_manifest=manifest,
        planning_clock=lambda: NOW,
        planning_id_factory=iter(("request-1", "goal-1", "planning-1")).__next__,
    )
    assert len(output) == 1
    return cast(dict[str, object], json.loads(output[0])), output[0]


def test_strategy_json_has_exact_public_shape_and_provenance() -> None:
    recorder = RecordingPlanner()
    document, serialized = run_json("--estrategia", "estudio", planner=recorder)
    assert len(recorder.calls) == 1
    assert set(document) == {
        "format_version",
        "input",
        "planning_request",
        "planning_result",
    }
    assert document["format_version"] == "1.0"
    assert document["input"] == {"mode": "strategy_id", "strategy_id": "estudio"}
    request = cast(dict[str, object], document["planning_request"])
    assert set(request) == {
        "planning_request_id",
        "goal",
        "created_at",
        "context_snapshot_id",
    }
    goal = cast(dict[str, object], request["goal"])
    assert set(goal) == {
        "goal_id",
        "objective",
        "scope",
        "provenance",
        "constraints",
        "success_criteria",
    }
    assert goal["objective"] == STUDY_OBJECTIVE
    assert goal["scope"] == {"kind": "task", "identifier": "request-1"}
    assert goal["provenance"] == {
        "source_type": "request",
        "source_id": "request-1",
        "actor": None,
    }
    assert goal["constraints"] == goal["success_criteria"] == []
    assert request["context_snapshot_id"] is None
    result = cast(dict[str, object], document["planning_result"])
    assert set(result) == {
        "planning_result_id",
        "planning_request_id",
        "goal_id",
        "status",
        "reason",
        "created_at",
        "plan",
        "missing_context",
        "constraint_conflicts",
    }
    assert result["status"] == "plan_created"
    assert result["reason"] == "decomposition_created"
    assert result["planning_request_id"] == request["planning_request_id"]
    assert result["goal_id"] == goal["goal_id"]
    plan = cast(dict[str, object], result["plan"])
    assert set(plan) == {"plan_id", "goal_id", "assumptions", "steps"}
    steps = cast(list[dict[str, object]], plan["steps"])
    assert len(steps) == 4
    assert [step["step_id"] for step in steps] == ["a", "b", "c", "d"]
    assert [step["depends_on"] for step in steps] == [[], ["a"], ["b"], ["c"]]
    assert all(
        set(step)
        == {
            "step_id",
            "objective",
            "depends_on",
            "required_handling",
            "constraints",
            "expected_outcome",
        }
        for step in steps
    )
    assert "No se ejecutó" not in serialized and "executed" not in serialized


def test_objective_json_preserves_literal_mode_and_normalized_matching() -> None:
    recorder = RecordingPlanner()
    document, _ = run_json(
        "--objetivo", "  pREPARAR  UNA   SESIÓN DE ESTUDIO  ", planner=recorder
    )
    assert len(recorder.calls) == 1
    assert document["input"] == {"mode": "objective"}
    request = cast(dict[str, object], document["planning_request"])
    goal = cast(dict[str, object], request["goal"])
    assert goal["objective"] == "pREPARAR  UNA   SESIÓN DE ESTUDIO"
    result = cast(dict[str, object], document["planning_result"])
    assert result["status"] == "plan_created"


def test_unknown_objective_is_valid_abstention() -> None:
    recorder = RecordingPlanner()
    document, _ = run_json("--objetivo", "Objetivo no registrado", planner=recorder)
    assert len(recorder.calls) == 1
    result = cast(dict[str, object], document["planning_result"])
    assert result["status"] == "unsatisfiable"
    assert result["reason"] == "no_registered_strategy"
    assert result["plan"] is None


@pytest.mark.parametrize(
    "arguments",
    [
        ("--estrategia", "desconocida", "--formato", "json"),
        ("--estrategia", "estudio", "--formato", "xml"),
        ("--estrategia", "estudio", "--formato"),
        ("--estrategia", "estudio", "--formato", "json", "--formato", "json"),
        ("--listar", "--formato", "json"),
        ("--requisitos", "estudio", "--formato", "json"),
        ("--formato", "json"),
        ("--objetivo", STUDY_OBJECTIVE, "--estrategia", "estudio", "--formato", "json"),
        ("--objetivo", STUDY_OBJECTIVE, "--formato", "json", "extra"),
    ],
)
def test_invalid_json_cli_arguments_are_usage_errors(
    arguments: tuple[str, ...], capsys: pytest.CaptureFixture[str]
) -> None:
    planner = RecordingPlanner()
    with pytest.raises(SystemExit) as error:
        cli.entrypoint(["planificar", *arguments], planning_planner=planner)
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err
    assert planner.calls == []


@pytest.mark.parametrize(
    "tampering",
    ["foreign_request", "foreign_goal", "steps", "assumptions", "wrong_type"],
)
def test_invalid_selected_result_emits_no_json(tampering: str) -> None:
    class AdversarialPlanner(RecordingPlanner):
        def plan(self, request: PlanningRequest) -> PlanningResult:
            valid = super().plan(request)
            assert valid.plan is not None
            if tampering == "foreign_request":
                return replace(valid, planning_request_id="foreign")
            if tampering == "foreign_goal":
                return replace(
                    valid,
                    goal_id="foreign",
                    plan=replace(valid.plan, goal_id="foreign"),
                )
            if tampering == "steps":
                return replace(
                    valid, plan=replace(valid.plan, steps=valid.plan.steps[:1])
                )
            if tampering == "assumptions":
                return replace(
                    valid, plan=replace(valid.plan, assumptions=("invented",))
                )
            return cast(PlanningResult, object())

    output: list[str] = []
    with pytest.raises(SystemExit):
        cli.entrypoint(
            ["planificar", "--estrategia", "estudio", "--formato", "json"],
            output_fn=output.append,
            planning_planner=AdversarialPlanner(),
            planning_clock=lambda: NOW,
        )
    assert output == []


def test_unknown_objective_rejects_fabricated_plan() -> None:
    class FabricatingPlanner(RecordingPlanner):
        def plan(self, request: PlanningRequest) -> PlanningResult:
            steps = built_in_manifest().entries[0].rule.steps
            return PlanningResult(
                "result-1",
                request.planning_request_id,
                request.goal.goal_id,
                PlanningStatus.PLAN_CREATED,
                PlanningReason.DECOMPOSITION_CREATED,
                NOW,
                plan=Plan("plan-1", request.goal.goal_id, (), steps),
            )

    output: list[str] = []
    with pytest.raises(SystemExit):
        cli.entrypoint(
            ["planificar", "--objetivo", "Desconocido", "--formato", "json"],
            output_fn=output.append,
            planning_planner=FabricatingPlanner(),
            planning_clock=lambda: NOW,
        )
    assert output == []


def synthetic_evaluation(
    *,
    required: bool,
    steps: bool,
    context: bool = False,
    conflicts: bool = False,
) -> tuple[Request, PlanningRequest, PlanningResult, StrategyManifest]:
    requirement = PlanningContextRequirement(
        "task", "topic", MemoryScope(ScopeKind.GLOBAL)
    )
    rule = PlanningRule(
        "Objetivo sintético",
        steps=(PlanStep("a", "Preparar", "Preparado"),) if steps else (),
        required_context=(requirement,) if required else (),
    )
    manifest = StrategyManifest((StrategyDescriptor("sintetica", "Prueba", rule),))
    user = Request(
        "sintetica",
        "cli",
        request_id="request-1",
        metadata={"input_mode": "strategy_id", "strategy_id": "sintetica"},
    )
    snapshot = None
    if context:
        snapshot = ContextSnapshot(
            "snapshot-1",
            WorkSubject(
                WorkSubjectKind.REQUEST,
                RequestWorkReference("request-1"),
                WorkOrigin("request", "request-1"),
            ),
            NOW - timedelta(seconds=1),
            ContextBudget(1),
            (
                ContextItem(
                    "item-1",
                    "task",
                    "topic",
                    "private-context-value",
                    ContextEvidence(
                        EvidenceSource.CALLER,
                        "private-evidence-reference",
                        EpistemicStatus.DIRECT,
                    ),
                    MemoryScope(ScopeKind.GLOBAL),
                    Relevance.REQUIRED,
                    Freshness.CURRENT,
                ),
            ),
            ResolutionStatus.RESOLVED,
        )
    constraints = (
        (
            PlanningConstraint(ConstraintKind.REQUIRE, "time", "morning"),
            PlanningConstraint(ConstraintKind.FORBID, "time", "morning"),
        )
        if conflicts
        else ()
    )
    goal = Goal(
        "goal-1",
        rule.objective,
        GoalScope(ScopeKind.TASK, "request-1"),
        GoalProvenance("request", "request-1", None),
        constraints=constraints,
    )
    planning_request = PlanningRequest("planning-1", goal, NOW, snapshot)
    result = DeterministicPlanner(
        manifest.rules,
        clock=lambda: NOW,
        plan_id_factory=lambda: "plan-1",
        result_id_factory=lambda: "result-1",
    ).plan(planning_request)
    cli._validated_selected_result(result, planning_request, manifest.entries[0])
    return user, planning_request, result, manifest


@pytest.mark.parametrize(
    "required,steps,context,conflicts,status,reason",
    [
        (True, True, False, False, "insufficient_context", "missing_required_context"),
        (True, False, True, False, "no_plan_required", "decomposition_unnecessary"),
        (True, True, True, False, "plan_created", "decomposition_created"),
        (True, True, False, True, "unsatisfiable", "conflicting_constraints"),
    ],
)
def test_valid_synthetic_outcomes_reuse_existing_serializers(
    required: bool,
    steps: bool,
    context: bool,
    conflicts: bool,
    status: str,
    reason: str,
) -> None:
    user, request, result, _ = synthetic_evaluation(
        required=required, steps=steps, context=context, conflicts=conflicts
    )
    document = json.loads(
        public_json.planning_json_document(
            user, request, result, strategy_id="sintetica"
        )
    )
    trace = cast(dict[str, object], document["planning_result"])
    assert trace["status"] == status and trace["reason"] == reason
    assert (
        trace["plan"] is None if status != "plan_created" else trace["plan"] is not None
    )
    if status == "insufficient_context":
        assert trace["missing_context"] == [
            {
                "kind": "task",
                "key": "topic",
                "scope": {"kind": "global", "identifier": None},
            }
        ]
    if context:
        assert document["planning_request"]["context_snapshot_id"] == "snapshot-1"
        serialized = json.dumps(document)
        assert "private-context-value" not in serialized
        assert "private-evidence-reference" not in serialized


def test_objective_json_validation_preserves_conflict_precedence() -> None:
    _, request, result, manifest = synthetic_evaluation(
        required=True, steps=True, conflicts=True
    )
    cli._validated_objective_result(result, request, manifest)
    unknown_goal = replace(request.goal, objective="Objetivo no registrado")
    unknown_request = replace(request, goal=unknown_goal)
    unknown_result = DeterministicPlanner(
        manifest.rules, clock=lambda: NOW, result_id_factory=lambda: "result-2"
    ).plan(unknown_request)
    assert unknown_result.reason is PlanningReason.CONFLICTING_CONSTRAINTS
    cli._validated_objective_result(unknown_result, unknown_request, manifest)
    fabricated = replace(
        unknown_result,
        status=PlanningStatus.UNSATISFIABLE,
        reason=PlanningReason.NO_REGISTERED_STRATEGY,
        constraint_conflicts=(),
    )
    with pytest.raises(ValueError):
        cli._validated_objective_result(fabricated, unknown_request, manifest)


@pytest.mark.parametrize(
    "corruption",
    [
        "top_extra",
        "request_missing",
        "goal_extra",
        "scope_wrong",
        "provenance_extra",
        "constraint_wrong",
        "result_extra",
        "plan_extra",
        "step_extra",
        "step_wrong",
        "missing_extra",
        "nonfinite",
        "unsupported",
    ],
)
def test_public_json_rejects_serializer_shape_drift(
    monkeypatch: pytest.MonkeyPatch, corruption: str
) -> None:
    user, request, result, _ = synthetic_evaluation(
        required=True, steps=True, context=True, conflicts=False
    )
    request_data = request.to_data()
    result_data = result.to_trace()
    if corruption == "top_extra":
        request_data["secret"] = "x"
    elif corruption == "request_missing":
        del request_data["created_at"]
    elif corruption == "goal_extra":
        request_data["goal"]["private"] = "x"
    elif corruption == "scope_wrong":
        request_data["goal"]["scope"]["identifier"] = False
    elif corruption == "provenance_extra":
        request_data["goal"]["provenance"]["secret"] = "x"
    elif corruption == "constraint_wrong":
        request_data["goal"]["constraints"] = [{"kind": "require", "subject": "x"}]
    elif corruption == "result_extra":
        result_data["executed"] = False
    elif corruption == "plan_extra":
        result_data["plan"]["executed"] = False
    elif corruption == "step_extra":
        result_data["plan"]["steps"][0]["secret"] = "x"
    elif corruption == "step_wrong":
        result_data["plan"]["steps"][0]["depends_on"] = None
    elif corruption == "missing_extra":
        result_data["missing_context"] = [
            {
                "kind": "task",
                "key": "x",
                "scope": {"kind": "global", "identifier": None, "extra": 1},
            }
        ]
    elif corruption == "nonfinite":
        result_data["plan"]["steps"][0]["constraints"] = [
            {"kind": "require", "subject": "x", "value": float("nan")}
        ]
    else:
        result_data["plan"]["steps"][0]["constraints"] = [
            {"kind": "require", "subject": "x", "value": object()}
        ]
    monkeypatch.setattr(PlanningRequest, "to_data", lambda _self: request_data)
    monkeypatch.setattr(PlanningResult, "to_trace", lambda _self: result_data)
    with pytest.raises((TypeError, ValueError)):
        public_json.planning_json_document(
            user, request, result, strategy_id="sintetica"
        )


def test_serialization_failure_is_controlled_and_emits_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args: object, **_kwargs: object) -> str:
        raise RuntimeError("private serializer detail")

    monkeypatch.setattr(public_json.json, "dumps", fail)
    output: list[str] = []
    with pytest.raises(SystemExit) as error:
        cli.entrypoint(
            ["planificar", "--estrategia", "estudio", "--formato", "json"],
            output_fn=output.append,
        )
    assert output == []
    assert "private serializer detail" not in str(error.value)


def test_serialization_failure_subprocess_exits_one_without_stdout() -> None:
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    script = (
        "import iris.__main__ as cli; "
        "import iris.planning.public_json as p; "
        "defect = lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('private detail')); "
        "p.json.dumps = defect; "
        "cli.entrypoint(['planificar', '--estrategia', 'estudio', '--formato', 'json'])"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
        check=False,
    )
    assert completed.returncode == 1
    assert completed.stdout == ""
    assert "salida JSON inválida" in completed.stderr
    assert "private detail" not in completed.stderr


def test_request_metadata_is_not_serialized(monkeypatch: pytest.MonkeyPatch) -> None:
    original = cli.Request

    def with_secret(**kwargs: object) -> Request:
        metadata = dict(cast(dict[str, object], kwargs["metadata"]))
        metadata["private_marker"] = "hidden"
        kwargs["metadata"] = metadata
        return original(**kwargs)

    monkeypatch.setattr(cli, "Request", with_secret)
    _, serialized = run_json("--estrategia", "estudio")
    assert "private_marker" not in serialized and "hidden" not in serialized


def test_fixed_identifiers_and_time_yield_stable_json() -> None:
    _, first = run_json("--estrategia", "estudio", planner=RecordingPlanner())
    _, second = run_json("--estrategia", "estudio", planner=RecordingPlanner())
    assert first == second
    assert "2026-11-14T00:00:00+00:00" in first


def test_legacy_text_modes_and_forbidden_authorities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from iris.capabilities import CapabilityRuntime
    from iris.execution import ExecutionCoordinator
    from iris.memory import MemoryService
    from iris.plan_runs import PlanRunFactory

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Planning JSON reached an operational authority")

    monkeypatch.setattr(cli, "OllamaProvider", forbidden)
    monkeypatch.setattr(CapabilityRuntime, "execute", forbidden)
    monkeypatch.setattr(ExecutionCoordinator, "execute", forbidden)
    monkeypatch.setattr(PlanRunFactory, "create", forbidden)
    monkeypatch.setattr(MemoryService, "get", forbidden)
    monkeypatch.setattr(MemoryService, "query", forbidden)
    monkeypatch.setattr(MemoryService, "store", forbidden)
    for args, fragment in (
        (["--objetivo", STUDY_OBJECTIVE], "Plan conceptual propuesto"),
        (["--estrategia", "estudio"], "Estrategia seleccionada"),
        (["--listar"], "Estrategia: estudio"),
        (["--requisitos", "estudio"], "Requisitos de contexto: ninguno"),
    ):
        output: list[str] = []
        cli.entrypoint(["planificar", *args], output_fn=output.append)
        assert any(fragment in line for line in output)
    run_json("--estrategia", "estudio")
    run_json("--objetivo", STUDY_OBJECTIVE)


def test_module_and_installed_console_are_independent_json_consumers() -> None:
    executable = Path(sys.executable).with_name(
        "iris.exe" if os.name == "nt" else "iris"
    )
    assert executable.is_file()
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    for prefix in ([sys.executable, "-m", "iris"], [str(executable)]):
        for mode in (
            ["--estrategia", "estudio"],
            ["--objetivo", STUDY_OBJECTIVE],
            ["--objetivo", "Objetivo ajeno"],
        ):
            completed = subprocess.run(
                [*prefix, "planificar", *mode, "--formato", "json"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=environment,
                check=False,
            )
            assert completed.returncode == 0 and completed.stderr == ""
            document = json.loads(completed.stdout)
            result = document["planning_result"]
            assert result["status"] in {"plan_created", "unsatisfiable"}
            if result["plan"] is not None:
                steps = result["plan"]["steps"]
                assert len(steps) == 4
                assert [step["step_id"] for step in steps] == ["a", "b", "c", "d"]
                assert [step["depends_on"] for step in steps] == [
                    [],
                    ["a"],
                    ["b"],
                    ["c"],
                ]
