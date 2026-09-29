# IRIS External Reference Registry

This document is the versioned source of truth for external projects used as
research references by IRIS. It records identity, relevance, history, analysis
outcomes, influence, and basic provenance without making an external project a
dependency or an architectural authority.

IRIS itself is not an external reference. Its source repository and Git history
are the primary record for IRIS.

> Los proyectos externos son referencias de investigación, no fuentes
> automáticas de implementación.

Registration does not mean that IRIS uses a project's code, adopts its
architecture, endorses its trade-offs, or has completed a license review.

## Research boundary

External projects may be studied for architecture, documentation, interfaces,
code, patterns, decisions, trade-offs, limitations, failure modes, and project
evolution. IRIS requirements and contracts remain authoritative.

Prefer conceptual adaptation over implementation transplant. Do not
automatically copy files, substantial code fragments, schemas, prompts, tests,
assets, or project-specific implementation structures into IRIS.

The required progression is:

```text
external project -> research -> comparison -> IRIS architectural decision -> IRIS implementation
```

The following progression is prohibited:

```text
external project -> copy implementation -> rename -> IRIS
```

If future work proposes incorporating code, substantial derivative code,
assets, or a significant dependency and introduces license, attribution,
maintenance, or architectural obligations, stop and request an Architect
decision before implementation.

## Reference lifecycle

```text
DISCOVERED -> identity/repository verification -> relevance review
           -> basic license/provenance review -> REGISTERED
```

Reference status and analysis outcome are separate dimensions.

### Reference statuses

| Status | Meaning |
| --- | --- |
| `DISCOVERED` | Candidate known but not yet approved for use in a Work Package. |
| `REGISTERED` | Identity, relevance, and basic provenance were recorded. This does not mean adopted. |
| `REVIEWED` | The reference received at least one recorded research analysis. |
| `CHANGED` | A material identity, location, ownership, purpose, or implementation change needs attention. |
| `REPLACED` | Another project or implementation superseded this reference; history remains preserved. |
| `ARCHIVED` | No longer active for new research, but retained for traceability. |

### Analysis outcomes

Each analysis is recorded independently and may use one of these outcomes:

| Outcome | Meaning |
| --- | --- |
| `REVIEWED` | Studied for a defined problem; no influence or adoption implied. |
| `INFLUENCED` | Contributed to an IRIS decision without direct adoption. |
| `ADOPTED_PATTERN` | A named conceptual pattern was deliberately adapted to IRIS contracts. |
| `REJECTED_PATTERN` | A named pattern was deliberately rejected with a recorded reason. |

An analysis record should contain its date, Work Package or decision context,
research question, outcome, conclusions, affected IRIS decision, and evidence.
One reference may have multiple analysis records with different outcomes.

## Duplicate and change control

Before registration, verify the candidate's name, canonical URL, owner or
organization, repository identity, forks, renames, moves, successors, and
archive status. Potential duplicates must be classified before adding an entry:

| Classification | Action |
| --- | --- |
| `SAME_REFERENCE` | Reuse the existing entry. |
| `SAME_REFERENCE_UPDATED` | Update the existing entry and preserve its prior identity in `Known changes`. |
| `SUCCESSOR` | Register the relationship; add a separate entry only after normal registration review. |
| `RELEVANT_FORK` | Record why the fork is independently relevant before adding it. |
| `ACCIDENTAL_DUPLICATE` | Reverify identity, preserve one entry, and record the correction. |

Do not silently erase old URLs, owners, purposes, archive events, successors,
or replaced implementations. Update `Known changes` so Git history and the
entry together explain what IRIS originally consulted.

## Work Package protocol

Before a future Work Package that may benefit from external research:

1. Consult this registry.
2. Identify relevant registered references.
3. Reverify material changes when appropriate.
4. Check whether new candidates merit registration.
5. Resolve possible duplicates before registration.
6. Use only registered references within the Work Package.
7. Record each consulted reference and its purpose in both the Work Package and
   the corresponding registry entry.
8. Record analysis outcomes and any influenced, adopted, or rejected patterns.

A new project must complete the registration process before appearing in a
Work Package as an available reference. Reusing a registered project creates a
new research-history or analysis record, not a duplicate registry entry. If the
project changed, mark it as `EXISTING REFERENCE - UPDATED` in the Work Package
and revalidate conclusions affected by the change.

For a new candidate, capture at least:

```text
NEW REFERENCE
Name:
Canonical URL:
Reason for inclusion:
Relevant areas:
Identity verified:
License/provenance reviewed:
```

## Registry summary

All entries below were registered on **2026-09-25**. Identity and repository
status were checked against the canonical GitHub repositories on that date.
Later research activity is recorded per entry. License notes are a basic
provenance record, not legal advice.

