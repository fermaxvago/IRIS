"""Current terminal entry point for IRIS."""

from __future__ import annotations

import argparse
import sys
import unicodedata
from collections.abc import Callable, Mapping, Sequence

from iris.core.request import Request
from iris.dispatch import CommandDispatcher, Dispatcher
from iris.intelligence import (
    MAX_CONTEXT_CHARACTERS,
    MAX_PREVIOUS_TURNS,
    ContextBindingError,
    ConversationBindingError,
    ConversationBusyError,
    ConversationDiscoveryContractError,
    ConversationDiscoveryError,
    ConversationLimitError,
    ConversationRouteBinder,
    ConversationRouteContractError,
    ConversationSession,
    IntelligenceRouteStatus,
    IntelligenceRuntime,
    ModelNotFoundError,
    ModelUnavailableError,
    ProviderContractError,
    ProviderNotFoundError,
    ProviderRegistry,
    UnsupportedConversationError,
)
from iris.intelligence.providers import OllamaOperationalError, OllamaProvider
from iris.intelligence.resource_intent import (
    ResourceIntent,
    recognize_resource_intent,
)
from iris.intelligence.system_awareness import (
    ConversationalSystemAwareness,
    SystemAwarenessError,
)
from iris.router import DeterministicRouter
from iris.router.contracts import Router
from iris.router.models import RouteDecision


def main(
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    router: Router[Request, RouteDecision] | None = None,
    dispatcher: Dispatcher | None = None,
    chat_session: ConversationSession | None = None,
    system_awareness: ConversationalSystemAwareness | None = None,
) -> None:
    """Run the minimal interactive CLI.

    Input/output callables are injectable so the real command loop can be
    verified without replacing the interface or adding a CLI framework.
    """

    active_router = router or DeterministicRouter()
    active_dispatcher = dispatcher or CommandDispatcher()

    output_fn("IRIS v0.1 iniciando...")
    output_fn("Hola Fernando. Soy IRIS.")
    output_fn("Modo: local")
    output_fn("Escribe 'estado', 'ayuda' o 'salir'.")

    if chat_session is not None:
        _chat_loop(chat_session, input_fn, output_fn, system_awareness)

    while True:
        try:
            user_input = input_fn("IRIS> ")
        except (EOFError, KeyboardInterrupt):
            output_fn("\nIRIS apagándose.")
            break

        request = Request(content=user_input, source="cli")
        decision = active_router.route(request)
        result = active_dispatcher.dispatch(request, decision)
        output_fn(result.output)

        if result.exit_requested:
            break


