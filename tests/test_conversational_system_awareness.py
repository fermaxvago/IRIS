"""WP066: one local observation, one explicit disclosure, one atomic turn."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

import iris.__main__ as cli
from iris.capabilities import (
    SYSTEM_STATUS_CAPABILITY_ID,
    CapabilityInput,
    CapabilityRegistry,
    CapabilityResult,
    CapabilityRuntime,
    SystemResourceObservation,
    SystemStatusTool,
)
from iris.context import ContextEngine, ContextKind, EvidenceSource, ResolutionStatus
from iris.core.system import SystemInfo
from iris.intelligence import (
    ContextBindingError,
    ConversationContextBinder,
    ConversationLimitError,
    ConversationRequest,
    ConversationSession,
    IntelligenceResult,
    IntelligenceRuntime,
    IntelligenceStatus,
    ModelCapability,
    ModelDescriptor,
    ModelLocation,
    ProviderRegistry,
)
from iris.intelligence.system_awareness import (
    ConversationalSystemAwareness,
    SystemAwarenessError,
)
from iris.memory import ScopeKind
from iris.work_identity.models import WorkSubjectKind

NOW = datetime(2026, 10, 21, 12, tzinfo=UTC)


def info(**changes: object) -> SystemInfo:
    result: dict[str, object] = {
        "cpu_percent": 27.0,
        "ram_used_gb": 21.4,
        "ram_total_gb": 31.7,
    }
    result.update(changes)
    return result  # type: ignore[return-value]


@dataclass
class Provider:
    provider_id: str = "local"
    model_id: str = "model"
    fail: bool = False
    requests: list[ConversationRequest] = field(default_factory=list)
    ordinary_requests: list[ConversationRequest] = field(default_factory=list)

    def list_models(self) -> tuple[ModelDescriptor, ...]:
        return (
            ModelDescriptor(
                provider_id=self.provider_id,
                model_id=self.model_id,
                location=ModelLocation.LOCAL,
                capabilities=frozenset({ModelCapability.CONVERSATION}),
            ),
        )

    def infer(self, request: Any) -> IntelligenceResult:
        raise AssertionError("no legacy inference")

    def chat(self, request: ConversationRequest) -> IntelligenceResult:
        self.ordinary_requests.append(request)
        return IntelligenceResult.succeeded(
            request, provider_id=self.provider_id, output="respuesta"
        )

    def chat_with_context(self, request: ConversationRequest) -> IntelligenceResult:
        self.requests.append(request)
        return IntelligenceResult(
            request_id=request.request_id,
            provider_id=self.provider_id,
            model_id=request.model_id,
            status=IntelligenceStatus.FAILURE
            if self.fail
            else IntelligenceStatus.SUCCESS,
            diagnostic="unavailable" if self.fail else None,
            output=None
            if self.fail
            else "Según la medición, no puedo diagnosticar presión.",
        )


@dataclass
class Harness:
    session: ConversationSession
    provider: Provider
    awareness: ConversationalSystemAwareness
    captures: list[int]
    binder: ConversationContextBinder


def harness(reading: SystemInfo | None = None) -> Harness:
    calls: list[int] = []

    def capture() -> SystemInfo:
        calls.append(1)
        return info() if reading is None else reading

    tool = SystemStatusTool(system_info_provider=capture, clock=lambda: NOW)
    provider = Provider()
    session = ConversationSession(
        IntelligenceRuntime(ProviderRegistry([provider])),
        provider_id="local",
        model_id="model",
    )
    binder = ConversationContextBinder(clock=lambda: NOW)
    awareness = ConversationalSystemAwareness(
        capability_runtime=CapabilityRuntime(CapabilityRegistry([tool])),
        context_binder=binder,
        clock=lambda: NOW,
    )
    return Harness(session, provider, awareness, calls, binder)


def run_cli(h: Harness, *answers: str) -> list[str]:
    entries = iter((*answers, "/salir", "salir"))
    output: list[str] = []
    cli.main(
        input_fn=lambda _prompt: next(entries),
        output_fn=output.append,
        chat_session=h.session,
        system_awareness=h.awareness,
    )
    return output


def test_diagnostic_inspection_preserves_existing_context_approval() -> None:
    h = harness()
    prepared = h.awareness.prepare(h.session, "¿Cómo está mi RAM?")
    assert prepared.proposal is not None
    proposal = prepared.proposal
    approval = h.binder.approve(
        proposal,
        approved_item_ids=proposal.item_ids,
        approved_scopes=proposal.scopes,
    )
    before = h.session.diagnostic_snapshot()
    output = run_cli(h, "/diagnostico")
    assert len(h.captures) == 1 and not h.provider.requests
    assert h.session.diagnostic_snapshot() == before
    assert not any(proposal.payload.section in line for line in output)
    assert not any(approval.approval_id in line for line in output)
    assert h.session.send(proposal.content, approval=approval).success
    assert len(h.provider.requests) == 1
    assert h.session.diagnostic_snapshot().active_turns == 1


def test_stale_disclosure_after_observation_reports_no_committed_turn() -> None:
    h = harness()
    entries = iter(("/recursos ¿Cómo está mi RAM?", "/diagnostico", "/salir", "salir"))
    output: list[str] = []

    def answer(prompt: str) -> str:
        if "¿Autorizas esta divulgación" in prompt:
            h.session.reset()
            return "sí"
        return next(entries)

    cli.main(
        input_fn=answer,
        output_fn=output.append,
        chat_session=h.session,
        system_awareness=h.awareness,
    )
    assert len(h.captures) == 1
    assert not h.provider.requests
    assert h.session.messages == ()
    assert any("Divulgación no válida" in line for line in output)
    assert any("no se confirmó un turno" in line for line in output)
    assert any("Turnos activos: 0/8" in line for line in output)


def test_structured_capability_preserves_text_and_captures_once() -> None:
    h = harness()
    tool = SystemStatusTool(
        system_info_provider=lambda: info(),
        system_info_formatter=lambda _info: "legacy",
        clock=lambda: NOW,
    )
    structured = tool.execute(CapabilityInput(payload={"output_mode": "structured"}))
    assert isinstance(structured.output, SystemResourceObservation)
    assert structured.output.complete
    assert structured.output.captured_at == NOW
    assert structured.output.cpu_percent == 27.0
    assert tool.execute(CapabilityInput()).output == "legacy"
    with pytest.raises(ValueError, match="unsupported"):
        tool.execute(CapabilityInput(payload={"output_mode": "json"}))
    assert h.captures == []


@pytest.mark.parametrize(
    "changes,missing",
    [
        ({"cpu_percent": None}, "cpu_percent"),
        ({"ram_used_gb": None}, "ram_used_gb"),
        ({"ram_total_gb": None}, "ram_total_gb"),
        ({"cpu_percent": float("nan")}, "cpu_percent"),
        ({"ram_used_gb": True}, "ram_used_gb"),
        ({"ram_total_gb": -1.0}, "ram_total_gb"),
        ({"ram_used_gb": 50.0}, "ram_used_gb"),
        ({"ram_used_gb": "21.4"}, "ram_used_gb"),
        ({"ram_used_gb": 10**1000}, "ram_used_gb"),
    ],
)
def test_partial_or_invalid_measurement_is_local_only(
    changes: dict[str, object], missing: str
) -> None:
    h = harness(info(**changes))
    output = run_cli(h, "/recursos ¿Cómo está mi RAM?")
    assert len(h.captures) == 1
    assert not h.provider.requests
    assert h.session.messages == ()
    assert any(missing in line for line in output)
    assert any("No disponible" in line for line in output)


def test_prepare_uses_exact_canonical_context_and_no_inference() -> None:
    h = harness()
    result = h.awareness.prepare(h.session, "¿Cómo están mi CPU y mi RAM?")
    assert len(h.captures) == 1
    assert result.proposal is not None
    proposal = result.proposal
    snapshot = proposal.snapshot
    assert snapshot.status is ResolutionStatus.RESOLVED
    assert snapshot.subject is proposal.subject
    assert snapshot.subject.kind is WorkSubjectKind.REQUEST
    assert len(snapshot.items) == 3
    assert {item.key for item in snapshot.items} == {
        "cpu_percent",
        "ram_used_gb",
        "ram_total_gb",
    }
    assert all(item.kind == ContextKind.RESOURCE.value for item in snapshot.items)
    assert all(item.evidence.source is EvidenceSource.SYSTEM for item in snapshot.items)
    assert all(item.evidence.reference == "system.status" for item in snapshot.items)
    assert all(item.scope.kind is ScopeKind.SESSION for item in snapshot.items)
    assert all(item.scope.identifier == h.session.session_id for item in snapshot.items)
    assert all(item.observed_at == NOW for item in snapshot.items)
    assert snapshot.created_at == NOW
    assert len(proposal.payload.section) <= 1500
    assert not h.provider.requests
    assert h.session.messages == ()
    second = h.awareness.prepare(h.session, "¿Cómo está mi RAM?")
    assert second.proposal is not None
    assert second.proposal.subject.subject_id != proposal.subject.subject_id
    assert len(h.captures) == 2


def test_cli_approved_turn_discloses_exact_payload_and_commits_once() -> None:
    h = harness()
    output = run_cli(h, "/recursos ¿Cómo están mi CPU y mi RAM?", "sí")
    assert len(h.captures) == 1
    assert len(h.provider.requests) == 1
    request = h.provider.requests[0]
    assert request.messages[-1].content == "¿Cómo están mi CPU y mi RAM?"
    assert request.context is not None
    assert "system.status" in request.context.section
    assert "cpu_percent" in request.context.section
    assert "ram_used_gb" in request.context.section
    assert "ram_total_gb" in request.context.section
    assert any(request.context.section == line for line in output)
    assert any("local/model" in line for line in output)
    assert h.session.completed_turns == 1
    assert len(h.session.messages) == 2
    assert all("IRIS_CONTEXT" not in m.content for m in h.session.messages)
    assert any("Según la medición" in line for line in output)
    assert output[-1].startswith("IRIS apag")


@pytest.mark.parametrize("decision", ["no", "", "quizás", "yes"])
def test_cli_denial_never_invokes_provider(decision: str) -> None:
    h = harness()
    output = run_cli(h, "/recursos ¿Cómo está mi RAM?", decision)
    assert len(h.captures) == 1
    assert not h.provider.requests
    assert h.session.messages == ()
    assert any("no autorizada" in line for line in output)


def test_bare_command_does_not_capture() -> None:
    h = harness()
    output = run_cli(h, "/recursos")
    assert h.captures == []
    assert not h.provider.requests
    assert any("Uso: /recursos" in line for line in output)


def test_provider_failure_preserves_observation_display_and_history() -> None:
    h = harness()
    h.provider.fail = True
    output = run_cli(h, "/recursos ¿Cómo está mi RAM?", "si")
    assert len(h.captures) == 1
    assert len(h.provider.requests) == 1
    assert h.session.messages == ()
    assert any("RAM utilizada: 21.4 GiB" in line for line in output)
    assert any("historial sin cambios" in line for line in output)


def test_replay_reset_foreign_session_and_model_fail_closed() -> None:
    h = harness()
    proposal = h.awareness.prepare(h.session, "pregunta").proposal
    assert proposal is not None
    h.awareness.send_approved(h.session, proposal)
    with pytest.raises(ContextBindingError):
        h.awareness.send_approved(h.session, proposal)
    other = harness()
    proposal2 = h.awareness.prepare(h.session, "segunda").proposal
    assert proposal2 is not None
    with pytest.raises(ContextBindingError):
        h.awareness.send_approved(other.session, proposal2)
    h.session.reset()
    with pytest.raises(ContextBindingError):
        h.awareness.send_approved(h.session, proposal2)


def test_budget_failure_and_expiration_prevent_inference() -> None:
    h = harness()
    h.session.send("x" * 2000)
    h.session.send("x" * 2000)
    before = h.session.messages
    with pytest.raises(ConversationLimitError):
        h.awareness.prepare(h.session, "x" * 1900)
    assert h.session.messages is before
    assert not h.provider.requests

    h2 = harness()
    proposal = h2.awareness.prepare(h2.session, "question").proposal
    assert proposal is not None
    expired = replace(proposal, expires_at=NOW - timedelta(seconds=1))
    with pytest.raises(ContextBindingError):
        h2.awareness.send_approved(h2.session, expired)
    assert not h2.provider.requests


def test_failed_capability_and_malformed_return_never_infer() -> None:
    h = harness()

    class FailedTool:
        descriptor = SystemStatusTool().descriptor

        def execute(self, _input: CapabilityInput) -> CapabilityResult:
            return CapabilityResult.failed(
                SYSTEM_STATUS_CAPABILITY_ID, diagnostic="offline"
            )

    h.awareness = ConversationalSystemAwareness(
        capability_runtime=CapabilityRuntime(CapabilityRegistry([FailedTool()])),
        clock=lambda: NOW,
    )
    with pytest.raises(SystemAwarenessError, match="offline"):
        h.awareness.prepare(h.session, "question")
    assert not h.provider.requests

    class MalformedTool:
        descriptor = SystemStatusTool().descriptor

        def execute(self, _input: CapabilityInput) -> CapabilityResult:
            return CapabilityResult.succeeded(
                SYSTEM_STATUS_CAPABILITY_ID, output="text"
            )

    h.awareness = ConversationalSystemAwareness(
        capability_runtime=CapabilityRuntime(CapabilityRegistry([MalformedTool()])),
        clock=lambda: NOW,
    )
    with pytest.raises(SystemAwarenessError, match="structured"):
        h.awareness.prepare(h.session, "question")
    assert not h.provider.requests


def test_invalid_context_cannot_be_forced_into_proposal() -> None:
    h = harness()

    class EmptyContext(ContextEngine):
        def build(self, **kwargs: Any) -> Any:
            snapshot = super().build(**kwargs)
            return replace(snapshot, items=(), status=ResolutionStatus.RESOLVED)

    h.awareness = ConversationalSystemAwareness(
        capability_runtime=h.awareness._capabilities,
        context_engine=EmptyContext(),
        context_binder=h.binder,
        clock=lambda: NOW,
    )
    with pytest.raises(SystemAwarenessError, match="incomplete"):
        h.awareness.prepare(h.session, "question")
    assert not h.provider.requests


def test_wrong_capability_identity_and_malformed_capture_fail_closed() -> None:
    h = harness()

    class WrongIdentity:
        descriptor = SystemStatusTool().descriptor

        def execute(self, _input: CapabilityInput) -> CapabilityResult:
            return CapabilityResult.succeeded("another.capability", output="wrong")

    h.awareness = ConversationalSystemAwareness(
        capability_runtime=CapabilityRuntime(CapabilityRegistry([WrongIdentity()])),
        clock=lambda: NOW,
    )
    with pytest.raises(ValueError, match="identifier"):
        h.awareness.prepare(h.session, "question")
    bad_tool = SystemStatusTool(system_info_provider=lambda: None)  # type: ignore[arg-type,return-value]
    h.awareness = ConversationalSystemAwareness(
        capability_runtime=CapabilityRuntime(CapabilityRegistry([bad_tool])),
        clock=lambda: NOW,
    )
    with pytest.raises(ValueError, match="malformed"):
        h.awareness.prepare(h.session, "question")
    assert not h.provider.requests


def test_future_or_non_utc_capture_cannot_be_disclosed() -> None:
    h = harness()
    future = SystemStatusTool(
        system_info_provider=info,
        clock=lambda: NOW + timedelta(seconds=1),
    )
    h.awareness = ConversationalSystemAwareness(
        capability_runtime=CapabilityRuntime(CapabilityRegistry([future])),
        context_binder=h.binder,
        clock=lambda: NOW,
    )
    with pytest.raises(SystemAwarenessError, match="future"):
        h.awareness.prepare(h.session, "question")
    with pytest.raises(ValueError, match="UTC"):
        SystemResourceObservation(27.0, 21.4, 31.7, datetime(2026, 10, 21))
    assert not h.provider.requests


def test_substituted_context_item_cannot_be_previewed() -> None:
    h = harness()

    class SubstitutedContext(ContextEngine):
        def build(self, **kwargs: Any) -> Any:
            snapshot = super().build(**kwargs)
            changed = replace(snapshot.items[0], value=99.0)
            return replace(snapshot, items=(changed, *snapshot.items[1:]))

    h.awareness = ConversationalSystemAwareness(
        capability_runtime=h.awareness._capabilities,
        context_engine=SubstitutedContext(),
        context_binder=h.binder,
        clock=lambda: NOW,
    )
    with pytest.raises(SystemAwarenessError, match="incomplete"):
        h.awareness.prepare(h.session, "question")
    assert not h.provider.requests


def test_decline_leaves_chat_usable_and_second_query_needs_fresh_consent() -> None:
    h = harness()
    output = run_cli(
        h,
        "/recursos ¿Cómo está mi RAM?",
        "no",
        "hola",
        "/recursos ¿Cómo está mi CPU?",
        "si",
    )
    assert len(h.captures) == 2
    assert len(h.provider.ordinary_requests) == 1
    assert len(h.provider.requests) == 1
    assert h.provider.requests[0].messages[0].content == "hola"
    assert h.provider.requests[0].messages[-1].content == "¿Cómo está mi CPU?"
    assert h.session.completed_turns == 2
    assert any("no autorizada" in line for line in output)


def test_confirmation_interruption_cannot_authorize() -> None:
    h = harness()
    prompts = iter(("/recursos ¿Cómo está mi CPU?",))
    output: list[str] = []

    def input_fn(_prompt: str) -> str:
        try:
            return next(prompts)
        except StopIteration as exc:
            raise EOFError from exc

    # EOF leaves chat and the legacy loop; no contextual turn is committed.
    cli.main(
        input_fn=input_fn,
        output_fn=output.append,
        chat_session=h.session,
        system_awareness=h.awareness,
    )
    assert len(h.captures) == 1
    assert h.session.messages == ()
    assert not h.provider.requests
    assert any("no autorizada" in line for line in output)


def test_unencodable_model_text_is_safe_for_legacy_windows_console() -> None:
    assert cli._safe_terminal_text("CPU 😊", encoding="cp1252") == "CPU \\U0001f60a"
