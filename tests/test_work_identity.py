"""WorkSubject and root-origin identity foundation tests."""

from __future__ import annotations

import ast
import builtins
import hashlib
import json
import socket
import subprocess
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from iris.core import Request
from iris.plan_runs import (
    AddBlockerUpdate,
    PlanBlocker,
    PlanObservation,
    PlanRun,
    PlanRunFactory,
    PlanRunIdentityError,
    PlanRunReducer,
    RecordObservationUpdate,
    RunProvenance,
    StepProgressState,
    StepProgressUpdate,
)
from iris.planning import Plan, PlanStep
from iris.work_identity import (
    PlanStepWorkReference,
    RequestWorkReference,
    UnknownPlanStepError,
    WorkOrigin,
    WorkReferenceMismatchError,
    WorkSubject,
    WorkSubjectKind,
    work_subject_from_plan_step,
    work_subject_from_request,
)

NOW = datetime(2026, 9, 27, 22, tzinfo=UTC)
RUN_PROVENANCE = RunProvenance("test", "test-work-identity", "tester")


def step(step_id: str, *, depends_on: tuple[str, ...] = ()) -> PlanStep:
    return PlanStep(
        step_id,
        f"Objective {step_id}",
        f"Expected {step_id}",
        depends_on,
    )


def plan(*steps: PlanStep, plan_id: str = "plan-1") -> Plan:
    return Plan(plan_id, "goal-1", (), steps)


def new_run(selected_plan: Plan, *, run_id: str = "run-1") -> PlanRun:
    return PlanRunFactory(
        clock=lambda: NOW,
        run_id_factory=lambda: run_id,
    ).create(selected_plan)


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


def observe(
    selected_plan: Plan,
    run: PlanRun,
    *,
    step_id: str | None = None,
    observation_id: str | None = None,
) -> tuple[PlanRun, str]:
    selected_id = observation_id or f"observation-{run.revision}"
    observation = PlanObservation(
        selected_id,
        run.run_id,
        "test",
        next_time(run),
        "work_identity_evidence",
        step_id,
        data={"identity_unchanged": True},
    )
    updated = PlanRunReducer().apply(
        selected_plan,
        run,
        RecordObservationUpdate(
            f"observe-{run.revision}-{selected_id}",
            run.run_id,
            run.revision,
            next_time(run),
            RUN_PROVENANCE,
            observation,
        ),
    )
    return updated, selected_id


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
    active = activate(selected_plan, run, step_id)
    observed, evidence_id = observe(
        selected_plan,
        active,
        step_id=step_id,
        observation_id=f"evidence-{step_id}",
    )
    return PlanRunReducer().apply(
        selected_plan,
        observed,
        StepProgressUpdate(
            f"finish-{observed.revision}-{step_id}",
            observed.run_id,
            observed.revision,
            next_time(observed),
            RUN_PROVENANCE,
            step_id,
            StepProgressState.SUCCEEDED,
            (evidence_id,),
        ),
    )


def nested_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            key for item in value.values() for key in nested_keys(item)
        }
    if isinstance(value, list):
        return {key for item in value for key in nested_keys(item)}
    return set()


def test_request_adapter_identifies_request_and_its_root_origin() -> None:
    request = Request("Show status", "cli", "request-1", {"channel": "local"})

    subject = work_subject_from_request(request)

    assert subject.kind is WorkSubjectKind.REQUEST
    assert subject.reference == RequestWorkReference("request-1")
    assert subject.origin == WorkOrigin("request", "request-1")
    assert subject.origin.source_id == request.request_id


def test_request_identity_ignores_content_source_and_metadata() -> None:
    first = Request("First content", "cli", "request-1", {"a": 1})
    second = Request("Reconstructed content", "api", "request-1", {"b": 2})

    first_subject = work_subject_from_request(first)
    second_subject = work_subject_from_request(second)

    assert first_subject == second_subject
    assert first_subject.subject_id == second_subject.subject_id


