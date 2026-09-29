"""Validated one-shot synthesis of an existing StepProgressUpdate contract."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from iris.outcome_assessment import StepOutcomeAssessment, StepOutcomeStatus
from iris.plan_runs import (
    PlanRun,
    RunProvenance,
    StepProgress,
    StepProgressState,
    StepProgressUpdate,
)
from iris.plan_runs.models import utc_time
from iris.planning import Plan
from iris.step_progress_transition import (
    StepProgressTransitionAction,
    StepProgressTransitionDecision,
    validate_step_progress_transition_decision_current,
)
from iris.step_progress_update_synthesis.errors import (
    NonActionableTransitionDecisionError,
    StepProgressUpdateGenerationError,
    TransitionAssessmentBindingError,
)


class StepProgressUpdateSynthesizer:
    """Bind one current transition decision and assessment into one update."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        update_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)
        self._update_id_factory = (
            update_id_factory if update_id_factory is not None else lambda: uuid4().hex
        )

    def synthesize(
        self,
        plan: Plan,
        run: PlanRun,
        assessment: StepOutcomeAssessment,
        decision: StepProgressTransitionDecision,
    ) -> StepProgressUpdate:
        """Return one update without invoking the reducer or mutating inputs."""

        self._validate_types(plan, run, assessment, decision)
        validate_step_progress_transition_decision_current(plan, run, decision)
        if decision.action is not StepProgressTransitionAction.TRANSITION:
            raise NonActionableTransitionDecisionError(
                "transition decision does not request a progress transition"
            )

        self._validate_identity_binding(assessment, decision)
        self._validate_causal_binding(assessment, decision)
        self._validate_evidence_binding(run, assessment, decision)
        progress = self._progress(run, decision.step_id)
        if assessment.assessed_at < progress.changed_at:
            raise TransitionAssessmentBindingError(
                "assessment predates the current ACTIVE StepProgress state"
            )

        update_id = self._new_update_id(run, assessment, decision)
        updated_at = self._updated_at(run, decision)
        target_state = cast(StepProgressState, decision.target_state)
        return StepProgressUpdate(
            update_id=update_id,
            run_id=decision.run_id,
            expected_revision=decision.observed_revision,
            updated_at=updated_at,
            provenance=RunProvenance(
                source_type="step_progress_transition",
                source_id=decision.decision_id,
                actor=None,
            ),
            step_id=decision.step_id,
            new_state=target_state,
            evidence_ids=assessment.evidence_ids,
        )

    @staticmethod
    def _validate_types(
        plan: Plan,
        run: PlanRun,
        assessment: StepOutcomeAssessment,
        decision: StepProgressTransitionDecision,
    ) -> None:
        if not isinstance(plan, Plan):
            raise TypeError("plan must be a Plan")
        if not isinstance(run, PlanRun):
            raise TypeError("run must be a PlanRun")
        if not isinstance(assessment, StepOutcomeAssessment):
            raise TypeError("assessment must be a StepOutcomeAssessment")
        if not isinstance(decision, StepProgressTransitionDecision):
            raise TypeError("decision must be a StepProgressTransitionDecision")

    @staticmethod
    def _validate_identity_binding(
        assessment: StepOutcomeAssessment,
        decision: StepProgressTransitionDecision,
    ) -> None:
        mismatches = tuple(
            name
            for name, assessment_value, decision_value in (
                (
                    "assessment_id",
                    assessment.assessment_id,
                    decision.assessment_id,
                ),
                ("plan_id", assessment.plan_id, decision.plan_id),
                ("run_id", assessment.run_id, decision.run_id),
                ("step_id", assessment.step_id, decision.step_id),
            )
            if assessment_value != decision_value
        )
        if mismatches:
            raise TransitionAssessmentBindingError(
                "assessment and transition decision differ in " + ", ".join(mismatches)
            )

    @staticmethod
    def _validate_causal_binding(
        assessment: StepOutcomeAssessment,
        decision: StepProgressTransitionDecision,
    ) -> None:
        if assessment.status is not StepOutcomeStatus.SATISFIED:
            raise TransitionAssessmentBindingError(
                "an actionable transition requires a SATISFIED assessment"
            )
        if assessment.run_revision > decision.observed_revision:
            raise TransitionAssessmentBindingError(
                "assessment observes a revision later than the transition decision"
            )
        if assessment.assessed_at > decision.decided_at:
            raise TransitionAssessmentBindingError(
                "assessment cannot postdate the transition decision"
            )

    @staticmethod
    def _validate_evidence_binding(
        run: PlanRun,
        assessment: StepOutcomeAssessment,
        decision: StepProgressTransitionDecision,
    ) -> None:
        observations = {
            observation.observation_id: observation for observation in run.observations
        }
        for evidence_id in assessment.evidence_ids:
            observation = observations.get(evidence_id)
            if observation is None:
                raise TransitionAssessmentBindingError(
                    f"assessment evidence {evidence_id} is absent from the PlanRun"
                )
            if observation.step_id != decision.step_id:
                raise TransitionAssessmentBindingError(
                    f"assessment evidence {evidence_id} is not scoped to the step"
                )

        current_step_evidence_ids = {
            observation.observation_id
            for observation in run.observations
            if observation.step_id == decision.step_id
        }
        if set(assessment.evidence_ids) != current_step_evidence_ids:
            raise TransitionAssessmentBindingError(
                "assessment does not cover the exact current step evidence basis"
            )

    @staticmethod
    def _progress(run: PlanRun, step_id: str) -> StepProgress:
        return next(item for item in run.step_progress if item.step_id == step_id)

    def _new_update_id(
        self,
        run: PlanRun,
        assessment: StepOutcomeAssessment,
        decision: StepProgressTransitionDecision,
    ) -> str:
        try:
            update_id = self._update_id_factory()
        except Exception as exc:
            raise StepProgressUpdateGenerationError(
                "StepProgressUpdate ID factory failed"
            ) from exc
        if (
            not isinstance(update_id, str)
            or not update_id
            or update_id != update_id.strip()
        ):
            raise StepProgressUpdateGenerationError(
                "StepProgressUpdate ID factory returned an invalid identifier"
            )
        if update_id in {
            run.run_id,
            assessment.assessment_id,
            decision.decision_id,
            decision.step_id,
        }:
            raise StepProgressUpdateGenerationError(
                "StepProgressUpdate identity must be independent from its lineage"
            )
        return update_id

    def _updated_at(
        self,
        run: PlanRun,
        decision: StepProgressTransitionDecision,
    ) -> datetime:
        try:
            value = self._clock()
        except Exception as exc:
            raise StepProgressUpdateGenerationError(
                "StepProgressUpdate clock failed"
            ) from exc
        try:
            updated_at = utc_time(value, "StepProgressUpdate updated_at")
        except (TypeError, ValueError) as exc:
            raise StepProgressUpdateGenerationError(
                "StepProgressUpdate clock returned an invalid timestamp"
            ) from exc
        if updated_at < run.updated_at or updated_at < decision.decided_at:
            raise StepProgressUpdateGenerationError(
                "StepProgressUpdate timestamp predates its Run or decision"
            )
        return updated_at