def _chat_loop(
    session: ConversationSession,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
    system_awareness: ConversationalSystemAwareness | None = None,
) -> None:
    output_fn(
        f"Chat local: {session.provider_id}/{session.model_id}. "
        "Usa /reiniciar para borrar la sesión o /salir para volver a IRIS."
    )
    while True:
        try:
            content = input_fn("IRIS chat> ")
        except (EOFError, KeyboardInterrupt):
            output_fn("Chat interrumpido. Volviendo a IRIS.")
            return
        command = content.strip()
        if command == "/salir":
            output_fn("Saliendo del chat. Volviendo a IRIS.")
            return
        if command == "/diagnostico":
            try:
                snapshot = session.diagnostic_snapshot()
            except ConversationBusyError:
                output_fn("Diagnóstico no disponible: la conversación está ocupada.")
                continue
            output_fn("Diagnóstico de conversación (sin comprobar disponibilidad):")
            output_fn(
                "Proveedor vinculado: "
                + _safe_terminal_text(snapshot.provider_id, allow_newline=False)
            )
            output_fn(
                "Modelo vinculado: "
                + _safe_terminal_text(snapshot.model_id, allow_newline=False)
            )
            output_fn(f"Turnos activos: {snapshot.active_turns}/{MAX_PREVIOUS_TURNS}")
            output_fn(
                f"Caracteres activos: {snapshot.active_characters}/"
                f"{MAX_CONTEXT_CHARACTERS} (solo mensajes retenidos; no son tokens)"
            )
            state = "activada" if snapshot.continuity_enabled else "desactivada"
            output_fn(f"Continuidad: {state}")
            output_fn(
                f"Revisión: {snapshot.revision}; generación: {snapshot.generation}"
            )
            output_fn("Disponibilidad actual del proveedor/modelo: no comprobada.")
            continue
        if command == "/reiniciar":
            session.reset()
            output_fn("Conversación temporal reiniciada.")
            output_fn("Continuidad desactivada.")
            continue
        if command == "/continuidad estado":
            state = "activada" if session.continuity_enabled else "desactivada"
            output_fn(f"Continuidad {state}; {session.completed_turns} turnos activos.")
            continue
        if command == "/continuidad activar":
            session.set_continuity(True)
            output_fn(
                "Continuidad activada. Los turnos antiguos podrán retirarse del "
                "contexto activo tras una respuesta válida; no se resumirán ni conservarán."
            )
            continue
        if command == "/continuidad desactivar":
            session.set_continuity(False)
            output_fn(
                "Continuidad desactivada. Los turnos ya retirados no se recuperan."
            )
            continue
        if command == "/continuidad" or command.startswith("/continuidad "):
            output_fn("Uso: /continuidad estado|activar|desactivar")
            continue
        parts = command.split(maxsplit=1)
        if parts and parts[0] == "/recursos":
            if len(parts) == 1 or not parts[1].strip():
                output_fn("Uso: /recursos <pregunta sobre CPU y RAM>")
                continue
            if _resource_consultation(
                session, parts[1], input_fn, output_fn, system_awareness
            ):
                return
            continue
        intent = (
            recognize_resource_intent(content)
            if not command.startswith("/")
            else ResourceIntent.NO_MATCH
        )
        if intent is ResourceIntent.AMBIGUOUS:
            output_fn(
                "¿Quieres consultar el estado local de CPU/RAM o solo una explicación?"
            )
            try:
                clarification = input_fn("¿Consultar recursos locales? [sí/no]> ")
            except (EOFError, KeyboardInterrupt):
                output_fn("Consulta cancelada. Volviendo a IRIS.")
                return
            if clarification.strip().casefold() not in ("si", "sí"):
                output_fn("No se consultaron recursos; historial sin cambios.")
                continue
            intent = ResourceIntent.MATCH
        if intent is ResourceIntent.MATCH:
            output_fn("IRIS puede tomar una lectura local de CPU y RAM.")
            try:
                approval = input_fn(
                    "¿Autorizas observar estos recursos ahora? [sí/no]> "
                )
            except (EOFError, KeyboardInterrupt):
                output_fn("Observación no autorizada. Volviendo a IRIS.")
                return
            if approval.strip().casefold() not in ("si", "sí"):
                output_fn("Observación no autorizada; historial sin cambios.")
                continue
            if _resource_consultation(
                session, content, input_fn, output_fn, system_awareness
            ):
                return
            continue
        try:
            if not _ensure_conversation_window(session, content, input_fn, output_fn):
                continue
            result = session.send(content)
        except ConversationLimitError as exc:
            output_fn(f"Límite de chat: {exc}")
            continue
        except (
            ModelNotFoundError,
            ModelUnavailableError,
            ProviderNotFoundError,
            UnsupportedConversationError,
            ProviderContractError,
            OllamaOperationalError,
        ) as exc:
            output_fn(f"Chat no disponible: {_safe_terminal_text(str(exc))}")
            continue
        except ValueError as exc:
            output_fn(f"Mensaje inválido: {_safe_terminal_text(str(exc))}")
            continue
        except KeyboardInterrupt:
            output_fn("Inferencia interrumpida; historial sin cambios.")
            continue
        if not result.success:
            output_fn(
                f"Chat falló: {_failure_explanation(result.metadata)}"
                f"{_generation_diagnostic(result.metadata)}; "
                "historial sin cambios (no se confirmó un turno)."
            )
            continue
        if result.output is None:
            raise ProviderContractError("successful chat result lacks output")
        output_fn(_safe_terminal_text(result.output))
        _report_rollover(session, output_fn)


