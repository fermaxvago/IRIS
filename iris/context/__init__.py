"""Bounded, ephemeral context for one IRIS request."""

from iris.context.contracts import ContextSelectionPolicy
from iris.context.engine import ContextEngine, ContextPolicyContractError
from iris.context.models import (
    ConflictReason,
    ContextBudget,
    ContextCandidate,
    ContextConflict,
    ContextEvidence,
    ContextItem,
    ContextKind,
    ContextSnapshot,
    ContextUncertainty,
    EvidenceSource,
    Freshness,
    Relevance,
    ResolutionStatus,
    UncertaintyReason,
)
from iris.context.selection import (
    DeterministicContextSelection,
    DuplicateContextCandidateError,
)
from iris.context.sources import MemoryContextSource

__all__ = [
    "ConflictReason",
    "ContextBudget",
    "ContextCandidate",
    "ContextConflict",
    "ContextEngine",
    "ContextEvidence",
    "ContextItem",
    "ContextKind",
    "ContextPolicyContractError",
    "ContextSelectionPolicy",
    "ContextSnapshot",
    "ContextUncertainty",
    "DeterministicContextSelection",
    "DuplicateContextCandidateError",
    "EvidenceSource",
    "Freshness",
    "MemoryContextSource",
    "Relevance",
    "ResolutionStatus",
    "UncertaintyReason",
]
