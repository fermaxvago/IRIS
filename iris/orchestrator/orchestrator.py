"""Identity boundary for one observe-decide-stop orchestration step."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from iris.memory.models import identifier, utc_time
from iris.orchestrator.contracts import OrchestrationPolicy
from iris.orchestrator.errors import OrchestrationPolicyContractError
from iris.orchestrator.models import (
    OrchestrationDecision,
    OrchestrationInput,
    OrchestrationSelection,
    OrchestrationTarget,
)
from iris.orchestrator.policy import DeterministicOrchestrationPolicy


class Orchestrator:
    """Coordinate one request by producing a decision, then stop."""

    def __init__(
        self,
        policy: OrchestrationPolicy | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._policy = DeterministicOrchestrationPolicy() if policy is None else policy
        self._clock: Callable[[], datetime] = (
            (lambda: datetime.now(UTC)) if clock is None else clock
        )
        self._id_factory: Callable[[], str] = (
            (lambda: uuid4().hex) if id_factory is None else id_factory
        )

    def decide(self, orchestration_input: OrchestrationInput) -> OrchestrationDecision:
        if not isinstance(orchestration_input, OrchestrationInput):
            raise TypeError("orchestration_input must be an OrchestrationInput")
        instant = utc_time(self._clock(), "decision created_at")
        if instant < orchestration_input.context.created_at:
            raise ValueError("decision cannot predate its context snapshot")
        decision_id = self._id_factory()
        identifier(decision_id, "decision_id")
        selected = self._policy.select(orchestration_input)
        if not isinstance(selected, OrchestrationSelection):
            raise OrchestrationPolicyContractError(
                "policy must return OrchestrationSelection"
            )
        self._validate_selection(orchestration_input, selected)
        return OrchestrationDecision(
            decision_id=decision_id,
            request_id=orchestration_input.request.request_id,
            context_snapshot_id=orchestration_input.context.snapshot_id,
            target=selected.target,
            reason=selected.reason,
            created_at=instant,
            need_ids=selected.need_ids,
            requirement=selected.requirement,
            context_references=selected.context_references,
        )

    @staticmethod
    def _validate_selection(
        orchestration_input: OrchestrationInput,
        selected: OrchestrationSelection,
    ) -> None:
        needs_by_id = {need.need_id: need for need in orchestration_input.needs}
        expected_ids = tuple(sorted(needs_by_id))
        if selected.need_ids != expected_ids:
            raise OrchestrationPolicyContractError(
                "policy must account for every supplied need exactly once"
            )
        if selected.requirement is not None and (
            needs_by_id.get(selected.requirement.need_id) != selected.requirement
        ):
            raise OrchestrationPolicyContractError(
                "policy selected a requirement outside the input"
            )
        if selected.target in {
            OrchestrationTarget.SYSTEM,
            OrchestrationTarget.MEMORY,
            OrchestrationTarget.CAPABILITY,
            OrchestrationTarget.INTELLIGENCE,
        } and (
            selected.requirement is None
            or not orchestration_input.availability.supports(selected.requirement)
        ):
            raise OrchestrationPolicyContractError(
                "policy selected an unavailable handler"
            )
        supplied_blockers = {
            blocker for need in orchestration_input.needs for blocker in need.blockers
        }
        if any(item not in supplied_blockers for item in selected.context_references):
            raise OrchestrationPolicyContractError(
                "policy referenced a context issue outside the input"
            )
