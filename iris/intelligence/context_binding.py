"""Process-local, one-turn disclosure binding for existing ContextSnapshots.

The caller of ``approve`` must first obtain an explicit human decision. This
module does not authenticate that caller or provide a general permissions system.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import uuid4

from iris.context import ContextSnapshot, Freshness, ResolutionStatus
from iris.intelligence.conversation import (
    MAX_CONTEXT_ITEMS,
    MAX_CONTEXT_SECTION_CHARACTERS,
    ConversationContextPayload,
    ConversationLimitError,
    ConversationMessage,
    ConversationRequest,
    ConversationRole,
    ConversationSession,
    ConversationWindow,
)
from iris.memory.models import MemoryScope, utc_time
from iris.work_identity.models import WorkSubject


class ContextBindingError(ValueError):
    """Context is ineligible, approval is invalid, or a binding is stale."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class ContextFreshnessPolicy:
    """Deterministic maximum ages for evidence and the approval decision."""

    max_age: timedelta = timedelta(minutes=10)
    approval_ttl: timedelta = timedelta(minutes=2)

    def __post_init__(self) -> None:
        for name in ("max_age", "approval_ttl"):
            value = getattr(self, name)
            if not isinstance(value, timedelta) or value <= timedelta(0):
                raise ValueError(f"{name} must be a positive timedelta")


@dataclass(frozen=True, slots=True)
class ContextDisclosureProposal:
    """Inspectable exact disclosure proposal; it is not authorization."""

    session: ConversationSession
    snapshot: ContextSnapshot
    subject: WorkSubject
    content: str
    provider_id: str
    model_id: str
    session_id: str
    session_generation: int
    session_revision: int
    turn_index: int
    window: ConversationWindow
    item_ids: tuple[str, ...]
    scopes: frozenset[MemoryScope]
    payload: ConversationContextPayload
    proposed_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ContextApproval:
    """Opaque one-use approval issued only by a trusted process-local caller."""

    approval_id: str
    proposal: ContextDisclosureProposal
    approved_item_ids: tuple[str, ...]
    approved_scopes: frozenset[MemoryScope]
    _issuer: ConversationContextBinder

    def _consume(
        self, session: ConversationSession, content: str
    ) -> ConversationContextPayload:
        return self._issuer._consume(self, session, content)