| Reference | Canonical repository | Status | Declared license summary |
| --- | --- | --- | --- |
| OpenJarvis | <https://github.com/open-jarvis/OpenJarvis> | `REVIEWED` | Apache-2.0 |
| OpenClaw | <https://github.com/openclaw/openclaw> | `REVIEWED` | MIT; third-party notices also apply |
| Letta | <https://github.com/letta-ai/letta> | `REGISTERED` | Apache-2.0 |
| Mem0 | <https://github.com/mem0ai/mem0> | `REGISTERED` | Apache-2.0 |
| OmniRoute | <https://github.com/arnoldwender/omniroute> | `REGISTERED` | MIT |
| LangGraph | <https://github.com/langchain-ai/langgraph> | `REVIEWED` | MIT |
| Microsoft Agent Framework | <https://github.com/microsoft/agent-framework> | `REVIEWED` | MIT |
| AutoGen | <https://github.com/microsoft/autogen> | `CHANGED` | Mixed scope; root CC-BY-4.0 and code package license files must be checked |
| PersonalJarvis | <https://github.com/PersonalJarvis/PersonalJarvis> | `REGISTERED` | Apache-2.0 on current line; releases through 1.6.0 remain MIT |
| Particle Interaction - wonderstone | <https://github.com/wonderstone/particle-interaction> | `REGISTERED` | No license recorded at repository root |

## OpenJarvis

- **Name:** OpenJarvis
- **Canonical URL:** <https://github.com/open-jarvis/OpenJarvis>
- **Status:** `REVIEWED`
- **Relevant areas:** personal AI; local-first architecture; agents;
  intelligence execution; model/resource routing; tools.
- **Date registered:** 2026-09-25
- **Last verified:** 2026-09-29
- **Relevant Work Packages:** WP011; WP012; WP013; WP014; WP015; WP016; WP017;
  WP018; WP019; WP020; WP021; WP022.
- **Research history:** Initial identity, relevance, and basic provenance review
  during registry initialization on 2026-09-25. WP011 relevance screening on
  2026-09-25 reviewed its local-first agent primitives and learning/execution
  loop; no Goal or Plan contract was adopted. WP012 reused the existing
  reference on 2026-09-26 to contrast its autonomous agent-loop direction with
  IRIS's reducer-only progress-state boundary; no loop behavior was adopted.
  Analysis outcome: `REVIEWED`. WP013 reused the reference on 2026-09-27 to
  review its on-demand, scheduled, continuous, ReAct, and orchestrator agent
  modes. The autonomous and scheduled loop pattern was deliberately excluded
  from the one-decision control foundation. Analysis outcome:
  `REJECTED_PATTERN`. WP014 reused the reference on 2026-09-27 to compare its
  model-driven agent/tool modes and direct tool-use path with IRIS's typed
  preparation boundary. Automatic tool-call generation and execution were
  excluded: WP014 accepts only explicit handling detail and stops at a semantic
  need. Analysis outcome: `REJECTED_PATTERN`. WP015 reused the reference on
  2026-09-27 to compare its explicit query entry points, distinct agent modes,
  and separately invoked tool/skill concepts with IRIS work identity. The
  comparison supported keeping incoming input, current operational subject,
  and later invocation distinct, but supplied no identity contract adopted by
  IRIS. Analysis outcome: `REVIEWED`. WP016 reused the canonical repository and
  current skills documentation on 2026-09-28 to review runtime injection of
  invoked skill content and its agent modes. IRIS retained explicit
  caller-supplied ContextCandidates and rejected automatic runtime enrichment
  as part of the Context foundation. Analysis outcome: `REJECTED_PATTERN`.
  WP017 reused the canonical agent and query-flow documentation on 2026-09-28
  to compare its explicit query/AgentContext boundary with subsequent
  ToolExecutor dispatch and a multi-turn tool loop. IRIS retained a typed
  WorkSubject/Context/HandlingNeed binding but rejected dispatch, execution,
  event emission, and iteration inside Orchestration. Analysis outcome:
  `REJECTED_PATTERN`. WP018 reverified the current Query Flow documentation on
  2026-09-28. Its explicit tool-call dispatch through `ToolExecutor`, followed
  by a tool result and another inference turn, supported an explicit
  invocation/result boundary; IRIS adopted neither the event bus nor the
  multi-turn tool loop. Analysis outcomes: `INFLUENCED` for the discrete
  invocation/result separation and `REJECTED_PATTERN` for automatic iteration.
  WP019 reverified the current Tool System and Query Flow documentation on
  2026-09-28. Its `ToolExecutor` returns a structured `ToolResult` carrying
  success/failure and observable execution data before that result is fed back
  into the agent loop. This influenced IRIS's explicit raw-result evidence
  boundary; event publication, trace persistence, and tool-result-to-model
  iteration were deliberately excluded. Analysis outcomes: `INFLUENCED` and
  `REJECTED_PATTERN`. WP020 reverified the current Evaluations documentation on
  2026-09-28. OpenJarvis separates dataset outputs from benchmark-specific
  scorers and uses deterministic comparison for some tasks while other tasks
  use LLM judges or deterministic-first fallbacks. This influenced IRIS's
  replaceable evaluator contract and conservative deterministic baseline;
  automatic LLM fallback, scoring runs, and mandatory numeric scores were
  excluded. Analysis outcomes: `INFLUENCED` and `REJECTED_PATTERN`.
  WP021 reverified the current OpenJarvis changelog on 2026-09-29, including
  its integrated diagnose-plan-execute-gate spec-search loop and held-out gate
  that accepts only non-regressing edits. The explicit gate influenced IRIS's
  assessment-to-policy decision boundary, while integrated execution,
  evaluation, adoption, and learning-loop progression were excluded. Analysis
  outcomes: `INFLUENCED` and `REJECTED_PATTERN`.
  WP022 reverified the current OpenJarvis changelog on 2026-09-29. **FACT:**
  `SpecSearchOrchestrator` combines diagnose, plan, execute, and a held-out
  non-regression gate in one learning session. **INFERENCE:** its explicit gate
  illustrates that evaluation and adoption are distinguishable even when one
  runtime composes them. **IRIS DECISION:** WP022 materializes only an already
  accepted transition decision into an inert update; it rejects the integrated
  loop, automatic adoption, and continuation. Analysis outcomes: `INFLUENCED`
  and `REJECTED_PATTERN`.
