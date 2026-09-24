"""Single-step orchestration decisions without subsystem execution."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from typing import cast

import pytest

from iris.capabilities.runtime import CapabilityRuntime
from iris.context import (
    ContextBudget,
    ContextCandidate,
    ContextEngine,
    ContextEvidence,
    ContextKind,
    ContextUncertainty,
    EvidenceSource,
    Freshness,
    Relevance,
    ResolutionStatus,
    UncertaintyReason,
)
from iris.core import Request
from iris.intelligence import IntelligenceRuntime
from iris.intelligence.routing import IntelligenceNeed, IntelligenceRouter
from iris.memory import EpistemicStatus, MemoryScope, MemoryService, ScopeKind
from iris.orchestrator import (
    ContextBlocker,
    ContextBlockerKind,
    DeterministicOrchestrationPolicy,
    HandlerAvailability,
    HandlingKind,
    HandlingNeed,
    MemoryOperation,
    OrchestrationInput,
    OrchestrationPolicy,
    OrchestrationPolicyContractError,
    OrchestrationReason,
    OrchestrationTarget,
    Orchestrator,
    RequestContextMismatchError,
)
from iris.orchestrator.models import OrchestrationSelection
from iris.router import DeterministicRouter, RouteTarget

NOW = datetime(2026, 9, 24, 18, tzinfo=UTC)
GLOBAL = MemoryScope(ScopeKind.GLOBAL)


def candidate(
    candidate_id: str,
    value: str,
    *,
    kind: str = ContextKind.TASK,
    key: str = "active_task",
) -> ContextCandidate:
    return ContextCandidate(
        candidate_id=candidate_id,
        kind=kind,
        key=key,
        value=value,
        evidence=ContextEvidence(
            EvidenceSource.CALLER, candidate_id, EpistemicStatus.DIRECT
        ),
        scope=GLOBAL,
        relevance=Relevance.HIGH,
        freshness=Freshness.CURRENT,
    )


def snapshot(
    request: Request,
    *candidates: ContextCandidate,
    uncertainties: tuple[ContextUncertainty, ...] = (),
):
    return ContextEngine().build(
        request_id=request.request_id,
        candidates=candidates,
        budget=ContextBudget(10),
        uncertainties=uncertainties,
        created_at=NOW,
    )


def fixed_orchestrator(
    policy: OrchestrationPolicy | None = None,
) -> Orchestrator:
    return Orchestrator(
        policy,
        clock=lambda: NOW + timedelta(seconds=1),
        id_factory=lambda: "decision-1",
    )


def decide(
    need: HandlingNeed,
    *,
    availability: HandlerAvailability,
    context=None,
):
    request = Request("input", "test", request_id="request-1")
    current = snapshot(request) if context is None else context
    return fixed_orchestrator().decide(
        OrchestrationInput(request, current, (need,), availability)
    )


def system_need(need_id: str = "system") -> HandlingNeed:
    return HandlingNeed(
        need_id, HandlingKind.SYSTEM, system_route=RouteTarget.SYSTEM_STATUS
    )


def memory_need(need_id: str = "memory") -> HandlingNeed:
    return HandlingNeed(
        need_id, HandlingKind.MEMORY, memory_operation=MemoryOperation.RECALL
    )


def capability_need(need_id: str = "capability") -> HandlingNeed:
    return HandlingNeed(
        need_id, HandlingKind.CAPABILITY, capability_id="desktop.open_spotify"
    )


def intelligence_need(need_id: str = "intelligence") -> HandlingNeed:
    return HandlingNeed(
        need_id,
        HandlingKind.INTELLIGENCE,
        intelligence_need=IntelligenceNeed(),
    )


ALL_AVAILABLE = HandlerAvailability(
    system=True,
    memory=True,
    capability=True,
    intelligence=True,
    capability_ids=frozenset({"desktop.open_spotify"}),
)


def test_models_are_immutable_typed_and_decision_is_traceable() -> None:
    request = Request("estado", "cli", request_id="request-1")
    context = snapshot(request)
    route = DeterministicRouter().route(request)
    need = HandlingNeed("status", HandlingKind.SYSTEM, system_route=route.target)
    decision = fixed_orchestrator().decide(
        OrchestrationInput(request, context, (need,), ALL_AVAILABLE)
    )
    assert route.target is RouteTarget.SYSTEM_STATUS
    assert decision.decision_id == "decision-1"
    assert decision.request_id == request.request_id
    assert decision.context_snapshot_id == context.snapshot_id
    assert decision.target is OrchestrationTarget.SYSTEM
    assert decision.reason is OrchestrationReason.DETERMINISTIC_SYSTEM_REQUEST
    assert decision.requirement == need
    assert decision.created_at == NOW + timedelta(seconds=1)
    trace = decision.to_trace()
    assert json.loads(json.dumps(trace))["target"] == "system"
    assert "reasoning" not in trace
    with pytest.raises(FrozenInstanceError):
        decision.target = OrchestrationTarget.MEMORY  # type: ignore[misc]
    with pytest.raises(ValueError, match="incompatible"):
        replace(decision, reason=OrchestrationReason.INTELLIGENCE_REQUIRED)


def test_time_is_utc_normalized_and_invalid_time_is_rejected() -> None:
    request = Request("estado", "cli", request_id="request-1")
    context = snapshot(request)
    offset = timezone(timedelta(hours=-6))
    local_time = (NOW + timedelta(seconds=1)).astimezone(offset)
    decision = Orchestrator(
        clock=lambda: local_time, id_factory=lambda: "decision-1"
    ).decide(OrchestrationInput(request, context, (system_need(),), ALL_AVAILABLE))
    assert decision.created_at == NOW + timedelta(seconds=1)
    with pytest.raises(ValueError, match="timezone-aware"):
        Orchestrator(
            clock=lambda: datetime(2026, 9, 24), id_factory=lambda: "decision-1"
        ).decide(OrchestrationInput(request, context, (system_need(),), ALL_AVAILABLE))
    with pytest.raises(ValueError, match="predate"):
        Orchestrator(
            clock=lambda: NOW - timedelta(seconds=1),
            id_factory=lambda: "decision-1",
        ).decide(OrchestrationInput(request, context, (system_need(),), ALL_AVAILABLE))


def test_request_and_context_must_match() -> None:
    first = Request("one", "test", request_id="one")
    second = Request("two", "test", request_id="two")
    with pytest.raises(RequestContextMismatchError):
        OrchestrationInput(first, snapshot(second), (), HandlerAvailability())


def test_malformed_need_and_availability_are_rejected() -> None:
    with pytest.raises(ValueError, match="lowercase"):
        ContextBlocker(
            ContextKind.TASK,
            "Bad Key",
            GLOBAL,
            ContextBlockerKind.MISSING,
        )
    with pytest.raises(TypeError, match="HandlingKind"):
        HandlingNeed("need", "system", system_route=RouteTarget.SYSTEM_STATUS)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="requires system_route"):
        HandlingNeed("need", HandlingKind.SYSTEM)
    with pytest.raises(ValueError, match="another subsystem"):
        HandlingNeed(
            "need",
            HandlingKind.MEMORY,
            memory_operation=MemoryOperation.RECALL,
            capability_id="system.status",
        )
    with pytest.raises(ValueError, match="unknown deterministic"):
        HandlingNeed("need", HandlingKind.SYSTEM, system_route=RouteTarget.UNKNOWN)
    with pytest.raises(TypeError, match="bool"):
        HandlerAvailability(system=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="availability"):
        HandlerAvailability(capability_ids=frozenset({"system.status"}))


@pytest.mark.parametrize(
    ("need", "availability", "target", "reason"),
    [
        (
            system_need(),
            HandlerAvailability(system=True),
            OrchestrationTarget.SYSTEM,
            OrchestrationReason.DETERMINISTIC_SYSTEM_REQUEST,
        ),
        (
            memory_need(),
            HandlerAvailability(memory=True),
            OrchestrationTarget.MEMORY,
            OrchestrationReason.EXPLICIT_MEMORY_OPERATION,
        ),
        (
            capability_need(),
            HandlerAvailability(
                capability=True,
                capability_ids=frozenset({"desktop.open_spotify"}),
            ),
            OrchestrationTarget.CAPABILITY,
            OrchestrationReason.EXPLICIT_CAPABILITY_REQUEST,
        ),
        (
            intelligence_need(),
            HandlerAvailability(intelligence=True),
            OrchestrationTarget.INTELLIGENCE,
            OrchestrationReason.INTELLIGENCE_REQUIRED,
        ),
    ],
)
def test_explicit_needs_select_their_available_handler(
    need: HandlingNeed,
    availability: HandlerAvailability,
    target: OrchestrationTarget,
    reason: OrchestrationReason,
) -> None:
    decision = decide(need, availability=availability)
    assert (decision.target, decision.reason) == (target, reason)
    assert decision.requirement == need


def test_intelligence_requirement_is_preserved_without_model_selection() -> None:
    need = intelligence_need()
    decision = decide(need, availability=HandlerAvailability(intelligence=True))
    assert decision.requirement is need
    assert decision.requirement.intelligence_need is need.intelligence_need
    assert not hasattr(decision, "provider_id")
    assert not hasattr(decision, "model_id")


@pytest.mark.parametrize(
    "need",
    [system_need(), memory_need(), capability_need(), intelligence_need()],
)
def test_unavailable_required_handler_is_unsatisfied(need: HandlingNeed) -> None:
    decision = decide(need, availability=HandlerAvailability())
    assert decision.target is OrchestrationTarget.UNSATISFIED
    assert decision.reason is OrchestrationReason.NO_ADMISSIBLE_HANDLER
    assert decision.requirement == need


def test_unknown_specific_capability_is_unsatisfied() -> None:
    decision = decide(
        capability_need(),
        availability=HandlerAvailability(
            capability=True, capability_ids=frozenset({"system.status"})
        ),
    )
    assert decision.target is OrchestrationTarget.UNSATISFIED
    assert decision.reason is OrchestrationReason.NO_ADMISSIBLE_HANDLER


def test_generic_capability_need_uses_explicit_layer_availability() -> None:
    generic = HandlingNeed("capability", HandlingKind.CAPABILITY)
    available = decide(generic, availability=HandlerAvailability(capability=True))
    unavailable = decide(generic, availability=HandlerAvailability())
    assert available.target is OrchestrationTarget.CAPABILITY
    assert available.requirement.capability_id is None
    assert unavailable.target is OrchestrationTarget.UNSATISFIED


def test_availability_alone_does_not_create_a_need() -> None:
    request = Request("unknown", "test", request_id="request-1")
    decision = fixed_orchestrator().decide(
        OrchestrationInput(request, snapshot(request), (), ALL_AVAILABLE)
    )
    assert decision.target is OrchestrationTarget.UNSATISFIED
    assert decision.reason is OrchestrationReason.NO_ADMISSIBLE_HANDLER
    assert decision.need_ids == ()


def blocking_context(issue: ContextBlockerKind):
    request = Request("continue", "test", request_id="request-1")
    first = candidate("one", "wp009", key="option_one")
    second = candidate("two", "physics", key="option_two")
    if issue is ContextBlockerKind.CONFLICTED:
        first = replace(first, key="active_task")
        second = replace(second, key="active_task")
        context = snapshot(request, first, second)
        blocker = ContextBlocker(
            ContextKind.TASK,
            "active_task",
            GLOBAL,
            issue,
            context.conflicts[0].candidate_ids,
        )
    else:
        reason = (
            UncertaintyReason.MULTIPLE_PLAUSIBLE
            if issue is ContextBlockerKind.AMBIGUOUS
            else UncertaintyReason.MISSING
        )
        ids = ("one", "two") if issue is ContextBlockerKind.AMBIGUOUS else ()
        uncertainty = ContextUncertainty(
            ContextKind.TASK, "active_task", GLOBAL, reason, ids
        )
        context = snapshot(request, first, second, uncertainties=(uncertainty,))
        blocker = ContextBlocker(ContextKind.TASK, "active_task", GLOBAL, issue, ids)
    return request, context, blocker


@pytest.mark.parametrize(
    ("issue", "expected_reason"),
    [
        (ContextBlockerKind.MISSING, OrchestrationReason.MISSING_REQUIRED_INFORMATION),
        (ContextBlockerKind.AMBIGUOUS, OrchestrationReason.CONTEXT_AMBIGUOUS),
        (ContextBlockerKind.CONFLICTED, OrchestrationReason.CONTEXT_CONFLICTED),
    ],
)
def test_explicit_relevant_context_issue_produces_clarification(
    issue: ContextBlockerKind, expected_reason: OrchestrationReason
) -> None:
    request, context, blocker = blocking_context(issue)
    need = replace(intelligence_need(), blockers=(blocker,))
    decision = fixed_orchestrator().decide(
        OrchestrationInput(
            request,
            context,
            (need,),
            HandlerAvailability(intelligence=True),
        )
    )
    assert decision.target is OrchestrationTarget.CLARIFY
    assert decision.reason is expected_reason
    assert decision.context_references == (blocker,)


@pytest.mark.parametrize(
    "issue",
    [
        ContextBlockerKind.MISSING,
        ContextBlockerKind.AMBIGUOUS,
        ContextBlockerKind.CONFLICTED,
    ],
)
def test_unrelated_context_issue_does_not_block_handling(
    issue: ContextBlockerKind,
) -> None:
    request, context, _ = blocking_context(issue)
    assert context.status in {
        ResolutionStatus.PARTIAL,
        ResolutionStatus.AMBIGUOUS,
        ResolutionStatus.CONFLICTED,
    }
    decision = fixed_orchestrator().decide(
        OrchestrationInput(
            request,
            context,
            (intelligence_need(),),
            HandlerAvailability(intelligence=True),
        )
    )
    assert decision.target is OrchestrationTarget.INTELLIGENCE


def test_blocker_must_reference_an_issue_in_the_snapshot() -> None:
    request = Request("continue", "test", request_id="request-1")
    blocker = ContextBlocker(
        ContextKind.TASK, "active_task", GLOBAL, ContextBlockerKind.MISSING
    )
    with pytest.raises(ValueError, match="does not exist"):
        OrchestrationInput(
            request,
            snapshot(request),
            (replace(intelligence_need(), blockers=(blocker,)),),
            HandlerAvailability(intelligence=True),
        )


def test_blocker_candidate_order_is_normalized() -> None:
    request, context, blocker = blocking_context(ContextBlockerKind.AMBIGUOUS)
    reversed_blocker = replace(
        blocker, candidate_ids=tuple(reversed(blocker.candidate_ids))
    )
    need = replace(intelligence_need(), blockers=(reversed_blocker,))
    decision = fixed_orchestrator().decide(
        OrchestrationInput(
            request,
            context,
            (need,),
            HandlerAvailability(intelligence=True),
        )
    )
    assert decision.context_references[0].candidate_ids == ("one", "two")


def test_multiple_needs_are_composite_and_input_order_independent() -> None:
    request = Request("find and remember", "test", request_id="request-1")
    context = snapshot(request)
    capability = capability_need("a-capability")
    memory = memory_need("b-memory")
    first = fixed_orchestrator().decide(
        OrchestrationInput(request, context, (memory, capability), ALL_AVAILABLE)
    )
    second = fixed_orchestrator().decide(
        OrchestrationInput(request, context, (capability, memory), ALL_AVAILABLE)
    )
    assert first == second
    assert first.target is OrchestrationTarget.UNSATISFIED
    assert first.reason is OrchestrationReason.COMPOSITE_HANDLING_REQUIRED
    assert first.need_ids == ("a-capability", "b-memory")
    assert first.requirement is None


def test_same_input_produces_same_semantic_decision() -> None:
    request = Request("explain", "test", request_id="request-1")
    context = snapshot(request)
    need = intelligence_need()
    input_value = OrchestrationInput(
        request,
        context,
        (need,),
        HandlerAvailability(intelligence=True),
    )
    first = fixed_orchestrator().decide(input_value)
    second = fixed_orchestrator().decide(input_value)
    assert first == second


def test_offline_and_person_presence_are_context_not_routing_or_authority() -> None:
    request = Request("open Spotify", "test", request_id="request-1")
    context = snapshot(
        request,
        candidate("offline", "offline", kind=ContextKind.RESOURCE, key="connectivity"),
        candidate(
            "person", "nadia", kind=ContextKind.ENVIRONMENT, key="person_present"
        ),
    )
    decision = fixed_orchestrator().decide(
        OrchestrationInput(
            request,
            context,
            (capability_need(),),
            HandlerAvailability(
                capability=True,
                capability_ids=frozenset({"desktop.open_spotify"}),
            ),
        )
    )
    assert decision.target is OrchestrationTarget.CAPABILITY
    assert not hasattr(decision, "authorized")


def test_local_intelligence_can_be_selected_while_offline_without_routing_model() -> (
    None
):
    request = Request("explain", "test", request_id="request-1")
    context = snapshot(
        request,
        candidate("offline", "offline", kind=ContextKind.RESOURCE, key="connectivity"),
    )
    decision = fixed_orchestrator().decide(
        OrchestrationInput(
            request,
            context,
            (intelligence_need(),),
            HandlerAvailability(intelligence=True),
        )
    )
    assert decision.target is OrchestrationTarget.INTELLIGENCE
    assert not hasattr(decision, "selected_resource")


def test_decision_does_not_execute_any_coordinated_subsystem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("orchestration crossed an execution boundary")

    monkeypatch.setattr(CapabilityRuntime, "execute", forbidden)
    monkeypatch.setattr(IntelligenceRuntime, "execute", forbidden)
    monkeypatch.setattr(IntelligenceRouter, "route", forbidden)
    monkeypatch.setattr(MemoryService, "query", forbidden)
    monkeypatch.setattr(MemoryService, "store", forbidden)
    for need in (system_need(), memory_need(), capability_need(), intelligence_need()):
        assert decide(need, availability=ALL_AVAILABLE).target is not None


def test_policy_contract_is_replaceable_and_programming_defects_propagate() -> None:
    assert isinstance(DeterministicOrchestrationPolicy(), OrchestrationPolicy)

    class Invalid:
        def select(
            self, orchestration_input: OrchestrationInput
        ) -> OrchestrationSelection:
            return cast(OrchestrationSelection, object())

    class Broken:
        def select(
            self, orchestration_input: OrchestrationInput
        ) -> OrchestrationSelection:
            raise RuntimeError("programming defect")

    class Unavailable:
        def select(
            self, orchestration_input: OrchestrationInput
        ) -> OrchestrationSelection:
            need = orchestration_input.needs[0]
            return OrchestrationSelection(
                OrchestrationTarget.SYSTEM,
                OrchestrationReason.DETERMINISTIC_SYSTEM_REQUEST,
                (need.need_id,),
                need,
            )

    request = Request("input", "test", request_id="request-1")
    input_value = OrchestrationInput(
        request, snapshot(request), (system_need(),), ALL_AVAILABLE
    )
    with pytest.raises(OrchestrationPolicyContractError):
        fixed_orchestrator(Invalid()).decide(input_value)
    with pytest.raises(RuntimeError, match="programming defect"):
        fixed_orchestrator(Broken()).decide(input_value)
    unavailable_input = replace(input_value, availability=HandlerAvailability())
    with pytest.raises(OrchestrationPolicyContractError, match="unavailable"):
        fixed_orchestrator(Unavailable()).decide(unavailable_input)
