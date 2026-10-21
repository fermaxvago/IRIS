"""WP067: direct-mode compatibility, wire isolation and failure evidence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from urllib.error import URLError

import pytest

import iris.__main__ as cli
from iris.capabilities import CapabilityRegistry, CapabilityRuntime, SystemStatusTool
from iris.core.system import SystemInfo
from iris.intelligence import (
    ConversationContextBinder,
    ConversationSession,
    IntelligenceRuntime,
    ProviderRegistry,
)
from iris.intelligence.conversation import (
    ConversationMessage,
    ConversationRequest,
    ConversationRole,
)
from iris.intelligence.providers import (
    OllamaDirectModeUnsupportedError,
    OllamaOperationalError,
    OllamaProtocolError,
    OllamaProvider,
)
from iris.intelligence.system_awareness import ConversationalSystemAwareness


class Transport:
    def __init__(self, thinking: object = None) -> None:
        self.thinking = thinking
        self.calls: list[tuple[str, dict[str, object] | None]] = []
        self.response: dict[str, object] = {
            "model": "qwen3:8b",
            "done": True,
            "done_reason": "stop",
            "message": {"role": "assistant", "content": "respuesta"},
        }
        self.installed = True
        self.fail_show = False

    def __call__(
        self, method: str, url: str, body: bytes | None, timeout: float
    ) -> tuple[int, bytes]:
        path = url.rsplit("/", 1)[-1]
        payload = json.loads(body) if body else None
        self.calls.append((path, payload))
        if path == "tags":
            models = (
                [{"name": "qwen3:8b", "model": "qwen3:8b"}] if self.installed else []
            )
            result: dict[str, object] = {"models": models}
        elif path == "show":
            if self.fail_show:
                raise URLError(ConnectionRefusedError())
            result = {"capabilities": ["completion"]}
            if self.thinking is not None:
                result["thinking"] = self.thinking
        elif path == "chat":
            result = self.response
        else:
            raise AssertionError(path)
        return 200, json.dumps(result).encode()


def request() -> ConversationRequest:
    return ConversationRequest(
        model_id="qwen3:8b",
        messages=(ConversationMessage(ConversationRole.USER, "hola"),),
        request_id="wp067-request",
    )


def provider(transport: Transport, *, direct: bool = True) -> OllamaProvider:
    return OllamaProvider(direct_generation=direct, _transport=transport)


def test_standard_wire_remains_unchanged() -> None:
    transport = Transport()
    assert provider(transport, direct=False).chat(request()).success
    assert transport.calls == [
        (
            "chat",
            {
                "model": "qwen3:8b",
                "messages": [{"role": "user", "content": "hola"}],
                "stream": False,
                "options": {"num_predict": 256},
            },
        )
    ]


def test_direct_wire_and_metadata_revalidation() -> None:
    transport = Transport({"values": [False, True], "default": True})
    selected = provider(transport)
    selected.verify_direct_model("qwen3:8b")
    assert selected.chat(request()).success
    assert [path for path, _ in transport.calls].count("chat") == 1
    assert [path for path, _ in transport.calls].count("show") >= 2
    chat_payload = transport.calls[-1][1]
    assert chat_payload is not None
    assert chat_payload["think"] is False
    assert chat_payload["options"] == {"num_predict": 256}
    assert chat_payload["stream"] is False
    assert "tools" not in chat_payload
    assert chat_payload["messages"] == [{"role": "user", "content": "hola"}]


@pytest.mark.parametrize(
    "thinking",
    [
        None,
        {"values": [True], "default": True},
        {"values": ["low", "high"], "default": "low"},
        {"values": ["false"], "default": "false"},
        {"values": [0], "default": 0},
    ],
)
def test_direct_mode_requires_boolean_false(thinking: object) -> None:
    transport = Transport(thinking)
    selected = provider(transport)
    result = selected.chat(request())
    assert not result.success
    assert result.metadata["failure_kind"] in (
        "unsupported_direct_mode",
        "protocol_error",
    )
    assert all(path != "chat" for path, _ in transport.calls)


@pytest.mark.parametrize(
    "thinking",
    [
        [],
        {"values": "false", "default": False},
        {"values": [], "default": False},
        {"values": [False], "default": "false"},
        {"values": [False, None], "default": False},
    ],
)
def test_malformed_thinking_metadata_is_protocol_error(thinking: object) -> None:
    transport = Transport(thinking)
    with pytest.raises(OllamaProtocolError):
        provider(transport).verify_direct_model("qwen3:8b")


def test_unavailable_or_replaced_model_does_not_send_message() -> None:
    transport = Transport({"values": [False], "default": False})
    selected = provider(transport)
    selected.verify_direct_model("qwen3:8b")
    transport.installed = False
    result = selected.chat(request())
    assert result.metadata["failure_kind"] == "unsupported_direct_mode"
    assert all(path != "chat" for path, _ in transport.calls)


def test_provider_failure_during_revalidation_does_not_send_message() -> None:
    transport = Transport({"values": [False], "default": False})
    transport.fail_show = True
    result = provider(transport).chat(request())
    assert result.metadata["failure_kind"] == "provider_unavailable"
    assert all(path != "chat" for path, _ in transport.calls)


def test_incomplete_generation_preserves_only_safe_diagnostics() -> None:
    transport = Transport()
    transport.response = {
        "model": "qwen3:8b",
        "done": True,
        "done_reason": "length",
        "eval_count": 256,
        "prompt_eval_count": 17,
        "message": {"role": "assistant", "content": "partial", "thinking": "private"},
    }
    selected = provider(transport, direct=False)
    session = ConversationSession(
        IntelligenceRuntime(ProviderRegistry([selected])),
        provider_id=selected.provider_id,
        model_id="qwen3:8b",
    )
    result = session.send("hola")
    assert not result.success
    assert result.metadata["failure_kind"] == "incomplete_generation"
    assert result.metadata["ollama.done_reason"] == "length"
    assert result.metadata["ollama.eval_count"] == 256
    assert result.metadata["ollama.prompt_eval_count"] == 17
    assert "private" not in str(result.metadata)
    assert session.messages == ()


@pytest.mark.parametrize("count", [True, -1, "256"])
def test_invalid_provider_counter_is_not_accepted(count: object) -> None:
    transport = Transport()
    transport.response = {
        "model": "qwen3:8b",
        "done": False,
        "eval_count": count,
    }
    result = provider(transport, direct=False).chat(request())
    assert result.metadata["failure_kind"] == "protocol_error"
    assert "ollama.eval_count" not in result.metadata


def test_direct_cli_model_and_select_are_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instances: list[OllamaProvider] = []
    sessions: list[ConversationSession | None] = []

    def factory(*, direct_generation: bool = False) -> OllamaProvider:
        instance = provider(
            Transport({"values": [False, True], "default": True}),
            direct=direct_generation,
        )
        instances.append(instance)
        return instance

    monkeypatch.setattr(cli, "OllamaProvider", factory)
    monkeypatch.setattr(
        cli, "main", lambda **kwargs: sessions.append(kwargs.get("chat_session"))
    )
    cli.entrypoint(["chat", "--model", "qwen3:8b", "--direct"])
    cli.entrypoint(["chat", "--select", "--direct"], input_fn=lambda _: "si")
    assert len(sessions) == 2
    assert all(
        session is not None and session.model_id == "qwen3:8b" for session in sessions
    )
    assert instances[0] is not instances[1]
    with pytest.raises(SystemExit) as exc:
        cli.entrypoint(["chat", "--direct"])
    assert exc.value.code == 2


def test_cli_rejects_incompatible_model_without_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "OllamaProvider", lambda **kwargs: provider(Transport()))
    monkeypatch.setattr(
        cli, "main", lambda **kwargs: pytest.fail("no session may start")
    )
    output: list[str] = []
    cli.entrypoint(["chat", "--model", "qwen3:8b", "--direct"], output_fn=output.append)
    assert any("Modo directo no disponible" in line for line in output)


def test_direct_provider_configuration_is_not_mutable_global_state() -> None:
    transport = Transport({"values": [False, True], "default": True})
    direct = provider(transport)
    standard = provider(transport, direct=False)
    assert direct.chat(request()).success
    assert standard.chat(request()).success
    assert "think" not in (transport.calls[-1][1] or {})


@pytest.mark.parametrize("direct", [False, True])
def test_contextual_resource_turn_preserves_approval_and_wire_data(
    direct: bool,
) -> None:
    now = datetime(2026, 10, 21, 12, tzinfo=UTC)
    transport = Transport({"values": [False, True], "default": True})
    selected = provider(transport, direct=direct)
    session = ConversationSession(
        IntelligenceRuntime(ProviderRegistry([selected])),
        provider_id=selected.provider_id,
        model_id="qwen3:8b",
    )
    captures: list[int] = []

    def capture() -> SystemInfo:
        captures.append(1)
        return {"cpu_percent": 27.0, "ram_used_gb": 21.4, "ram_total_gb": 31.7}

    awareness = ConversationalSystemAwareness(
        capability_runtime=CapabilityRuntime(
            CapabilityRegistry(
                [SystemStatusTool(system_info_provider=capture, clock=lambda: now)]
            )
        ),
        context_binder=ConversationContextBinder(clock=lambda: now),
        clock=lambda: now,
    )
    consultation = awareness.prepare(session, "¿Cómo está mi RAM?")
    assert consultation.proposal is not None
    assert captures == [1]
    assert session.messages == ()
    result = awareness.send_approved(session, consultation.proposal)
    assert result.success
    chat_calls = [payload for path, payload in transport.calls if path == "chat"]
    assert len(chat_calls) == 1
    chat_payload = chat_calls[0]
    assert chat_payload is not None
    if direct:
        assert chat_payload.get("think") is False
    else:
        assert "think" not in chat_payload
    assert chat_payload["options"] == {"num_predict": 256}
    assert "tools" not in chat_payload
    messages = chat_payload["messages"]
    assert isinstance(messages, list)
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert consultation.proposal.payload.section in messages[0]["content"]
    assert session.completed_turns == 1
    assert all("IRIS_CONTEXT" not in message.content for message in session.messages)


def test_direct_revalidation_blocks_approved_context_before_chat() -> None:
    now = datetime(2026, 10, 21, 12, tzinfo=UTC)
    transport = Transport({"values": [False, True], "default": True})
    selected = provider(transport)
    session = ConversationSession(
        IntelligenceRuntime(ProviderRegistry([selected])),
        provider_id=selected.provider_id,
        model_id="qwen3:8b",
    )
    awareness = ConversationalSystemAwareness(
        capability_runtime=CapabilityRuntime(
            CapabilityRegistry(
                [
                    SystemStatusTool(
                        system_info_provider=lambda: {
                            "cpu_percent": 27.0,
                            "ram_used_gb": 21.4,
                            "ram_total_gb": 31.7,
                        },
                        clock=lambda: now,
                    )
                ]
            )
        ),
        context_binder=ConversationContextBinder(clock=lambda: now),
        clock=lambda: now,
    )
    consultation = awareness.prepare(session, "¿Cómo está mi RAM?")
    assert consultation.proposal is not None
    transport.thinking = {"values": [True], "default": True}
    result = awareness.send_approved(session, consultation.proposal)
    assert not result.success
    assert result.metadata["failure_kind"] == "unsupported_direct_mode"
    assert session.messages == ()
    assert all(path != "chat" for path, _ in transport.calls)


def test_direct_mode_domain_error_type() -> None:
    assert issubclass(OllamaDirectModeUnsupportedError, OllamaOperationalError)
