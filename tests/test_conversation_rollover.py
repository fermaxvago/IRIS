"""WP069: atomic bounded windows and exact contextual approval identity."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from threading import Event, Thread
from typing import Any

import pytest

import iris.__main__ as cli
from iris.context import (
    ContextBudget,
    ContextCandidate,
    ContextEngine,
    ContextEvidence,
    EvidenceSource,
    Freshness,
    Relevance,
)
from iris.intelligence import (
    ContextBindingError,
    ConversationContextBinder,
    ConversationLimitError,
    ConversationRequest,
    ConversationSession,
    IntelligenceResult,
    IntelligenceRuntime,
    ModelCapability,
    ModelDescriptor,
    ModelLocation,
    ProviderRegistry,
)
from iris.intelligence.conversation import ConversationBusyError
from iris.memory import EpistemicStatus, MemoryScope, ScopeKind
from iris.work_identity.models import RequestWorkReference, WorkSubject, WorkSubjectKind

NOW = datetime(2026, 10, 22, 12, tzinfo=UTC)


@dataclass
class Provider:
    provider_id: str = "local"
    output: str = "respuesta"
    fail: bool = False
    incomplete: bool = False
    callback: Callable[[ConversationRequest], None] | None = None
    requests: list[ConversationRequest] = field(default_factory=list)

    def list_models(self) -> tuple[ModelDescriptor, ...]:
        return (
            ModelDescriptor(
                provider_id=self.provider_id,
                model_id="modelo",
                location=ModelLocation.LOCAL,
                capabilities=frozenset({ModelCapability.CONVERSATION}),
            ),
        )

    def infer(self, request: Any) -> IntelligenceResult:
        raise AssertionError("legacy inference is not used")

    def chat(self, request: ConversationRequest) -> IntelligenceResult:
        return self._answer(request)

    def chat_with_context(self, request: ConversationRequest) -> IntelligenceResult:
        return self._answer(request)

    def _answer(self, request: ConversationRequest) -> IntelligenceResult:
        self.requests.append(request)
        if self.callback is not None:
            self.callback(request)
        if self.fail:
            return IntelligenceResult.failed(
                request, provider_id=self.provider_id, diagnostic="offline"
            )
        if self.incomplete:
            return IntelligenceResult.failed(
                request,
                provider_id=self.provider_id,
                diagnostic="generation did not complete",
                metadata={"failure_kind": "incomplete_generation"},
            )
        return IntelligenceResult.succeeded(
            request, provider_id=self.provider_id, output=self.output
        )


def session(provider: Provider | None = None) -> tuple[ConversationSession, Provider]:
    actual = provider or Provider()
    return (
        ConversationSession(
            IntelligenceRuntime(ProviderRegistry([actual])),
            provider_id=actual.provider_id,
            model_id="modelo",
        ),
        actual,
    )


def fill(conversation: ConversationSession, count: int = 8) -> None:
    for index in range(count):
        assert conversation.send(f"turno {index}").success


def approved_context(
    conversation: ConversationSession,
    *,
    binder: ConversationContextBinder | None = None,
    content: str = "consulta",
) -> tuple[ConversationContextBinder, Any, Any]:
    actual = binder or ConversationContextBinder(clock=lambda: NOW)
    owner = WorkSubject(WorkSubjectKind.REQUEST, RequestWorkReference("request-1"))
    item = ContextCandidate(
        candidate_id="item-1",
        kind="task",
        key="state",
        value="observed",
        evidence=ContextEvidence(
            EvidenceSource.CALLER, "source-1", EpistemicStatus.DIRECT
        ),
        scope=MemoryScope(ScopeKind.SESSION, conversation.session_id),
        relevance=Relevance.REQUIRED,
        freshness=Freshness.CURRENT,
        observed_at=NOW - timedelta(seconds=10),
    )
    snapshot = ContextEngine().build(
        subject=owner,
        candidates=(item,),
        budget=ContextBudget(1),
        created_at=NOW,
    )
    proposal = actual.propose(conversation, snapshot, subject=owner, content=content)
    approval = actual.approve(
        proposal,
        approved_item_ids=proposal.item_ids,
        approved_scopes=proposal.scopes,
    )
    return actual, proposal, approval


def test_default_policy_rejects_ninth_without_inference_or_mutation() -> None:
    conversation, provider = session()
    assert not conversation.continuity_enabled
    fill(conversation)
    before = conversation.messages
    revision = conversation.revision
    with pytest.raises(ConversationLimitError, match="session is full"):
        conversation.send("noveno")
    assert conversation.messages is before
    assert conversation.revision == revision == 8
    assert len(provider.requests) == 8
    assert conversation.can_rollover("noveno")


def test_explicit_policy_rolls_only_complete_oldest_pairs_and_is_session_local() -> (
    None
):
    conversation, provider = session()
    other, _ = session()
    fill(conversation)
    before = conversation.messages
    with pytest.raises(ConversationLimitError):
        conversation.prepare_window("noveno")
    conversation.set_continuity(True)
    assert conversation.revision == 9
    window = conversation.prepare_window("noveno")
    assert window.history is before
    assert window.retired_turns == 0
    assert conversation.messages is before
    assert conversation.send("noveno").success
    assert provider.requests[-1].messages[:-1] == before
    assert conversation.messages == (*before[2:], *conversation.messages[-2:])
    assert conversation.completed_turns == 8
    assert conversation.last_commit_evictions == 1
    assert conversation.revision == 10
    assert conversation.send("décimo").success
    assert conversation.completed_turns == 8
    assert conversation.messages[0].content == "turno 2"
    assert not other.continuity_enabled and other.messages == ()


def test_character_budget_uses_longest_suffix_then_adjusts_after_generation() -> None:
    provider = Provider(output="a" * 1000)
    conversation, _ = session(provider)
    fill(conversation, 5)
    conversation.set_continuity(True)
    before = conversation.messages
    window = conversation.prepare_window("u" * 1500)
    assert window.history == before[2:]
    assert window.retired_turns == 1
    assert conversation.messages is before
    assert conversation.send("u" * 1500).success
    assert provider.requests[-1].messages[:-1] == before[2:]
    assert conversation.messages[:-2] == before[4:]
    assert conversation.last_commit_evictions == 2
    assert sum(len(item.content) for item in conversation.messages) <= 6000


@pytest.mark.parametrize(
    "mode", ["failure", "incomplete", "exception", "interrupt", "blank", "too_long"]
)
def test_failed_generation_never_evicts_or_advances_revision(mode: str) -> None:
    conversation, provider = session()
    fill(conversation)
    conversation.set_continuity(True)
    before = conversation.messages
    revision = conversation.revision
    if mode == "failure":
        provider.fail = True
    elif mode == "incomplete":
        provider.incomplete = True
    elif mode == "exception":
        provider.callback = lambda request: (_ for _ in ()).throw(RuntimeError())
    elif mode == "interrupt":
        provider.callback = lambda request: (_ for _ in ()).throw(KeyboardInterrupt())
    elif mode == "blank":
        provider.output = " "
    else:
        provider.output = "z" * 6001
    if mode in ("failure", "incomplete"):
        assert not conversation.send("intento").success
    else:
        with pytest.raises((RuntimeError, KeyboardInterrupt, ValueError)):
            conversation.send("intento")
    assert conversation.messages is before
    assert conversation.revision == revision
    assert conversation.completed_turns == 8


def test_candidate_rejects_stale_revision_and_policy_reset_invalidate_state() -> None:
    conversation, _ = session()
    candidate = conversation.prepare_window("hola")
    assert candidate.revision == 0
    conversation.set_continuity(True)
    assert conversation.revision == 1
    assert conversation.prepare_window("hola") != candidate
    conversation.send("hola")
    assert conversation.revision == 2
    conversation.reset()
    assert conversation.revision == 3
    assert conversation.generation == 1
    assert conversation.messages == ()
    assert not conversation.continuity_enabled


def test_context_approval_transmits_exact_candidate_and_consumes_once() -> None:
    conversation, provider = session()
    fill(conversation)
    conversation.set_continuity(True)
    binder, proposal, approval = approved_context(conversation)
    assert proposal.window.revision == conversation.revision
    assert proposal.window.history == conversation.messages
    assert conversation.send("consulta", approval=approval).success
    request = provider.requests[-1]
    assert request.messages[:-1] == proposal.window.history
    assert request.context is not None
    assert conversation.completed_turns == 8
    with pytest.raises(ContextBindingError):
        conversation.send("consulta", approval=approval)


def test_context_budget_selects_the_same_longest_suffix_for_approval_and_inference() -> (
    None
):
    provider = Provider(output="a" * 1000)
    conversation, _ = session(provider)
    fill(conversation, 5)
    conversation.set_continuity(True)
    before = conversation.messages
    _, proposal, approval = approved_context(conversation, content="u" * 1000)
    assert proposal.window.history == before[2:]
    assert proposal.window.retired_turns == 1
    assert conversation.messages is before
    assert conversation.send(proposal.content, approval=approval).success
    assert provider.requests[-1].messages[:-1] == proposal.window.history
    assert provider.requests[-1].context is not None
    assert conversation.messages[:-2] == before[4:]


def test_failed_contextual_inference_does_not_reuse_approval_or_evict() -> None:
    conversation, provider = session()
    fill(conversation)
    conversation.set_continuity(True)
    _, proposal, approval = approved_context(conversation)
    before = conversation.messages
    revision = conversation.revision
    provider.fail = True
    assert not conversation.send(proposal.content, approval=approval).success
    assert conversation.messages is before and conversation.revision == revision
    with pytest.raises(ContextBindingError):
        conversation.send(proposal.content, approval=approval)


@pytest.mark.parametrize("transition", ["ordinary", "rollover", "reset", "disable"])
def test_context_approval_is_stale_after_every_state_transition(
    transition: str,
) -> None:
    conversation, provider = session()
    fill(conversation)
    conversation.set_continuity(True)
    _, proposal, approval = approved_context(conversation)
    before_requests = len(provider.requests)
    if transition in ("ordinary", "rollover"):
        conversation.send("intermedio")
        assert conversation.completed_turns == 8
    elif transition == "reset":
        conversation.reset()
    else:
        conversation.set_continuity(False)
    with pytest.raises(ContextBindingError):
        conversation.send(proposal.content, approval=approval)
    assert len(provider.requests) == before_requests + int(
        transition in ("ordinary", "rollover")
    )


def test_mutated_candidate_or_destination_cannot_be_approved() -> None:
    conversation, provider = session()
    binder, proposal, _ = approved_context(conversation)
    forged = replace(proposal, window=replace(proposal.window, content="different"))
    with pytest.raises(ContextBindingError):
        binder.approve(
            forged, approved_item_ids=forged.item_ids, approved_scopes=forged.scopes
        )
    other, _ = session()
    with pytest.raises(ContextBindingError):
        conversation.send("consulta", approval=approved_context(other)[2])
    assert not provider.requests


def test_session_lock_blocks_concurrent_send_reset_and_policy_change() -> None:
    entered = Event()
    release = Event()

    def wait_for_release(request: ConversationRequest) -> None:
        entered.set()
        assert release.wait(timeout=5)

    provider = Provider(callback=wait_for_release)
    conversation, _ = session(provider)
    results: list[object] = []

    def send() -> None:
        results.append(conversation.send("primero"))

    worker = Thread(target=send)
    worker.start()
    assert entered.wait(timeout=5)
    try:
        with pytest.raises(ConversationBusyError):
            conversation.send("segundo")
        with pytest.raises(ConversationBusyError):
            conversation.reset()
        with pytest.raises(ConversationBusyError):
            conversation.set_continuity(True)
        with pytest.raises(ConversationBusyError):
            conversation.prepare_window("tercero")
        assert conversation.messages == () and conversation.revision == 0
    finally:
        release.set()
        worker.join(timeout=5)
    assert len(results) == 1 and conversation.revision == 1


def test_cli_offers_once_and_reports_only_committed_eviction() -> None:
    conversation, provider = session()
    fill(conversation)
    answers = iter(
        ("noveno", "no", "noveno", "sí", "/continuidad estado", "/salir", "salir")
    )
    output: list[str] = []
    cli.main(
        input_fn=lambda prompt: next(answers),
        output_fn=output.append,
        chat_session=conversation,
    )
    assert len(provider.requests) == 9
    assert conversation.completed_turns == 8
    assert sum("retiró 1 turno" in line for line in output) == 1
    assert any("Continuidad activada" in line for line in output)


def test_cli_explicit_disable_then_reset_preserves_policy_lifecycle() -> None:
    conversation, _ = session()
    inputs = iter(
        (
            "/continuidad activar",
            "/continuidad desactivar",
            "/continuidad activar",
            "/reiniciar",
            "/continuidad estado",
            "/salir",
            "salir",
        )
    )
    output: list[str] = []
    cli.main(
        input_fn=lambda prompt: next(inputs),
        output_fn=output.append,
        chat_session=conversation,
    )
    assert not conversation.continuity_enabled
    assert conversation.generation == 1 and conversation.revision == 4
    assert any("Continuidad desactivada; 0 turnos" in line for line in output)


def test_disabling_continuity_does_not_restore_evicted_history() -> None:
    conversation, provider = session()
    fill(conversation)
    conversation.set_continuity(True)
    conversation.send("noveno")
    before = conversation.messages
    assert before[0].content == "turno 1"
    conversation.set_continuity(False)
    with pytest.raises(ConversationLimitError):
        conversation.send("décimo")
    assert conversation.messages is before
    assert len(provider.requests) == 9


def test_unrelated_slash_command_remains_ordinary_chat() -> None:
    conversation, provider = session()
    inputs = iter(("/continuidadx revisar", "/salir", "salir"))
    cli.main(
        input_fn=lambda prompt: next(inputs),
        output_fn=lambda text: None,
        chat_session=conversation,
    )
    assert provider.requests[-1].messages[-1].content == "/continuidadx revisar"