- **Known changes:** Not recorded.
- **Influenced decisions:** WP018 keeps an explicit invocation/result boundary
  while leaving result-driven model iteration outside the Execution layer.
  WP019 preserves structured execution facts in a separate observation before
  any outcome interpretation. WP020 separates explicit evidence from a
  replaceable evaluator and preserves evaluator provenance without adopting a
  benchmark runtime. WP021 inserts an explicit operational policy gate between
  epistemic assessment and any future progress update. WP022 preserves that
  gate as the immediate provenance of a separately synthesized update.
- **Adopted patterns:** Not recorded.
- **Rejected patterns:** WP013 rejects an agent/tool, scheduled, or continuous
  loop as the foundational PlanRun control API; one call produces one decision
  and stops. WP014 rejects a model/tool loop as a source of implicit handling
  detail or execution. WP016 rejects automatic agent-runtime context enrichment
  as a replacement for explicit evidence submission and bounded selection.
  WP017 rejects a tool-executing, event-emitting, multi-turn agent loop as the
  Orchestration contract; one call still returns one inert decision. WP018
  rejects tool-result-to-model iteration, event publication, and trace
  persistence inside the single-call Execution foundation. WP019 likewise
  rejects an event bus and automatic agent continuation as part of evidence
  recording. WP020 rejects automatic LLM-judge fallback and benchmark-driven
  workflow progression. WP021 rejects a combined
  diagnose-execute-evaluate-adopt loop as the progress-transition boundary.
- **License/provenance notes:** Repository declares Apache License 2.0 in the
  root `LICENSE` file. No code or assets incorporated into IRIS.
- **General notes:** Registered as a research reference only.

## OpenClaw

- **Name:** OpenClaw
- **Canonical URL:** <https://github.com/openclaw/openclaw>
- **Status:** `REVIEWED`
- **Relevant areas:** personal assistant; gateways; channels; integrations;
  multiple devices; future IRIS Mesh concepts.
- **Date registered:** 2026-09-25
- **Last verified:** 2026-09-29
- **Relevant Work Packages:** WP011; WP012; WP013; WP014; WP015; WP016; WP017;
  WP018; WP019; WP020; WP021; WP022.
