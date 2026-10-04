"""Immutable output of one bounded post-recording advancement composition."""

from dataclasses import dataclass

from iris.plan_control import ControlDecision
from iris.plan_run_advancement import PlanRunProgressAdvanceResult
from iris.plan_runs import PlanRun, StepProgress, StepProgressUpdate
from iris.plan_step_execution_progress_advancement_composition.errors import (
    PlanStepExecutionProgressAdvancementCompositionInvariantError,
)
from iris.plan_step_execution_progress_update_composition import (
    PlanStepExecutionProgressUpdateCompositionResult,
)


@dataclass(frozen=True, slots=True)
class PlanStepExecutionProgressAdvancementCompositionResult(
    PlanStepExecutionProgressUpdateCompositionResult
):
    """Preserve WP041 artifacts and append the optional exact WP023 result."""

    post_recording_advancement_result: PlanRunProgressAdvanceResult | None

    def __post_init__(self) -> None:
        PlanStepExecutionProgressUpdateCompositionResult.__post_init__(self)
        advancement = self.post_recording_advancement_result
        if advancement is not None and not isinstance(
            advancement, PlanRunProgressAdvanceResult
        ):
            raise TypeError(
                "post_recording_advancement_result must be a "
                "PlanRunProgressAdvanceResult or None"
            )
        update = self.post_recording_progress_update
        if (update is None) != (advancement is None):
            raise PlanStepExecutionProgressAdvancementCompositionInvariantError(
                "post-recording update and advancement must either both exist or "
                "both be absent"
            )
        if update is not None and advancement is not None:
            self._validate_advancement(update, advancement)

    def _validate_advancement(
        self,
        update: StepProgressUpdate,
        advancement: PlanRunProgressAdvanceResult,
    ) -> None:
        recording = self.execution_recording_result
        if recording is None:
            raise PlanStepExecutionProgressAdvancementCompositionInvariantError(
                "post-recording advancement requires its exact recording"
            )
        source_run = recording.recorded_run
        updated_run = advancement.updated_run
        control = advancement.control_decision
        if not isinstance(updated_run, PlanRun) or not isinstance(
            control, ControlDecision
        ):
            raise PlanStepExecutionProgressAdvancementCompositionInvariantError(
                "post-recording advancement contains noncanonical artifacts"
            )
        if (
            advancement.source_update_id != update.update_id
            or advancement.source_revision != update.expected_revision
            or advancement.source_revision != source_run.revision
            or updated_run.plan_id != source_run.plan_id
            or updated_run.run_id != source_run.run_id
            or updated_run.goal_id != source_run.goal_id
            or updated_run.revision != source_run.revision + 1
            or updated_run.created_at != source_run.created_at
            or updated_run.updated_at != update.updated_at
            or control.plan_id != updated_run.plan_id
            or control.run_id != updated_run.run_id
            or control.observed_revision != updated_run.revision
        ):
            raise PlanStepExecutionProgressAdvancementCompositionInvariantError(
                "post-recording advancement contradicts the exact WP041 lineage"
            )
        self._validate_successor_state(source_run, update, updated_run)

    @staticmethod
    def _validate_successor_state(
        source_run: PlanRun,
        update: StepProgressUpdate,
        updated_run: PlanRun,
    ) -> None:
        invariant = PlanStepExecutionProgressAdvancementCompositionInvariantError
        if (
            updated_run.observations != source_run.observations
            or updated_run.blockers != source_run.blockers
        ):
            raise invariant(
                "post-recording advancement changed observations or blockers"
            )
        source = {item.step_id: item for item in source_run.step_progress}
        successor = {item.step_id: item for item in updated_run.step_progress}
        if source.keys() != successor.keys():
            raise invariant(
                "post-recording advancement changed the StepProgress identity set"
            )
        target = successor.get(update.step_id)
        if target is None or not isinstance(target, StepProgress):
            raise invariant("successor Run is missing the updated StepProgress")
        if (
            target.state is not update.new_state
            or target.changed_at != update.updated_at
            or target.evidence_ids != update.evidence_ids
        ):
            raise invariant("successor StepProgress does not reflect the exact update")
        if any(
            successor[step_id] != progress
            for step_id, progress in source.items()
            if step_id != update.step_id
        ):
            raise invariant("advancement changed an unrelated StepProgress")

    def to_data(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible representation."""

        data = PlanStepExecutionProgressUpdateCompositionResult.to_data(self)
        data["post_recording_advancement_result"] = (
            None
            if self.post_recording_advancement_result is None
            else self.post_recording_advancement_result.to_data()
        )
        return data
