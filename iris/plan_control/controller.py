"""One-shot deterministic control over canonical PlanRun projections."""

from __future__ import annotations

from iris.plan_control.errors import (
    NonCandidateSelectedStepError,
    PlanControlInvariantError,
    PlanIdentityMismatchError,
    PolicyContractViolationError,
    RunIdentityMismatchError,
    StaleControlDecisionError,
    UnknownSelectedStepError,
)
from iris.plan_control.models import (
    ControlDecision,
    ControlDecisionKind,
    ControlProvenance,
    ControlReason,
    StepSelectionRequest,
    StepSelectionResult,
    StepSelectionResultKind,
    _identifier,
)
from iris.plan_control.policies import StepSelectionPolicy
from iris.plan_runs import (
    PlanRun,
    PlanRunCondition,
    StepAvailability,
    derive_availability,
    derive_run_condition,
    validate_plan_run,
)
from iris.planning import Plan


class PlanRunController:
    """Produce one ControlDecision and stop without mutating or acting."""

    def __init__(
        self,
        *,
        controller_id: str = "plan_run_controller",
        controller_version: str | None = "1",
        selection_policy: StepSelectionPolicy | None = None,
    ) -> None:
        _identifier(controller_id, "controller_id")
        if controller_version is not None:
            _identifier(controller_version, "controller_version")
        self._controller_id = controller_id
        self._controller_version = controller_version
        self._selection_policy = selection_policy

    def decide(self, plan: Plan, run: PlanRun) -> ControlDecision:
        """Observe one Run revision, produce one decision, and stop."""

        validate_plan_run(plan, run)
        condition = derive_run_condition(plan, run).condition
        availability = derive_availability(plan, run)
        ready_ids = tuple(
            item.step_id
            for item in availability
            if item.availability is StepAvailability.READY
        )
        active_ids = tuple(
            item.step_id
            for item in availability
            if item.availability is StepAvailability.ACTIVE
        )

        if condition is PlanRunCondition.STRUCTURALLY_COMPLETE:
            return self._decision(
                plan,
                run,
                ControlDecisionKind.RUN_STRUCTURALLY_COMPLETE,
                ControlReason.RUN_STRUCTURALLY_COMPLETE,
            )
        if active_ids:
            return self._decision(
                plan,
                run,
                ControlDecisionKind.ACTIVE_WORK_PENDING,
                ControlReason.ACTIVE_STEP_EXISTS,
                candidate_step_ids=ready_ids,
                active_step_ids=active_ids,
            )
        if condition is PlanRunCondition.CANNOT_ADVANCE:
            return self._decision(
                plan,
                run,
                ControlDecisionKind.RUN_CANNOT_ADVANCE,
                ControlReason.RUN_CANNOT_ADVANCE,
            )
        if len(ready_ids) == 1:
            return self._decision(
                plan,
                run,
                ControlDecisionKind.STEP_SELECTED,
                ControlReason.ONLY_READY_STEP,
                candidate_step_ids=ready_ids,
                selected_step_id=ready_ids[0],
            )
        if len(ready_ids) > 1:
            return self._resolve_multiple(plan, run, ready_ids)
        raise PlanControlInvariantError(
            "an OPEN PlanRun without ACTIVE or READY steps is inconsistent"
        )

    def _resolve_multiple(
        self, plan: Plan, run: PlanRun, ready_ids: tuple[str, ...]
    ) -> ControlDecision:
        policy = self._selection_policy
        if policy is None:
            return self._decision(
                plan,
                run,
                ControlDecisionKind.SELECTION_UNRESOLVED,
                ControlReason.MULTIPLE_READY_UNRESOLVED,
                candidate_step_ids=ready_ids,
            )
        try:
            policy_id = policy.policy_id
            policy_version = policy.policy_version
        except (AttributeError, TypeError, ValueError) as error:
            raise PolicyContractViolationError(
                "selection policy provenance is invalid"
            ) from error
        try:
            provenance = ControlProvenance(
                self._controller_id,
                self._controller_version,
                policy_id,
                policy_version,
            )
        except (TypeError, ValueError) as error:
            raise PolicyContractViolationError(
                "selection policy provenance is invalid"
            ) from error
        request = StepSelectionRequest(
            plan.plan_id,
            run.run_id,
            run.revision,
            ready_ids,
        )
        result = policy.select(request)
        if not isinstance(result, StepSelectionResult):
            raise PolicyContractViolationError(
                "selection policy must return StepSelectionResult"
            )
        if result.kind is StepSelectionResultKind.UNRESOLVED:
            return ControlDecision(
                plan.plan_id,
                run.run_id,
                run.revision,
                ControlDecisionKind.SELECTION_UNRESOLVED,
                ControlReason.MULTIPLE_READY_UNRESOLVED,
                provenance,
                ready_ids,
            )
        selected = result.selected_step_id
        if selected is None:  # protected by the model; defends foreign subclasses
            raise PolicyContractViolationError(
                "SELECTED policy result requires selected_step_id"
            )
        known_ids = {step.step_id for step in plan.steps}
        if selected not in known_ids:
            raise UnknownSelectedStepError(
                f"selection policy chose unknown step {selected}"
            )
        if selected not in ready_ids:
            raise NonCandidateSelectedStepError(
                f"selection policy chose non-candidate step {selected}"
            )
        return ControlDecision(
            plan.plan_id,
            run.run_id,
            run.revision,
            ControlDecisionKind.STEP_SELECTED,
            ControlReason.POLICY_SELECTED,
            provenance,
            ready_ids,
            selected,
        )

    def _decision(
        self,
        plan: Plan,
        run: PlanRun,
        kind: ControlDecisionKind,
        reason: ControlReason,
        *,
        candidate_step_ids: tuple[str, ...] = (),
        selected_step_id: str | None = None,
        active_step_ids: tuple[str, ...] = (),
    ) -> ControlDecision:
        return ControlDecision(
            plan.plan_id,
            run.run_id,
            run.revision,
            kind,
            reason,
            ControlProvenance(self._controller_id, self._controller_version),
            candidate_step_ids,
            selected_step_id,
            active_step_ids,
        )


def validate_control_decision_current(
    plan: Plan, run: PlanRun, decision: ControlDecision
) -> None:
    """Reject a decision whose Plan, Run, or observed revision is no longer current."""

    validate_plan_run(plan, run)
    if not isinstance(decision, ControlDecision):
        raise TypeError("decision must be a ControlDecision")
    if decision.plan_id != plan.plan_id:
        raise PlanIdentityMismatchError("ControlDecision references a different Plan")
    if decision.run_id != run.run_id:
        raise RunIdentityMismatchError("ControlDecision references a different PlanRun")
    if decision.observed_revision != run.revision:
        raise StaleControlDecisionError(
            "ControlDecision observed revision "
            f"{decision.observed_revision}; current revision is {run.revision}"
        )