- **Research history:** Initial identity, relevance, and basic provenance review
  during registry initialization on 2026-09-25. WP011 relevance screening on
  2026-09-25 reviewed its gateway, channel, and integration boundaries; these
  did not supply a Goal or Plan representation for WP011. Analysis outcome:
  `REVIEWED`. WP012 reused the reference on 2026-09-26 to review run lifecycle,
  background execution, and timeout ownership. The distinction between
  observing a runtime/tool condition and declaring logical step failure
  influenced IRIS's explicit-update boundary. Analysis outcome: `INFLUENCED`.
  WP013 reused the reference on 2026-09-27 to compare its serialized agent loop
  and independently managed background processes with IRIS control decisions.
  This confirmed that selection should not start execution, wait on a process,
  or imply completion. Analysis outcome: `REVIEWED`. WP014 reused the reference
  on 2026-09-27 to review the boundary between agent-loop tool invocation and
  separately managed background processes. It reinforced that expressing work
  to be handled is not process initiation or lifecycle observation. No runtime
  behavior was adopted. Analysis outcome: `REVIEWED`. WP015 reused the
  reference on 2026-09-27 to review its distinction among an inbound message,
  session identity, per-invocation run ID, and independently identified
  background sub-agent sessions. This influenced the separation of causal
  `WorkOrigin` from current `WorkSubject`; OpenClaw lifecycle and session
  machinery were not adopted. Analysis outcome: `INFLUENCED`. WP016 reused the
  canonical context and context-engine documentation on 2026-09-28 to review
  per-run assembly, session-aware compaction, and optional persistence/index
  lifecycle hooks. These mechanisms were reviewed as a contrast: IRIS Context
  remains an ephemeral, caller-supplied snapshot distinct from session/runtime
  lifecycle. Analysis outcome: `REVIEWED`. WP017 reused current message,
  session, context, and multi-agent routing documentation on 2026-09-28. Its
  separation of gateway-owned sessions, per-run model context, and routed agent
  boundaries reinforced that current work identity, contextual observation,
  and runtime execution are distinct. No gateway, session, routing, or
  execution runtime was adopted. Analysis outcome: `INFLUENCED`.
  WP018 reverified the current session-tool documentation on 2026-09-28. Its
  distinct stable session key, accepted background-run ID, active-run route,
  and later completion reporting reinforced that longer-lived work scope and a
  concrete execution instance need separate identities. Background sessions,
  queues, timeouts, cancellation, and recovery were not adopted. Analysis
  outcome: `INFLUENCED`. WP019 reverified the current sub-agent completion
  documentation on 2026-09-28. It explicitly treats a child run's completion
  output as evidence for the requester to synthesize and states that child-run
  completion does not itself complete the requester's goal. This influenced
  the separation of raw execution observation from PlanStep/Goal outcome
  judgment. Analysis outcome: `INFLUENCED`. WP020 reverified the current
  sub-agent completion model on 2026-09-28. A child run reports a result back
  to its requester for review, while the requesting run remains a distinct
  scope. This reinforced that completed execution evidence requires a separate
  higher-level assessment and does not itself prove the parent outcome.
  Analysis outcome: `INFLUENCED`.
  WP021 reverified the current TaskFlow documentation on 2026-09-29. Managed
  flow mutations require the latest expected revision, callers must continue
  from the returned post-mutation record, creation is distinct from execution,
  and waiting and terminal statuses remain explicit. These mechanisms
  influenced strict transition-decision currentness, explicit abstention, and
  refusal to resurrect terminal progress; the durable task-flow runtime was
  not adopted. Analysis outcome: `INFLUENCED`.
  WP022 reverified current TaskFlow webhook documentation on 2026-09-29.
  **FACT:** managed flow mutations carry `expectedRevision`, stale revisions
  return `revision_conflict`, successful record operations remain distinct from
  completed child work, and flow creation has no general idempotency key.
  **INFERENCE:** mutation eligibility must be checked at the application
  boundary, and repeated preparation does not itself provide exactly-once
  behavior. **IRIS DECISION:** WP022 preserves two gates: decision currentness
  before synthesis and `StepProgressUpdate.expected_revision` for the existing
  reducer; duplicate synthesis remains allowed. Analysis outcome: `INFLUENCED`.
- **Known changes:** Not recorded.
- **Influenced decisions:** WP012 keeps tool/runtime outcomes separate from
  PlanObservation and StepProgress transitions; no OpenClaw lifecycle or retry
  implementation was adopted. WP015 separates a known initiating origin from
  the stable identity of the current derived work unit. WP016 keeps Context
  snapshot construction explicit and ephemeral instead of adopting a session
  context-engine lifecycle. WP017 binds each orchestration decision to a stable
  subject identity and an exact ContextSnapshot without adopting session or
  gateway identity as either one. WP018 keeps stable subject identity separate
  from execution-attempt identity and does not adopt a background runtime.
  WP019 records one execution attempt by its execution ID while keeping that
  fact separate from work progress and goal completion. WP020 keeps completion
  evidence separate from an evaluator's PlanStep-level epistemic conclusion.
  WP021 revalidates the exact current Run revision before a transition decision
  can be consumed and keeps waiting/terminal distinctions out of failure
  inference. WP022 carries that revision into an inert update while leaving
  final stale-write rejection to the reducer.
- **Adopted patterns:** Not recorded.
- **Rejected patterns:** Not recorded.
- **License/provenance notes:** Root `LICENSE` declares MIT. The repository also
  maintains `THIRD_PARTY_NOTICES.md`; incorporated or adapted material may have
  additional provenance requirements. No code or assets incorporated into IRIS.
- **General notes:** Registered as a research reference only.

## Letta

- **Name:** Letta
- **Canonical URL:** <https://github.com/letta-ai/letta>
- **Status:** `REGISTERED`
- **Relevant areas:** stateful agents; persistent memory; context management;
  long-term continuity.
- **Date registered:** 2026-09-25
- **Last verified:** 2026-09-25
- **Relevant Work Packages:** Not recorded.
- **Research history:** Initial identity, relevance, and basic provenance review
  during registry initialization on 2026-09-25. No problem-specific analysis
  recorded.
- **Known changes:** The canonical repository currently states that active source
  lives in <https://github.com/letta-ai/letta-code> and that historical V1 source
  remains on its `archive` branch. This is recorded as a related implementation
  change, not as an automatic canonical URL replacement.
- **Influenced decisions:** Not recorded.
- **Adopted patterns:** Not recorded.
- **Rejected patterns:** Not recorded.
- **License/provenance notes:** Canonical repository declares Apache License 2.0
  in the root `LICENSE` file. Reverify the license and provenance of
  `letta-ai/letta-code` separately before studying or using that repository.
  No code or assets incorporated into IRIS.
- **General notes:** Registered as a research reference only.

## Mem0

