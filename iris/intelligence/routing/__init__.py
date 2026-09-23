"""Deterministic, provider-neutral intelligence routing for IRIS."""

from iris.intelligence.routing.contracts import RoutingPolicy
from iris.intelligence.routing.models import (
    CandidateRejection,
    CandidateRejectionReason,
    CandidateResolution,
    IntelligenceNeed,
    IntelligencePreferences,
    IntelligenceRequirements,
    IntelligenceResource,
    IntelligenceRoute,
    IntelligenceRouteReason,
    IntelligenceRouteStatus,
    ModelAffinity,
)
from iris.intelligence.routing.policies import (
    DeterministicRoutingPolicy,
    EmptyCandidateSetError,
)
from iris.intelligence.routing.resolver import (
    CandidateResolver,
    DuplicateIntelligenceResourceError,
)
from iris.intelligence.routing.router import (
    IntelligenceRouter,
    RoutingPolicyContractError,
)

__all__ = [
    "CandidateRejection",
    "CandidateRejectionReason",
    "CandidateResolution",
    "CandidateResolver",
    "DeterministicRoutingPolicy",
    "DuplicateIntelligenceResourceError",
    "EmptyCandidateSetError",
    "IntelligenceNeed",
    "IntelligencePreferences",
    "IntelligenceRequirements",
    "IntelligenceResource",
    "IntelligenceRoute",
    "IntelligenceRouteReason",
    "IntelligenceRouteStatus",
    "IntelligenceRouter",
    "ModelAffinity",
    "RoutingPolicy",
    "RoutingPolicyContractError",
]
