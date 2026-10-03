"""Compose one bounded WP039 reaction with the existing WP021 boundary."""

from __future__ import annotations

from datetime import datetime

from iris.context import ContextBudget, ContextCandidate, ContextUncertainty
from iris.execution.models import ExecutionInput
from iris.orchestrator import HandlerAvailability
from iris.outcome_assessment import StepOutcomeAssessment
from iris.plan_runs import PlanObservation, PlanRun
from iris.plan_step_execution_evidence_assessment_composition import (
    PlanStepExecutionEvidenceAssessmentComposer,
    PlanStepExecutionEvidenceAssessmentCompositionResult,
)
from iris.plan_step_execution_result_recording import (
    PlanStepExecutionResultRecordingResult,
)
from iris.plan_step_execution_start import PlanStepExecutionStartResult
from iris.plan_step_execution_transition_decision_composition.errors import (
    PlanStepExecutionTransitionDecisionCompositionInvariantError,
)
from iris.plan_step_execution_transition_decision_composition.models import (
    PlanStepExecutionTransitionDecisionCompositionResult,
)
from iris.planning import Plan, PlanStep
from iris.step_progress_transition import (
    StepProgressTransitionDecider,
    StepProgressTransitionDecision,
    StepProgressTransitionError,
    validate_step_progress_transition_decision_current,
)


