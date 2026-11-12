"""Validated, static descriptors for the built-in conceptual Planning rules."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from iris.planning import DeterministicPlanner, PlanningRule
from iris.planning.study_strategy import study_session_rule

_ID_PATTERN = re.compile(r"[a-z][a-z0-9_]*\Z")


@dataclass(frozen=True, slots=True)
class StrategyDescriptor:
    strategy_id: str
    description: str
    rule: PlanningRule

    def __post_init__(self) -> None:
        if type(self.strategy_id) is not str or not _ID_PATTERN.fullmatch(
            self.strategy_id
        ):
            raise ValueError("invalid strategy identifier")
        if (
            type(self.description) is not str
            or not self.description.strip()
            or self.description != self.description.strip()
            or any(
                unicodedata.category(char).startswith("C") for char in self.description
            )
        ):
            raise ValueError("invalid strategy description")
        if type(self.rule) is not PlanningRule:
            raise ValueError("invalid planning rule")
        if (
            PlanningRule(
                self.rule.objective,
                self.rule.steps,
                self.rule.assumptions,
                self.rule.required_context,
            )
            != self.rule
        ):
            raise ValueError("inconsistent planning rule")


@dataclass(frozen=True, slots=True)
class StrategyManifest:
    entries: tuple[StrategyDescriptor, ...]

    def __post_init__(self) -> None:
        if (
            type(self.entries) is not tuple
            or not self.entries
            or any(type(entry) is not StrategyDescriptor for entry in self.entries)
        ):
            raise ValueError("invalid strategy manifest")
        for entry in self.entries:
            StrategyDescriptor(entry.strategy_id, entry.description, entry.rule)
        if len({entry.strategy_id for entry in self.entries}) != len(self.entries):
            raise ValueError("duplicate strategy identifier")
        # The planner owns normalized-objective uniqueness and rule validation.
        DeterministicPlanner(tuple(entry.rule for entry in self.entries))
        object.__setattr__(
            self,
            "entries",
            tuple(sorted(self.entries, key=lambda item: item.strategy_id)),
        )

    def resolve(self, strategy_id: str) -> StrategyDescriptor | None:
        return next(
            (entry for entry in self.entries if entry.strategy_id == strategy_id), None
        )

    @property
    def rules(self) -> tuple[PlanningRule, ...]:
        return tuple(entry.rule for entry in self.entries)


def built_in_manifest() -> StrategyManifest:
    return StrategyManifest(
        (
            StrategyDescriptor(
                "estudio",
                "Preparación conceptual de una sesión individual de estudio.",
                study_session_rule(),
            ),
        )
    )
