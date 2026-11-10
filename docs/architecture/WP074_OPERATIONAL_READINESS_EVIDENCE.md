# WP074 — Operational readiness evidence, version 1

**Assessed repository:** `fermaxvago/IRIS`

**Assessment date:** 2026-11-10

**Source revision:** canonical `main` at
`a0e4eadd02f5441e0d8c47c6b52d78cfa3d6f50d` (WP073 merge).

**Scope:** four examined journeys through existing interfaces. This is an
assessment of that revision, not a provider-health report or an authorization
to add operational routes. The new controlled test is T-074-01 on the WP074
branch; its result and CI revision must be reported separately from this source
anchor.

## Reading the evidence

`PRESENT` means the examined implementation exists; `PARTIAL` means only part
of the stated journey exists. `REACHABLE` means the examined CLI exposes the
journey, not that an external provider is currently available. Validation
categories describe the method, not a readiness score. The source and tests
below are repository evidence. The post-WP073 [`push` CI run
42704907877](https://github.com/fermaxvago/IRIS/actions/runs/42704907877)
applies to the canonical base; WP074 PR CI is separate. Neither a fake provider
nor CI is physical Ollama or hardware validation.

| Journey | Implementation | Accessibility from examined entry | Validation at source revision / WP074 |
| --- | --- | --- | --- |
| R1 Ordinary conversation | PRESENT | REACHABLE | STATIC_SOURCE_INSPECTION, CONTROLLED_TEST, CI_EXECUTION (base) |
| R2 Authorized resource consultation | PRESENT | REACHABLE | STATIC_SOURCE_INSPECTION, CONTROLLED_TEST, CI_EXECUTION (base) |
| R3 Baseline and resource comparison | PRESENT | REACHABLE | STATIC_SOURCE_INSPECTION, CONTROLLED_TEST, CI_EXECUTION (base) |
| R4 Planning to execution as a CLI journey | PARTIAL | NOT_REACHABLE_FROM_EXAMINED_ENTRY | STATIC_SOURCE_INSPECTION, CONTROLLED_TEST (component APIs), CI_EXECUTION (base) |

The validation labels do **not** include `PHYSICAL_OBSERVATION_VERIFIED` for
WP074. Historical physical observations in [ACC-WP070](continuity/ACC-WP070.md)
represent earlier revisions and do not establish current provider availability.

## R1 — Ordinary conversation

**Entry and interfaces.** `python -m iris chat --model <installed-model>` or
`chat --select` enters `iris/__main__.py:entrypoint`, then `main` and
`_chat_loop_active`. Explicit selection creates a `ConversationSession`; assisted
selection uses `ConversationRouteBinder`. Ordinary input reaches
`ConversationSession.send`, `IntelligenceRuntime`, and the bound provider.
The existing `--direct` option remains an opt-in provider mode.

**Evidence and authority.** Inspect
`iris/__main__.py`, `iris/intelligence/conversation.py`,
`iris/intelligence/conversation_routing.py`, `iris/intelligence/runtime.py`, and
`iris/intelligence/providers/ollama.py`. Relevant tests are
`tests/test_conversation.py` (validated response, atomic commit and failures),
`tests/test_conversation_routing.py` (selection and binding),
`tests/test_conversation_rollover.py` (authorized bounded history), and
`tests/test_conversational_generation_control.py` (direct-mode contract).
The CLI presents and routes; the session owns confirmed history. Provider
computation is not a committed turn: only a validated successful response
commits a pair. A failure can leave provider-side work unknown while leaving
the confirmed conversation without a new turn.

**Demonstrated / unproven.** Source and controlled tests demonstrate the entry,
bounded request, fake-provider interaction, response checks and failure
atomicity. They do not prove that an installed model is currently available,
that a physical Ollama request will complete, or that all model context windows
accept the character-bounded request. These are operational validation gaps,
not evidence that the CLI route is absent.

**Reproduce.** Run
`python -m pytest -q tests/test_conversation.py tests/test_conversation_routing.py tests/test_conversation_rollover.py tests/test_conversational_generation_control.py`.
Physical use, if independently authorized and available, begins with
`python -m iris chat --model <installed-model>`; it is not reproduced by these
controlled tests.

## R2 — Authorized CPU/RAM consultation

**Entry and interfaces.** `/recursos <pregunta>` enters
`iris/__main__.py:_resource_consultation` directly. A bounded Spanish natural
request uses `iris/intelligence/resource_intent.py` (and the WP071 clarification
for certain incomplete requests), then requires a separate local-observation
confirmation. The consultation uses
`ConversationalSystemAwareness.prepare`, `CapabilityRuntime`, and the registered
`system.status` structured output. It builds a canonical `ContextSnapshot` and
uses `ConversationContextBinder` for an exact disclosure proposal. The CLI
shows the reading and payload, asks for disclosure approval, then calls
`send_approved`, which reaches the existing session/provider path.

**Evidence and authority.** Inspect `iris/intelligence/system_awareness.py`,
`iris/capabilities/system_status.py`, `iris/intelligence/context_binding.py`,
`iris/__main__.py`, `tests/test_conversational_system_awareness.py`,
`tests/test_conversational_resource_intent.py`, and
`tests/test_conversation_context_binding.py`. Observation is a capability
operation. A local observation does not grant model disclosure; disclosure
does not grant execution authority. Context is informational and one-use.
The explicit command itself requests observation; the natural-language path
adds preliminary observation confirmation.

**Demonstrated / unproven.** Controlled tests demonstrate one structured
capture, incomplete-reading abstention, exact preview, approval and contextual
turn atomicity. T-074-01 additionally exercises successful disclosure while a
separate comparison baseline survives. A reading is point-in-time evidence,
not continuous monitoring or a cause of resource pressure. Current physical
hardware values and successful live provider response are not established by
WP074's deterministic tests.

**Reproduce.** Run
`python -m pytest -q tests/test_conversational_system_awareness.py tests/test_conversational_resource_intent.py tests/test_conversation_context_binding.py`
and `python -m pytest -q tests/test_resource_comparison.py -k wp074_cross_path`.
In the actual CLI, use `/recursos ¿Cómo está mi RAM?` and inspect the separate
disclosure prompt before any model request.

## R3 — One retained baseline and local delta

**Entry and interfaces.** `/comparar base` asks for one capture and temporary
retention. A supported natural request such as `¿Estoy usando más RAM que
antes?` is classified by
`iris/intelligence/resource_comparison_intent.py` before ordinary resource
intent. It enters the same `_compare_now` consent and execution path as
`/comparar ahora`. `LocalResourceComparison` owns the process-local baseline,
invokes the registered `system.status` capability, validates compatibility and
uses the pure comparator. `_show_resource_delta` renders the result locally.

**Evidence and authority.** Inspect `iris/intelligence/resource_comparison.py`,
`iris/intelligence/resource_comparison_intent.py`, `iris/__main__.py`,
`tests/test_resource_comparison.py`, and
`tests/test_resource_comparison_intent.py`. Recognition grants no capture;
the second reading requires fresh consent. The baseline expires at 600
monotonic seconds, is bound to chat identity and generation, and is consumed
once on successful comparison. The comparison path neither calls the model
nor constructs contextual disclosure.

**Demonstrated / unproven.** Existing tests demonstrate TTL, session
invalidation, provenance and metric validation, consent, and consumption.
T-074-01 adds the previously missing *successful contextual turn between
baseline and natural-language comparison*. It verifies the delta against the
original baseline after exactly three total captures. Two point readings
cannot establish trend, cause or hardware health. No long-term history or
cross-session comparison is available from this route.

**Reproduce.** Run
`python -m pytest -q tests/test_resource_comparison.py tests/test_resource_comparison_intent.py`.
In chat, use `/comparar base`, approve it, then use a supported natural
comparison and independently approve the second reading. The result remains
local.

## R4 — Planning / execution boundary

**Examined entry.** `iris/__main__.py:entrypoint` exposes only the bare legacy
`IRIS>` loop and `chat --model|--select`. The legacy loop calls
`DeterministicRouter` and `CommandDispatcher` for `estado`, `ayuda`, and
`salir`; chat routes to conversation, resource consultation or comparison.
Neither path constructs a `PlanningRequest` or invokes a planner. The **first
unproven integration boundary** is therefore from a supported CLI input to
`PlanningRequest` / `DeterministicPlanner.plan`. This is a scoped CLI finding,
not a claim that planning APIs are globally unavailable.

**Existing component chain.** `iris/planning/models.py` validates `Goal`,
`PlanStep`, `Plan`, and `PlanningRequest`; `DeterministicPlanner.plan` creates
a planning result without execution. `PlanRunFactory`, `PlanRunReducer` and
`PlanRun` own run state. `PlanRunController.decide` selects or abstains; it
does not activate a handler. `PlanStepOrchestrationComposer` and
`PlanStepExecutionRequestMaterializer` prepare exact context and an
`ExecutionRequest`. `PlanStepExecutionBinder.bind` checks the selected step
and current run. `PlanStepExecutionStartCoordinator.start` uses
`ExecutionCoordinator.execute` to activate and invoke at most one handler.
`PlanStepExecutionResultRecorder.record` turns the result into a run
observation. `PlanStepEvidenceAssessor.assess` evaluates recorded evidence;
`PlanStepEvidenceTransitionComposer.compose` decides a transition, and
post-recording composition modules prepare a successor. Selection, binding,
activation, recording, assessment and successor preparation are distinct
contracts, not one automatic CLI journey.

**Evidence / limitations.** Representative controlled tests are
`tests/test_planning.py`, `tests/test_plan_runs.py`,
`tests/test_plan_control.py`, `tests/test_plan_step_orchestration.py`,
`tests/test_plan_step_execution_request_materialization.py`,
`tests/test_plan_step_execution_binding.py`,
`tests/test_plan_step_execution_start.py`,
`tests/test_execution.py`, `tests/test_plan_step_execution_result_recording.py`,
`tests/test_plan_step_evidence_assessment.py`,
`tests/test_plan_step_evidence_transition.py`, and the
`tests/test_plan_step_execution_*_composition.py` series. They establish
component behavior for their constructed inputs; they do not demonstrate
that a conversational user can request, approve and execute a plan end to end.
No production Planning-to-CLI connection is added by WP074. Planning is not
execution; an `ExecutionBinding` is not authorization.

**Reproduce.** Run
`python -m pytest -q tests/test_planning.py tests/test_plan_runs.py tests/test_plan_control.py tests/test_execution.py tests/test_plan_step_execution_start.py tests/test_plan_step_execution_result_recording.py tests/test_plan_step_evidence_assessment.py tests/test_plan_step_evidence_transition.py`
and the relevant `tests/test_plan_step_execution_*_composition.py` files.
Inspect `iris/__main__.py`, `iris/router/deterministic.py` and
`iris/dispatch.py` to verify the examined CLI boundary.

## New evidence and nonduplication

T-074-01 is
`tests/test_resource_comparison.py::test_wp074_cross_path_session_and_baseline_isolation`.
It drives the actual CLI with an injected `CapabilityRuntime`, deterministic
clocks and a fake conversational provider. It records capture, provider-call
and committed-turn counts **at each of four distinct consent prompts**. It
asserts the exact contextual payload was displayed, the intermediate
consultation did not replace the baseline, the final delta uses the original
baseline, and a later comparison has no reusable baseline. The provider sees
the ordinary and approved contextual turns only.

The closest pre-existing test,
`tests/test_resource_comparison.py::test_ordinary_turn_and_resource_consultation_do_not_replace_natural_baseline`,
**denies** intermediate disclosure, so it exercises no successful contextual
provider turn. `tests/test_conversational_system_awareness.py` separately
tests approved disclosure without a retained comparison baseline. WP068
resource-intent tests cover preliminary consent; WP072 comparison tests cover
baseline lifecycle; WP073 intent tests cover classifier precedence. None
contains this full cross-path sequence. [ACC-WP070](continuity/ACC-WP070.md)
is a historical architecture checkpoint at an earlier SHA, not this WP074
integration test or a current physical observation.

`docs/research/REFERENCE_REGISTRY.md` was inspected. This assessment relies
on canonical IRIS source and tests, not a material new external reference;
the registry and earlier ACC files are unchanged.