- **Name:** Mem0
- **Canonical URL:** <https://github.com/mem0ai/mem0>
- **Status:** `REGISTERED`
- **Relevant areas:** agent memory; memory retrieval; memory management;
  personalization.
- **Date registered:** 2026-09-25
- **Last verified:** 2026-09-25
- **Relevant Work Packages:** Not recorded.
- **Research history:** Initial identity, relevance, and basic provenance review
  during registry initialization on 2026-09-25. No problem-specific analysis
  recorded.
- **Known changes:** Not recorded.
- **Influenced decisions:** Not recorded.
- **Adopted patterns:** Not recorded.
- **Rejected patterns:** Not recorded.
- **License/provenance notes:** Repository declares Apache License 2.0 in the
  root `LICENSE` file. No code or assets incorporated into IRIS.
- **General notes:** Registered as a research reference only.

## OmniRoute

- **Name:** OmniRoute
- **Canonical URL:** <https://github.com/arnoldwender/omniroute>
- **Status:** `REGISTERED`
- **Relevant areas:** model routing; provider abstraction; fallback concepts;
  availability; cost-aware routing.
- **Date registered:** 2026-09-25
- **Last verified:** 2026-09-25
- **Relevant Work Packages:** Not recorded.
- **Research history:** Initial identity, relevance, and basic provenance review
  during registry initialization on 2026-09-25. No problem-specific analysis
  recorded.
- **Known changes:** Not recorded.
- **Influenced decisions:** Not recorded.
- **Adopted patterns:** Not recorded.
- **Rejected patterns:** Not recorded.
- **License/provenance notes:** Repository declares MIT in the root `LICENSE`
  file. No code or assets incorporated into IRIS.
- **General notes:** Fallback is an area for research, not an adopted IRIS policy.

## LangGraph

- **Name:** LangGraph
- **Canonical URL:** <https://github.com/langchain-ai/langgraph>
- **Status:** `REVIEWED`
- **Relevant areas:** agent/workflow graphs; state; execution loops;
  checkpoints; durable execution.
- **Date registered:** 2026-09-25
- **Last verified:** 2026-09-29
- **Relevant Work Packages:** WP011; WP012; WP013; WP014; WP015; WP016; WP017;
  WP018; WP019; WP020; WP021; WP022.
- **Research history:** Initial identity, relevance, and basic provenance review
  during registry initialization on 2026-09-25. WP011 reviewed explicit graph
  nodes/edges and their relationship to runtime state on 2026-09-25. IRIS kept
  only a representation-level DAG and did not adopt runtime, checkpoints or
  execution loops. WP012 reused the reference on 2026-09-26 to examine state
  snapshots, checkpoint boundaries, interrupts, and resume semantics. Their
  separation influenced IRIS's decision to model immutable PlanRun revisions
  while excluding checkpoint persistence and resume. Analysis outcome:
  `INFLUENCED`. WP013 reused the reference on 2026-09-27 to review explicit
  super-step advancement, node activation, update boundaries, interrupts, and
  checkpoint boundaries. This influenced the one-decision boundary while IRIS
  continued to exclude graph execution, interrupts, persistence, and resume.
  Analysis outcome: `INFLUENCED`. WP014 reused the reference on 2026-09-27 to
  review its explicit state schema and node-returned state-update boundary.
  This reinforced an immutable preparation result distinct from invocation or
  in-place PlanRun mutation; the graph runtime itself was not adopted. Analysis
  outcome: `INFLUENCED`. WP015 reused the reference on 2026-09-27 to review its
  distinction among invocation input, shared state schema, discrete node work,
  and persistence/thread configuration. This influenced the decision to keep
  `WorkSubject` free of state and revision while preserving a separately typed
  operational reference. No graph or persistence runtime was adopted. Analysis
  outcome: `INFLUENCED`. WP016 reused the current Graph API documentation on
  2026-09-28 to verify that runtime context has its own schema and is passed to
  nodes separately from graph state and invocation input/output schemas. This
  influenced IRIS to generalize Context ownership without absorbing mutable
  PlanRun state or runtime dependencies. Analysis outcome: `INFLUENCED`.
  WP017 reused the current Graph API documentation on 2026-09-28 to reverify
  distinct state, input/output, and runtime-context schemas. This reinforced a
  typed orchestration binding whose subject, exact context snapshot, semantic
  needs, and availability remain separate inputs. No graph runtime, node
  execution, or checkpoint behavior was adopted. Analysis outcome:
  `INFLUENCED`. WP018 reverified the current Graph API and fault-tolerance
  documentation on 2026-09-28. The documented distinction among run identity,
  node attempt, task result, and state update reinforced IRIS's separate
  subject/decision/execution lineage. LangGraph's retries, timeouts,
  checkpointer-backed replay avoidance, and node-driven state progression were
  deliberately postponed. Analysis outcomes: `INFLUENCED` and
  `REJECTED_PATTERN` for those runtime mechanisms in WP018. WP019 reverified
  current fault-tolerance documentation on 2026-09-28. Its separately exposed
  run, task, checkpoint, and node-attempt identities, plus typed failure context
  before an error handler updates state or routes elsewhere, reinforced
  preserving raw execution evidence before interpretation. Automatic retries,
  checkpoint-backed recovery, error-handler state updates, and routing were
  rejected for the observation adapter. Analysis outcomes: `INFLUENCED` and
  `REJECTED_PATTERN`. WP020 reviewed current LangSmith evaluation documentation
  in the LangGraph ecosystem on 2026-09-28. Its code evaluators,
  reference-based comparisons, and LLM-as-judge evaluators demonstrate
  replaceable evaluation mechanisms applied to recorded run outputs. IRIS
  adopted only the evaluator separation: managed tracing, feedback attachment,
  automatic evaluation, scoring, routing, and state mutation remain outside
  WP020. Analysis outcomes: `INFLUENCED` and `REJECTED_PATTERN`.
  WP021 reverified current persistence, checkpointer, `StateSnapshot`, and
  `update_state` documentation on 2026-09-29. LangGraph preserves historical
  checkpoints and creates a new checkpoint for a state update rather than
  changing the original snapshot. This influenced IRIS's distinct historical
  assessment lineage and strict decision currentness. IRIS explicitly rejected
  combining evaluation/control, state update, and routing in one Command-like
  runtime primitive. Analysis outcomes: `INFLUENCED` and `REJECTED_PATTERN`.
  WP022 reverified current persistence, checkpointer, `StateSnapshot`, and
  `update_state` documentation on 2026-09-29. **FACT:** `update_state` creates a
  new checkpoint rather than modifying the original, applies configured
  reducers, and records update attribution in snapshot metadata; graph nodes
  may otherwise combine state update with next-node routing. **INFERENCE:** a
  prepared state update and its later application are useful distinct lineage
  points. **IRIS DECISION:** WP022 emits only `StepProgressUpdate` with
  transition-decision provenance and rejects checkpoint persistence,
  update-plus-routing primitives, and automatic graph progression. Analysis
  outcomes: `INFLUENCED` and `REJECTED_PATTERN`.