def _resource_consultation(
    session: ConversationSession,
    question: str,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
    system_awareness: ConversationalSystemAwareness | None,
) -> bool:
    """Run the existing one-capture, one-disclosure CLI flow for either entry.

    Return true only when an interrupted disclosure should leave chat mode.
    The caller owns any preliminary observation confirmation.
    """

    if not _ensure_conversation_window(session, question, input_fn, output_fn):
        return False
    awareness = system_awareness or ConversationalSystemAwareness()
    try:
        consultation = awareness.prepare(session, question)
    except (
        SystemAwarenessError,
        ContextBindingError,
        ConversationLimitError,
        ValueError,
    ) as exc:
        output_fn(
            f"Consulta de recursos no disponible: {_safe_terminal_text(str(exc))}"
        )
        return False
    observation = consultation.observation
    output_fn("IRIS — Observación local (system.status):")
    output_fn(f"CPU: {_format_resource(observation.cpu_percent, '%')}")
    output_fn(f"RAM utilizada: {_format_resource(observation.ram_used_gb, 'GiB')}")
    output_fn(f"RAM total: {_format_resource(observation.ram_total_gb, 'GiB')}")
    output_fn(f"Captura (UTC): {observation.captured_at.isoformat()}")
    if consultation.proposal is None:
        missing = (
            name
            for name in ("cpu_percent", "ram_used_gb", "ram_total_gb")
            if getattr(observation, name) is None
        )
        output_fn(
            "Medición incompleta o inválida ("
            + ", ".join(missing)
            + "); no se enviará contexto al modelo."
        )
        return False
    proposal = consultation.proposal
    output_fn(
        "Divulgación propuesta al modelo local "
        f"{_safe_terminal_text(proposal.provider_id)}/"
        f"{_safe_terminal_text(proposal.model_id)}:"
    )
    output_fn(
        "Se enviarán estos datos y metadatos exactos como información, no instrucciones:"
    )
    output_fn(_safe_terminal_text(proposal.payload.section))
    try:
        answer = input_fn("¿Autorizas esta divulgación para un turno? [sí/no]> ")
    except (EOFError, KeyboardInterrupt):
        output_fn("Divulgación no autorizada. Volviendo a IRIS.")
        return True
    if answer.strip().casefold() not in ("si", "sí"):
        output_fn("Divulgación no autorizada; historial sin cambios.")
        return False
    try:
        result = awareness.send_approved(session, proposal)
    except ContextBindingError:
        output_fn(
            "Divulgación no válida: la propuesta o aprobación ya no corresponde "
            "al turno; la observación local se mostró, pero no se confirmó un turno."
        )
        return False
    except (
        ConversationLimitError,
        ModelNotFoundError,
        ModelUnavailableError,
        ProviderNotFoundError,
        UnsupportedConversationError,
        ProviderContractError,
        OllamaOperationalError,
        ValueError,
    ) as exc:
        output_fn(
            f"Explicación no disponible: {_safe_terminal_text(str(exc))}; historial sin cambios."
        )
        return False
    except KeyboardInterrupt:
        output_fn("Inferencia interrumpida; historial sin cambios.")
        return False
    if not result.success:
        output_fn(
            f"Modelo falló: {_failure_explanation(result.metadata)}"
            f"{_generation_diagnostic(result.metadata)}; "
            "historial sin cambios (no se confirmó un turno)."
        )
        return False
    if result.output is None:
        raise ProviderContractError("successful chat result lacks output")
    output_fn(_safe_terminal_text(result.output))
    _report_rollover(session, output_fn)
    return False


