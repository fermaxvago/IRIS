"""WorkSubject-owned Context regression and boundary tests for WP016."""

from __future__ import annotations

import builtins
import json
import socket
import subprocess
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from iris.context import (
    ContextBudget,
    ContextCandidate,
    ContextConflict,
    ContextEngine,
    ContextEvidence,
    ContextOwnershipError,
    ContextSelectionPolicy,
    ContextSnapshot,
    ContextUncertainty,
    DeterministicContextSelection,
    EvidenceSource,
    Freshness,
    Relevance,
    RequestEvidenceSubjectMismatchError,
    ResolutionStatus,
    UncertaintyReason,
)
from iris.context.selection import ContextSelection
from iris.core import Request
from iris.memory import EpistemicStatus, MemoryScope, ScopeKind
from iris.orchestrator import (
    HandlerAvailability,
    OrchestrationInput,
    RequestContextMismatchError,
)
from iris.plan_runs import PlanRunFactory
from iris.planning import Plan, PlanStep
from iris.work_identity import (
    PlanStepWorkReference,
    RequestWorkReference,
    WorkOrigin,
    WorkSubject,
    WorkSubjectKind,
    work_subject_from_plan_step,
    work_subject_from_request,
)

NOW = datetime(2026, 9, 28, 2, tzinfo=UTC)
GLOBAL = MemoryScope(ScopeKind.GLOBAL)


def request_subject(request_id: str = "request-1") -> WorkSubject:
    return WorkSubject(
        WorkSubjectKind.REQUEST,
        RequestWorkReference(request_id),
        WorkOrigin("request", request_id),
    )


def plan_step_subject(origin: WorkOrigin | None = None) -> WorkSubject:
    return WorkSubject(
        WorkSubjectKind.PLAN_STEP,
        PlanStepWorkReference("plan-1", "run-1", "step-1"),
        origin,
    )


def context_candidate(
    candidate_id: str = "candidate-1",
    *,
    source: EvidenceSource = EvidenceSource.CALLER,
    reference: str = "caller-1",
    epistemic: EpistemicStatus = EpistemicStatus.UNKNOWN,
) -> ContextCandidate:
    return ContextCandidate(
        candidate_id,
        "task",
        "active_task",
        "wp016",
        ContextEvidence(source, reference, epistemic),
        GLOBAL,
        Relevance.HIGH,
        Freshness.CURRENT,
        NOW,
    )


def build_for(
    subject: WorkSubject,
    *candidates: ContextCandidate,
    policy: ContextSelectionPolicy | None = None,
    budget: int = 10,
):
    return ContextEngine(policy).build(
        subject=subject,
        candidates=candidates,
        budget=ContextBudget(budget),
        created_at=NOW,
    )


def test_request_subject_is_canonical_snapshot_owner_and_serializes_once() -> None:
    subject = request_subject()
    snapshot = build_for(subject, context_candidate())

    assert snapshot.subject == subject
    assert snapshot.subject_id == subject.subject_id
    assert snapshot.request_id == "request-1"
    assert snapshot.snapshot_id != snapshot.subject_id
    assert snapshot.status is ResolutionStatus.RESOLVED
    serialized = snapshot.to_data()
    assert serialized["subject"] == subject.to_data()
    assert "request_id" not in serialized
    assert json.dumps(serialized, sort_keys=True) == json.dumps(
        snapshot.to_data(), sort_keys=True
    )
    with pytest.raises(FrozenInstanceError):
        snapshot.subject = plan_step_subject()  # type: ignore[misc]


def test_plan_step_subject_owns_context_without_impersonating_root_request() -> None:
    subject = plan_step_subject(WorkOrigin("request", "request-1"))
    evidence = context_candidate(
        source=EvidenceSource.REQUEST,
        reference="request-1",
        epistemic=EpistemicStatus.INFERRED,
    )
    snapshot = build_for(subject, evidence)

    assert snapshot.subject is subject
    assert snapshot.request_id is None
    assert snapshot.items[0].evidence.epistemic is EpistemicStatus.INFERRED
    assert snapshot.to_data()["subject"] == subject.to_data()
    assert "request_id" not in snapshot.to_data()


@pytest.mark.parametrize(
    "subject",
    [
        request_subject("request-1"),
        plan_step_subject(WorkOrigin("request", "request-1")),
        plan_step_subject(),
        plan_step_subject(WorkOrigin("system_event", "event-1")),
    ],
)
def test_request_evidence_requires_the_structurally_known_request(
    subject: WorkSubject,
) -> None:
    incompatible = context_candidate(
        source=EvidenceSource.REQUEST,
        reference="request-2",
    )
    with pytest.raises(RequestEvidenceSubjectMismatchError):
        build_for(subject, incompatible)


def test_unknown_or_nonrequest_origin_rejects_request_evidence() -> None:
    request_evidence = context_candidate(
        source=EvidenceSource.REQUEST,
        reference="request-1",
    )
    for subject in (
        plan_step_subject(),
        plan_step_subject(WorkOrigin("system_event", "event-1")),
    ):
        with pytest.raises(RequestEvidenceSubjectMismatchError):
            build_for(subject, request_evidence)


def test_mismatch_is_rejected_even_with_valid_nonrequest_evidence() -> None:
    valid = context_candidate("valid")
    mismatched = context_candidate(
        "mismatched",
        source=EvidenceSource.REQUEST,
        reference="request-2",
    )
    with pytest.raises(RequestEvidenceSubjectMismatchError):
        build_for(request_subject(), valid, mismatched)


