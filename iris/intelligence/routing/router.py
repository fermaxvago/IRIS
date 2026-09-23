"""Composition boundary for intelligence candidate resolution and selection."""

from iris.intelligence.routing.contracts import RoutingPolicy
from iris.intelligence.routing.models import (
    IntelligenceNeed,
    IntelligenceResource,
    IntelligenceRoute,
    IntelligenceRouteReason,
    IntelligenceRouteStatus,
)
from iris.intelligence.routing.policies import DeterministicRoutingPolicy
from iris.intelligence.routing.resolver import CandidateResolver


class RoutingPolicyContractError(ValueError):
    """Raised when a policy returns something outside the candidate set."""


class IntelligenceRouter:
    """Route one need without performing inference or other side effects."""

    def __init__(
        self,
        *,
        resolver: CandidateResolver | None = None,
        policy: RoutingPolicy | None = None,
    ) -> None:
        self._resolver = CandidateResolver() if resolver is None else resolver
        self._policy = DeterministicRoutingPolicy() if policy is None else policy

    def route(
        self,
        need: IntelligenceNeed,
        resources: tuple[IntelligenceResource, ...],
    ) -> IntelligenceRoute:
        """Resolve requirements, then select by preferences deterministically."""

        resolution = self._resolver.resolve(need, resources)
        if not resolution.candidates:
            return IntelligenceRoute(
                status=IntelligenceRouteStatus.UNSATISFIED,
                reason=IntelligenceRouteReason.NO_VALID_CANDIDATE,
                resolution=resolution,
            )

        selected = self._policy.select(need, resolution.candidates)
        if not isinstance(selected, IntelligenceResource):
            raise RoutingPolicyContractError(
                "routing policy must return an IntelligenceResource"
            )
        if selected not in resolution.candidates:
            raise RoutingPolicyContractError(
                "routing policy selected a resource outside the candidate set"
            )

        unmet = tuple(
            preference
            for preference in need.preferences.preferred_affinities
            if preference not in selected.affinities
        )
        if unmet:
            return IntelligenceRoute(
                status=IntelligenceRouteStatus.DEGRADED,
                reason=IntelligenceRouteReason.PREFERENCES_DEGRADED,
                resolution=resolution,
                selected_resource=selected,
                unmet_preferences=unmet,
            )
        return IntelligenceRoute(
            status=IntelligenceRouteStatus.EXACT,
            reason=IntelligenceRouteReason.ALL_PREFERENCES_SATISFIED,
            resolution=resolution,
            selected_resource=selected,
        )
