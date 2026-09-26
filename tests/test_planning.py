"""Goal and Planning contracts, DAG validation, and side-effect boundaries."""

from __future__ import annotations

import json
import socket
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone

import pytest

from iris.context import (
    ContextBudget,
    ContextEvidence,
    ContextItem,
    ContextSnapshot,
    EvidenceSource,
    Freshness,
    Relevance,
    ResolutionStatus,
)
from iris.memory import EpistemicStatus, MemoryScope, ScopeKind
from iris.orchestrator import HandlingKind
from iris.planning import (
    ConstraintKind,
    DeterministicPlanner,
    DuplicatePlanningRuleError,
    Goal,
    GoalProvenance,
    GoalScope,
    Plan,
    Planner,
    PlanningConstraint,
    PlanningContextRequirement,
    PlanningReason,
    PlanningRequest,
    PlanningResult,
    PlanningRule,
    PlanningStatus,
    PlanStep,
    PlanValidationError,
)

NOW = datetime(2026, 9, 26, 4, tzinfo=UTC)
LATER = NOW + timedelta(seconds=1)
GLOBAL = MemoryScope(ScopeKind.GLOBAL)
TASK_SCOPE = GoalScope(ScopeKind.TASK, "physics-assignment")


def goal(
    objective: str = "Preparar el espacio necesario para trabajar en la tarea de física.",
    *,
    constraints: tuple[PlanningConstraint, ...] = (),
) -> Goal:
    return Goal(
        goal_id="goal-1",
        objective=objective,
        scope=TASK_SCOPE,
        provenance=GoalProvenance("request", "request-1", "user-1"),
        constraints=constraints,
        success_criteria=(
            "required resources identified",
            "assignment identified",
            "working document identified",
        ),
    )


def planning_request(
    selected_goal: Goal | None = None,
    *,
    context: ContextSnapshot | None = None,
) -> PlanningRequest:
    return PlanningRequest(
        planning_request_id="planning-request-1",
        goal=goal() if selected_goal is None else selected_goal,
        created_at=NOW,
        context=context,
    )


def step(
    step_id: str,
    *,
    depends_on: tuple[str, ...] = (),
    handling: HandlingKind | None = None,
) -> PlanStep:
    return PlanStep(
        step_id=step_id,
        objective=f"Objective {step_id}",
        expected_outcome=f"Expected {step_id}",
        depends_on=depends_on,
        required_handling=handling,
    )


def physics_steps() -> tuple[PlanStep, ...]:
    return (
        PlanStep(
            "a",
            "Localizar la tarea de física.",
            "Una referencia inequívoca a la tarea relevante.",
            required_handling=HandlingKind.CAPABILITY,
        ),
        PlanStep(
            "b",
            "Identificar el documento asociado.",
            "Una referencia al documento de trabajo.",
            depends_on=("a",),
        ),
        PlanStep(
            "c",
            "Identificar los recursos necesarios.",
            "Una lista conceptual de recursos requeridos.",
            depends_on=("a",),
        ),
        PlanStep(
            "d",
            "Verificar la preparación del espacio.",
            "Los criterios de preparación quedan cubiertos.",
            depends_on=("c", "b"),
            required_handling=HandlingKind.SYSTEM,
        ),
    )


def planner_for(*rules: PlanningRule) -> DeterministicPlanner:
    return DeterministicPlanner(
        tuple(rules),
        clock=lambda: LATER,
        plan_id_factory=lambda: "plan-1",
        result_id_factory=lambda: "planning-result-1",
    )


def snapshot(*items: ContextItem) -> ContextSnapshot:
    return ContextSnapshot(
        snapshot_id="context-1",
        request_id="request-1",
        created_at=NOW - timedelta(seconds=1),
        budget=ContextBudget(max_items=len(items)),
        items=tuple(items),
        status=ResolutionStatus.RESOLVED,
    )


def context_item(kind: str, key: str) -> ContextItem:
    return ContextItem(
        candidate_id=f"{kind}-{key}",
        kind=kind,
        key=key,
        value="known",
        evidence=ContextEvidence(
            EvidenceSource.CALLER,
            "planning-test",
            EpistemicStatus.DIRECT,
        ),
        scope=GLOBAL,
        relevance=Relevance.REQUIRED,
        freshness=Freshness.CURRENT,
    )