def test_legacy_request_build_adapts_to_the_same_canonical_semantics() -> None:
    item = context_candidate()
    legacy = ContextEngine().build(
        request_id="request-1",
        candidates=(item,),
        budget=ContextBudget(1),
        created_at=NOW,
    )
    canonical = build_for(request_subject(), item, budget=1)

    assert legacy.subject == canonical.subject == request_subject()
    assert legacy.items == canonical.items
    assert legacy.status == canonical.status
    assert legacy.uncertainties == canonical.uncertainties
    assert legacy.conflicts == canonical.conflicts
    assert legacy.budget_excluded_ids == canonical.budget_excluded_ids
    assert legacy.snapshot_id != canonical.snapshot_id


def test_exactly_one_valid_owner_input_is_required() -> None:
    engine = ContextEngine()
    kwargs = {"candidates": (), "budget": ContextBudget(0), "created_at": NOW}
    with pytest.raises(ContextOwnershipError, match="exactly one"):
        engine.build(**kwargs)
    with pytest.raises(ContextOwnershipError, match="mutually exclusive"):
        engine.build(subject=request_subject(), request_id="request-1", **kwargs)
    with pytest.raises(TypeError, match="WorkSubject"):
        engine.build(subject="request-1", **kwargs)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="nonblank"):
        engine.build(request_id=" ", **kwargs)


def test_selection_policy_remains_subject_agnostic() -> None:
    class RecordingPolicy:
        calls: list[tuple[tuple[ContextCandidate, ...], ContextBudget]] = []

        def select(
            self,
            candidates: tuple[ContextCandidate, ...],
            budget: ContextBudget,
        ) -> ContextSelection:
            self.calls.append((candidates, budget))
            return DeterministicContextSelection().select(candidates, budget)

    policy = RecordingPolicy()
    item = context_candidate()
    snapshot = build_for(plan_step_subject(), item, policy=policy)
    assert snapshot.items == (item.to_item(),)
    assert policy.calls == [((item,), ContextBudget(10))]


def test_origin_knowledge_changes_neither_subject_nor_context_owner_identity() -> None:
    unknown = plan_step_subject()
    known = plan_step_subject(WorkOrigin("request", "request-1"))
    first = build_for(unknown)
    second = build_for(known)

    assert unknown.subject_id == known.subject_id
    assert first.subject_id == second.subject_id
    assert first.snapshot_id != second.snapshot_id
    assert first.items == second.items == ()


def test_plan_step_context_neither_requires_nor_mutates_runtime_state() -> None:
    selected_plan = Plan(
        "plan-1",
        "goal-1",
        (),
        (PlanStep("step-1", "Do work", "Work exists"),),
    )
    run = PlanRunFactory(
        clock=lambda: NOW,
        run_id_factory=lambda: "run-1",
    ).create(selected_plan)
    before = run.to_data()
    subject = work_subject_from_plan_step(selected_plan, run, "step-1")

    snapshot = build_for(subject)

    assert snapshot.subject == subject
    assert run.to_data() == before
    assert run.revision == 0


def test_plan_step_context_does_not_enter_request_orchestration_path() -> None:
    root = Request("start", "test", request_id="request-1")
    snapshot = build_for(plan_step_subject(WorkOrigin("request", "request-1")))
    with pytest.raises(RequestContextMismatchError):
        OrchestrationInput(root, snapshot, (), HandlerAvailability())


def test_context_components_remain_subject_agnostic_and_evidence_focused() -> None:
    candidate = context_candidate()
    snapshot = build_for(plan_step_subject(), candidate)
    conflict = ContextConflict(
        "task",
        "active_task",
        GLOBAL,
        ("a", "b"),
        (
            ContextEvidence(EvidenceSource.CALLER, "a"),
            ContextEvidence(EvidenceSource.CALLER, "b"),
        ),
    )
    uncertainty = ContextUncertainty(
        "task", "missing_detail", GLOBAL, UncertaintyReason.MISSING
    )
    for value in (
        candidate,
        snapshot.items[0],
        conflict,
        uncertainty,
    ):
        assert not hasattr(value, "subject")
        assert not hasattr(value, "subject_id")
    serialized_keys = set(snapshot.to_data())
    assert not serialized_keys.intersection(
        {"authorization", "permission", "trust", "trace_id", "parent_snapshot_id"}
    )


def test_direct_snapshot_validates_request_evidence_in_conflicts() -> None:
    conflict = ContextConflict(
        "task",
        "active_task",
        GLOBAL,
        ("a", "b"),
        (
            ContextEvidence(EvidenceSource.REQUEST, "request-2"),
            ContextEvidence(EvidenceSource.CALLER, "caller-1"),
        ),
    )
    with pytest.raises(RequestEvidenceSubjectMismatchError):
        ContextSnapshot(
            "snapshot-1",
            request_subject("request-1"),
            NOW,
            ContextBudget(0),
            (),
            ResolutionStatus.CONFLICTED,
            conflicts=(conflict,),
        )


def test_request_factory_context_preserves_existing_request_path() -> None:
    request = Request("status", "test", request_id="request-1")
    subject = work_subject_from_request(request)
    evidence = context_candidate(
        source=EvidenceSource.REQUEST,
        reference=request.request_id,
        epistemic=EpistemicStatus.DIRECT,
    )
    snapshot = build_for(subject, evidence)
    orchestration_input = OrchestrationInput(
        request,
        snapshot,
        (),
        HandlerAvailability(),
    )
    assert orchestration_input.context.request_id == request.request_id


def test_context_build_has_no_filesystem_network_or_subprocess_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("external side effect attempted")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)

    snapshot = build_for(plan_step_subject(), context_candidate())
    assert snapshot.status is ResolutionStatus.RESOLVED
