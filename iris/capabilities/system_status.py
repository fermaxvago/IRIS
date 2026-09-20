"""System information exposed as the first executable IRIS tool."""

from __future__ import annotations

from collections.abc import Callable

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
    ) -> None:
        self._system_info_provider = system_info_provider
        self._system_info_formatter = system_info_formatter

    @property
    def descriptor(self) -> CapabilityDescriptor:
        """Return the stable ``system.status`` identity."""

        return self._descriptor

    def execute(self, _capability_input: CapabilityInput) -> CapabilityResult:
        """Collect system information and return its current CLI rendering."""

        info = self._system_info_provider()
        output = self._system_info_formatter(info)
        return CapabilityResult.succeeded(
            SYSTEM_STATUS_CAPABILITY_ID,
            output=output,
        )
