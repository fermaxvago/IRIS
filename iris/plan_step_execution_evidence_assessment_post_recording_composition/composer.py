"""Compose one exact WP050 result with WP027 complete-evidence assessment."""

from __future__ import annotations

from datetime import datetime

from iris.context import ContextBudget, ContextCandidate, ContextUncertainty
from iris.execution.models import ExecutionInput
from iris.orchestrator import HandlerAvailability
from iris.outcome_assessment import StepOutcomeAssessment
from iris.plan_runs import PlanRun, validate_plan_run
from iris.plan_step_evidence_assessment import PlanStepEvidenceAssessor
from iris.plan_step_execution_evidence_assessment_post_recording_composition.errors import (
    PlanStepExecutionEvidenceAssessmentPostRecordingCompositionInvariantError,
)
from iris.plan_step_execution_evidence_assessment_post_recording_composition.models import (
    PlanStepExecutionEvidenceAssessmentPostRecordingCompositionResult,
    _validate_assessment,
)
from iris.plan_step_execution_result_recording_post_recording_composition import (
    PlanStepExecutionResultRecordingPostRecordingComposer,
    PlanStepExecutionResultRecordingPostRecordingCompositionResult,
)
from iris.plan_step_execution_start_post_recording_composition import (
    PlanStepExecutionStartPostRecordingComposer,
)
from iris.planning import Plan


class PlanStepExecutionEvidenceAssessmentPostRecordingComposer:
    """Assess one exact optional Step C recording through WP027, then stop."""

    def __init__(
        self,
        *,
        recording_composer: PlanStepExecutionResultRecordingPostRecordingComposer,
        assessor: PlanStepEvidenceAssessor | None = None,
    ) -> None:
        if not isinstance(
            recording_composer,
            PlanStepExecutionResultRecordingPostRecordingComposer,
        ):
            raise TypeError(
                "recording_composer must be a "
                "PlanStepExecutionResultRecordingPostRecordingComposer"
            )
        if assessor is not None and not isinstance(assessor, PlanStepEvidenceAssessor):
            raise TypeError("assessor must be a PlanStepEvidenceAssessor")
        self._recording_composer = recording_composer
        self._assessor = PlanStepEvidenceAssessor() if assessor is None else assessor

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
    ) -> PlanStepExecutionEvidenceAssessmentPostRecordingCompositionResult:
        """Invoke WP050 once, optionally assess exact Step C evidence, then stop."""

        # Preserve WP050's causal/lazy input semantics by delegating first.
        recording_composition = self._recording_composer.compose(
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
        self._validate_recording_composition(
            plan,
            run,
            step_id,
            post_recording_budget,
            post_recording_created_at,
            post_recording_execution_input,
            recording_composition,
        )

        recording = recording_composition.post_recording_execution_recording_result
        if recording is None:
            return self._result(recording_composition, None)

        assessment = self._assessor.assess(
            plan,
            recording.recorded_run,
            recording.step_id,
        )
        try:
            _validate_assessment(recording, assessment)
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            invariant = PlanStepExecutionEvidenceAssessmentPostRecordingCompositionInvariantError
            if isinstance(exc, invariant):
                raise
            raise invariant("WP027 returned contradictory Step C assessment") from exc
        return self._result(recording_composition, assessment)

    @staticmethod
    def _validate_recording_composition(
        plan: Plan,
        source_run: PlanRun,
        processed_step_id: str,
        post_recording_budget: ContextBudget,
        post_recording_created_at: datetime,
        post_recording_execution_input: ExecutionInput | None,
        result: PlanStepExecutionResultRecordingPostRecordingCompositionResult,
    ) -> None:
        invariant = (
            PlanStepExecutionEvidenceAssessmentPostRecordingCompositionInvariantError
        )
        if not isinstance(
            result,
            PlanStepExecutionResultRecordingPostRecordingCompositionResult,
        ):
            raise invariant(
                "WP050 must return a "
                "PlanStepExecutionResultRecordingPostRecordingCompositionResult"
            )
        try:
            PlanStepExecutionStartPostRecordingComposer._validate_binding_result(
                plan,
                source_run,
                processed_step_id,
                post_recording_budget,
                post_recording_created_at,
                post_recording_execution_input,
                result,
            )
            PlanStepExecutionResultRecordingPostRecordingCompositionResult.__post_init__(
                result
            )
            recording = result.post_recording_execution_recording_result
            if recording is not None:
                validate_plan_run(plan, recording.recorded_run)
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise invariant("WP050 returned contradictory cumulative lineage") from exc

    @staticmethod
    def _result(
        recording_composition: (
            PlanStepExecutionResultRecordingPostRecordingCompositionResult
        ),
        assessment: StepOutcomeAssessment | None,
    ) -> PlanStepExecutionEvidenceAssessmentPostRecordingCompositionResult:
        return PlanStepExecutionEvidenceAssessmentPostRecordingCompositionResult(
            assessment=recording_composition.assessment,
            transition_decision=recording_composition.transition_decision,
            progress_update=recording_composition.progress_update,
            advancement_result=recording_composition.advancement_result,
            handling_preparation=recording_composition.handling_preparation,
            work_subject=recording_composition.work_subject,
            context_snapshot=recording_composition.context_snapshot,
            orchestration_decision=recording_composition.orchestration_decision,
            execution_request=recording_composition.execution_request,
            execution_binding=recording_composition.execution_binding,
            execution_start_result=recording_composition.execution_start_result,
            execution_recording_result=(
                recording_composition.execution_recording_result
            ),
            post_recording_assessment=recording_composition.post_recording_assessment,
            post_recording_transition_decision=(
                recording_composition.post_recording_transition_decision
            ),
            post_recording_progress_update=(
                recording_composition.post_recording_progress_update
            ),
            post_recording_advancement_result=(
                recording_composition.post_recording_advancement_result
            ),
            post_recording_handling_preparation=(
                recording_composition.post_recording_handling_preparation
            ),
            post_recording_work_subject=(
                recording_composition.post_recording_work_subject
            ),
            post_recording_context_snapshot=(
                recording_composition.post_recording_context_snapshot
            ),
            post_recording_orchestration_decision=(
                recording_composition.post_recording_orchestration_decision
            ),
            post_recording_execution_request=(
                recording_composition.post_recording_execution_request
            ),
            post_recording_execution_binding=(
                recording_composition.post_recording_execution_binding
            ),
            post_recording_execution_start_result=(
                recording_composition.post_recording_execution_start_result
            ),
            post_recording_execution_recording_result=(
                recording_composition.post_recording_execution_recording_result
            ),
            post_recording_execution_assessment=assessment,
        )
