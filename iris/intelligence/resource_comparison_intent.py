"""Conservative recognition of requests for the existing local comparison.

This module only classifies the current human text. It has no operational
authority and deliberately abstains outside a small Spanish phrase set.
"""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum


class ComparisonIntent(StrEnum):
    MATCH = "match"
    CLARIFY = "clarify"
    REJECT = "reject"
    NO_MATCH = "no_match"


_COMPARISON_WORDS = frozenset(
    {
        "compara",
        "comparar",
        "comparado",
        "comparada",
        "comparacion",
        "aumento",
        "aumentado",
        "aumenta",
        "disminuyo",
        "disminuido",
        "subio",
        "bajo",
        "aumentara",
        "mas",
        "menos",
        "compares",
    }
)
_METRIC_WORDS = frozenset(
    {"cpu", "ram", "memoria", "gpu", "vram", "disco", "temperatura", "frecuencia"}
)
_UNSUPPORTED_METRICS = frozenset(
    {"gpu", "vram", "disco", "temperatura", "frecuencia", "voltaje", "red", "procesos"}
)
_UNSUPPORTED_HISTORY = frozenset(
    {"ayer", "anoche", "semana", "mes", "historico", "historica", "sesion", "importado"}
)
_FOREIGN_SCOPE = frozenset(
    {
        "servidor",
        "remoto",
        "remota",
        "telefono",
        "celular",
        "profesor",
        "amigo",
        "otra",
        "otro",
        "ajeno",
    }
)
_MODIFICATION_WORDS = frozenset(
    {
        "cierra",
        "cerrar",
        "reinicia",
        "reiniciar",
        "elimina",
        "eliminar",
        "borra",
        "borrar",
        "libera",
        "liberar",
        "apaga",
        "apagar",
        "optimiza",
        "optimizar",
        "ejecuta",
        "ejecutar",
    }
)
_NON_REQUEST_WORDS = frozenset(
    {
        "no",
        "nunca",
        "tampoco",
        "pasaria",
        "tuvieras",
        "estuviera",
        "hipoteticamente",
        "supongamos",
        "imagina",
    }
)
_QUOTES = frozenset("\"'`“”«»‘’")
_SUPPORTED_METRIC = r"(?:cpu|ram|cpu y ram|ram y cpu)"
_MATCH_PATTERNS = (
    re.compile(
        rf"(?:iris )?(?:dime si )?estoy usando (?:mas|menos) {_SUPPORTED_METRIC} que antes"
    ),
    re.compile(
        rf"(?:iris )?(?:ha )?(?:aumento|aumentado|disminuyo|disminuido|subio|subido|bajo|bajado) "
        rf"mi uso de {_SUPPORTED_METRIC} (?:respecto a|comparado con) "
        r"(?:la )?base(?: anterior)?"
    ),
    re.compile(
        rf"(?:iris )?compara (?:el |mi )?uso actual de {_SUPPORTED_METRIC} "
        r"con (?:la )?base(?: anterior)?"
    ),
)


def recognize_resource_comparison_intent(message: str) -> ComparisonIntent:
    """Classify one direct input; a match still requires a baseline and consent."""

    if not isinstance(message, str):
        raise TypeError("message must be a string")
    folded = "".join(
        char
        for char in unicodedata.normalize("NFKD", message.casefold())
        if not unicodedata.combining(char)
    )
    words = re.findall(r"[a-z0-9]+", folded)
    if not words:
        return ComparisonIntent.NO_MATCH
    word_set = set(words)
    text = " ".join(words)
    if text.startswith(("explica ", "explicame ", "que significa ", "que es ")):
        return ComparisonIntent.NO_MATCH
    comparison = bool(word_set & (_COMPARISON_WORDS - {"mas", "menos"})) or bool(
        word_set & {"mas", "menos"} and word_set & {"que", "antes", "base"}
    )
    metric = bool(word_set & _METRIC_WORDS)
    if not comparison or not metric:
        return ComparisonIntent.NO_MATCH
    if any(char in _QUOTES for char in message):
        return ComparisonIntent.REJECT
    if (
        word_set
        & (
            _UNSUPPORTED_METRICS
            | _UNSUPPORTED_HISTORY
            | _FOREIGN_SCOPE
            | _MODIFICATION_WORDS
        )
        or "de otro" in text
        or "de otra" in text
    ):
        return ComparisonIntent.REJECT
    if word_set & _NON_REQUEST_WORDS:
        return ComparisonIntent.REJECT
    # A second action or alternative must never be salvaged as a read-only request.
    if " o " in f" {text} " or (
        " y " in f" {text} " and "cpu y ram" not in text and "ram y cpu" not in text
    ):
        return ComparisonIntent.REJECT
    if ("con" in word_set and "base" not in word_set) or (
        word_set & {"mas", "menos"}
        and "que" in word_set
        and not word_set & {"antes", "base"}
    ):
        return ComparisonIntent.REJECT
    if any(pattern.fullmatch(text) for pattern in _MATCH_PATTERNS):
        return ComparisonIntent.MATCH
    if text in {
        "tengo mas ram que antes",
        "mi cpu subio",
        "compara mi consumo de ram",
    } or (
        (
            "?" in message
            or word_set
            & {
                "compara",
                "comparar",
                "dime",
                "revisa",
                "muestra",
                "muestrame",
                "consulta",
                "checa",
            }
        )
        and word_set & {"ram", "cpu", "memoria"}
    ):
        return ComparisonIntent.CLARIFY
    return ComparisonIntent.NO_MATCH
