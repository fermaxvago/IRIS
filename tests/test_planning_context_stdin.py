"""WP080: strict caller context input, canonical selection and privacy."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

import iris.__main__ as cli
from iris.context import (
    ContextBudget,
    ContextConflict,
    ContextEngine,
    ContextSnapshot,
    EvidenceSource,
    Freshness,
    Relevance,
    ResolutionStatus,
)
from iris.core.request import Request
from iris.memory import EpistemicStatus, MemoryScope, ScopeKind
from iris.planning import (
    DeterministicPlanner,
    PlanningContextRequirement,
    PlanningRequest,
    PlanningResult,
    PlanningRule,
    PlanStep,
)
from iris.planning.context_stdin import ContextInputError, read_context_input
from iris.planning.strategy_manifest import (
    StrategyDescriptor,
    StrategyManifest,
    built_in_manifest,
)

NOW = datetime(2026, 11, 14, 12, tzinfo=UTC)
A = PlanningContextRequirement("task", "topic", MemoryScope(ScopeKind.GLOBAL))
B = PlanningContextRequirement(
    "task", "materials", MemoryScope(ScopeKind.TASK, "task-1")
)
MARKER = "PRIVATE_CONTEXT_MARKER_93847"


def manifest(*, steps: bool = True) -> StrategyManifest:
    rule = PlanningRule(
        "Preparar tema sintético",
        steps=(PlanStep("a", "Delimitar el tema.", "Tema identificado."),)
        if steps
        else (),
        required_context=(A, B),
    )
    return StrategyManifest((StrategyDescriptor("sintetica", "Prueba", rule),))


def item(
    requirement: PlanningContextRequirement, value: object = MARKER
) -> dict[str, object]:
    return {**requirement.to_data(), "value": value}


def encoded(*items: dict[str, object]) -> bytes:
    return json.dumps(
        {"format_version": "1.0", "items": list(items)}, ensure_ascii=True
    ).encode()


class RecordingPlanner:
    def __init__(self, rules: tuple[PlanningRule, ...]) -> None:
        self.delegate = DeterministicPlanner(rules, clock=lambda: NOW)
        self.calls: list[PlanningRequest] = []

    def plan(self, request: PlanningRequest) -> PlanningResult:
        self.calls.append(request)
        return self.delegate.plan(request)


def run(
    source: bytes,
    *,
    chosen: StrategyManifest | None = None,
    planner: RecordingPlanner | None = None,
    engine: ContextEngine | None = None,
) -> tuple[dict[str, object], RecordingPlanner]:
    selected = chosen or manifest()
    recorder = planner or RecordingPlanner(selected.rules)
    output: list[str] = []
    ids = iter(("request-1", "goal-1", "planning-1", "candidate-1", "candidate-2"))
    cli.entrypoint(
        [
            "planificar",
            "--estrategia",
            "sintetica",
            "--contexto-stdin",
            "--formato",
            "json",
        ],
        output_fn=output.append,
        planning_manifest=selected,
        planning_planner=recorder,
        planning_clock=lambda: NOW,
        planning_id_factory=ids.__next__,
        planning_context_stream=io.BytesIO(source),
        planning_context_engine=engine,
    )
    assert len(output) == 1
    return cast(dict[str, object], json.loads(output[0])), recorder


def test_complete_context_preserves_identity_provenance_and_private_values() -> None:
    document, planner = run(encoded(item(A), item(B, True)))
    assert len(planner.calls) == 1
    request = planner.calls[0]
    snapshot = request.context
    assert snapshot is not None
    assert request.goal.objective == "Preparar tema sintético"
    assert (
        request.goal.scope.identifier
        == request.goal.provenance.source_id
        == "request-1"
    )
    assert request.goal.provenance.actor is None
    assert snapshot.request_id == "request-1"
    assert snapshot.subject.origin.source_id == "request-1"
    assert (
        snapshot.created_at
        <= request.created_at
        <= datetime.fromisoformat(document["planning_result"]["created_at"])
    )
    assert {entry.candidate_id for entry in snapshot.items} == {
        "candidate-1",
        "candidate-2",
    }
    assert [(entry.kind, entry.key, entry.scope) for entry in snapshot.items] == [
        (A.kind, A.key, A.scope),
        (B.kind, B.key, B.scope),
    ]
    assert [entry.value for entry in snapshot.items] == [MARKER, True]
    assert type(snapshot.items[1].value) is bool
    for entry in snapshot.items:
        assert entry.evidence.source is EvidenceSource.CALLER
        assert entry.evidence.reference == "request-1"
        assert entry.evidence.epistemic is EpistemicStatus.UNKNOWN
        assert entry.relevance is Relevance.REQUIRED
        assert entry.freshness is Freshness.UNKNOWN
        assert entry.observed_at is None
    assert document["planning_request"]["context_snapshot_id"] == snapshot.snapshot_id
    assert document["planning_result"]["status"] == "plan_created"
    assert MARKER not in json.dumps(document)
    assert set(document) == {
        "format_version",
        "input",
        "planning_request",
        "planning_result",
    }


def test_request_identity_and_literal_strategy_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[Request] = []
    original = cli.Request

    def record(**kwargs: object) -> Request:
        request = original(**kwargs)
        created.append(request)
        return request

    monkeypatch.setattr(cli, "Request", record)
    document, planner = run(encoded(item(A)))
    assert len(created) == len(planner.calls) == 1
    request = created[0]
    planning = planner.calls[0]
    assert request.source == "cli" and request.content == "sintetica"
    assert request.request_id == planning.goal.scope.identifier
    assert request.request_id == planning.goal.provenance.source_id
    assert dict(request.metadata) == {
        "input_mode": "strategy_id",
        "strategy_id": "sintetica",
    }
    assert (
        len({request.request_id, planning.goal.goal_id, planning.planning_request_id})
        == 3
    )
    assert document["input"] == {"mode": "strategy_id", "strategy_id": "sintetica"}


def test_partial_context_and_no_step_rule_preserve_planner_semantics() -> None:
    partial, planner = run(encoded(item(A)))
    assert len(planner.calls) == 1
    result = partial["planning_result"]
    assert result["status"] == "insufficient_context"
    assert result["reason"] == "missing_required_context"
    assert result["missing_context"] == [B.to_data()]
    complete, _ = run(encoded(item(A), item(B)), chosen=manifest(steps=False))
    assert complete["planning_result"]["status"] == "no_plan_required"
    assert complete["planning_result"]["plan"] is None


@pytest.mark.parametrize(
    "source",
    [
        b"",
        b"{",
        b"[]",
        b"{}{}",
        b"\xff",
        b'{"format_version":"1.0","format_version":"1.0","items":[]}',
        b'{"format_version":"1.0","items":[{"kind":"task","kind":"task"}]}',
        b'{"format_version":"1.0","items":[{"scope":{"kind":"global","kind":"global"}}]}',
        b'{"format_version":"1.0","items":[{"value":NaN}]}',
        b'{"format_version":"1.0","items":[{"value":Infinity}]}',
        b'{"format_version":"1.0","items":[{"value":1e999}]}',
        b'{"format_version":"1.0","items":[{"value":' + b"9" * 5000 + b"}]}",
        b"[" * 1100 + b"0" + b"]" * 1100,
        b'{"format_version":"1.0","items":[]}',
    ],
)
def test_malformed_documents_fail_before_planning(source: bytes) -> None:
    recorder = RecordingPlanner(manifest().rules)
    with pytest.raises((ContextInputError, ValueError)):
        read_context_input(io.BytesIO(source), manifest().entries[0])
    assert recorder.calls == []


@pytest.mark.parametrize(
    "value",
    [None, [], {}, "", "  ", "x" * 1025, 2**53, -(2**53), float("inf")],
)
def test_invalid_values_rejected(value: object) -> None:
    with pytest.raises(ContextInputError):
        read_context_input(io.BytesIO(encoded(item(A, value))), manifest().entries[0])


def test_value_boundaries_and_scalar_types() -> None:
    for value in ("x" * 1024, "  x  ", 2**53 - 1, -(2**53 - 1), 1.5, True, False):
        parsed = read_context_input(
            io.BytesIO(encoded(item(A, value))), manifest().entries[0]
        )
        assert parsed[0].value == value
        assert type(parsed[0].value) is type(value)
    with pytest.raises(ContextInputError):
        read_context_input(
            io.BytesIO(encoded(item(A, "\ud800"))), manifest().entries[0]
        )


def test_byte_limit_and_bounded_reads() -> None:
    source = encoded(item(A))
    assert len(source) < 32768
    assert read_context_input(
        io.BytesIO(source + b" " * (32768 - len(source))), manifest().entries[0]
    )

    class CountingStream(io.BytesIO):
        sizes: list[int]

        def __init__(self, content: bytes) -> None:
            super().__init__(content)
            self.sizes = []

        def read(self, size: int = -1) -> bytes:
            self.sizes.append(size)
            return super().read(size)

    stream = CountingStream(source + b" " * (32769 - len(source)) + b"extra")
    with pytest.raises(ContextInputError):
        read_context_input(stream, manifest().entries[0])
    assert sum(stream.sizes) <= 32769
    assert stream.tell() == 32769


@pytest.mark.parametrize(
    "tampering", ["unknown", "duplicate", "scope", "extra", "missing", "null_scope"]
)
def test_requirement_and_schema_mismatch(tampering: str) -> None:
    first = item(A)
    if tampering == "unknown":
        first["key"] = "other"
    elif tampering == "duplicate":
        with pytest.raises(ContextInputError):
            read_context_input(io.BytesIO(encoded(first, first)), manifest().entries[0])
        return
    elif tampering == "scope":
        first["scope"] = (
            B.scope.to_data()
            if hasattr(B.scope, "to_data")
            else {"kind": "task", "identifier": "task-1"}
        )
    elif tampering == "extra":
        first["extra"] = MARKER
    elif tampering == "missing":
        first.pop("kind")
    else:
        first["scope"]["identifier"] = "foreign"
    with pytest.raises(ContextInputError):
        read_context_input(io.BytesIO(encoded(first)), manifest().entries[0])


@pytest.mark.parametrize(
    "source",
    [
        encoded(item(A, MARKER), item(B, None)),
        encoded({**item(A), "extra": MARKER}),
        b'{"format_version":"2.0","items":[]}',
        b'{"format_version":true,"items":[]}',
        b'{"format_version":"1.0","items":[],"extra":"private"}',
        b'{"format_version":"1.0"}',
        b'{"format_version":"1.0","items":"not-an-array"}',
        encoded(*([item(A)] * 17)),
        encoded({**item(A), "scope": {"kind": "wrong", "identifier": None}}),
        encoded(
            {**item(A), "scope": {"kind": "global", "identifier": None, "extra": 1}}
        ),
    ],
)
def test_caller_error_has_exit_two_empty_stdout_and_no_value_leak(
    source: bytes, capsys: pytest.CaptureFixture[str]
) -> None:
    output: list[str] = []
    with pytest.raises(SystemExit) as error:
        cli.entrypoint(
            [
                "planificar",
                "--estrategia",
                "sintetica",
                "--contexto-stdin",
                "--formato",
                "json",
            ],
            planning_manifest=manifest(),
            planning_context_stream=io.BytesIO(source),
            output_fn=output.append,
        )
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == "" and output == []
    assert MARKER not in captured.err


@pytest.mark.parametrize(
    "args",
    [
        ("--estrategia", "estudio", "--contexto-stdin", "--formato", "json"),
        ("--estrategia", "missing", "--contexto-stdin", "--formato", "json"),
        ("--estrategia", "sintetica", "--contexto-stdin"),
        (
            "--objetivo",
            "Preparar una sesión de estudio",
            "--contexto-stdin",
            "--formato",
            "json",
        ),
        ("--listar", "--contexto-stdin", "--formato", "json"),
        ("--requisitos", "sintetica", "--contexto-stdin", "--formato", "json"),
        (
            "--estrategia",
            "sintetica",
            "--contexto-stdin",
            "--contexto-stdin",
            "--formato",
            "json",
        ),
    ],
)
def test_incompatible_cli_rejected_before_stdin(
    args: tuple[str, ...], capsys: pytest.CaptureFixture[str]
) -> None:
    class ForbiddenStream(io.BytesIO):
        def read(self, size: int = -1) -> bytes:
            pytest.fail("stdin consumed before CLI validation")

    with pytest.raises(SystemExit) as error:
        cli.entrypoint(
            ["planificar", *args],
            planning_manifest=manifest()
            if "sintetica" in args
            else built_in_manifest(),
            planning_context_stream=ForbiddenStream(),
        )
    assert error.value.code == 2
    assert capsys.readouterr().out == ""


def test_legacy_strategy_json_does_not_read_stdin() -> None:
    class ForbiddenStream(io.BytesIO):
        def read(self, size: int = -1) -> bytes:
            pytest.fail("legacy Planning read context stdin")

    output: list[str] = []
    cli.entrypoint(
        ["planificar", "--estrategia", "estudio", "--formato", "json"],
        planning_context_stream=ForbiddenStream(),
        output_fn=output.append,
    )
    assert len(output) == 1
    assert json.loads(output[0])["planning_result"]["status"] == "plan_created"


def test_invalid_nested_manifest_rejected_before_stdin() -> None:
    chosen = deepcopy(manifest())
    object.__setattr__(chosen.entries[0].rule.required_context[0], "key", "BAD")

    class ForbiddenStream(io.BytesIO):
        def read(self, size: int = -1) -> bytes:
            pytest.fail("invalid manifest consumed stdin")

    with pytest.raises(SystemExit) as error:
        cli.entrypoint(
            [
                "planificar",
                "--estrategia",
                "sintetica",
                "--contexto-stdin",
                "--formato",
                "json",
            ],
            planning_manifest=chosen,
            planning_context_stream=ForbiddenStream(),
        )
    assert error.value.code != 2


@pytest.mark.parametrize(
    "fault",
    [
        "drop",
        "change",
        "change_type",
        "evidence",
        "exclude",
        "foreign",
        "origin",
        "budget",
        "conflict",
        "extra",
    ],
)
def test_context_engine_mismatch_is_internal_failure(fault: str) -> None:
    class FaultyEngine(ContextEngine):
        def build(self, **kwargs: object) -> ContextSnapshot:
            valid = super().build(**kwargs)
            if fault == "drop":
                return replace(valid, items=())
            if fault == "change":
                return replace(valid, items=(replace(valid.items[0], value="changed"),))
            if fault == "change_type":
                return replace(valid, items=(replace(valid.items[0], value=1),))
            if fault == "evidence":
                changed = replace(valid.items[0].evidence, reference="other")
                return replace(
                    valid, items=(replace(valid.items[0], evidence=changed),)
                )
            if fault == "exclude":
                return replace(
                    valid, budget_excluded_ids=(valid.items[0].candidate_id,)
                )
            if fault == "origin":
                changed = replace(valid.subject, origin=None)
                return replace(valid, subject=changed)
            if fault == "budget":
                return replace(valid, budget=type(valid.budget)(0))
            if fault == "conflict":
                conflict = ContextConflict(
                    "task",
                    "other",
                    A.scope,
                    ("foreign-1", "foreign-2"),
                    (valid.items[0].evidence, valid.items[0].evidence),
                )
                return replace(
                    valid, status=ResolutionStatus.CONFLICTED, conflicts=(conflict,)
                )
            if fault == "extra":
                added = replace(valid.items[0], candidate_id="invented", key="other")
                return replace(
                    valid, budget=ContextBudget(2), items=(*valid.items, added)
                )
            return replace(
                valid,
                subject=ContextEngine()
                .build(request_id="foreign", candidates=(), budget=valid.budget)
                .subject,
            )

    output: list[str] = []
    planner = RecordingPlanner(manifest().rules)
    with pytest.raises(SystemExit) as error:
        cli.entrypoint(
            [
                "planificar",
                "--estrategia",
                "sintetica",
                "--contexto-stdin",
                "--formato",
                "json",
            ],
            planning_manifest=manifest(),
            planning_context_stream=io.BytesIO(encoded(item(A))),
            planning_context_engine=FaultyEngine(),
            planning_planner=planner,
            output_fn=output.append,
        )
    assert error.value.code != 2
    assert output == [] and planner.calls == []
    assert MARKER not in str(error.value)


def test_scalar_type_change_that_compares_equal_is_rejected() -> None:
    class TypeChangingEngine(ContextEngine):
        def build(self, **kwargs: object) -> ContextSnapshot:
            valid = super().build(**kwargs)
            changed = replace(valid.items[0], value=1)
            return replace(valid, items=(changed,))

    output: list[str] = []
    with pytest.raises(SystemExit):
        cli.entrypoint(
            [
                "planificar",
                "--estrategia",
                "sintetica",
                "--contexto-stdin",
                "--formato",
                "json",
            ],
            planning_manifest=manifest(),
            planning_context_stream=io.BytesIO(encoded(item(A, True))),
            planning_context_engine=TypeChangingEngine(),
            output_fn=output.append,
        )
    assert output == []


@pytest.mark.parametrize("mutation", ["value", "scope", "evidence"])
def test_engine_mutation_of_input_candidate_is_rejected(mutation: str) -> None:
    class MutatingEngine(ContextEngine):
        def build(self, **kwargs: object) -> ContextSnapshot:
            candidate = kwargs["candidates"][0]
            if mutation == "value":
                object.__setattr__(candidate, "value", "changed")
            elif mutation == "scope":
                object.__setattr__(candidate.scope, "identifier", "other-task")
            else:
                object.__setattr__(candidate.evidence, "reference", "other-request")
            return super().build(**kwargs)

    output: list[str] = []
    with pytest.raises(SystemExit):
        cli.entrypoint(
            [
                "planificar",
                "--estrategia",
                "sintetica",
                "--contexto-stdin",
                "--formato",
                "json",
            ],
            planning_manifest=manifest(),
            planning_context_stream=io.BytesIO(encoded(item(B))),
            planning_context_engine=MutatingEngine(),
            output_fn=output.append,
        )
    assert output == []


def test_decreasing_utc_clock_fails_before_planning() -> None:
    instants = iter((NOW, NOW.replace(year=2025)))
    output: list[str] = []
    recorder = RecordingPlanner(manifest().rules)
    with pytest.raises(SystemExit):
        cli.entrypoint(
            [
                "planificar",
                "--estrategia",
                "sintetica",
                "--contexto-stdin",
                "--formato",
                "json",
            ],
            planning_manifest=manifest(),
            planning_context_stream=io.BytesIO(encoded(item(A))),
            planning_clock=instants.__next__,
            planning_planner=recorder,
            output_fn=output.append,
        )
    assert output == [] and recorder.calls == []


@pytest.mark.parametrize("fault", ["engine", "planner", "serializer"])
def test_internal_failures_are_private_and_emit_no_partial_json(
    fault: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BrokenEngine(ContextEngine):
        def build(self, **_kwargs: object) -> ContextSnapshot:
            raise RuntimeError(MARKER)

    class BrokenPlanner:
        def plan(self, _request: PlanningRequest) -> PlanningResult:
            raise RuntimeError(MARKER)

    if fault == "serializer":
        monkeypatch.setattr(
            cli,
            "planning_json_document",
            lambda *_, **__: (_ for _ in ()).throw(ValueError(MARKER)),
        )
    output: list[str] = []
    with pytest.raises(SystemExit) as error:
        cli.entrypoint(
            [
                "planificar",
                "--estrategia",
                "sintetica",
                "--contexto-stdin",
                "--formato",
                "json",
            ],
            planning_manifest=manifest(),
            planning_context_stream=io.BytesIO(encoded(item(A))),
            planning_context_engine=BrokenEngine() if fault == "engine" else None,
            planning_planner=BrokenPlanner() if fault == "planner" else None,
            output_fn=output.append,
        )
    assert error.value.code != 2
    assert output == [] and MARKER not in str(error.value)


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
def test_real_entrypoints_reject_production_no_requirement_strategy(
    prefix: list[str],
) -> None:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        [
            *prefix,
            "planificar",
            "--estrategia",
            "estudio",
            "--contexto-stdin",
            "--formato",
            "json",
        ],
        input=MARKER,
        text=True,
        capture_output=True,
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        check=False,
    )
    assert completed.returncode == 2
    assert completed.stdout == "" and MARKER not in completed.stderr


def test_no_runtime_authority_is_invoked(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("forbidden operational authority invoked")

    monkeypatch.setattr(cli, "OllamaProvider", forbidden)
    monkeypatch.setattr(cli, "CapabilityRuntime", forbidden)
    monkeypatch.setattr(cli, "ConversationalSystemAwareness", forbidden)
    document, _ = run(encoded(item(A)))
    assert document["planning_result"]["status"] == "insufficient_context"