def test_multi_step_planning_creates_valid_diamond_without_execution() -> None:
    request = planning_request()
    planner = planner_for(
        PlanningRule(
            request.goal.objective,
            steps=physics_steps(),
            assumptions=("La tarea de física sigue disponible.",),
        )
    )

    result = planner.plan(request)

    assert result.status is PlanningStatus.PLAN_CREATED
    assert result.reason is PlanningReason.DECOMPOSITION_CREATED
    assert result.plan is not None
    assert result.plan.goal_id == request.goal.goal_id
    assert result.plan.plan_id != request.goal.goal_id
    assert [item.step_id for item in result.plan.steps] == ["a", "b", "c", "d"]
    assert result.plan.steps[-1].depends_on == ("b", "c")
    assert not hasattr(result.plan.steps[-1], "observed_outcome")
    assert not hasattr(result, "execution_result")


def test_no_plan_required_is_not_execution_or_completion() -> None:
    selected_goal = goal("abrir Spotify")
    result = planner_for(PlanningRule("abrir Spotify")).plan(
        planning_request(selected_goal)
    )

    assert result.status is PlanningStatus.NO_PLAN_REQUIRED
    assert result.reason is PlanningReason.DECOMPOSITION_UNNECESSARY
    assert result.plan is None
    assert "execution" not in result.to_trace()


def test_insufficient_context_preserves_missing_requirement() -> None:
    selected_goal = goal("haz lo de antes")
    requirement = PlanningContextRequirement("task", "previous_reference", GLOBAL)
    planner = planner_for(
        PlanningRule(
            selected_goal.objective,
            steps=(step("a"),),
            required_context=(requirement,),
        )
    )

    result = planner.plan(planning_request(selected_goal))

    assert result.status is PlanningStatus.INSUFFICIENT_CONTEXT
    assert result.missing_context == (requirement,)
    assert result.plan is None


def test_explicit_context_satisfies_rule_without_mutating_snapshot() -> None:
    selected_goal = goal("haz lo de antes")
    requirement = PlanningContextRequirement("task", "previous_reference", GLOBAL)
    context = snapshot(context_item("task", "previous_reference"))
    original = context.items
    result = planner_for(
        PlanningRule(
            selected_goal.objective,
            steps=(step("a"),),
            required_context=(requirement,),
        )
    ).plan(planning_request(selected_goal, context=context))

    assert result.status is PlanningStatus.PLAN_CREATED
    assert context.items == original


def test_unsatisfiable_constraints_are_structured_data() -> None:
    constraints = (
        PlanningConstraint(ConstraintKind.NOT_BEFORE, "work", NOW + timedelta(hours=2)),
        PlanningConstraint(ConstraintKind.DEADLINE, "work", NOW + timedelta(hours=1)),
    )
    selected_goal = goal(constraints=constraints)
    result = planner_for(
        PlanningRule(selected_goal.objective, steps=physics_steps())
    ).plan(planning_request(selected_goal))

    assert result.status is PlanningStatus.UNSATISFIABLE
    assert result.reason is PlanningReason.CONFLICTING_CONSTRAINTS
    assert result.constraint_conflicts == ("invalid_time_window:work",)
    assert result.plan is None


def test_required_and_forbidden_value_is_unsatisfiable() -> None:
    selected_goal = goal(
        constraints=(
            PlanningConstraint(ConstraintKind.REQUIRE, "resource_location", "local"),
            PlanningConstraint(ConstraintKind.FORBID, "resource_location", "local"),
        )
    )
    result = planner_for(
        PlanningRule(selected_goal.objective, steps=physics_steps())
    ).plan(planning_request(selected_goal))
    assert result.reason is PlanningReason.CONFLICTING_CONSTRAINTS
    assert result.constraint_conflicts == ("required_and_forbidden:resource_location",)


def test_unknown_goal_is_unsatisfiable_only_under_current_rule_set() -> None:
    result = planner_for().plan(planning_request(goal("unknown objective")))
    assert result.status is PlanningStatus.UNSATISFIABLE
    assert result.reason is PlanningReason.NO_REGISTERED_STRATEGY


def test_invalid_dependency_is_rejected() -> None:
    with pytest.raises(PlanValidationError, match="unknown dependencies"):
        Plan("plan-1", "goal-1", (), (step("a", depends_on=("missing",)),))


