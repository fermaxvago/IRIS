"""One-shot complete-evidence assessment and transition-decision composition."""

from __future__ import annotations

from iris.outcome_assessment import StepOutcomeAssessment
from iris.plan_runs import PlanRun, UnknownPlanStepError
from iris.plan_step_evidence_assessment import PlanStepEvidenceAssessor
from iris.plan_step_evidence_transition.errors import (
    PlanStepEvidenceTransitionInvariantError,
)
from iris.plan_step_evidence_transition.models import (
    PlanStepEvidenceTransitionDecisionResult,
)
from iris.planning import Plan, PlanStep
from iris.step_progress_transition import (
    StepProgressTransitionDecider,
    StepProgressTransitionDecision,
    validate_step_progress_transition_decision_current,
)


class PlanStepEvidenceTransitionComposer:
    """Assess one Run's complete Step evidence, decide once, and stop."""

    def __init__(
        self,
        *,
        assessor: PlanStepEvidenceAssessor | None = None,
        transition_decider: StepProgressTransitionDecider | None = None,
    ) -> None:
        if assessor is not None and not isinstance(assessor, PlanStepEvidenceAssessor):
            raise TypeError("assessor must be a PlanStepEvidenceAssessor")
        if transition_decider is not None and not isinstance(
            transition_decider, StepProgressTransitionDecider
        ):
            raise TypeError(
                "transition_decider must be a StepProgressTransitionDecider"
            )
        self._assessor = PlanStepEvidenceAssessor() if assessor is None else assessor
        self._transition_decider = (
            StepProgressTransitionDecider()
            if transition_decider is None
            else transition_decider
        )

    def compose(
        self,
        plan: Plan,
        run: PlanRun,
        step_id: str,
    ) -> PlanStepEvidenceTransitionDecisionResult:
        """Return one current assessment/decision pair without mutation."""

        assessment = self._assessor.assess(plan, run, step_id)
        self._validate_assessment(plan, run, step_id, assessment)
        step = self._canonical_step(plan, step_id)
        decision = self._transition_decider.decide(plan, run, step, assessment)
        if not isinstance(decision, StepProgressTransitionDecision):
            raise PlanStepEvidenceTransitionInvariantError(
                "transition decider must return a StepProgressTransitionDecision"
            )
        validate_step_progress_transition_decision_current(plan, run, decision)
        self._validate_decision(plan, run, step, assessment, decision)
        return PlanStepEvidenceTransitionDecisionResult(assessment, decision)

    @staticmethod
    def _canonical_step(plan: Plan, step_id: str) -> PlanStep:
        step = next((item for item in plan.steps if item.step_id == step_id), None)
        if step is None:
            raise UnknownPlanStepError(f"unknown Plan step {step_id}")
        return step

    @staticmethod
    def _validate_assessment(
        plan: Plan,
        run: PlanRun,
        step_id: str,
        assessment: StepOutcomeAssessment,
    ) -> None:
        if not isinstance(assessment, StepOutcomeAssessment):
            raise PlanStepEvidenceTransitionInvariantError(
                "assessor must return a StepOutcomeAssessment"
            )
        if (
            assessment.plan_id != plan.plan_id
            or assessment.run_id != run.run_id
            or assessment.run_revision != run.revision
            or assessment.step_id != step_id
        ):
            raise PlanStepEvidenceTransitionInvariantError(
                "assessment does not match the supplied Plan, Run revision, and step"
            )

    @staticmethod
    def _validate_decision(
        plan: Plan,
        run: PlanRun,
        step: PlanStep,
        assessment: StepOutcomeAssessment,
        decision: StepProgressTransitionDecision,
    ) -> None:
        if (
            decision.plan_id != plan.plan_id
            or decision.run_id != run.run_id
            or decision.observed_revision != run.revision
            or decision.step_id != step.step_id
            or decision.assessment_id != assessment.assessment_id
        ):
            raise PlanStepEvidenceTransitionInvariantError(
                "transition decision does not match its assessment and supplied Run"
            )
