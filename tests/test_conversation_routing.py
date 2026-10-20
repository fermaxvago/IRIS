"""Deterministic coverage for WP064 discovery-to-session binding."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest

import iris.__main__ as cli
from iris.intelligence import (
    ConversationBindingError,
    ConversationDiscoveryContractError,
    ConversationDiscoveryError,
    ConversationRouteBinder,
    ConversationRouteContractError,
    IntelligenceNeed,
    IntelligencePreferences,
    IntelligenceRequirements,
    IntelligenceResult,
    IntelligenceRouter,
    ModelAffinity,
    ModelCapability,
    ModelDescriptor,
    ModelLocation,
    ProviderRegistry,
    local_conversation_need,
    resource_from_descriptor,
)
from iris.intelligence.conversation import ConversationRequest
from iris.intelligence.routing import IntelligenceRouteStatus


def model(
    model_id: str,
    *,
    provider_id: str = "local",
    location: ModelLocation = ModelLocation.LOCAL,
    capabilities: frozenset[ModelCapability] = frozenset(
        {ModelCapability.CONVERSATION}
    ),
    available: bool = True,
) -> ModelDescriptor:
    return ModelDescriptor(
        model_id=model_id,
        provider_id=provider_id,
        location=location,
        capabilities=capabilities,
        context_window=4096,
        available=available,
        metadata={"source": "declared"},
    )


class ChatProvider:
    def __init__(self, provider_id: str, models: tuple[ModelDescriptor, ...]) -> None:
        self.provider_id = provider_id
        self.models = models
        self.inventory_calls = 0
        self.chat_calls = 0
        self.discovery_error: Exception | None = None

    def list_models(self) -> tuple[ModelDescriptor, ...]:
        self.inventory_calls += 1
        if self.discovery_error is not None:
            raise self.discovery_error
        return self.models

    def infer(self, request: Any) -> IntelligenceResult:
        raise AssertionError("legacy inference must not run")

    def chat(self, request: ConversationRequest) -> IntelligenceResult:
        self.chat_calls += 1
        return IntelligenceResult.succeeded(
            request, provider_id=self.provider_id, output="respuesta"
        )


class InferOnlyProvider:
    def __init__(self, provider_id: str, models: tuple[ModelDescriptor, ...]) -> None:
        self.provider_id = provider_id
        self.models = models

    def list_models(self) -> tuple[ModelDescriptor, ...]:
        return self.models

    def infer(self, request: Any) -> IntelligenceResult:
        raise AssertionError("legacy inference must not run")


def binder(
    *providers: ChatProvider | InferOnlyProvider, **kwargs: Any
) -> ConversationRouteBinder:
    return ConversationRouteBinder(ProviderRegistry(providers), **kwargs)


def test_single_local_model_proposal_and_exact_binding_without_inference() -> None:
    descriptor = model("m")
    provider = ChatProvider("local", (descriptor,))
    chooser = binder(provider)

    proposal = chooser.propose()

    assert proposal.need.requirements.required_location is ModelLocation.LOCAL
    assert proposal.need.requirements.capabilities == frozenset(
        {ModelCapability.CONVERSATION}
    )
    assert proposal.route.status is IntelligenceRouteStatus.EXACT
    assert proposal.selected_identity == ("local", "m")
    assert proposal.provenance == "policy_recommendation"
    assert proposal.route.selected_resource is not None
    assert proposal.route.selected_resource.model is descriptor
    assert proposal.route.selected_resource.model.context_window == 4096
    assert proposal.route.selected_resource.model.metadata["source"] == "declared"
    assert proposal.route.selected_resource.metadata["source"] == "declared"
    assert proposal.route.selected_resource.affinities == frozenset()
    assert provider.chat_calls == 0
    with pytest.raises(FrozenInstanceError):
        proposal.provenance = "other"  # type: ignore[misc]

    session = chooser.bind(proposal)
    assert (session.provider_id, session.model_id) == ("local", "m")
    assert session.messages == ()
    assert provider.inventory_calls == 2
    assert provider.chat_calls == 0
    assert session.send("hola").success
    assert session.completed_turns == 1


def test_existing_router_is_called_and_controls_deterministic_choice() -> None:
    class SpyRouter(IntelligenceRouter):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[tuple[IntelligenceNeed, tuple[Any, ...]]] = []

        def route(self, need: IntelligenceNeed, resources: tuple[Any, ...]) -> Any:
            self.calls.append((need, resources))
            return super().route(need, resources)

    spy = SpyRouter()
    provider = ChatProvider("local", (model("z"), model("a")))
    chooser = binder(provider, router=spy)
    first = chooser.propose()
    second = chooser.propose()
    assert first.selected_identity == second.selected_identity == ("local", "a")
    assert len(spy.calls) == 2
    assert all(call[0] is not None and len(call[1]) == 2 for call in spy.calls)
    assert provider.chat_calls == 0


def test_forged_router_resolution_is_rejected_without_binding() -> None:
    class ForeignRouter(IntelligenceRouter):
        def route(self, need: IntelligenceNeed, resources: tuple[Any, ...]) -> Any:
            return super().route(need, ())

    provider = ChatProvider("local", (model("m"),))
    with pytest.raises(ConversationRouteContractError):
        binder(provider, router=ForeignRouter()).propose()
    assert provider.chat_calls == 0


@pytest.mark.parametrize(
    ("descriptor", "reason"),
    [
        (model("cloud", location=ModelLocation.CLOUD), "location_mismatch"),
        (
            model("no-chat", capabilities=frozenset({ModelCapability.TEXT_GENERATION})),
            "missing_capability",
        ),
        (model("unavailable", available=False), "unavailable"),
    ],
)
def test_hard_requirements_reject_ineligible_models(
    descriptor: ModelDescriptor, reason: str
) -> None:
    proposal = binder(ChatProvider("local", (descriptor,))).propose()
    assert proposal.route.status is IntelligenceRouteStatus.UNSATISFIED
    assert proposal.selected_identity is None
    assert reason in proposal.explanation


def test_infer_only_provider_cannot_be_selected_even_if_descriptor_claims_chat() -> (
    None
):
    proposal = binder(InferOnlyProvider("local", (model("m"),))).propose()
    assert proposal.route.status is IntelligenceRouteStatus.UNSATISFIED
    assert proposal.unsupported_chat_providers == ("local",)
    assert "Proveedor sin chat" in proposal.explanation


def test_successful_empty_inventory_is_unsatisfied_not_discovery_failure() -> None:
    chooser = binder(ChatProvider("local", ()))
    proposal = chooser.propose()
    assert proposal.route.status is IntelligenceRouteStatus.UNSATISFIED
    with pytest.raises(ConversationBindingError):
        chooser.bind(proposal)


def test_partial_inventory_failure_is_not_unsatisfied() -> None:
    first = ChatProvider("a", (model("m", provider_id="a"),))
    second = ChatProvider("b", ())
    second.discovery_error = OSError("secret\x1b[31m")
    with pytest.raises(ConversationDiscoveryError, match="provider b") as failure:
        binder(first, second).propose()
    assert isinstance(failure.value.__cause__, OSError)
    assert "secret" not in str(failure.value)


@pytest.mark.parametrize(
    "models",
    [
        (model("m"), model("m")),
        (model("m", provider_id="foreign"),),
        ("not-a-descriptor",),
    ],
)
def test_malformed_inventory_is_contract_failure(models: Any) -> None:
    with pytest.raises(ConversationDiscoveryContractError):
        binder(ChatProvider("local", models)).propose()


def test_non_tuple_inventory_is_contract_failure() -> None:
    provider = ChatProvider("local", (model("m"),))
    provider.models = [model("m")]  # type: ignore[assignment]
    with pytest.raises(ConversationDiscoveryContractError, match="tuple"):
        binder(provider).propose()


def test_affinity_declarations_are_explicit_and_drive_existing_router() -> None:
    provider = ChatProvider("local", (model("a"), model("z")))
    preferences = IntelligencePreferences((ModelAffinity.REASONING,))
    chooser = binder(
        provider,
        affinities={("local", "a"): frozenset({ModelAffinity.REASONING})},
    )
    proposal = chooser.propose(local_conversation_need(preferences))
    assert proposal.route.status is IntelligenceRouteStatus.EXACT
    assert proposal.selected_identity == ("local", "a")
    assert proposal.route.unmet_preferences == ()
    assert chooser.bind(proposal).model_id == "a"


def test_missing_affinity_is_unknown_and_degraded_not_inferred() -> None:
    provider = ChatProvider("local", (model("reasoner"),))
    need = local_conversation_need(IntelligencePreferences((ModelAffinity.REASONING,)))
    proposal = binder(provider).propose(need)
    assert proposal.route.status is IntelligenceRouteStatus.DEGRADED
    assert proposal.route.unmet_preferences == (ModelAffinity.REASONING,)
    assert "reasoning" in proposal.explanation


@pytest.mark.parametrize(
    "mapping",
    [
        {("local", "m"): frozenset({"reasoning"})},
        {("local", "m"): (ModelAffinity.CODE, ModelAffinity.CODE)},
        {("local",): frozenset({ModelAffinity.CODE})},
        {"local/m": frozenset({ModelAffinity.CODE})},
    ],
)
def test_invalid_affinity_configuration_is_rejected(mapping: Any) -> None:
    with pytest.raises((TypeError, ValueError)):
        binder(ChatProvider("local", (model("m"),)), affinities=mapping)


def test_affinity_configuration_for_unknown_model_is_contract_failure() -> None:
    chooser = binder(
        ChatProvider("local", (model("m"),)),
        affinities={("local", "missing"): frozenset({ModelAffinity.CODE})},
    )
    with pytest.raises(ConversationDiscoveryContractError):
        chooser.propose()


def test_adapter_preserves_descriptor_without_fabricated_metrics() -> None:
    descriptor = model("m")
    resource = resource_from_descriptor(descriptor)
    assert resource.model is descriptor
    assert resource.affinities == frozenset()
    assert resource.metadata["source"] == "declared"


def test_binding_fails_when_resource_disappears_or_changes_hard_requirements() -> None:
    provider = ChatProvider("local", (model("m"),))
    chooser = binder(provider)
    proposal = chooser.propose()
    provider.models = ()
    with pytest.raises(ConversationBindingError, match="disappeared"):
        chooser.bind(proposal)
    provider.models = (model("m", location=ModelLocation.CLOUD),)
    with pytest.raises(ConversationBindingError, match="requirements"):
        chooser.bind(proposal)
    provider.models = (
        model("m", capabilities=frozenset({ModelCapability.TEXT_GENERATION})),
    )
    with pytest.raises(ConversationBindingError, match="requirements"):
        chooser.bind(proposal)
    assert provider.chat_calls == 0


def test_binding_never_substitutes_an_alternate_model() -> None:
    provider = ChatProvider("local", (model("a"),))
    chooser = binder(provider)
    proposal = chooser.propose()
    provider.models = (model("z"),)
    with pytest.raises(ConversationBindingError, match="disappeared"):
        chooser.bind(proposal)
    assert provider.chat_calls == 0


def test_binding_revalidation_fails_closed_on_another_provider_failure() -> None:
    selected = ChatProvider("a", (model("m", provider_id="a"),))
    other = ChatProvider("z", ())
    chooser = binder(selected, other)
    proposal = chooser.propose()
    other.discovery_error = OSError("offline")
    with pytest.raises(ConversationDiscoveryError):
        chooser.bind(proposal)
    assert selected.chat_calls == 0


def test_bound_session_retains_wp063_atomic_failure_and_limits() -> None:
    provider = ChatProvider("local", (model("m"),))
    chooser = binder(provider)
    session = chooser.bind(chooser.propose())
    with pytest.raises(ValueError):
        session.send(" ")
    assert session.messages == ()
    with pytest.raises(ValueError):
        session.send("x" * 2_001)
    assert session.messages == ()


def test_inference_failure_after_binding_does_not_commit_history() -> None:
    class FailingChatProvider(ChatProvider):
        def chat(self, request: ConversationRequest) -> IntelligenceResult:
            self.chat_calls += 1
            return IntelligenceResult.failed(
                request, provider_id=self.provider_id, diagnostic="offline"
            )

    provider = FailingChatProvider("local", (model("m"),))
    chooser = binder(provider)
    session = chooser.bind(chooser.propose())
    result = session.send("hola")
    assert not result.success
    assert session.messages == ()
    assert provider.chat_calls == 1


def test_assisted_cli_enters_chat_then_returns_to_legacy_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = ChatProvider("local", (model("m"),))
    monkeypatch.setattr(cli, "OllamaProvider", lambda: provider)
    inputs = iter(("si", "hola", "/salir", "salir"))
    prompts: list[str] = []
    output: list[str] = []

    def receive(prompt: str) -> str:
        prompts.append(prompt)
        return next(inputs)

    cli.entrypoint(["chat", "--select"], input_fn=receive, output_fn=output.append)
    assert provider.chat_calls == 1
    assert "IRIS chat> " in prompts
    assert "IRIS> " in prompts
    assert "respuesta" in output
    assert output[-1] == "IRIS apagándose."


def test_assisted_cli_requires_confirmation_and_never_infers_before_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = ChatProvider("local", (model("m"),))
    monkeypatch.setattr(cli, "OllamaProvider", lambda: provider)
    sessions: list[Any] = []
    monkeypatch.setattr(
        cli, "main", lambda **kwargs: sessions.append(kwargs.get("chat_session"))
    )
    prompts = iter(("maybe", "si"))
    output: list[str] = []
    cli.entrypoint(
        ["chat", "--select"],
        input_fn=lambda prompt: next(prompts),
        output_fn=output.append,
    )
    assert len(sessions) == 1
    assert sessions[0].provider_id == "local"
    assert sessions[0].model_id == "m"
    assert sessions[0].messages == ()
    assert provider.inventory_calls == 2
    assert provider.chat_calls == 0
    assert "Responde 'si' o 'no'." in output
    assert any("local/m" in line for line in output)


@pytest.mark.parametrize("answer", ["no", EOFError(), KeyboardInterrupt()])
def test_assisted_cli_cancellation_creates_no_session(
    answer: str | BaseException, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = ChatProvider("local", (model("m"),))
    monkeypatch.setattr(cli, "OllamaProvider", lambda: provider)
    sessions: list[Any] = []
    monkeypatch.setattr(
        cli, "main", lambda **kwargs: sessions.append(kwargs.get("chat_session"))
    )

    def confirm(prompt: str) -> str:
        if isinstance(answer, BaseException):
            raise answer
        return answer

    cli.entrypoint(["chat", "--select"], input_fn=confirm, output_fn=lambda _: None)
    assert sessions == [None]
    assert provider.inventory_calls == 1
    assert provider.chat_calls == 0


def test_assisted_cli_unsatisfied_and_discovery_failure_do_not_confirm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = ChatProvider("local", ())
    monkeypatch.setattr(cli, "OllamaProvider", lambda: provider)
    sessions: list[Any] = []
    monkeypatch.setattr(
        cli, "main", lambda **kwargs: sessions.append(kwargs.get("chat_session"))
    )
    output: list[str] = []
    cli.entrypoint(
        ["chat", "--select"],
        input_fn=lambda _: pytest.fail("must not ask for confirmation"),
        output_fn=output.append,
    )
    assert sessions == [None]
    assert any("unsatisfied" in value for value in output)
    provider.discovery_error = OSError("offline")
    cli.entrypoint(
        ["chat", "--select"],
        input_fn=lambda _: pytest.fail("must not ask for confirmation"),
        output_fn=output.append,
    )
    assert sessions == [None, None]
    assert any("no disponible" in value for value in output)


def test_assisted_cli_sanitizes_untrusted_provider_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = ChatProvider("bad\x1b[31m", (model("m", provider_id="bad\x1b[31m"),))
    monkeypatch.setattr(cli, "OllamaProvider", lambda: provider)
    monkeypatch.setattr(cli, "main", lambda **kwargs: None)
    output: list[str] = []
    prompts: list[str] = []

    def decline(prompt: str) -> str:
        prompts.append(prompt)
        return "no"

    cli.entrypoint(
        ["chat", "--select"],
        input_fn=decline,
        output_fn=output.append,
    )
    assert "\x1b" not in "".join(output)
    assert "\x1b" not in "".join(prompts)


def test_explicit_chat_and_mutual_exclusion_remain_intact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessions: list[Any] = []
    monkeypatch.setattr(
        cli, "main", lambda **kwargs: sessions.append(kwargs.get("chat_session"))
    )
    cli.entrypoint(["chat", "--model", "m"])
    assert sessions[-1].model_id == "m"
    with pytest.raises(SystemExit) as exc:
        cli.entrypoint(["chat", "--model", "m", "--select"])
    assert exc.value.code == 2


def test_nonlocal_need_cannot_relax_cli_hard_requirements() -> None:
    chooser = binder(ChatProvider("local", (model("m"),)))
    need = IntelligenceNeed(
        requirements=IntelligenceRequirements(
            capabilities=frozenset({ModelCapability.TEXT_GENERATION}),
            required_location=ModelLocation.CLOUD,
        )
    )
    with pytest.raises(ValueError, match="LOCAL"):
        chooser.propose(need)
