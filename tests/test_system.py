from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from iris.core import system


def test_windows_disk_path_prefers_configured_system_drive() -> None:
    path = system.get_system_disk_path(
        "Windows",
        environ={"SystemDrive": "D:"},
        executable=r"C:\Python\python.exe",
    )

    assert path == "D:\\"


def test_windows_disk_path_falls_back_to_executable_drive() -> None:
    path = system.get_system_disk_path(
        "Windows",
        environ={},
        executable=r"E:\Tools\Python\python.exe",
    )

    assert path == "E:\\"


def test_non_windows_disk_path_uses_host_root() -> None:
    assert system.get_system_disk_path("Linux", environ={}) == os.path.abspath(os.sep)


def test_get_system_info_collects_available_metrics(monkeypatch) -> None:
    gib = 1024**3
    monkeypatch.setattr(system, "get_system_disk_path", lambda system_name: "D:\\")
    monkeypatch.setattr(
        system.psutil,
        "virtual_memory",
        lambda: SimpleNamespace(total=32 * gib, used=8 * gib, percent=25.0),
    )
    monkeypatch.setattr(
        system.psutil,
        "disk_usage",
        lambda path: SimpleNamespace(total=100 * gib, used=40 * gib, percent=40.0),
    )
    monkeypatch.setattr(
        system.psutil,
        "sensors_battery",
        lambda: SimpleNamespace(percent=75.0, power_plugged=True),
    )
    monkeypatch.setattr(system.psutil, "cpu_percent", lambda interval: 12.5)

    info = system.get_system_info()

    assert info["disk_path"] == "D:\\"
    assert info["cpu_percent"] == 12.5
    assert info["ram_total_gb"] == 32.0
    assert info["disk_used_gb"] == 40.0
    assert info["battery_percent"] == 75.0
    assert info["plugged_in"] is True


def test_unavailable_metrics_degrade_without_hiding_programming_errors(
    monkeypatch,
) -> None:
    def unavailable(*args, **kwargs):
        raise OSError("metric unavailable")

    monkeypatch.setattr(system.psutil, "virtual_memory", unavailable)
    monkeypatch.setattr(system.psutil, "disk_usage", unavailable)
    monkeypatch.setattr(system.psutil, "sensors_battery", unavailable)
    monkeypatch.setattr(system.psutil, "cpu_percent", unavailable)

    info = system.get_system_info()
    rendered = system.format_system_info(info)

    assert info["cpu_percent"] is None
    assert info["ram_total_gb"] is None
    assert info["disk_total_gb"] is None
    assert info["battery_percent"] is None
    assert "CPU: No disponible" in rendered
    assert "RAM: No disponible" in rendered
    assert "Batería: No disponible" in rendered


def test_metric_reader_does_not_swallow_programming_errors() -> None:
    def broken_metric():
        raise TypeError("programming defect")

    with pytest.raises(TypeError, match="programming defect"):
        system._read_metric(broken_metric)