def _ensure_conversation_window(
    session: ConversationSession,
    content: str,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
) -> bool:
    """Offer one session-policy choice before inference or resource capture."""

    try:
        session.prepare_window(content)
        return True
    except ConversationLimitError as exc:
        if not session.can_rollover(content):
            output_fn(f"Límite de chat: {exc}")
            return False
        output_fn(
            "La ventana activa está llena. Continuar retirará turnos completos "
            "antiguos solo después de una respuesta válida; no se conservarán."
        )
        try:
            answer = input_fn("¿Activar continuidad para esta sesión? [sí/no]> ")
        except (EOFError, KeyboardInterrupt):
            output_fn("Continuidad no autorizada; historial sin cambios.")
            return False
        if answer.strip().casefold() not in ("si", "sí"):
            output_fn("Continuidad no autorizada; historial sin cambios.")
            return False
        session.set_continuity(True)
        output_fn("Continuidad activada para esta sesión temporal.")
        return True
    except ValueError as exc:
        output_fn(f"Mensaje inválido: {_safe_terminal_text(str(exc))}")
        return False


def _report_rollover(
    session: ConversationSession, output_fn: Callable[[str], None]
) -> None:
    if session.last_commit_evictions:
        count = session.last_commit_evictions
        action = (
            "se retiró 1 turno antiguo"
            if count == 1
            else f"se retiraron {count} turnos antiguos"
        )
        output_fn(f"Contexto actualizado: {action} de la ventana activa.")


def _safe_terminal_text(
    value: str, *, encoding: str | None = None, allow_newline: bool = True
) -> str:
    """Escape control and formatting characters in untrusted model text."""

    safe = "".join(
        character
        if (character == "\n" and allow_newline)
        or not unicodedata.category(character).startswith("C")
        else ascii(character)[1:-1]
        for character in value
    )
    # Windows terminals may use a legacy code page. Preserve the transcript and
    # render unencodable characters visibly instead of crashing the CLI.
    codec = encoding or sys.stdout.encoding or "utf-8"
    return safe.encode(codec, errors="backslashreplace").decode(codec)


def _format_resource(value: float | None, unit: str) -> str:
    return "No disponible" if value is None else f"{value} {unit}"


def _generation_diagnostic(metadata: Mapping[str, object]) -> str:
    """Display only validated operational facts, never prompts or reasoning."""

    details: list[str] = []
    reason = metadata.get("ollama.done_reason")
    if isinstance(reason, str) and reason in ("stop", "length"):
        details.append(f"fin={reason}")
    for key, label in (
        ("ollama.eval_count", "tokens generados"),
        ("ollama.prompt_eval_count", "tokens de entrada"),
    ):
        value = metadata.get(key)
        if (
            isinstance(value, int)
            and not isinstance(value, bool)
            and 0 <= value <= 1_000_000_000
        ):
            details.append(f"{label}={value}")
    return " [" + ", ".join(details) + "]" if details else ""


def _failure_explanation(metadata: Mapping[str, object]) -> str:
    """Explain only known failure categories; metadata is not trusted prose."""

    kind = metadata.get("failure_kind")
    explanations = {
        "provider_unavailable": "No se pudo contactar al proveedor",
        "timeout": "La operación superó el tiempo de espera",
        "incomplete_generation": "No se obtuvo una respuesta completa y utilizable",
        "unsupported_direct_mode": "El modelo no admite el modo directo solicitado",
        "protocol_error": "La respuesta del proveedor incumplió el contrato esperado",
        "model_not_found": "El proveedor no expuso el modelo seleccionado",
    }
    return (
        explanations.get(
            kind, "La operación falló; no se estableció una causa específica"
        )
        if isinstance(kind, str)
        else "La operación falló; no se estableció una causa específica"
    )


