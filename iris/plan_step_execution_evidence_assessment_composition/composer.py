"""Compose one bounded WP038 reaction with the existing WP027 boundary."""

from __future__ import annotations

from datetime import datetime

from iris.context import ContextBudget, ContextCandidate, ContextUncertainty
from iris.execution.models import ExecutionInput
from iris.orchestrator import HandlerAvailability
from iris.outcome_assessment import StepOutcomeAssessment
from iris.plan_run_advancement import PlanRunProgressAdvanceResult
from iris.plan_runs import PlanObservation, PlanRun, StepProgressUpdate
from iris.plan_step_evidence_assessment import PlanStepEvidenceAssessor
from iris.plan_step_execution_evidence_assessment_composition.errors import (
    PlanStepExecutionEvidenceAssessmentCompositionInvariantError,
)
from iris.plan_step_execution_evidence_assessment_composition.models import (
    PlanStepExecutionEvidenceAssessmentCompositionResult,
)
from iris.plan_step_execution_result_recording import (
    PlanStepExecutionResultRecordingResult,
)
from iris.plan_step_execution_result_recording_composition import (
    PlanStepExecutionResultRecordingComposer,
    PlanStepExecutionResultRecordingCompositionResult,
)
from iris.plan_step_execution_start import PlanStepExecutionStartResult
from iris.planning import Plan
from iris.step_progress_transition import StepProgressTransitionDecision