class PlanStepExecutionTransitionDecisionComposer:
    """Append at most one exact WP021 decision to one WP039 reaction."""

    def __init__(
        self,
        *,
        evidence_assessment_composer: PlanStepExecutionEvidenceAssessmentComposer,
        transition_decider: StepProgressTransitionDecider | None = None,
    ) -> None:
        if not isinstance(
            evidence_assessment_composer,
            PlanStepExecutionEvidenceAssessmentComposer,
        ):
            raise TypeError(
                "evidence_assessment_composer must be a "
                "PlanStepExecutionEvidenceAssessmentComposer"
            )
        if transition_decider is not None and not isinstance(
            transition_decider, StepProgressTransitionDecider
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
    ) -> PlanStepExecutionTransitionDecisionCompositionResult:
        """Invoke WP039 once, optionally decide for its assessment, then stop."""

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
        )
        self._validate_evidence_composition(
            plan,
            run,
            step_id,
            evidence_composition,
        )

        assessment = evidence_composition.post_recording_assessment
        if assessment is None:
            return self._result(evidence_composition, None)

        recording = evidence_composition.execution_recording_result
        if recording is None:  # guarded by delegated-result validation
            raise PlanStepExecutionTransitionDecisionCompositionInvariantError(
                "post-recording assessment requires its canonical recording"
            )
        canonical_step = self._canonical_step(plan, recording.step_id)
        decision = self._transition_decider.decide(
            plan,
            recording.recorded_run,
            canonical_step,
            assessment,
        )
        self._validate_decision(
            plan,
            recording,
            assessment,
            decision,
        )
        return self._result(evidence_composition, decision)

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
    def _validate_evidence_composition(
        plan: Plan,
        source_run: PlanRun,
        processed_step_id: str,
        result: PlanStepExecutionEvidenceAssessmentCompositionResult,
    ) -> None:
        invariant = PlanStepExecutionTransitionDecisionCompositionInvariantError
        if not isinstance(result, PlanStepExecutionEvidenceAssessmentCompositionResult):
            raise invariant(
                "WP039 must return a "
                "PlanStepExecutionEvidenceAssessmentCompositionResult"
            )
        inherited_assessment = result.assessment
        inherited_decision = result.transition_decision
        if not isinstance(
            inherited_assessment, StepOutcomeAssessment
        ) or not isinstance(inherited_decision, StepProgressTransitionDecision):
            raise invariant(
                "WP039 result must preserve canonical inherited assessment artifacts"
            )
        if (
            inherited_assessment.plan_id != plan.plan_id
            or inherited_assessment.run_id != source_run.run_id
            or inherited_assessment.run_revision != source_run.revision
            or inherited_assessment.step_id != processed_step_id
            or inherited_decision.plan_id != plan.plan_id
            or inherited_decision.run_id != source_run.run_id
            or inherited_decision.observed_revision != source_run.revision
            or inherited_decision.step_id != processed_step_id
            or inherited_decision.assessment_id != inherited_assessment.assessment_id
        ):
            raise invariant(
                "WP039 result does not match the supplied Plan, source Run, and step"
            )

        recording = result.execution_recording_result
        assessment = result.post_recording_assessment
        start = result.execution_start_result
        if (recording is None) != (assessment is None):
            raise invariant(
                "WP039 recording and post-recording assessment must share presence"
            )
        if (start is None) != (recording is None):
            raise invariant("WP039 start and recording must share one presence shape")
        if recording is None:
            return
        if not isinstance(recording, PlanStepExecutionResultRecordingResult):
            raise invariant("WP039 recording result must be canonical or None")
        if not isinstance(start, PlanStepExecutionStartResult) or not isinstance(
            assessment, StepOutcomeAssessment
        ):
            raise invariant("WP039 recording lineage contains noncanonical artifacts")

        recorded_run = recording.recorded_run
        observation = recording.observation
        if not isinstance(recorded_run, PlanRun) or not isinstance(
            observation, PlanObservation
        ):
            raise invariant("WP039 recording must contain canonical Run evidence")
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
            or observation.observation_id != recording.observation_id
            or observation.run_id != recording.run_id
            or observation.step_id != recording.step_id
            or observation.source != "execution"
            or observation.source_reference != recording.execution_id
            or observation.kind != "execution_result"
            or observation not in recorded_run.observations
        ):
            raise invariant("WP039 recording contradicts the cumulative lineage")
        if (
            assessment.plan_id != recording.plan_id
            or assessment.run_id != recording.run_id
            or assessment.run_revision != recorded_run.revision
            or assessment.step_id != recording.step_id
            or recording.observation_id not in assessment.evidence_ids
        ):
            raise invariant(
                "WP039 assessment contradicts its exact execution recording"
            )

    @staticmethod
    def _canonical_step(plan: Plan, step_id: str) -> PlanStep:
        step = next((item for item in plan.steps if item.step_id == step_id), None)
        if step is None:
            raise PlanStepExecutionTransitionDecisionCompositionInvariantError(
                "WP039 recording references an unknown PlanStep"
            )
        return step

    @staticmethod
    def _validate_decision(
        plan: Plan,
        recording: PlanStepExecutionResultRecordingResult,
        assessment: StepOutcomeAssessment,
        decision: StepProgressTransitionDecision,
    ) -> None:
        invariant = PlanStepExecutionTransitionDecisionCompositionInvariantError
        if not isinstance(decision, StepProgressTransitionDecision):
            raise invariant("WP021 must return a StepProgressTransitionDecision")
        try:
            validate_step_progress_transition_decision_current(
                plan,
                recording.recorded_run,
                decision,
            )
        except (StepProgressTransitionError, TypeError, ValueError) as exc:
            raise invariant(
                "WP021 returned a decision that is not current for the recorded Run"
            ) from exc
        if (
            decision.plan_id != assessment.plan_id
            or decision.plan_id != recording.plan_id
            or decision.run_id != assessment.run_id
            or decision.run_id != recording.run_id
            or decision.observed_revision != assessment.run_revision
            or decision.observed_revision != recording.recorded_run.revision
            or decision.step_id != assessment.step_id
            or decision.step_id != recording.step_id
            or decision.assessment_id != assessment.assessment_id
        ):
            raise invariant(
                "WP021 decision contradicts the exact WP039 assessment lineage"
            )

    @staticmethod
    def _result(
        evidence_composition: PlanStepExecutionEvidenceAssessmentCompositionResult,
        decision: StepProgressTransitionDecision | None,
    ) -> PlanStepExecutionTransitionDecisionCompositionResult:
        return PlanStepExecutionTransitionDecisionCompositionResult(
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
            execution_recording_result=(
                evidence_composition.execution_recording_result
            ),
            post_recording_assessment=evidence_composition.post_recording_assessment,
            post_recording_transition_decision=decision,
        )
