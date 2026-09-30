"""Assess the complete canonical evidence basis of one PlanStep and stop."""

from __future__ import annotations

from iris.outcome_assessment import (
    ConservativeStepOutcomeEvaluator,
    StepOutcomeAssessment,
    StepOutcomeEvaluator,
)
from iris.plan_runs import (
    PlanObservation,
    PlanRun,
    UnknownPlanStepError,
    validate_plan_run,
)
from iris.plan_step_evidence_assessment.errors import (
    PlanStepEvidenceAssessmentInvariantError,
    PlanStepEvidenceAssessmentLineageError,
)
from iris.planning import Plan, PlanStep


def _validate_inputs(plan: Plan, run: PlanRun, step_id: str) -> None:
    if not isinstance(plan, Plan):
        raise TypeError("plan must be a Plan")
    if not isinstance(run, PlanRun):
        raise TypeError("run must be a PlanRun")
    if not isinstance(step_id, str):
        raise TypeError("step_id must be a string")
    if not step_id or step_id != step_id.strip():
        raise PlanStepEvidenceAssessmentLineageError(
            "step_id must be a nonblank identifier"
        )


class PlanStepEvidenceAssessor:
    """Evaluate one explicit Run revision's complete Step-scoped evidence."""

    def __init__(self, evaluator: StepOutcomeEvaluator | None = None) -> None:
        if evaluator is not None and not isinstance(evaluator, StepOutcomeEvaluator):
            raise TypeError("evaluator must implement StepOutcomeEvaluator")
        self._evaluator: StepOutcomeEvaluator = (
            ConservativeStepOutcomeEvaluator() if evaluator is None else evaluator
        )

    def assess(
        self,
        plan: Plan,
        run: PlanRun,
        step_id: str,
    ) -> StepOutcomeAssessment:
        """Return one validated assessment without mutating or continuing the Run."""

        _validate_inputs(plan, run, step_id)
        validate_plan_run(plan, run)
        step = self._canonical_step(plan, step_id)
        evidence = tuple(
            observation
            for observation in run.observations
            if observation.step_id == step.step_id
        )
        assessment = self._evaluator.evaluate(plan, run, step, evidence)
        self._validate_assessment(plan, run, step, evidence, assessment)
        return assessment

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
        step: PlanStep,
        evidence: tuple[PlanObservation, ...],
        assessment: StepOutcomeAssessment,
    ) -> None:
        if not isinstance(assessment, StepOutcomeAssessment):
            raise PlanStepEvidenceAssessmentInvariantError(
                "evaluator must return a StepOutcomeAssessment"
            )
        if (
            assessment.plan_id != plan.plan_id
            or assessment.run_id != run.run_id
            or assessment.run_revision != run.revision
            or assessment.step_id != step.step_id
        ):
            raise PlanStepEvidenceAssessmentInvariantError(
                "assessment identity does not match the supplied Plan, Run, and step"
            )
        evidence_ids = tuple(item.observation_id for item in evidence)
        if assessment.evidence_ids != evidence_ids:
            raise PlanStepEvidenceAssessmentInvariantError(
                "assessment must cover the complete canonical Step evidence basis"
            )
        if assessment.assessed_at < run.created_at:
            raise PlanStepEvidenceAssessmentInvariantError(
                "assessment cannot predate PlanRun creation"
            )
        if evidence and assessment.assessed_at < max(
            item.observed_at for item in evidence
        ):
            raise PlanStepEvidenceAssessmentInvariantError(
                "assessment cannot predate its latest evidence"
            )
