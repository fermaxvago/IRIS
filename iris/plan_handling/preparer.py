"""Pure preparation of one selected PlanStep into an existing HandlingNeed."""

from __future__ import annotations

import hashlib
import json

from iris.intelligence.routing import IntelligenceNeed
from iris.orchestrator import HandlingKind, HandlingNeed, MemoryOperation
from iris.plan_control import (
    ControlDecision,
    ControlDecisionKind,
    validate_control_decision_current,
)
from iris.plan_handling.errors import (
    InvalidControlDecisionKindError,
    PlanHandlingInvariantError,
    PreparationPlanIdentityError,
    PreparationRunIdentityError,
    SelectedStepNotReadyError,
    SpecificationKindMismatchError,
    SpecificationStepMismatchError,
    StaleStepHandlingPreparationError,
    UnexpectedStepHandlingSpecificationError,
    UnknownSelectedPlanStepError,
)
from iris.plan_handling.models import (
    StepHandlingPreparationProvenance,
    StepHandlingPreparationReason,
    StepHandlingPreparationResult,
    StepHandlingPreparationStatus,
    StepHandlingSpecification,
)
from iris.plan_runs import (
    PlanRun,
    StepAvailability,
    derive_step_availability,
    validate_plan_run,
)
from iris.planning import Plan, PlanStep
from iris.router import RouteTarget


