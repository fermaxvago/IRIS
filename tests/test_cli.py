from __future__ import annotations

import iris.__main__ as cli
from iris.core import system


def _input_sequence(*commands: str):
    command_iterator = iter(commands)
    return lambda prompt: next(command_iterator)


def test_cli_supports_current_commands(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "get_system_info",
        lambda: {
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
    )

    rendered = "\n".join(output)
    assert "Dispositivo: Test-PC" in rendered
    assert "Comandos disponibles: estado, ayuda, salir" in rendered
    assert "Todavía no sé hacer eso" in rendered
    assert output[-1] == "IRIS apagándose."


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
