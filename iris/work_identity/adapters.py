"""Pure adapters from established IRIS identities into WorkSubject."""

from __future__ import annotations

from iris.core import Request
from iris.plan_runs import PlanRun, UnknownPlanStepError, validate_plan_run
from iris.planning import Plan
from iris.work_identity.models import (
    PlanStepWorkReference,
    RequestWorkReference,
    WorkOrigin,
    WorkSubject,
    WorkSubjectKind,
)


def work_subject_from_request(request: Request) -> WorkSubject:
    """Identify one Request and record it as its own known root origin."""

    if not isinstance(request, Request):
        raise TypeError("request must be a Request")
    reference = RequestWorkReference(request.request_id)
    return WorkSubject(
        WorkSubjectKind.REQUEST,
        reference,
        WorkOrigin("request", request.request_id),
    )


def work_subject_from_plan_step(
    plan: Plan,
    run: PlanRun,
    step_id: str,
    origin: WorkOrigin | None = None,
) -> WorkSubject:
    """Identify one PlanStep in one Run without inspecting readiness or state."""

    validate_plan_run(plan, run)
    reference = PlanStepWorkReference(plan.plan_id, run.run_id, step_id)
    if reference.step_id not in {step.step_id for step in plan.steps}:
        raise UnknownPlanStepError(f"unknown Plan step {reference.step_id}")
    return WorkSubject(WorkSubjectKind.PLAN_STEP, reference, origin)
