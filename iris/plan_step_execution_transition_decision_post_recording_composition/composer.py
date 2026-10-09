"""Compose one exact WP051 result with the canonical WP021 decision boundary."""

from __future__ import annotations

from datetime import datetime

from iris.context import ContextBudget, ContextCandidate, ContextUncertainty
from iris.execution.models import ExecutionInput
from iris.orchestrator import HandlerAvailability
from iris.outcome_assessment import StepOutcomeAssessment
from iris.plan_runs import PlanRun, validate_plan_run
from iris.plan_step_execution_evidence_assessment_post_recording_composition import (
    PlanStepExecutionEvidenceAssessmentPostRecordingComposer,
    PlanStepExecutionEvidenceAssessmentPostRecordingCompositionResult,
)
from iris.plan_step_execution_result_recording import (
    PlanStepExecutionResultRecordingResult,
)
from iris.plan_step_execution_transition_decision_post_recording_composition.errors import (
    PlanStepExecutionTransitionDecisionPostRecordingCompositionInvariantError,
)
from iris.plan_step_execution_transition_decision_post_recording_composition.models import (
    PlanStepExecutionTransitionDecisionPostRecordingCompositionResult,
    _validate_transition_decision,
)
from iris.planning import Plan, PlanStep
from iris.step_progress_transition import (
    StepProgressTransitionDecider,
    StepProgressTransitionDecision,
    StepProgressTransitionError,
    validate_step_progress_transition_decision_current,
)


