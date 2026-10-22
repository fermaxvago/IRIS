"""Bounded, process-local conversation state independent of providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from threading import Lock
from typing import TYPE_CHECKING
from uuid import uuid4

from iris.intelligence.models import IntelligenceResult
from iris.intelligence.runtime import IntelligenceRuntime

if TYPE_CHECKING:
    from iris.intelligence.context_binding import (
        ContextApproval,
        ConversationContextBinder,
    )

MAX_PREVIOUS_TURNS = 8
MAX_USER_CHARACTERS = 2_000
MAX_CONTEXT_CHARACTERS = 6_000
MAX_OUTPUT_TOKENS = 256
MAX_CONTEXT_ITEMS = 8
MAX_CONTEXT_SECTION_CHARACTERS = 1_500


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
class ConversationContextPayload:
    """Approved, one-turn informational data; never a history message."""

    snapshot_id: str
    subject_id: str
    section: str
    item_ids: tuple[str, ...]
    approval_id: str | None = field(default=None, repr=False, compare=False)
    _issuer: ConversationContextBinder | None = field(
        default=None, repr=False, compare=False
    )
    _claimed: bool = field(default=False, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _identifier(self.snapshot_id, "snapshot_id")
        _identifier(self.subject_id, "subject_id")
        if not isinstance(self.section, str) or not self.section.strip():
            raise ValueError("context section must contain text")
        if len(self.section) > MAX_CONTEXT_SECTION_CHARACTERS:
            raise ConversationLimitError("context section exceeds 1500 characters")
        if not isinstance(self.item_ids, tuple) or not self.item_ids:
            raise ValueError("context item IDs must be a nonempty tuple")
        if len(self.item_ids) > MAX_CONTEXT_ITEMS:
            raise ConversationLimitError("context exceeds eight selected items")
        if len(self.item_ids) != len(set(self.item_ids)):
            raise ValueError("context item IDs must be distinct")
        for item_id in self.item_ids:
            _identifier(item_id, "context item ID")
        if (self.approval_id is None) != (self._issuer is None):
            raise ValueError("context authorization must be complete")

    def _claim(self, request: ConversationRequest, provider_id: str) -> None:
        from iris.intelligence.context_binding import ContextBindingError

        if self._issuer is None or self.approval_id is None:
            raise ContextBindingError("context lacks a consumed approval")
        self._issuer._claim_payload(self, request, provider_id)
        object.__setattr__(self, "_claimed", True)

    def _assert_claimed(self) -> None:
        from iris.intelligence.context_binding import ContextBindingError

        if not self._claimed:
            raise ContextBindingError("context was not authorized by the runtime")

    def _clear_claim(self) -> None:
        object.__setattr__(self, "_claimed", False)
        if self._issuer is not None:
            self._issuer._cancel_payload(self)


@dataclass(frozen=True, slots=True)
class ConversationRequest:
    """One ordered, role-aware request ending in an uncommitted user message."""

    model_id: str
    messages: tuple[ConversationMessage, ...]
    max_output_tokens: int = MAX_OUTPUT_TOKENS
    request_id: str = field(default_factory=lambda: uuid4().hex)
    context: ConversationContextPayload | None = None

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
        if self.context is not None:
            if not isinstance(self.context, ConversationContextPayload):
                raise TypeError("context must be a ConversationContextPayload")
            if (
                sum(len(message.content) for message in self.messages)
                + len(self.context.section)
                > MAX_CONTEXT_CHARACTERS
            ):
                raise ConversationLimitError(
                    "transmitted conversation and context exceed 6000 characters"
                )
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


@dataclass(frozen=True, slots=True)
class ConversationWindow:
    """Immutable inference candidate, not a committed conversation state."""

    session_id: str
    generation: int
    revision: int
    continuity_enabled: bool
    history: tuple[ConversationMessage, ...]
    content: str
    context_section: str | None
    retired_turns: int


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
        self._generation = 0
        self._revision = 0
        self._continuity_enabled = False
        self._last_commit_evictions = 0
        self._lock = Lock()

    @property
    def messages(self) -> tuple[ConversationMessage, ...]:
        return self._messages

    @property
    def completed_turns(self) -> int:
        return len(self._messages) // 2

    @property
    def generation(self) -> int:
        """Reset generation invalidates approvals even when session ID is stable."""

        return self._generation

    @property
    def revision(self) -> int:
        """Monotonic identity of confirmed session state and policy."""

        return self._revision

    @property
    def continuity_enabled(self) -> bool:
        return self._continuity_enabled

    @property
    def last_commit_evictions(self) -> int:
        return self._last_commit_evictions

    def set_continuity(self, enabled: bool) -> None:
        if not isinstance(enabled, bool):
            raise TypeError("continuity policy must be boolean")
        if not self._lock.acquire(blocking=False):
            raise ConversationBusyError("conversation is busy")
        try:
            if self._continuity_enabled != enabled:
                self._continuity_enabled = enabled
                self._revision += 1
        finally:
            self._lock.release()

    def prepare_window(
        self, content: str, context: ConversationContextPayload | None = None
    ) -> ConversationWindow:
        """Select the longest valid recent suffix without changing history."""

        if not self._lock.acquire(blocking=False):
            raise ConversationBusyError("conversation is busy")
        try:
            return self._prepare_window_unlocked(content, context)
        finally:
            self._lock.release()

    def can_rollover(
        self, content: str, context: ConversationContextPayload | None = None
    ) -> bool:
        """Test a hypothetical enabled policy without authorizing or changing it."""

        if not self._lock.acquire(blocking=False):
            raise ConversationBusyError("conversation is busy")
        try:
            if self._continuity_enabled:
                return False
            try:
                candidate = self._prepare_window_unlocked(
                    content, context, enabled=True
                )
            except ConversationLimitError:
                return False
            return (
                candidate.retired_turns > 0
                or self.completed_turns >= MAX_PREVIOUS_TURNS
            )
        finally:
            self._lock.release()

    def _prepare_window_unlocked(
        self,
        content: str,
        context: ConversationContextPayload | None = None,
        *,
        enabled: bool | None = None,
    ) -> ConversationWindow:
        if not isinstance(content, str):
            raise TypeError("user content must be a string")
        if len(content) > MAX_USER_CHARACTERS:
            raise ConversationLimitError("user message exceeds 2000 characters")
        user_message = ConversationMessage(ConversationRole.USER, content)
        if context is not None and not isinstance(context, ConversationContextPayload):
            raise TypeError("context must be a ConversationContextPayload")
        rolling = self._continuity_enabled if enabled is None else enabled
        history = self._messages
        retired = 0
        while True:
            if not rolling and len(history) // 2 >= MAX_PREVIOUS_TURNS:
                raise ConversationLimitError("session is full; use /reiniciar")
            try:
                ConversationRequest(
                    model_id=self.model_id,
                    messages=(*history, user_message),
                    context=context,
                )
            except ConversationLimitError:
                if not rolling or not history:
                    raise
                history = history[2:]
                retired += 1
                continue
            return ConversationWindow(
                session_id=self.session_id,
                generation=self._generation,
                revision=self._revision,
                continuity_enabled=rolling,
                history=history,
                content=content,
                context_section=None if context is None else context.section,
                retired_turns=retired,
            )

    def reset(self) -> None:
        if not self._lock.acquire(blocking=False):
            raise ConversationBusyError("conversation is busy")
        try:
            self._messages = ()
            self._generation += 1
            self._revision += 1
            self._continuity_enabled = False
            self._last_commit_evictions = 0
        finally:
            self._lock.release()

    def send(
        self,
        content: str,
        *,
        approval: ContextApproval | None = None,
    ) -> IntelligenceResult:
        if not self._lock.acquire(blocking=False):
            raise ConversationBusyError("conversation is busy")
        try:
            context: ConversationContextPayload | None = None
            if approval is not None:
                from iris.intelligence.context_binding import ContextApproval

                if not isinstance(approval, ContextApproval):
                    raise TypeError("approval must be a ContextApproval")
                context = approval._consume(self, content)
            window = self._prepare_window_unlocked(content, context)
            user_message = ConversationMessage(ConversationRole.USER, content)
            request = ConversationRequest(
                model_id=self.model_id,
                messages=(*window.history, user_message),
                context=context,
            )
            result = self._runtime.chat(self.provider_id, request)
            if not result.success:
                return result
            if not isinstance(result.output, str) or not result.output.strip():
                raise ValueError("successful chat response must contain assistant text")
            assistant_message = ConversationMessage(
                ConversationRole.ASSISTANT, result.output
            )
            retained = window.history
            while (
                len(retained) // 2 + 1 > MAX_PREVIOUS_TURNS
                or sum(len(message.content) for message in retained)
                + len(content)
                + len(assistant_message.content)
                > MAX_CONTEXT_CHARACTERS
            ):
                if not self._continuity_enabled or not retained:
                    raise ConversationLimitError(
                        "assistant response exceeds the 6000-character session limit"
                    )
                retained = retained[2:]
            previous_turns = self.completed_turns
            self._messages = (*retained, user_message, assistant_message)
            self._last_commit_evictions = previous_turns - len(retained) // 2
            self._revision += 1
            return result
        finally:
            if context is not None:
                context._clear_claim()
            self._lock.release()


def _identifier(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip() or value != value.strip():
        raise ValueError(f"{name} must be nonblank without surrounding whitespace")
    return value
