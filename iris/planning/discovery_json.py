"""Public JSON 1.0 for read-only built-in strategy metadata queries."""

from __future__ import annotations

import json
from typing import cast

from iris.memory.models import MemoryScope
from iris.planning.models import PlanningContextRequirement
from iris.planning.strategy_manifest import (
    StrategyDescriptor,
    StrategyManifest,
)


def _fields(value: object, names: tuple[str, ...]) -> dict[str, object]:
    if type(value) is not dict or set(value) != set(names):
        raise ValueError("invalid discovery JSON fields")
    return cast(dict[str, object], value)


def _string(value: object, expected: str) -> None:
    if type(value) is not str or value != expected:
        raise ValueError("discovery JSON differs from registered strategy")


def _validated_manifest(manifest: StrategyManifest) -> StrategyManifest:
    if type(manifest) is not StrategyManifest:
        raise ValueError("invalid strategy manifest")
    validated = StrategyManifest(manifest.entries)
    if validated.entries != manifest.entries:
        raise ValueError("strategy manifest order changed")
    for descriptor in validated.entries:
        for requirement in descriptor.rule.required_context:
            if (
                type(requirement) is not PlanningContextRequirement
                or type(requirement.scope) is not MemoryScope
            ):
                raise ValueError("invalid registered context requirement")
            scope = MemoryScope(requirement.scope.kind, requirement.scope.identifier)
            if scope != requirement.scope:
                raise ValueError("inconsistent registered context scope")
            if (
                PlanningContextRequirement(requirement.kind, requirement.key, scope)
                != requirement
            ):
                raise ValueError("inconsistent registered context requirement")
    return validated


def _catalog_data(manifest: StrategyManifest) -> dict[str, object]:
    return {
        "format_version": "1.0",
        "document_type": "strategy_catalog",
        "strategies": [
            {
                "strategy_id": entry.strategy_id,
                "description": entry.description,
                "objective": entry.rule.objective,
            }
            for entry in manifest.entries
        ],
    }


def _requirements_data(descriptor: StrategyDescriptor) -> dict[str, object]:
    return {
        "format_version": "1.0",
        "document_type": "strategy_requirements",
        "strategy_id": descriptor.strategy_id,
        "objective": descriptor.rule.objective,
        "required_context": [
            requirement.to_data() for requirement in descriptor.rule.required_context
        ],
    }


def _validated_catalog(data: object, manifest: StrategyManifest) -> None:
    fields = _fields(data, ("format_version", "document_type", "strategies"))
    _string(fields["format_version"], "1.0")
    _string(fields["document_type"], "strategy_catalog")
    strategies = fields["strategies"]
    if type(strategies) is not list or len(strategies) != len(manifest.entries):
        raise ValueError("invalid strategy catalog")
    for item, entry in zip(strategies, manifest.entries, strict=True):
        published = _fields(item, ("strategy_id", "description", "objective"))
        _string(published["strategy_id"], entry.strategy_id)
        _string(published["description"], entry.description)
        _string(published["objective"], entry.rule.objective)


def _validated_requirements(data: object, descriptor: StrategyDescriptor) -> None:
    fields = _fields(
        data,
        (
            "format_version",
            "document_type",
            "strategy_id",
            "objective",
            "required_context",
        ),
    )
    _string(fields["format_version"], "1.0")
    _string(fields["document_type"], "strategy_requirements")
    _string(fields["strategy_id"], descriptor.strategy_id)
    _string(fields["objective"], descriptor.rule.objective)
    requirements = fields["required_context"]
    if type(requirements) is not list or len(requirements) != len(
        descriptor.rule.required_context
    ):
        raise ValueError("invalid published requirements")
    for item, source in zip(
        requirements, descriptor.rule.required_context, strict=True
    ):
        published = _fields(item, ("kind", "key", "scope"))
        _string(published["kind"], source.kind)
        _string(published["key"], source.key)
        scope = _fields(published["scope"], ("kind", "identifier"))
        _string(scope["kind"], source.scope.kind.value)
        if (
            type(scope["identifier"]) is not type(source.scope.identifier)
            or scope["identifier"] != source.scope.identifier
        ):
            raise ValueError("published requirement scope differs from rule")


def _serialized(data: dict[str, object]) -> str:
    document = json.dumps(
        data, ensure_ascii=True, allow_nan=False, separators=(",", ":")
    )
    if type(document) is not str:
        raise ValueError("discovery serializer returned a non-string")
    return document


def catalog_json_document(manifest: StrategyManifest) -> str:
    """Validate and serialize every registered descriptor without Planning."""

    validated = _validated_manifest(manifest)
    data = _catalog_data(validated)
    _validated_catalog(data, validated)
    return _serialized(data)


def requirements_json_document(manifest: StrategyManifest, strategy_id: str) -> str:
    """Serialize exactly the selected rule's declared requirements."""

    validated = _validated_manifest(manifest)
    descriptor = validated.resolve(strategy_id)
    if descriptor is None:
        raise ValueError("unknown registered strategy")
    data = _requirements_data(descriptor)
    _validated_requirements(data, descriptor)
    return _serialized(data)
