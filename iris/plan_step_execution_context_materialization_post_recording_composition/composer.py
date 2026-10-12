"""Compose exact WP056 successor identity with canonical WP016 Context."""

from __future__ import annotations

from dataclasses import fields
from datetime import datetime

from iris.context import (
    ContextBudget,
    ContextCandidate,
    ContextEngine,
    ContextSnapshot,
    ContextUncertainty,
)
from iris.execution import ExecutionResult
from iris.execution.models import ExecutionInput
from iris.memory.models import utc_time
from iris.orchestrator import HandlerAvailability
from iris.plan_runs import PlanRun
from iris.plan_step_execution_context_materialization_post_recording_composition.errors import (
    PlanStepExecutionContextMaterializationPostRecordingCompositionInvariantError,
)
from iris.plan_step_execution_context_materialization_post_recording_composition.models import (
    PlanStepExecutionContextMaterializationPostRecordingCompositionResult,
    validate_successor_snapshot,
)
from iris.plan_step_execution_work_subject_materialization_post_recording_composition import (
    PlanStepExecutionWorkSubjectMaterializationPostRecordingComposer,
    PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionResult,
)
from iris.planning import Plan
from iris.work_identity import WorkSubject


class PlanStepExecutionContextMaterializationPostRecordingComposer:
    """Append at most one exact successor ContextSnapshot, then stop."""

    def __init__(
        self,
        *,
        work_subject_materialization_composer: (
            PlanStepExecutionWorkSubjectMaterializationPostRecordingComposer
        ),
        context_engine: ContextEngine | None = None,
    ) -> None:
        if not isinstance(
            work_subject_materialization_composer,
            PlanStepExecutionWorkSubjectMaterializationPostRecordingComposer,
        ):
            raise TypeError(
                "work_subject_materialization_composer must be a "
                "PlanStepExecutionWorkSubjectMaterializationPostRecordingComposer"
            )
        if context_engine is not None and not isinstance(context_engine, ContextEngine):
            raise TypeError("context_engine must be a ContextEngine")
        self._work_subject_materialization_composer = (
            work_subject_materialization_composer
        )
        self._context_engine = (
            ContextEngine() if context_engine is None else context_engine
        )

    def compose(
        self,
        plan: Plan,
        run: PlanRun,
        step_id: str,
        *,
        candidates: tuple[ContextCandidate, ...],
        budget: ContextBudget,
        uncertainties: tuple[ContextUncertainty, ...] = (),
        created_at: datetime,
        availability: HandlerAvailability,
        execution_input: ExecutionInput | None = None,
        post_recording_candidates: tuple[ContextCandidate, ...],
        post_recording_budget: ContextBudget,
        post_recording_uncertainties: tuple[ContextUncertainty, ...] = (),
        post_recording_created_at: datetime,
        post_recording_availability: HandlerAvailability,
        post_recording_execution_input: ExecutionInput | None = None,
        successor_context_candidates: tuple[ContextCandidate, ...],
        successor_context_budget: ContextBudget,
        successor_context_uncertainties: tuple[ContextUncertainty, ...] = (),
        successor_context_created_at: datetime,
    ) -> PlanStepExecutionContextMaterializationPostRecordingCompositionResult:
        """Delegate once, contextualize only exact selected successor, then stop."""

        upstream = self._work_subject_materialization_composer.compose(
            plan,
            run,
            step_id,
            candidates=candidates,
            budget=budget,
            uncertainties=uncertainties,
            created_at=created_at,
            availability=availability,
            execution_input=execution_input,
            post_recording_candidates=post_recording_candidates,
            post_recording_budget=post_recording_budget,
            post_recording_uncertainties=post_recording_uncertainties,
            post_recording_created_at=post_recording_created_at,
            post_recording_availability=post_recording_availability,
            post_recording_execution_input=post_recording_execution_input,
        )
        self._validate_upstream(
            plan,
            run,
            step_id,
            post_recording_budget,
            post_recording_created_at,
            post_recording_execution_input,
            upstream,
        )
        subject = upstream.post_recording_execution_work_subject
        if subject is None:
            return self._result(upstream, None)

        self._validate_successor_inputs(
            successor_context_candidates,
            successor_context_budget,
            successor_context_uncertainties,
            successor_context_created_at,
        )
        self._validate_context_causality(upstream, successor_context_created_at)
        snapshot = self._context_engine.build(
            subject=subject,
            candidates=successor_context_candidates,
            budget=successor_context_budget,
            uncertainties=successor_context_uncertainties,
            created_at=successor_context_created_at,
        )
        self._validate_snapshot(
            subject,
            successor_context_candidates,
            successor_context_budget,
            successor_context_uncertainties,
            successor_context_created_at,
            snapshot,
        )
        return self._result(upstream, snapshot)

    @staticmethod
    def _validate_upstream(
        plan: Plan,
        source_run: PlanRun,
        processed_step_id: str,
        post_recording_budget: ContextBudget,
        post_recording_created_at: datetime,
        post_recording_execution_input: ExecutionInput | None,
        result: PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionResult,
    ) -> None:
        invariant = PlanStepExecutionContextMaterializationPostRecordingCompositionInvariantError
        if not isinstance(
            result,
            PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionResult,
        ):
            raise invariant("WP056 must return its canonical composition result")
        try:
            PlanStepExecutionWorkSubjectMaterializationPostRecordingComposer._validate_upstream(
                plan,
                source_run,
                processed_step_id,
                post_recording_budget,
                post_recording_created_at,
                post_recording_execution_input,
                result,
            )
            PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionResult.__post_init__(
                result
            )
        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise invariant("WP056 returned contradictory cumulative lineage") from exc

    @staticmethod
    def _validate_successor_inputs(
        candidates: tuple[ContextCandidate, ...],
        budget: ContextBudget,
        uncertainties: tuple[ContextUncertainty, ...],
        created_at: datetime,
    ) -> None:
        if not isinstance(candidates, tuple) or any(
            not isinstance(candidate, ContextCandidate) for candidate in candidates
        ):
            raise TypeError(
                "successor_context_candidates must be a tuple of ContextCandidate"
            )
        if not isinstance(budget, ContextBudget):
            raise TypeError("successor_context_budget must be a ContextBudget")
        if not isinstance(uncertainties, tuple) or any(
            not isinstance(uncertainty, ContextUncertainty)
            for uncertainty in uncertainties
        ):
            raise TypeError(
                "successor_context_uncertainties must be a tuple of ContextUncertainty"
            )
        utc_time(created_at, "successor_context_created_at")

    @staticmethod
    def _validate_context_causality(
        result: PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionResult,
        created_at: datetime,
    ) -> None:
        invariant = PlanStepExecutionContextMaterializationPostRecordingCompositionInvariantError
        start = result.post_recording_execution_start_result
        advancement = result.post_recording_execution_advancement_result
        if (
            start is None
            or not isinstance(start.execution_result, ExecutionResult)
            or advancement is None
        ):
            raise invariant(
                "successor Context requires exact Step C execution and advancement"
            )
        instant = utc_time(created_at, "successor_context_created_at")
        if (
            instant < start.execution_result.completed_at
            or instant < advancement.updated_run.updated_at
        ):
            raise invariant(
                "successor Context cannot predate Step C execution or successor Run"
            )

    @staticmethod
    def _validate_snapshot(
        subject: WorkSubject,
        candidates: tuple[ContextCandidate, ...],
        budget: ContextBudget,
        uncertainties: tuple[ContextUncertainty, ...],
        created_at: datetime,
        snapshot: ContextSnapshot,
    ) -> None:
        invariant = PlanStepExecutionContextMaterializationPostRecordingCompositionInvariantError
        validate_successor_snapshot(snapshot, subject)
        if snapshot.budget != budget:
            raise invariant(
                "WP016 snapshot budget contradicts successor_context_budget"
            )
        if snapshot.created_at != utc_time(created_at, "successor_context_created_at"):
            raise invariant(
                "WP016 snapshot time contradicts successor_context_created_at"
            )
        by_id = {candidate.candidate_id: candidate for candidate in candidates}
        for item in snapshot.items:
            candidate = by_id.get(item.candidate_id)
            if (
                candidate is None
                or not candidate.eligible
                or item != candidate.to_item()
                or (
                    item.observed_at is not None
                    and item.observed_at > snapshot.created_at
                )
            ):
                raise invariant(
                    "WP016 snapshot selected foreign or ineligible evidence"
                )
        if any(
            candidate_id not in by_id for candidate_id in snapshot.budget_excluded_ids
        ):
            raise invariant("WP016 snapshot excludes foreign candidate IDs")
        if any(
            item.candidate_id in snapshot.budget_excluded_ids for item in snapshot.items
        ):
            raise invariant("WP016 snapshot both selected and excluded evidence")
        if snapshot.uncertainties[: len(uncertainties)] != uncertainties:
            raise invariant("WP016 snapshot omitted supplied uncertainties")
        for uncertainty in snapshot.uncertainties:
            if any(
                candidate_id not in by_id for candidate_id in uncertainty.candidate_ids
            ):
                raise invariant(
                    "WP016 snapshot uncertainty references foreign evidence"
                )
        for conflict in snapshot.conflicts:
            for candidate_id, evidence in zip(
                conflict.candidate_ids, conflict.evidence, strict=True
            ):
                candidate = by_id.get(candidate_id)
                if (
                    candidate is None
                    or not candidate.eligible
                    or (candidate.kind, candidate.key, candidate.scope)
                    != (conflict.kind, conflict.key, conflict.scope)
                    or candidate.evidence != evidence
                ):
                    raise invariant(
                        "WP016 snapshot conflict references foreign evidence"
                    )

    @staticmethod
    def _result(
        upstream: PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionResult,
        snapshot: ContextSnapshot | None,
    ) -> PlanStepExecutionContextMaterializationPostRecordingCompositionResult:
        return PlanStepExecutionContextMaterializationPostRecordingCompositionResult(
            **{
                field.name: getattr(upstream, field.name)
                for field in fields(
                    PlanStepExecutionWorkSubjectMaterializationPostRecordingCompositionResult
                )
            },
            post_recording_execution_context_snapshot=snapshot,
        )
