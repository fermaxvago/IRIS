"""Conservative deterministic PlanStep outcome evaluation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from iris.outcome_assessment.errors import (
    DuplicateOutcomeEvidenceError,
    ForeignOutcomeEvidenceError,
    OutcomeAssessmentIdentityError,
    OutcomeEvaluationError,
)
from iris.outcome_assessment.models import StepOutcomeAssessment, StepOutcomeStatus
from iris.plan_runs import PlanObservation, PlanRun, validate_plan_run
from iris.planning import Plan, PlanStep


def _utc_time(value: datetime, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise OutcomeAssessmentIdentityError(
            f"{name} must be a timezone-aware datetime"
        )
    return value.astimezone(UTC)


class ConservativeStepOutcomeEvaluator:
    """Abstain unless explicit future rules can justify a binary conclusion."""

    DEFAULT_EVALUATOR_REFERENCE = "deterministic.conservative.v1"

    def __init__(
        self,
        *,
        evaluator_reference: str = DEFAULT_EVALUATOR_REFERENCE,
        clock: Callable[[], datetime] | None = None,
        assessment_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if not isinstance(evaluator_reference, str) or not evaluator_reference.strip():
            raise ValueError("evaluator_reference must be nonblank text")
        if evaluator_reference != evaluator_reference.strip():
            raise ValueError("evaluator_reference must not have surrounding whitespace")
        self._evaluator_reference = evaluator_reference
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)
        self._assessment_id_factory = (
            assessment_id_factory
            if assessment_id_factory is not None
            else lambda: uuid4().hex
        )

    @property
    def evaluator_reference(self) -> str:
        return self._evaluator_reference

    def evaluate(
        self,
        plan: Plan,
        run: PlanRun,
        step: PlanStep,
        evidence: tuple[PlanObservation, ...],
    ) -> StepOutcomeAssessment:
        """Validate explicit evidence, produce one conservative assessment, stop."""

        validate_plan_run(plan, run)
        if not isinstance(step, PlanStep):
            raise TypeError("step must be a PlanStep")
        if not isinstance(evidence, tuple):
            raise TypeError("evidence must be a tuple of PlanObservation values")
        if any(not isinstance(item, PlanObservation) for item in evidence):
            raise TypeError("evidence must contain PlanObservation values")

        canonical_step = next(
            (item for item in plan.steps if item.step_id == step.step_id), None
        )
        if canonical_step is None:
            raise OutcomeAssessmentIdentityError(
                f"step {step.step_id} does not belong to Plan {plan.plan_id}"
            )
        if canonical_step != step:
            raise OutcomeAssessmentIdentityError(
                "step definition differs from the canonical PlanStep"
            )

        observation_ids = tuple(item.observation_id for item in evidence)
        if len(observation_ids) != len(set(observation_ids)):
            raise DuplicateOutcomeEvidenceError(
                "outcome evidence must not contain duplicate observation IDs"
            )
        canonical_observations = {
            item.observation_id: item for item in run.observations
        }
        for observation in evidence:
            if observation.run_id != run.run_id:
                raise ForeignOutcomeEvidenceError(
                    f"observation {observation.observation_id} belongs to another Run"
                )
            if observation.step_id != step.step_id:
                raise ForeignOutcomeEvidenceError(
                    f"observation {observation.observation_id} is not scoped to "
                    f"step {step.step_id}"
                )
            canonical = canonical_observations.get(observation.observation_id)
            if canonical is None:
                raise ForeignOutcomeEvidenceError(
                    f"observation {observation.observation_id} is not recorded in "
                    f"PlanRun {run.run_id}"
                )
            if canonical != observation:
                raise ForeignOutcomeEvidenceError(
                    f"observation {observation.observation_id} differs from canonical "
                    "PlanRun evidence"
                )

        assessed_at = self._read_clock()
        if assessed_at < run.created_at:
            raise OutcomeAssessmentIdentityError(
                "assessment cannot predate PlanRun creation"
            )
        if evidence and assessed_at < max(item.observed_at for item in evidence):
            raise OutcomeAssessmentIdentityError(
                "assessment cannot predate its latest evidence"
            )
        assessment_id = self._new_assessment_id()

        if evidence:
            status = StepOutcomeStatus.INDETERMINATE
            details: dict[str, object] = {
                "reason": "unsupported_expected_outcome",
                "evidence_count": len(evidence),
            }
        else:
            status = StepOutcomeStatus.INSUFFICIENT_EVIDENCE
            details = {"reason": "no_evidence", "evidence_count": 0}

        return StepOutcomeAssessment(
            assessment_id=assessment_id,
            plan_id=plan.plan_id,
            run_id=run.run_id,
            run_revision=run.revision,
            step_id=step.step_id,
            status=status,
            evidence_ids=observation_ids,
            evaluator_reference=self._evaluator_reference,
            assessed_at=assessed_at,
            details=details,
        )

    def _read_clock(self) -> datetime:
        try:
            instant = self._clock()
        except Exception as exc:
            raise OutcomeEvaluationError("outcome evaluator clock failed") from exc
        return _utc_time(instant, "assessed_at")

    def _new_assessment_id(self) -> str:
        try:
            assessment_id = self._assessment_id_factory()
        except Exception as exc:
            raise OutcomeEvaluationError(
                "outcome evaluator assessment ID factory failed"
            ) from exc
        if not isinstance(assessment_id, str):
            raise OutcomeEvaluationError(
                "outcome evaluator assessment ID factory returned a non-string"
            )
        return assessment_id
