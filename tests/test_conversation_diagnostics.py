"""WP070: coherent read-only diagnostics and bounded failure presentation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass, field
from threading import Event, Thread
from typing import Any

import pytest

import iris.__main__ as cli
from iris.intelligence import (
    ConversationBusyError,
    ConversationRequest,
    ConversationSession,
    IntelligenceResult,
    IntelligenceRuntime,
    ModelCapability,
    ModelDescriptor,
    ModelLocation,
    ProviderRegistry,
)


@dataclass
class Provider:
    provider_id: str = "local"
    model_id: str = "model"
    response: str = "respuesta privada"
    failure: dict[str, object] | None = None
    callback: Callable[[], None] | None = None
    requests: list[ConversationRequest] = field(default_factory=list)

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
        raise AssertionError("legacy inference is not used")

    def chat(self, request: ConversationRequest) -> IntelligenceResult:
        self.requests.append(request)
        if self.callback is not None:
            self.callback()
        if self.failure is not None:
            return IntelligenceResult.failed(
                request,
                provider_id=self.provider_id,
                diagnostic="untrusted provider detail",
                metadata=self.failure,
            )
        return IntelligenceResult.succeeded(
            request, provider_id=self.provider_id, output=self.response
        )


def make_session(
    provider: Provider | None = None,
) -> tuple[ConversationSession, Provider]:
    actual = provider or Provider()
    return (
        ConversationSession(
            IntelligenceRuntime(ProviderRegistry([actual])),
            provider_id=actual.provider_id,
            model_id=actual.model_id,
        ),
        actual,
    )


def run_cli(
    session: ConversationSession, *entries: str, system_awareness: Any = None
) -> list[str]:
    inputs = iter((*entries, "/salir", "salir"))
    output: list[str] = []
    cli.main(
        input_fn=lambda _prompt: next(inputs),
        output_fn=output.append,
        chat_session=session,
        system_awareness=system_awareness,
    )
    return output


def diagnostic_lines(output: list[str]) -> list[str]:
    start = output.index("Diagnóstico de conversación (sin comprobar disponibilidad):")
    return output[start : start + 8]


def test_snapshot_is_immutable_coherent_and_remains_historical() -> None:
    conversation, provider = make_session()
    initial = conversation.diagnostic_snapshot()
    assert (
        initial.provider_id,
        initial.model_id,
        initial.active_turns,
        initial.active_characters,
        initial.continuity_enabled,
        initial.revision,
        initial.generation,
    ) == ("local", "model", 0, 0, False, 0, 0)
    with pytest.raises(FrozenInstanceError):
        initial.active_turns = 99  # type: ignore[misc]

    conversation.send("pregunta privada")
    committed = conversation.diagnostic_snapshot()
    assert committed.active_turns == 1
    assert committed.active_characters == len("pregunta privada") + len(
        provider.response
    )
    assert committed.revision == 1 and committed.generation == 0
    assert initial.active_turns == 0 and initial.active_characters == 0
    conversation.set_continuity(True)
    enabled = conversation.diagnostic_snapshot()
    assert enabled.continuity_enabled and enabled.revision == 2
    conversation.set_continuity(False)
    assert conversation.diagnostic_snapshot().revision == 3
    conversation.reset()
    reset = conversation.diagnostic_snapshot()
    assert (reset.active_turns, reset.active_characters) == (0, 0)
    assert not reset.continuity_enabled and reset.generation == 1
    assert reset.revision == 4
    assert enabled.active_turns == 1 and enabled.continuity_enabled
    assert len(provider.requests) == 1


def test_snapshot_after_rollover_uses_retained_history_not_lifetime_count() -> None:
    conversation, provider = make_session()
    for index in range(8):
        conversation.send(f"turno {index}")
    before = conversation.diagnostic_snapshot()
    conversation.set_continuity(True)
    conversation.send("noveno")
    after = conversation.diagnostic_snapshot()
    assert before.active_turns == after.active_turns == 8
    assert after.active_characters == sum(len(m.content) for m in conversation.messages)
    assert after.revision == before.revision + 2
    assert conversation.last_commit_evictions == 1
    assert before.active_characters != after.active_characters
    assert len(provider.requests) == 9


def test_snapshot_is_busy_without_partial_read_or_inference_interference() -> None:
    entered = Event()
    release = Event()

    def wait_for_release() -> None:
        entered.set()
        assert release.wait(timeout=5)

    conversation, provider = make_session(Provider(callback=wait_for_release))
    result: list[IntelligenceResult] = []
    worker = Thread(target=lambda: result.append(conversation.send("private")))
    worker.start()
    assert entered.wait(timeout=5)
    try:
        with pytest.raises(ConversationBusyError, match="busy"):
            conversation.diagnostic_snapshot()
        output = run_cli(conversation, "/diagnostico")
        assert any("conversación está ocupada" in line for line in output)
        assert not any("Diagnóstico de conversación" in line for line in output)
        assert conversation.messages == () and conversation.revision == 0
    finally:
        release.set()
        worker.join(timeout=5)
    assert not worker.is_alive()
    assert len(result) == len(provider.requests) == 1
    assert conversation.diagnostic_snapshot().active_turns == 1


def test_cli_diagnostic_is_read_only_private_and_terminal_safe() -> None:
    class NoObservation:
        def prepare(self, *_args: object) -> None:
            raise AssertionError("diagnostic attempted resource observation")

        def send_approved(self, *_args: object) -> None:
            raise AssertionError("diagnostic attempted contextual disclosure")

    provider = Provider(provider_id="local\x1b[31m\nspoof", model_id="model\x1b[2J")
    conversation, _ = make_session(provider)
    conversation.send("mensaje privado")
    before = (
        conversation.messages,
        conversation.revision,
        conversation.generation,
        conversation.continuity_enabled,
        conversation.last_commit_evictions,
    )
    output = run_cli(conversation, "/diagnostico", system_awareness=NoObservation())
    lines = diagnostic_lines(output)
    assert len(provider.requests) == 1
    assert "local\\x1b[31m\\nspoof" in lines[1]
    assert "model\\x1b[2J" in lines[2]
    assert "Turnos activos: 1/8" in lines
    assert any("solo mensajes retenidos; no son tokens" in line for line in lines)
    assert any("no comprobada" in line for line in lines)
    assert not any(
        "mensaje privado" in line or provider.response in line for line in lines
    )
    assert not any(conversation.session_id in line or "\x1b" in line for line in lines)
    assert before == (
        conversation.messages,
        conversation.revision,
        conversation.generation,
        conversation.continuity_enabled,
        conversation.last_commit_evictions,
    )


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("provider_unavailable", "No se pudo contactar"),
        ("timeout", "superó el tiempo"),
        ("incomplete_generation", "No se obtuvo una respuesta completa"),
        ("unsupported_direct_mode", "no admite el modo directo"),
        ("protocol_error", "incumplió el contrato"),
        ("model_not_found", "no expuso el modelo"),
        ("\x1b[31mprivate", "no se estableció una causa específica"),
    ],
)
def test_failure_explanation_is_bounded_and_does_not_commit(
    kind: str, expected: str
) -> None:
    provider = Provider(
        failure={
            "failure_kind": kind,
            "ollama.done_reason": "\x1b[31m" + "x" * 2000,
            "ollama.eval_count": 10**1000,
        }
    )
    conversation, _ = make_session(provider)
    output = run_cli(conversation, "hola", "/diagnostico")
    failure_lines = [line for line in output if line.startswith("Chat falló:")]
    assert len(failure_lines) == 1
    assert expected in failure_lines[0]
    assert "historial sin cambios" in failure_lines[0]
    assert "private" not in failure_lines[0]
    assert "\x1b" not in failure_lines[0] and "x" * 50 not in failure_lines[0]
    assert len(failure_lines[0]) < 200
    assert conversation.messages == () and conversation.revision == 0
    assert len(provider.requests) == 1
    assert "Turnos activos: 0/8" in diagnostic_lines(output)


def test_failure_then_manual_success_and_diagnostic_recovery() -> None:
    provider = Provider(
        failure={
            "failure_kind": "incomplete_generation",
            "ollama.done_reason": "length",
            "ollama.eval_count": 256,
        }
    )
    conversation, _ = make_session(provider)
    output = run_cli(conversation, "fallo", "/diagnostico")
    assert any(
        "fin=length" in line and "tokens generados=256" in line for line in output
    )
    assert "Revisión: 0; generación: 0" in diagnostic_lines(output)
    provider.failure = None
    output = run_cli(conversation, "nuevo intento", "/diagnostico")
    assert len(provider.requests) == 2
    assert conversation.messages[0].content == "nuevo intento"
    assert "Revisión: 1; generación: 0" in diagnostic_lines(output)


def test_limit_and_command_compatibility_keep_diagnostics_read_only() -> None:
    conversation, provider = make_session()
    output = run_cli(
        conversation,
        "/diagnostico",
        "x" * 2001,
        "/continuidad activar",
        "/diagnostico",
        "/reiniciar",
        "/diagnostico",
        "/unknown",
    )
    assert any("Límite de chat:" in line for line in output)
    assert len(provider.requests) == 1
    assert provider.requests[0].messages[-1].content == "/unknown"
    assert (
        output.count("Diagnóstico de conversación (sin comprobar disponibilidad):") == 3
    )
    assert conversation.diagnostic_snapshot().active_turns == 1
    assert not conversation.continuity_enabled and conversation.generation == 1
