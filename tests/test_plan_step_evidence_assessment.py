"""WP027 complete PlanStep evidence-basis assessment composition."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from iris.execution import ExecutionFailure, ExecutionResult, ExecutionStatus
from iris.execution_observation import ExecutionObservationAdapter
from iris.orchestrator import OrchestrationReason, OrchestrationTarget
from iris.outcome_assessment import (
    ConservativeStepOutcomeEvaluator,
    OutcomeEvaluationError,
    StepOutcomeAssessment,
    StepOutcomeStatus,
)
from iris.plan_runs import (
    AddBlockerUpdate,
    PlanBlocker,
    PlanObservation,
    PlanRun,
    PlanRunFactory,
    PlanRunIdentityError,
    PlanRunReducer,
    RecordObservationUpdate,
    RunProvenance,
    StepProgressState,
    StepProgressUpdate,
    UnknownPlanStepError,
)
from iris.plan_step_evidence_assessment import (
    PlanStepEvidenceAssessmentInvariantError,
    PlanStepEvidenceAssessmentLineageError,
    PlanStepEvidenceAssessor,
)
from iris.plan_step_execution_result_recording import (
    PlanStepExecutionResultRecorder,
)
from iris.plan_step_execution_start import PlanStepExecutionStartResult
from iris.planning import Plan, PlanStep
from iris.step_progress_transition import (
    StepProgressTransitionDecider,
    StepProgressTransitionReason,
)
from iris.work_identity import PlanStepWorkReference, WorkSubject, WorkSubjectKind

CREATED = datetime(2026, 9, 30, 19, tzinfo=UTC)
OBSERVED_1 = CREATED + timedelta(seconds=1)
OBSERVED_2 = CREATED + timedelta(seconds=2)
OBSERVED_3 = CREATED + timedelta(seconds=3)
ASSESSED = CREATED + timedelta(seconds=4)


def make_plan(*, plan_id: str = "plan-1") -> Plan:
    return Plan(
        plan_id,
        "goal-1",
        (),
        (
            PlanStep("step-a", "Perform A", "A exists"),
            PlanStep("step-b", "Perform B", "B exists", ("step-a",)),
        ),
    )


def make_run(plan: Plan, *, run_id: str = "run-1") -> PlanRun:
    return PlanRunFactory(
        clock=lambda: CREATED,
        run_id_factory=lambda: run_id,
    ).create(plan)


def make_observation(
    run: PlanRun,
    *,
    observation_id: str,
    step_id: str | None = "step-a",
    observed_at: datetime = OBSERVED_1,
    source: str = "execution",
    kind: str = "execution_result",
) -> PlanObservation:
    return PlanObservation(
        observation_id=observation_id,
        run_id=run.run_id,
        step_id=step_id,
        source=source,
        source_reference=f"source-{observation_id}",
        observed_at=observed_at,
        kind=kind,
        data={"raw": observation_id},
    )


def record(plan: Plan, run: PlanRun, observation: PlanObservation) -> PlanRun:
    return PlanRunReducer().apply(
        plan,
        run,
        RecordObservationUpdate(
            update_id=f"record-{observation.observation_id}",
            run_id=run.run_id,
            expected_revision=run.revision,
            updated_at=max(run.updated_at, observation.observed_at),
            provenance=RunProvenance("test", observation.observation_id),
            observation=observation,
        ),
    )


def assessment_for(
    plan: Plan,
    run: PlanRun,
    step: PlanStep,
    evidence: tuple[PlanObservation, ...],
    *,
    assessment_id: str = "assessment-1",
    status: StepOutcomeStatus | None = None,
    assessed_at: datetime = ASSESSED,
    evidence_ids: tuple[str, ...] | None = None,
) -> StepOutcomeAssessment:
    selected_ids = (
        tuple(item.observation_id for item in evidence)
        if evidence_ids is None
        else evidence_ids
    )
    selected_status = status
    if selected_status is None:
        selected_status = (
            StepOutcomeStatus.INDETERMINATE
            if selected_ids
            else StepOutcomeStatus.INSUFFICIENT_EVIDENCE
        )
    return StepOutcomeAssessment(
        assessment_id=assessment_id,
        plan_id=plan.plan_id,
        run_id=run.run_id,
        run_revision=run.revision,
        step_id=step.step_id,
        status=selected_status,
        evidence_ids=selected_ids,
        evaluator_reference="test.evaluator.v1",
        assessed_at=assessed_at,
        details={"evidence_count": len(selected_ids)},
    )


AssessmentFactory = Callable[
    [Plan, PlanRun, PlanStep, tuple[PlanObservation, ...]],
    StepOutcomeAssessment,
]


@dataclass
class RecordingEvaluator:
    factory: AssessmentFactory = assessment_for
    error: Exception | None = None
    calls: list[tuple[Plan, PlanRun, PlanStep, tuple[PlanObservation, ...]]] = field(
        default_factory=list
    )

    def evaluate(
        self,
        plan: Plan,
        run: PlanRun,
        step: PlanStep,
        evidence: tuple[PlanObservation, ...],
    ) -> StepOutcomeAssessment:
        self.calls.append((plan, run, step, evidence))
        if self.error is not None:
            raise self.error
        return self.factory(plan, run, step, evidence)


def test_public_api_is_importable() -> None:
    assert PlanStepEvidenceAssessor.__name__ == "PlanStepEvidenceAssessor"


def test_constructor_accepts_protocol_and_rejects_non_evaluator() -> None:
    evaluator = RecordingEvaluator()
    assert PlanStepEvidenceAssessor(evaluator).__class__ is PlanStepEvidenceAssessor
    with pytest.raises(TypeError, match="StepOutcomeEvaluator"):
        PlanStepEvidenceAssessor(cast(Any, object()))


@pytest.mark.parametrize(
    ("position", "bad_value", "message"),
    [
        (0, object(), "plan must be a Plan"),
        (1, object(), "run must be a PlanRun"),
        (2, object(), "step_id must be a string"),
    ],
)
def test_assess_rejects_wrong_top_level_types(
    position: int,
    bad_value: object,
    message: str,
) -> None:
    plan = make_plan()
    values: list[object] = [plan, make_run(plan), "step-a"]
    values[position] = bad_value
    with pytest.raises(TypeError, match=message):
        PlanStepEvidenceAssessor().assess(*cast(Any, values))


@pytest.mark.parametrize("step_id", ["", " step-a", "step-a "])
def test_blank_or_padded_step_identity_is_rejected(step_id: str) -> None:
    plan = make_plan()
    evaluator = RecordingEvaluator()
    with pytest.raises(PlanStepEvidenceAssessmentLineageError):
        PlanStepEvidenceAssessor(evaluator).assess(plan, make_run(plan), step_id)
    assert evaluator.calls == []


def test_missing_step_is_rejected_before_evaluator_invocation() -> None:
    plan = make_plan()
    evaluator = RecordingEvaluator()
    with pytest.raises(UnknownPlanStepError, match="step-missing"):
        PlanStepEvidenceAssessor(evaluator).assess(
            plan,
            make_run(plan),
            "step-missing",
        )
    assert evaluator.calls == []


def test_canonical_plan_step_object_is_supplied_to_evaluator() -> None:
    plan = make_plan()
    run = make_run(plan)
    evaluator = RecordingEvaluator()

    PlanStepEvidenceAssessor(evaluator).assess(plan, run, "step-a")

    assert len(evaluator.calls) == 1
    assert evaluator.calls[0][2] is plan.steps[0]


def test_one_step_observation_is_the_complete_basis() -> None:
    plan = make_plan()
    run = make_run(plan)
    run = record(
        plan,
        run,
        make_observation(run, observation_id="observation-1"),
    )
    evaluator = RecordingEvaluator()
    before = run.to_data()

    assessment = PlanStepEvidenceAssessor(evaluator).assess(plan, run, "step-a")

    assert evaluator.calls[0][3] == (run.observations[0],)
    assert evaluator.calls[0][3][0] is run.observations[0]
    assert assessment.evidence_ids == ("observation-1",)
    assert run.to_data() == before


def test_all_target_observations_preserve_canonical_run_order() -> None:
    plan = make_plan()
    run = make_run(plan)
    inputs = (
        make_observation(
            run,
            observation_id="observation-c",
            observed_at=OBSERVED_1,
        ),
        make_observation(
            run,
            observation_id="observation-a",
            observed_at=OBSERVED_2,
            source="sensor",
            kind="measurement",
        ),
        make_observation(
            run,
            observation_id="observation-b",
            observed_at=OBSERVED_3,
            source="user",
            kind="confirmation",
        ),
    )
    for observation in inputs:
        run = record(plan, run, observation)
    evaluator = RecordingEvaluator()

    assessment = PlanStepEvidenceAssessor(evaluator).assess(plan, run, "step-a")

    evidence = evaluator.calls[0][3]
    assert evidence == run.observations
    assert tuple(item.observation_id for item in evidence) == (
        "observation-a",
        "observation-b",
        "observation-c",
    )
    assert assessment.evidence_ids == (
        "observation-a",
        "observation-b",
        "observation-c",
    )


def test_other_step_and_run_level_observations_are_excluded() -> None:
    plan = make_plan()
    run = make_run(plan)
    observations = (
        make_observation(run, observation_id="target"),
        make_observation(
            run,
            observation_id="other-step",
            step_id="step-b",
            observed_at=OBSERVED_2,
        ),
        make_observation(
            run,
            observation_id="run-level",
            step_id=None,
            observed_at=OBSERVED_3,
        ),
    )
    for observation in observations:
        run = record(plan, run, observation)
    evaluator = RecordingEvaluator()

    assessment = PlanStepEvidenceAssessor(evaluator).assess(plan, run, "step-a")

    evidence = evaluator.calls[0][3]
    assert tuple(item.observation_id for item in evidence) == ("target",)
    assert assessment.evidence_ids == ("target",)


def test_blockers_are_not_outcome_evidence() -> None:
    plan = make_plan()
    run = make_run(plan)
    observation = make_observation(run, observation_id="observation-1")
    run = record(plan, run, observation)
    run = PlanRunReducer().apply(
        plan,
        run,
        AddBlockerUpdate(
            update_id="add-blocker-1",
            run_id=run.run_id,
            expected_revision=run.revision,
            updated_at=OBSERVED_2,
            provenance=RunProvenance("test", "blocker-1"),
            blocker=PlanBlocker(
                blocker_id="blocker-1",
                run_id=run.run_id,
                step_id="step-a",
                kind="external_wait",
                reason="Waiting for an external condition",
                provenance=RunProvenance("test", "condition-1"),
                created_at=OBSERVED_2,
            ),
        ),
    )
    evaluator = RecordingEvaluator()

    assessment = PlanStepEvidenceAssessor(evaluator).assess(plan, run, "step-a")

    assert assessment.evidence_ids == ("observation-1",)
    assert len(evaluator.calls[0][3]) == 1


def test_empty_basis_still_invokes_default_evaluator_once() -> None:
    plan = make_plan()
    run = make_run(plan)
    evaluator = ConservativeStepOutcomeEvaluator(
        clock=lambda: ASSESSED,
        assessment_id_factory=lambda: "assessment-default-empty",
    )

    assessment = PlanStepEvidenceAssessor(evaluator).assess(plan, run, "step-a")

    assert assessment.status is StepOutcomeStatus.INSUFFICIENT_EVIDENCE
    assert assessment.evidence_ids == ()


def test_default_assessor_constructs_existing_conservative_evaluator() -> None:
    plan = make_plan()
    run = make_run(plan)

    assessment = PlanStepEvidenceAssessor().assess(plan, run, "step-a")

    assert assessment.status is StepOutcomeStatus.INSUFFICIENT_EVIDENCE
    assert assessment.evaluator_reference == "deterministic.conservative.v1"


def test_default_evaluator_preserves_indeterminate_for_recorded_evidence() -> None:
    plan = make_plan()
    run = make_run(plan)
    run = record(plan, run, make_observation(run, observation_id="observation-1"))
    evaluator = ConservativeStepOutcomeEvaluator(
        clock=lambda: ASSESSED,
        assessment_id_factory=lambda: "assessment-default-recorded",
    )

    assessment = PlanStepEvidenceAssessor(evaluator).assess(plan, run, "step-a")

    assert assessment.status is StepOutcomeStatus.INDETERMINATE
    assert assessment.evidence_ids == ("observation-1",)


@pytest.mark.parametrize(
    "returned_ids",
    [
        ("observation-a",),
        ("observation-a", "observation-b", "observation-extra"),
    ],
)
def test_incomplete_or_extra_evaluator_evidence_is_rejected(
    returned_ids: tuple[str, ...],
) -> None:
    plan = make_plan()
    run = make_run(plan)
    run = record(
        plan,
        run,
        make_observation(run, observation_id="observation-a"),
    )
    run = record(
        plan,
        run,
        make_observation(
            run,
            observation_id="observation-b",
            observed_at=OBSERVED_2,
        ),
    )

    def incomplete(
        plan: Plan,
        run: PlanRun,
        step: PlanStep,
        evidence: tuple[PlanObservation, ...],
    ) -> StepOutcomeAssessment:
        return assessment_for(
            plan,
            run,
            step,
            evidence,
            evidence_ids=returned_ids,
        )

    with pytest.raises(
        PlanStepEvidenceAssessmentInvariantError,
        match="complete canonical Step evidence basis",
    ):
        PlanStepEvidenceAssessor(RecordingEvaluator(incomplete)).assess(
            plan,
            run,
            "step-a",
        )


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("plan_id", "plan-other"),
        ("run_id", "run-other"),
        ("run_revision", 99),
        ("step_id", "step-b"),
    ],
)
def test_wrong_assessment_identity_or_revision_is_rejected(
    field_name: str,
    bad_value: object,
) -> None:
    plan = make_plan()
    run = make_run(plan)

    def wrong(
        plan: Plan,
        run: PlanRun,
        step: PlanStep,
        evidence: tuple[PlanObservation, ...],
    ) -> StepOutcomeAssessment:
        valid = assessment_for(plan, run, step, evidence)
        return replace(valid, **cast(Any, {field_name: bad_value}))

    with pytest.raises(
        PlanStepEvidenceAssessmentInvariantError,
        match="assessment identity",
    ):
        PlanStepEvidenceAssessor(RecordingEvaluator(wrong)).assess(
            plan,
            run,
            "step-a",
        )


def test_non_assessment_evaluator_result_is_rejected() -> None:
    plan = make_plan()
    run = make_run(plan)

    def invalid(
        plan: Plan,
        run: PlanRun,
        step: PlanStep,
        evidence: tuple[PlanObservation, ...],
    ) -> StepOutcomeAssessment:
        return cast(StepOutcomeAssessment, object())

    with pytest.raises(
        PlanStepEvidenceAssessmentInvariantError,
        match="must return a StepOutcomeAssessment",
    ):
        PlanStepEvidenceAssessor(RecordingEvaluator(invalid)).assess(
            plan,
            run,
            "step-a",
        )


def test_temporal_postconditions_reject_assessment_before_run_or_evidence() -> None:
    plan = make_plan()
    run = make_run(plan)

    def before_run(
        plan: Plan,
        run: PlanRun,
        step: PlanStep,
        evidence: tuple[PlanObservation, ...],
    ) -> StepOutcomeAssessment:
        return assessment_for(
            plan,
            run,
            step,
            evidence,
            assessed_at=CREATED - timedelta(seconds=1),
        )

    with pytest.raises(
        PlanStepEvidenceAssessmentInvariantError,
        match="PlanRun creation",
    ):
        PlanStepEvidenceAssessor(RecordingEvaluator(before_run)).assess(
            plan,
            run,
            "step-a",
        )

    run = record(plan, run, make_observation(run, observation_id="observation-1"))

    def before_evidence(
        plan: Plan,
        run: PlanRun,
        step: PlanStep,
        evidence: tuple[PlanObservation, ...],
    ) -> StepOutcomeAssessment:
        return assessment_for(
            plan,
            run,
            step,
            evidence,
            assessed_at=CREATED,
        )

    with pytest.raises(
        PlanStepEvidenceAssessmentInvariantError,
        match="latest evidence",
    ):
        PlanStepEvidenceAssessor(RecordingEvaluator(before_evidence)).assess(
            plan,
            run,
            "step-a",
        )


def test_assessment_need_not_follow_run_updated_at() -> None:
    plan = make_plan()
    run = make_run(plan)
    run = record(plan, run, make_observation(run, observation_id="observation-1"))
    run = PlanRunReducer().apply(
        plan,
        run,
        AddBlockerUpdate(
            update_id="add-blocker-step-b",
            run_id=run.run_id,
            expected_revision=run.revision,
            updated_at=OBSERVED_3,
            provenance=RunProvenance("test", "blocker-step-b"),
            blocker=PlanBlocker(
                blocker_id="blocker-step-b",
                run_id=run.run_id,
                step_id="step-b",
                kind="external_wait",
                reason="Waiting for B",
                provenance=RunProvenance("test", "condition-step-b"),
                created_at=OBSERVED_3,
            ),
        ),
    )

    def between_evidence_and_update(
        plan: Plan,
        run: PlanRun,
        step: PlanStep,
        evidence: tuple[PlanObservation, ...],
    ) -> StepOutcomeAssessment:
        return assessment_for(
            plan,
            run,
            step,
            evidence,
            assessed_at=OBSERVED_2,
        )

    assessment = PlanStepEvidenceAssessor(
        RecordingEvaluator(between_evidence_and_update)
    ).assess(plan, run, "step-a")

    assert assessment.assessed_at == OBSERVED_2
    assert assessment.assessed_at < run.updated_at


def test_assessment_of_historical_revision_remains_bound_to_that_revision() -> None:
    plan = make_plan()
    historical_run = make_run(plan)
    historical_run = record(
        plan,
        historical_run,
        make_observation(historical_run, observation_id="observation-1"),
    )
    assessment = PlanStepEvidenceAssessor(RecordingEvaluator()).assess(
        plan,
        historical_run,
        "step-a",
    )
    later_run = record(
        plan,
        historical_run,
        make_observation(
            historical_run,
            observation_id="observation-2",
            observed_at=OBSERVED_2,
        ),
    )

    assert later_run.revision == historical_run.revision + 1
    assert assessment.run_revision == historical_run.revision
    assert assessment.evidence_ids == ("observation-1",)


def run_with_progress(state: StepProgressState) -> tuple[Plan, PlanRun]:
    plan = make_plan()
    run = make_run(plan)
    run = record(plan, run, make_observation(run, observation_id="observation-1"))
    if state is StepProgressState.NOT_STARTED:
        return plan, run
    first_target = (
        StepProgressState.FAILED
        if state is StepProgressState.FAILED
        else StepProgressState.ACTIVE
    )
    run = PlanRunReducer().apply(
        plan,
        run,
        StepProgressUpdate(
            update_id="progress-update-1",
            run_id=run.run_id,
            expected_revision=run.revision,
            updated_at=OBSERVED_2,
            provenance=RunProvenance("test", "progress-1"),
            step_id="step-a",
            new_state=first_target,
            evidence_ids=("observation-1",)
            if first_target is StepProgressState.FAILED
            else (),
        ),
    )
    if state is StepProgressState.SUCCEEDED:
        run = PlanRunReducer().apply(
            plan,
            run,
            StepProgressUpdate(
                update_id="progress-update-2",
                run_id=run.run_id,
                expected_revision=run.revision,
                updated_at=OBSERVED_3,
                provenance=RunProvenance("test", "progress-2"),
                step_id="step-a",
                new_state=StepProgressState.SUCCEEDED,
                evidence_ids=("observation-1",),
            ),
        )
    return plan, run


@pytest.mark.parametrize("state", tuple(StepProgressState))
def test_progress_state_does_not_choose_assessment_status(
    state: StepProgressState,
) -> None:
    plan, run = run_with_progress(state)
    assessment = PlanStepEvidenceAssessor(RecordingEvaluator()).assess(
        plan,
        run,
        "step-a",
    )

    assert (
        next(item.state for item in run.step_progress if item.step_id == "step-a")
        is state
    )
    assert assessment.status is StepOutcomeStatus.INDETERMINATE


def test_successful_assessment_is_read_only_and_invokes_evaluator_once() -> None:
    plan = make_plan()
    run = make_run(plan)
    run = record(plan, run, make_observation(run, observation_id="observation-1"))
    before = run.to_data()
    evaluator = RecordingEvaluator()

    assessment = PlanStepEvidenceAssessor(evaluator).assess(plan, run, "step-a")

    assert len(evaluator.calls) == 1
    assert assessment.status is StepOutcomeStatus.INDETERMINATE
    assert run.to_data() == before


def test_evaluator_failure_propagates_without_retry_or_mutation() -> None:
    plan = make_plan()
    run = make_run(plan)
    before = run.to_data()
    evaluator = RecordingEvaluator(error=OutcomeEvaluationError("evaluation failed"))

    with pytest.raises(OutcomeEvaluationError, match="evaluation failed"):
        PlanStepEvidenceAssessor(evaluator).assess(plan, run, "step-a")

    assert len(evaluator.calls) == 1
    assert run.to_data() == before


def test_valid_replaceable_evaluator_status_is_not_reinterpreted() -> None:
    plan = make_plan()
    run = make_run(plan)
    run = record(plan, run, make_observation(run, observation_id="observation-1"))

    def satisfied(
        plan: Plan,
        run: PlanRun,
        step: PlanStep,
        evidence: tuple[PlanObservation, ...],
    ) -> StepOutcomeAssessment:
        return assessment_for(
            plan,
            run,
            step,
            evidence,
            status=StepOutcomeStatus.SATISFIED,
        )

    before = run.to_data()
    assessment = PlanStepEvidenceAssessor(RecordingEvaluator(satisfied)).assess(
        plan,
        run,
        "step-a",
    )

    assert assessment.status is StepOutcomeStatus.SATISFIED
    assert run.to_data() == before


def test_multiple_assessments_of_same_basis_are_valid() -> None:
    plan = make_plan()
    run = make_run(plan)
    counter = iter(("assessment-1", "assessment-2"))

    def independently_identified(
        plan: Plan,
        run: PlanRun,
        step: PlanStep,
        evidence: tuple[PlanObservation, ...],
    ) -> StepOutcomeAssessment:
        return assessment_for(
            plan,
            run,
            step,
            evidence,
            assessment_id=next(counter),
        )

    evaluator = RecordingEvaluator(independently_identified)
    assessor = PlanStepEvidenceAssessor(evaluator)
    first = assessor.assess(plan, run, "step-a")
    second = assessor.assess(plan, run, "step-a")

    assert first.assessment_id != second.assessment_id
    assert len(evaluator.calls) == 2


def test_plan_run_validation_precedes_evaluation() -> None:
    plan = make_plan()
    foreign_plan = make_plan(plan_id="plan-other")
    run = make_run(foreign_plan)
    evaluator = RecordingEvaluator()

    with pytest.raises(PlanRunIdentityError):
        PlanStepEvidenceAssessor(evaluator).assess(plan, run, "step-a")

    assert evaluator.calls == []


def test_package_has_no_execution_or_mutation_dependency() -> None:
    import iris.plan_step_evidence_assessment.assessor as assessor_module

    source = inspect.getsource(assessor_module)
    forbidden = (
        "iris.execution",
        "plan_step_execution",
        "PlanRunReducer",
        "PlanRunUpdate",
        "StepProgressUpdate",
        "StepProgressTransitionDecider",
        "PlanRunController",
    )
    assert all(name not in source for name in forbidden)


def test_wp026_recorded_evidence_interoperates_without_package_coupling() -> None:
    plan = make_plan()
    run = make_run(plan)
    work_subject = WorkSubject(
        WorkSubjectKind.PLAN_STEP,
        PlanStepWorkReference(plan.plan_id, run.run_id, "step-a"),
    )
    execution = ExecutionResult(
        execution_id="execution-1",
        subject_id=work_subject.subject_id,
        decision_id="decision-1",
        context_snapshot_id="context-1",
        target=OrchestrationTarget.SYSTEM,
        decision_reason=OrchestrationReason.DETERMINISTIC_SYSTEM_HANDLING,
        status=ExecutionStatus.REJECTED,
        handler_reference=None,
        started_at=CREATED,
        completed_at=CREATED + timedelta(milliseconds=500),
        failure=ExecutionFailure("handler_unavailable", "No handler available."),
    )
    start_result = PlanStepExecutionStartResult(
        plan_id=plan.plan_id,
        run_id=run.run_id,
        source_revision=run.revision,
        step_id="step-a",
        execution_id=execution.execution_id,
        activation_update_id=None,
        active_run=None,
        execution_result=execution,
    )
    recording = PlanStepExecutionResultRecorder(
        observation_adapter=ExecutionObservationAdapter(
            clock=lambda: OBSERVED_1,
            observation_id_factory=lambda: "execution-observation-1",
        ),
        update_id_factory=lambda: "record-update-1",
    ).record(plan, run, start_result)
    evaluator = ConservativeStepOutcomeEvaluator(
        clock=lambda: ASSESSED,
        assessment_id_factory=lambda: "assessment-wp026",
    )

    assessment = PlanStepEvidenceAssessor(evaluator).assess(
        plan,
        recording.recorded_run,
        "step-a",
    )

    assert assessment.evidence_ids == (recording.observation_id,)
    assert assessment.status is StepOutcomeStatus.INDETERMINATE
    assert (
        recording.recorded_run.step_progress[0].state is StepProgressState.NOT_STARTED
    )


def test_wp027_assessment_has_complete_basis_expected_by_wp021() -> None:
    plan, run = run_with_progress(StepProgressState.ACTIVE)
    assessment = PlanStepEvidenceAssessor(RecordingEvaluator()).assess(
        plan,
        run,
        "step-a",
    )
    decision = StepProgressTransitionDecider(
        clock=lambda: ASSESSED + timedelta(seconds=1),
        decision_id_factory=lambda: "decision-transition-1",
    ).decide(plan, run, plan.steps[0], assessment)

    assert decision.reason is StepProgressTransitionReason.INDETERMINATE_OUTCOME
    assert decision.reason is not (
        StepProgressTransitionReason.INCOMPLETE_CURRENT_EVIDENCE_BASIS
    )