def test_different_request_identity_changes_subject_id() -> None:
    first = work_subject_from_request(Request("same", "cli", "request-1"))
    second = work_subject_from_request(Request("same", "cli", "request-2"))

    assert first.subject_id != second.subject_id


def test_plan_step_adapter_builds_typed_operational_reference() -> None:
    selected_plan = plan(step("step-3"), plan_id="plan-1")
    run = new_run(selected_plan, run_id="run-7")

    subject = work_subject_from_plan_step(selected_plan, run, "step-3")

    assert subject.kind is WorkSubjectKind.PLAN_STEP
    assert subject.reference == PlanStepWorkReference("plan-1", "run-7", "step-3")
    assert subject.origin is None


def test_same_plan_run_and_step_produce_same_subject() -> None:
    selected_plan = plan(step("a"))
    run = new_run(selected_plan)

    first = work_subject_from_plan_step(selected_plan, run, "a")
    second = work_subject_from_plan_step(selected_plan, run, "a")

    assert first == second
    assert first.subject_id == second.subject_id


def test_plan_step_identity_changes_with_plan_run_or_step() -> None:
    plan_a = plan(step("a"), step("b"), plan_id="plan-a")
    run_a = new_run(plan_a, run_id="run-a")
    run_b = new_run(plan_a, run_id="run-b")
    plan_b = plan(step("a"), plan_id="plan-b")
    plan_b_run = new_run(plan_b, run_id="run-a")

    identities = {
        work_subject_from_plan_step(plan_a, run_a, "a").subject_id,
        work_subject_from_plan_step(plan_a, run_a, "b").subject_id,
        work_subject_from_plan_step(plan_a, run_b, "a").subject_id,
        work_subject_from_plan_step(plan_b, plan_b_run, "a").subject_id,
    }

    assert len(identities) == 4


def test_plan_run_revision_is_not_part_of_subject_identity() -> None:
    selected_plan = plan(step("a"))
    initial = new_run(selected_plan)
    revised, _ = observe(selected_plan, initial)

    before = work_subject_from_plan_step(selected_plan, initial, "a")
    after = work_subject_from_plan_step(selected_plan, revised, "a")

    assert initial.revision != revised.revision
    assert before == after
    assert before.subject_id == after.subject_id


def test_origin_may_be_unknown_and_later_knowledge_does_not_change_identity() -> None:
    selected_plan = plan(step("a"))
    run = new_run(selected_plan)
    known_origin = WorkOrigin("request", "request-root")

    unknown = work_subject_from_plan_step(selected_plan, run, "a")
    known = work_subject_from_plan_step(selected_plan, run, "a", origin=known_origin)

    assert unknown.origin is None
    assert known.origin == known_origin
    assert unknown != known
    assert unknown.subject_id == known.subject_id


def test_origin_is_value_equality_and_accepts_descriptive_vocabulary() -> None:
    first = WorkOrigin("system_event", "event-17")
    second = WorkOrigin("system_event", "event-17")

    assert first == second
    assert first.to_data() == {
        "source_type": "system_event",
        "source_id": "event-17",
    }


@pytest.mark.parametrize(
    ("kind", "reference"),
    [
        (
            WorkSubjectKind.REQUEST,
            PlanStepWorkReference("plan-1", "run-1", "a"),
        ),
        (WorkSubjectKind.PLAN_STEP, RequestWorkReference("request-1")),
    ],
)
def test_kind_and_typed_reference_mismatch_is_rejected(
    kind: WorkSubjectKind,
    reference: RequestWorkReference | PlanStepWorkReference,
) -> None:
    with pytest.raises(WorkReferenceMismatchError):
        WorkSubject(kind, reference)


def test_invalid_subject_kind_or_reference_type_is_rejected() -> None:
    with pytest.raises(TypeError):
        WorkSubject(
            "request",  # type: ignore[arg-type]
            RequestWorkReference("request-1"),
        )
    with pytest.raises(WorkReferenceMismatchError):
        WorkSubject(WorkSubjectKind.REQUEST, object())  # type: ignore[arg-type]


