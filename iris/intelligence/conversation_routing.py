"""Explicit discovery, recommendation, and confirmed local chat binding."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType

from iris.intelligence.contracts import (
    ConversationalIntelligenceProvider,
    IntelligenceProvider,
)
from iris.intelligence.conversation import ConversationSession
from iris.intelligence.models import ModelCapability, ModelDescriptor, ModelLocation
from iris.intelligence.registry import ProviderRegistry
from iris.intelligence.routing import (
    CandidateResolver,
    IntelligenceNeed,
    IntelligencePreferences,
    IntelligenceRequirements,
    IntelligenceResource,
    IntelligenceRoute,
    IntelligenceRouter,
    IntelligenceRouteStatus,
    ModelAffinity,
)
from iris.intelligence.runtime import IntelligenceRuntime


class ConversationDiscoveryError(RuntimeError):
    """A registered provider's inventory could not be obtained."""


class ConversationDiscoveryContractError(ValueError):
    """A registered provider returned contradictory inventory data."""


class ConversationBindingError(RuntimeError):
    """The exact confirmed conversational resource is no longer eligible."""


class ConversationRouteContractError(ValueError):
    """The delegated route contradicts the declared conversational need."""


def local_conversation_need(
    preferences: IntelligencePreferences | None = None,
) -> IntelligenceNeed:
    """Require a local conversational model; affinities remain optional."""

    return IntelligenceNeed(
        requirements=IntelligenceRequirements(
            capabilities=frozenset({ModelCapability.CONVERSATION}),
            required_location=ModelLocation.LOCAL,
        ),
        preferences=(IntelligencePreferences() if preferences is None else preferences),
    )


def resource_from_descriptor(
    descriptor: ModelDescriptor,
    *,
    affinities: frozenset[ModelAffinity] = frozenset(),
) -> IntelligenceResource:
    """Adapt a descriptor without inventing capability or performance claims."""

    return IntelligenceResource(
        model=descriptor, affinities=affinities, metadata=descriptor.metadata
    )


@dataclass(frozen=True, slots=True)
class ConversationRouteProposal:
    """Inspectable recommendation only; neither binding nor inference."""

    need: IntelligenceNeed
    route: IntelligenceRoute
    unsupported_chat_providers: tuple[str, ...] = ()
    provenance: str = field(default="policy_recommendation", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.need, IntelligenceNeed):
            raise TypeError("need must be an IntelligenceNeed")
        if not isinstance(self.route, IntelligenceRoute):
            raise TypeError("route must be an IntelligenceRoute")
        _require_local_conversation(self.need)
        if not isinstance(self.unsupported_chat_providers, tuple) or not all(
            isinstance(value, str) and value.strip() == value and value
            for value in self.unsupported_chat_providers
        ):
            raise TypeError("unsupported_chat_providers must contain identifiers")

    @property
    def selected_identity(self) -> tuple[str, str] | None:
        resource = self.route.selected_resource
        return None if resource is None else (resource.provider_id, resource.model_id)

    @property
    def explanation(self) -> str:
        """Describe actual router evidence, not relative model quality."""

        parts = [f"Ruta: {self.route.status.value} ({self.route.reason.value})."]
        if self.selected_identity is not None:
            parts.append("Recurso: " + "/".join(self.selected_identity) + ".")
        if self.route.unmet_preferences:
            parts.append(
                "Preferencias no cumplidas: "
                + ", ".join(value.value for value in self.route.unmet_preferences)
                + "."
            )
        for rejection in self.route.resolution.rejections:
            parts.append(
                f"Excluido {rejection.resource.provider_id}/"
                f"{rejection.resource.model_id}: "
                + ", ".join(reason.value for reason in rejection.reasons)
                + "."
            )
        if self.unsupported_chat_providers:
            parts.append(
                "Proveedor sin chat: "
                + ", ".join(self.unsupported_chat_providers)
                + "."
            )
        return " ".join(parts)


