"""Immutable output of one conditional PlanStep progress advancement."""

from dataclasses import dataclass

from iris.outcome_assessment import StepOutcomeAssessment
from iris.plan_run_advancement import PlanRunProgressAdvanceResult
from iris.plan_runs import StepProgressUpdate
from iris.plan_step_progress_advancement.errors import (
    PlanStepProgressAdvancementInvariantError,
)
from iris.step_progress_transition import StepProgressTransitionDecision


@dataclass(frozen=True, slots=True)
class PlanStepProgressAdvancementResult:
    """Preserve WP029 artifacts and the optional exact WP023 result."""

    assessment: StepOutcomeAssessment
    transition_decision: StepProgressTransitionDecision
    progress_update: StepProgressUpdate | None
    advancement_result: PlanRunProgressAdvanceResult | None

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
        if self.advancement_result is not None and not isinstance(
            self.advancement_result, PlanRunProgressAdvanceResult
        ):
            raise TypeError(
                "advancement_result must be a PlanRunProgressAdvanceResult or None"
            )

        decision = self.transition_decision
        if (
            self.assessment.plan_id != decision.plan_id
            or self.assessment.run_id != decision.run_id
            or self.assessment.run_revision != decision.observed_revision
            or self.assessment.step_id != decision.step_id
            or self.assessment.assessment_id != decision.assessment_id
        ):
            raise PlanStepProgressAdvancementInvariantError(
                "assessment and transition decision lineage must match exactly"
            )

        if (self.progress_update is None) != (self.advancement_result is None):
            raise PlanStepProgressAdvancementInvariantError(
                "progress update and advancement result must either both exist or "
                "both be absent"
            )
        if self.progress_update is not None and self.advancement_result is not None:
            self._validate_advanced_lineage(
                self.progress_update,
                self.advancement_result,
            )

    def _validate_advanced_lineage(
        self,
        update: StepProgressUpdate,
        advancement: PlanRunProgressAdvanceResult,
    ) -> None:
        decision = self.transition_decision
        updated_run = advancement.updated_run
        if (
            update.run_id != decision.run_id
            or update.expected_revision != decision.observed_revision
            or update.step_id != decision.step_id
            or update.new_state is not decision.target_state
            or update.evidence_ids != self.assessment.evidence_ids
            or advancement.source_update_id != update.update_id
            or advancement.source_revision != update.expected_revision
            or updated_run.plan_id != self.assessment.plan_id
            or updated_run.run_id != self.assessment.run_id
            or updated_run.revision != self.assessment.run_revision + 1
        ):
            raise PlanStepProgressAdvancementInvariantError(
                "progress update and advancement lineage must match exactly"
            )

    def to_data(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible representation."""

        return {
            "assessment": self.assessment.to_data(),
            "transition_decision": self.transition_decision.to_data(),
            "progress_update": (
                None if self.progress_update is None else self.progress_update.to_data()
            ),
            "advancement_result": (
                None
                if self.advancement_result is None
                else self.advancement_result.to_data()
            ),
        }
