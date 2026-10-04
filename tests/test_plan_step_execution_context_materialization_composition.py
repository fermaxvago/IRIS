"""WP045 bounded post-recording selected-work Context materialization."""

from __future__ import annotations

import inspect
import json
from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

import pytest

import iris.plan_step_execution_context_materialization_composition as public_api
import iris.plan_step_execution_context_materialization_composition.composer as composer_module
from iris.context import (
    ContextBudget,
    ContextCandidate,
    ContextEngine,
    ContextEvidence,
    ContextSnapshot,
    ContextUncertainty,
    EvidenceSource,
    Freshness,
    Relevance,
    RequestEvidenceSubjectMismatchError,
    ResolutionStatus,
    UncertaintyReason,
)
from iris.execution import CapabilityExecutionInput
from iris.execution.models import ExecutionInput
from iris.memory import MemoryScope, ScopeKind
from iris.orchestrator import HandlerAvailability, HandlingKind
from iris.plan_control import ControlDecision, ControlDecisionKind
from iris.plan_handling import StepHandlingPreparationStatus
from iris.plan_runs import PlanRun, StepProgressState
from iris.plan_step_execution_context_materialization_composition import (
    PlanStepExecutionContextMaterializationComposer,
    PlanStepExecutionContextMaterializationCompositionError,
    PlanStepExecutionContextMaterializationCompositionInvariantError,
    PlanStepExecutionContextMaterializationCompositionResult,
)
from iris.plan_step_execution_work_subject_materialization_composition import (
    PlanStepExecutionWorkSubjectMaterializationComposer,
    PlanStepExecutionWorkSubjectMaterializationCompositionResult,
)
from iris.planning import Plan
from iris.work_identity import (
    PlanStepWorkReference,
    RequestWorkReference,
    WorkOrigin,
    WorkSubject,
    WorkSubjectKind,
    work_subject_from_plan_step,
)
from tests.test_plan_step_execution_evidence_assessment_composition import (
    BUDGET,
    CAPABILITY_AVAILABLE,
    CONTEXT_CREATED,
    capability_input,
    unsafe_clone,
)
from tests.test_plan_step_execution_work_subject_materialization_composition import (
    RecordingWP043,
    canonical_wp043,
    compose_from_wp043,
    no_advancement_wp043,
    wp043_for_kind,
)

POST_RECORDING_CREATED = datetime(2026, 10, 3, 0, 3, 30, tzinfo=UTC)
POST_RECORDING_BUDGET = ContextBudget(3)
GLOBAL = MemoryScope(ScopeKind.GLOBAL)


def candidate(
    candidate_id: str,
    value: str,
    *,
    key: str,
    relevance: Relevance = Relevance.NORMAL,
    source: EvidenceSource = EvidenceSource.CALLER,
    reference: str | None = None,
) -> ContextCandidate:
    return ContextCandidate(
        candidate_id=candidate_id,
        kind="task",
        key=key,
        value=value,
        evidence=ContextEvidence(source, reference or candidate_id),
        scope=GLOBAL,
        relevance=relevance,
        freshness=Freshness.CURRENT,
    )


class RecordingWP044(PlanStepExecutionWorkSubjectMaterializationComposer):
    def __init__(
        self,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__(handling_preparation_composer=RecordingWP043())
        self.forced = forced
        self.error = error
        self.calls: list[tuple[object, ...]] = []

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
    ) -> PlanStepExecutionWorkSubjectMaterializationCompositionResult:
        self.calls.append(
            (
                plan,
                run,
                step_id,
                candidates,
                budget,
                uncertainties,
                created_at,
                availability,
                execution_input,
            )
        )
        if self.error is not None:
            raise self.error
        return cast(
            PlanStepExecutionWorkSubjectMaterializationCompositionResult,
            self.forced,
        )


