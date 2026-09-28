"""Stable operational work identity and descriptive root provenance."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from iris.work_identity.errors import (
    WorkIdentityError,
    WorkReferenceMismatchError,
    WorkSubjectInvariantError,
)
from iris.work_identity.models import (
    PlanStepWorkReference,
    RequestWorkReference,
    WorkOrigin,
    WorkSubject,
    WorkSubjectKind,
)

if TYPE_CHECKING:
    from iris.core import Request
    from iris.plan_runs import PlanRun
    from iris.planning import Plan


def work_subject_from_request(request: Request) -> WorkSubject:
    """Load the Request adapter without coupling identity models to Planning."""

    from iris.work_identity.adapters import work_subject_from_request as adapt

    return adapt(request)


def work_subject_from_plan_step(
    plan: Plan,
    run: PlanRun,
    step_id: str,
    origin: WorkOrigin | None = None,
) -> WorkSubject:
    """Load the Plan adapter only when a caller explicitly needs it."""

    from iris.work_identity.adapters import work_subject_from_plan_step as adapt

    return adapt(plan, run, step_id, origin)


def __getattr__(name: str) -> Any:
    """Preserve the WP015 error re-export without an eager PlanRun import."""

    if name == "UnknownPlanStepError":
        from iris.plan_runs import UnknownPlanStepError

        return UnknownPlanStepError
    raise AttributeError(name)


__all__ = [
    "PlanStepWorkReference",
    "RequestWorkReference",
    "UnknownPlanStepError",
    "WorkIdentityError",
    "WorkOrigin",
    "WorkReferenceMismatchError",
    "WorkSubject",
    "WorkSubjectInvariantError",
    "WorkSubjectKind",
    "work_subject_from_plan_step",
    "work_subject_from_request",
]
