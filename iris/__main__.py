"""Current terminal entry point for IRIS."""

from __future__ import annotations

from collections.abc import Callable

from iris.core.request import Request
from iris.dispatch import CommandDispatcher, Dispatcher
from iris.router import DeterministicRouter
from iris.router.contracts import Router
from iris.router.models import RouteDecision


def main(
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    router: Router[Request, RouteDecision] | None = None,
    dispatcher: Dispatcher | None = None,
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


if __name__ == "__main__":
    main()
