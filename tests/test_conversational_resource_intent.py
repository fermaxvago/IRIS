"""WP068: conservative Spanish recognition and two separate CLI approvals."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest

import iris.__main__ as cli
from iris.capabilities import CapabilityRegistry, CapabilityRuntime, SystemStatusTool
from iris.core.system import SystemInfo
from iris.intelligence import (
    ConversationContextBinder,
    ConversationRequest,
    ConversationSession,
    IntelligenceResult,
    IntelligenceRuntime,
    ModelCapability,
    ModelDescriptor,
    ModelLocation,
    ProviderRegistry,
)
from iris.intelligence.resource_intent import (
    ResourceIntent,
    recognize_resource_intent,
)
from iris.intelligence.system_awareness import ConversationalSystemAwareness

NOW = datetime(2026, 10, 22, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    "message",
    [
        "¿Cuánta RAM estoy usando?",
        "Muéstrame el uso de CPU",
        "IRIS, revisa mis recursos",
        "¿Puedes comprobar si tengo la RAM llena?",
        "¿Cómo anda mi memoria RAM?",
        "   ¿CUANTA   ram estoy USANDO?  ",
        "Checa mi CPU, por favor.",
    ],
)
def test_recognizes_only_bounded_affirmative_requests(message: str) -> None:
    assert recognize_resource_intent(message) is ResourceIntent.MATCH


@pytest.mark.parametrize(
    "message",
    [
        "¿Qué es la RAM?",
        "Mi computadora está lenta",
        "No revises mi RAM",
        "¿Qué pasaría si mi RAM estuviera llena?",
        "Mi profesor dijo: “revisa tu RAM”",
        "¿Cuánta memoria necesita otro dispositivo?",
        "Libera la RAM y cierra procesos",
        "Revisa mi RAM y cierra procesos",
        "¿Puedes revisar mi computadora?",
        "Revisa la RAM de Ana",
        "Muéstrame CPU de un servidor",
        "Revisa mi RAM y envía un reporte",
        "Hola, ¿qué tal?",
        "RAM",
        "CPU",
        "¿Podrías explicarme qué es la memoria RAM?",
        "'Revisa mi RAM'",
    ],
)
def test_exclusions_abstain(message: str) -> None:
    assert recognize_resource_intent(message) is ResourceIntent.NO_MATCH


def test_only_explicit_bounded_choice_is_ambiguous() -> None:
    assert (
        recognize_resource_intent("¿Puedes revisar mi RAM o explicarme qué es?")
        is ResourceIntent.AMBIGUOUS
    )
    assert (
        recognize_resource_intent("Revisa mi RAM o cierra procesos")
        is ResourceIntent.NO_MATCH
    )
    assert recognize_resource_intent("Mi equipo va lento") is ResourceIntent.NO_MATCH
    assert recognize_resource_intent("Revisa mi CPU y RAM") is ResourceIntent.MATCH


def test_recognizer_has_no_runtime_dependencies() -> None:
    import iris.intelligence.resource_intent as module

    assert not any(
        name in vars(module)
        for name in ("OllamaProvider", "CapabilityRuntime", "ConversationSession")
    )
    with pytest.raises(TypeError):
        recognize_resource_intent(None)  # type: ignore[arg-type]


@dataclass
class Provider:
    provider_id: str = "local"
    fail: bool = False
    ordinary: list[ConversationRequest] = field(default_factory=list)
    contextual: list[ConversationRequest] = field(default_factory=list)

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
        raise AssertionError("legacy inference is not part of this test")

    def chat(self, request: ConversationRequest) -> IntelligenceResult:
        self.ordinary.append(request)
        return IntelligenceResult.succeeded(
            request, provider_id=self.provider_id, output="respuesta"
        )

    def chat_with_context(self, request: ConversationRequest) -> IntelligenceResult:
        self.contextual.append(request)
        if self.fail:
            return IntelligenceResult.failed(
                request, provider_id=self.provider_id, diagnostic="offline"
            )
        return IntelligenceResult.succeeded(
            request, provider_id=self.provider_id, output="explicación"
        )


@dataclass
class Harness:
    session: ConversationSession
    provider: Provider
    awareness: ConversationalSystemAwareness
    captures: list[int]


def harness(*, incomplete: bool = False) -> Harness:
    captures: list[int] = []

    def capture() -> SystemInfo:
        captures.append(1)
        return {
            "cpu_percent": 27.0,
            "ram_used_gb": None if incomplete else 21.4,
            "ram_total_gb": 31.7,
        }

    provider = Provider()
    session = ConversationSession(
        IntelligenceRuntime(ProviderRegistry([provider])),
        provider_id=provider.provider_id,
        model_id="modelo",
    )
    awareness = ConversationalSystemAwareness(
        capability_runtime=CapabilityRuntime(
            CapabilityRegistry(
                [SystemStatusTool(system_info_provider=capture, clock=lambda: NOW)]
            )
        ),
        context_binder=ConversationContextBinder(clock=lambda: NOW),
        clock=lambda: NOW,
    )
    return Harness(session, provider, awareness, captures)


def drive(h: Harness, *answers: str) -> tuple[list[str], list[str]]:
    pending = iter((*answers, "/salir", "salir"))
    output: list[str] = []
    prompts: list[str] = []

    def receive(prompt: str) -> str:
        prompts.append(prompt)
        return next(pending)

    cli.main(
        input_fn=receive,
        output_fn=output.append,
        chat_session=h.session,
        system_awareness=h.awareness,
    )
    return output, prompts


@pytest.mark.parametrize("decision", ["no", "", "quizá", "yes", "  NO  "])
def test_match_denial_never_captures_or_infers(decision: str) -> None:
    h = harness()
    output, prompts = drive(h, "¿Cuánta RAM estoy usando?", decision)
    assert not h.captures
    assert not h.provider.ordinary and not h.provider.contextual
    assert h.session.messages == ()
    assert sum("observar" in prompt for prompt in prompts) == 1
    assert not any("Divulgación propuesta" in line for line in output)


@pytest.mark.parametrize("failure", [EOFError(), KeyboardInterrupt()])
def test_interrupted_preliminary_approval_fails_closed(failure: BaseException) -> None:
    h = harness()
    output: list[str] = []
    pending = iter(("¿Cuánta RAM estoy usando?",))

    def receive(prompt: str) -> str:
        if "observar" in prompt:
            raise failure
        try:
            return next(pending)
        except StopIteration as exc:
            raise EOFError from exc

    cli.main(
        input_fn=receive,
        output_fn=output.append,
        chat_session=h.session,
        system_awareness=h.awareness,
    )
    assert not h.captures and not h.provider.contextual
    assert h.session.messages == ()
    assert any("Observación no autorizada" in line for line in output)


def test_ambiguous_requires_clarification_then_separate_observation_approval() -> None:
    h = harness()
    output, prompts = drive(
        h, "¿Puedes revisar mi RAM o explicarme qué es?", "sí", "no"
    )
    assert not h.captures and h.session.messages == ()
    assert any("Consultar recursos locales" in prompt for prompt in prompts)
    assert any("observar" in prompt for prompt in prompts)
    assert any("Observación no autorizada" in line for line in output)


@pytest.mark.parametrize("clarification", ["no", "", "quizá"])
def test_ambiguous_without_resolution_has_no_effect(clarification: str) -> None:
    h = harness()
    _, prompts = drive(h, "¿Puedes revisar mi RAM o explicarme qué es?", clarification)
    assert not h.captures and h.session.messages == ()
    assert not any("observar" in prompt for prompt in prompts)
    assert not h.provider.contextual


def test_natural_path_uses_one_capture_exact_preview_and_original_question() -> None:
    h = harness()
    question = "  ¿CUÁNTA RAM estoy usando?  "
    output, prompts = drive(h, question, " SÍ ", "si")
    assert len(h.captures) == 1
    assert len(h.provider.contextual) == 1
    request = h.provider.contextual[0]
    assert request.messages[-1].content == question
    assert request.context is not None
    assert request.context.section in output
    assert "cpu_percent" in request.context.section
    assert "ram_used_gb" in request.context.section
    assert "ram_total_gb" in request.context.section
    assert h.session.completed_turns == 1
    assert all("IRIS_CONTEXT" not in item.content for item in h.session.messages)
    assert sum("observar" in prompt for prompt in prompts) == 1
    assert sum("divulgación" in prompt for prompt in prompts) == 1


def test_explicit_command_uses_same_procedure_without_preliminary_prompt() -> None:
    h = harness()
    output, prompts = drive(h, "/recursos ¿Cómo está mi CPU?", "si")
    assert len(h.captures) == 1 and len(h.provider.contextual) == 1
    assert h.provider.contextual[0].messages[-1].content == "¿Cómo está mi CPU?"
    assert not any("observar" in prompt for prompt in prompts)
    assert any("Divulgación propuesta" in line for line in output)


def test_natural_observation_and_context_consent_are_separate() -> None:
    h = harness()
    output, _ = drive(h, "¿Cómo anda mi memoria RAM?", "sí", "no", "hola")
    assert len(h.captures) == 1
    assert not h.provider.contextual
    assert len(h.provider.ordinary) == 1
    assert h.session.completed_turns == 1
    assert h.session.messages[0].content == "hola"
    assert any("Divulgación no autorizada" in line for line in output)


def test_incomplete_reading_stays_local_only() -> None:
    h = harness(incomplete=True)
    output, _ = drive(h, "Revisa mi RAM", "si")
    assert len(h.captures) == 1
    assert not h.provider.contextual and h.session.messages == ()
    assert any("Medición incompleta" in line for line in output)


def test_provider_failure_preserves_history_and_reading() -> None:
    h = harness()
    h.provider.fail = True
    output, _ = drive(h, "Revisa mi RAM", "sí", "sí")
    assert len(h.captures) == 1 and len(h.provider.contextual) == 1
    assert h.session.messages == ()
    assert any("RAM utilizada: 21.4 GiB" in line for line in output)
    assert any("historial sin cambios" in line for line in output)


def test_each_consultation_requires_fresh_observation_and_disclosure() -> None:
    h = harness()
    _, prompts = drive(
        h,
        "Revisa mi RAM",
        "sí",
        "no",
        "Revisa mi CPU",
        "sí",
        "sí",
    )
    assert len(h.captures) == 2
    assert len(h.provider.contextual) == 1
    assert sum("observar" in prompt for prompt in prompts) == 2
    assert sum("divulgación" in prompt for prompt in prompts) == 2
    assert h.session.completed_turns == 1


@pytest.mark.parametrize("message", ["/checa mi RAM", "estado", "ayuda"])
def test_unknown_slash_and_legacy_words_remain_ordinary_chat(message: str) -> None:
    h = harness()
    _, prompts = drive(h, message)
    assert not h.captures
    assert len(h.provider.ordinary) == 1
    assert h.provider.ordinary[0].messages[-1].content == message
    assert not any("observar" in prompt for prompt in prompts)


def test_reset_and_exit_preserve_existing_lifecycle() -> None:
    h = harness()
    output, _ = drive(h, "hola", "/reiniciar", "/recursos")
    assert not h.captures
    assert h.session.messages == () and h.session.generation == 1
    assert any("Uso: /recursos" in line for line in output)
    assert output[-1].startswith("IRIS apag")


def test_full_session_denied_continuity_does_not_capture_resources() -> None:
    h = harness()
    for index in range(8):
        h.session.send(f"turno {index}")
    before = h.session.messages
    output, prompts = drive(h, "/recursos ¿Cómo está mi RAM?", "no")
    assert not h.captures and not h.provider.contextual
    assert h.session.messages is before
    assert any("Activar continuidad" in prompt for prompt in prompts)
    assert not any("divulgación" in prompt for prompt in prompts)
    assert any("Continuidad no autorizada" in line for line in output)


def test_natural_resource_intent_keeps_observation_and_continuity_distinct() -> None:
    h = harness()
    for index in range(8):
        h.session.send(f"turno {index}")
    output, prompts = drive(h, "Revisa mi RAM", "sí", "no")
    assert not h.captures and not h.provider.contextual
    assert h.session.completed_turns == 8
    assert any("observar" in prompt for prompt in prompts)
    assert any("Activar continuidad" in prompt for prompt in prompts)
    assert any("Continuidad no autorizada" in line for line in output)


def test_resource_consultation_rolls_only_after_contextual_success() -> None:
    h = harness()
    for index in range(8):
        h.session.send(f"turno {index}")
    h.session.set_continuity(True)
    before = h.session.messages
    output, _ = drive(h, "/recursos ¿Cómo está mi RAM?", "sí")
    assert len(h.captures) == 1 and len(h.provider.contextual) == 1
    assert h.provider.contextual[-1].messages[:-1] == before
    assert h.session.completed_turns == 8
    assert h.session.messages[:-2] == before[2:]
    assert h.session.last_commit_evictions == 1
    assert any("retiró 1 turno" in line for line in output)


def test_resource_provider_failure_preserves_full_confirmed_window() -> None:
    h = harness()
    for index in range(8):
        h.session.send(f"turno {index}")
    h.session.set_continuity(True)
    h.provider.fail = True
    before = h.session.messages
    revision = h.session.revision
    output, _ = drive(h, "Revisa mi RAM", "sí", "sí")
    assert len(h.captures) == 1
    assert h.session.messages is before and h.session.revision == revision
    assert not any("Contexto actualizado" in line for line in output)
