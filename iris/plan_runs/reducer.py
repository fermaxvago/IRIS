"""Deterministic, side-effect-free reducer for one atomic PlanRun update."""

from __future__ import annotations

from dataclasses import replace

from iris.plan_runs.errors import (
    DuplicateRunIdentityError,
    ForeignEvidenceError,
    InvalidBlockerOperationError,
    InvalidStepTransitionError,
    PlanRunIdentityError,
    PlanRunInvariantError,
    StalePlanRunUpdateError,
    UnknownPlanStepError,
)
from iris.plan_runs.models import (
    AddBlockerUpdate,
    PlanBlocker,
    PlanBlockerState,
    PlanObservation,
    PlanRun,
    PlanRunUpdate,
    RecordObservationUpdate,
    ResolveBlockerUpdate,
    StepAvailability,
    StepProgress,
    StepProgressState,
    StepProgressUpdate,
)
from iris.plan_runs.state import derive_step_availability, validate_plan_run
from iris.planning import Plan

_LEGAL_TRANSITIONS = {
    (StepProgressState.NOT_STARTED, StepProgressState.ACTIVE),
    (StepProgressState.NOT_STARTED, StepProgressState.FAILED),
    (StepProgressState.ACTIVE, StepProgressState.SUCCEEDED),
    (StepProgressState.ACTIVE, StepProgressState.FAILED),
}


