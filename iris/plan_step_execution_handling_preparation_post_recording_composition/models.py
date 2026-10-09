"""Immutable WP054 lineage plus optional successor handling preparation."""

from copy import copy
from dataclasses import dataclass, fields, is_dataclass

from iris.orchestrator import HandlingNeed
from iris.plan_control import ControlDecisionKind
from iris.plan_handling import (
    StepHandlingPreparationProvenance,
    StepHandlingPreparationResult,
)
from iris.plan_step_execution_handling_preparation_post_recording_composition.errors import (
    PlanStepExecutionHandlingPreparationPostRecordingCompositionInvariantError,
)
from iris.plan_step_execution_progress_advancement_post_recording_composition import (
    PlanStepExecutionProgressAdvancementPostRecordingCompositionResult,
)


def _unchanged_by_validation(original: object, checked: object) -> bool:
    if not is_dataclass(original):
        return False
    return all(
        type(getattr(original, item.name)) is type(getattr(checked, item.name))
        and getattr(original, item.name) == getattr(checked, item.name)
        for item in fields(original)
    )


def validate_preparation_artifact(
    preparation: StepHandlingPreparationResult,
) -> None:
    """Recheck the WP014 artifact without normalizing a forged return."""

    invariant = (
        PlanStepExecutionHandlingPreparationPostRecordingCompositionInvariantError
    )
    if not isinstance(preparation, StepHandlingPreparationResult):
        raise invariant("WP014 must return a StepHandlingPreparationResult")
    try:
        checked = copy(preparation)
        StepHandlingPreparationResult.__post_init__(checked)
        if not _unchanged_by_validation(preparation, checked):
            raise ValueError("preparation requires normalization")
        provenance = preparation.provenance
        checked_provenance = copy(provenance)
        StepHandlingPreparationProvenance.__post_init__(checked_provenance)
        if not _unchanged_by_validation(provenance, checked_provenance):
            raise ValueError("preparation provenance requires normalization")
        need = preparation.handling_need
        if need is not None:
            if not isinstance(need, HandlingNeed):
                raise TypeError("handling_need must be a HandlingNeed")
            checked_need = copy(need)
            HandlingNeed.__post_init__(checked_need)
            if not _unchanged_by_validation(need, checked_need):
                raise ValueError("HandlingNeed requires normalization")
    except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
        raise invariant("WP014 returned noncanonical preparation artifacts") from exc


@dataclass(frozen=True, slots=True)
class PlanStepExecutionHandlingPreparationPostRecordingCompositionResult(
    PlanStepExecutionProgressAdvancementPostRecordingCompositionResult
):
    """Preserve WP054 and append optional exact WP014 preparation."""

    post_recording_execution_handling_preparation: StepHandlingPreparationResult | None

    def __post_init__(self) -> None:
        PlanStepExecutionProgressAdvancementPostRecordingCompositionResult.__post_init__(
            self
        )
        invariant = (
            PlanStepExecutionHandlingPreparationPostRecordingCompositionInvariantError
        )
        advancement = self.post_recording_execution_advancement_result
        preparation = self.post_recording_execution_handling_preparation
        selected = (
            advancement is not None
            and advancement.control_decision.kind is ControlDecisionKind.STEP_SELECTED
        )
        if selected != (preparation is not None):
            raise invariant(
                "successor preparation must exist exactly for STEP_SELECTED control"
            )
        if preparation is None:
            return
        validate_preparation_artifact(preparation)
        if (
            preparation is self.handling_preparation
            or preparation is self.post_recording_handling_preparation
        ):
            raise invariant(
                "successor preparation must be distinct from earlier stages"
            )
        assert advancement is not None
        successor = advancement.updated_run
        control = advancement.control_decision
        if (
            preparation.plan_id != successor.plan_id
            or preparation.plan_id != control.plan_id
            or preparation.run_id != successor.run_id
            or preparation.run_id != control.run_id
            or preparation.observed_revision != successor.revision
            or preparation.observed_revision != control.observed_revision
            or preparation.step_id != control.selected_step_id
        ):
            raise invariant(
                "WP014 preparation contradicts the exact successor selection"
            )

    def to_data(self) -> dict[str, object]:
        """Append canonical WP014 data to inherited WP054 serialization."""

        data = (
            PlanStepExecutionProgressAdvancementPostRecordingCompositionResult.to_data(
                self
            )
        )
        data["post_recording_execution_handling_preparation"] = (
            None
            if self.post_recording_execution_handling_preparation is None
            else self.post_recording_execution_handling_preparation.to_data()
        )
        return data
