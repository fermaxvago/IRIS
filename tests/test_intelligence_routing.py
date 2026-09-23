from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass, field

import pytest

from iris.intelligence import (
    CandidateRejectionReason,
    CandidateResolver,
    DeterministicRoutingPolicy,
    DuplicateIntelligenceResourceError,
    IntelligenceNeed,
    IntelligencePreferences,
    IntelligenceRequest,
    IntelligenceRequirements,
    IntelligenceResource,
    IntelligenceResult,
    IntelligenceRouter,
    IntelligenceRouteReason,
    IntelligenceRouteStatus,
    IntelligenceRuntime,
    ModelAffinity,
    ModelCapability,
    ModelDescriptor,
    ModelLocation,
    ProviderRegistry,
    RoutingPolicy,
    RoutingPolicyContractError,
)


def make_resource(
    model_id: str = "model-a",
    *,
    provider_id: str = "provider-a",
    location: ModelLocation = ModelLocation.LOCAL,
    capabilities: frozenset[ModelCapability] | None = None,
    available: bool = True,
    affinities: frozenset[ModelAffinity] = frozenset(),
) -> IntelligenceResource:
    return IntelligenceResource(
        model=ModelDescriptor(
            model_id=model_id,
            provider_id=provider_id,
            location=location,
            capabilities=(
                frozenset({ModelCapability.TEXT_GENERATION})
                if capabilities is None
                else capabilities
            ),
            available=available,
        ),
        affinities=affinities,
    )


def local_text_need(
    *preferred_affinities: ModelAffinity,
) -> IntelligenceNeed:
    return IntelligenceNeed(
        requirements=IntelligenceRequirements(
            capabilities=frozenset({ModelCapability.TEXT_GENERATION}),
            required_location=ModelLocation.LOCAL,
        ),
        preferences=IntelligencePreferences(preferred_affinities),
    )


def test_need_is_provider_neutral_validated_copied_and_immutable() -> None:
    metadata = {"purpose": "analysis"}
    need = IntelligenceNeed(metadata=metadata)

    metadata["purpose"] = "changed"

    assert need.requirements.capabilities == frozenset(
        {ModelCapability.TEXT_GENERATION}
    )
    assert need.requirements.required_location is None
    assert need.metadata["purpose"] == "analysis"
    assert not hasattr(need, "provider_id")
    assert not hasattr(need, "model_id")
    with pytest.raises(TypeError):
        need.metadata["new"] = True  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        need.requirements = IntelligenceRequirements()  # type: ignore[misc]


def test_requirements_and_preferences_validate_domain_values() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        IntelligenceRequirements(capabilities=frozenset())
    with pytest.raises(TypeError, match="ModelCapability"):
        IntelligenceRequirements(
            capabilities=frozenset({"text_generation"})  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError, match="ModelLocation"):
        IntelligenceRequirements(required_location="local")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="duplicates"):
        IntelligencePreferences((ModelAffinity.CODE, ModelAffinity.CODE))


def test_resource_reuses_model_descriptor_and_freezes_routing_metadata() -> None:
    affinities = {ModelAffinity.CODE}
    metadata = {"source": "configured"}
    resource = IntelligenceResource(
        model=make_resource().model,
        affinities=affinities,
        metadata=metadata,
    )

    affinities.clear()
    metadata["source"] = "changed"

    assert resource.provider_id == "provider-a"
    assert resource.model_id == "model-a"
    assert resource.affinities == frozenset({ModelAffinity.CODE})
    assert resource.metadata["source"] == "configured"
    with pytest.raises(TypeError):
        resource.metadata["new"] = True  # type: ignore[index]


def test_candidate_resolver_accepts_a_single_valid_resource() -> None:
    resource = make_resource()

    resolution = CandidateResolver().resolve(local_text_need(), (resource,))

    assert resolution.candidates == (resource,)
    assert resolution.rejections == ()


def test_candidate_resolver_rejects_missing_capability() -> None:
    embedding_only = make_resource(capabilities=frozenset({ModelCapability.EMBEDDING}))

    resolution = CandidateResolver().resolve(local_text_need(), (embedding_only,))

    assert resolution.candidates == ()
    assert resolution.rejections[0].reasons == (
        CandidateRejectionReason.MISSING_CAPABILITY,
    )


