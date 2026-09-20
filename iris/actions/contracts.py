"""Minimal contract for concrete environment operations."""

from typing import Protocol, TypeVar, runtime_checkable

ActionInputT = TypeVar("ActionInputT", contravariant=True)
ActionOutputT = TypeVar("ActionOutputT", covariant=True)


@runtime_checkable
class Action(Protocol[ActionInputT, ActionOutputT]):
    """A concrete operation against the environment, usable by future tools."""

    @property
    def name(self) -> str:
        """Return the stable action name."""
        ...

    def execute(self, action_input: ActionInputT) -> ActionOutputT:
        """Execute the operation for a validated input."""
        ...
