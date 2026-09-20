"""Minimal contract for capabilities known by IRIS."""

from typing import Protocol, TypeVar, runtime_checkable

SkillInputT = TypeVar("SkillInputT", contravariant=True)
SkillOutputT = TypeVar("SkillOutputT", covariant=True)


@runtime_checkable
class Skill(Protocol[SkillInputT, SkillOutputT]):
    """A higher-level procedure that may compose tools in a future runtime."""

    @property
    def name(self) -> str:
        """Return the stable skill name."""
        ...

    def invoke(self, skill_input: SkillInputT) -> SkillOutputT:
        """Perform the capability for a validated input."""
        ...
