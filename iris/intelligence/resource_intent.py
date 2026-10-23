"""Conservative, side-effect-free recognition of local resource questions.

This is a bounded CLI language rule, not a capability router or authorization.
Only the current human input is examined; the original text is never rewritten.
"""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum


class ResourceIntent(StrEnum):
    MATCH = "match"
    AMBIGUOUS = "ambiguous"
    CLARIFY_LOCAL_RESOURCE = "clarify_local_resource"
    NO_MATCH = "no_match"


_OBSERVATION_VERBS = frozenset(
    {
        "revisa",
        "revisar",
        "revises",
        "comprueba",
        "comprobar",
        "checa",
        "checar",
        "verifica",
        "verificar",
        "consulta",
        "consultar",
        "muestra",
        "muestrame",
        "dime",
    }
)
_MODIFICATION_WORDS = frozenset(
    {
        "cierra",
        "cerrar",
        "cierres",
        "libera",
        "liberar",
        "limpia",
        "limpiar",
        "borra",
        "borrar",
        "elimina",
        "eliminar",
        "mata",
        "matar",
        "termina",
        "terminar",
        "apaga",
        "apagar",
        "reinicia",
        "reiniciar",
        "optimiza",
        "optimizar",
        "modifica",
        "modificar",
        "cambia",
        "cambiar",
        "ejecuta",
        "ejecutar",
        "corre",
        "correr",
        "abre",
        "abrir",
        "mueve",
        "mover",
        "descarga",
        "descargar",
        "instala",
        "instalar",
        "desinstala",
        "desinstalar",
        "envia",
        "enviar",
        "guarda",
        "guardar",
        "comparte",
        "compartir",
        "suspende",
        "suspender",
    }
)
_FOREIGN_DEVICE_WORDS = frozenset(
    {
        "otro",
        "otra",
        "ajeno",
        "servidor",
        "dispositivo",
        "celular",
        "telefono",
        "tablet",
        "profesor",
        "dijo",
        "tu",
        "su",
        "ellos",
    }
)
_NEGATION_WORDS = frozenset({"no", "nunca", "tampoco", "evita", "evitar", "sin"})
_HYPOTHETICAL_WORDS = frozenset(
    {"pasaria", "estuviera", "supongamos", "hipoteticamente", "hipotetico", "imagina"}
)
_EDUCATIONAL_PHRASES = ("que es", "para que sirve", "que significa", "definicion de")
_QUOTE_CHARACTERS = frozenset("\"'`“”«»‘’")
_INCOMPLETE_LOCAL_INSPECTIONS = frozenset(
    {
        "revisa mi computadora",
        "revisa mi equipo",
        "puedes revisar mi computadora",
        "puedes revisar mi equipo",
        "podrias revisar mi computadora",
        "podrias revisar mi equipo",
    }
)


def recognize_resource_intent(message: str) -> ResourceIntent:
    """Classify one direct human message without observation or inference.

    A match is only an offer to ask for local-observation consent. Unknown
    formulations intentionally abstain and remain ordinary conversation.
    """

    if not isinstance(message, str):
        raise TypeError("message must be a string")
    if not message.strip() or any(char in _QUOTE_CHARACTERS for char in message):
        return ResourceIntent.NO_MATCH
    folded = "".join(
        char
        for char in unicodedata.normalize("NFKD", message.casefold())
        if not unicodedata.combining(char)
    )
    words = re.findall(r"[a-z0-9]+", folded)
    if not words:
        return ResourceIntent.NO_MATCH
    word_set = set(words)
    text = " ".join(words)
    resource = bool({"ram", "cpu"} & word_set) or "mis recursos" in text
    # A resource belonging to an unspecified other owner is not a local reading.
    foreign_possessive = any(
        words[index] in {"ram", "cpu", "recursos"}
        and words[index + 1 : index + 2] == ["de"]
        and words[index + 2 : index + 3] not in (["mi"], ["mis"])
        for index in range(len(words))
    )
    # Do not extract the read-only clause of an otherwise compound request.
    remainder = text.replace("cpu y ram", "").replace("ram y cpu", "")
    if (
        word_set
        & (
            _MODIFICATION_WORDS
            | _FOREIGN_DEVICE_WORDS
            | _NEGATION_WORDS
            | _HYPOTHETICAL_WORDS
        )
        or foreign_possessive
        or " y " in f" {remainder} "
    ):
        return ResourceIntent.NO_MATCH
    if not resource:
        local_request = text.removeprefix("iris ")
        if local_request in _INCOMPLETE_LOCAL_INSPECTIONS:
            return ResourceIntent.CLARIFY_LOCAL_RESOURCE
        return ResourceIntent.NO_MATCH
    observation = bool(word_set & _OBSERVATION_VERBS)
    explanation = bool(
        {"explica", "explicame", "explicar"} & word_set
        or any(phrase in text for phrase in _EDUCATIONAL_PHRASES)
    )
    if observation and explanation and "o" in word_set:
        return ResourceIntent.AMBIGUOUS
    if explanation:
        return ResourceIntent.NO_MATCH
    if observation:
        return ResourceIntent.MATCH
    if "cuanta" in word_set or "cuanto" in word_set:
        if word_set & {"estoy", "tengo", "mi", "mis"} and word_set & {
            "usando",
            "utilizando",
            "uso",
            "ocupada",
        }:
            return ResourceIntent.MATCH
    if "como" in word_set and word_set & {"anda", "esta", "estan", "van"}:
        if word_set & {"mi", "mis", "tengo"}:
            return ResourceIntent.MATCH
    return ResourceIntent.NO_MATCH