def entrypoint(
    argv: Sequence[str] | None = None,
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    """Parse an explicit chat invocation while preserving bare legacy IRIS."""

    arguments = sys.argv[1:] if argv is None else argv
    if not arguments:
        main(input_fn=input_fn, output_fn=output_fn)
        return
    parser = argparse.ArgumentParser(prog="iris")
    commands = parser.add_subparsers(dest="command", required=True)
    chat = commands.add_parser("chat", help="conversación textual local con Ollama")
    selection = chat.add_mutually_exclusive_group(required=True)
    selection.add_argument("--model", help="modelo Ollama instalado")
    selection.add_argument(
        "--select", action="store_true", help="recomendar un modelo local"
    )
    chat.add_argument(
        "--direct",
        action="store_true",
        help="generación directa si el modelo la admite",
    )
    parsed = parser.parse_args(arguments)
    if parsed.command == "chat":
        provider = (
            OllamaProvider(direct_generation=True)
            if parsed.direct
            else OllamaProvider()
        )
        registry = ProviderRegistry([provider])
        if parsed.select:
            session = _select_chat_session(registry, input_fn, output_fn)
            if session is not None and parsed.direct:
                try:
                    provider.verify_direct_model(session.model_id)
                except OllamaOperationalError as exc:
                    output_fn(
                        f"Modo directo no disponible: {_safe_terminal_text(str(exc))}"
                    )
                    return
            main(input_fn=input_fn, output_fn=output_fn, chat_session=session)
            return
        runtime = IntelligenceRuntime(registry)
        if parsed.direct:
            try:
                provider.verify_direct_model(parsed.model)
            except OllamaOperationalError as exc:
                output_fn(
                    f"Modo directo no disponible: {_safe_terminal_text(str(exc))}"
                )
                return
        main(
            input_fn=input_fn,
            output_fn=output_fn,
            chat_session=ConversationSession(
                runtime,
                provider_id=provider.provider_id,
                model_id=parsed.model,
            ),
        )


def _select_chat_session(
    registry: ProviderRegistry,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
) -> ConversationSession | None:
    """Recommend, confirm and revalidate before creating a temporary chat."""

    binder = ConversationRouteBinder(registry)
    try:
        proposal = binder.propose()
    except (
        ConversationDiscoveryError,
        ConversationDiscoveryContractError,
        ConversationRouteContractError,
    ) as exc:
        output_fn(f"Selección no disponible: {_safe_terminal_text(str(exc))}")
        return None
    output_fn(_safe_terminal_text(proposal.explanation))
    if proposal.route.status is IntelligenceRouteStatus.UNSATISFIED:
        output_fn("No hay un modelo local compatible; no se creó una sesión.")
        return None
    identity = proposal.selected_identity
    if identity is None:
        raise RuntimeError("satisfied route lacks a selected identity")
    while True:
        try:
            answer = input_fn(
                "¿Usar "
                f"{_safe_terminal_text(identity[0])}/"
                f"{_safe_terminal_text(identity[1])} para un chat temporal? [si/no]> "
            )
        except (EOFError, KeyboardInterrupt):
            output_fn("Selección cancelada; no se creó una sesión.")
            return None
        if answer.strip().lower() == "no":
            output_fn("Selección cancelada; no se creó una sesión.")
            return None
        if answer.strip().lower() == "si":
            break
        output_fn("Responde 'si' o 'no'.")
    try:
        session = binder.bind(proposal)
    except (
        ConversationDiscoveryError,
        ConversationDiscoveryContractError,
        ConversationBindingError,
    ) as exc:
        output_fn(f"Revalidación falló: {_safe_terminal_text(str(exc))}")
        return None
    output_fn(
        f"Modelo confirmado: {_safe_terminal_text(session.provider_id)}/"
        f"{_safe_terminal_text(session.model_id)}. "
        "El chat comenzará al enviar un mensaje."
    )
    return session


if __name__ == "__main__":
    entrypoint()