class RecordingContextEngine(ContextEngine):
    def __init__(
        self,
        *,
        forced: object | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__()
        self.forced = forced
        self.error = error
        self.calls: list[
            tuple[
                WorkSubject | None,
                str | None,
                tuple[ContextCandidate, ...],
                ContextBudget,
                tuple[ContextUncertainty, ...],
                datetime | None,
            ]
        ] = []
        self.results: list[ContextSnapshot] = []

    def build(
        self,
        *,
        subject: WorkSubject | None = None,
        request_id: str | None = None,
        candidates: tuple[ContextCandidate, ...],
        budget: ContextBudget,
        uncertainties: tuple[ContextUncertainty, ...] = (),
        created_at: datetime | None = None,
    ) -> ContextSnapshot:
        self.calls.append(
            (subject, request_id, candidates, budget, uncertainties, created_at)
        )
        if self.error is not None:
            raise self.error
        if self.forced is None:
            result = super().build(
                subject=subject,
                request_id=request_id,
                candidates=candidates,
                budget=budget,
                uncertainties=uncertainties,
                created_at=created_at,
            )
        else:
            result = cast(ContextSnapshot, self.forced)
        self.results.append(result)
        return result


def canonical_wp044(
    *,
    selected_handling: HandlingKind | None = HandlingKind.CAPABILITY,
) -> tuple[
    Plan,
    PlanRun,
    PlanStepExecutionWorkSubjectMaterializationCompositionResult,
]:
    plan, run, wp043 = canonical_wp043(selected_handling=selected_handling)
    result, _, _ = compose_from_wp043(plan, run, wp043)
    assert result.post_recording_work_subject is not None
    return plan, run, result


def no_subject_wp044() -> tuple[
    Plan,
    PlanRun,
    PlanStepExecutionWorkSubjectMaterializationCompositionResult,
]:
    plan, run, wp043 = no_advancement_wp043()
    result, _, _ = compose_from_wp043(plan, run, wp043)
    assert result.post_recording_work_subject is None
    return plan, run, result


def compose_from_wp044(
    plan: Plan,
    run: PlanRun,
    delegated: object,
    *,
    engine: RecordingContextEngine | None = None,
    inherited_candidates: tuple[ContextCandidate, ...] = (),
    inherited_budget: ContextBudget = BUDGET,
    inherited_uncertainties: tuple[ContextUncertainty, ...] = (),
    inherited_created_at: datetime = CONTEXT_CREATED,
    post_candidates: tuple[ContextCandidate, ...] = (),
    post_budget: ContextBudget = POST_RECORDING_BUDGET,
    post_uncertainties: tuple[ContextUncertainty, ...] = (),
    post_created_at: datetime = POST_RECORDING_CREATED,
    execution_input: CapabilityExecutionInput | None = None,
) -> tuple[
    PlanStepExecutionContextMaterializationCompositionResult,
    RecordingWP044,
    RecordingContextEngine,
]:
    wp044 = RecordingWP044(forced=delegated)
    actual_engine = RecordingContextEngine() if engine is None else engine
    supplied_input = capability_input() if execution_input is None else execution_input
    result = PlanStepExecutionContextMaterializationComposer(
        work_subject_materialization_composer=wp044,
        context_engine=actual_engine,
    ).compose(
        plan,
        run,
        "a",
        candidates=inherited_candidates,
        budget=inherited_budget,
        uncertainties=inherited_uncertainties,
        created_at=inherited_created_at,
        availability=CAPABILITY_AVAILABLE,
        execution_input=supplied_input,
        post_recording_candidates=post_candidates,
        post_recording_budget=post_budget,
        post_recording_uncertainties=post_uncertainties,
        post_recording_created_at=post_created_at,
    )
    return result, wp044, actual_engine


def test_public_api_constructor_signature_and_exact_exports() -> None:
    assert set(public_api.__all__) == {
        "PlanStepExecutionContextMaterializationComposer",
        "PlanStepExecutionContextMaterializationCompositionResult",
        "PlanStepExecutionContextMaterializationCompositionError",
        "PlanStepExecutionContextMaterializationCompositionInvariantError",
    }
    assert issubclass(
        PlanStepExecutionContextMaterializationCompositionInvariantError,
        PlanStepExecutionContextMaterializationCompositionError,
    )
    signature = inspect.signature(
        PlanStepExecutionContextMaterializationComposer.compose
    )
    assert tuple(signature.parameters) == (
        "self",
        "plan",
        "run",
        "step_id",
        "candidates",
        "budget",
        "uncertainties",
        "created_at",
        "availability",
        "execution_input",
        "post_recording_candidates",
        "post_recording_budget",
        "post_recording_uncertainties",
        "post_recording_created_at",
    )
    with pytest.raises(TypeError, match="work_subject_materialization_composer"):
        PlanStepExecutionContextMaterializationComposer()  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="work_subject_materialization_composer"):
        PlanStepExecutionContextMaterializationComposer(
            work_subject_materialization_composer=cast(Any, object())
        )
    with pytest.raises(TypeError, match="context_engine"):
        PlanStepExecutionContextMaterializationComposer(
            work_subject_materialization_composer=RecordingWP044(),
            context_engine=cast(Any, object()),
        )
    assert PlanStepExecutionContextMaterializationComposer(
        work_subject_materialization_composer=RecordingWP044()
    )


