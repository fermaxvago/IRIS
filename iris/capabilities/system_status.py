"""System information exposed as the first executable IRIS tool."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from iris.capabilities.models import (
    CapabilityDescriptor,
    CapabilityInput,
    CapabilityKind,
    CapabilityResult,
)
from iris.core.system import SystemInfo, format_system_info, get_system_info

SYSTEM_STATUS_CAPABILITY_ID = "system.status"

SystemInfoProvider = Callable[[], SystemInfo]
SystemInfoFormatter = Callable[[SystemInfo], str]


@dataclass(frozen=True, slots=True)
class SystemResourceObservation:
    """One CPU/RAM reading; the existing ``_gb`` fields report GiB."""

    cpu_percent: float | None
    ram_used_gb: float | None
    ram_total_gb: float | None
    captured_at: datetime
    invalid_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.captured_at, datetime):
            raise ValueError("captured_at must be timezone-aware UTC")
        offset = self.captured_at.utcoffset()
        if offset is None or offset.total_seconds() != 0:
            raise ValueError("captured_at must be timezone-aware UTC")
        for name in ("cpu_percent", "ram_used_gb", "ram_total_gb"):
            value = getattr(self, name)
            if value is not None and (
                type(value) is not float or not math.isfinite(value)
            ):
                raise ValueError(f"{name} must be finite float or None")
        if self.cpu_percent is not None and not 0 <= self.cpu_percent <= 100:
            raise ValueError("cpu_percent must be between 0 and 100")
        if self.ram_used_gb is not None and self.ram_used_gb < 0:
            raise ValueError("ram_used_gb must be nonnegative")
        if self.ram_total_gb is not None and self.ram_total_gb <= 0:
            raise ValueError("ram_total_gb must be positive")
        if not isinstance(self.invalid_fields, tuple) or any(
            name not in ("cpu_percent", "ram_used_gb", "ram_total_gb")
            for name in self.invalid_fields
        ):
            raise ValueError("invalid_fields must name resource measurements")

    @property
    def complete(self) -> bool:
        return (
            self.cpu_percent is not None
            and self.ram_used_gb is not None
            and self.ram_total_gb is not None
            and self.ram_used_gb <= self.ram_total_gb + 0.01
            and not self.invalid_fields
        )


def _metric(info: SystemInfo, name: str) -> tuple[float | None, bool]:
    value = info.get(name)
    if value is None:
        return None, False
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None, True
    try:
        number = float(value)
    except OverflowError:
        return None, True
    if not math.isfinite(number):
        return None, True
    if (
        (name == "cpu_percent" and not 0 <= number <= 100)
        or (name == "ram_used_gb" and number < 0)
        or (name == "ram_total_gb" and number <= 0)
    ):
        return None, True
    return number, False


class SystemStatusTool:
    """Read and format the current best-effort system snapshot."""

    _descriptor = CapabilityDescriptor(
        capability_id=SYSTEM_STATUS_CAPABILITY_ID,
        description="Collect and format a best-effort host system snapshot.",
        kind=CapabilityKind.TOOL,
        metadata={"category": "system", "effect": "read"},
    )

    def __init__(
        self,
        *,
        system_info_provider: SystemInfoProvider = get_system_info,
        system_info_formatter: SystemInfoFormatter = format_system_info,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._system_info_provider = system_info_provider
        self._system_info_formatter = system_info_formatter
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def descriptor(self) -> CapabilityDescriptor:
        """Return the stable ``system.status`` identity."""

        return self._descriptor

    def execute(self, capability_input: CapabilityInput) -> CapabilityResult:
        """Collect system information and return its current CLI rendering."""

        mode = capability_input.payload.get("output_mode", "text")
        if mode not in ("text", "structured") or type(mode) is not str:
            raise ValueError("unsupported system.status output_mode")
        info = self._system_info_provider()
        if mode == "structured":
            if not isinstance(info, Mapping):
                raise ValueError("system.status returned malformed system data")
            captured_at = self._clock()
            names = ("cpu_percent", "ram_used_gb", "ram_total_gb")
            metrics = {name: _metric(info, name) for name in names}
            used, total = metrics["ram_used_gb"][0], metrics["ram_total_gb"][0]
            invalid = [name for name in names if metrics[name][1]]
            # get_system_info rounds both GiB readings to two decimals.
            if used is not None and total is not None and used > total + 0.01:
                invalid.append("ram_used_gb")
                metrics["ram_used_gb"] = (None, True)
            return CapabilityResult.succeeded(
                SYSTEM_STATUS_CAPABILITY_ID,
                output=SystemResourceObservation(
                    cpu_percent=metrics["cpu_percent"][0],
                    ram_used_gb=metrics["ram_used_gb"][0],
                    ram_total_gb=metrics["ram_total_gb"][0],
                    captured_at=captured_at,
                    invalid_fields=tuple(invalid),
                ),
            )
        output = self._system_info_formatter(info)
        return CapabilityResult.succeeded(
            SYSTEM_STATUS_CAPABILITY_ID,
            output=output,
        )
