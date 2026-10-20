"""Bounded, process-local conversation state independent of providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from threading import Lock
from uuid import uuid4

from iris.intelligence.models import IntelligenceResult
from iris.intelligence.runtime import IntelligenceRuntime

MAX_PREVIOUS_TURNS = 8
MAX_USER_CHARACTERS = 2_000
MAX_CONTEXT_CHARACTERS = 6_000
MAX_OUTPUT_TOKENS = 256


class ConversationRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    role: ConversationRole
    content: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, ConversationRole):
            raise TypeError("role must be a ConversationRole")
        if not isinstance(self.content, str):
            raise TypeError("content must be a string")
        if not self.content.strip():
            raise ValueError("content must not be blank")


@dataclass(frozen=True, slots=True)
class ConversationRequest:
    """One ordered, role-aware request ending in an uncommitted user message."""

    model_id: str
    messages: tuple[ConversationMessage, ...]
    max_output_tokens: int = MAX_OUTPUT_TOKENS
    request_id: str = field(default_factory=lambda: uuid4().hex)

    def __post_init__(self) -> None:
        _identifier(self.model_id, "model_id")
        _identifier(self.request_id, "request_id")
        if not isinstance(self.messages, tuple) or not self.messages:
            raise ValueError("messages must be a nonempty tuple")
        if len(self.messages) % 2 != 1:
            raise ValueError("messages must end with an uncommitted user message")
        for index, message in enumerate(self.messages):
            if not isinstance(message, ConversationMessage):
                raise TypeError("messages must contain ConversationMessage values")
            expected = (
                ConversationRole.USER if index % 2 == 0 else ConversationRole.ASSISTANT
            )
            if message.role is not expected:
                raise ValueError("messages must alternate user and assistant roles")
        if len(self.messages) // 2 > MAX_PREVIOUS_TURNS:
            raise ConversationLimitError("request exceeds eight previous turns")
        if len(self.messages[-1].content) > MAX_USER_CHARACTERS:
            raise ConversationLimitError("user message exceeds 2000 characters")
        if (
            sum(len(message.content) for message in self.messages)
            > MAX_CONTEXT_CHARACTERS
        ):
            raise ConversationLimitError("conversation exceeds 6000 characters")
        if isinstance(self.max_output_tokens, bool) or not isinstance(
            self.max_output_tokens, int
        ):
            raise TypeError("max_output_tokens must be an integer")
        if not 1 <= self.max_output_tokens <= MAX_OUTPUT_TOKENS:
            raise ValueError("max_output_tokens exceeds the conversational limit")


class ConversationLimitError(ValueError):
    """The proposed turn cannot fit without discarding completed history."""


class ConversationBusyError(RuntimeError):
    """Another turn or reset is already active for this session."""


class ConversationSession:
    """Commit complete pairs only after a validated provider response."""

    def __init__(
        self,
        runtime: IntelligenceRuntime,
        *,
        provider_id: str,
        model_id: str,
        session_id: str | None = None,
    ) -> None:
        if not isinstance(runtime, IntelligenceRuntime):
            raise TypeError("runtime must be an IntelligenceRuntime")
        self._runtime = runtime
        self.provider_id = _identifier(provider_id, "provider_id")
        self.model_id = _identifier(model_id, "model_id")
        self.session_id = _identifier(
            uuid4().hex if session_id is None else session_id, "session_id"
        )
        self._messages: tuple[ConversationMessage, ...] = ()
        self._lock = Lock()

    @property
    def messages(self) -> tuple[ConversationMessage, ...]:
        return self._messages

    @property
    def completed_turns(self) -> int:
        return len(self._messages) // 2

    def reset(self) -> None:
        if not self._lock.acquire(blocking=False):
            raise ConversationBusyError("conversation is busy")
        try:
            self._messages = ()
        finally:
            self._lock.release()

    def send(self, content: str) -> IntelligenceResult:
        if not self._lock.acquire(blocking=False):
            raise ConversationBusyError("conversation is busy")
        try:
            if not isinstance(content, str):
                raise TypeError("user content must be a string")
            if len(content) > MAX_USER_CHARACTERS:
                raise ConversationLimitError("user message exceeds 2000 characters")
            user_message = ConversationMessage(ConversationRole.USER, content)
            if self.completed_turns >= MAX_PREVIOUS_TURNS:
                raise ConversationLimitError("session is full; use /reiniciar")
            used = sum(len(message.content) for message in self._messages)
            if used + len(content) > MAX_CONTEXT_CHARACTERS:
                raise ConversationLimitError("conversation exceeds 6000 characters")
            request = ConversationRequest(
                model_id=self.model_id,
                messages=(*self._messages, user_message),
            )
            result = self._runtime.chat(self.provider_id, request)
            if not result.success:
                return result
            if not isinstance(result.output, str) or not result.output.strip():
                raise ValueError("successful chat response must contain assistant text")
            assistant_message = ConversationMessage(
                ConversationRole.ASSISTANT, result.output
            )
            if (
                used + len(content) + len(assistant_message.content)
                > MAX_CONTEXT_CHARACTERS
            ):
                raise ConversationLimitError(
                    "assistant response exceeds the 6000-character session limit"
                )
            self._messages = (*self._messages, user_message, assistant_message)
            return result
        finally:
            self._lock.release()


def _identifier(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip() or value != value.strip():
        raise ValueError(f"{name} must be nonblank without surrounding whitespace")
    return value