@pytest.mark.parametrize(
    ("position", "invalid"),
    [
        (0, object()),
        (1, object()),
        (2, 7),
        (3, []),
        (3, (object(),)),
        (4, object()),
        (5, []),
        (5, (object(),)),
        (6, object()),
        (7, object()),
        (8, []),
        (8, (object(),)),
        (9, object()),
        (10, []),
        (10, (object(),)),
        (11, object()),
    ],
)
def test_invalid_inputs_fail_before_wp044(position: int, invalid: object) -> None:
    plan, run, delegated = no_subject_wp044()
    wp044 = RecordingWP044(forced=delegated)
    values: list[object] = [
        plan,
        run,
        "a",
        (),
        BUDGET,
        (),
        CONTEXT_CREATED,
        CAPABILITY_AVAILABLE,
        (),
        POST_RECORDING_BUDGET,
        (),
        POST_RECORDING_CREATED,
    ]
    values[position] = invalid
    with pytest.raises(TypeError):
        PlanStepExecutionContextMaterializationComposer(
            work_subject_materialization_composer=wp044
        ).compose(
            cast(Plan, values[0]),
            cast(PlanRun, values[1]),
            cast(str, values[2]),
            candidates=cast(tuple[ContextCandidate, ...], values[3]),
            budget=cast(ContextBudget, values[4]),
            uncertainties=cast(tuple[ContextUncertainty, ...], values[5]),
            created_at=cast(datetime, values[6]),
            availability=cast(HandlerAvailability, values[7]),
            post_recording_candidates=cast(tuple[ContextCandidate, ...], values[8]),
            post_recording_budget=cast(ContextBudget, values[9]),
            post_recording_uncertainties=cast(
                tuple[ContextUncertainty, ...], values[10]
            ),
            post_recording_created_at=cast(datetime, values[11]),
        )
    assert wp044.calls == []


def test_step_b_and_step_c_inputs_remain_exact_and_separate() -> None:
    plan, run, delegated = canonical_wp044()
    inherited_candidate = candidate("step-b", "B", key="step_b")
    post_candidate = candidate("step-c", "C", key="step_c")
    inherited_uncertainty = ContextUncertainty(
        "task", "missing_b", GLOBAL, UncertaintyReason.MISSING
    )
    post_uncertainty = ContextUncertainty(
        "task", "missing_c", GLOBAL, UncertaintyReason.MISSING
    )
    inherited_budget = ContextBudget(1)
    post_budget = ContextBudget(2)
    operation_input = capability_input()
    result, wp044, engine = compose_from_wp044(
        plan,
        run,
        delegated,
        inherited_candidates=(inherited_candidate,),
        inherited_budget=inherited_budget,
        inherited_uncertainties=(inherited_uncertainty,),
        inherited_created_at=CONTEXT_CREATED,
        post_candidates=(post_candidate,),
        post_budget=post_budget,
        post_uncertainties=(post_uncertainty,),
        post_created_at=POST_RECORDING_CREATED,
        execution_input=operation_input,
    )
    assert wp044.calls == [
        (
            plan,
            run,
            "a",
            (inherited_candidate,),
            inherited_budget,
            (inherited_uncertainty,),
            CONTEXT_CREATED,
            CAPABILITY_AVAILABLE,
            operation_input,
        )
    ]
    subject = delegated.post_recording_work_subject
    assert engine.calls == [
        (
            subject,
            None,
            (post_candidate,),
            post_budget,
            (post_uncertainty,),
            POST_RECORDING_CREATED,
        )
    ]
    assert result.post_recording_context_snapshot is engine.results[0]