def test_self_dependency_is_rejected() -> None:
    with pytest.raises(PlanValidationError, match="depend on itself"):
        step("a", depends_on=("a",))


def test_cycle_is_rejected() -> None:
    with pytest.raises(PlanValidationError, match="acyclic"):
        Plan(
            "plan-1",
            "goal-1",
            (),
            (
                step("a", depends_on=("b",)),
                step("b", depends_on=("c",)),
                step("c", depends_on=("a",)),
            ),
        )


def test_diamond_dependency_is_accepted() -> None:
    plan = Plan("plan-1", "goal-1", (), physics_steps())
    assert plan.steps[-1].depends_on == ("b", "c")


def test_zero_steps_and_duplicate_ids_are_invalid_plans() -> None:
    with pytest.raises(PlanValidationError, match="at least one step"):
        Plan("plan-1", "goal-1", (), ())
    with pytest.raises(PlanValidationError, match="unique"):
        Plan("plan-1", "goal-1", (), (step("a"), step("a")))


def test_multiple_roots_and_multiple_terminal_steps_are_valid() -> None:
    plan = Plan(
        "plan-1",
        "goal-1",
        (),
        (
            step("root-b"),
            step("terminal-b", depends_on=("root-b",)),
            step("root-a"),
            step("terminal-a", depends_on=("root-a",)),
        ),
    )
    roots = [item.step_id for item in plan.steps if not item.depends_on]
    depended_on = {dependency for item in plan.steps for dependency in item.depends_on}
    terminals = [item.step_id for item in plan.steps if item.step_id not in depended_on]
    assert roots == ["root-a", "root-b"]
    assert terminals == ["terminal-a", "terminal-b"]


def test_optional_conceptual_handling_does_not_select_runtime_details() -> None:
    conceptual = step("a", handling=HandlingKind.INTELLIGENCE)
    unspecified = step("b")
    assert conceptual.required_handling is HandlingKind.INTELLIGENCE
    assert unspecified.required_handling is None
    assert not hasattr(conceptual, "provider_id")
    assert not hasattr(conceptual, "capability_id")
    with pytest.raises(ValueError, match="clarification"):
        step("c", handling=HandlingKind.CLARIFICATION)


def test_goal_preserves_scope_provenance_constraints_and_success_criteria() -> None:
    selected = goal(
        constraints=(PlanningConstraint(ConstraintKind.FORBID, "modify_files"),)
    )
    assert selected.scope is TASK_SCOPE
    assert selected.provenance.source_id == "request-1"
    assert selected.constraints[0].subject == "modify_files"
    assert selected.success_criteria == (
        "assignment identified",
        "required resources identified",
        "working document identified",
    )


def test_empty_constraints_and_multiple_assumptions_are_supported() -> None:
    selected = goal()
    plan = Plan(
        "plan-1",
        selected.goal_id,
        ("Second assumption", "First assumption"),
        (step("a"),),
    )
    assert selected.constraints == ()
    assert plan.assumptions == ("First assumption", "Second assumption")


def test_models_are_immutable_and_json_serializable_with_stable_ordering() -> None:
    selected = goal()
    request = planning_request(selected)
    result = planner_for(
        PlanningRule(
            selected.objective,
            steps=tuple(reversed(physics_steps())),
            assumptions=("z assumption", "a assumption"),
        )
    ).plan(request)
    assert result.plan is not None
    with pytest.raises(FrozenInstanceError):
        selected.objective = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.plan.steps = ()  # type: ignore[misc]

    serialized = json.dumps(
        {
            "goal": selected.to_data(),
            "request": request.to_data(),
            "result": result.to_trace(),
        },
        sort_keys=True,
    )
    assert '"status": "plan_created"' in serialized
    assert [item.step_id for item in result.plan.steps] == ["a", "b", "c", "d"]
    assert result.plan.assumptions == ("a assumption", "z assumption")


def test_goal_and_plan_identities_must_be_distinct() -> None:
    with pytest.raises(PlanValidationError, match="independent identities"):
        Plan("same", "same", (), (step("a"),))