class PlanRunReducer:
    """Validate one update and return revision N+1, then stop."""

    def apply(self, plan: Plan, run: PlanRun, update: PlanRunUpdate) -> PlanRun:
        validate_plan_run(plan, run)
        if not isinstance(update, PlanRunUpdate):
            raise TypeError("update must be a PlanRunUpdate")
        self._validate_envelope(run, update)

        if isinstance(update, StepProgressUpdate):
            result = self._transition_step(plan, run, update)
        elif isinstance(update, RecordObservationUpdate):
            result = self._record_observation(plan, run, update)
        elif isinstance(update, AddBlockerUpdate):
            result = self._add_blocker(plan, run, update)
        elif isinstance(update, ResolveBlockerUpdate):
            result = self._resolve_blocker(plan, run, update)
        else:  # pragma: no cover - sealed by public subclasses
            raise TypeError("unsupported PlanRunUpdate operation")
        validate_plan_run(plan, result)
        return result

    @staticmethod
    def _validate_envelope(run: PlanRun, update: PlanRunUpdate) -> None:
        if update.run_id != run.run_id:
            raise PlanRunIdentityError("update references a different PlanRun")
        if update.expected_revision != run.revision:
            raise StalePlanRunUpdateError(
                f"update expected revision {update.expected_revision}; "
                f"current revision is {run.revision}"
            )
        if update.updated_at < run.updated_at:
            raise PlanRunInvariantError(
                "update timestamp cannot predate current run updated_at"
            )

    @staticmethod
    def _progress(run: PlanRun, step_id: str) -> StepProgress:
        for progress in run.step_progress:
            if progress.step_id == step_id:
                return progress
        raise UnknownPlanStepError(f"unknown Plan step {step_id}")

    def _transition_step(
        self, plan: Plan, run: PlanRun, update: StepProgressUpdate
    ) -> PlanRun:
        current = self._progress(run, update.step_id)
        transition = (current.state, update.new_state)
        if transition not in _LEGAL_TRANSITIONS:
            raise InvalidStepTransitionError(
                f"illegal transition {current.state.value} -> {update.new_state.value}"
            )
        if current.state is StepProgressState.NOT_STARTED:
            availability = derive_step_availability(plan, run, update.step_id)
            if availability.availability is not StepAvailability.READY:
                raise InvalidStepTransitionError(
                    f"step {update.step_id} is {availability.availability.value}, "
                    "not ready"
                )
        self._validate_evidence(run, update.step_id, update.evidence_ids)
        changed = StepProgress(
            step_id=update.step_id,
            state=update.new_state,
            changed_at=update.updated_at,
            evidence_ids=update.evidence_ids,
        )
        progress = tuple(
            changed if item.step_id == update.step_id else item
            for item in run.step_progress
        )
        return self._next(run, update, step_progress=progress)

    @staticmethod
    def _validate_evidence(
        run: PlanRun, step_id: str, evidence_ids: tuple[str, ...]
    ) -> None:
        if not evidence_ids:
            return
        observations = {item.observation_id: item for item in run.observations}
        for evidence_id in evidence_ids:
            evidence = observations.get(evidence_id)
            if evidence is None:
                raise ForeignEvidenceError(f"unknown evidence {evidence_id}")
            if evidence.run_id != run.run_id:
                raise ForeignEvidenceError(
                    f"evidence {evidence_id} belongs to another Run"
                )
            if evidence.step_id not in {None, step_id}:
                raise ForeignEvidenceError(
                    f"evidence {evidence_id} is scoped to another step"
                )

    def _record_observation(
        self, plan: Plan, run: PlanRun, update: RecordObservationUpdate
    ) -> PlanRun:
        observation = update.observation
        if observation.run_id != run.run_id:
            raise PlanRunIdentityError("observation belongs to a different PlanRun")
        if observation.step_id is not None:
            self._require_plan_step(plan, observation.step_id)
        if any(
            item.observation_id == observation.observation_id
            for item in run.observations
        ):
            raise DuplicateRunIdentityError(
                f"duplicate observation identity {observation.observation_id}"
            )
        if not run.created_at <= observation.observed_at <= update.updated_at:
            raise PlanRunInvariantError(
                "observation time must fall between Run creation and update"
            )
        return self._next(
            run,
            update,
            observations=run.observations + (observation,),
        )

    def _add_blocker(
        self, plan: Plan, run: PlanRun, update: AddBlockerUpdate
    ) -> PlanRun:
        blocker = update.blocker
        if blocker.run_id != run.run_id:
            raise PlanRunIdentityError("blocker belongs to a different PlanRun")
        self._require_plan_step(plan, blocker.step_id)
        progress = self._progress(run, blocker.step_id)
        if progress.state is not StepProgressState.NOT_STARTED:
            raise InvalidBlockerOperationError(
                "blockers can be added only to NOT_STARTED steps"
            )
        if blocker.state is not PlanBlockerState.ACTIVE:
            raise InvalidBlockerOperationError("a new blocker must be active")
        if blocker.created_at != update.updated_at:
            raise InvalidBlockerOperationError(
                "blocker created_at must equal update timestamp"
            )
        if any(item.blocker_id == blocker.blocker_id for item in run.blockers):
            raise DuplicateRunIdentityError(
                f"duplicate blocker identity {blocker.blocker_id}"
            )
        return self._next(run, update, blockers=run.blockers + (blocker,))

    def _resolve_blocker(
        self, plan: Plan, run: PlanRun, update: ResolveBlockerUpdate
    ) -> PlanRun:
        blocker = next(
            (item for item in run.blockers if item.blocker_id == update.blocker_id),
            None,
        )
        if blocker is None:
            raise InvalidBlockerOperationError(f"unknown blocker {update.blocker_id}")
        self._require_plan_step(plan, blocker.step_id)
        progress = self._progress(run, blocker.step_id)
        if progress.state is not StepProgressState.NOT_STARTED:
            raise InvalidBlockerOperationError(
                "blockers can be resolved only while the step is NOT_STARTED"
            )
        if blocker.state is PlanBlockerState.RESOLVED:
            raise InvalidBlockerOperationError("blocker is already resolved")
        resolved = replace(
            blocker,
            state=PlanBlockerState.RESOLVED,
            resolved_at=update.updated_at,
        )
        blockers = tuple(
            resolved if item.blocker_id == update.blocker_id else item
            for item in run.blockers
        )
        return self._next(run, update, blockers=blockers)

    @staticmethod
    def _require_plan_step(plan: Plan, step_id: str) -> None:
        if all(step.step_id != step_id for step in plan.steps):
            raise UnknownPlanStepError(f"unknown Plan step {step_id}")

    @staticmethod
    def _next(
        run: PlanRun,
        update: PlanRunUpdate,
        *,
        step_progress: tuple[StepProgress, ...] | None = None,
        observations: tuple[PlanObservation, ...] | None = None,
        blockers: tuple[PlanBlocker, ...] | None = None,
    ) -> PlanRun:
        return PlanRun(
            run_id=run.run_id,
            plan_id=run.plan_id,
            goal_id=run.goal_id,
            revision=run.revision + 1,
            created_at=run.created_at,
            updated_at=update.updated_at,
            step_progress=(
                run.step_progress if step_progress is None else step_progress
            ),
            observations=run.observations if observations is None else observations,
            blockers=run.blockers if blockers is None else blockers,
        )