def test_no_post_recording_subject_skips_context_and_preserves_wp044() -> None:
    plan, run, delegated = no_subject_wp044()
    result, wp044, engine = compose_from_wp044(
        plan,
        run,
        delegated,
        post_candidates=(candidate("unused", "unused", key="unused"),),
    )
    assert len(wp044.calls) == 1
    assert engine.calls == []
    assert result.post_recording_context_snapshot is None
    for item in fields(delegated):
        assert getattr(result, item.name) is getattr(delegated, item.name)


def test_nonselecting_malformed_fresh_control_is_rejected_without_context() -> None:
    plan, run, wp043 = wp043_for_kind(ControlDecisionKind.ACTIVE_WORK_PENDING)
    delegated, _, _ = compose_from_wp043(plan, run, wp043)
    advancement = delegated.post_recording_advancement_result
    assert advancement is not None
    assert delegated.post_recording_work_subject is None
    malformed = unsafe_clone(
        delegated,
        post_recording_advancement_result=unsafe_clone(
            advancement,
            control_decision=unsafe_clone(
                advancement.control_decision,
                observed_revision=advancement.control_decision.observed_revision + 1,
            ),
        ),
    )
    engine = RecordingContextEngine()
    with pytest.raises(
        PlanStepExecutionContextMaterializationCompositionInvariantError
    ):
        compose_from_wp044(plan, run, malformed, engine=engine)
    assert engine.calls == []


def test_subject_path_invokes_context_once_with_exact_subject_and_empty_snapshot() -> (
    None
):
    plan, run, delegated = canonical_wp044()
    result, wp044, engine = compose_from_wp044(
        plan,
        run,
        delegated,
        post_budget=ContextBudget(0),
    )
    subject = delegated.post_recording_work_subject
    assert subject is not None
    assert len(wp044.calls) == len(engine.calls) == 1
    assert engine.calls[0][0] is subject
    snapshot = result.post_recording_context_snapshot
    assert snapshot is engine.results[0]
    assert snapshot.subject is subject
    assert snapshot.items == ()
    assert snapshot.status is ResolutionStatus.RESOLVED


@pytest.mark.parametrize(
    ("status", "candidates", "uncertainties"),
    [
        (
            ResolutionStatus.RESOLVED,
            (candidate("resolved", "value", key="resolved"),),
            (),
        ),
        (
            ResolutionStatus.PARTIAL,
            (),
            (ContextUncertainty("task", "missing", GLOBAL, UncertaintyReason.MISSING),),
        ),
        (
            ResolutionStatus.AMBIGUOUS,
            (
                candidate("option-a", "a", key="option_a"),
                candidate("option-b", "b", key="option_b"),
            ),
            (
                ContextUncertainty(
                    "task",
                    "choice",
                    GLOBAL,
                    UncertaintyReason.MULTIPLE_PLAUSIBLE,
                    ("option-a", "option-b"),
                ),
            ),
        ),
        (
            ResolutionStatus.CONFLICTED,
            (
                candidate("conflict-a", "a", key="same"),
                candidate("conflict-b", "b", key="same"),
            ),
            (),
        ),
    ],
)
def test_all_context_statuses_are_preserved_and_inert(
    status: ResolutionStatus,
    candidates: tuple[ContextCandidate, ...],
    uncertainties: tuple[ContextUncertainty, ...],
) -> None:
    plan, run, delegated = canonical_wp044()
    result, _, engine = compose_from_wp044(
        plan,
        run,
        delegated,
        post_candidates=candidates,
        post_budget=ContextBudget(2),
        post_uncertainties=uncertainties,
    )
    assert len(engine.calls) == 1
    assert result.post_recording_context_snapshot is engine.results[0]
    assert result.post_recording_context_snapshot.status is status