- **Known changes:** Not recorded.
- **Influenced decisions:** WP012 separates operational Run snapshots from
  checkpoints, persistence, interrupts, and autonomous graph execution. WP013
  makes control advancement explicit and one-shot without adopting a graph
  runtime or super-step executor. WP014 returns a new typed preparation value
  without mutating PlanRun or invoking a runtime. WP015 separates operational
  subject identity from mutable workflow state and original input. WP016 keeps
  WorkSubject-owned evidence Context separate from PlanRun state and runtime
  dependency configuration. WP017 keeps subject identity separate from the
  exact contextual observation and from the decision instance identity. WP018
  keeps one explicit execution attempt separate from work identity and refuses
  to claim global exactly-once behavior without persistence. WP019 uses
  execution-attempt identity as the observation source reference while leaving
  state advancement to an explicit later reducer update. WP020 keeps
  deterministic and model-backed evaluation as replaceable mechanisms while
  leaving evidence selection and state progression outside the evaluator.
  WP021 keeps assessment applicability, policy output, decision lineage, and a
  future reducer update as separate contracts. WP022 fills only the
  decision-to-update seam and still leaves reducer application external.
- **Adopted patterns:** Not recorded.
- **Rejected patterns:** WP019 rejects retry, checkpoint recovery, automatic
  state update, and error-handler routing inside execution evidence recording.
  WP020 rejects attaching managed evaluation feedback to workflow state or
  coupling assessment to retry/routing behavior. WP021 rejects a combined
  update-and-routing primitive and does not adopt checkpoint persistence,
  interrupt/resume, or automatic graph progression.
- **License/provenance notes:** Repository declares MIT in the root `LICENSE`
  file. Hosted or commercial offerings may have separate terms and are outside
  this repository-level review. No code or assets incorporated into IRIS.
- **General notes:** Registration does not introduce an execution loop,
  checkpointing, or durable workflow into IRIS.

## Microsoft Agent Framework

- **Name:** Microsoft Agent Framework
- **Canonical URL:** <https://github.com/microsoft/agent-framework>
- **Status:** `REVIEWED`
- **Relevant areas:** agents; workflows; execution; multi-agent architecture;
  observability; human-in-the-loop; durability.
- **Date registered:** 2026-09-25
- **Last verified:** 2026-09-29
- **Relevant Work Packages:** WP011; WP012; WP013; WP014; WP015; WP016; WP017;
  WP018; WP019; WP020; WP021; WP022.
