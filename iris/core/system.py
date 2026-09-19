"""Portable collection and formatting of basic host system information."""

from __future__ import annotations

import os
import platform
import socket
import sys
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import PureWindowsPath
from typing import TypeVar, TypedDict

import psutil

_BYTES_PER_GIB = 1024**3
_T = TypeVar("_T")
_RECOVERABLE_METRIC_ERRORS = (OSError, NotImplementedError, psutil.Error)


class SystemInfo(TypedDict):
    """Snapshot returned by :func:`get_system_info`.

    Resource metrics are optional because operating systems, containers and
    permissions do not expose every metric consistently.
    """

    device_name: str
    operating_system: str
    operating_system_version: str
    python_version: str
    cpu_percent: float | None
    ram_total_gb: float | None
    ram_used_gb: float | None
    ram_percent: float | None
    disk_path: str
    disk_total_gb: float | None
    disk_used_gb: float | None
    disk_percent: float | None
    battery_percent: float | None
    plugged_in: bool | None
    timestamp: str


def get_system_disk_path(
    system_name: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    executable: str | None = None,
) -> str:
    """Return the filesystem root that contains the running IRIS process.

    Windows is the primary target. The injectable arguments keep platform
    selection deterministic in tests without introducing an adapter hierarchy.
    """

    current_system = system_name or platform.system()
    environment = os.environ if environ is None else environ

    if current_system == "Windows":
        configured_drive = environment.get("SystemDrive")
        if configured_drive:
            return str(PureWindowsPath(configured_drive + "\\"))

        executable_path = executable or sys.executable
        executable_anchor = PureWindowsPath(executable_path).anchor
        return executable_anchor or "\\"

    return os.path.abspath(os.sep)


def _read_metric(reader: Callable[[], _T]) -> _T | None:
    """Return one metric, degrading only known platform/permission failures."""

    try:
        return reader()
    except _RECOVERABLE_METRIC_ERRORS:
        return None


def _gibibytes(byte_count: int) -> float:
    return round(byte_count / _BYTES_PER_GIB, 2)


def get_system_info() -> SystemInfo:
    """Collect a best-effort snapshot without coupling the core to one OS."""

    operating_system = _read_metric(platform.system) or "No disponible"
    disk_path = get_system_disk_path(operating_system)
    memory = _read_metric(psutil.virtual_memory)
    disk = _read_metric(lambda: psutil.disk_usage(disk_path))
    battery = _read_metric(psutil.sensors_battery)
    cpu_percent = _read_metric(lambda: psutil.cpu_percent(interval=0.1))

    return {
        "device_name": _read_metric(socket.gethostname) or "No disponible",
        "operating_system": operating_system,
        "operating_system_version": _read_metric(platform.version)
        or "No disponible",
        "python_version": _read_metric(platform.python_version) or "No disponible",
        "cpu_percent": cpu_percent,
        "ram_total_gb": _gibibytes(memory.total) if memory else None,
        "ram_used_gb": _gibibytes(memory.used) if memory else None,
        "ram_percent": memory.percent if memory else None,
        "disk_path": disk_path,
        "disk_total_gb": _gibibytes(disk.total) if disk else None,
        "disk_used_gb": _gibibytes(disk.used) if disk else None,
        "disk_percent": disk.percent if disk else None,
        "battery_percent": battery.percent if battery else None,
        "plugged_in": battery.power_plugged if battery else None,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


def _format_usage(
    used_gb: float | None,
    total_gb: float | None,
    percent: float | None,
) -> str:
    if used_gb is None or total_gb is None or percent is None:
        return "No disponible"
    return f"{used_gb} GB / {total_gb} GB ({percent}%)"


def format_system_info(info: SystemInfo) -> str:
    """Render a system snapshot for the current Spanish terminal interface."""

    cpu = (
        "No disponible"
        if info["cpu_percent"] is None
        else f'{info["cpu_percent"]}%'
    )
    battery = "No disponible"

    if info["battery_percent"] is not None:
        if info["plugged_in"] is None:
            battery = f'{info["battery_percent"]}%'
        else:
            charging = "conectada" if info["plugged_in"] else "en batería"
            battery = f'{info["battery_percent"]}% ({charging})'

    memory = _format_usage(
        info["ram_used_gb"], info["ram_total_gb"], info["ram_percent"]
    )
    disk = _format_usage(
        info["disk_used_gb"], info["disk_total_gb"], info["disk_percent"]
    )

    return (
        f'Dispositivo: {info["device_name"]}\n'
        f'Sistema: {info["operating_system"]} {info["operating_system_version"]}\n'
        f'Python: {info["python_version"]}\n'
        f"CPU: {cpu}\n"
        f"RAM: {memory}\n"
        f'Disco ({info["disk_path"]}): {disk}\n'
        f"Batería: {battery}\n"
        f'Hora: {info["timestamp"]}'
    )
