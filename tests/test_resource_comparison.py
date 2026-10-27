"""WP072: one ephemeral local baseline and two independently approved captures."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

import iris.__main__ as cli
from iris.capabilities import (
    SYSTEM_STATUS_CAPABILITY_ID,
    CapabilityInput,
    CapabilityRegistry,
    CapabilityResult,
    CapabilityRuntime,
    SystemResourceObservation,
    SystemStatusTool,
)
from iris.core.system import SystemInfo
from iris.intelligence import (
    ConversationContextBinder,
    ConversationRequest,
    ConversationSession,
    IntelligenceResult,
    IntelligenceRuntime,
    ModelCapability,
    ModelDescriptor,
    ModelLocation,
    ProviderRegistry,
)
from iris.intelligence.resource_comparison import (
    BASELINE_LIFETIME_SECONDS,
    LocalResourceComparison,
    ResourceCapacityChangedError,
    ResourceCaptureError,
    ResourceComparisonError,
    ResourceProvenanceError,
    compare_resource_observations,
)
from iris.intelligence.system_awareness import ConversationalSystemAwareness


def info(cpu: object = 20.0, used: object = 10.0, total: object = 32.0) -> SystemInfo:
    return cast(
        SystemInfo,
        {"cpu_percent": cpu, "ram_used_gb": used, "ram_total_gb": total},
    )


@dataclass
class Time:
    mono: float = 100.0
    utc: datetime = datetime(2026, 10, 23, 12, tzinfo=UTC)
    capture_offset: timedelta = timedelta()

    def monotonic(self) -> float:
        return self.mono

    def now(self) -> datetime:
        return self.utc

    def captured_at(self) -> datetime:
        return self.utc + self.capture_offset

    def advance(self, seconds: float) -> None:
        self.mono += seconds
        self.utc += timedelta(seconds=seconds)


@dataclass
class Provider:
    calls: list[ConversationRequest] = field(default_factory=list)

    @property
    def provider_id(self) -> str:
        return "local"

    def list_models(self) -> tuple[ModelDescriptor, ...]:
        return (
            ModelDescriptor(
                provider_id=self.provider_id,
                model_id="modelo",
                location=ModelLocation.LOCAL,
                capabilities=frozenset({ModelCapability.CONVERSATION}),
            ),
        )

    def infer(self, request: Any) -> IntelligenceResult:
        raise AssertionError("legacy inference is not part of comparison")

    def chat(self, request: ConversationRequest) -> IntelligenceResult:
        self.calls.append(request)
        return IntelligenceResult.succeeded(
            request, provider_id=self.provider_id, output="respuesta"
        )

    def chat_with_context(self, request: ConversationRequest) -> IntelligenceResult:
        self.calls.append(request)
        return IntelligenceResult.succeeded(
            request, provider_id=self.provider_id, output="explicación"
        )


@dataclass
class Rig:
    time: Time
    session: ConversationSession
    provider: Provider
    runtime: CapabilityRuntime
    awareness: ConversationalSystemAwareness
    readings: list[object]
    captures: list[int]

    def comparison(self) -> LocalResourceComparison:
        return LocalResourceComparison(
            self.session,
            capability_runtime=self.runtime,
            monotonic_clock=self.time.monotonic,
            utc_clock=self.time.now,
        )


def rig(*readings: object) -> Rig:
    time = Time()
    queue = list(readings)
    captures: list[int] = []

    def collector() -> SystemInfo:
        captures.append(1)
        reading = queue.pop(0)
        if isinstance(reading, Exception):
            raise reading
        if callable(reading):
            reading = reading()
        return cast(SystemInfo, reading)

    runtime = CapabilityRuntime(
        CapabilityRegistry(
            [SystemStatusTool(system_info_provider=collector, clock=time.captured_at)]
        )
    )
    provider = Provider()
    session = ConversationSession(
        IntelligenceRuntime(ProviderRegistry([provider])),
        provider_id=provider.provider_id,
        model_id="modelo",
    )
    awareness = ConversationalSystemAwareness(
        capability_runtime=runtime,
        context_binder=ConversationContextBinder(clock=time.now),
        clock=time.now,
    )
    return Rig(time, session, provider, runtime, awareness, queue, captures)


def drive(h: Rig, *inputs: str, output_fn: Any = None) -> tuple[list[str], list[str]]:
    answers = iter((*inputs, "/salir", "salir"))
    output: list[str] = []
    prompts: list[str] = []

    def receive(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    def emit(value: str) -> None:
        output.append(value)
        if output_fn is not None:
            output_fn(value)

    cli.main(
        input_fn=receive,
        output_fn=emit,
        chat_session=h.session,
        system_awareness=h.awareness,
        comparison_runtime=h.runtime,
        comparison_monotonic_clock=h.time.monotonic,
        comparison_utc_clock=h.time.now,
    )
    return output, prompts


def observation(
    at: datetime, *, cpu: float = 20.0, used: float = 10.0, total: float = 32.0
) -> SystemResourceObservation:
    return SystemResourceObservation(cpu, used, total, at)


def test_compare_without_baseline_and_status_are_read_only() -> None:
    h = rig()
    before = h.session.diagnostic_snapshot()
    output, prompts = drive(h, "/comparar estado", "/comparar ahora")
    assert not h.captures and not h.provider.calls
    assert not any("segunda lectura" in prompt for prompt in prompts)
    assert any("No hay base temporal válida" in line for line in output)
    assert h.session.diagnostic_snapshot() == before


@pytest.mark.parametrize("decision", ["no", "", "quizá", "adelante", "yes"])
def test_baseline_requires_explicit_capture_and_retention_consent(
    decision: str,
) -> None:
    h = rig()
    output, prompts = drive(h, "/comparar base", decision, "/comparar estado")
    assert not h.captures and not h.provider.calls
    assert any("retención temporal" in prompt for prompt in prompts)
    assert any("No hay base temporal válida" in line for line in output)


def test_approved_baseline_one_capture_and_comparison_consumes_once() -> None:
    h = rig(info(), lambda: (h.time.advance(1), info(30.0, 12.5))[1])
    before = h.session.diagnostic_snapshot()
    output, prompts = drive(
        h,
        "/comparar base",
        "sí",
        "/comparar estado",
        "/comparar ahora",
        "sí",
        "/comparar ahora",
    )
    assert len(h.captures) == 2
    assert sum("retención temporal" in prompt for prompt in prompts) == 1
    assert sum("segunda lectura" in prompt for prompt in prompts) == 1
    assert not h.provider.calls
    assert h.session.diagnostic_snapshot() == before
    assert any("Base temporal activa" in line for line in output)
    assert any("No hay base temporal válida" in line for line in output)


def test_pure_comparator_deltas_and_reading_identity() -> None:
    start = datetime(2026, 10, 23, 12, tzinfo=UTC)
    first = observation(start, cpu=35.0, used=20.25)
    second = observation(start + timedelta(seconds=1), cpu=20.0, used=21.5)
    delta = compare_resource_observations(
        first, second, now=start + timedelta(seconds=2)
    )
    assert delta.baseline is first and delta.current is second
    assert delta.cpu_delta_pp == -15.0
    assert delta.ram_delta_gib == 1.25
    equal = compare_resource_observations(
        first,
        observation(start + timedelta(seconds=1), cpu=35.0, used=20.25),
        now=start + timedelta(seconds=2),
    )
    assert equal.cpu_delta_pp == 0 and equal.ram_delta_gib == 0


@pytest.mark.parametrize(
    "bad",
    [
        None,
        object(),
        observation(datetime(2026, 10, 23, 12, tzinfo=UTC), used=10.0),
    ],
)
def test_comparator_rejects_noncanonical_or_unordered_readings(bad: object) -> None:
    now = datetime(2026, 10, 23, 12, tzinfo=UTC)
    with pytest.raises(ResourceComparisonError):
        compare_resource_observations(
            cast(SystemResourceObservation, bad),
            observation(now),
            now=now,
        )


@pytest.mark.parametrize("seconds,active", [(599.999, True), (600, False)])
def test_monotonic_ttl_is_strict(seconds: float, active: bool) -> None:
    h = rig(info())
    comparison = h.comparison()
    comparison.establish(comparison.stamp())
    h.time.advance(seconds)
    assert comparison.status() is active
    assert BASELINE_LIFETIME_SECONDS == 600
    assert len(h.captures) == 1


def test_comparison_succeeds_at_599_999_seconds_but_not_at_600() -> None:
    h = rig(info(), info(25.0, 11.0))
    comparison = h.comparison()
    comparison.establish(comparison.stamp())
    h.time.advance(599.999)
    delta = comparison.compare_now(comparison.stamp())
    assert delta.cpu_delta_pp == 5.0 and len(h.captures) == 2

    other = rig(info(), info(25.0, 11.0))
    next_comparison = other.comparison()
    next_comparison.establish(next_comparison.stamp())
    other.time.advance(600)
    with pytest.raises(ResourceComparisonError, match="no active baseline"):
        next_comparison.compare_now(next_comparison.stamp())
    assert len(other.captures) == 1


def test_monotonic_regression_and_invalid_clock_fail_closed() -> None:
    h = rig(info(), info())
    comparison = h.comparison()
    comparison.establish(comparison.stamp())
    h.time.mono = 99.0
    with pytest.raises(ResourceComparisonError, match="regressed"):
        comparison.status()
    assert not comparison.status()
    h.time.mono = float("nan")
    with pytest.raises(ResourceComparisonError, match="invalid"):
        comparison.establish(comparison.stamp())


def test_reset_invalidates_but_revision_only_does_not() -> None:
    h = rig(info())
    comparison = h.comparison()
    comparison.establish(comparison.stamp())
    h.session.set_continuity(True)
    assert comparison.status()
    h.session.send("hola")
    assert comparison.status()
    h.session.reset()
    assert not comparison.status()
    assert len(h.captures) == 1


def test_session_change_between_consent_and_capture_rejects_without_capture() -> None:
    h = rig(info())
    comparison = h.comparison()
    stamp = comparison.stamp()
    h.session.reset()
    with pytest.raises(ResourceComparisonError, match="identity"):
        comparison.establish(stamp)
    assert not h.captures


def test_session_reset_during_capture_discards_candidate() -> None:
    h = rig(lambda: (h.session.reset(), info())[1])
    comparison = h.comparison()
    with pytest.raises(ResourceComparisonError, match="identity"):
        comparison.establish(comparison.stamp())
    assert len(h.captures) == 1 and not comparison.status()


def test_session_reset_during_second_capture_discards_delta_and_baseline() -> None:
    h = rig(info(), lambda: (h.session.reset(), info(25.0, 11.0))[1])
    comparison = h.comparison()
    comparison.establish(comparison.stamp())
    h.time.advance(1)
    with pytest.raises(ResourceComparisonError, match="identity"):
        comparison.compare_now(comparison.stamp())
    assert len(h.captures) == 2 and not comparison.status()


def test_replacement_is_atomic_and_failed_candidate_keeps_valid_baseline() -> None:
    h = rig(info(20.0, 10.0), info(None, 11.0), info(25.0, 12.0))
    comparison = h.comparison()
    first = comparison.establish(comparison.stamp())
    h.time.advance(1)
    with pytest.raises(ResourceCaptureError):
        comparison.establish(comparison.stamp())
    assert comparison.status()
    h.time.advance(1)
    replacement = comparison.establish(comparison.stamp())
    assert replacement is not first and replacement.cpu_percent == 25.0
    assert len(h.captures) == 3


def test_failed_replacement_does_not_revive_expired_baseline() -> None:
    h = rig(info(), info(None, 10.0))
    comparison = h.comparison()
    comparison.establish(comparison.stamp())
    h.time.advance(600)
    with pytest.raises(ResourceCaptureError):
        comparison.establish(comparison.stamp())
    assert not comparison.status()


def test_expiration_during_second_capture_rejects_delta() -> None:
    h = rig(info(), lambda: (h.time.advance(600), info())[1])
    comparison = h.comparison()
    comparison.establish(comparison.stamp())
    with pytest.raises(ResourceComparisonError, match="expired"):
        comparison.compare_now(comparison.stamp())
    assert len(h.captures) == 2 and not comparison.status()


@pytest.mark.parametrize(
    "current_at",
    [
        datetime(2026, 10, 23, 12, tzinfo=UTC),
        datetime(2026, 10, 23, 11, tzinfo=UTC),
    ],
)
def test_equal_or_reversed_timestamps_rejected(current_at: datetime) -> None:
    start = datetime(2026, 10, 23, 12, tzinfo=UTC)
    with pytest.raises(ResourceComparisonError, match="timestamps"):
        compare_resource_observations(
            observation(start), observation(current_at), now=start
        )


def test_non_utc_or_mutated_observation_rejected() -> None:
    start = datetime(2026, 10, 23, 12, tzinfo=UTC)
    first = observation(start)
    object.__setattr__(first, "captured_at", datetime(2026, 10, 23, 12))
    with pytest.raises(ResourceComparisonError):
        compare_resource_observations(
            first,
            observation(start + timedelta(seconds=1)),
            now=start + timedelta(seconds=2),
        )
    with pytest.raises(ResourceComparisonError, match="validation time"):
        compare_resource_observations(
            observation(start),
            observation(start + timedelta(seconds=1)),
            now=datetime(2026, 10, 23, 12),
        )


def test_future_timestamp_and_capacity_change_rejected() -> None:
    start = datetime(2026, 10, 23, 12, tzinfo=UTC)
    with pytest.raises(ResourceComparisonError, match="future"):
        compare_resource_observations(
            observation(start),
            observation(start + timedelta(seconds=2)),
            now=start + timedelta(seconds=1),
        )
    with pytest.raises(ResourceCapacityChangedError):
        compare_resource_observations(
            observation(start),
            observation(start + timedelta(seconds=1), total=31.99),
            now=start + timedelta(seconds=2),
        )


def test_future_dated_capture_does_not_establish_or_replace_baseline() -> None:
    h = rig(info(), info())
    comparison = h.comparison()
    first = comparison.establish(comparison.stamp())
    h.time.capture_offset = timedelta(seconds=10)
    with pytest.raises(ResourceCaptureError, match="future"):
        comparison.establish(comparison.stamp())
    assert comparison.status()
    assert first.cpu_percent == 20.0 and len(h.captures) == 2


def test_invalid_utc_validation_clock_fails_closed() -> None:
    h = rig(info())
    comparison = LocalResourceComparison(
        h.session,
        capability_runtime=h.runtime,
        monotonic_clock=h.time.monotonic,
        utc_clock=lambda: datetime(2026, 10, 23, 12),
    )
    with pytest.raises(ResourceCaptureError):
        comparison.establish(comparison.stamp())
    assert len(h.captures) == 1 and not comparison.status()


def test_capacity_change_consumes_incompatible_baseline() -> None:
    h = rig(info(), info(total=31.99))
    comparison = h.comparison()
    comparison.establish(comparison.stamp())
    h.time.advance(1)
    with pytest.raises(ResourceCapacityChangedError):
        comparison.compare_now(comparison.stamp())
    assert not comparison.status() and len(h.captures) == 2


@pytest.mark.parametrize(
    "reading",
    [
        info(None, 10.0),
        info(20.0, None),
        info(20.0, 10.0, None),
        info(float("nan"), 10.0),
        info(float("inf"), 10.0),
        info(True, 10.0),
        info("20", 10.0),
        info(-1.0, 10.0),
        info(20.0, 33.0),
    ],
)
def test_invalid_or_incomplete_capture_never_creates_baseline(
    reading: SystemInfo,
) -> None:
    h = rig(reading)
    comparison = h.comparison()
    with pytest.raises(ResourceCaptureError):
        comparison.establish(comparison.stamp())
    assert not comparison.status() and len(h.captures) == 1


def test_failed_second_capture_keeps_only_valid_baseline() -> None:
    h = rig(info(), info(cpu=None), info(25.0, 11.0))
    comparison = h.comparison()
    comparison.establish(comparison.stamp())
    h.time.advance(1)
    with pytest.raises(ResourceCaptureError):
        comparison.compare_now(comparison.stamp())
    assert comparison.status()
    h.time.advance(1)
    delta = comparison.compare_now(comparison.stamp())
    assert delta.cpu_delta_pp == 5.0 and delta.ram_delta_gib == 1.0
    assert len(h.captures) == 3 and not comparison.status()


def test_capability_exception_does_not_retry_or_invent_reading() -> None:
    h = rig(RuntimeError("offline"))
    comparison = h.comparison()
    with pytest.raises(ResourceCaptureError):
        comparison.establish(comparison.stamp())
    assert len(h.captures) == 1 and not comparison.status()


def test_malformed_capability_result_rejected_without_retry() -> None:
    h = rig()

    class MalformedTool(SystemStatusTool):
        def execute(self, capability_input: CapabilityInput) -> Any:
            assert capability_input.payload == {"output_mode": "structured"}
            return object()

    comparison = LocalResourceComparison(
        h.session,
        capability_runtime=CapabilityRuntime(CapabilityRegistry([MalformedTool()])),
        monotonic_clock=h.time.monotonic,
        utc_clock=h.time.now,
    )
    with pytest.raises(ResourceCaptureError):
        comparison.establish(comparison.stamp())
    assert not comparison.status()


def test_wrong_capability_result_identity_invalidates_baseline() -> None:
    h = rig()

    class IdentitySwitchTool(SystemStatusTool):
        count = 0

        def execute(self, capability_input: CapabilityInput) -> CapabilityResult:
            assert capability_input.payload == {"output_mode": "structured"}
            self.count += 1
            if self.count == 1:
                return CapabilityResult.succeeded(
                    SYSTEM_STATUS_CAPABILITY_ID,
                    output=observation(h.time.now()),
                )
            return CapabilityResult.succeeded(
                "other.capability", output=observation(h.time.now())
            )

    comparison = LocalResourceComparison(
        h.session,
        capability_runtime=CapabilityRuntime(
            CapabilityRegistry([IdentitySwitchTool()])
        ),
        monotonic_clock=h.time.monotonic,
        utc_clock=h.time.now,
    )
    comparison.establish(comparison.stamp())
    h.time.advance(1)
    with pytest.raises(ResourceProvenanceError):
        comparison.compare_now(comparison.stamp())
    assert not comparison.status()


def test_denied_second_capture_preserves_baseline() -> None:
    h = rig(info())
    output, _ = drive(
        h, "/comparar base", "sí", "/comparar ahora", "no", "/comparar estado"
    )
    assert len(h.captures) == 1 and not h.provider.calls
    assert any("Base temporal activa" in line for line in output)


def test_denied_replacement_preserves_previous_baseline() -> None:
    h = rig(info())
    output, _ = drive(
        h, "/comparar base", "sí", "/comparar base", "no", "/comparar estado"
    )
    assert len(h.captures) == 1 and not h.provider.calls
    assert any("Base temporal activa" in line for line in output)


def test_cancelled_baseline_cannot_be_compared() -> None:
    h = rig(info())
    output, _ = drive(
        h, "/comparar base", "sí", "/comparar cancelar", "/comparar ahora"
    )
    assert len(h.captures) == 1 and not h.provider.calls
    assert any("No hay base temporal válida" in line for line in output)


def test_explicit_cancel_and_unknown_commands_never_capture_or_infer() -> None:
    h = rig()
    output, _ = drive(
        h, "/comparar", "/comparar mañana", "/comparar base ahora", "/comparar cancelar"
    )
    assert not h.captures and not h.provider.calls
    assert sum("Uso: /comparar" in line for line in output) == 3
    assert any("Base temporal descartada" in line for line in output)


@pytest.mark.parametrize("end", ["/salir", None, "interrupt"])
def test_chat_termination_discards_baseline_even_with_reused_session(
    end: str | None,
) -> None:
    h = rig(info())
    answers = iter(("/comparar base", "sí", end))
    output: list[str] = []

    def receive(prompt: str) -> str:
        try:
            value = next(answers)
        except StopIteration:
            return "salir"
        if value == "interrupt":
            raise KeyboardInterrupt
        if value is None:
            raise EOFError
        return value

    cli.main(
        input_fn=receive,
        output_fn=output.append,
        chat_session=h.session,
        comparison_runtime=h.runtime,
        comparison_monotonic_clock=h.time.monotonic,
        comparison_utc_clock=h.time.now,
    )
    second, _ = drive(h, "/comparar ahora")
    assert len(h.captures) == 1 and not h.provider.calls
    assert any("No hay base temporal válida" in line for line in second)


def test_reset_discards_baseline_without_capture() -> None:
    h = rig(info())
    output, _ = drive(h, "/comparar base", "sí", "/reiniciar", "/comparar ahora")
    assert len(h.captures) == 1
    assert h.session.generation == 1
    assert any("No hay base temporal válida" in line for line in output)


def test_successive_comparisons_require_independent_baselines_and_consents() -> None:
    h = rig(
        info(20.0, 10.0),
        lambda: (h.time.advance(1), info(25.0, 11.0))[1],
        lambda: (h.time.advance(1), info(30.0, 12.0))[1],
        lambda: (h.time.advance(1), info(35.0, 13.0))[1],
    )
    output, prompts = drive(
        h,
        "/comparar base",
        "sí",
        "/comparar ahora",
        "sí",
        "/comparar ahora",
        "/comparar base",
        "sí",
        "/comparar ahora",
        "sí",
    )
    assert len(h.captures) == 4
    assert sum("retención temporal" in prompt for prompt in prompts) == 2
    assert sum("segunda lectura" in prompt for prompt in prompts) == 2
    assert sum("Comparación local" in line for line in output) == 2
    assert not h.provider.calls


def test_comparison_output_failure_cannot_restore_consumed_baseline() -> None:
    h = rig(info(), info(25.0, 11.0))
    comparison = h.comparison()
    comparison.establish(comparison.stamp())
    h.time.advance(1)
    delta = comparison.compare_now(comparison.stamp())

    def broken_output(_: str) -> None:
        raise RuntimeError("terminal unavailable")

    with pytest.raises(RuntimeError):
        cli._show_resource_delta(delta, broken_output)
    assert not comparison.status()


def test_cli_comparison_does_not_change_conversation_or_policy() -> None:
    h = rig(info(), lambda: (h.time.advance(1), info(25.0, 11.0))[1])
    before = h.session.diagnostic_snapshot()
    output, _ = drive(h, "/comparar base", "sí", "/comparar ahora", "sí")
    assert len(h.captures) == 2 and not h.provider.calls
    assert h.session.diagnostic_snapshot() == before
    assert any("+5.0 puntos porcentuales" in line for line in output)
    assert any("+1.00 GiB" in line for line in output)
    assert any("no establecen tendencia ni causa" in line for line in output)


def test_recursos_between_comparison_captures_does_not_replace_baseline() -> None:
    h = rig(
        info(20.0, 10.0),
        lambda: (h.time.advance(1), info(90.0, 20.0))[1],
        lambda: (h.time.advance(1), info(25.0, 11.0))[1],
    )
    output, _ = drive(
        h,
        "/comparar base",
        "sí",
        "/recursos ¿Cómo está mi RAM?",
        "no",
        "/comparar ahora",
        "sí",
    )
    assert len(h.captures) == 3
    assert not h.provider.calls
    assert any("+5.0 puntos porcentuales" in line for line in output)
    assert any("+1.00 GiB" in line for line in output)


def test_external_reading_cannot_be_supplied_through_cli() -> None:
    h = rig()
    output, _ = drive(h, "/comparar base 1,2,3", "/comparar ahora 4,5,6")
    assert not h.captures and not h.provider.calls
    assert sum("Uso: /comparar" in line for line in output) == 2


def test_ordinary_chat_and_resource_intent_remain_separate() -> None:
    h = rig(info())
    output, _ = drive(h, "hola", "Revisa mi computadora", "no")
    assert len(h.provider.calls) == 1
    assert not h.captures
    assert h.session.completed_turns == 1
    assert any("Aclaración cancelada" in line for line in output)


@pytest.mark.parametrize("failure", [EOFError(), KeyboardInterrupt()])
def test_interrupted_comparison_consent_does_not_capture(
    failure: BaseException,
) -> None:
    h = rig()
    output: list[str] = []
    started = False

    def receive(prompt: str) -> str:
        nonlocal started
        if "retención temporal" in prompt:
            raise failure
        if not started:
            started = True
            return "/comparar base"
        return "salir"

    cli.main(
        input_fn=receive,
        output_fn=output.append,
        chat_session=h.session,
        comparison_runtime=h.runtime,
    )
    assert not h.captures and not h.provider.calls
    assert h.session.messages == ()


def test_natural_comparison_without_baseline_never_observes_or_infers() -> None:
    h = rig()
    before = h.session.diagnostic_snapshot()
    output, prompts = drive(h, "¿Estoy usando más RAM que antes?")
    assert not h.captures and not h.provider.calls
    assert not any("segunda lectura" in prompt for prompt in prompts)
    assert any("/comparar base" in line for line in output)
    assert h.session.diagnostic_snapshot() == before


@pytest.mark.parametrize("age", [599.999, 600.0])
def test_natural_comparison_respects_existing_strict_baseline_ttl(age: float) -> None:
    h = rig(info(), info(25.0, 11.0))

    def advance_after_baseline(line: str) -> None:
        if "Base temporal guardada" in line:
            h.time.advance(age)

    output, prompts = drive(
        h,
        "/comparar base",
        "sí",
        "¿Estoy usando más RAM que antes?",
        "sí" if age < 600 else "/comparar estado",
        output_fn=advance_after_baseline,
    )
    assert len(h.captures) == (2 if age < 600 else 1)
    assert not h.provider.calls
    assert sum("segunda lectura" in prompt for prompt in prompts) == (
        1 if age < 600 else 0
    )
    assert any("Comparación local" in line for line in output) is (age < 600)


@pytest.mark.parametrize("answer", ["no", "", "quizá", "adelante", "yes"])
def test_natural_comparison_requires_fresh_second_capture_consent(
    answer: str,
) -> None:
    h = rig(info())
    output, prompts = drive(
        h,
        "/comparar base",
        "sí",
        "Dime si estoy usando más RAM que antes",
        answer,
        "/comparar estado",
    )
    assert len(h.captures) == 1 and not h.provider.calls
    assert sum("segunda lectura" in prompt for prompt in prompts) == 1
    assert any("Base temporal activa" in line for line in output)
    assert h.session.messages == ()


def test_natural_comparison_uses_wp072_and_consumes_baseline_once() -> None:
    h = rig(info(20.0, 10.0), lambda: (h.time.advance(1), info(25.0, 11.0))[1])
    before = h.session.diagnostic_snapshot()
    output, prompts = drive(
        h,
        "/comparar base",
        "sí",
        "¿Aumentó mi uso de CPU respecto a la base?",
        "sí",
        "¿Estoy usando más RAM que antes?",
        "/comparar estado",
    )
    assert len(h.captures) == 2 and not h.provider.calls
    assert sum("segunda lectura" in prompt for prompt in prompts) == 1
    assert any("+5.0 puntos porcentuales" in line for line in output)
    assert any("+1.00 GiB" in line for line in output)
    assert any("No hay base temporal válida" in line for line in output)
    assert h.session.diagnostic_snapshot() == before


@pytest.mark.parametrize(
    "message,fragment",
    [
        ("¿Tengo más RAM que antes?", "Para comparar"),
        ("Compara mi consumo de RAM", "Para comparar"),
        ("Compara mi CPU con ayer", "no es compatible"),
        ("Compara mi RAM y cierra Chrome", "no es compatible"),
        ("Compara la RAM de mi servidor", "no es compatible"),
        ("Revisa si uso más RAM que antes", "Para comparar"),
    ],
)
def test_nonmatching_comparison_never_falls_through(
    message: str, fragment: str
) -> None:
    h = rig()
    output, prompts = drive(h, message, message)
    assert not h.captures and not h.provider.calls
    assert not any("Autorizas" in prompt for prompt in prompts)
    assert sum(fragment in line for line in output) == 2
    assert h.session.messages == ()


def test_comparison_phrase_with_observation_verb_uses_comparison_route() -> None:
    h = rig(info(), lambda: (h.time.advance(1), info(25.0, 11.0))[1])
    output, prompts = drive(
        h, "/comparar base", "sí", "Dime si estoy usando más RAM que antes", "sí"
    )
    assert len(h.captures) == 2 and not h.provider.calls
    assert sum("segunda lectura" in prompt for prompt in prompts) == 1
    assert not any("observar estos recursos" in prompt for prompt in prompts)
    assert any("Comparación local" in line for line in output)


def test_natural_comparison_preserves_wp072_capture_failure_and_baseline() -> None:
    h = rig(info(), info(cpu=None))
    output, _ = drive(
        h,
        "/comparar base",
        "sí",
        "¿Estoy usando más RAM que antes?",
        "sí",
        "/comparar estado",
    )
    assert len(h.captures) == 2 and not h.provider.calls
    assert any("Comparación no disponible" in line for line in output)
    assert any("Base temporal activa" in line for line in output)


def test_natural_comparison_does_not_change_explicit_resource_consultation() -> None:
    h = rig(info())
    output, prompts = drive(h, "¿Cuánta RAM estoy usando?", "no")
    assert not h.captures and not h.provider.calls
    assert any("observar estos recursos" in prompt for prompt in prompts)
    assert not any("segunda lectura" in prompt for prompt in prompts)
    assert h.session.messages == ()
    assert any("Observación no autorizada" in line for line in output)


def test_educational_comparison_question_remains_ordinary_conversation() -> None:
    h = rig()
    output, prompts = drive(h, "Explícame qué significa comparar la RAM")
    assert not h.captures
    assert len(h.provider.calls) == 1
    assert h.session.completed_turns == 1
    assert not any("segunda lectura" in prompt for prompt in prompts)
    assert not any("Para comparar" in line for line in output)


def test_ordinary_turn_and_resource_consultation_do_not_replace_natural_baseline() -> (
    None
):
    h = rig(
        info(20.0, 10.0),
        lambda: (h.time.advance(1), info(90.0, 20.0))[1],
        lambda: (h.time.advance(1), info(25.0, 11.0))[1],
    )
    output, _ = drive(
        h,
        "/comparar base",
        "sí",
        "hola",
        "/recursos ¿Cómo está mi RAM?",
        "no",
        "¿Estoy usando más RAM que antes?",
        "sí",
    )
    assert len(h.captures) == 3
    assert len(h.provider.calls) == 1  # Only the ordinary turn reaches the model.
    assert h.session.completed_turns == 1
    assert any("+5.0 puntos porcentuales" in line for line in output)
    assert any("+1.00 GiB" in line for line in output)


def test_natural_comparison_rechecks_session_after_consent() -> None:
    h = rig(info(), info(25.0, 11.0))
    answers = iter(
        ("/comparar base", "sí", "¿Estoy usando más RAM que antes?", "/salir", "salir")
    )
    output: list[str] = []

    def receive(prompt: str) -> str:
        if "segunda lectura" in prompt:
            h.session.reset()
            return "sí"
        return next(answers)

    cli.main(
        input_fn=receive,
        output_fn=output.append,
        chat_session=h.session,
        comparison_runtime=h.runtime,
        comparison_monotonic_clock=h.time.monotonic,
        comparison_utc_clock=h.time.now,
    )
    assert len(h.captures) == 1 and not h.provider.calls
    assert h.session.messages == ()
    assert any("Comparación no disponible" in line for line in output)


@pytest.mark.parametrize("end", [None, "interrupt"])
def test_interrupted_natural_comparison_consent_fails_closed(end: str | None) -> None:
    h = rig(info())
    answers = iter(("/comparar base", "sí", "¿Estoy usando más RAM que antes?"))
    output: list[str] = []

    def receive(prompt: str) -> str:
        if "segunda lectura" in prompt:
            if end is None:
                raise EOFError
            raise KeyboardInterrupt
        try:
            return next(answers)
        except StopIteration:
            return "salir"

    cli.main(
        input_fn=receive,
        output_fn=output.append,
        chat_session=h.session,
        comparison_runtime=h.runtime,
        comparison_monotonic_clock=h.time.monotonic,
        comparison_utc_clock=h.time.now,
    )
    assert len(h.captures) == 1 and not h.provider.calls
    assert h.session.messages == ()
    assert any("Comparación no autorizada" in line for line in output)
