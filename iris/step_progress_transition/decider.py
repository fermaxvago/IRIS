"""Validated one-shot StepProgress transition decisions and currentness checks."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from iris.outcome_assessment import StepOutcomeAssessment, StepOutcomeStatus
from iris.plan_runs import PlanRun, StepProgress, StepProgressState, validate_plan_run
from iris.planning import Plan, PlanStep
from iris.step_progress_transition.contracts import StepProgressTransitionPolicy
from iris.step_progress_transition.errors import (
    StaleStepProgressTransitionDecisionError,
    TransitionAssessmentEvidenceError,
    TransitionAssessmentIdentityError,
    TransitionDecisionGenerationError,
    TransitionDecisionIdentityError,
    TransitionPolicyContractViolationError,
    TransitionPolicyExecutionError,
)
from iris.step_progress_transition.models import (
    StepProgressTransitionAction,
    StepProgressTransitionDecision,
    StepProgressTransitionPolicyResult,
    StepProgressTransitionProvenance,
    StepProgressTransitionReason,
    StepProgressTransitionRequest,
    _identifier,
    _optional_identifier,
    _utc_time,
)
from iris.step_progress_transition.policies import (
    ConservativeStepProgressTransitionPolicy,
)


class StepProgressTransitionDecider:
    """Validate assessment applicability, make one decision, and stop."""

    DEFAULT_DECIDER_ID = "step_progress_transition_decider"
    DEFAULT_DECIDER_VERSION = "1"

    def __init__(
        self,
        *,
        transition_policy: StepProgressTransitionPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
        decision_id_factory: Callable[[], str] | None = None,
        decider_id: str = DEFAULT_DECIDER_ID,
        decider_version: str | None = DEFAULT_DECIDER_VERSION,
    ) -> None:
        _identifier(decider_id, "decider_id")
        _optional_identifier(decider_version, "decider_version")
        self._policy = (
            ConservativeStepProgressTransitionPolicy()
            if transition_policy is None
            else transition_policy
        )
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)
        self._decision_id_factory = (
            decision_id_factory
            if decision_id_factory is not None
            else lambda: uuid4().hex
        )
        self._decider_id = decider_id
        self._decider_version = decider_version

    def decide(
        self,
        plan: Plan,
        run: PlanRun,
        step: PlanStep,
        assessment: StepOutcomeAssessment,
    ) -> StepProgressTransitionDecision:
        """Return one current transition decision without creating an update."""

        self._validate_types(plan, run, step, assessment)
        validate_plan_run(plan, run)
        self._validate_step(plan, step)
        self._validate_assessment_identity(plan, run, step, assessment)
        self._validate_assessment_evidence(run, step, assessment)

        progress = self._progress(run, step.step_id)
        current_evidence_ids = {
            observation.observation_id
            for observation in run.observations
            if observation.step_id == step.step_id
        }
        if set(assessment.evidence_ids) != current_evidence_ids:
            return self._decision(
                plan,
                run,
                progress,
                assessment,
                StepProgressTransitionPolicyResult(
                    StepProgressTransitionAction.NO_TRANSITION,
                    None,
                    StepProgressTransitionReason.INCOMPLETE_CURRENT_EVIDENCE_BASIS,
                ),
                policy_provenance=None,
            )

        if (
            progress.state is StepProgressState.ACTIVE
            and assessment.assessed_at < progress.changed_at
        ):
            return self._decision(
                plan,
                run,
                progress,
                assessment,
                StepProgressTransitionPolicyResult(
                    StepProgressTransitionAction.NO_TRANSITION,
                    None,
                    StepProgressTransitionReason.ASSESSMENT_PREDATES_CURRENT_STEP_STATE,
                ),
                policy_provenance=None,
            )

        request = StepProgressTransitionRequest(
            plan_id=plan.plan_id,
            run_id=run.run_id,
            observed_revision=run.revision,
            step_id=step.step_id,
            assessment_id=assessment.assessment_id,
            source_state=progress.state,
            assessment_status=assessment.status,
        )
        policy_provenance = self._policy_provenance()
        result = self._invoke_policy(request)
        self._validate_policy_result(request, result)
        return self._decision(
            plan,
            run,
            progress,
            assessment,
            result,
            policy_provenance=policy_provenance,
        )

    @staticmethod
    def _validate_types(
        plan: Plan,
        run: PlanRun,
        step: PlanStep,
        assessment: StepOutcomeAssessment,
    ) -> None:
        if not isinstance(plan, Plan):
            raise TypeError("plan must be a Plan")
        if not isinstance(run, PlanRun):
            raise TypeError("run must be a PlanRun")
        if not isinstance(step, PlanStep):
            raise TypeError("step must be a PlanStep")
        if not isinstance(assessment, StepOutcomeAssessment):
            raise TypeError("assessment must be a StepOutcomeAssessment")

    @staticmethod
    def _validate_step(plan: Plan, step: PlanStep) -> None:
        canonical = next(
            (item for item in plan.steps if item.step_id == step.step_id), None
        )
        if canonical is None:
            raise TransitionAssessmentIdentityError(
                f"step {step.step_id} does not belong to Plan {plan.plan_id}"
            )
        if canonical != step:
            raise TransitionAssessmentIdentityError(
                "step definition differs from the canonical PlanStep"
            )

    @staticmethod
    def _validate_assessment_identity(
        plan: Plan,
        run: PlanRun,
        step: PlanStep,
        assessment: StepOutcomeAssessment,
    ) -> None:
        if assessment.plan_id != plan.plan_id:
            raise TransitionAssessmentIdentityError(
                "assessment references a different Plan"
            )
        if assessment.run_id != run.run_id:
            raise TransitionAssessmentIdentityError(
                "assessment references a different PlanRun"
            )
        if assessment.step_id != step.step_id:
            raise TransitionAssessmentIdentityError(
                "assessment references a different PlanStep"
            )
        if assessment.run_revision > run.revision:
            raise TransitionAssessmentIdentityError(
                "assessment references a future PlanRun revision"
            )
        if assessment.assessed_at < run.created_at:
            raise TransitionAssessmentIdentityError(
                "assessment cannot predate PlanRun creation"
            )

    @staticmethod
    def _validate_assessment_evidence(
        run: PlanRun,
        step: PlanStep,
        assessment: StepOutcomeAssessment,
    ) -> None:
        canonical = {item.observation_id: item for item in run.observations}
        for evidence_id in assessment.evidence_ids:
            observation = canonical.get(evidence_id)
            if observation is None:
                raise TransitionAssessmentEvidenceError(
                    f"assessment evidence {evidence_id} is absent from current PlanRun"
                )
            if observation.step_id != step.step_id:
                raise TransitionAssessmentEvidenceError(
                    f"assessment evidence {evidence_id} is not scoped to "
                    f"step {step.step_id}"
                )

    @staticmethod
    def _progress(run: PlanRun, step_id: str) -> StepProgress:
        progress = next(
            (item for item in run.step_progress if item.step_id == step_id), None
        )
        if progress is None:  # validate_plan_run guards this; defensive boundary
            raise TransitionAssessmentIdentityError(
                f"current PlanRun has no progress for step {step_id}"
            )
        return progress

    def _policy_provenance(self) -> tuple[str, str | None]:
        try:
            policy_id = self._policy.policy_id
            policy_version = self._policy.policy_version
            provenance = StepProgressTransitionProvenance(
                self._decider_id,
                self._decider_version,
                policy_id,
                policy_version,
            )
        except Exception as exc:
            raise TransitionPolicyContractViolationError(
                "transition policy provenance is invalid"
            ) from exc
        if provenance.policy_id is None:  # protected by the protocol; defensive
            raise TransitionPolicyContractViolationError(
                "transition policy requires a nonblank policy_id"
            )
        return provenance.policy_id, provenance.policy_version

    def _invoke_policy(
        self, request: StepProgressTransitionRequest
    ) -> StepProgressTransitionPolicyResult:
        try:
            result = self._policy.decide(request)
        except TransitionPolicyContractViolationError:
            raise
        except Exception as exc:
            raise TransitionPolicyExecutionError(
                "transition policy execution failed"
            ) from exc
        if not isinstance(result, StepProgressTransitionPolicyResult):
            raise TransitionPolicyContractViolationError(
                "transition policy must return StepProgressTransitionPolicyResult"
            )
        return result

    @staticmethod
    def _validate_policy_result(
        request: StepProgressTransitionRequest,
        result: StepProgressTransitionPolicyResult,
    ) -> None:
        expected = _conservative_contract_result(request)
        if result != expected:
            raise TransitionPolicyContractViolationError(
                "transition policy returned a result incompatible with the request"
            )

    def _decision(
        self,
        plan: Plan,
        run: PlanRun,
        progress: StepProgress,
        assessment: StepOutcomeAssessment,
        result: StepProgressTransitionPolicyResult,
        *,
        policy_provenance: tuple[str, str | None] | None,
    ) -> StepProgressTransitionDecision:
        decided_at = self._read_clock()
        if decided_at < run.updated_at:
            raise TransitionDecisionIdentityError(
                "decision cannot predate current PlanRun updated_at"
            )
        if decided_at < assessment.assessed_at:
            raise TransitionDecisionIdentityError(
                "decision cannot predate its assessment"
            )
        decision_id = self._new_decision_id()
        policy_id, policy_version = (
            (None, None) if policy_provenance is None else policy_provenance
        )
        return StepProgressTransitionDecision(
            decision_id=decision_id,
            plan_id=plan.plan_id,
            run_id=run.run_id,
            observed_revision=run.revision,
            step_id=progress.step_id,
            assessment_id=assessment.assessment_id,
            source_state=progress.state,
            action=result.action,
            target_state=result.target_state,
            reason=result.reason,
            provenance=StepProgressTransitionProvenance(
                self._decider_id,
                self._decider_version,
                policy_id,
                policy_version,
            ),
            decided_at=decided_at,
        )

    def _read_clock(self) -> datetime:
        try:
            instant = self._clock()
            return _utc_time(instant, "decided_at")
        except Exception as exc:
            raise TransitionDecisionGenerationError(
                "transition decision clock failed"
            ) from exc

    def _new_decision_id(self) -> str:
        try:
            decision_id = self._decision_id_factory()
        except Exception as exc:
            raise TransitionDecisionGenerationError(
                "transition decision ID factory failed"
            ) from exc
        try:
            return _identifier(decision_id, "decision_id")
        except (TypeError, ValueError) as exc:
            raise TransitionDecisionGenerationError(
                "transition decision ID factory returned an invalid identifier"
            ) from exc


def _conservative_contract_result(
    request: StepProgressTransitionRequest,
) -> StepProgressTransitionPolicyResult:
    state_reason = {
        StepProgressState.NOT_STARTED: StepProgressTransitionReason.STEP_NOT_STARTED,
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


def validate_step_progress_transition_decision_current(
    plan: Plan,
    run: PlanRun,
    decision: StepProgressTransitionDecision,
) -> None:
    """Validate strict decision currentness without assessment or mutation."""

    if not isinstance(plan, Plan):
        raise TypeError("plan must be a Plan")
    if not isinstance(run, PlanRun):
        raise TypeError("run must be a PlanRun")
    if not isinstance(decision, StepProgressTransitionDecision):
        raise TypeError("decision must be a StepProgressTransitionDecision")
    validate_plan_run(plan, run)
    if decision.plan_id != plan.plan_id:
        raise TransitionDecisionIdentityError(
            "transition decision references a different Plan"
        )
    if decision.run_id != run.run_id:
        raise TransitionDecisionIdentityError(
            "transition decision references a different PlanRun"
        )
    if decision.observed_revision != run.revision:
        raise StaleStepProgressTransitionDecisionError(
            "transition decision observed revision "
            f"{decision.observed_revision}; current revision is {run.revision}"
        )
    if all(step.step_id != decision.step_id for step in plan.steps):
        raise TransitionDecisionIdentityError(
            f"transition decision references unknown step {decision.step_id}"
        )
    progress = next(
        item for item in run.step_progress if item.step_id == decision.step_id
    )
    if progress.state is not decision.source_state:
        raise TransitionDecisionIdentityError(
            "transition decision source_state differs from current StepProgress"
        )
