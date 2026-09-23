"""Initial deterministic selection policy for valid intelligence resources."""

from iris.intelligence.routing.models import IntelligenceNeed, IntelligenceResource


class EmptyCandidateSetError(ValueError):
    """Raised when a policy is asked to select from no candidates."""


class DeterministicRoutingPolicy:
    """Prefer ordered affinity matches, then stable provider/model identity."""

    def select(
        self,
        need: IntelligenceNeed,
        candidates: tuple[IntelligenceResource, ...],
    ) -> IntelligenceResource:
        if not isinstance(need, IntelligenceNeed):
            raise TypeError("need must be an IntelligenceNeed")
        if not isinstance(candidates, tuple):
            raise TypeError("candidates must be a tuple")
        if not candidates:
            raise EmptyCandidateSetError("cannot select from an empty candidate set")
        if not all(
            isinstance(candidate, IntelligenceResource) for candidate in candidates
        ):
            raise TypeError("candidates must contain IntelligenceResource values")

        ordered = tuple(
            sorted(
                candidates,
                key=lambda resource: (resource.provider_id, resource.model_id),
            )
        )
        preferences = need.preferences.preferred_affinities

        def preference_vector(resource: IntelligenceResource) -> tuple[bool, ...]:
            return tuple(
                preference in resource.affinities for preference in preferences
            )

        return max(ordered, key=preference_vector)