@pytest.mark.parametrize(
    ("handling", "expected_status"),
    [
        (HandlingKind.CAPABILITY, StepHandlingPreparationStatus.PREPARED),
        (None, StepHandlingPreparationStatus.HANDLING_UNSPECIFIED),
        (HandlingKind.SYSTEM, StepHandlingPreparationStatus.INSUFFICIENT_DETAIL),
        (HandlingKind.MEMORY, StepHandlingPreparationStatus.INSUFFICIENT_DETAIL),
        (HandlingKind.INTELLIGENCE, StepHandlingPreparationStatus.INSUFFICIENT_DETAIL),
    ],
)
def test_handling_status_never_gates_context(
    handling: HandlingKind | None,
    expected_status: StepHandlingPreparationStatus,
) -> None:
    plan, run, delegated = canonical_wp044(selected_handling=handling)
    preparation = delegated.post_recording_handling_preparation
    assert preparation is not None and preparation.status is expected_status
    result, _, engine = compose_from_wp044(plan, run, delegated)
    assert len(engine.calls) == 1
    assert result.post_recording_context_snapshot is engine.results[0]


def test_a_b_c_lineage_and_context_artifacts_remain_distinct() -> None:
    plan, run, delegated = canonical_wp044()
    result, _, _ = compose_from_wp044(plan, run, delegated)
    inherited = result.context_snapshot
    post = result.post_recording_context_snapshot
    assert result.assessment.step_id == "a"
    assert inherited is delegated.context_snapshot
    assert inherited is not None and post is not None
    assert isinstance(inherited.subject.reference, PlanStepWorkReference)
    assert isinstance(post.subject.reference, PlanStepWorkReference)
    assert inherited.subject.reference.step_id == "b"
    assert result.post_recording_progress_update is not None
    assert result.post_recording_progress_update.step_id == "b"
    assert post.subject is result.post_recording_work_subject
    assert post.subject.reference.step_id == "c"
    assert post.subject.reference.step_id != result.assessment.step_id
    assert inherited is not post


