"""Immutable output of one PlanStep evidence-to-transition composition."""

from dataclasses import dataclass

from iris.outcome_assessment import StepOutcomeAssessment
from iris.plan_step_evidence_transition.errors import (
    PlanStepEvidenceTransitionInvariantError,
)
from iris.step_progress_transition import StepProgressTransitionDecision


@dataclass(frozen=True, slots=True)
class PlanStepEvidenceTransitionDecisionResult:
    """One assessment and the transition decision bound to that assessment."""

    assessment: StepOutcomeAssessment
    transition_decision: StepProgressTransitionDecision

    def __post_init__(self) -> None:
        if not isinstance(self.assessment, StepOutcomeAssessment):
            raise TypeError("assessment must be a StepOutcomeAssessment")
        if not isinstance(self.transition_decision, StepProgressTransitionDecision):
            raise TypeError(
                "transition_decision must be a StepProgressTransitionDecision"
            )

        decision = self.transition_decision
        if (
            self.assessment.plan_id != decision.plan_id
            or self.assessment.run_id != decision.run_id
            or self.assessment.step_id != decision.step_id
            or self.assessment.assessment_id != decision.assessment_id
        ):
            raise PlanStepEvidenceTransitionInvariantError(
                "assessment and transition decision lineage must match exactly"
            )
        if self.assessment.run_revision != decision.observed_revision:
            raise PlanStepEvidenceTransitionInvariantError(
                "assessment and transition decision must observe the same revision"
            )

    def to_data(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible representation."""

        return {
            "assessment": self.assessment.to_data(),
            "transition_decision": self.transition_decision.to_data(),
        }
