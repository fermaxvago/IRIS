"""WP073 recognition has no access to observations, sessions, or models."""

from __future__ import annotations

import pytest

from iris.intelligence.resource_comparison_intent import (
    ComparisonIntent,
    recognize_resource_comparison_intent,
)


@pytest.mark.parametrize(
    "message",
    [
        "¿Estoy usando más RAM que antes?",
        "Dime si estoy usando más RAM que antes",
        "¿Aumentó mi uso de CPU respecto a la base?",
        "Compara el uso actual de RAM con la base anterior",
        "  ¿ESTOY   USANDO MÁS ram QUE antes?  ",
        "¿Ha aumentado mi uso de CPU respecto a la base?",
        "Compara el uso actual de CPU y RAM con la base anterior",
    ],
)
def test_bounded_supported_comparisons_match(message: str) -> None:
    assert recognize_resource_comparison_intent(message) is ComparisonIntent.MATCH


@pytest.mark.parametrize(
    "message",
    [
        "¿Cuánta RAM estoy usando?",
        "Consulta mi CPU",
        "¿Qué es la RAM?",
        "¿Cómo va mi PC?",
        "¿Cómo funciona el procesador?",
        "Explícame por qué aumenta la memoria utilizada.",
        "Explícame qué significa comparar la RAM",
        "¿Qué diferencia existe entre CPU y GPU?",
        "hola",
        "RAM",
        "...",
        "",
        "ramificación del programa",
        "Dime más sobre RAM",
        "Mi RAM aumentó",
    ],
)
def test_noncomparison_input_abstains(message: str) -> None:
    assert recognize_resource_comparison_intent(message) is ComparisonIntent.NO_MATCH


@pytest.mark.parametrize(
    "message",
    [
        "¿Tengo más RAM que antes?",
        "¿Mi CPU subió?",
        "Compara mi consumo de RAM",
        "Compara mi RAM con la base",
        "Compara mi memoria con la base",
        "Revisa si uso más RAM que antes",
    ],
)
def test_incomplete_metric_or_reference_requires_new_request(message: str) -> None:
    assert recognize_resource_comparison_intent(message) is ComparisonIntent.CLARIFY


@pytest.mark.parametrize(
    "message",
    [
        "Compara mi CPU con ayer",
        "Compara la RAM de mi servidor",
        "Compara mi RAM y cierra Chrome",
        "Compara mi CPU o reinicia el equipo",
        "Compara mi GPU con la base",
        "Compara la temperatura de mi CPU con la base",
        "Compara mi RAM de la semana pasada",
        "Dime si estoy usando más RAM que el lunes",
        "Compara mi CPU con el lunes",
        "No compara mi RAM con la base",
        "¿Qué pasaría si mi RAM aumentara respecto a la base?",
        'Mi profesor dijo: "Compara mi RAM con la base"',
        "Compara mi uso de CPU con la base y envía el resultado",
    ],
)
def test_recognizable_but_unsafe_comparisons_reject(message: str) -> None:
    assert recognize_resource_comparison_intent(message) is ComparisonIntent.REJECT


def test_type_and_runtime_isolation() -> None:
    import iris.intelligence.resource_comparison_intent as module

    with pytest.raises(TypeError):
        recognize_resource_comparison_intent(None)  # type: ignore[arg-type]
    assert not any(
        name in vars(module)
        for name in (
            "ConversationSession",
            "LocalResourceComparison",
            "CapabilityRuntime",
        )
    )