def test_candidate_resolver_rejects_location_mismatch() -> None:
    cloud = make_resource(location=ModelLocation.CLOUD)

    resolution = CandidateResolver().resolve(local_text_need(), (cloud,))

    assert resolution.candidates == ()
    assert resolution.rejections[0].reasons == (
        CandidateRejectionReason.LOCATION_MISMATCH,
    )


def test_candidate_resolver_rejects_unavailable_resource() -> None:
    unavailable = make_resource(available=False)

    resolution = CandidateResolver().resolve(local_text_need(), (unavailable,))

    assert resolution.candidates == ()
    assert resolution.rejections[0].reasons == (CandidateRejectionReason.UNAVAILABLE,)


def test_candidate_resolver_reports_all_hard_constraint_failures() -> None:
    invalid = make_resource(
        location=ModelLocation.CLOUD,
        capabilities=frozenset({ModelCapability.EMBEDDING}),
        available=False,
    )

    resolution = CandidateResolver().resolve(local_text_need(), (invalid,))

    assert resolution.rejections[0].reasons == (
        CandidateRejectionReason.UNAVAILABLE,
        CandidateRejectionReason.MISSING_CAPABILITY,
        CandidateRejectionReason.LOCATION_MISMATCH,
    )


def test_candidate_resolution_is_deterministic_and_rejects_duplicates() -> None:
    zulu = make_resource("zulu", provider_id="provider-z")
    alpha = make_resource("alpha", provider_id="provider-a")
    resolver = CandidateResolver()

    first = resolver.resolve(local_text_need(), (zulu, alpha))
    second = resolver.resolve(local_text_need(), (alpha, zulu))

    assert first == second
    assert first.candidates == (alpha, zulu)
    with pytest.raises(DuplicateIntelligenceResourceError):
        resolver.resolve(local_text_need(), (alpha, alpha))


def test_policy_contract_is_structural_and_selects_ordered_affinity() -> None:
    policy = DeterministicRoutingPolicy()
    assert isinstance(policy, RoutingPolicy)
    code = make_resource(
        "code",
        affinities=frozenset({ModelAffinity.CODE}),
    )
    reasoning = make_resource(
        "reasoning",
        affinities=frozenset({ModelAffinity.REASONING}),
    )
    need = local_text_need(ModelAffinity.REASONING, ModelAffinity.CODE)

    assert policy.select(need, (code, reasoning)) is reasoning


def test_route_is_exact_when_all_preferences_are_met() -> None:
    resource = make_resource(
        affinities=frozenset({ModelAffinity.REASONING, ModelAffinity.CODE})
    )

    route = IntelligenceRouter().route(
        local_text_need(ModelAffinity.REASONING, ModelAffinity.CODE),
        (resource,),
    )

    assert route.status is IntelligenceRouteStatus.EXACT
    assert route.reason is IntelligenceRouteReason.ALL_PREFERENCES_SATISFIED
    assert route.selected_resource is resource
    assert route.unmet_preferences == ()


def test_route_is_degraded_only_for_unmet_preferences() -> None:
    resource = make_resource(affinities=frozenset({ModelAffinity.REASONING}))

    route = IntelligenceRouter().route(
        local_text_need(ModelAffinity.REASONING, ModelAffinity.CODE),
        (resource,),
    )

    assert route.status is IntelligenceRouteStatus.DEGRADED
    assert route.reason is IntelligenceRouteReason.PREFERENCES_DEGRADED
    assert route.selected_resource is resource
    assert route.unmet_preferences == (ModelAffinity.CODE,)


def test_route_is_unsatisfied_when_no_resource_meets_requirements() -> None:
    cloud = make_resource(location=ModelLocation.CLOUD)

    route = IntelligenceRouter().route(local_text_need(), (cloud,))

    assert route.status is IntelligenceRouteStatus.UNSATISFIED
    assert route.reason is IntelligenceRouteReason.NO_VALID_CANDIDATE
    assert route.selected_resource is None
    assert route.resolution.candidates == ()