def test_existing_currentness_authorities_are_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, run, delegated = canonical_wp044()
    control_calls: list[tuple[Plan, PlanRun, ControlDecision]] = []
    preparation_calls: list[tuple[Plan, PlanRun, object]] = []
    canonical_control = composer_module.validate_control_decision_current
    canonical_preparation = composer_module.validate_step_handling_preparation_current

    def control_spy(
        selected_plan: Plan,
        selected_run: PlanRun,
        decision: ControlDecision,
    ) -> None:
        control_calls.append((selected_plan, selected_run, decision))
        canonical_control(selected_plan, selected_run, decision)

    def preparation_spy(
        selected_plan: Plan,
        selected_run: PlanRun,
        preparation: object,
    ) -> None:
        preparation_calls.append((selected_plan, selected_run, preparation))
        canonical_preparation(selected_plan, selected_run, cast(Any, preparation))

    monkeypatch.setattr(
        composer_module, "validate_control_decision_current", control_spy
    )
    monkeypatch.setattr(
        composer_module,
        "validate_step_handling_preparation_current",
        preparation_spy,
    )
    compose_from_wp044(plan, run, delegated)
    advancement = delegated.post_recording_advancement_result
    preparation = delegated.post_recording_handling_preparation
    assert advancement is not None and preparation is not None
    assert control_calls == [
        (plan, advancement.updated_run, advancement.control_decision)
    ]
    assert preparation_calls == [(plan, advancement.updated_run, preparation)]


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_type",
        "source_step",
        "missing_advancement",
        "successor_plan",
        "control_revision",
        "missing_preparation",
        "preparation_step",
        "subject_kind",
        "subject_reference",
        "subject_plan",
        "subject_run",
        "subject_step",
        "subject_origin",
    ],
)
def test_malformed_wp044_outputs_fail_before_context(mutation: str) -> None:
    plan, run, delegated = canonical_wp044()
    malformed: object = delegated
    advancement = delegated.post_recording_advancement_result
    preparation = delegated.post_recording_handling_preparation
    subject = delegated.post_recording_work_subject
    assert advancement is not None and preparation is not None and subject is not None
    if mutation == "wrong_type":
        malformed = object()
    elif mutation == "source_step":
        malformed = unsafe_clone(
            delegated,
            assessment=unsafe_clone(delegated.assessment, step_id="b"),
            transition_decision=unsafe_clone(
                delegated.transition_decision,
                step_id="b",
            ),
        )
    elif mutation == "missing_advancement":
        malformed = unsafe_clone(
            delegated,
            post_recording_advancement_result=None,
        )
    elif mutation == "successor_plan":
        malformed = unsafe_clone(
            delegated,
            post_recording_advancement_result=unsafe_clone(
                advancement,
                updated_run=unsafe_clone(
                    advancement.updated_run,
                    plan_id="foreign-plan",
                ),
            ),
        )
    elif mutation == "control_revision":
        malformed = unsafe_clone(
            delegated,
            post_recording_advancement_result=unsafe_clone(
                advancement,
                control_decision=unsafe_clone(
                    advancement.control_decision,
                    observed_revision=advancement.control_decision.observed_revision
                    + 1,
                ),
            ),
        )
    elif mutation == "missing_preparation":
        malformed = unsafe_clone(
            delegated,
            post_recording_handling_preparation=None,
        )
    elif mutation == "preparation_step":
        malformed = unsafe_clone(
            delegated,
            post_recording_handling_preparation=unsafe_clone(
                preparation,
                step_id="b",
            ),
        )
    else:
        changed_subject: object
        if mutation == "subject_kind":
            changed_subject = unsafe_clone(subject, kind=WorkSubjectKind.REQUEST)
        elif mutation == "subject_reference":
            changed_subject = unsafe_clone(
                subject,
                reference=RequestWorkReference("request-1"),
            )
        elif mutation == "subject_plan":
            changed_subject = unsafe_clone(
                subject,
                reference=PlanStepWorkReference("foreign-plan", run.run_id, "c"),
            )
        elif mutation == "subject_run":
            changed_subject = unsafe_clone(
                subject,
                reference=PlanStepWorkReference(plan.plan_id, "foreign-run", "c"),
            )
        elif mutation == "subject_step":
            changed_subject = unsafe_clone(
                subject,
                reference=PlanStepWorkReference(plan.plan_id, run.run_id, "b"),
            )
        else:
            changed_subject = unsafe_clone(
                subject,
                origin=WorkOrigin("request", "request-1"),
            )
        malformed = unsafe_clone(
            delegated,
            post_recording_work_subject=changed_subject,
        )
    engine = RecordingContextEngine()
    with pytest.raises(
        PlanStepExecutionContextMaterializationCompositionInvariantError
    ):
        compose_from_wp044(plan, run, malformed, engine=engine)
    assert engine.calls == []


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_type",
        "distinct_subject",
        "wrong_subject_id",
        "budget",
        "created_at",
        "status",
    ],
)
def test_malformed_context_outputs_become_wp045_invariants(mutation: str) -> None:
    plan, run, delegated = canonical_wp044()
    subject = delegated.post_recording_work_subject
    advancement = delegated.post_recording_advancement_result
    assert subject is not None and advancement is not None
    canonical = ContextEngine().build(
        subject=subject,
        candidates=(),
        budget=POST_RECORDING_BUDGET,
        created_at=POST_RECORDING_CREATED,
    )
    malformed: object = canonical
    if mutation == "wrong_type":
        malformed = object()
    elif mutation in {"distinct_subject", "wrong_subject_id"}:
        replacement = work_subject_from_plan_step(
            plan,
            advancement.updated_run,
            "c",
        )
        assert replacement == subject and replacement is not subject
        if mutation == "wrong_subject_id":
            replacement = unsafe_clone(replacement, subject_id="wrong-subject")
        malformed = unsafe_clone(canonical, subject=replacement)
    elif mutation == "budget":
        malformed = unsafe_clone(canonical, budget=ContextBudget(99))
    elif mutation == "created_at":
        malformed = unsafe_clone(
            canonical,
            created_at=POST_RECORDING_CREATED + timedelta(seconds=1),
        )
    else:
        malformed = unsafe_clone(canonical, status=cast(Any, "resolved"))
    engine = RecordingContextEngine(forced=malformed)
    with pytest.raises(
        PlanStepExecutionContextMaterializationCompositionInvariantError
    ):
        compose_from_wp044(plan, run, delegated, engine=engine)
    assert len(engine.calls) == 1