class ConversationContextBinder:
    """Validate, propose, issue, and consume one-turn context disclosure."""

    def __init__(
        self,
        *,
        policy: ContextFreshnessPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if policy is not None and not isinstance(policy, ContextFreshnessPolicy):
            raise TypeError("policy must be ContextFreshnessPolicy")
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable")
        self._policy = ContextFreshnessPolicy() if policy is None else policy
        self._clock: Callable[[], datetime] = _utc_now if clock is None else clock
        self._proposals: dict[
            int, tuple[ContextDisclosureProposal, tuple[object, ...]]
        ] = {}
        self._issued: dict[str, tuple[ContextApproval, tuple[object, ...]]] = {}
        self._authorized_payloads: dict[
            int, tuple[ConversationContextPayload, ContextDisclosureProposal, str]
        ] = {}
        self._lock = Lock()

    def propose(
        self,
        session: ConversationSession,
        snapshot: ContextSnapshot,
        *,
        subject: WorkSubject,
        content: str,
    ) -> ContextDisclosureProposal:
        """Inspect one snapshot and turn without inference or consent inference."""

        if not isinstance(session, ConversationSession):
            raise TypeError("session must be a ConversationSession")
        now = utc_time(self._clock(), "context binding clock")
        _eligible_snapshot(snapshot, subject, now, self._policy)
        payload = _payload(snapshot)
        window = session.prepare_window(content, payload)
        proposal = ContextDisclosureProposal(
            session=session,
            snapshot=snapshot,
            subject=subject,
            content=content,
            provider_id=session.provider_id,
            model_id=session.model_id,
            session_id=session.session_id,
            session_generation=session.generation,
            session_revision=window.revision,
            turn_index=session.completed_turns,
            window=window,
            item_ids=payload.item_ids,
            scopes=frozenset(item.scope for item in snapshot.items),
            payload=payload,
            proposed_at=now,
            expires_at=now + self._policy.approval_ttl,
        )
        with self._lock:
            self._proposals[id(proposal)] = (proposal, _proposal_seal(proposal))
        return proposal

    def approve(
        self,
        proposal: ContextDisclosureProposal,
        *,
        approved_item_ids: tuple[str, ...],
        approved_scopes: frozenset[MemoryScope],
    ) -> ContextApproval:
        """Trusted caller issues only after an explicit disclosure decision.

        The caller must show the exact proposal and obtain human acceptance.
        Passing a boolean is deliberately insufficient.
        """

        if not isinstance(proposal, ContextDisclosureProposal):
            raise TypeError("proposal must be ContextDisclosureProposal")
        if not isinstance(approved_item_ids, tuple) or not isinstance(
            approved_scopes, frozenset
        ):
            raise TypeError("approval requires exact item IDs and scopes")
        if approved_item_ids != proposal.item_ids or approved_scopes != proposal.scopes:
            raise ContextBindingError("approval does not cover exact items and scopes")
        now = utc_time(self._clock(), "context approval clock")
        self._validate_proposal(proposal, now)
        with self._lock:
            original = self._proposals.get(id(proposal))
            if (
                original is None
                or original[0] is not proposal
                or original[1] != _proposal_seal(proposal)
            ):
                raise ContextBindingError(
                    "disclosure proposal was not issued or changed"
                )
            del self._proposals[id(proposal)]
            approval = ContextApproval(
                approval_id=uuid4().hex,
                proposal=proposal,
                approved_item_ids=approved_item_ids,
                approved_scopes=approved_scopes,
                _issuer=self,
            )
            self._issued[approval.approval_id] = (approval, _approval_seal(approval))
        return approval

    def _consume(
        self,
        approval: ContextApproval,
        session: ConversationSession,
        content: str,
    ) -> ConversationContextPayload:
        # Pop before validation or inference: failure never leaves implicit reuse.
        with self._lock:
            original = self._issued.get(approval.approval_id)
            if original is None or original[0] is not approval:
                raise ContextBindingError("context approval is absent or already used")
            del self._issued[approval.approval_id]
        if original[1] != _approval_seal(approval):
            raise ContextBindingError("context approval changed after issuance")
        proposal = approval.proposal
        if (
            session is not proposal.session
            or content != proposal.content
            or approval.approved_item_ids != proposal.item_ids
            or approval.approved_scopes != proposal.scopes
        ):
            raise ContextBindingError("approval does not match this session or turn")
        now = utc_time(self._clock(), "context use clock")
        self._validate_proposal(proposal, now, session_locked=True)
        authorized = replace(
            proposal.payload, approval_id=approval.approval_id, _issuer=self
        )
        with self._lock:
            self._authorized_payloads[id(authorized)] = (
                authorized,
                proposal,
                approval.approval_id,
            )
        return authorized

    def _claim_payload(
        self,
        payload: ConversationContextPayload,
        request: ConversationRequest,
        provider_id: str,
    ) -> None:
        with self._lock:
            original = self._authorized_payloads.get(id(payload))
            if original is None or original[0] is not payload:
                raise ContextBindingError("context payload lacks a one-use approval")
            del self._authorized_payloads[id(payload)]
        proposal = original[1]
        if (
            request.context is not payload
            or request.model_id != proposal.model_id
            or provider_id != proposal.provider_id
            or request.messages
            != (
                *proposal.window.history,
                ConversationMessage(ConversationRole.USER, proposal.content),
            )
            or payload.snapshot_id != proposal.payload.snapshot_id
            or payload.subject_id != proposal.payload.subject_id
            or payload.section != proposal.payload.section
            or payload.item_ids != proposal.payload.item_ids
            or payload.approval_id != original[2]
            or payload._issuer is not self
        ):
            raise ContextBindingError("context payload or destination was substituted")
        now = utc_time(self._clock(), "context execution clock")
        self._validate_proposal(proposal, now, session_locked=True)

    def _cancel_payload(self, payload: ConversationContextPayload) -> None:
        with self._lock:
            original = self._authorized_payloads.get(id(payload))
            if original is not None and original[0] is payload:
                del self._authorized_payloads[id(payload)]

    def _validate_proposal(
        self,
        proposal: ContextDisclosureProposal,
        now: datetime,
        *,
        session_locked: bool = False,
    ) -> None:
        session = proposal.session
        if (
            session.session_id != proposal.session_id
            or session.generation != proposal.session_generation
            or session.revision != proposal.session_revision
            or session.completed_turns != proposal.turn_index
            or session.continuity_enabled != proposal.window.continuity_enabled
            or proposal.window.session_id != proposal.session_id
            or proposal.window.generation != proposal.session_generation
            or proposal.window.revision != proposal.session_revision
            or session.provider_id != proposal.provider_id
            or session.model_id != proposal.model_id
        ):
            raise ContextBindingError("session or destination changed after proposal")
        if now < proposal.proposed_at or now > proposal.expires_at:
            raise ContextBindingError("context approval has expired or clock regressed")
        _eligible_snapshot(proposal.snapshot, proposal.subject, now, self._policy)
        if (
            proposal.snapshot.snapshot_id != proposal.payload.snapshot_id
            or proposal.subject.subject_id != proposal.payload.subject_id
            or proposal.item_ids != proposal.payload.item_ids
            or proposal.item_ids
            != tuple(item.candidate_id for item in proposal.snapshot.items)
            or proposal.scopes
            != frozenset(item.scope for item in proposal.snapshot.items)
            or proposal.payload != _payload(proposal.snapshot)
        ):
            raise ContextBindingError("approved snapshot content was substituted")
        current_window = (
            session._prepare_window_unlocked(proposal.content, proposal.payload)
            if session_locked
            else session.prepare_window(proposal.content, proposal.payload)
        )
        if current_window != proposal.window:
            raise ContextBindingError("approved history window changed")


def _eligible_snapshot(
    snapshot: ContextSnapshot,
    subject: WorkSubject,
    now: datetime,
    policy: ContextFreshnessPolicy,
) -> None:
    if not isinstance(snapshot, ContextSnapshot) or not isinstance(
        subject, WorkSubject
    ):
        raise TypeError("snapshot and subject must be canonical models")
    if snapshot.subject is not subject:
        raise ContextBindingError("snapshot belongs to a different WorkSubject")
    try:
        if (
            replace(subject) != subject
            or replace(subject.reference) != subject.reference
        ):
            raise ContextBindingError("WorkSubject requires normalization")
        if subject.origin is not None and replace(subject.origin) != subject.origin:
            raise ContextBindingError("WorkSubject origin requires normalization")
        if replace(snapshot) != snapshot or replace(snapshot.budget) != snapshot.budget:
            raise ContextBindingError("ContextSnapshot requires normalization")
        for item in snapshot.items:
            if (
                replace(item) != item
                or replace(item.evidence) != item.evidence
                or replace(item.scope) != item.scope
            ):
                raise ContextBindingError("context item requires normalization")
    except (TypeError, ValueError) as exc:
        raise ContextBindingError("malformed contextual artifact") from exc
    if (
        snapshot.status is not ResolutionStatus.RESOLVED
        or snapshot.conflicts
        or snapshot.uncertainties
        or snapshot.budget_excluded_ids
    ):
        raise ContextBindingError("only unambiguous RESOLVED context is eligible")
    if not snapshot.items:
        raise ContextBindingError("context has no selected items")
    if len(snapshot.items) > MAX_CONTEXT_ITEMS:
        raise ConversationLimitError("context exceeds eight selected items")
    ids = tuple(item.candidate_id for item in snapshot.items)
    if len(ids) != len(set(ids)):
        raise ContextBindingError("context repeats an evidence identity")
    if snapshot.created_at > now or now - snapshot.created_at > policy.max_age:
        raise ContextBindingError("snapshot is future-dated or stale")
    for item in snapshot.items:
        if item.freshness not in (Freshness.CURRENT, Freshness.RECENT):
            raise ContextBindingError("item has stale or unknown freshness")
        observed = item.observed_at
        if observed is None:
            raise ContextBindingError("item lacks a verifiable observation time")
        if observed > snapshot.created_at or observed > now:
            raise ContextBindingError("item observation is future-dated")
        if now - observed > policy.max_age:
            raise ContextBindingError("item observation is stale")


def _proposal_seal(proposal: ContextDisclosureProposal) -> tuple[object, ...]:
    """Snapshot immutable scalar values independently of mutable Python objects."""

    return (
        id(proposal.session),
        id(proposal.snapshot),
        id(proposal.subject),
        id(proposal.payload),
        proposal.content,
        proposal.provider_id,
        proposal.model_id,
        proposal.session_id,
        proposal.session_generation,
        proposal.session_revision,
        proposal.turn_index,
        _window_seal(proposal.window),
        proposal.item_ids,
        _scope_values(proposal.scopes),
        proposal.payload.snapshot_id,
        proposal.payload.subject_id,
        proposal.payload.section,
        proposal.payload.item_ids,
        proposal.payload.approval_id,
        id(proposal.payload._issuer),
        proposal.payload._claimed,
        proposal.proposed_at,
        proposal.expires_at,
    )


def _approval_seal(approval: ContextApproval) -> tuple[object, ...]:
    return (
        id(approval.proposal),
        _proposal_seal(approval.proposal),
        approval.approved_item_ids,
        _scope_values(approval.approved_scopes),
        id(approval._issuer),
    )


def _window_seal(window: ConversationWindow) -> tuple[object, ...]:
    return (
        window.session_id,
        window.generation,
        window.revision,
        window.continuity_enabled,
        tuple((message.role, message.content) for message in window.history),
        window.content,
        window.context_section,
        window.retired_turns,
    )


def _scope_values(scopes: frozenset[MemoryScope]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((scope.kind.value, scope.identifier or "") for scope in scopes))


def _payload(snapshot: ContextSnapshot) -> ConversationContextPayload:
    evidence = {
        "snapshot_id": snapshot.snapshot_id,
        "subject_id": snapshot.subject_id,
        "snapshot_created_at": snapshot.created_at.isoformat(),
        "items": [
            {
                "id": item.candidate_id,
                "kind": item.kind,
                "key": item.key,
                "value": item.value,
                "source": item.evidence.source.value,
                "reference": item.evidence.reference,
                "epistemic": item.evidence.epistemic.value,
                "scope": {
                    "kind": item.scope.kind.value,
                    "identifier": item.scope.identifier,
                },
                "freshness": item.freshness.value,
                "observed_at": item.observed_at.isoformat()
                if item.observed_at is not None
                else None,
            }
            for item in snapshot.items
        ],
    }
    encoded = json.dumps(
        evidence, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
    # Literal delimiters cannot be injected through JSON scalar values.
    encoded = encoded.replace("<", "\\u003c").replace(">", "\\u003e")
    section = f"\n<IRIS_CONTEXT_DATA_JSON>\n{encoded}\n</IRIS_CONTEXT_DATA_JSON>"
    if len(section) > MAX_CONTEXT_SECTION_CHARACTERS:
        raise ConversationLimitError("serialized context exceeds 1500 characters")
    return ConversationContextPayload(
        snapshot_id=snapshot.snapshot_id,
        subject_id=snapshot.subject_id,
        section=section,
        item_ids=tuple(item.candidate_id for item in snapshot.items),
    )