def _need_id(plan_id: str, run_id: str, revision: int, step_id: str) -> str:
    material = json.dumps(
        [plan_id, run_id, revision, step_id],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"plan_step_{hashlib.sha256(material).hexdigest()}"


class PlanStepHandlingPreparer:
    """Prepare one semantic HandlingNeed without orchestration or execution."""

    def __init__(
        self,
        *,
        preparer_id: str = "plan_step_handling_preparer",
        preparer_version: str | None = "1",
    ) -> None:
        self._provenance = StepHandlingPreparationProvenance(
            preparer_id,
            preparer_version,
        )

    def prepare(
        self,
        plan: Plan,
        run: PlanRun,
        decision: ControlDecision,
        specification: StepHandlingSpecification | None = None,
    ) -> StepHandlingPreparationResult:
        """Produce one immutable preparation result and stop."""

        validate_plan_run(plan, run)
        validate_control_decision_current(plan, run, decision)
        if decision.kind is not ControlDecisionKind.STEP_SELECTED:
            raise InvalidControlDecisionKindError(
                "PlanStep handling preparation requires STEP_SELECTED"
            )
        selected_id = decision.selected_step_id
        if selected_id is None:  # protected by ControlDecision; defensive boundary
            raise PlanHandlingInvariantError(
                "STEP_SELECTED decision is missing selected_step_id"
            )
        selected_step = next(
            (step for step in plan.steps if step.step_id == selected_id),
            None,
        )
        if selected_step is None:
            raise UnknownSelectedPlanStepError(
                f"selected step {selected_id} does not exist in Plan"
            )
        availability = derive_step_availability(plan, run, selected_id).availability
        if availability is not StepAvailability.READY:
            raise SelectedStepNotReadyError(
                f"selected step {selected_id} is {availability.value}, not READY"
            )
        if specification is not None and not isinstance(
            specification, StepHandlingSpecification
        ):
            raise TypeError("specification must be a StepHandlingSpecification or None")

        required = selected_step.required_handling
        if required is None:
            if specification is not None:
                raise UnexpectedStepHandlingSpecificationError(
                    "a specification cannot override unspecified PlanStep handling"
                )
            return self._result(
                plan,
                run,
                selected_id,
                StepHandlingPreparationStatus.HANDLING_UNSPECIFIED,
                StepHandlingPreparationReason.HANDLING_NOT_DECLARED,
            )
        if required is HandlingKind.CLARIFICATION:
            raise PlanHandlingInvariantError(
                "CLARIFICATION is not valid PlanStep required_handling"
            )
        if specification is not None:
            self._validate_specification(selected_step, specification)

        if required is HandlingKind.CAPABILITY:
            capability_id = (
                None if specification is None else specification.capability_id
            )
            reason = (
                StepHandlingPreparationReason.CAPABILITY_KIND_SUFFICIENT
                if specification is None
                else StepHandlingPreparationReason.SPECIFICATION_COMPLETED_HANDLING
            )
            return self._prepared(
                plan,
                run,
                selected_id,
                required,
                reason,
                capability_id=capability_id,
            )

        if specification is None:
            insufficient_reason = {
                HandlingKind.SYSTEM: (
                    StepHandlingPreparationReason.SYSTEM_ROUTE_REQUIRED
                ),
                HandlingKind.MEMORY: (
                    StepHandlingPreparationReason.MEMORY_OPERATION_REQUIRED
                ),
                HandlingKind.INTELLIGENCE: (
                    StepHandlingPreparationReason.INTELLIGENCE_NEED_REQUIRED
                ),
            }.get(required)
            if insufficient_reason is None:
                raise PlanHandlingInvariantError(
                    f"unsupported PlanStep handling kind {required.value}"
                )
            return self._result(
                plan,
                run,
                selected_id,
                StepHandlingPreparationStatus.INSUFFICIENT_DETAIL,
                insufficient_reason,
                handling_kind=required,
            )

        return self._prepared(
            plan,
            run,
            selected_id,
            required,
            StepHandlingPreparationReason.SPECIFICATION_COMPLETED_HANDLING,
            system_route=specification.system_route,
            memory_operation=specification.memory_operation,
            intelligence_need=specification.intelligence_need,
        )

    @staticmethod
    def _validate_specification(
        step: PlanStep, specification: StepHandlingSpecification
    ) -> None:
        if specification.step_id != step.step_id:
            raise SpecificationStepMismatchError(
                "StepHandlingSpecification belongs to a different PlanStep"
            )
        if specification.kind is not step.required_handling:
            raise SpecificationKindMismatchError(
                "StepHandlingSpecification kind contradicts required_handling"
            )

    def _prepared(
        self,
        plan: Plan,
        run: PlanRun,
        step_id: str,
        kind: HandlingKind,
        reason: StepHandlingPreparationReason,
        *,
        system_route: RouteTarget | None = None,
        memory_operation: MemoryOperation | None = None,
        capability_id: str | None = None,
        intelligence_need: IntelligenceNeed | None = None,
    ) -> StepHandlingPreparationResult:
        need = HandlingNeed(
            need_id=_need_id(plan.plan_id, run.run_id, run.revision, step_id),
            kind=kind,
            system_route=system_route,
            memory_operation=memory_operation,
            capability_id=capability_id,
            intelligence_need=intelligence_need,
            blockers=(),
        )
        return self._result(
            plan,
            run,
            step_id,
            StepHandlingPreparationStatus.PREPARED,
            reason,
            handling_kind=kind,
            handling_need=need,
        )

    def _result(
        self,
        plan: Plan,
        run: PlanRun,
        step_id: str,
        status: StepHandlingPreparationStatus,
        reason: StepHandlingPreparationReason,
        *,
        handling_kind: HandlingKind | None = None,
        handling_need: HandlingNeed | None = None,
    ) -> StepHandlingPreparationResult:
        return StepHandlingPreparationResult(
            plan_id=plan.plan_id,
            run_id=run.run_id,
            observed_revision=run.revision,
            step_id=step_id,
            status=status,
            reason=reason,
            provenance=self._provenance,
            handling_kind=handling_kind,
            handling_need=handling_need,
        )


def validate_step_handling_preparation_current(
    plan: Plan,
    run: PlanRun,
    result: StepHandlingPreparationResult,
) -> None:
    """Reject a result whose Plan, Run, revision, step, or readiness is stale."""

    validate_plan_run(plan, run)
    if not isinstance(result, StepHandlingPreparationResult):
        raise TypeError("result must be a StepHandlingPreparationResult")
    if result.plan_id != plan.plan_id:
        raise PreparationPlanIdentityError(
            "preparation result references a different Plan"
        )
    if result.run_id != run.run_id:
        raise PreparationRunIdentityError(
            "preparation result references a different PlanRun"
        )
    if result.observed_revision != run.revision:
        raise StaleStepHandlingPreparationError(
            "preparation observed revision "
            f"{result.observed_revision}; current revision is {run.revision}"
        )
    step = next((item for item in plan.steps if item.step_id == result.step_id), None)
    if step is None:
        raise UnknownSelectedPlanStepError(
            f"prepared step {result.step_id} does not exist in Plan"
        )
    required = step.required_handling
    if required is None:
        if result.status is not StepHandlingPreparationStatus.HANDLING_UNSPECIFIED:
            raise PlanHandlingInvariantError(
                "result contradicts unspecified PlanStep handling"
            )
    elif result.handling_kind is not required:
        raise PlanHandlingInvariantError(
            "result handling_kind contradicts PlanStep required_handling"
        )

    if result.status is StepHandlingPreparationStatus.PREPARED:
        availability = derive_step_availability(
            plan,
            run,
            result.step_id,
        ).availability
        if availability is not StepAvailability.READY:
            raise SelectedStepNotReadyError(
                f"prepared step {result.step_id} is {availability.value}, not READY"
            )
        expected_need_id = _need_id(
            plan.plan_id,
            run.run_id,
            run.revision,
            result.step_id,
        )
        if (
            result.handling_need is None
            or result.handling_need.need_id != expected_need_id
        ):
            raise PlanHandlingInvariantError(
                "prepared HandlingNeed identity is not canonical for this step revision"
            )