def test_plan_step_adapter_delegates_invalid_plan_run_linkage_to_wp012() -> None:
    expected_plan = plan(step("a"), plan_id="plan-a")
    foreign_plan = plan(step("a"), plan_id="plan-b")
    foreign_run = new_run(foreign_plan)

    with pytest.raises(PlanRunIdentityError):
        work_subject_from_plan_step(expected_plan, foreign_run, "a")


def test_plan_step_adapter_rejects_unknown_step_with_wp012_error() -> None:
    selected_plan = plan(step("a"))
    run = new_run(selected_plan)

    with pytest.raises(UnknownPlanStepError):
        work_subject_from_plan_step(selected_plan, run, "unknown")


@pytest.mark.parametrize("state", ["ready", "waiting", "blocked", "active", "terminal"])
def test_plan_step_subject_exists_independently_of_availability(state: str) -> None:
    if state == "waiting":
        selected_plan = plan(step("a"), step("b", depends_on=("a",)))
        run = new_run(selected_plan)
        selected_id = "b"
    else:
        selected_plan = plan(step("a"))
        run = new_run(selected_plan)
        selected_id = "a"
        if state == "blocked":
            run = block(selected_plan, run, "a")
        elif state == "active":
            run = activate(selected_plan, run, "a")
        elif state == "terminal":
            run = finish(selected_plan, run, "a")

    subject = work_subject_from_plan_step(selected_plan, run, selected_id)

    assert subject.reference == PlanStepWorkReference(
        selected_plan.plan_id, run.run_id, selected_id
    )


def test_plan_step_adapter_requires_no_control_decision_and_does_not_mutate_run() -> (
    None
):
    selected_plan = plan(step("a"))
    run = new_run(selected_plan)
    plan_before = selected_plan.to_data()
    run_before = run.to_data()

    subject = work_subject_from_plan_step(selected_plan, run, "a")

    assert subject.kind is WorkSubjectKind.PLAN_STEP
    assert selected_plan.to_data() == plan_before
    assert run.to_data() == run_before


def test_models_are_frozen_slotted_and_have_no_mutable_metadata() -> None:
    origin = WorkOrigin("request", "request-1")
    request_reference = RequestWorkReference("request-1")
    step_reference = PlanStepWorkReference("plan-1", "run-1", "a")
    subject = WorkSubject(WorkSubjectKind.REQUEST, request_reference, origin)

    with pytest.raises(FrozenInstanceError):
        origin.source_id = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        request_reference.request_id = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        step_reference.step_id = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        subject.origin = None  # type: ignore[misc]
    assert not hasattr(origin, "__dict__")
    assert not hasattr(subject, "metadata")


@pytest.mark.parametrize(
    "constructor",
    [
        lambda: WorkOrigin("", "source-1"),
        lambda: WorkOrigin("SystemEvent", "source-1"),
        lambda: WorkOrigin("system-event", "source-1"),
        lambda: WorkOrigin("system_event", ""),
        lambda: WorkOrigin("system_event", " source-1"),
        lambda: RequestWorkReference(" "),
        lambda: PlanStepWorkReference("plan-1", "run-1 ", "a"),
    ],
)
def test_blank_whitespace_or_invalid_vocabulary_is_rejected(
    constructor: Any,
) -> None:
    with pytest.raises(ValueError):
        constructor()


def test_subject_id_is_derived_and_cannot_be_supplied_by_caller() -> None:
    reference = RequestWorkReference("request-1")

    with pytest.raises(TypeError):
        WorkSubject(  # type: ignore[call-arg]
            WorkSubjectKind.REQUEST,
            reference,
            None,
            subject_id="caller-controlled",
        )