def test_post_recording_timestamp_is_forwarded_exactly_and_normalized() -> None:
    plan, run, delegated = canonical_wp044()
    local_time = datetime(
        2026,
        10,
        2,
        18,
        3,
        30,
        tzinfo=timezone(timedelta(hours=-6)),
    )
    result, _, engine = compose_from_wp044(
        plan,
        run,
        delegated,
        post_created_at=local_time,
    )
    assert engine.calls[0][5] is local_time
    assert result.post_recording_context_snapshot is not None
    assert result.post_recording_context_snapshot.created_at == local_time.astimezone(
        UTC
    )


def test_context_cannot_predate_completed_execution_and_equal_time_is_valid() -> None:
    plan, run, delegated = canonical_wp044()
    start = delegated.execution_start_result
    assert start is not None
    completed = start.execution_result.completed_at
    engine = RecordingContextEngine()
    with pytest.raises(
        PlanStepExecutionContextMaterializationCompositionInvariantError,
        match="cannot predate",
    ):
        compose_from_wp044(
            plan,
            run,
            delegated,
            engine=engine,
            post_created_at=completed - timedelta(microseconds=1),
        )
    assert engine.calls == []
    result, _, equal_engine = compose_from_wp044(
        plan,
        run,
        delegated,
        post_created_at=completed,
    )
    assert result.post_recording_context_snapshot is equal_engine.results[0]


def test_invalid_context_timestamp_remains_a_canonical_input_error() -> None:
    plan, run, delegated = canonical_wp044()
    engine = RecordingContextEngine()
    with pytest.raises(ValueError, match="timezone-aware"):
        compose_from_wp044(
            plan,
            run,
            delegated,
            engine=engine,
            post_created_at=datetime(2026, 10, 3),
        )
    assert engine.calls == []


def test_upstream_and_context_errors_propagate_unchanged() -> None:
    plan, run, delegated = canonical_wp044()
    upstream_failure = RuntimeError("wp044 failed")
    wp044 = RecordingWP044(error=upstream_failure)
    engine = RecordingContextEngine()
    with pytest.raises(RuntimeError) as upstream_caught:
        PlanStepExecutionContextMaterializationComposer(
            work_subject_materialization_composer=wp044,
            context_engine=engine,
        ).compose(
            plan,
            run,
            "a",
            candidates=(),
            budget=BUDGET,
            created_at=CONTEXT_CREATED,
            availability=CAPABILITY_AVAILABLE,
            post_recording_candidates=(),
            post_recording_budget=POST_RECORDING_BUDGET,
            post_recording_created_at=POST_RECORDING_CREATED,
        )
    assert upstream_caught.value is upstream_failure
    assert engine.calls == []

    context_failure = RequestEvidenceSubjectMismatchError("context failed")
    failing_engine = RecordingContextEngine(error=context_failure)
    with pytest.raises(RequestEvidenceSubjectMismatchError) as context_caught:
        compose_from_wp044(
            plan,
            run,
            delegated,
            engine=failing_engine,
        )
    assert context_caught.value is context_failure
    assert len(failing_engine.calls) == 1


def test_real_context_validation_error_is_not_converted_to_none() -> None:
    plan, run, delegated = canonical_wp044()
    request_candidate = candidate(
        "request-evidence",
        "value",
        key="request_value",
        source=EvidenceSource.REQUEST,
        reference="request-root",
    )
    with pytest.raises(RequestEvidenceSubjectMismatchError):
        compose_from_wp044(
            plan,
            run,
            delegated,
            post_candidates=(request_candidate,),
        )


def test_result_immutability_serialization_and_exact_artifact_identity() -> None:
    plan, run, delegated = canonical_wp044()
    result, _, engine = compose_from_wp044(plan, run, delegated)
    snapshot = result.post_recording_context_snapshot
    assert snapshot is engine.results[0]
    for item in fields(delegated):
        assert getattr(result, item.name) is getattr(delegated, item.name)
    with pytest.raises(FrozenInstanceError):
        result.post_recording_context_snapshot = None  # type: ignore[misc]
    assert json.loads(json.dumps(result.to_data())) == result.to_data()
    assert result.to_data()["post_recording_context_snapshot"] == (
        snapshot.to_data()  # type: ignore[union-attr]
    )