def test_planning_result_rejects_wrong_goal_and_incompatible_payloads() -> None:
    valid_plan = Plan("plan-1", "another-goal", (), (step("a"),))
    with pytest.raises(ValueError, match="different Goal"):
        PlanningResult(
            "result-1",
            "request-1",
            "goal-1",
            PlanningStatus.PLAN_CREATED,
            PlanningReason.DECOMPOSITION_CREATED,
            NOW,
            plan=valid_plan,
        )
    with pytest.raises(ValueError, match="requires a Plan"):
        PlanningResult(
            "result-1",
            "request-1",
            "goal-1",
            PlanningStatus.PLAN_CREATED,
            PlanningReason.DECOMPOSITION_CREATED,
            NOW,
        )
    with pytest.raises(ValueError, match="only PLAN_CREATED"):
        PlanningResult(
            "result-1",
            "request-1",
            "another-goal",
            PlanningStatus.NO_PLAN_REQUIRED,
            PlanningReason.DECOMPOSITION_UNNECESSARY,
            NOW,
            plan=valid_plan,
        )
    with pytest.raises(ValueError, match="incompatible"):
        PlanningResult(
            "result-1",
            "request-1",
            "goal-1",
            PlanningStatus.NO_PLAN_REQUIRED,
            PlanningReason.MISSING_REQUIRED_CONTEXT,
            NOW,
        )


def test_temporal_inputs_require_awareness_and_normalize_to_utc() -> None:
    local = timezone(timedelta(hours=-6))
    constraint = PlanningConstraint(
        ConstraintKind.DEADLINE,
        "work",
        datetime(2026, 9, 25, 23, tzinfo=local),
    )
    assert constraint.value == datetime(2026, 9, 26, 5, tzinfo=UTC)
    with pytest.raises(ValueError, match="timezone-aware"):
        PlanningConstraint(
            ConstraintKind.DEADLINE,
            "work",
            datetime(2026, 9, 26, 5),
        )


def test_request_rejects_future_or_mismatched_context() -> None:
    future = ContextSnapshot(
        snapshot_id="context-1",
        request_id="request-1",
        created_at=NOW + timedelta(seconds=1),
        budget=ContextBudget(0),
        items=(),
        status=ResolutionStatus.RESOLVED,
    )
    with pytest.raises(ValueError, match="predate"):
        planning_request(context=future)

    wrong = ContextSnapshot(
        snapshot_id="context-2",
        request_id="different-request",
        created_at=NOW - timedelta(seconds=1),
        budget=ContextBudget(0),
        items=(),
        status=ResolutionStatus.RESOLVED,
    )
    with pytest.raises(ValueError, match="do not match"):
        planning_request(context=wrong)


def test_deterministic_planner_is_provider_independent_protocol() -> None:
    planner = planner_for(PlanningRule("abrir Spotify"))
    assert isinstance(planner, Planner)
    assert not hasattr(planner, "provider")
    assert not hasattr(planner, "runtime")


def test_duplicate_normalized_rules_are_rejected() -> None:
    with pytest.raises(DuplicatePlanningRuleError):
        planner_for(PlanningRule("Abrir   Spotify"), PlanningRule("abrir spotify"))


def test_no_plan_path_never_requests_plan_identity() -> None:
    planner = DeterministicPlanner(
        (PlanningRule("abrir Spotify"),),
        clock=lambda: LATER,
        plan_id_factory=lambda: (_ for _ in ()).throw(AssertionError("plan ID used")),
        result_id_factory=lambda: "result-1",
    )
    assert (
        planner.plan(planning_request(goal("abrir Spotify"))).status
        is PlanningStatus.NO_PLAN_REQUIRED
    )


def test_unexpected_programming_defect_propagates() -> None:
    planner = DeterministicPlanner(
        (PlanningRule("abrir Spotify"),),
        clock=lambda: LATER,
        result_id_factory=lambda: (_ for _ in ()).throw(
            AttributeError("programming defect")
        ),
    )
    with pytest.raises(AttributeError, match="programming defect"):
        planner.plan(planning_request(goal("abrir Spotify")))


def test_planning_performs_no_filesystem_network_or_execution_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("side effect attempted")

    monkeypatch.setattr("builtins.open", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    request = planning_request()
    context_before = request.context

    result = planner_for(
        PlanningRule(request.goal.objective, steps=physics_steps())
    ).plan(request)

    assert result.status is PlanningStatus.PLAN_CREATED
    assert request.context is context_before
    assert not hasattr(result, "execution_id")
    assert not hasattr(result, "memory_record")
