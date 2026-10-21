"""One explicitly requested system observation and one-turn context proposal."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import uuid4

from iris.capabilities import (
    SYSTEM_STATUS_CAPABILITY_ID,
    CapabilityInput,
    CapabilityRuntime,
    SystemResourceObservation,
    create_default_runtime,
)
from iris.context import (
    ContextBudget,
    ContextCandidate,
    ContextEngine,
    ContextEvidence,
    ContextKind,
    ContextSnapshot,
    EvidenceSource,
    Freshness,
    Relevance,
    ResolutionStatus,
)
from iris.intelligence.context_binding import (
    ContextDisclosureProposal,
    ConversationContextBinder,
)
from iris.intelligence.conversation import ConversationSession
from iris.intelligence.models import IntelligenceResult
from iris.memory.models import EpistemicStatus, MemoryScope, ScopeKind, utc_time
from iris.work_identity.models import (
    RequestWorkReference,
    WorkOrigin,
    WorkSubject,
    WorkSubjectKind,
)


class SystemAwarenessError(ValueError):
    """The requested observation cannot safely become contextual evidence."""


@dataclass(frozen=True, slots=True)
class ResourceConsultation:
    """Local reading and optional inspectable disclosure; never approval."""

    observation: SystemResourceObservation
    proposal: ContextDisclosureProposal | None


class ConversationalSystemAwareness:
    """Compose existing read-only capability, context and disclosure authorities."""

    def __init__(
        self,
        *,
        capability_runtime: CapabilityRuntime | None = None,
        context_engine: ContextEngine | None = None,
        context_binder: ConversationContextBinder | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._capabilities = capability_runtime or create_default_runtime()
        self._context = context_engine or ContextEngine()
        self._binder = context_binder or ConversationContextBinder()
        self._clock = clock or (lambda: datetime.now(UTC))

    def prepare(
        self, session: ConversationSession, question: str
    ) -> ResourceConsultation:
        """Capture once; only complete canonical evidence gets a proposal."""

        if not isinstance(session, ConversationSession):
            raise TypeError("session must be ConversationSession")
        if not isinstance(question, str) or not question.strip():
            raise ValueError("resource question must be nonblank")
        result = self._capabilities.execute(
            SYSTEM_STATUS_CAPABILITY_ID,
            CapabilityInput(payload={"output_mode": "structured"}),
        )
        if not result.success:
            raise SystemAwarenessError(result.diagnostic or "system.status failed")
        observation = result.output
        if not isinstance(observation, SystemResourceObservation):
            raise SystemAwarenessError("system.status did not return structured data")
        # Scratch-copy validation detects malformed injected/frozen results without repair.
        try:
            if replace(observation) != observation:
                raise ValueError("noncanonical observation")
        except (TypeError, ValueError) as exc:
            raise SystemAwarenessError("malformed system.status observation") from exc
        if not observation.complete:
            return ResourceConsultation(observation, None)
        assert observation.cpu_percent is not None
        assert observation.ram_used_gb is not None
        assert observation.ram_total_gb is not None
        now = utc_time(self._clock(), "resource context clock")
        if observation.captured_at > now:
            raise SystemAwarenessError("resource observation is future-dated")
        work_id = uuid4().hex
        subject = WorkSubject(
            WorkSubjectKind.REQUEST,
            RequestWorkReference(work_id),
            WorkOrigin("request", work_id),
        )
        scope = MemoryScope(ScopeKind.SESSION, session.session_id)
        evidence = ContextEvidence(
            EvidenceSource.SYSTEM,
            SYSTEM_STATUS_CAPABILITY_ID,
            EpistemicStatus.OBSERVED,
        )
        candidates = tuple(
            ContextCandidate(
                candidate_id=name,
                kind=ContextKind.RESOURCE.value,
                key=name,
                value=value,
                evidence=evidence,
                scope=scope,
                relevance=Relevance.REQUIRED,
                freshness=Freshness.CURRENT,
                observed_at=observation.captured_at,
            )
            for name, value in (
                ("cpu_percent", observation.cpu_percent),
                ("ram_used_gb", observation.ram_used_gb),
                ("ram_total_gb", observation.ram_total_gb),
            )
        )
        snapshot = self._context.build(
            subject=subject,
            candidates=candidates,
            budget=ContextBudget(max_items=3),
            created_at=now,
        )
        if (
            not isinstance(snapshot, ContextSnapshot)
            or snapshot.subject is not subject
            or snapshot.created_at != now
            or snapshot.budget.max_items != 3
            or snapshot.status is not ResolutionStatus.RESOLVED
            or len(snapshot.items) != 3
            or snapshot.uncertainties
            or snapshot.conflicts
            or snapshot.budget_excluded_ids
            or {item.candidate_id for item in snapshot.items}
            != {"cpu_percent", "ram_used_gb", "ram_total_gb"}
            or {item.candidate_id: item for item in snapshot.items}
            != {candidate.candidate_id: candidate.to_item() for candidate in candidates}
        ):
            raise SystemAwarenessError("resource context is incomplete or unresolved")
        proposal = self._binder.propose(
            session, snapshot, subject=subject, content=question
        )
        return ResourceConsultation(observation, proposal)

    def send_approved(
        self, session: ConversationSession, proposal: ContextDisclosureProposal
    ) -> IntelligenceResult:
        """Called only after the trusted CLI obtains explicit human acceptance."""

        approval = self._binder.approve(
            proposal,
            approved_item_ids=proposal.item_ids,
            approved_scopes=proposal.scopes,
        )
        return session.send(proposal.content, approval=approval)
