"""Two bounded conceptual strategies for future human IRIS reviews."""

from __future__ import annotations

from iris.planning import PlanningRule, PlanStep

COMPATIBILITY_OBJECTIVE = "Preparar una revisión manual de compatibilidad de IRIS"
SECURITY_OBJECTIVE = "Preparar una revisión manual de seguridad de IRIS"


def compatibility_review_rule() -> PlanningRule:
    """Describe preparation for a manual compatibility review."""

    return PlanningRule(
        COMPATIBILITY_OBJECTIVE,
        steps=(
            PlanStep(
                "a",
                "Identificar interfaces, contratos y comportamientos observables "
                "potencialmente afectados por un cambio propuesto.",
                "Alcance de revisión y superficies de compatibilidad identificados "
                "conceptualmente.",
            ),
            PlanStep(
                "b",
                "Identificar comportamientos, interfaces y garantías históricas "
                "que deben permanecer sin cambios.",
                "Invariantes históricos que requieren verificación identificados.",
                depends_on=("a",),
            ),
            PlanStep(
                "c",
                "Preparar casos positivos, negativos, de límite y de regresión "
                "para las superficies de compatibilidad identificadas.",
                "Lista conceptual de casos de verificación establecida.",
                depends_on=("b",),
            ),
            PlanStep(
                "d",
                "Definir la evidencia necesaria para que una persona evalúe "
                "compatibilidad y discrepancias pendientes.",
                "Criterios de aceptación y requisitos de evidencia definidos.",
                depends_on=("c",),
            ),
        ),
    )


def security_review_rule() -> PlanningRule:
    """Describe preparation for a manual security review."""

    return PlanningRule(
        SECURITY_OBJECTIVE,
        steps=(
            PlanStep(
                "a",
                "Identificar fronteras de confianza, superficies de entrada, "
                "categorías de datos y componentes potencialmente afectados.",
                "Mapa conceptual de fronteras relevantes para seguridad establecido.",
            ),
            PlanStep(
                "b",
                "Identificar autoridades, permisos y capacidades operativas que "
                "no deben inferirse de entradas ni de resultados de Planning.",
                "Restricciones de autoridad relevantes identificadas.",
                depends_on=("a",),
            ),
            PlanStep(
                "c",
                "Preparar casos adversariales sobre entradas malformadas, "
                "privacidad, escalamiento de autoridad, aislamiento y fallo seguro.",
                "Lista conceptual de casos adversariales establecida.",
                depends_on=("b",),
            ),
            PlanStep(
                "d",
                "Definir la evidencia necesaria para que una persona evalúe "
                "las propiedades de seguridad identificadas.",
                "Criterios de aceptación de seguridad y requisitos de evidencia "
                "definidos.",
                depends_on=("c",),
            ),
        ),
    )
