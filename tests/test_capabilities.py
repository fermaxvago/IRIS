from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from iris.capabilities import (
    SYSTEM_STATUS_CAPABILITY_ID,
    CapabilityDescriptor,
    CapabilityInput,
    CapabilityKind,
    CapabilityNotFoundError,
    CapabilityRegistry,
    CapabilityResult,
    CapabilityRuntime,
    DuplicateCapabilityError,
    ExecutionStatus,
    SystemStatusTool,
    Tool,
)


@dataclass
class RecordingTool:
    capability_id: str = "test.echo"
    received_inputs: list[CapabilityInput] = field(default_factory=list)

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            capability_id=self.capability_id,
            description="Echo explicit test input.",
            kind=CapabilityKind.TOOL,
            metadata={"category": "test"},
        )

    def execute(self, capability_input: CapabilityInput) -> CapabilityResult:
        self.received_inputs.append(capability_input)
        return CapabilityResult.succeeded(
            self.capability_id,
            output=capability_input.payload.get("value"),
        )


def test_registry_registers_discovers_and_lists_capabilities() -> None:
    second = RecordingTool(capability_id="test.zulu")
    first = RecordingTool(capability_id="test.alpha")
    registry = CapabilityRegistry([second])

    registered = registry.register(first)

    assert registered is first
    assert registry.get("test.alpha") is first
    assert registry.get("test.zulu") is second
    assert [
        descriptor.capability_id for descriptor in registry.list_capabilities()
    ] == ["test.alpha", "test.zulu"]
    assert isinstance(first, Tool)


def test_registry_rejects_duplicate_identifiers() -> None:
    registry = CapabilityRegistry([RecordingTool()])

    with pytest.raises(DuplicateCapabilityError, match="test.echo"):
        registry.register(RecordingTool())


def test_registry_fails_explicitly_for_unknown_capability() -> None:
    registry = CapabilityRegistry()

    with pytest.raises(CapabilityNotFoundError, match="missing.tool"):
        registry.get("missing.tool")


def test_runtime_fails_explicitly_for_unknown_capability() -> None:
    runtime = CapabilityRuntime(CapabilityRegistry())

    with pytest.raises(CapabilityNotFoundError, match="missing.tool"):
        runtime.execute("missing.tool", CapabilityInput())


def test_runtime_executes_registered_capability_with_explicit_input() -> None:
    tool = RecordingTool()
    runtime = CapabilityRuntime(CapabilityRegistry([tool]))
    invocation_input = CapabilityInput(
        payload={"value": "hello"},
        metadata={"request_id": "request-1"},
    )

    result = runtime.execute("test.echo", invocation_input)

    assert tool.received_inputs == [invocation_input]
    assert result.success is True
    assert result.status is ExecutionStatus.SUCCESS
    assert result.output == "hello"


def test_runtime_preserves_expected_failure_results() -> None:
    class FailingTool(RecordingTool):
        def execute(self, capability_input: CapabilityInput) -> CapabilityResult:
            return CapabilityResult.failed(
                self.capability_id,
                diagnostic="expected operational failure",
                metadata={"recoverable": True},
            )

    runtime = CapabilityRuntime(CapabilityRegistry([FailingTool()]))

    result = runtime.execute("test.echo", CapabilityInput())

    assert result.success is False
    assert result.status is ExecutionStatus.FAILURE
    assert result.diagnostic == "expected operational failure"
    assert result.metadata["recoverable"] is True


def test_runtime_does_not_hide_unexpected_programming_errors() -> None:
    class BrokenTool(RecordingTool):
        def execute(self, capability_input: CapabilityInput) -> CapabilityResult:
            raise TypeError("programming defect")

    runtime = CapabilityRuntime(CapabilityRegistry([BrokenTool()]))

    with pytest.raises(TypeError, match="programming defect"):
        runtime.execute("test.echo", CapabilityInput())


def test_runtime_rejects_result_for_a_different_capability() -> None:
    class InvalidTool(RecordingTool):
        def execute(self, capability_input: CapabilityInput) -> CapabilityResult:
            return CapabilityResult.succeeded("different.tool")

    runtime = CapabilityRuntime(CapabilityRegistry([InvalidTool()]))

    with pytest.raises(ValueError, match="does not match"):
        runtime.execute("test.echo", CapabilityInput())


def test_capability_models_copy_and_freeze_metadata() -> None:
    metadata = {"category": "system"}
    descriptor = CapabilityDescriptor(
        capability_id="system.example",
        description="Example system capability.",
        kind=CapabilityKind.TOOL,
        metadata=metadata,
    )
    capability_input = CapabilityInput(payload={"value": 1})

    metadata["category"] = "changed"

    assert descriptor.metadata["category"] == "system"
    with pytest.raises(TypeError):
        descriptor.metadata["new"] = True  # type: ignore[index]
    with pytest.raises(TypeError):
        capability_input.payload["new"] = True  # type: ignore[index]


def test_capability_descriptor_rejects_invalid_identity() -> None:
    with pytest.raises(ValueError, match="must not be blank"):
        CapabilityDescriptor(
            capability_id=" ",
            description="Invalid capability.",
            kind=CapabilityKind.TOOL,
        )

    with pytest.raises(TypeError, match="CapabilityKind"):
        CapabilityDescriptor(
            capability_id="test.invalid",
            description="Invalid capability.",
            kind="tool",  # type: ignore[arg-type]
        )


def test_failed_result_requires_a_diagnostic() -> None:
    with pytest.raises(ValueError, match="require a diagnostic"):
        CapabilityResult(
            capability_id="test.failure",
            status=ExecutionStatus.FAILURE,
        )


def test_system_status_is_an_executable_tool() -> None:
    provider_calls = 0

    def provide_system_info():
        nonlocal provider_calls
        provider_calls += 1
        return {}

    tool = SystemStatusTool(
        system_info_provider=provide_system_info,
        system_info_formatter=lambda info: "formatted status",
    )
    runtime = CapabilityRuntime(CapabilityRegistry([tool]))

    result = runtime.execute(
        SYSTEM_STATUS_CAPABILITY_ID,
        CapabilityInput(metadata={"source": "test"}),
    )

    assert provider_calls == 1
    assert tool.descriptor.kind is CapabilityKind.TOOL
    assert result.output == "formatted status"