class ConversationRouteBinder:
    """Use canonical registry/router/runtime; never infer during selection."""

    def __init__(
        self,
        registry: ProviderRegistry,
        *,
        router: IntelligenceRouter | None = None,
        affinities: Mapping[tuple[str, str], frozenset[ModelAffinity]] | None = None,
    ) -> None:
        if not isinstance(registry, ProviderRegistry):
            raise TypeError("registry must be a ProviderRegistry")
        if router is not None and not isinstance(router, IntelligenceRouter):
            raise TypeError("router must be an IntelligenceRouter")
        self._registry = registry
        self._router = IntelligenceRouter() if router is None else router
        self._runtime = IntelligenceRuntime(registry)
        self._affinities = _validated_affinities(affinities)

    def discover(self) -> tuple[ModelDescriptor, ...]:
        """Fail closed if any registered inventory fails or violates contract."""

        descriptors: list[ModelDescriptor] = []
        identities: set[tuple[str, str]] = set()
        for provider in self._registry.list_providers():
            if not isinstance(provider, IntelligenceProvider):
                raise ConversationDiscoveryContractError(
                    f"registered provider lacks inventory contract: {provider.provider_id}"
                )
            try:
                models = provider.list_models()
            except Exception as exc:
                raise ConversationDiscoveryError(
                    f"inventory failed for provider {provider.provider_id}"
                ) from exc
            if not isinstance(models, tuple):
                raise ConversationDiscoveryContractError(
                    f"inventory is not a tuple for provider {provider.provider_id}"
                )
            for descriptor in models:
                if not isinstance(descriptor, ModelDescriptor):
                    raise ConversationDiscoveryContractError(
                        f"invalid model descriptor from {provider.provider_id}"
                    )
                try:
                    canonical = replace(descriptor)
                except (TypeError, ValueError) as exc:
                    raise ConversationDiscoveryContractError(
                        f"malformed descriptor from {provider.provider_id}"
                    ) from exc
                if (
                    canonical != descriptor
                    or descriptor.provider_id != provider.provider_id
                ):
                    raise ConversationDiscoveryContractError(
                        f"foreign or noncanonical descriptor from {provider.provider_id}"
                    )
                identity = (descriptor.provider_id, descriptor.model_id)
                if identity in identities:
                    raise ConversationDiscoveryContractError(
                        f"duplicate model identity: {'/'.join(identity)}"
                    )
                identities.add(identity)
                descriptors.append(descriptor)
        unknown = set(self._affinities) - identities
        if unknown:
            raise ConversationDiscoveryContractError(
                "affinity configuration references an undiscovered model"
            )
        return tuple(
            sorted(descriptors, key=lambda model: (model.provider_id, model.model_id))
        )

    def propose(
        self,
        need: IntelligenceNeed | None = None,
    ) -> ConversationRouteProposal:
        """Route validated registered resources without creating a session."""

        active_need = local_conversation_need() if need is None else need
        _require_local_conversation(active_need)
        descriptors = self.discover()
        resources: list[IntelligenceResource] = []
        unsupported: set[str] = set()
        for descriptor in descriptors:
            provider = self._registry.get(descriptor.provider_id)
            if not isinstance(provider, ConversationalIntelligenceProvider):
                unsupported.add(descriptor.provider_id)
                continue
            resources.append(
                resource_from_descriptor(
                    descriptor,
                    affinities=self._affinities.get(
                        (descriptor.provider_id, descriptor.model_id), frozenset()
                    ),
                )
            )
        route = self._router.route(active_need, tuple(resources))
        if not isinstance(route, IntelligenceRoute):
            raise ConversationRouteContractError("router returned an invalid route")
        expected = CandidateResolver().resolve(active_need, tuple(resources))
        if route.resolution != expected or any(
            actual is not canonical
            for actual, canonical in zip(
                (
                    *route.resolution.candidates,
                    *(r.resource for r in route.resolution.rejections),
                ),
                (*expected.candidates, *(r.resource for r in expected.rejections)),
                strict=True,
            )
        ):
            raise ConversationRouteContractError(
                "router resolution contradicts discovered resources"
            )
        selected = route.selected_resource
        if selected is not None:
            if not any(selected is candidate for candidate in expected.candidates):
                raise ConversationRouteContractError(
                    "router selected a noncanonical resource"
                )
            expected_unmet = tuple(
                value
                for value in active_need.preferences.preferred_affinities
                if value not in selected.affinities
            )
            if route.unmet_preferences != expected_unmet:
                raise ConversationRouteContractError(
                    "router preference evidence contradicts the need"
                )
        return ConversationRouteProposal(
            need=active_need,
            route=route,
            unsupported_chat_providers=tuple(sorted(unsupported)),
        )

    def bind(self, proposal: ConversationRouteProposal) -> ConversationSession:
        """Bind the exact accepted pair after fresh inventory validation."""

        if not isinstance(proposal, ConversationRouteProposal):
            raise TypeError("proposal must be a ConversationRouteProposal")
        _require_local_conversation(proposal.need)
        identity = proposal.selected_identity
        if (
            identity is None
            or proposal.route.status is IntelligenceRouteStatus.UNSATISFIED
        ):
            raise ConversationBindingError("unsatisfied route cannot create a session")
        # Re-query all registered inventories; never silently ignore a failed provider.
        descriptors = self.discover()
        selected = next(
            (
                descriptor
                for descriptor in descriptors
                if (descriptor.provider_id, descriptor.model_id) == identity
            ),
            None,
        )
        if selected is None:
            raise ConversationBindingError("confirmed model disappeared before binding")
        provider = self._registry.get(identity[0])
        if not isinstance(provider, ConversationalIntelligenceProvider):
            raise ConversationBindingError("confirmed provider no longer supports chat")
        resource = resource_from_descriptor(selected)
        if not CandidateResolver().resolve(proposal.need, (resource,)).candidates:
            raise ConversationBindingError(
                "confirmed model no longer meets requirements"
            )
        return ConversationSession(
            self._runtime, provider_id=identity[0], model_id=identity[1]
        )


