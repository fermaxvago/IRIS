"""Current terminal entry point for IRIS."""

from __future__ import annotations

import argparse
import sys
import unicodedata
from collections.abc import Callable, Sequence

from iris.core.request import Request
from iris.dispatch import CommandDispatcher, Dispatcher
from iris.intelligence import (
    ConversationLimitError,
    ConversationSession,
    IntelligenceRuntime,
    ModelNotFoundError,
    ModelUnavailableError,
    ProviderContractError,
    ProviderNotFoundError,
    ProviderRegistry,
    UnsupportedConversationError,
)
from iris.intelligence.providers import OllamaOperationalError, OllamaProvider
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
        _chat_loop(chat_session, input_fn, output_fn)

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
        if command == "/reiniciar":
            session.reset()
            output_fn("Conversación temporal reiniciada.")
            continue
        try:
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
            kind = result.metadata.get("failure_kind", "provider_failure")
            output_fn(
                f"Chat falló ({_safe_terminal_text(str(kind))}); historial sin cambios."
            )
            continue
        if result.output is None:
            raise ProviderContractError("successful chat result lacks output")
        output_fn(_safe_terminal_text(result.output))


def _safe_terminal_text(value: str) -> str:
    """Escape control and formatting characters in untrusted model text."""

    return "".join(
        character
        if character == "\n" or not unicodedata.category(character).startswith("C")
        else ascii(character)[1:-1]
        for character in value
    )


def entrypoint(argv: Sequence[str] | None = None) -> None:
    """Parse an explicit chat invocation while preserving bare legacy IRIS."""

    arguments = sys.argv[1:] if argv is None else argv
    if not arguments:
        main()
        return
    parser = argparse.ArgumentParser(prog="iris")
    commands = parser.add_subparsers(dest="command", required=True)
    chat = commands.add_parser("chat", help="conversación textual local con Ollama")
    chat.add_argument("--model", required=True, help="modelo Ollama instalado")
    parsed = parser.parse_args(arguments)
    if parsed.command == "chat":
        provider = OllamaProvider()
        runtime = IntelligenceRuntime(ProviderRegistry([provider]))
        main(
            chat_session=ConversationSession(
                runtime,
                provider_id=provider.provider_id,
                model_id=parsed.model,
            )
        )


if __name__ == "__main__":
    entrypoint()
