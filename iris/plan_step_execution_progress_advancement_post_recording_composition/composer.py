"""Compose one exact WP053 result with optional canonical WP023 advancement."""

from __future__ import annotations

from datetime import datetime

from iris.context import ContextBudget, ContextCandidate, ContextUncertainty
from iris.execution.models import ExecutionInput
from iris.orchestrator import HandlerAvailability
from iris.plan_control import validate_control_decision_current
from iris.plan_run_advancement import (
    PlanRunProgressAdvancer,
    PlanRunProgressAdvanceResult,
)
from iris.plan_runs import PlanRun
from iris.plan_step_execution_progress_advancement_post_recording_composition.errors import (
    PlanStepExecutionProgressAdvancementPostRecordingCompositionInvariantError,
)
from iris.plan_step_execution_progress_advancement_post_recording_composition.models import (
    PlanStepExecutionProgressAdvancementPostRecordingCompositionResult,
)
from iris.plan_step_execution_progress_advancement_post_recording_composition.validation import (
    validate_advancement,
)
from iris.plan_step_execution_progress_update_post_recording_composition import (
    PlanStepExecutionProgressUpdatePostRecordingComposer,
    PlanStepExecutionProgressUpdatePostRecordingCompositionResult,
)
from iris.planning import Plan


class PlanStepExecutionProgressAdvancementPostRecordingComposer:
    """Append at most one exact WP023 advancement to one WP053 composition."""

    def __init__(
        self,
        *,
        progress_update_composer: PlanStepExecutionProgressUpdatePostRecordingComposer,
        progress_advancer: PlanRunProgressAdvancer | None = None,
    ) -> None:
        if not isinstance(
            progress_update_composer,
            PlanStepExecutionProgressUpdatePostRecordingComposer,
        ):
            raise TypeError(
                "progress_update_composer must be a "
                "PlanStepExecutionProgressUpdatePostRecordingComposer"
            )
        if progress_advancer is not None and not isinstance(
            progress_advancer, PlanRunProgressAdvancer
        ):
            raise TypeError("progress_advancer must be a PlanRunProgressAdvancer")
        self._progress_update_composer = progress_update_composer
        self._progress_advancer = (
            PlanRunProgressAdvancer()
            if progress_advancer is None
            else progress_advancer
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
    ) -> PlanStepExecutionProgressAdvancementPostRecordingCompositionResult:
        """Delegate once, optionally advance the exact Step C update, then stop."""

        # Preserve WP053's deferred validation on unreachable input branches.
        upstream = self._progress_update_composer.compose(
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
        self._validate_upstream(
            plan,
            run,
            step_id,
            post_recording_budget,
            post_recording_created_at,
            post_recording_execution_input,
            upstream,
        )
        update = upstream.post_recording_execution_progress_update
        if update is None:
            return self._result(upstream, None)

        recording = upstream.post_recording_execution_recording_result
        if recording is None:  # guarded by upstream validation
            raise PlanStepExecutionProgressAdvancementPostRecordingCompositionInvariantError(
                "Step C update requires its exact recording"
            )
        source_run = recording.recorded_run
        advancement = self._progress_advancer.advance(plan, source_run, update)
        validate_advancement(plan.plan_id, source_run, update, advancement)
        try:
            validate_control_decision_current(
                plan, advancement.updated_run, advancement.control_decision
            )
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise PlanStepExecutionProgressAdvancementPostRecordingCompositionInvariantError(
                "WP023 returned a noncurrent control decision"
            ) from exc
        return self._result(upstream, advancement)

    @staticmethod
    def _validate_upstream(
        plan: Plan,
        source_run: PlanRun,
        processed_step_id: str,
        post_recording_budget: ContextBudget,
        post_recording_created_at: datetime,
        post_recording_execution_input: ExecutionInput | None,
        result: PlanStepExecutionProgressUpdatePostRecordingCompositionResult,
    ) -> None:
        invariant = (
            PlanStepExecutionProgressAdvancementPostRecordingCompositionInvariantError
        )
        if not isinstance(
            result, PlanStepExecutionProgressUpdatePostRecordingCompositionResult
        ):
            raise invariant("WP053 must return its canonical composition result")
        try:
            PlanStepExecutionProgressUpdatePostRecordingComposer._validate_upstream(
                plan,
                source_run,
                processed_step_id,
                post_recording_budget,
                post_recording_created_at,
                post_recording_execution_input,
                result,
            )
            PlanStepExecutionProgressUpdatePostRecordingCompositionResult.__post_init__(
                result
            )
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise invariant("WP053 returned contradictory cumulative lineage") from exc

    @staticmethod
    def _result(
        upstream: PlanStepExecutionProgressUpdatePostRecordingCompositionResult,
        advancement: PlanRunProgressAdvanceResult | None,
    ) -> PlanStepExecutionProgressAdvancementPostRecordingCompositionResult:
        return PlanStepExecutionProgressAdvancementPostRecordingCompositionResult(
            assessment=upstream.assessment,
            transition_decision=upstream.transition_decision,
            progress_update=upstream.progress_update,
            advancement_result=upstream.advancement_result,
            handling_preparation=upstream.handling_preparation,
            work_subject=upstream.work_subject,
            context_snapshot=upstream.context_snapshot,
            orchestration_decision=upstream.orchestration_decision,
            execution_request=upstream.execution_request,
            execution_binding=upstream.execution_binding,
            execution_start_result=upstream.execution_start_result,
            execution_recording_result=upstream.execution_recording_result,
            post_recording_assessment=upstream.post_recording_assessment,
            post_recording_transition_decision=upstream.post_recording_transition_decision,
            post_recording_progress_update=upstream.post_recording_progress_update,
            post_recording_advancement_result=upstream.post_recording_advancement_result,
            post_recording_handling_preparation=upstream.post_recording_handling_preparation,
            post_recording_work_subject=upstream.post_recording_work_subject,
            post_recording_context_snapshot=upstream.post_recording_context_snapshot,
            post_recording_orchestration_decision=upstream.post_recording_orchestration_decision,
            post_recording_execution_request=upstream.post_recording_execution_request,
            post_recording_execution_binding=upstream.post_recording_execution_binding,
            post_recording_execution_start_result=upstream.post_recording_execution_start_result,
            post_recording_execution_recording_result=upstream.post_recording_execution_recording_result,
            post_recording_execution_assessment=upstream.post_recording_execution_assessment,
            post_recording_execution_transition_decision=upstream.post_recording_execution_transition_decision,
            post_recording_execution_progress_update=upstream.post_recording_execution_progress_update,
            post_recording_execution_advancement_result=advancement,
        )