class PlanStepExecutionTransitionDecisionPostRecordingComposer:
    """Append one optional exact WP021 decision to one exact WP051 result."""

    def __init__(
        self,
        *,
        evidence_assessment_composer: (
            PlanStepExecutionEvidenceAssessmentPostRecordingComposer
        ),
        transition_decider: StepProgressTransitionDecider | None = None,
    ) -> None:
        if not isinstance(
            evidence_assessment_composer,
            PlanStepExecutionEvidenceAssessmentPostRecordingComposer,
        ):
            raise TypeError(
                "evidence_assessment_composer must be a "
                "PlanStepExecutionEvidenceAssessmentPostRecordingComposer"
            )
        if transition_decider is not None and not isinstance(
            transition_decider,
            StepProgressTransitionDecider,
        ):
            raise TypeError(
                "transition_decider must be a StepProgressTransitionDecider"
            )
        self._evidence_assessment_composer = evidence_assessment_composer
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
        *,
        candidates: tuple[ContextCandidate, ...],
        budget: ContextBudget,
        uncertainties: tuple[ContextUncertainty, ...] = (),
        created_at: datetime,
        availability: HandlerAvailability,
        execution_input: ExecutionInput | None = None,
        post_recording_candidates: tuple[ContextCandidate, ...],
        post_recording_budget: ContextBudget,
        post_recording_uncertainties: tuple[ContextUncertainty, ...] = (),
        post_recording_created_at: datetime,
        post_recording_availability: HandlerAvailability,
        post_recording_execution_input: ExecutionInput | None = None,
    ) -> PlanStepExecutionTransitionDecisionPostRecordingCompositionResult:
        """Invoke WP051 once, optionally decide for exact Step C, then stop."""

        # Delegate first to preserve WP050/WP051 causal and lazy validation.
        evidence_composition = self._evidence_assessment_composer.compose(
            plan,
            run,
            step_id,
            candidates=candidates,
            budget=budget,
            uncertainties=uncertainties,
            created_at=created_at,
            availability=availability,
            execution_input=execution_input,
            post_recording_candidates=post_recording_candidates,
            post_recording_budget=post_recording_budget,
            post_recording_uncertainties=post_recording_uncertainties,
            post_recording_created_at=post_recording_created_at,
            post_recording_availability=post_recording_availability,
            post_recording_execution_input=post_recording_execution_input,
        )
        self._validate_evidence_composition(
            plan,
            run,
            step_id,
            post_recording_budget,
            post_recording_created_at,
            post_recording_execution_input,
            evidence_composition,
        )

        assessment = evidence_composition.post_recording_execution_assessment
        if assessment is None:
            return self._result(evidence_composition, None)

        recording = evidence_composition.post_recording_execution_recording_result
        if recording is None:  # guarded by delegated-result validation
            raise PlanStepExecutionTransitionDecisionPostRecordingCompositionInvariantError(
                "Step C assessment requires its exact recording"
            )
        canonical_step = self._canonical_step(plan, recording.step_id)
        decision = self._transition_decider.decide(
            plan,
            recording.recorded_run,
            canonical_step,
            assessment,
        )
        self._validate_decision(plan, recording, assessment, decision)
        return self._result(evidence_composition, decision)

    @staticmethod
    def _validate_evidence_composition(
        plan: Plan,
        source_run: PlanRun,
        processed_step_id: str,
        post_recording_budget: ContextBudget,
        post_recording_created_at: datetime,
        post_recording_execution_input: ExecutionInput | None,
        result: PlanStepExecutionEvidenceAssessmentPostRecordingCompositionResult,
    ) -> None:
        invariant = (
            PlanStepExecutionTransitionDecisionPostRecordingCompositionInvariantError
        )
        if not isinstance(
            result,
            PlanStepExecutionEvidenceAssessmentPostRecordingCompositionResult,
        ):
            raise invariant(
                "WP051 must return a "
                "PlanStepExecutionEvidenceAssessmentPostRecordingCompositionResult"
            )
        try:
            PlanStepExecutionEvidenceAssessmentPostRecordingComposer._validate_recording_composition(
                plan,
                source_run,
                processed_step_id,
                post_recording_budget,
                post_recording_created_at,
                post_recording_execution_input,
                result,
            )
            PlanStepExecutionEvidenceAssessmentPostRecordingCompositionResult.__post_init__(
                result
            )
            recording = result.post_recording_execution_recording_result
            if recording is not None:
                validate_plan_run(plan, recording.recorded_run)
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise invariant("WP051 returned contradictory cumulative lineage") from exc

    @staticmethod
    def _canonical_step(plan: Plan, step_id: str) -> PlanStep:
        step = next((item for item in plan.steps if item.step_id == step_id), None)
        if step is None:
            raise PlanStepExecutionTransitionDecisionPostRecordingCompositionInvariantError(
                "Step C recording references an unknown PlanStep"
            )
        return step

    @staticmethod
    def _validate_decision(
        plan: Plan,
        recording: PlanStepExecutionResultRecordingResult,
        assessment: StepOutcomeAssessment,
        decision: StepProgressTransitionDecision,
    ) -> None:
        invariant = (
            PlanStepExecutionTransitionDecisionPostRecordingCompositionInvariantError
        )
        _validate_transition_decision(recording, assessment, decision)
        try:
            validate_step_progress_transition_decision_current(
                plan,
                recording.recorded_run,
                decision,
            )
        except (StepProgressTransitionError, TypeError, ValueError) as exc:
            raise invariant(
                "WP021 returned a decision that is not current for Step C"
            ) from exc

    @staticmethod
    def _result(
        evidence_composition: (
            PlanStepExecutionEvidenceAssessmentPostRecordingCompositionResult
        ),
        decision: StepProgressTransitionDecision | None,
    ) -> PlanStepExecutionTransitionDecisionPostRecordingCompositionResult:
        return PlanStepExecutionTransitionDecisionPostRecordingCompositionResult(
            assessment=evidence_composition.assessment,
            transition_decision=evidence_composition.transition_decision,
            progress_update=evidence_composition.progress_update,
            advancement_result=evidence_composition.advancement_result,
            handling_preparation=evidence_composition.handling_preparation,
            work_subject=evidence_composition.work_subject,
            context_snapshot=evidence_composition.context_snapshot,
            orchestration_decision=evidence_composition.orchestration_decision,
            execution_request=evidence_composition.execution_request,
            execution_binding=evidence_composition.execution_binding,
            execution_start_result=evidence_composition.execution_start_result,
            execution_recording_result=evidence_composition.execution_recording_result,
            post_recording_assessment=evidence_composition.post_recording_assessment,
            post_recording_transition_decision=(
                evidence_composition.post_recording_transition_decision
            ),
            post_recording_progress_update=(
                evidence_composition.post_recording_progress_update
            ),
            post_recording_advancement_result=(
                evidence_composition.post_recording_advancement_result
            ),
            post_recording_handling_preparation=(
                evidence_composition.post_recording_handling_preparation
            ),
            post_recording_work_subject=(
                evidence_composition.post_recording_work_subject
            ),
            post_recording_context_snapshot=(
                evidence_composition.post_recording_context_snapshot
            ),
            post_recording_orchestration_decision=(
                evidence_composition.post_recording_orchestration_decision
            ),
            post_recording_execution_request=(
                evidence_composition.post_recording_execution_request
            ),
            post_recording_execution_binding=(
                evidence_composition.post_recording_execution_binding
            ),
            post_recording_execution_start_result=(
                evidence_composition.post_recording_execution_start_result
            ),
            post_recording_execution_recording_result=(
                evidence_composition.post_recording_execution_recording_result
            ),
            post_recording_execution_assessment=(
                evidence_composition.post_recording_execution_assessment
            ),
            post_recording_execution_transition_decision=decision,
        )
