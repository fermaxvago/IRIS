"""Immutable models for conservative StepProgress transition decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from iris.outcome_assessment import StepOutcomeStatus
from iris.plan_runs import StepProgressState
from iris.step_progress_transition.errors import (
    TransitionDecisionIdentityError,
    TransitionPolicyContractViolationError,
)


def _identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a nonblank identifier")
    return value


def _optional_identifier(value: str | None, name: str) -> str | None:
    if value is not None:
        _identifier(value, name)
    return value


def _revision(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value


def _utc_time(value: datetime, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be a timezone-aware datetime")
    return value.astimezone(UTC)


class StepProgressTransitionAction(StrEnum):
    """Whether the policy requests the one supported progress transition."""

    TRANSITION = "transition"
    NO_TRANSITION = "no_transition"


class StepProgressTransitionReason(StrEnum):
    """Auditable reason for a transition or deliberate abstention."""

    OUTCOME_SATISFIED = "outcome_satisfied"
    OUTCOME_NOT_SATISFIED = "outcome_not_satisfied"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    INDETERMINATE_OUTCOME = "indeterminate_outcome"
    INCOMPLETE_CURRENT_EVIDENCE_BASIS = "incomplete_current_evidence_basis"
    ASSESSMENT_PREDATES_CURRENT_STEP_STATE = "assessment_predates_current_step_state"
    STEP_NOT_STARTED = "step_not_started"
    STEP_ALREADY_SUCCEEDED = "step_already_succeeded"
    STEP_ALREADY_FAILED = "step_already_failed"


@dataclass(frozen=True, slots=True)
class StepProgressTransitionProvenance:
    """Decider identity and the policy actually invoked, if any."""

    decider_id: str
    decider_version: str | None = None
    policy_id: str | None = None
    policy_version: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.decider_id, "decider_id")
        _optional_identifier(self.decider_version, "decider_version")
        _optional_identifier(self.policy_id, "policy_id")
        _optional_identifier(self.policy_version, "policy_version")
        if self.policy_id is None and self.policy_version is not None:
            raise ValueError("policy_version requires policy_id")

    def to_data(self) -> dict[str, object]:
        return {
            "decider_id": self.decider_id,
            "decider_version": self.decider_version,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
        }


@dataclass(frozen=True, slots=True)
class StepProgressTransitionRequest:
    """Validated, applicability-cleared input for a transition policy."""

    plan_id: str
    run_id: str
    observed_revision: int
    step_id: str
    assessment_id: str
    source_state: StepProgressState
    assessment_status: StepOutcomeStatus

    def __post_init__(self) -> None:
        for value, name in (
            (self.plan_id, "request plan_id"),
            (self.run_id, "request run_id"),
            (self.step_id, "request step_id"),
            (self.assessment_id, "request assessment_id"),
        ):
            _identifier(value, name)
        _revision(self.observed_revision, "request observed_revision")
        if not isinstance(self.source_state, StepProgressState):
            raise TypeError("source_state must be a StepProgressState")
        if not isinstance(self.assessment_status, StepOutcomeStatus):
            raise TypeError("assessment_status must be a StepOutcomeStatus")

    def to_data(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "run_id": self.run_id,
            "observed_revision": self.observed_revision,
            "step_id": self.step_id,
            "assessment_id": self.assessment_id,
            "source_state": self.source_state.value,
            "assessment_status": self.assessment_status.value,
        }


@dataclass(frozen=True, slots=True)
class StepProgressTransitionPolicyResult:
    """A policy outcome without canonical identity, time, or provenance."""

    action: StepProgressTransitionAction
    target_state: StepProgressState | None
    reason: StepProgressTransitionReason

    def __post_init__(self) -> None:
        if not isinstance(self.action, StepProgressTransitionAction):
            raise TypeError("action must be a StepProgressTransitionAction")
        if self.target_state is not None and not isinstance(
            self.target_state, StepProgressState
        ):
            raise TypeError("target_state must be a StepProgressState or None")
        if not isinstance(self.reason, StepProgressTransitionReason):
            raise TypeError("reason must be a StepProgressTransitionReason")
        if self.action is StepProgressTransitionAction.TRANSITION:
            if self.target_state is not StepProgressState.SUCCEEDED:
                raise TransitionPolicyContractViolationError(
                    "TRANSITION requires target_state SUCCEEDED"
                )
            if self.reason is not StepProgressTransitionReason.OUTCOME_SATISFIED:
                raise TransitionPolicyContractViolationError(
                    "TRANSITION requires OUTCOME_SATISFIED reason"
                )
        else:
            if self.target_state is not None:
                raise TransitionPolicyContractViolationError(
                    "NO_TRANSITION requires target_state None"
                )
            if self.reason is StepProgressTransitionReason.OUTCOME_SATISFIED:
                raise TransitionPolicyContractViolationError(
                    "OUTCOME_SATISFIED requires TRANSITION"
                )

    def to_data(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "target_state": (
                None if self.target_state is None else self.target_state.value
            ),
            "reason": self.reason.value,
        }


@dataclass(frozen=True, slots=True)
class StepProgressTransitionDecision:
    """One inert operational decision over one exact PlanRun revision."""

    decision_id: str
    plan_id: str
    run_id: str
    observed_revision: int
    step_id: str
    assessment_id: str
    source_state: StepProgressState
    action: StepProgressTransitionAction
    target_state: StepProgressState | None
    reason: StepProgressTransitionReason
    provenance: StepProgressTransitionProvenance
    decided_at: datetime

    def __post_init__(self) -> None:
        for value, name in (
            (self.decision_id, "decision_id"),
            (self.plan_id, "decision plan_id"),
            (self.run_id, "decision run_id"),
            (self.step_id, "decision step_id"),
            (self.assessment_id, "decision assessment_id"),
        ):
            _identifier(value, name)
        if self.decision_id in {
            self.plan_id,
            self.run_id,
            self.step_id,
            self.assessment_id,
        }:
            raise TransitionDecisionIdentityError(
                "decision_id must be independent from Plan, Run, step, and assessment"
            )
        _revision(self.observed_revision, "decision observed_revision")
        if not isinstance(self.source_state, StepProgressState):
            raise TypeError("source_state must be a StepProgressState")
        if not isinstance(self.provenance, StepProgressTransitionProvenance):
            raise TypeError("provenance must be StepProgressTransitionProvenance")
        if not isinstance(self.action, StepProgressTransitionAction):
            raise TypeError("action must be a StepProgressTransitionAction")
        if self.target_state is not None and not isinstance(
            self.target_state, StepProgressState
        ):
            raise TypeError("target_state must be a StepProgressState or None")
        if not isinstance(self.reason, StepProgressTransitionReason):
            raise TypeError("reason must be a StepProgressTransitionReason")
        if self.action is StepProgressTransitionAction.TRANSITION:
            if self.target_state is not StepProgressState.SUCCEEDED:
                raise ValueError("TRANSITION requires target_state SUCCEEDED")
            if self.reason is not StepProgressTransitionReason.OUTCOME_SATISFIED:
                raise ValueError("TRANSITION requires OUTCOME_SATISFIED reason")
        elif self.target_state is not None:
            raise ValueError("NO_TRANSITION requires target_state None")
        elif self.reason is StepProgressTransitionReason.OUTCOME_SATISFIED:
            raise ValueError("OUTCOME_SATISFIED requires TRANSITION")
        if (
            self.action is StepProgressTransitionAction.TRANSITION
            and self.source_state is not StepProgressState.ACTIVE
        ):
            raise ValueError("TRANSITION is supported only from ACTIVE")
        applicability_reasons = {
            StepProgressTransitionReason.INCOMPLETE_CURRENT_EVIDENCE_BASIS,
            StepProgressTransitionReason.ASSESSMENT_PREDATES_CURRENT_STEP_STATE,
        }
        if self.reason in applicability_reasons:
            if self.provenance.policy_id is not None:
                raise ValueError(
                    "applicability decisions cannot record policy invocation"
                )
            if (
                self.reason
                is StepProgressTransitionReason.ASSESSMENT_PREDATES_CURRENT_STEP_STATE
                and self.source_state is not StepProgressState.ACTIVE
            ):
                raise ValueError(
                    "ASSESSMENT_PREDATES_CURRENT_STEP_STATE requires ACTIVE source"
                )
        else:
            if self.provenance.policy_id is None:
                raise ValueError("policy decision requires policy provenance")
            expected_reason = {
                StepProgressState.NOT_STARTED: (
                    StepProgressTransitionReason.STEP_NOT_STARTED
                ),
                StepProgressState.SUCCEEDED: (
                    StepProgressTransitionReason.STEP_ALREADY_SUCCEEDED
                ),
                StepProgressState.FAILED: (
                    StepProgressTransitionReason.STEP_ALREADY_FAILED
                ),
            }.get(self.source_state)
            if expected_reason is not None and self.reason is not expected_reason:
                raise ValueError("decision reason is incompatible with source_state")
            if self.source_state is StepProgressState.ACTIVE and self.reason not in {
                StepProgressTransitionReason.OUTCOME_SATISFIED,
                StepProgressTransitionReason.OUTCOME_NOT_SATISFIED,
                StepProgressTransitionReason.INSUFFICIENT_EVIDENCE,
                StepProgressTransitionReason.INDETERMINATE_OUTCOME,
            }:
                raise ValueError("decision reason is incompatible with ACTIVE source")
        object.__setattr__(self, "decided_at", _utc_time(self.decided_at, "decided_at"))

    def to_data(self) -> dict[str, object]:
        return {
            "decision_id": self.decision_id,
            "plan_id": self.plan_id,
            "run_id": self.run_id,
            "observed_revision": self.observed_revision,
            "step_id": self.step_id,
            "assessment_id": self.assessment_id,
            "source_state": self.source_state.value,
            "action": self.action.value,
            "target_state": (
                None if self.target_state is None else self.target_state.value
            ),
            "reason": self.reason.value,
            "provenance": self.provenance.to_data(),
            "decided_at": self.decided_at.isoformat(),
        }
