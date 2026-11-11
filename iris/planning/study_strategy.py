"""The one built-in conceptual strategy exposed by the explicit Planning CLI."""

from __future__ import annotations

from iris.planning import PlanningRule, PlanStep

STUDY_OBJECTIVE = "Preparar una sesión de estudio"


def study_session_rule() -> PlanningRule:
    """Describe human study preparation; no step has executable handling."""

    return PlanningRule(
        STUDY_OBJECTIVE,
        steps=(
            PlanStep(
                "a",
                "Delimitar un tema de estudio y el resultado de aprendizaje esperado.",
                "Tema y resultado de aprendizaje deseado identificados.",
            ),
            PlanStep(
                "b",
                "Identificar materiales y ejercicios pertinentes al tema.",
                "Recursos de estudio necesarios identificados.",
                depends_on=("a",),
            ),
            PlanStep(
                "c",
                "Organizar una secuencia de repaso y práctica.",
                "Secuencia conceptual de estudio definida.",
                depends_on=("b",),
            ),
            PlanStep(
                "d",
                "Establecer una forma de comprobar la comprensión y reconocer dudas "
                "pendientes.",
                "Criterio de autoevaluación definido.",
                depends_on=("c",),
            ),
        ),
    )
