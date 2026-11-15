"""Strict, bounded caller context for one explicit Planning strategy."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime
from typing import BinaryIO, cast

from iris.context import (
    ContextBudget,
    ContextCandidate,
    ContextEngine,
    ContextEvidence,
    ContextItem,
    ContextSnapshot,
    EvidenceSource,
    Freshness,
    Relevance,
    ResolutionStatus,
)
from iris.context.models import ContextValue
from iris.memory import EpistemicStatus, MemoryScope, ScopeKind
from iris.planning import PlanningContextRequirement
from iris.planning.strategy_manifest import StrategyDescriptor
from iris.work_identity import (
    RequestWorkReference,
    WorkOrigin,
    WorkSubject,
    WorkSubjectKind,
)

MAX_BYTES = 32768
MAX_ITEMS = 16
MAX_STRING = 1024
MAX_INTEGER = 2**53 - 1


class ContextInputError(ValueError):
    """The caller's bounded JSON document violates the public input contract."""


@dataclass(frozen=True, slots=True)
class SubmittedContextItem:
    requirement: PlanningContextRequirement
    value: ContextValue


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ContextInputError("duplicate JSON property")
        result[key] = value
    return result


def _integer(token: str) -> int:
    try:
        value = int(token)
    except ValueError as exc:
        raise ContextInputError("invalid or excessive integer") from exc
    if abs(value) > MAX_INTEGER:
        raise ContextInputError("integer outside public range")
    return value


def _float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise ContextInputError("nonfinite number")
    return value


def _constant(_token: str) -> None:
    raise ContextInputError("nonfinite constant")


def _fields(value: object, expected: set[str]) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected:
        raise ContextInputError("invalid context document shape")
    return cast(dict[str, object], value)


def _text(value: object) -> str:
    if type(value) is not str or any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ContextInputError("invalid context text")
    return value


def _value(value: object) -> ContextValue:
    if type(value) is str:
        text = _text(value)
        if not text.strip() or len(text) > MAX_STRING:
            raise ContextInputError("invalid context string value")
        return text
    if type(value) is int:
        if abs(value) > MAX_INTEGER:
            raise ContextInputError("integer outside public range")
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ContextInputError("nonfinite number")
        return value
    if type(value) is bool:
        return value
    raise ContextInputError("invalid context scalar value")


def read_context_input(
    stream: BinaryIO, descriptor: StrategyDescriptor
) -> tuple[SubmittedContextItem, ...]:
    """Read at most MAX_BYTES + 1 bytes and match only declared identities."""

    chunks: list[bytes] = []
    size = 0
    while size <= MAX_BYTES:
        chunk = stream.read(MAX_BYTES + 1 - size)
        if type(chunk) is not bytes:
            raise TypeError("context stream must provide bytes")
        if not chunk:
            break
        chunks.append(chunk)
        size += len(chunk)
    if size > MAX_BYTES:
        raise ContextInputError("context document exceeds byte limit")
    try:
        source = b"".join(chunks).decode("utf-8", errors="strict")
        data = json.loads(
            source,
            object_pairs_hook=_object,
            parse_int=_integer,
            parse_float=_float,
            parse_constant=_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ContextInputError("invalid context JSON") from exc
    document = _fields(data, {"format_version", "items"})
    if (
        type(document["format_version"]) is not str
        or document["format_version"] != "1.0"
    ):
        raise ContextInputError("unsupported context format")
    raw_items = document["items"]
    if type(raw_items) is not list or not 1 <= len(raw_items) <= MAX_ITEMS:
        raise ContextInputError("invalid context item count")
    if len(raw_items) > len(descriptor.rule.required_context):
        raise ContextInputError("context exceeds declared requirements")
    declared = set(descriptor.rule.required_context)
    seen: set[PlanningContextRequirement] = set()
    accepted: list[SubmittedContextItem] = []
    for raw in raw_items:
        item = _fields(raw, {"kind", "key", "scope", "value"})
        scope_data = _fields(item["scope"], {"kind", "identifier"})
        kind = _text(item["kind"])
        key = _text(item["key"])
        scope_kind = _text(scope_data["kind"])
        scope_identifier = scope_data["identifier"]
        if scope_identifier is not None:
            scope_identifier = _text(scope_identifier)
        try:
            scope = MemoryScope(ScopeKind(scope_kind), scope_identifier)
            requirement = PlanningContextRequirement(kind, key, scope)
        except (TypeError, ValueError) as exc:
            raise ContextInputError("invalid context requirement identity") from exc
        if requirement not in declared or requirement in seen:
            raise ContextInputError("unknown or duplicate context requirement")
        seen.add(requirement)
        accepted.append(SubmittedContextItem(requirement, _value(item["value"])))
    return tuple(accepted)


def build_context_snapshot(
    *,
    request_id: str,
    items: tuple[SubmittedContextItem, ...],
    candidate_id_factory: Callable[[], str],
    created_at: datetime,
    engine: ContextEngine,
) -> ContextSnapshot:
    """Use ContextEngine and reject any dropped, changed or invented selection."""

    candidates = tuple(
        ContextCandidate(
            candidate_id=candidate_id_factory(),
            kind=item.requirement.kind,
            key=item.requirement.key,
            value=item.value,
            evidence=ContextEvidence(
                EvidenceSource.CALLER, request_id, EpistemicStatus.UNKNOWN
            ),
            scope=item.requirement.scope,
            relevance=Relevance.REQUIRED,
            freshness=Freshness.UNKNOWN,
            observed_at=None,
            eligible=True,
        )
        for item in items
    )
    if len({item.candidate_id for item in candidates}) != len(candidates):
        raise ValueError("duplicate generated candidate identity")
    pristine_candidates = deepcopy(candidates)
    budget = ContextBudget(len(candidates))
    snapshot = engine.build(
        request_id=request_id,
        candidates=candidates,
        budget=budget,
        created_at=created_at,
    )
    if type(snapshot) is not ContextSnapshot:
        raise ValueError("context engine returned a noncanonical snapshot")
    if replace(snapshot) != snapshot:
        raise ValueError("context engine returned a malformed snapshot")
    canonical_subject = WorkSubject(
        WorkSubjectKind.REQUEST,
        RequestWorkReference(request_id),
        WorkOrigin("request", request_id),
    )
    if (
        snapshot.request_id != request_id
        or snapshot.created_at != created_at
        or type(snapshot.subject) is not WorkSubject
        or replace(snapshot.subject) != canonical_subject
        or snapshot.status is not ResolutionStatus.RESOLVED
        or type(snapshot.budget) is not ContextBudget
        or replace(snapshot.budget) != budget
        or snapshot.budget.max_items != len(pristine_candidates)
        or snapshot.uncertainties
        or snapshot.conflicts
        or snapshot.budget_excluded_ids
        or len(snapshot.items) != len(candidates)
    ):
        raise ValueError("context selection did not preserve supplied candidates")
    expected = {item.candidate_id: item.to_item() for item in pristine_candidates}
    actual = {item.candidate_id: item for item in snapshot.items}
    if actual.keys() != expected.keys() or any(
        type(actual[key]) is not ContextItem
        or replace(actual[key]) != value
        or type(actual[key].value) is not type(value.value)
        or type(actual[key].scope) is not MemoryScope
        or replace(actual[key].scope) != value.scope
        or type(actual[key].evidence) is not ContextEvidence
        or replace(actual[key].evidence) != value.evidence
        for key, value in expected.items()
    ):
        raise ValueError("context selection changed supplied candidates")
    return snapshot
