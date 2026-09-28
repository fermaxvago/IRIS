"""WorkSubject ownership and compatibility boundaries for WP017."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta

import pytest

from iris.context import ContextBudget, ContextEngine
from iris.core import Request
from iris.execution import ExecutionRequest, SystemExecutionInput
from iris.orchestrator import (
    HandlerAvailability,
    HandlingKind,
    HandlingNeed,
    OrchestrationInput,
    OrchestrationReason,
    OrchestrationTarget,
    Orchestrator,
    StaleOrchestrationDecisionError,
    SubjectContextMismatchError,
    validate_orchestration_decision_current,
)
from iris.plan_runs import PlanRunFactory
from iris.planning import Plan, PlanStep
from iris.router import RouteTarget
from iris.work_identity import (
    WorkOrigin,
    work_subject_from_plan_step,
    work_subject_from_request,
)

NOW = datetime(2026, 9, 28, 16, tzinfo=UTC)


def plan_step_subject(*, origin: WorkOrigin | None = None):
    plan = Plan(
        "plan-1",
        "goal-1",
        (),
        (PlanStep("step-1", "Inspect state", "State is known"),),
    )
    run = PlanRunFactory(
        clock=lambda: NOW,
        run_id_factory=lambda: "run-1",
    ).create(plan)
    return work_subject_from_plan_step(plan, run, "step-1", origin=origin)


def snapshot(subject):
    return ContextEngine().build(
        subject=subject,
        candidates=(),
        budget=ContextBudget(0),
        created_at=NOW,
    )


def input_for(subject, context=None):
    need = HandlingNeed(
        "need-1",
        HandlingKind.SYSTEM,
        system_route=RouteTarget.SYSTEM_STATUS,
    )
    return OrchestrationInput(
        subject,
        snapshot(subject) if context is None else context,
        (need,),
        HandlerAvailability(system=True),
    )


def orchestrator(*, decision_id: str = "decision-1") -> Orchestrator:
    return Orchestrator(
        clock=lambda: NOW + timedelta(seconds=1),
        id_factory=lambda: decision_id,
    )


def test_plan_step_is_a_first_class_orchestration_subject() -> None:
    subject = plan_step_subject()
    decision = orchestrator().decide(input_for(subject))

    assert decision.subject_id == subject.subject_id
    assert decision.target is OrchestrationTarget.SYSTEM
    assert decision.reason is OrchestrationReason.DETERMINISTIC_SYSTEM_HANDLING
    assert decision.request_id is None
    assert decision.to_trace()["subject_id"] == subject.subject_id
    assert "request_id" not in decision.to_trace()


def test_origin_does_not_become_request_compatibility_identity() -> None:
    subject = plan_step_subject(origin=WorkOrigin("request", "request-1"))

    decision = orchestrator().decide(input_for(subject))

    assert decision.request_id is None


def test_subject_context_ownership_uses_subject_id_not_full_equality() -> None:
    unknown_origin = plan_step_subject()
    known_origin = plan_step_subject(origin=WorkOrigin("request", "request-1"))
    context = snapshot(unknown_origin)

    value = input_for(known_origin, context)

    assert unknown_origin != known_origin
    assert unknown_origin.subject_id == known_origin.subject_id
    assert value.subject is known_origin
    assert value.context is context


def test_origin_relationship_cannot_reconcile_different_subject_ownership() -> None:
    plan_subject = plan_step_subject(origin=WorkOrigin("request", "request-1"))
    request_subject = plan_step_subject(origin=WorkOrigin("request", "request-2"))
    other_context = snapshot(request_subject)

    # Distinct operational work must remain distinct even when both have origins.
    other_plan = Plan(
        "plan-2",
        "goal-1",
        (),
        (PlanStep("step-1", "Inspect state", "State is known"),),
    )
    other_run = PlanRunFactory(
        clock=lambda: NOW,
        run_id_factory=lambda: "run-2",
    ).create(other_plan)
    different_subject = work_subject_from_plan_step(
        other_plan,
        other_run,
        "step-1",
        origin=plan_subject.origin,
    )

    with pytest.raises(SubjectContextMismatchError):
        input_for(different_subject, other_context)


def test_currentness_accepts_changed_origin_knowledge_for_same_subject() -> None:
    unknown_origin = plan_step_subject()
    known_origin = plan_step_subject(origin=WorkOrigin("request", "request-1"))
    context = snapshot(unknown_origin)
    decision = orchestrator().decide(input_for(known_origin, context))

    validate_orchestration_decision_current(decision, unknown_origin, context)


def test_currentness_rejects_wrong_subject_and_exact_snapshot_change() -> None:
    subject = plan_step_subject()
    context = snapshot(subject)
    decision = orchestrator().decide(input_for(subject, context))
    different_subject = replace(
        subject,
        reference=replace(subject.reference, step_id="step-2"),
    )

    with pytest.raises(StaleOrchestrationDecisionError, match="WorkSubject"):
        validate_orchestration_decision_current(
            decision, different_subject, snapshot(different_subject)
        )
    with pytest.raises(StaleOrchestrationDecisionError, match="ContextSnapshot"):
        validate_orchestration_decision_current(decision, subject, snapshot(subject))


def test_currentness_rejects_subject_context_mismatch_before_decision_checks() -> None:
    subject = plan_step_subject()
    context = snapshot(subject)
    decision = orchestrator().decide(input_for(subject, context))
    other = replace(subject, reference=replace(subject.reference, step_id="step-2"))

    with pytest.raises(SubjectContextMismatchError):
        validate_orchestration_decision_current(decision, other, context)


def test_same_semantic_input_preserves_selection_not_decision_instance_identity() -> (
    None
):
    subject = plan_step_subject()
    value = input_for(subject)
    first = orchestrator(decision_id="decision-1").decide(value)
    second = orchestrator(decision_id="decision-2").decide(value)

    assert first.decision_id != second.decision_id
    assert (
        first.subject_id,
        first.context_snapshot_id,
        first.target,
        first.reason,
        first.need_ids,
        first.requirement,
        first.context_references,
    ) == (
        second.subject_id,
        second.context_snapshot_id,
        second.target,
        second.reason,
        second.need_ids,
        second.requirement,
        second.context_references,
    )


def test_plan_step_decision_cannot_enter_request_only_execution() -> None:
    subject = plan_step_subject()
    decision = orchestrator().decide(input_for(subject))

    with pytest.raises(ValueError, match="limited to REQUEST"):
        ExecutionRequest("execution-1", decision, decision.created_at)


def test_request_subject_retains_the_existing_request_execution_seam() -> None:
    request = Request("status", "test", request_id="request-1")
    subject = work_subject_from_request(request)
    decision = orchestrator().decide(input_for(subject))

    execution = ExecutionRequest(
        "execution-1",
        decision,
        decision.created_at,
        SystemExecutionInput(request),
    )

    assert decision.subject_id == subject.subject_id
    assert decision.request_id == request.request_id
    assert "request_id" not in decision.to_trace()
    assert execution.decision is decision


def test_plan_step_decision_rejects_root_request_compatibility_value() -> None:
    subject = plan_step_subject(origin=WorkOrigin("request", "request-1"))
    decision = orchestrator().decide(input_for(subject))

    with pytest.raises(ValueError, match="compatibility"):
        replace(decision, request_id="request-1")


def test_decision_subject_context_and_instance_identifiers_are_distinct() -> None:
    subject = plan_step_subject()
    decision = orchestrator().decide(input_for(subject))

    assert (
        len({decision.decision_id, decision.subject_id, decision.context_snapshot_id})
        == 3
    )
    with pytest.raises(ValueError, match="must be distinct"):
        replace(decision, context_snapshot_id=decision.subject_id)


def test_foundational_models_keep_identity_and_runtime_concerns_separate() -> None:
    subject = plan_step_subject()
    value = input_for(subject)
    decision = orchestrator().decide(value)

    assert not hasattr(value.needs[0], "subject_id")
    assert not hasattr(value.availability, "availability_id")
    assert not hasattr(value.availability, "lease")
    assert not hasattr(decision, "authorized")
    assert not hasattr(decision, "handler_lease")
    with pytest.raises(FrozenInstanceError):
        decision.subject_id = "different"  # type: ignore[misc]


def test_request_centric_reason_names_are_compatibility_aliases_only() -> None:
    assert (
        OrchestrationReason.DETERMINISTIC_SYSTEM_REQUEST
        is OrchestrationReason.DETERMINISTIC_SYSTEM_HANDLING
    )
    assert (
        OrchestrationReason.EXPLICIT_CAPABILITY_REQUEST
        is OrchestrationReason.EXPLICIT_CAPABILITY_HANDLING
    )
    assert "deterministic_system_request" not in {
        item.value for item in OrchestrationReason
    }
