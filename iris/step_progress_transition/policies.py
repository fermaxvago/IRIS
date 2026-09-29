"""Deterministic baseline StepProgress transition policy."""

from __future__ import annotations

from dataclasses import dataclass

from iris.outcome_assessment import StepOutcomeStatus
from iris.plan_runs import StepProgressState
from iris.step_progress_transition.models import (
    StepProgressTransitionAction,
    StepProgressTransitionPolicyResult,
    StepProgressTransitionReason,
    StepProgressTransitionRequest,
    _identifier,
    _optional_identifier,
)


@dataclass(frozen=True, slots=True)
class ConservativeStepProgressTransitionPolicy:
    """Permit only an applicable ACTIVE + SATISFIED success transition."""

    policy_id: str = "conservative_step_progress_transition"
    policy_version: str | None = "1"

    def __post_init__(self) -> None:
        _identifier(self.policy_id, "policy_id")
        _optional_identifier(self.policy_version, "policy_version")

    def decide(
        self, request: StepProgressTransitionRequest
    ) -> StepProgressTransitionPolicyResult:
        if not isinstance(request, StepProgressTransitionRequest):
            raise TypeError("request must be a StepProgressTransitionRequest")

        state_reason = {
            StepProgressState.NOT_STARTED: (
                StepProgressTransitionReason.STEP_NOT_STARTED
            ),
            StepProgressState.SUCCEEDED: (
                StepProgressTransitionReason.STEP_ALREADY_SUCCEEDED
            ),
            StepProgressState.FAILED: StepProgressTransitionReason.STEP_ALREADY_FAILED,
        }.get(request.source_state)
        if state_reason is not None:
            return StepProgressTransitionPolicyResult(
                StepProgressTransitionAction.NO_TRANSITION,
                None,
                state_reason,
            )

        if request.assessment_status is StepOutcomeStatus.SATISFIED:
            return StepProgressTransitionPolicyResult(
                StepProgressTransitionAction.TRANSITION,
                StepProgressState.SUCCEEDED,
                StepProgressTransitionReason.OUTCOME_SATISFIED,
            )
        reason = {
            StepOutcomeStatus.NOT_SATISFIED: (
                StepProgressTransitionReason.OUTCOME_NOT_SATISFIED
            ),
            StepOutcomeStatus.INSUFFICIENT_EVIDENCE: (
                StepProgressTransitionReason.INSUFFICIENT_EVIDENCE
            ),
            StepOutcomeStatus.INDETERMINATE: (
                StepProgressTransitionReason.INDETERMINATE_OUTCOME
            ),
        }[request.assessment_status]
        return StepProgressTransitionPolicyResult(
            StepProgressTransitionAction.NO_TRANSITION,
            None,
            reason,
        )