class PlanStepExecutionEvidenceAssessmentComposer:
    """Append at most one exact WP027 assessment to one WP038 reaction."""

    def __init__(
        self,
        *,
        recording_composer: PlanStepExecutionResultRecordingComposer,
        assessor: PlanStepEvidenceAssessor | None = None,
    ) -> None:
        if not isinstance(recording_composer, PlanStepExecutionResultRecordingComposer):
            raise TypeError(
                "recording_composer must be a PlanStepExecutionResultRecordingComposer"
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
    ) -> PlanStepExecutionEvidenceAssessmentCompositionResult:
        """Invoke WP038 once, optionally assess its recorded Step, then stop."""

        self._validate_input_types(
            plan,
            run,
            step_id,
            candidates,
            budget,
            uncertainties,
            created_at,
            availability,
        )
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
        )
        self._validate_recording_composition(
            plan,
            run,
            step_id,
            recording_composition,
        )

        recording = recording_composition.execution_recording_result
        if recording is None:
            return self._result(recording_composition, None)

        post_recording_assessment = self._assessor.assess(
            plan,
            recording.recorded_run,
            recording.step_id,
        )
        self._validate_post_recording_assessment(
            plan,
            recording,
            post_recording_assessment,
        )
        return self._result(recording_composition, post_recording_assessment)

    @staticmethod
    def _validate_input_types(
        plan: Plan,
        run: PlanRun,
        step_id: str,
        candidates: tuple[ContextCandidate, ...],
        budget: ContextBudget,
        uncertainties: tuple[ContextUncertainty, ...],
        created_at: datetime,
        availability: HandlerAvailability,
    ) -> None:
        if not isinstance(plan, Plan):
            raise TypeError("plan must be a Plan")
        if not isinstance(run, PlanRun):
            raise TypeError("run must be a PlanRun")
        if not isinstance(step_id, str):
            raise TypeError("step_id must be a string")
        if not isinstance(candidates, tuple) or any(
            not isinstance(candidate, ContextCandidate) for candidate in candidates
        ):
            raise TypeError("candidates must be a tuple of ContextCandidate")
        if not isinstance(budget, ContextBudget):
            raise TypeError("budget must be ContextBudget")
        if not isinstance(uncertainties, tuple) or any(
            not isinstance(uncertainty, ContextUncertainty)
            for uncertainty in uncertainties
        ):
            raise TypeError("uncertainties must be a tuple of ContextUncertainty")
        if not isinstance(created_at, datetime):
            raise TypeError("created_at must be a datetime")
        if not isinstance(availability, HandlerAvailability):
            raise TypeError("availability must be a HandlerAvailability")

    @staticmethod
    def _validate_recording_composition(
        plan: Plan,
        source_run: PlanRun,
        processed_step_id: str,
        result: PlanStepExecutionResultRecordingCompositionResult,
    ) -> None:
        invariant = PlanStepExecutionEvidenceAssessmentCompositionInvariantError
        if not isinstance(result, PlanStepExecutionResultRecordingCompositionResult):
            raise invariant(
                "WP038 must return a PlanStepExecutionResultRecordingCompositionResult"
            )
        inherited_assessment = result.assessment
        transition = result.transition_decision
        update = result.progress_update
        advancement = result.advancement_result
        start = result.execution_start_result
        recording = result.execution_recording_result
        if not isinstance(
            inherited_assessment, StepOutcomeAssessment
        ) or not isinstance(transition, StepProgressTransitionDecision):
            raise invariant(
                "WP038 result must contain canonical assessment and transition types"
            )
        if (
            inherited_assessment.plan_id != plan.plan_id
            or inherited_assessment.run_id != source_run.run_id
            or inherited_assessment.run_revision != source_run.revision
            or inherited_assessment.step_id != processed_step_id
            or transition.plan_id != plan.plan_id
            or transition.run_id != source_run.run_id
            or transition.observed_revision != source_run.revision
            or transition.step_id != processed_step_id
            or transition.assessment_id != inherited_assessment.assessment_id
        ):
            raise invariant(
                "WP038 result does not match the supplied Plan, source Run, and step"
            )
        if update is not None and not isinstance(update, StepProgressUpdate):
            raise invariant("WP038 progress update must be canonical or None")
        if advancement is not None and not isinstance(
            advancement, PlanRunProgressAdvanceResult
        ):
            raise invariant("WP038 advancement must be canonical or None")
        if start is not None and not isinstance(start, PlanStepExecutionStartResult):
            raise invariant("WP038 start result must be canonical or None")
        if recording is not None and not isinstance(
            recording, PlanStepExecutionResultRecordingResult
        ):
            raise invariant("WP038 recording result must be canonical or None")
        if (update is None) != (advancement is None):
            raise invariant(
                "WP038 progress update and advancement must both exist or be absent"
            )
        if (start is None) != (recording is None):
            raise invariant(
                "WP038 start and recording results must share one presence shape"
            )
        if recording is None:
            return

        assert start is not None
        recorded_run = recording.recorded_run
        observation = recording.observation
        if not isinstance(recorded_run, PlanRun) or not isinstance(
            observation, PlanObservation
        ):
            raise invariant("WP038 recording must contain canonical Run evidence")
        if (
            recording.plan_id != plan.plan_id
            or recording.plan_id != start.plan_id
            or recording.run_id != source_run.run_id
            or recording.run_id != start.run_id
            or recording.step_id != start.step_id
            or recording.execution_id != start.execution_id
            or recorded_run.plan_id != recording.plan_id
            or recorded_run.run_id != recording.run_id
            or recorded_run.goal_id != source_run.goal_id
            or recorded_run.revision != recording.recorded_from_revision + 1
        ):
            raise invariant("WP038 recording contradicts the cumulative lineage")
        if (
            observation.observation_id != recording.observation_id
            or observation.run_id != recording.run_id
            or observation.step_id != recording.step_id
            or observation.source != "execution"
            or observation.source_reference != recording.execution_id
            or observation.kind != "execution_result"
            or observation not in recorded_run.observations
        ):
            raise invariant(
                "WP038 recording observation is not canonical execution evidence"
            )

    @staticmethod
    def _validate_post_recording_assessment(
        plan: Plan,
        recording: PlanStepExecutionResultRecordingResult,
        assessment: StepOutcomeAssessment,
    ) -> None:
        invariant = PlanStepExecutionEvidenceAssessmentCompositionInvariantError
        if not isinstance(assessment, StepOutcomeAssessment):
            raise invariant("WP027 must return a StepOutcomeAssessment")
        if (
            assessment.plan_id != plan.plan_id
            or assessment.plan_id != recording.plan_id
            or assessment.run_id != recording.run_id
            or assessment.run_id != recording.recorded_run.run_id
            or assessment.run_revision != recording.recorded_run.revision
            or assessment.step_id != recording.step_id
            or recording.observation_id not in assessment.evidence_ids
        ):
            raise invariant(
                "WP027 assessment contradicts the exact WP038 recording lineage"
            )

    @staticmethod
    def _result(
        recording_composition: PlanStepExecutionResultRecordingCompositionResult,
        assessment: StepOutcomeAssessment | None,
    ) -> PlanStepExecutionEvidenceAssessmentCompositionResult:
        return PlanStepExecutionEvidenceAssessmentCompositionResult(
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
            post_recording_assessment=assessment,
        )