- **Research history:** Initial identity, relevance, and basic provenance review
  during registry initialization on 2026-09-25. WP011 reviewed graph-based
  workflows, explicit execution paths, and the distinction between agents and
  deterministic workflow functions on 2026-09-25. IRIS retained a
  provider-independent Planner and excluded workflow runtime behavior. Analysis
  outcome: `REVIEWED`. WP012 reused the reference on 2026-09-26 to review
  workflow state, checkpoints/resume, and request/response human-in-the-loop
  boundaries. This influenced the decision to keep PlanRun state independent
  from checkpoint, approval, and external-request machinery. Analysis outcome:
  `INFLUENCED`. WP013 reused the reference on 2026-09-27 to review workflow
  super-step completion, state isolation, checkpoints, and request/response
  waiting. Explicit advancement boundaries and waiting as a state distinct from
  failure influenced the typed control outcomes, while execution, HITL, and
  checkpoints remained excluded. Analysis outcome: `INFLUENCED`. WP014 reused
  the reference on 2026-09-27 to review typed executor messages and explicit
  workflow executor invocation. Typed compatibility at the preparation
  boundary influenced the separate `StepHandlingSpecification` and result
  contracts; no workflow runtime or executor invocation was adopted. Analysis
  outcome: `INFLUENCED`. WP015 reused the reference on 2026-09-27 to review
  uniquely identified executors processing typed workflow messages and the
  distinction between external workflow interaction and internal processing
  units. This influenced typed WorkSubject references and strict kind/reference
  compatibility without adopting its workflow runtime. Analysis outcome:
  `INFLUENCED`. WP016 reused current Microsoft Learn workflow documentation on
  2026-09-28 to review typed executor messages, separately shared workflow
  state, and checkpoint/observability capabilities. This reinforced explicit
  Context ownership while keeping evidence snapshots separate from workflow
  state, execution, checkpoints, and tracing. Analysis outcome: `INFLUENCED`.
  WP017 reused current executor, edge, and workflow documentation on 2026-09-28
  to review typed message flow and the boundary where a workflow runtime
  actually invokes executors. Typed compatibility influenced the explicit
  WorkSubject/Context/HandlingNeed binding; IRIS stopped before executor
  invocation, routing runtime, streaming, or durability. Analysis outcome:
  `INFLUENCED`. WP018 reverified current executor, workflow-execution,
  checkpoint, and durable-extension documentation on 2026-09-28. Typed
  executor input/output and distinct executor identity influenced the rich
  validation envelope plus lightweight result lineage. Checkpoints, durable
  cached completion, event streaming, and automatic workflow progression were
  reviewed but postponed. Analysis outcomes: `INFLUENCED` and
  `REVIEWED`/postponed for durability. WP019 reverified current executor and
  workflow-event documentation on 2026-09-28. Distinct executor-completed,
  executor-failed, intermediate-output, terminal-output, and workflow-lifecycle
  events reinforced treating completion facts as observable data separate from
  workflow-level progression. IRIS did not adopt the event stream, custom event
  bus, checkpoints, or durable workflow runtime. Analysis outcomes:
  `INFLUENCED` and `REVIEWED`/postponed for durability. WP020 reverified the
  current Agent Framework Evaluation documentation on 2026-09-28. Its distinct
  `EvalItem`, evaluator, and aggregated result concepts, plus local custom
  checks and Foundry-backed evaluators, influenced IRIS's provider-independent
  evaluator contract and explicit evaluator reference. Foundry services,
  aggregate scoring, mandatory pass/fail, and workflow advancement were not
  adopted. Analysis outcome: `INFLUENCED`.
  WP021 reverified current workflow checkpoint documentation on 2026-09-29.
  Agent Framework creates checkpoints at super-step boundaries after executor
  completion and captures executor, pending-message/request, and shared state
  for explicit resume. This reinforced an explicit consistent-state boundary
  between assessment, decision, and later mutation. IRIS did not adopt its
  checkpoint storage, resume, or workflow runtime. Analysis outcome:
  `INFLUENCED`.
  WP022 reverified current workflow state and checkpoint documentation on
  2026-09-29. **FACT:** workflow state updates have explicit visibility timing,
  and checkpoints capture executor, pending-message/request, and shared state
  at super-step boundaries for later resume. **INFERENCE:** state materialization
  belongs to an explicit consistent-state boundary rather than to an earlier
  epistemic result. **IRIS DECISION:** WP022 constructs an inert update with
  immediate decision provenance but does not adopt shared workflow state,
  checkpointing, resume, storage, or the Agent Framework runtime. Analysis
  outcome: `INFLUENCED`.
- **Known changes:** Record as a related project when assessing the evolution or
  conceptual succession of AutoGen ideas. No equivalence between the projects is
  assumed.
- **Influenced decisions:** WP012 models deterministic progress state without
  adopting workflow execution, checkpointing, or human-in-the-loop runtime.
  WP013 represents one deterministic control outcome without treating pending
  or unresolved work as failure and without advancing a workflow runtime.
  WP014 validates explicit typed handling detail and returns a semantic need
  without invoking an executor. WP015 uses typed operational references rather
  than treating the initiating input as every downstream unit's identity.
  WP016 keeps subject-scoped Context distinct from shared workflow state and
  runtime operations. WP017 makes OrchestrationInput a typed binding boundary
  while keeping executor invocation and workflow progression outside it. WP018
  adds a typed side-effect binding and result lineage without adopting the
  surrounding workflow runtime, checkpoints, or automatic advancement. WP019
  records one raw completion result as evidence without equating an executor
  event with PlanStep progress. WP020 introduces a replaceable evaluator over
  explicit canonical evidence while retaining an inert assessment result and
  no progress transition. WP021 adds a separate current-state applicability and
  operational-decision layer while continuing to defer mutation to a later
  explicit update/reducer boundary. WP022 materializes that decision as an
  existing typed update while preserving reducer ownership of mutation.
