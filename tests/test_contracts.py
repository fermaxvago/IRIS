from __future__ import annotations

from iris.actions import Action
from iris.memory import Memory
from iris.router import Router
from iris.skills import Skill


class ExampleRouter:
    def route(self, request: str) -> str:
        return "local"


class ExampleSkill:
    name = "example-skill"

    def invoke(self, skill_input: str) -> str:
        return skill_input.upper()


class ExampleAction:
    name = "example-action"

    def execute(self, action_input: int) -> int:
        return action_input + 1


class ExampleMemory:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def store(self, key: str, value: str) -> None:
        self.values[key] = value

    def retrieve(self, key: str) -> str | None:
        return self.values.get(key)

    def forget(self, key: str) -> bool:
        return self.values.pop(key, None) is not None


def test_contracts_accept_structural_implementations() -> None:
    assert isinstance(ExampleRouter(), Router)
    assert isinstance(ExampleSkill(), Skill)
    assert isinstance(ExampleAction(), Action)
    assert isinstance(ExampleMemory(), Memory)


def test_memory_contract_does_not_depend_on_a_model_provider() -> None:
    memory = ExampleMemory()

    memory.store("owner", "IRIS")

    assert memory.retrieve("owner") == "IRIS"
    assert memory.forget("owner") is True
    assert memory.retrieve("owner") is None