def test_preference_cannot_override_locality_or_trigger_cloud_fallback() -> None:
    local = make_resource("local", affinities=frozenset())
    cloud = make_resource(
        "cloud",
        provider_id="cloud-provider",
        location=ModelLocation.CLOUD,
        affinities=frozenset({ModelAffinity.REASONING}),
    )

    route = IntelligenceRouter().route(
        local_text_need(ModelAffinity.REASONING),
        (cloud, local),
    )

    assert route.status is IntelligenceRouteStatus.DEGRADED
    assert route.selected_resource is local
    assert cloud not in route.resolution.candidates
    assert route.resolution.rejections[0].reasons == (
        CandidateRejectionReason.LOCATION_MISMATCH,
    )


def test_multiple_candidates_use_stable_identity_tiebreaker() -> None:
    zulu = make_resource("model-z", provider_id="provider-z")
    alpha_later_model = make_resource("model-b", provider_id="provider-a")
    alpha_first_model = make_resource("model-a", provider_id="provider-a")
    resources = (zulu, alpha_later_model, alpha_first_model)
    router = IntelligenceRouter()

    selections = [
        router.route(local_text_need(), ordering).selected_resource
        for ordering in (resources, tuple(reversed(resources)), resources)
    ]

    assert selections == [alpha_first_model, alpha_first_model, alpha_first_model]


def test_same_need_resources_and_policy_produce_same_route() -> None:
    resources = (
        make_resource("one", affinities=frozenset({ModelAffinity.CODE})),
        make_resource("two", affinities=frozenset({ModelAffinity.REASONING})),
    )
    need = local_text_need(ModelAffinity.CODE)
    router = IntelligenceRouter()

    assert router.route(need, resources) == router.route(need, resources)


def test_router_rejects_policy_attempt_to_escape_candidate_set() -> None:
    local = make_resource("local")
    prohibited_cloud = make_resource(
        "cloud",
        location=ModelLocation.CLOUD,
    )

    class InvalidPolicy:
        def select(
            self,
            need: IntelligenceNeed,
            candidates: tuple[IntelligenceResource, ...],
        ) -> IntelligenceResource:
            return prohibited_cloud

    router = IntelligenceRouter(policy=InvalidPolicy())

    with pytest.raises(RoutingPolicyContractError, match="outside"):
        router.route(local_text_need(), (local, prohibited_cloud))


@dataclass
class RuntimeProvider:
    provider_id: str
    model: ModelDescriptor
    fail: bool = False
    requests: list[IntelligenceRequest] = field(default_factory=list)

    def list_models(self) -> tuple[ModelDescriptor, ...]:
        return (self.model,)

    def infer(self, request: IntelligenceRequest) -> IntelligenceResult:
        self.requests.append(request)
        if self.fail:
            return IntelligenceResult.failed(
                request,
                provider_id=self.provider_id,
                diagnostic="execution failed",
            )
        return IntelligenceResult.succeeded(
            request,
            provider_id=self.provider_id,
            output="routed response",
        )


@pytest.mark.parametrize("execution_fails", [False, True])
def test_selected_route_integrates_with_runtime_without_reclassifying_execution(
    execution_fails: bool,
) -> None:
    resource = make_resource("neutral-model", provider_id="neutral-provider")
    route = IntelligenceRouter().route(local_text_need(), (resource,))
    selected = route.selected_resource
    assert selected is not None
    provider = RuntimeProvider(
        provider_id=selected.provider_id,
        model=selected.model,
        fail=execution_fails,
    )
    runtime = IntelligenceRuntime(ProviderRegistry([provider]))
    request = IntelligenceRequest(
        content="Use the selected resource",
        model_id=selected.model_id,
    )

    result = runtime.execute(selected.provider_id, request)

    assert route.status is IntelligenceRouteStatus.EXACT
    assert result.success is not execution_fails
    assert provider.requests == [request]


def test_routing_has_no_provider_or_inference_side_effects() -> None:
    resource = make_resource()
    provider = RuntimeProvider(provider_id=resource.provider_id, model=resource.model)

    route = IntelligenceRouter().route(local_text_need(), (resource,))

    assert route.status is IntelligenceRouteStatus.EXACT
    assert provider.requests == []