def _require_local_conversation(need: IntelligenceNeed) -> None:
    if not isinstance(need, IntelligenceNeed):
        raise TypeError("need must be an IntelligenceNeed")
    requirements = need.requirements
    if (
        requirements.required_location is not ModelLocation.LOCAL
        or ModelCapability.CONVERSATION not in requirements.capabilities
    ):
        raise ValueError("conversational routing requires LOCAL and CONVERSATION")


def _validated_affinities(
    values: Mapping[tuple[str, str], frozenset[ModelAffinity]] | None,
) -> Mapping[tuple[str, str], frozenset[ModelAffinity]]:
    if values is None:
        return MappingProxyType({})
    if not isinstance(values, Mapping):
        raise TypeError("affinities must be a mapping")
    normalized: dict[tuple[str, str], frozenset[ModelAffinity]] = {}
    for identity, declared in values.items():
        if (
            not isinstance(identity, tuple)
            or len(identity) != 2
            or not all(
                isinstance(part, str) and part and part.strip() == part
                for part in identity
            )
        ):
            raise TypeError("affinity keys must be exact provider/model pairs")
        if isinstance(declared, (str, bytes)):
            raise TypeError("affinities must contain ModelAffinity values")
        try:
            items = tuple(declared)
        except TypeError as exc:
            raise TypeError("affinities must be a collection") from exc
        if not all(isinstance(item, ModelAffinity) for item in items):
            raise TypeError("affinities must contain ModelAffinity values")
        if len(items) != len(set(items)):
            raise ValueError("affinities must not repeat values")
        normalized[identity] = frozenset(items)
    return MappingProxyType(normalized)