def test_canonical_subject_id_matches_structured_sha256_encoding() -> None:
    subject = WorkSubject(
        WorkSubjectKind.PLAN_STEP,
        PlanStepWorkReference("plan-1", "run-1", "step-1"),
    )
    material = json.dumps(
        {
            "kind": "plan_step",
            "reference": {
                "plan_id": "plan-1",
                "run_id": "run-1",
                "step_id": "step-1",
            },
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    assert subject.subject_id == f"work_subject_{hashlib.sha256(material).hexdigest()}"


def test_structured_encoding_resists_simple_delimiter_ambiguity() -> None:
    first = WorkSubject(
        WorkSubjectKind.PLAN_STEP,
        PlanStepWorkReference("plan:a", "run", "step"),
    )
    second = WorkSubject(
        WorkSubjectKind.PLAN_STEP,
        PlanStepWorkReference("plan", "a:run", "step"),
    )

    assert first.subject_id != second.subject_id


def test_serialization_is_stable_with_and_without_origin() -> None:
    reference = PlanStepWorkReference("plan-1", "run-1", "a")
    unknown = WorkSubject(WorkSubjectKind.PLAN_STEP, reference)
    known = WorkSubject(
        WorkSubjectKind.PLAN_STEP,
        reference,
        WorkOrigin("request", "request-root"),
    )

    assert unknown.to_data() == unknown.to_data()
    assert unknown.to_data()["origin"] is None
    assert known.to_data()["origin"] == {
        "source_type": "request",
        "source_id": "request-root",
    }
    assert json.dumps(known.to_data(), sort_keys=True) == json.dumps(
        known.to_data(), sort_keys=True
    )


def test_subject_serialization_contains_identity_only() -> None:
    subject = WorkSubject(
        WorkSubjectKind.PLAN_STEP,
        PlanStepWorkReference("plan-1", "run-1", "a"),
        WorkOrigin("request", "request-root"),
    )
    keys = nested_keys(subject.to_data())

    assert keys.isdisjoint(
        {
            "revision",
            "status",
            "availability",
            "step_progress",
            "run_condition",
            "handling_need",
            "handling_kind",
            "capability_id",
            "memory_operation",
            "system_route",
            "intelligence_need",
            "permission",
            "approval",
            "trusted",
            "authorized",
            "risk_score",
            "content",
            "payload",
            "created_at",
            "updated_at",
        }
    )


def test_work_identity_has_no_forbidden_direct_dependencies() -> None:
    root = Path(__file__).parents[1] / "iris" / "work_identity"
    imported_modules: set[str] = set()
    for path in (root / "models.py", root / "adapters.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                imported_modules.add(node.module)
            elif isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)

    assert not any(
        module.startswith(
            (
                "iris.context",
                "iris.orchestrator",
                "iris.execution",
                "iris.plan_control",
                "iris.plan_handling",
            )
        )
        for module in imported_modules
    )


def test_public_api_exports_foundational_contracts() -> None:
    import iris.work_identity as public_api

    expected = {
        "WorkSubjectKind",
        "WorkOrigin",
        "RequestWorkReference",
        "PlanStepWorkReference",
        "WorkSubject",
        "work_subject_from_request",
        "work_subject_from_plan_step",
        "WorkIdentityError",
        "WorkSubjectInvariantError",
        "WorkReferenceMismatchError",
        "UnknownPlanStepError",
    }

    assert expected <= set(public_api.__all__)
    assert all(hasattr(public_api, name) for name in expected)


def test_adapters_perform_no_filesystem_network_or_subprocess_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = Request("Status", "cli", "request-1")
    selected_plan = plan(step("a"))
    run = new_run(selected_plan)

    def forbidden(*args: object, **kwargs: object) -> Any:
        raise AssertionError(f"forbidden side effect: {args!r} {kwargs!r}")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)

    request_subject = work_subject_from_request(request)
    step_subject = work_subject_from_plan_step(selected_plan, run, "a")

    assert request_subject.kind is WorkSubjectKind.REQUEST
    assert step_subject.kind is WorkSubjectKind.PLAN_STEP
