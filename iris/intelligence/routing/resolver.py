"""Pure hard-constraint resolution for intelligence resources."""

from iris.intelligence.routing.models import (
    CandidateRejection,
    CandidateRejectionReason,
    CandidateResolution,
    IntelligenceNeed,
    IntelligenceResource,
)


class DuplicateIntelligenceResourceError(ValueError):
    """Raised when a candidate input repeats a provider/model identity."""


class CandidateResolver:
    """Determine valid candidates without choosing among them."""

    def resolve(
        self,
        need: IntelligenceNeed,
        resources: tuple[IntelligenceResource, ...],
    ) -> CandidateResolution:
        """Apply availability, capability, and locality requirements."""

        if not isinstance(need, IntelligenceNeed):
            raise TypeError("need must be an IntelligenceNeed")
        if not isinstance(resources, tuple):
            raise TypeError("resources must be a tuple")
        if not all(
            isinstance(resource, IntelligenceResource) for resource in resources
        ):
            raise TypeError("resources must contain IntelligenceResource values")

        ordered = tuple(sorted(resources, key=_resource_identity))
        identities = [_resource_identity(resource) for resource in ordered]
        if len(identities) != len(set(identities)):
            raise DuplicateIntelligenceResourceError(
                "resources must not repeat a provider/model identity"
            )

        candidates: list[IntelligenceResource] = []
        rejections: list[CandidateRejection] = []
        for resource in ordered:
            reasons: list[CandidateRejectionReason] = []
            if not resource.model.available:
                reasons.append(CandidateRejectionReason.UNAVAILABLE)
            if not need.requirements.capabilities.issubset(resource.model.capabilities):
                reasons.append(CandidateRejectionReason.MISSING_CAPABILITY)
            required_location = need.requirements.required_location
            if (
                required_location is not None
                and resource.model.location is not required_location
            ):
                reasons.append(CandidateRejectionReason.LOCATION_MISMATCH)

            if reasons:
                rejections.append(
                    CandidateRejection(resource=resource, reasons=tuple(reasons))
                )
            else:
                candidates.append(resource)

        return CandidateResolution(
            candidates=tuple(candidates),
            rejections=tuple(rejections),
        )


def _resource_identity(resource: IntelligenceResource) -> tuple[str, str]:
    return resource.provider_id, resource.model_id
