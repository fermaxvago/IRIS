"""The bounded, versioned public representation of a Planning evaluation."""

from __future__ import annotations

import json
from typing import cast

from iris.core.request import Request
from iris.planning.models import PlanningRequest, PlanningResult


def _fields(value: object, names: tuple[str, ...]) -> dict[str, object]:
    if type(value) is not dict or set(value) != set(names):
        raise ValueError("invalid public Planning field structure")
    return cast(dict[str, object], value)


def _string(value: object) -> None:
    if type(value) is not str:
        raise ValueError("invalid public Planning string")


def _optional_string(value: object) -> None:
    if value is not None:
        _string(value)


def _list(value: object) -> list[object]:
    if type(value) is not list:
        raise ValueError("invalid public Planning list")
    return cast(list[object], value)


def _scope(value: object) -> None:
    data = _fields(value, ("kind", "identifier"))
    _string(data["kind"])
    _optional_string(data["identifier"])


def _constraint(value: object) -> None:
    data = _fields(value, ("kind", "subject", "value"))
    _string(data["kind"])
    _string(data["subject"])
    if data["value"] is not None and type(data["value"]) not in (
        str,
        int,
        float,
        bool,
    ):
        raise ValueError("invalid public Planning constraint value")


def _goal(value: object) -> dict[str, object]:
    data = _fields(
        value,
        (
            "goal_id",
            "objective",
            "scope",
            "provenance",
            "constraints",
            "success_criteria",
        ),
    )
    _string(data["goal_id"])
    _string(data["objective"])
    _scope(data["scope"])
    provenance = _fields(data["provenance"], ("source_type", "source_id", "actor"))
    _string(provenance["source_type"])
    _optional_string(provenance["source_id"])
    _optional_string(provenance["actor"])
    for item in _list(data["constraints"]):
        _constraint(item)
    for item in _list(data["success_criteria"]):
        _string(item)
    return data


def _planning_request(value: object, source: PlanningRequest) -> None:
    data = _fields(
        value, ("planning_request_id", "goal", "created_at", "context_snapshot_id")
    )
    _string(data["planning_request_id"])
    goal = _goal(data["goal"])
    _string(data["created_at"])
    _optional_string(data["context_snapshot_id"])
    if (
        data["planning_request_id"] != source.planning_request_id
        or data["created_at"] != source.created_at.isoformat()
        or data["context_snapshot_id"]
        != (None if source.context is None else source.context.snapshot_id)
        or goal["goal_id"] != source.goal.goal_id
        or goal["objective"] != source.goal.objective
    ):
        raise ValueError("public Planning request identity mismatch")
    scope = _fields(goal["scope"], ("kind", "identifier"))
    provenance = _fields(goal["provenance"], ("source_type", "source_id", "actor"))
    if (
        scope["kind"] != source.goal.scope.kind.value
        or scope["identifier"] != source.goal.scope.identifier
        or provenance["source_type"] != source.goal.provenance.source_type
        or provenance["source_id"] != source.goal.provenance.source_id
        or provenance["actor"] != source.goal.provenance.actor
    ):
        raise ValueError("public Planning request provenance mismatch")


def _step(value: object) -> None:
    data = _fields(
        value,
        (
            "step_id",
            "objective",
            "depends_on",
            "required_handling",
            "constraints",
            "expected_outcome",
        ),
    )
    for name in ("step_id", "objective", "expected_outcome"):
        _string(data[name])
    _optional_string(data["required_handling"])
    for item in _list(data["depends_on"]):
        _string(item)
    for item in _list(data["constraints"]):
        _constraint(item)


def _plan(value: object) -> None:
    if value is None:
        return
    data = _fields(value, ("plan_id", "goal_id", "assumptions", "steps"))
    _string(data["plan_id"])
    _string(data["goal_id"])
    for item in _list(data["assumptions"]):
        _string(item)
    for item in _list(data["steps"]):
        _step(item)


def _requirement(value: object) -> None:
    data = _fields(value, ("kind", "key", "scope"))
    _string(data["kind"])
    _string(data["key"])
    _scope(data["scope"])


def _planning_result(value: object, source: PlanningResult) -> None:
    data = _fields(
        value,
        (
            "planning_result_id",
            "planning_request_id",
            "goal_id",
            "status",
            "reason",
            "created_at",
            "plan",
            "missing_context",
            "constraint_conflicts",
        ),
    )
    for name in (
        "planning_result_id",
        "planning_request_id",
        "goal_id",
        "status",
        "reason",
        "created_at",
    ):
        _string(data[name])
    _plan(data["plan"])
    for item in _list(data["missing_context"]):
        _requirement(item)
    for item in _list(data["constraint_conflicts"]):
        _string(item)
    if (
        data["planning_result_id"] != source.planning_result_id
        or data["planning_request_id"] != source.planning_request_id
        or data["goal_id"] != source.goal_id
        or data["status"] != source.status.value
        or data["reason"] != source.reason.value
        or data["created_at"] != source.created_at.isoformat()
        or (data["plan"] is None) != (source.plan is None)
    ):
        raise ValueError("public Planning result identity mismatch")
    if source.plan is not None:
        plan = _fields(data["plan"], ("plan_id", "goal_id", "assumptions", "steps"))
        if (
            plan["plan_id"] != source.plan.plan_id
            or plan["goal_id"] != source.plan.goal_id
        ):
            raise ValueError("public Planning plan identity mismatch")


def planning_json_document(
    user_request: Request,
    request: PlanningRequest,
    result: PlanningResult,
    *,
    strategy_id: str | None,
) -> str:
    """Serialize one validated evaluation only after checking the public shape."""

    if (
        user_request.source != "cli"
        or user_request.request_id != request.goal.scope.identifier
        or request.goal.provenance.source_type != "request"
        or request.goal.provenance.source_id != user_request.request_id
    ):
        raise ValueError("public Planning input provenance mismatch")
    if strategy_id is None:
        if user_request.content != request.goal.objective:
            raise ValueError("public Planning objective provenance mismatch")
        input_data = {"mode": "objective"}
    else:
        if (
            user_request.content != strategy_id
            or user_request.metadata.get("input_mode") != "strategy_id"
            or user_request.metadata.get("strategy_id") != strategy_id
        ):
            raise ValueError("public Planning strategy provenance mismatch")
        input_data = {"mode": "strategy_id", "strategy_id": strategy_id}
    document: dict[str, object] = {
        "format_version": "1.0",
        "input": input_data,
        "planning_request": request.to_data(),
        "planning_result": result.to_trace(),
    }
    _fields(
        document, ("format_version", "input", "planning_request", "planning_result")
    )
    _fields(input_data, ("mode",) if strategy_id is None else ("mode", "strategy_id"))
    _planning_request(document["planning_request"], request)
    _planning_result(document["planning_result"], result)
    return json.dumps(
        document, ensure_ascii=True, allow_nan=False, separators=(",", ":")
    )
