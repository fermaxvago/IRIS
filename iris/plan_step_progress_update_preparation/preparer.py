"""Bounded WP028-to-WP022 progress-update preparation composition."""

from __future__ import annotations

from iris.outcome_assessment import StepOutcomeAssessment
from iris.plan_runs import PlanRun, StepProgressUpdate
from iris.plan_step_evidence_transition import (
    PlanStepEvidenceTransitionComposer,
    PlanStepEvidenceTransitionDecisionResult,
)
from iris.plan_step_progress_update_preparation.errors import (
    PlanStepProgressUpdatePreparationInvariantError,
)
from iris.plan_step_progress_update_preparation.models import (
    PlanStepProgressUpdatePreparationResult,
)
from iris.planning import Plan
from iris.step_progress_transition import (
    StepProgressTransitionAction,
    StepProgressTransitionDecision,
)
from iris.step_progress_update_synthesis import StepProgressUpdateSynthesizer


class PlanStepProgressUpdatePreparer:
    """Prepare zero or one inert update from exactly one WP028 composition."""

    def __init__(
        self,
        *,
        evidence_transition_composer: PlanStepEvidenceTransitionComposer | None = None,
        progress_update_synthesizer: StepProgressUpdateSynthesizer | None = None,
    ) -> None:
        if evidence_transition_composer is not None and not isinstance(
            evidence_transition_composer, PlanStepEvidenceTransitionComposer
        ):
            raise TypeError(
                "evidence_transition_composer must be a "
                "PlanStepEvidenceTransitionComposer"
            )
        if progress_update_synthesizer is not None and not isinstance(
            progress_update_synthesizer, StepProgressUpdateSynthesizer
        ):
            raise TypeError(
                "progress_update_synthesizer must be a StepProgressUpdateSynthesizer"
            )
        self._evidence_transition_composer = (
            PlanStepEvidenceTransitionComposer()
            if evidence_transition_composer is None
            else evidence_transition_composer
        )
        self._progress_update_synthesizer = (
            StepProgressUpdateSynthesizer()
            if progress_update_synthesizer is None
            else progress_update_synthesizer
        )

    def prepare(
        self,
        plan: Plan,
        run: PlanRun,
        step_id: str,
    ) -> PlanStepProgressUpdatePreparationResult:
        """Return one assessment/decision pair and its optional inert update."""

        self._validate_input_types(plan, run, step_id)
        transition_result = self._evidence_transition_composer.compose(
            plan, run, step_id
        )
        self._validate_transition_result(plan, run, step_id, transition_result)

        assessment = transition_result.assessment
        decision = transition_result.transition_decision
        if decision.action is StepProgressTransitionAction.NO_TRANSITION:
            return PlanStepProgressUpdatePreparationResult(
                assessment,
                decision,
                None,
            )

        update = self._progress_update_synthesizer.synthesize(
            plan,
            run,
            assessment,
            decision,
        )
        self._validate_update(run, assessment, decision, update)
        return PlanStepProgressUpdatePreparationResult(
            assessment,
            decision,
            update,
        )

    @staticmethod
    def _validate_input_types(plan: Plan, run: PlanRun, step_id: str) -> None:
        if not isinstance(plan, Plan):
            raise TypeError("plan must be a Plan")
        if not isinstance(run, PlanRun):
            raise TypeError("run must be a PlanRun")
        if not isinstance(step_id, str):
            raise TypeError("step_id must be a string")

    @staticmethod
    def _validate_transition_result(
        plan: Plan,
        run: PlanRun,
        step_id: str,
        result: PlanStepEvidenceTransitionDecisionResult,
    ) -> None:
        if not isinstance(result, PlanStepEvidenceTransitionDecisionResult):
            raise PlanStepProgressUpdatePreparationInvariantError(
                "WP028 evidence transition composer must return a "
                "PlanStepEvidenceTransitionDecisionResult"
            )
        assessment = result.assessment
        decision = result.transition_decision
        if not isinstance(assessment, StepOutcomeAssessment) or not isinstance(
            decision, StepProgressTransitionDecision
        ):
            raise PlanStepProgressUpdatePreparationInvariantError(
                "WP028 result must contain canonical assessment and decision types"
            )
        if (
            assessment.plan_id != plan.plan_id
            or assessment.run_id != run.run_id
            or assessment.run_revision != run.revision
            or assessment.step_id != step_id
            or decision.plan_id != plan.plan_id
            or decision.run_id != run.run_id
            or decision.observed_revision != run.revision
            or decision.step_id != step_id
            or decision.assessment_id != assessment.assessment_id
        ):
            raise PlanStepProgressUpdatePreparationInvariantError(
                "WP028 result does not match the supplied Plan, Run revision, and step"
            )

    @staticmethod
    def _validate_update(
        run: PlanRun,
        assessment: StepOutcomeAssessment,
        decision: StepProgressTransitionDecision,
        update: StepProgressUpdate,
    ) -> None:
        if not isinstance(update, StepProgressUpdate):
            raise PlanStepProgressUpdatePreparationInvariantError(
                "WP022 progress update synthesizer must return a StepProgressUpdate"
            )
        if (
            update.run_id != run.run_id
            or update.expected_revision != run.revision
            or update.expected_revision != decision.observed_revision
            or update.step_id != decision.step_id
            or update.new_state is not decision.target_state
            or update.evidence_ids != assessment.evidence_ids
            or update.provenance.source_type != "step_progress_transition"
            or update.provenance.source_id != decision.decision_id
            or update.provenance.actor is not None
        ):
            raise PlanStepProgressUpdatePreparationInvariantError(
                "WP022 update does not match the supplied Run, assessment, and decision"
            )
