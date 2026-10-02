"""Immutable output of one optional progress-update preparation pass."""

from dataclasses import dataclass

from iris.outcome_assessment import StepOutcomeAssessment
from iris.plan_runs import StepProgressUpdate
from iris.plan_step_progress_update_preparation.errors import (
    PlanStepProgressUpdatePreparationInvariantError,
)
from iris.step_progress_transition import (
    StepProgressTransitionAction,
    StepProgressTransitionDecision,
)


@dataclass(frozen=True, slots=True)
class PlanStepProgressUpdatePreparationResult:
    """Preserve one assessment, decision, and optional inert update."""

    assessment: StepOutcomeAssessment
    transition_decision: StepProgressTransitionDecision
    progress_update: StepProgressUpdate | None

    def __post_init__(self) -> None:
        if not isinstance(self.assessment, StepOutcomeAssessment):
            raise TypeError("assessment must be a StepOutcomeAssessment")
        if not isinstance(self.transition_decision, StepProgressTransitionDecision):
            raise TypeError(
                "transition_decision must be a StepProgressTransitionDecision"
            )
        if self.progress_update is not None and not isinstance(
            self.progress_update, StepProgressUpdate
        ):
            raise TypeError("progress_update must be a StepProgressUpdate or None")

        decision = self.transition_decision
        if (
            self.assessment.plan_id != decision.plan_id
            or self.assessment.run_id != decision.run_id
            or self.assessment.run_revision != decision.observed_revision
            or self.assessment.step_id != decision.step_id
            or self.assessment.assessment_id != decision.assessment_id
        ):
            raise PlanStepProgressUpdatePreparationInvariantError(
                "assessment and transition decision lineage must match exactly"
            )

        transition_requested = (
            decision.action is StepProgressTransitionAction.TRANSITION
        )
        if transition_requested != (self.progress_update is not None):
            raise PlanStepProgressUpdatePreparationInvariantError(
                "a progress update must exist if and only if TRANSITION is requested"
            )
        if self.progress_update is not None:
            self._validate_update(self.progress_update)

    def _validate_update(self, update: StepProgressUpdate) -> None:
        decision = self.transition_decision
        if (
            update.run_id != decision.run_id
            or update.expected_revision != decision.observed_revision
            or update.step_id != decision.step_id
            or update.new_state is not decision.target_state
            or update.evidence_ids != self.assessment.evidence_ids
            or update.provenance.source_type != "step_progress_transition"
            or update.provenance.source_id != decision.decision_id
            or update.provenance.actor is not None
        ):
            raise PlanStepProgressUpdatePreparationInvariantError(
                "progress update does not match its assessment and transition decision"
            )

    def to_data(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible representation."""

        return {
            "assessment": self.assessment.to_data(),
            "transition_decision": self.transition_decision.to_data(),
            "progress_update": (
                None if self.progress_update is None else self.progress_update.to_data()
            ),
        }