- **Adopted patterns:** Not recorded.
- **Rejected patterns:** Not recorded.
- **License/provenance notes:** Repository declares MIT in the root `LICENSE`
  file. Integrations and third-party systems retain their own terms. No code or
  assets incorporated into IRIS.
- **General notes:** Registered as a distinct reference from AutoGen.

## AutoGen

- **Name:** AutoGen
- **Canonical URL:** <https://github.com/microsoft/autogen>
- **Status:** `CHANGED`
- **Relevant areas:** multi-agent systems; agent communication; delegation;
  distributed runtime; historical Microsoft agent architecture.
- **Date registered:** 2026-09-25
- **Last verified:** 2026-09-25
- **Relevant Work Packages:** WP011.
- **Research history:** Initial identity, relevance, and basic provenance review
  during registry initialization on 2026-09-25. WP011 reviewed task
  decomposition and agent-conversation approaches on 2026-09-25. Conversational
  multi-agent decomposition was rejected for the deterministic, representation-
  only WP011 foundation. Analysis outcome: `REJECTED_PATTERN`.
- **Known changes:** Microsoft Agent Framework must be considered when studying
  the evolution or conceptual succession of some AutoGen ideas. This does not
  establish equivalence or automatic replacement. On 2026-09-25 the canonical
  repository declared maintenance mode and directed new users toward Microsoft
  Agent Framework; historical conclusions should account for that status.
- **Influenced decisions:** Not recorded.
- **Adopted patterns:** Not recorded.
- **Rejected patterns:** WP011 rejected model-driven, multi-agent conversation as
  the mandatory mechanism for constructing the foundational Plan contract.
- **License/provenance notes:** GitHub identifies the root `LICENSE` as
  CC-BY-4.0, while code packages contain separate `LICENSE-CODE` files that
  declare MIT. Treat the repository as mixed-scope and verify the exact file and
  version before any reuse. No code or assets incorporated into IRIS.
- **General notes:** Registered as a distinct reference from Microsoft Agent
  Framework.

## PersonalJarvis

- **Name:** PersonalJarvis
- **Canonical URL:** <https://github.com/PersonalJarvis/PersonalJarvis>
- **Status:** `REGISTERED`
- **Relevant areas:** personal assistant; desktop interaction; voice; agents;
  desktop actions; plugins; user experience.
- **Date registered:** 2026-09-25
- **Last verified:** 2026-09-25
- **Relevant Work Packages:** Not recorded.
- **Research history:** Initial identity, relevance, and basic provenance review
  during registry initialization on 2026-09-25. No problem-specific analysis
  recorded.
- **Known changes:** Project documentation records a license change on
  2026-08-27: releases through 1.6.0 remain MIT and the 2.x line is Apache-2.0.
- **Influenced decisions:** Not recorded.
- **Adopted patterns:** Not recorded.
- **Rejected patterns:** Not recorded.
- **License/provenance notes:** Current root `LICENSE` declares Apache License
  2.0 and the repository includes `NOTICE`; historical releases through 1.6.0
  remain MIT. Bundled components may retain separate licenses. No code or assets
  incorporated into IRIS.
- **General notes:** Registered as a research reference only.

## Particle Interaction - wonderstone

- **Name:** Particle Interaction - wonderstone
- **Canonical URL:** <https://github.com/wonderstone/particle-interaction>
- **Status:** `REGISTERED`
- **Relevant areas:** gesture interaction; hand tracking; MediaPipe; Three.js;
  particles; spatial/visual interfaces; future multimodal IRIS interaction.
- **Date registered:** 2026-09-25
- **Last verified:** 2026-09-25
- **Relevant Work Packages:** Not recorded.
- **Research history:** Initial identity, relevance, and basic provenance review
  during registry initialization on 2026-09-25. No problem-specific analysis
  recorded.
- **Known changes:** This reference previously suffered link confusion during
  research. Future URL, owner, or implementation changes must be corroborated
  against repository identity before replacing the canonical URL.
- **Influenced decisions:** Not recorded.
- **Adopted patterns:** Not recorded.
- **Rejected patterns:** Not recorded.
- **License/provenance notes:** No license was recorded at the repository root
  during verification. Treat permission as unknown; do not copy code or assets.
- **General notes:** Preserve prior URL evidence in `Known changes` if a future
  correction is verified. Registration does not implement gesture, vision, or
  particle interaction in IRIS.

## Explicit exclusions

- <https://github.com/fermaxvago/IRIS> is the target project, not an external
  research reference, and is intentionally excluded from this registry.
- No entry above introduces code, assets, dependencies, submodules, vendoring,
  architecture changes, or Work Package scope.
- No reference above has an adopted or rejected pattern until a named analysis
  explicitly records that outcome.
