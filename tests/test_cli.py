from __future__ import annotations

import iris.__main__ as cli
from iris.core import system
from iris.core.request import Request
from iris.dispatch import CommandDispatcher
from iris.router import DeterministicRouter, RouteDecision


def _input_sequence(*commands: str):
    command_iterator = iter(commands)
    return lambda prompt: next(command_iterator)


def test_cli_supports_current_commands() -> None:
    dispatcher = CommandDispatcher(
        system_info_provider=lambda: {
            "device_name": "Test-PC",
            "operating_system": "Windows",
            "operating_system_version": "test",
            "python_version": "3.13",
            "cpu_percent": 10.0,
            "ram_total_gb": 32.0,
            "ram_used_gb": 8.0,
            "ram_percent": 25.0,
            "disk_path": "C:\\",
            "disk_total_gb": 1000.0,
            "disk_used_gb": 500.0,
            "disk_percent": 50.0,
            "battery_percent": 80.0,
            "plugged_in": True,
            "timestamp": "2026-09-19T12:00:00",
        },
    )
    output: list[str] = []

    cli.main(
        input_fn=_input_sequence("estado", "ayuda", "desconocido", "salir"),
        output_fn=output.append,
        dispatcher=dispatcher,
    )

    rendered = "\n".join(output)
    assert "Dispositivo: Test-PC" in rendered
    assert "Comandos disponibles: estado, ayuda, salir" in rendered
    assert "Todavía no sé hacer eso" in rendered
    assert output[-1] == "IRIS apagándose."


def test_cli_routes_status_as_a_request_before_dispatch() -> None:
    routed_requests: list[Request] = []
    deterministic_router = DeterministicRouter()

    class RecordingRouter:
        def route(self, request: Request) -> RouteDecision:
            routed_requests.append(request)
            return deterministic_router.route(request)

    dispatcher = CommandDispatcher(
        system_info_provider=lambda: {},
        system_info_formatter=lambda info: "system snapshot",
    )
    output: list[str] = []

    cli.main(
        input_fn=_input_sequence("estado", "salir"),
        output_fn=output.append,
        router=RecordingRouter(),
        dispatcher=dispatcher,
    )

    assert [request.content for request in routed_requests] == ["estado", "salir"]
    assert all(request.source == "cli" for request in routed_requests)
    assert "system snapshot" in output


def test_cli_continues_when_all_system_metrics_are_unavailable(monkeypatch) -> None:
    def unavailable(*args, **kwargs):
        raise OSError("not exposed by host")

    monkeypatch.setattr(system.psutil, "virtual_memory", unavailable)
    monkeypatch.setattr(system.psutil, "disk_usage", unavailable)
    monkeypatch.setattr(system.psutil, "sensors_battery", unavailable)
    monkeypatch.setattr(system.psutil, "cpu_percent", unavailable)
    output: list[str] = []

    cli.main(
        input_fn=_input_sequence("estado", "ayuda", "salir"),
        output_fn=output.append,
    )

    rendered = "\n".join(output)
    assert "CPU: No disponible" in rendered
    assert "Comandos disponibles: estado, ayuda, salir" in rendered
    assert output[-1] == "IRIS apagándose."


def test_cli_handles_end_of_input_cleanly() -> None:
    output: list[str] = []

    def end_of_input(prompt: str) -> str:
        raise EOFError

    cli.main(input_fn=end_of_input, output_fn=output.append)

    assert output[-1] == "\nIRIS apagándose."


def test_cli_handles_keyboard_interrupt_cleanly() -> None:
    output: list[str] = []

    def interrupt_input(prompt: str) -> str:
        raise KeyboardInterrupt

    cli.main(input_fn=interrupt_input, output_fn=output.append)

    assert output[-1] == "\nIRIS apagándose."
