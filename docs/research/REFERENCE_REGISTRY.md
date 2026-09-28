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
- **Last verified:** 2026-09-28
- **Relevant Work Packages:** WP011; WP012; WP013; WP014; WP015; WP016.
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
- **Known changes:** Not recorded.
- **Influenced decisions:** Not recorded.
- **Adopted patterns:** Not recorded.
- **Rejected patterns:** WP013 rejects an agent/tool, scheduled, or continuous
  loop as the foundational PlanRun control API; one call produces one decision
  and stops. WP014 rejects a model/tool loop as a source of implicit handling
  detail or execution. WP016 rejects automatic agent-runtime context enrichment
  as a replacement for explicit evidence submission and bounded selection.
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
- **Last verified:** 2026-09-28
- **Relevant Work Packages:** WP011; WP012; WP013; WP014; WP015; WP016.
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
  lifecycle. Analysis outcome: `REVIEWED`.
- **Known changes:** Not recorded.
- **Influenced decisions:** WP012 keeps tool/runtime outcomes separate from
  PlanObservation and StepProgress transitions; no OpenClaw lifecycle or retry
  implementation was adopted. WP015 separates a known initiating origin from
  the stable identity of the current derived work unit. WP016 keeps Context
  snapshot construction explicit and ephemeral instead of adopting a session
  context-engine lifecycle.
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
- **Last verified:** 2026-09-28
- **Relevant Work Packages:** WP011; WP012; WP013; WP014; WP015; WP016.
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
- **Known changes:** Not recorded.
- **Influenced decisions:** WP012 separates operational Run snapshots from
  checkpoints, persistence, interrupts, and autonomous graph execution. WP013
  makes control advancement explicit and one-shot without adopting a graph
  runtime or super-step executor. WP014 returns a new typed preparation value
  without mutating PlanRun or invoking a runtime. WP015 separates operational
  subject identity from mutable workflow state and original input. WP016 keeps
  WorkSubject-owned evidence Context separate from PlanRun state and runtime
  dependency configuration.
- **Adopted patterns:** Not recorded.
- **Rejected patterns:** Not recorded.
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
- **Last verified:** 2026-09-28
- **Relevant Work Packages:** WP011; WP012; WP013; WP014; WP015; WP016.
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
  runtime operations.
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
