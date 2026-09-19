"""Current terminal entry point for IRIS."""

from __future__ import annotations

from collections.abc import Callable

from iris.core.system import format_system_info, get_system_info


def main(
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    """Run the minimal interactive CLI.

    Input/output callables are injectable so the real command loop can be
    verified without replacing the interface or adding a CLI framework.
    """

    output_fn("IRIS v0.1 iniciando...")
    output_fn("Hola Fernando. Soy IRIS.")
    output_fn("Modo: local")
    output_fn("Escribe 'estado', 'ayuda' o 'salir'.")

    while True:
        try:
            user_input = input_fn("IRIS> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            output_fn("\nIRIS apagándose.")
            break

        if user_input == "salir":
            output_fn("IRIS apagándose.")
            break

        if user_input == "ayuda":
            output_fn("Comandos disponibles: estado, ayuda, salir")
            continue

        if user_input == "estado":
            info = get_system_info()
            output_fn(format_system_info(info))
            continue

        output_fn("Todavía no sé hacer eso, pero lo voy a aprender.")


if __name__ == "__main__":
    main()
