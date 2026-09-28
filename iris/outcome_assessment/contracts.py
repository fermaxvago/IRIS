"""Replaceable contracts for PlanStep outcome evaluation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from iris.outcome_assessment.models import StepOutcomeAssessment
from iris.plan_runs import PlanObservation, PlanRun
from iris.planning import Plan, PlanStep


@runtime_checkable
class StepOutcomeEvaluator(Protocol):
    """Assess explicit recorded evidence without changing PlanRun state."""

    def evaluate(
        self,
        plan: Plan,
        run: PlanRun,
        step: PlanStep,
        evidence: tuple[PlanObservation, ...],
    ) -> StepOutcomeAssessment:
        """Return one epistemic conclusion and stop."""
        ...
