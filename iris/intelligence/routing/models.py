"""Provider-neutral domain models for deterministic intelligence routing."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from iris.intelligence.models import ModelCapability, ModelDescriptor, ModelLocation


def _freeze_mapping(
    value: Mapping[str, object],
    *,
    field_name: str,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    if not all(isinstance(key, str) for key in value):
        raise TypeError(f"{field_name} keys must be strings")
    return MappingProxyType(dict(value))


class ModelAffinity(StrEnum):
    """Declarative routing profiles, distinct from technical capabilities.

    Affinities are evidence supplied by resource configuration. The router does
    not infer them from model or provider names.
    """

    GENERAL = "general"
    REASONING = "reasoning"
    CODE = "code"
    FAST_RESPONSE = "fast_response"
    RESOURCE_EFFICIENT = "resource_efficient"


@dataclass(frozen=True, slots=True)
class IntelligenceRequirements:
    """Hard constraints that every candidate resource must satisfy."""

    capabilities: frozenset[ModelCapability] = field(
        default_factory=lambda: frozenset({ModelCapability.TEXT_GENERATION})
    )
    required_location: ModelLocation | None = None

    def __post_init__(self) -> None:
        if isinstance(self.capabilities, (str, bytes)):
            raise TypeError(
                "capabilities must be a collection of ModelCapability values"
            )
        try:
            capabilities = frozenset(self.capabilities)
        except TypeError as exc:
            raise TypeError(
                "capabilities must be a collection of ModelCapability values"
            ) from exc
        if not capabilities:
            raise ValueError("capabilities must not be empty")
        if not all(
            isinstance(capability, ModelCapability) for capability in capabilities
        ):
            raise TypeError("capabilities must contain ModelCapability values")
        if self.required_location is not None and not isinstance(
            self.required_location, ModelLocation
        ):
            raise TypeError("required_location must be a ModelLocation or None")
        object.__setattr__(self, "capabilities", capabilities)


@dataclass(frozen=True, slots=True)
class IntelligencePreferences:
    """Ordered soft preferences used only after hard-constraint filtering."""

    preferred_affinities: tuple[ModelAffinity, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.preferred_affinities, (str, bytes)):
            raise TypeError(
                "preferred_affinities must be a collection of ModelAffinity values"
            )
        try:
            affinities = tuple(self.preferred_affinities)
        except TypeError as exc:
            raise TypeError(
                "preferred_affinities must be a collection of ModelAffinity values"
            ) from exc
        if not all(isinstance(affinity, ModelAffinity) for affinity in affinities):
            raise TypeError("preferred_affinities must contain ModelAffinity values")
        if len(affinities) != len(set(affinities)):
            raise ValueError("preferred_affinities must not contain duplicates")
        object.__setattr__(self, "preferred_affinities", affinities)


@dataclass(frozen=True, slots=True)
class IntelligenceNeed:
    """One provider- and model-neutral cognitive need to be routed."""

    requirements: IntelligenceRequirements = field(
        default_factory=IntelligenceRequirements
    )
    preferences: IntelligencePreferences = field(
        default_factory=IntelligencePreferences
    )
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.requirements, IntelligenceRequirements):
            raise TypeError("requirements must be IntelligenceRequirements")
        if not isinstance(self.preferences, IntelligencePreferences):
            raise TypeError("preferences must be IntelligencePreferences")
        object.__setattr__(
            self,
            "metadata",
            _freeze_mapping(self.metadata, field_name="metadata"),
        )


@dataclass(frozen=True, slots=True)
class IntelligenceResource:
    """A routable provider/model pair plus explicit routing-only metadata."""

    model: ModelDescriptor
    affinities: frozenset[ModelAffinity] = field(default_factory=frozenset)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.model, ModelDescriptor):
            raise TypeError("model must be a ModelDescriptor")
        if isinstance(self.affinities, (str, bytes)):
            raise TypeError("affinities must be a collection of ModelAffinity values")
        try:
            affinities = frozenset(self.affinities)
        except TypeError as exc:
            raise TypeError(
                "affinities must be a collection of ModelAffinity values"
            ) from exc
        if not all(isinstance(affinity, ModelAffinity) for affinity in affinities):
            raise TypeError("affinities must contain ModelAffinity values")
        object.__setattr__(self, "affinities", affinities)
        object.__setattr__(
            self,
            "metadata",
            _freeze_mapping(self.metadata, field_name="metadata"),
        )

    @property
    def provider_id(self) -> str:
        """Return the provider selected by this concrete resource."""

        return self.model.provider_id

    @property
    def model_id(self) -> str:
        """Return the model selected by this concrete resource."""

        return self.model.model_id


class CandidateRejectionReason(StrEnum):
    """Structured hard-constraint rejection reasons."""

    UNAVAILABLE = "unavailable"
    MISSING_CAPABILITY = "missing_capability"
    LOCATION_MISMATCH = "location_mismatch"


@dataclass(frozen=True, slots=True)
class CandidateRejection:
    """Record why one resource was excluded from the candidate set."""

    resource: IntelligenceResource
    reasons: tuple[CandidateRejectionReason, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.resource, IntelligenceResource):
            raise TypeError("resource must be an IntelligenceResource")
        if isinstance(self.reasons, (str, bytes)):
            raise TypeError(
                "reasons must be a collection of CandidateRejectionReason values"
            )
        try:
            reasons = tuple(self.reasons)
        except TypeError as exc:
            raise TypeError(
                "reasons must be a collection of CandidateRejectionReason values"
            ) from exc
        if not reasons:
            raise ValueError("candidate rejection requires at least one reason")
        if not all(isinstance(reason, CandidateRejectionReason) for reason in reasons):
            raise TypeError("reasons must contain CandidateRejectionReason values")
        if len(reasons) != len(set(reasons)):
            raise ValueError("candidate rejection reasons must not contain duplicates")
        object.__setattr__(self, "reasons", reasons)


@dataclass(frozen=True, slots=True)
class CandidateResolution:
    """Deterministic output of hard-constraint filtering."""

    candidates: tuple[IntelligenceResource, ...]
    rejections: tuple[CandidateRejection, ...]

    def __post_init__(self) -> None:
        if isinstance(self.candidates, (str, bytes)):
            raise TypeError("candidates must be a collection of resources")
        if isinstance(self.rejections, (str, bytes)):
            raise TypeError("rejections must be a collection of candidate rejections")
        try:
            candidates = tuple(self.candidates)
            rejections = tuple(self.rejections)
        except TypeError as exc:
            raise TypeError("candidate resolution values must be collections") from exc
        if not all(
            isinstance(candidate, IntelligenceResource) for candidate in candidates
        ):
            raise TypeError("candidates must contain IntelligenceResource values")
        if not all(
            isinstance(rejection, CandidateRejection) for rejection in rejections
        ):
            raise TypeError("rejections must contain CandidateRejection values")
        candidate_identities = {
            (candidate.provider_id, candidate.model_id) for candidate in candidates
        }
        rejected_identities = {
            (rejection.resource.provider_id, rejection.resource.model_id)
            for rejection in rejections
        }
        if len(candidate_identities) != len(candidates):
            raise ValueError("candidates must not repeat resource identities")
        if len(rejected_identities) != len(rejections):
            raise ValueError("rejections must not repeat resource identities")
        if candidate_identities & rejected_identities:
            raise ValueError("a resource cannot be both accepted and rejected")
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "rejections", rejections)


class IntelligenceRouteStatus(StrEnum):
    """Outcome of selecting one resource for an IntelligenceNeed."""

    EXACT = "exact"
    DEGRADED = "degraded"
    UNSATISFIED = "unsatisfied"


class IntelligenceRouteReason(StrEnum):
    """Stable diagnostic reason for a routing outcome."""

    ALL_PREFERENCES_SATISFIED = "all_preferences_satisfied"
    PREFERENCES_DEGRADED = "preferences_degraded"
    NO_VALID_CANDIDATE = "no_valid_candidate"


@dataclass(frozen=True, slots=True)
class IntelligenceRoute:
    """Inspectable routing outcome; it never represents inference execution."""

    status: IntelligenceRouteStatus
    reason: IntelligenceRouteReason
    resolution: CandidateResolution
    selected_resource: IntelligenceResource | None = None
    unmet_preferences: tuple[ModelAffinity, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, IntelligenceRouteStatus):
            raise TypeError("status must be an IntelligenceRouteStatus")
        if not isinstance(self.reason, IntelligenceRouteReason):
            raise TypeError("reason must be an IntelligenceRouteReason")
        if not isinstance(self.resolution, CandidateResolution):
            raise TypeError("resolution must be a CandidateResolution")
        if isinstance(self.unmet_preferences, (str, bytes)):
            raise TypeError("unmet_preferences must be a collection of affinities")
        try:
            unmet_preferences = tuple(self.unmet_preferences)
        except TypeError as exc:
            raise TypeError(
                "unmet_preferences must be a collection of affinities"
            ) from exc
        if not all(
            isinstance(preference, ModelAffinity) for preference in unmet_preferences
        ):
            raise TypeError("unmet_preferences must contain ModelAffinity values")
        if len(unmet_preferences) != len(set(unmet_preferences)):
            raise ValueError("unmet_preferences must not contain duplicates")
        object.__setattr__(self, "unmet_preferences", unmet_preferences)

        if self.status is IntelligenceRouteStatus.UNSATISFIED:
            if self.selected_resource is not None:
                raise ValueError("unsatisfied routes cannot select a resource")
            if self.reason is not IntelligenceRouteReason.NO_VALID_CANDIDATE:
                raise ValueError("unsatisfied routes require NO_VALID_CANDIDATE")
            if self.resolution.candidates:
                raise ValueError("unsatisfied routes cannot contain valid candidates")
            if self.unmet_preferences:
                raise ValueError(
                    "unsatisfied routes cannot report preference degradation"
                )
            return

        if self.selected_resource is None:
            raise ValueError("satisfied routes require a selected resource")
        if self.selected_resource not in self.resolution.candidates:
            raise ValueError("selected resource must belong to the candidate set")
        if self.status is IntelligenceRouteStatus.EXACT:
            if self.reason is not IntelligenceRouteReason.ALL_PREFERENCES_SATISFIED:
                raise ValueError("exact routes require ALL_PREFERENCES_SATISFIED")
            if self.unmet_preferences:
                raise ValueError("exact routes cannot contain unmet preferences")
        if self.status is IntelligenceRouteStatus.DEGRADED:
            if self.reason is not IntelligenceRouteReason.PREFERENCES_DEGRADED:
                raise ValueError("degraded routes require PREFERENCES_DEGRADED")
            if not self.unmet_preferences:
                raise ValueError("degraded routes require unmet preferences")