def test_result_rejects_optional_shape_foreign_owner_and_snapshot_reuse() -> None:
    plan, run, delegated = canonical_wp044()
    valid, _, _ = compose_from_wp044(plan, run, delegated)
    snapshot = valid.post_recording_context_snapshot
    assert snapshot is not None
    with pytest.raises(
        PlanStepExecutionContextMaterializationCompositionInvariantError
    ):
        unsafe_clone(valid, post_recording_context_snapshot=None).__post_init__()

    _, _, absent = no_subject_wp044()
    with pytest.raises(
        PlanStepExecutionContextMaterializationCompositionInvariantError
    ):
        PlanStepExecutionContextMaterializationComposer._result(absent, snapshot)

    inherited = delegated.context_snapshot
    assert inherited is not None
    with pytest.raises(
        PlanStepExecutionContextMaterializationCompositionInvariantError,
        match="distinct artifacts",
    ):
        PlanStepExecutionContextMaterializationComposer._result(delegated, inherited)


def test_repeated_invocation_has_no_deduplication_or_identity_claim() -> None:
    plan, run, delegated = canonical_wp044()
    wp044 = RecordingWP044(forced=delegated)
    engine = RecordingContextEngine()
    composer = PlanStepExecutionContextMaterializationComposer(
        work_subject_materialization_composer=wp044,
        context_engine=engine,
    )
    kwargs = {
        "candidates": (),
        "budget": BUDGET,
        "created_at": CONTEXT_CREATED,
        "availability": CAPABILITY_AVAILABLE,
        "post_recording_candidates": (),
        "post_recording_budget": POST_RECORDING_BUDGET,
        "post_recording_created_at": POST_RECORDING_CREATED,
    }
    first = composer.compose(plan, run, "a", **kwargs)  # type: ignore[arg-type]
    second = composer.compose(plan, run, "a", **kwargs)  # type: ignore[arg-type]
    first_snapshot = first.post_recording_context_snapshot
    second_snapshot = second.post_recording_context_snapshot
    assert len(wp044.calls) == len(engine.calls) == 2
    assert first_snapshot is engine.results[0]
    assert second_snapshot is engine.results[1]
    assert first_snapshot is not second_snapshot
    assert first_snapshot.snapshot_id != second_snapshot.snapshot_id  # type: ignore[union-attr]
    assert first_snapshot.subject is second_snapshot.subject  # type: ignore[union-attr]


def test_selected_step_c_remains_not_started_and_context_is_inert() -> None:
    plan, run, delegated = canonical_wp044()
    before = (plan.to_data(), run.to_data())
    result, _, _ = compose_from_wp044(plan, run, delegated)
    advancement = result.post_recording_advancement_result
    snapshot = result.post_recording_context_snapshot
    assert advancement is not None and snapshot is not None
    selected = advancement.control_decision.selected_step_id
    progress = next(
        item
        for item in advancement.updated_run.step_progress
        if item.step_id == selected
    )
    assert selected == "c"
    assert progress.state is StepProgressState.NOT_STARTED
    assert snapshot.subject is result.post_recording_work_subject
    assert (plan.to_data(), run.to_data()) == before


def test_wp045_has_no_forbidden_authority_or_continuation_dependencies() -> None:
    source = (
        Path(__file__).parents[1]
        / "iris"
        / "plan_step_execution_context_materialization_composition"
        / "composer.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "PlanStepContextMaterializer",
        "MemoryContextSource",
        "MemoryService",
        "MemoryQuery",
        "vector",
        "retrieval",
        "candidate_discovery",
        "Orchestrator",
        "OrchestrationDecision",
        "ExecutionRequest",
        "PlanStepExecutionBinder",
        "PlanStepExecutionStartCoordinator",
        "ExecutionCoordinator",
        "PlanRunReducer",
        "PlanRunController",
        "PlanRunProgressAdvancer",
    ):
        assert forbidden not in source
