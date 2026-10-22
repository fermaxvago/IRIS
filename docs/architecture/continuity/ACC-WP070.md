# IRIS — ARCHITECTURE CONTINUITY CHECKPOINT — ACC-WP070

**Represented canonical `main`:** `721f088c5a9728cac5ce923688300d219242f678`

**Checkpoint date:** 2026-10-22

**Previous checkpoint:** [ACC-WP065](ACC-WP065.md)

**Succession foundation:** [ARCHITECT-SUCCESSION-FOUNDATIONS](ARCHITECT-SUCCESSION-FOUNDATIONS.md)

## 0. How to read this checkpoint

This is an immutable historical photograph of IRIS **after the canonical WP070
merge and before this documentation commit**. The ACC-WP070 documentation
commit and any later merge are not part of the represented state.

- **FROZEN** identifies responsibility boundaries and contracts established by
  accepted history and still supported by the represented source.
- **CURRENT** identifies facts verified specifically at
  `721f088c5a9728cac5ce923688300d219242f678`.
- **FORWARD** identifies open questions, risks or non-binding hypotheses. It is
  not implementation authorization.

Canonical source and Git objects outrank PR prose, tests, reports and design
history. Tests establish their exercised cases, not universal correctness.
This checkpoint records architecture; it creates no runtime, publication,
merge, successor-Architect or future-Work-Package authority.

# PART I — CANONICAL ANCHOR AND GIT LINEAGE

## 1. Represented commit

**CURRENT:** fetched `origin/main` resolved exactly to
`721f088c5a9728cac5ce923688300d219242f678`. Its tree is
`99ec8e756f44073defb7f93bc0429414e594f741`; its parents, in order, are:

1. `c5bfdca1e78954c8f05e32b03190bd710849f871` — canonical post-WP069 main.
2. `9e67431c5f8ab7a75a70fd8e65787f742927f88f` — accepted WP070 implementation.

The implementation and merge trees are identical. GitHub reports PR #79,
`WP070 — Bounded Conversational Diagnostics and Operational Acceptance`, as
merged. Post-merge workflow run
[`39850515127`](https://github.com/fermaxvago/IRIS/actions/runs/39850515127)
has event `push`, exact head
`721f088c5a9728cac5ce923688300d219242f678`, completed status and `success`
conclusion. Its quality job passed tests, Ruff lint, Ruff formatting, strict
mypy, wheel build and source-distribution build.

At the represented commit, `LATEST.md` still points to ACC-WP065 and this file
does not exist. Updating those documents is later checkpoint publication, not
part of the photograph.

## 2. Verified integration lineage

The following consecutive first-parent sequence was reconstructed from local
commit, parent and tree objects and cross-checked against GitHub PR metadata.
For every row, the implementation commit has the stated base as its sole
parent; the merge parents are exactly **base, implementation**; and the
implementation and merge trees are equal. No unexplained first-parent
integration appears in this interval.

| Stage | PR and verified title | Base / first parent | Implementation / second parent | Canonical merge | Implementation and merge tree |
| --- | --- | --- | --- | --- | --- |
| ACC-WP065 | #74 `ACC-WP065 — Architecture Continuity Checkpoint` | `7f60284a6a1eec4dab6776a825803d23c30b1b84` | `ab8c2a8b337e55ac9435351f879069022962466d` | `a690d38aa67a7c672d194646ec57d6a5a4a59c11` | `95cd14c580fd09e60b22dcf569df597812024a57` |
| WP066 | #75 `WP066 — Bounded Conversational System Awareness` | `a690d38aa67a7c672d194646ec57d6a5a4a59c11` | `b35b469e4db434ed8b367aa517c8e15b896e9a8b` | `ea251c84d5eef5969e43b2df6d64a0ddf864085d` | `e6775c9f9ad974409ae5840ea9c19de7c43e76dc` |
| WP067 | #76 `WP067 — Bounded Conversational Generation Control` | `ea251c84d5eef5969e43b2df6d64a0ddf864085d` | `14f0b9494940734dd89e04af12316a23e92c313f` | `d08e88363d43734a3580de7cfec580e646ca6089` | `401142021457065aabe0426f29d8081da7101966` |
| WP068 | #77 `WP068 — Bounded Natural-Language Capability Intent Recognition` | `d08e88363d43734a3580de7cfec580e646ca6089` | `41b6563fd5325686f1eddec25114bdbde5588f98` | `10063b58966de668ccb10b4232b2ef2c3f34d4fb` | `cd7f4e86d92262430ab2c3114dba0e0afd0fb7db` |
| WP069 | #78 `WP069 — Authorized Atomic Conversational Rollover` | `10063b58966de668ccb10b4232b2ef2c3f34d4fb` | `cb9470f39638717be7c67577b0be88887363d268` | `c5bfdca1e78954c8f05e32b03190bd710849f871` | `45ea8f968203756f35a58fa87b667ef6ce7c6ddb` |
| WP070 | #79 `WP070 — Bounded Conversational Diagnostics and Operational Acceptance` | `c5bfdca1e78954c8f05e32b03190bd710849f871` | `9e67431c5f8ab7a75a70fd8e65787f742927f88f` | `721f088c5a9728cac5ce923688300d219242f678` | `99ec8e756f44073defb7f93bc0429414e594f741` |

All six PRs are reported by GitHub as merged. Equal trees establish equal file
content, not equal commit, review or lifecycle identity:

```text
implementation commit
    != pull request
    != synthetic PR test merge
    != canonical merge commit
    != represented historical state
    != later checkpoint documentation commit
```

The represented state is the canonical WP070 merge, not a synthetic Actions
checkout and not the future ACC-WP070 documentation merge.

# PART II — FROZEN ARCHITECTURAL FOUNDATION

## 3. Responsibility walls retained from ACC-WP065

**FROZEN:** [ACC-WP065](ACC-WP065.md) remains the full historical treatment of
the earlier foundations. Canonical source at the represented commit continues
to support these distinctions:

| Distinction | Consequence |
| --- | --- |
| Routing != Execution | A route or candidate selection does not invoke an operation. |
| Planning != Plan Execution | Constructing a Plan does not perform a PlanStep. |
| Selection != Activation | Selection does not itself make work active. |
| ExecutionRequest != ExecutionBinding | Request materialization and exact lineage binding remain separate. |
| ExecutionBinding != Authorization | Binding witnesses identity/lineage; it is not general permission. |
| Authorization != Execution | An admitted operation still requires its execution authority. |
| ExecutionResult != PlanObservation | Operational output and canonical Plan evidence remain distinct. |
| Observation != Assessment | Recorded evidence does not itself establish an outcome. |
| Assessment != Transition Decision | Interpretation does not itself choose progress. |
| Transition Decision != Progress Update | Decision and synthesized update remain distinct. |
| Progress Update != Updated PlanRun | An update does not itself create the next Run. |
| Updated PlanRun != Fresh ControlDecision | Changed state requires fresh control evaluation. |
| Currentness != Identity | Equal identifiers cannot replace revision/currentness checks. |
| Structural Completion != Goal Satisfaction | Completed structure does not prove the Goal is satisfied. |
| Domain-valid != Canonically reachable | A valid value may still be causally invalid. |
| Invocation-local exactly-once != Durable exactly-once | Local call guards are not distributed idempotency. |

The conversational boundaries established through WP065 also remain:

```text
model discovery != model selection
model recommendation != human confirmation
model confirmation != inference
conversation history != ContextSnapshot
context eligibility != disclosure approval
disclosure proposal != authorization
approval != authentication
approval consumption != durable permission
contextual data != system instructions
information access != execution authority
model output != permission to act
temporary conversation != persistent memory
declared local model != independently proven physical locality
Linux CI success != physical deployment validation
```

## 4. Additional conversational walls through WP070

**FROZEN:** WP066–WP070 add composition, generation control, bounded
recognition, rollover and inspection without collapsing their authorities:

| Distinction | Verified consequence |
| --- | --- |
| Local observation != model disclosure | `system.status` may produce a reading; a separate exact proposal and approval govern disclosure. |
| Point-in-time measurement != diagnosis | CPU/RAM values do not prove pressure, cause or continuing health. |
| Recognized intent != authorized observation | A deterministic match only permits the CLI to ask for consent. |
| Authorized observation != authorized disclosure | Natural-language consultation has two independent decisions. |
| Direct mode != fallback policy | `--direct` is explicit and bound to the selected compatible Ollama model. |
| Prepared window != committed history | Candidate suffix selection is side-effect free. |
| Provider response != committed turn | Local validation and atomic commit still follow generation. |
| Active turn count != session revision | Rollover can advance state while retaining eight pairs. |
| Continuity consent != observation/disclosure consent | Eviction policy grants no capability or context authority. |
| Bound model != available model | Session identity does not establish current provider health. |
| Diagnostic inspection != monitoring | `/diagnostico` reads bounded session metadata only. |
| Retained characters != token count | Character accounting does not guarantee model-window fit. |

Nothing in WP066–WP070 adds autonomous tools, persistent telemetry, hidden
conversation archives, automatic retry/model switching or durable recovery.

# PART III — WP066 SYSTEM AWARENESS

## 5. One bounded resource observation

**CURRENT:** WP066 added
[`ConversationalSystemAwareness`](../../../iris/intelligence/system_awareness.py)
as a composition layer over existing authorities. It calls the registered
`system.status` capability through `CapabilityRuntime` with
`output_mode="structured"`; it does not call `get_system_info()` directly and
does not introduce another observer.

[`SystemStatusTool`](../../../iris/capabilities/system_status.py) preserves its
default text output for `estado`. The explicit structured mode performs the
same single capture and returns a typed `SystemResourceObservation` containing:

- `cpu_percent` — total CPU utilization percentage;
- `ram_used_gb` — used physical memory in GiB; and
- `ram_total_gb` — total physical memory in GiB.

The capability rejects unsupported modes, booleans as numeric values,
non-finite or out-of-range readings, nonpositive total RAM and used RAM greater
than total RAM beyond the source's documented `0.01` GiB rounding tolerance.
Missing or invalid fields remain explicit; they are not converted to zero.

## 6. Canonical context and disclosure

A complete observation creates a fresh `WorkSubject` of type `REQUEST`, one
session-scoped `MemoryScope`, three required `ContextCandidate` values and
system evidence referencing `system.status`. Each item is `RESOURCE`,
`OBSERVED`, `CURRENT`, explicitly relevant and timestamped with the capture
time. `ContextEngine` receives `ContextBudget(max_items=3)` and must return the
exact nonempty, conflict-free, uncertainty-free `RESOLVED` snapshot with no
budget exclusions.

The CLI command `/recursos <pregunta>` uses this composition. It displays the
validated values, capture time, source, destination and the exact serialized
context proposal before asking for disclosure approval. A bare `/recursos`
takes no reading. An incomplete observation can be displayed locally but
cannot become a misleading contextual proposal. `ConversationContextBinder`
retains ownership of one-use exact disclosure approval; successful inference
still commits only one validated pair through `ConversationSession`.

The reading is not monitoring, health diagnosis, modification authority or
persistent telemetry. WP066's reported physical Ollama attempts reached the
selected model but returned `incomplete_generation` under the unchanged
256-token bound; history remained unchanged. That historical result is not a
permanent statement about the represented implementation.

# PART IV — WP067 GENERATION CONTROL

## 7. Explicit Ollama direct mode

**CURRENT:** WP067 added opt-in `--direct` for both `chat --model` and
`chat --select`. Standard mode omits Ollama's `think` field. Direct mode sets
top-level `"think": false` while preserving `stream: false`, canonical message
serialization and `options.num_predict` at the request's maximum of 256.
No control string or privileged role is inserted.

[`OllamaProvider.verify_direct_model()`](../../../iris/intelligence/providers/ollama.py)
first verifies the exact selected identity through installed model discovery,
then calls `/api/show` for that model. The `thinking` value must be an object,
`values` must be a nonempty list of actual booleans or nonempty strings, its
`default` must be a supported actual boolean/string, and boolean `False` must
be explicitly present. Numeric `0`, string `"false"`, absent metadata and named
levels alone do not authorize boolean direct mode.

Compatibility is checked before the CLI session begins and immediately before
each direct chat request. Provider configuration is local to that CLI instance;
there is no global mutation, automatic fallback, retry or model replacement.
A revalidation failure prevents inference, including contextual transmission.

## 8. Completion and bounded diagnostics

The provider accepts chat success only when the exact response model matches,
`done` is true, optional `done_reason` is absent or `stop`, the role is
`assistant`, no tool calls exist and final content is nonblank. Length or other
explicit termination, `done=false`, thinking-only output, tool calls and
malformed responses fail.

Operational results preserve validated provider metadata such as
`ollama.done_reason`, `ollama.eval_count` and `ollama.prompt_eval_count` where
available. They do not preserve hidden thinking or contextual JSON and do not
prove why generation stopped. Failure classes remain distinct, including
provider unavailability, timeout, protocol error, incomplete generation,
model absence and unsupported direct mode.

Engineer-reported physical evidence for WP067 includes successful standard and
direct greetings and one complete direct `/recursos` response on local Windows
with `qwen3:8b`. It demonstrates those bounded observations only; it is not
general provider-reliability or factual-correctness evidence.

# PART V — WP068 NATURAL-LANGUAGE INTENT

## 9. Conservative Spanish resource recognition

**CURRENT:** [`recognize_resource_intent()`](../../../iris/intelligence/resource_intent.py)
is a deterministic, side-effect-free rule over the current direct human input.
It returns `MATCH`, `AMBIGUOUS` or `NO_MATCH`. It performs limited case,
accent, whitespace and punctuation normalization for comparison while
preserving the original question for any later consultation.

The recognizer has no registry, runtime, context, history, memory, filesystem,
network or model access. A CPU/RAM keyword alone is insufficient. Explicit
negation, hypothetical/educational wording, quotations, foreign-device
references, modification verbs and compound unauthorized actions abstain.
This is a narrow Spanish pattern recognizer, not general language understanding
or a capability router.

## 10. Two independent human decisions

The CLI handles controls in precedence order before recognition. Explicit
`/recursos` enters the existing consultation directly. A natural-language
`MATCH` only prompts for a fresh local-observation decision; only trimmed,
case-insensitive `si` or `sí` authorizes one capture. `AMBIGUOUS` may ask one
clarification and must still obtain the observation decision. Other responses,
EOF and interruption fail closed.

The recognized path and explicit command share `_resource_consultation`; no
second consultation implementation exists. After observation, the unchanged
WP065/WP066 preview and separate exact disclosure approval still apply. A
denial or failed provider call commits no turn. Unknown slash commands and
ordinary text retain ordinary conversation treatment. Engineer-reported WP068
physical evidence includes preliminary denial without capture and a later
separately approved natural-language observation/disclosure with a complete
direct-model response; this remains one environment-specific demonstration.

# PART VI — WP069 ATOMIC ROLLOVER

## 11. Session-local continuity policy

**CURRENT:** `ConversationSession` owns a process-local continuity flag that is
disabled by default. The CLI exposes `/continuidad estado`, `activar` and
`desactivar`. Activation permits future bounded rollover; deactivation cannot
restore retired messages. `/reiniciar` clears active history, disables
continuity, advances generation and revision, and invalidates earlier state.
No policy or transcript persists across sessions.

The numerical limits remain:

| Contract | Maximum |
| --- | ---: |
| Retained completed user/assistant pairs | 8 |
| Current user message | 2,000 characters |
| Active/transmitted conversation | 6,000 characters |
| Requested output | 256 tokens |
| Context items | 8 |
| Serialized context section | 1,500 characters |

These character limits are not tokenizer guarantees.

## 12. Candidate, inference and commit windows

`ConversationSession.prepare_window()` selects an immutable
`ConversationWindow` under the existing nonblocking lock. It validates the
current message and context, begins with confirmed history and, only when
continuity is enabled, removes the fewest oldest complete pairs needed to
produce the longest valid recent suffix. It preserves chronological order and
the exact current user content. Preparation does not mutate confirmed history.

`send()` revalidates and builds a public `ConversationRequest`, invokes
`IntelligenceRuntime`, validates the result and then may retire additional
oldest complete pairs if the full assistant response needs more room. The
final history is a suffix of the inference candidate followed by the complete
new pair. If the new pair cannot fit alone, or provider/result validation
fails, history, revision and eviction feedback remain unchanged. There is no
truncation, summarization, retry or secondary archive.

Successful commits and policy changes advance a monotonic session revision;
reset also advances generation. Equal active turn counts therefore do not
identify equal session states.

## 13. Exact contextual binding under rollover

`ConversationContextBinder` obtains the candidate from the session rather than
maintaining a competing window-selection algorithm. A proposal binds exact
session object/ID, generation, revision, continuity policy, provider/model,
content, snapshot, subject, item IDs, scopes and the immutable prepared history
window. A structural seal includes the exact message roles/content, context
section and retired-turn count.

Consumption revalidates the current candidate under the session's send lock.
Any intervening successful turn, rollover, reset, policy transition,
destination/content/window substitution, expiration or prior consumption fails
closed. Resource consultation preflights a deterministically known session
limit before hardware capture. Continuity approval never becomes observation,
disclosure or tool approval.

Engineer-reported WP069 physical evidence includes ninth and tenth turns with
explicit continuity, application-generated eviction feedback, one separately
approved contextual resource turn, later deactivation and reset. Retired
messages are not recoverable in-session; the evidence does not establish
durable recovery or general performance.

# PART VII — WP070 CONVERSATIONAL DIAGNOSTICS

## 14. Immutable diagnostic snapshot

**CURRENT:** WP070 introduced the frozen, slotted
[`ConversationDiagnosticSnapshot`](../../../iris/intelligence/conversation.py)
with exactly these fields:

```text
provider_id
model_id
active_turns
active_characters
continuity_enabled
revision
generation
```

`ConversationSession.diagnostic_snapshot()` acquires the session's existing
lock with `blocking=False`, reads one coherent state, constructs the immutable
content-free value and releases the lock. A busy session raises the existing
`ConversationBusyError`; there is no wait, retry, fallback read or partial
snapshot. Previously returned snapshots do not change after later session
mutation.

The operation does not mutate messages, policy, revision, generation or last
commit evictions. It does not call inference, system observation, context
binding or persistence. It includes no transcript, session ID, authorization,
context payload, hardware value, raw provider response, path, credential,
thinking content or provider-health claim.

## 15. `/diagnostico` command

The exact `/diagnostico` command is handled in the chat loop before reset,
continuity, resource intent or ordinary inference. It displays terminal-safe
provider/model identifiers, retained pair and character counts, continuity
policy, revision and generation, and explicitly states that current
provider/model availability was not checked. The CLI uses canonical
`MAX_PREVIOUS_TURNS` and `MAX_CONTEXT_CHARACTERS`; it does not duplicate limits.

Active characters are the sum of retained message content only. They are not
token counts, contextual overhead or guaranteed future capacity. The command
does not contact Ollama, inspect CPU/RAM, consume approval, commit a turn,
change policy, reset state or save diagnostics. Control characters in
provider/model identifiers are escaped through the established terminal-safety
path. A busy session receives a bounded explanation and no stale snapshot.

## 16. Bounded failure transparency

WP070 reuses existing typed failures and result metadata. `_failure_explanation`
maps only an allowlist of known `failure_kind` values to bounded Spanish
explanations: `provider_unavailable`, `timeout`, `incomplete_generation`,
`unsupported_direct_mode`, `protocol_error` and `model_not_found`. Missing,
malformed or unknown categories receive generic language rather than promoted
untrusted prose.

Generation diagnostics expose only validated `stop`/`length` reasons and
bounded nonboolean integer counters. They never print raw payloads, prompts,
context JSON or thinking content. Presentation does not change failure class,
retry, switch models, repair Ollama, consume another approval or turn failure
into success. A failed inference commits no conversational pair, while provider
computation may nevertheless have occurred and is not claimed rolled back.

## 17. Operational acceptance evidence

Focused tests exercise snapshot immutability and historical stability,
nonblocking busy behavior, no partial reads, read-only CLI effects, privacy,
terminal escaping, allowlisted/unknown failure presentation, inspection before
and after commits, rollover, reset and context-approval isolation. Existing
regressions preserve command routing and WP063–WP069 boundaries.

WP070's physical Windows smoke inspected initial state, continuity activation,
revision change and reset/generation change, then exited. It made no model
request or hardware observation; it therefore verifies the CLI inspection
surface, not Ollama health or physical inference reliability.

# PART VIII — CUMULATIVE AUTHORITY MAP

## 18. Current ownership matrix

| Responsibility | Canonical owner | What it owns | Mutates / invokes / persists |
| --- | --- | --- | --- |
| Provider registration and discovery | `ProviderRegistry`; provider `list_models()` | Explicit provider identities and point-in-time descriptors | Registry setup; no inference or inventory persistence |
| Deterministic model routing | `CandidateResolver`, `DeterministicRoutingPolicy`, intelligence router | Need/resource evaluation and route status | No model invocation or permission grant |
| Conversation route proposal/binding | `ConversationRouteBinder` | Discovery adaptation, proposal, confirmation revalidation and exact session creation | Creates a temporary session; no inference during proposal/bind |
| Provider execution | `IntelligenceRuntime` and selected provider | Destination/capability validation and provider transport | May invoke external model; grants no tools |
| Active conversation history | `ConversationSession` | Confirmed complete pairs, reset and atomic commit | Process-local mutation; no persistence |
| Rollover and revision | `ConversationSession` | Candidate suffix, final retained window, continuity flag, revision/generation | Mutates only on successful commit or explicit transition |
| Context evidence construction | `ContextEngine` and canonical context models | Subject-scoped selection, uncertainty and snapshot | No disclosure permission or model invocation |
| Context disclosure | `ConversationContextBinder` | Exact proposal, one-use approval, freshness/scope/payload checks | Process-local approval state; no authentication/persistence |
| Local resource observation | `SystemStatusTool` through `CapabilityRuntime` | One best-effort system capture and typed/text result | Reads host once per execution; no model invocation |
| Resource-conversation composition | `ConversationalSystemAwareness` | One observation -> canonical snapshot -> binder proposal | Composes owners; creates no second capability/approval authority |
| Natural-language resource intent | `recognize_resource_intent` | Bounded classification of current human text | Pure classification; no execution/network/memory |
| Direct generation compatibility | `OllamaProvider` | Exact installed-model metadata check and Ollama wire field | Metadata network operation; no fallback/global mutation |
| Read-only conversational diagnostics | `ConversationSession.diagnostic_snapshot()` | Coherent bounded state view | No mutation, inference, observation or persistence |
| CLI presentation and human decisions | `iris/__main__.py` | Command precedence, prompts, previews, safe display | Composes existing authorities; does not own their semantics |
| Repository quality evidence | `.github/workflows/ci.yml` | Linux checks for the evaluated revision | Ephemeral runner/build artifacts; no merge authority |
| Planning, execution and tool permissions | Existing non-conversational authorities | Their established requests, bindings and effects | Not granted or expanded by conversation/history/context |

A presenter or composer does not become the authority it invokes. The
represented repository contains no unified autonomous conversational control
plane.

## 19. Historical causal photograph

```text
explicit model selection
        OR
assisted deterministic selection
        |
        v
confirmed provider/model binding
        |
        v
temporary ConversationSession
        |
        +-- /diagnostico
        |       `-- coherent read-only snapshot
        |           (no inference, observation or approval use)
        |
        +-- ordinary turn
        |       `-- bounded candidate -> provider validation
        |           -> atomic history commit
        |
        +-- /recursos OR bounded recognized resource intent
        |       `-- observation decision where required
        |           -> one local CPU/RAM observation
        |           -> canonical ContextSnapshot
        |           -> exact disclosure preview
        |           -> separate one-use approval
        |           -> validated contextual inference
        |           -> atomic history commit
        |
        `-- explicit continuity policy
                `-- immutable candidate window
                    -> validated response
                    -> atomic bounded rollover commit
```

The diagram describes available branches, not an automatic sequence. The model
cannot select commands, grant consent, execute tools or change policy.

# PART IX — CONSENT, IDENTITY, FAILURE AND TIME

## 20. Consent and identity boundaries

**FROZEN:** the represented implementation preserves:

```text
observation consent != disclosure consent
disclosure consent != execution authorization
continuity consent != permission to observe or disclose
model confirmation != tool authorization
diagnostic snapshot != context proposal
valid proposal != reusable permission
approval != authentication
session generation != session revision != active turn count
provider computation != committed local turn
local snapshot != provider health or external-world truth
```

Context approval remains bound to exact eligible snapshot, subject, session,
generation, revision, provider/model, question, items, scopes and prepared
window. The default binder policy permits at most ten minutes of evidence and
snapshot age and two minutes of approval validity, with eligibility rechecked
at use time. Successful state or policy transitions make older proposals
stale. Consumption is one-use even if inference later fails. These are
process-local trusted-caller protections, not cryptographic identity or a
multi-user access-control system.

## 21. Failure and abstention semantics

| Condition | Verified category/boundary | Confirmed local consequence |
| --- | --- | --- |
| Bare `/recursos` or denied natural observation | Expected abstention | No capture, proposal, inference or turn commit |
| Incomplete/invalid resource reading | Observation/context failure | Available values may display locally; no contextual inference |
| Disclosure denied or stale | Explicit contextual rejection | No contextual provider request; observation may already have occurred |
| Conservative intent `NO_MATCH` | Ordinary chat path | No capability execution from recognition |
| Session full with continuity disabled | Conversation limit | No provider call; confirmed history/revision unchanged |
| Candidate preparation succeeds | Prepared state only | No history mutation or provider work |
| Provider unavailable/timeout | Operational failure | Attempt status is category-dependent; no new local turn commit |
| Incomplete or protocol-invalid generation | Provider/result failure | No commit, rollover or success feedback; provider work may have occurred |
| Unsupported direct mode/model absent | Pre-inference compatibility failure | No conversational message/context sent; no fallback |
| Successful response cannot fit alone | Local post-generation rejection | Prior history/revision unchanged; external computation not rolled back |
| Stale/foreign/consumed context approval | Binding rejection | No silent window rebuild or approval restoration |
| Busy `/diagnostico` | Synchronized absence | No partial/stale snapshot and no interference with active operation |
| Unknown failure metadata | Unproven cause | Generic bounded explanation; no raw metadata promotion |

Fail-closed validation does not imply retry, recovery, remote rollback or
durable exactly-once behavior.

# PART X — ARCHITECTURAL DECISION HISTORY

## 22. Evidence provenance

Three evidence classes are kept separate:

1. **Canonical implementation evidence:** accepted source, tests, Git objects,
   merged PR metadata and workflow records.
2. **Historical design evidence:** Architect instructions, Q1–Q3 comparison and
   Contract Pass conclusions. These explain intent but do not prove runtime.
3. **Engineer-reported evidence:** local validation, physical observations and
   environmental limitations in PR reports. These are not silently promoted to
   canonical behavior.

| WP | Adopt / adapt | Rejected or excluded | Implemented boundary |
| --- | --- | --- | --- |
| WP066 | Reuse `system.status`, ContextEngine, binder and session; adapt one structured observation to canonical evidence and CLI consent. | Second observer, monitoring, GPU/process metrics, modification, telemetry, autonomous tools. | One explicit CPU/RAM consultation with separate disclosure approval. |
| WP067 | Adopt exact installed-model capability evidence; adapt Ollama's top-level `think` field locally; preserve typed diagnostics. | Name-based inference, generic profiles, retries, fallback, token increase, reasoning trace capture. | Opt-in, revalidated boolean direct generation for one selected model. |
| WP068 | Adopt conservative deterministic recognition and abstention; adapt existing consultation behind preliminary consent. | LLM classifier, general intent router, new executable intents, recognition-as-authorization. | One narrow Spanish CPU/RAM intent; shared `/recursos` procedure. |
| WP069 | Adopt explicit rolling-window policy, immutable candidate and atomic commit; adapt context approval to exact revision/window. | Summaries, archives, persistence, unbounded history, pre-inference eviction, automatic policy. | Session-owned bounded continuity with monotonic state identity. |
| WP070 | Adopt read-only coherent inspection; adapt known typed failures to bounded presentation; reuse session lock. | Observability framework, health monitoring, traces/logs, repair automation, duplicated state authority. | Content-free snapshot, `/diagnostico`, allowlisted explanations and integrated acceptance tests. |

Historical WP070 comparative research considered OpenClaw, Home Assistant,
Promptfoo, Langfuse, LangGraph, OpenJarvis, n8n, Microsoft Agent Framework,
Playwright, Celery and Temporal. At the represented commit,
[`REFERENCE_REGISTRY.md`](../../research/REFERENCE_REGISTRY.md) contains prior
review records for Temporal, Celery, OpenJarvis, OpenClaw, LangGraph, Microsoft
Agent Framework and Ollama. It does not contain WP070 records for every project
in that design-history list. No registry entry is inferred, backdated or added
by this checkpoint, and no external project became a WP070 runtime dependency.

# PART XI — CURRENT FRONTIER AND CLASSIFIED DEBT

## 23. Current implementation frontier

| Capability | Classification at represented state | Evidence / boundary |
| --- | --- | --- |
| Legacy deterministic CLI, routing and dispatch | IMPLEMENTED AND TEST-VERIFIED | Existing commands and full suite; separate from chat intent recognition. |
| Structured memory, ContextEngine and snapshots | IMPLEMENTED AND TEST-VERIFIED | Canonical source/tests; no automatic conversational retrieval. |
| Repository quality CI | IMPLEMENTED AND TEST-VERIFIED | PR/push Linux workflow with pytest, Ruff, mypy and builds. |
| Local Ollama chat and temporary session | IMPLEMENTED AND TEST-VERIFIED; PHYSICALLY OBSERVED IN BOUNDED RUNS | Provider/session tests plus reported Windows/Ollama demonstrations; not persistent chat. |
| Deterministic model recommendation/binding | IMPLEMENTED AND TEST-VERIFIED | Existing router and exact binder; no fallback. |
| One-turn contextual approval/transport | IMPLEMENTED AND TEST-VERIFIED | Exact binder and serializer tests; trusted caller is not authentication. |
| Human-facing CPU/RAM consultation | IMPLEMENTED AND TEST-VERIFIED; PHYSICALLY OBSERVED | `/recursos` and narrow recognized intent; point-in-time only. |
| Direct generation control | IMPLEMENTED AND TEST-VERIFIED; PHYSICALLY OBSERVED FOR ONE MODEL | Exact Ollama metadata required; no general compatibility claim. |
| Bounded continuity beyond eight lifetime turns | IMPLEMENTED AND TEST-VERIFIED; PHYSICALLY OBSERVED | Active state stays at eight pairs; no archive/summarization. |
| Read-only conversational diagnostics | IMPLEMENTED AND TEST-VERIFIED; CLI PHYSICALLY OBSERVED | Session metadata only; no provider health check. |
| Automatic memory retrieval/RAG | NOT IMPLEMENTED | Explicitly outside this interval. |
| Conversational autonomous tools/resource modification | NOT IMPLEMENTED | No tool definitions or output-dispatch authority. |
| Persistent chat/telemetry/durable recovery | NOT IMPLEMENTED | Session, approvals and retired history are process-local. |
| Distributed/multi-node coordination | NOT IMPLEMENTED | No network discovery or scheduler. |

An internal API is not automatically a user-facing feature. A physical smoke
test is not production-readiness evidence.

## 24. CONFIRMED limitations

- Conversation history, continuity policy, approvals and revision state are
  process-local; there is no durable recovery.
- Retired rollover exchanges are neither summarized nor recoverable in-session.
- `/diagnostico` does not check provider/model availability or system health.
- Character limits do not establish exact tokenizer/model-window fit.
- Context approval relies on a trusted caller and is not authentication.
- CPU/RAM observation is point-in-time, not monitoring or diagnosis.
- Resource-intent recognition covers a deliberately narrow Spanish pattern set.
- Failure categories and counters do not prove root cause.
- Assistant text can repeat disclosed facts and remains model output, not sensor
  authority.
- JSON/terminal-safe formatting is not complete prompt-injection resistance.
- Ordinary CI skips the opt-in physical Ollama integration and runs on Linux,
  not a physical Windows/Ollama deployment.
- No persistent conversational memory, autonomous tools, automatic fallback,
  repair or retry exists.

## 25. POTENTIAL risks

- Linux CI and specific Windows deployments may differ in filesystem,
  networking, console and provider behavior.
- Provider-specific metadata or generation behavior may evolve outside the
  tested Ollama contract.
- Valid resource questions outside the current deterministic phrases may
  intentionally abstain or follow ordinary chat.
- Future changes could increase maintenance risk across intertwined approval,
  generation, revision and window validations if their tests drift.
- Users may mistake model-generated resource explanations for authoritative
  diagnosis despite the preserved application boundary.

These are plausible risks, not demonstrated defects at the represented commit.

## 26. FORWARD questions

- Whether broader conversational capability is justified and how it would
  preserve deterministic authorization.
- Whether persistent memory or durable recovery should ever be separately
  designed.
- Whether provider health inspection requires a distinct authority.
- Whether physical integration merits a dedicated reproducible environment.
- Whether any additional capability should be exposed through bounded natural
  language.
- Whether a future diagnostic interface needs additional information without
  becoming monitoring or telemetry.

These questions do not authorize WP071 or any implementation.

# PART XII — VERIFICATION HISTORY

## 27. Evidence ledger

Workflow event, exact head, completed status and success conclusion were
independently queried for every listed PR and canonical push run. Job logs were
checked for the test summary and required quality/build steps.

| Stage | Local / report evidence | PR CI | Canonical post-merge CI | Physical evidence |
| --- | --- | --- | --- | --- |
| ACC-WP065 | Reported local `2474 passed, 1 skipped`; Ruff/mypy pass; local isolated build limitations documented. | [`39538546737`](https://github.com/fermaxvago/IRIS/actions/runs/39538546737): `pull_request`, exact head `ab8c2a8b337e55ac9435351f879069022962466d`, success; `2474 passed, 1 skipped`; Ruff/mypy/build pass. | [`39651928349`](https://github.com/fermaxvago/IRIS/actions/runs/39651928349): `push`, exact merge `a690d38aa67a7c672d194646ec57d6a5a4a59c11`, success; same counts/gates. | None claimed. |
| WP066 | Reported focused `28 passed`; full `2502 passed, 1 skipped`; Ruff/mypy pass; no-isolation wheel/sdist pass after Windows temp restriction. | [`39667918234`](https://github.com/fermaxvago/IRIS/actions/runs/39667918234): exact implementation head, success; `2502 passed, 1 skipped`; all required gates pass. | [`39670492903`](https://github.com/fermaxvago/IRIS/actions/runs/39670492903): `push`, exact merge `ea251c84d5eef5969e43b2df6d64a0ddf864085d`, success; same counts/gates. | Real reading and approved Ollama attempts; generation incomplete, no committed answer. |
| WP067 | Reported focused regression `173 passed`; full `2527 passed, 1 skipped`; required gates pass with documented Windows build adjustment. | [`39674208220`](https://github.com/fermaxvago/IRIS/actions/runs/39674208220): exact implementation head, success; `2527 passed, 1 skipped`; gates pass. | [`39696498350`](https://github.com/fermaxvago/IRIS/actions/runs/39696498350): `push`, exact merge `d08e88363d43734a3580de7cfec580e646ca6089`, success; same counts/gates. | Standard/direct greetings and one direct contextual consultation completed on reported Windows/Ollama environment. |
| WP068 | Reported focused `126 passed`; full `2574 passed, 1 skipped`; required gates pass with documented Windows build adjustment. | [`39798871215`](https://github.com/fermaxvago/IRIS/actions/runs/39798871215): exact implementation head, completed success; `2574 passed, 1 skipped`; gates pass. | [`39800297234`](https://github.com/fermaxvago/IRIS/actions/runs/39800297234): `push`, exact merge `10063b58966de668ccb10b4232b2ef2c3f34d4fb`, success; same counts/gates. | Denial/no capture plus later separately approved reading/disclosure and complete direct response. |
| WP069 | Reported full `2601 passed, 1 skipped`; Ruff/mypy/build pass after documented Windows temp adjustment. | [`39837864005`](https://github.com/fermaxvago/IRIS/actions/runs/39837864005): exact implementation head, success; `2601 passed, 1 skipped`; gates pass. | [`39838413482`](https://github.com/fermaxvago/IRIS/actions/runs/39838413482): `push`, exact merge `c5bfdca1e78954c8f05e32b03190bd710849f871`, success; same counts/gates. | Ninth/tenth turns, eviction feedback, one separately approved resource turn, deactivation and reset reported. |
| WP070 | Reported focused `43 passed`; conversational regression `262 passed`; full `2616 passed, 1 skipped`; Ruff/mypy/build pass with workspace-local Windows temp. | [`39847573570`](https://github.com/fermaxvago/IRIS/actions/runs/39847573570): exact implementation head, success; `2616 passed, 1 skipped`; gates pass. | [`39850515127`](https://github.com/fermaxvago/IRIS/actions/runs/39850515127): `push`, exact represented merge, completed success; `2616 passed, 1 skipped`; Ruff lint/format, mypy, wheel and sdist pass. | `/diagnostico` lifecycle smoke only; no model inference or resource observation. |

The WP066 post-merge run ID `39669011808` supplied as a candidate historical
reference returned GitHub 404 during this audit. Querying Actions by exact
canonical head and `push` event recovered and verified `39670492903`; the table
uses the recoverable canonical evidence rather than repeating the invalid ID.

All CI logs identify one skipped opt-in physical Ollama integration test. A
skip is not a successful physical test. Local counts above remain
Engineer-reported unless the named CI logs independently show the same full
suite count. The physical observations are bounded historical reports, not
general deployment certification.

## 28. ACC-WP070 authoring verification boundary

Checks performed while authoring this later document belong to the checkpoint
PR, not the represented WP070 state. Fresh local verification completed:

- focused WP070/system-awareness tests: `43 passed`;
- full suite under the repository environment: `2616 passed, 1 skipped`;
- the skip remained the opt-in physical Ollama integration;
- Ruff lint passed and Ruff reported 348 files already formatted;
- strict mypy reported no issues in 262 source files;
- local-link, Git-object, documentation-scope and `git diff --check`
  validation passed; and
- `git fsck --no-reflogs` reported no corruption and seven harmless dangling
  blobs.

The ordinary isolated local build could not obtain `setuptools>=68` because
the sandbox could not reach the package index. Re-running the unchanged build
with the repository environment, a workspace-local temporary directory and
`--no-isolation --sdist --wheel` produced both artifacts successfully. This is
reported as an environmental limitation, not an isolated-build PASS or a code
defect. The successful WP070 post-merge workflow does not substitute for the
ACC-WP070 documentation PR's own fresh CI evidence.

# PART XIII — ARCHITECT SUCCESSION AND NON-CLAIMS

## 29. Recovery procedure

The durable succession principles remain those in
[ARCHITECT-SUCCESSION-FOUNDATIONS](ARCHITECT-SUCCESSION-FOUNDATIONS.md):

```text
architecture documentation != architecture authority
historical memory != independent judgment
historical CURRENT != present-day CURRENT
verified contract != permanent future design
passing tests != universal correctness
merged PR != independently verified canonical state
provider selection != provider availability
model output != authorization
diagnostic inspection != monitoring
session continuity != persistent memory
one successful physical test != general deployment readiness
```

A future Architect should:

1. Verify canonical repository access and present branch state.
2. Locate the latest valid ACC rather than assuming this one remains latest.
3. Verify its represented SHA, parents, tree and workflow evidence.
4. Reconstruct integration lineage and distinguish implementation, PR,
   synthetic test merge, canonical merge and documentation commit.
5. Inspect canonical source at the represented commit.
6. Recover authority ownership and frozen responsibility boundaries.
7. Recover consent, identity, temporal and failure boundaries.
8. Separate source-proven facts from design history and Engineer reports.
9. Inspect confirmed limitations and present-day repository changes.
10. Run a separate Q1 -> Q2 -> Q3 -> Contract Pass for new work.
11. Independently audit future PRs and their actual evaluated revisions.
12. Preserve human-only merge authority.

This supports recovery without the original chat. It does not appoint, train,
certify or activate a successor Architect or automated succession system.

## 30. Explicit non-claims

This checkpoint does not claim:

- that passing tests prove factual model output, complete security or every
  deployment environment;
- that a loopback endpoint or `LOCAL` descriptor cryptographically proves
  physical locality;
- that process-local approval authenticates a human;
- that JSON formatting prevents all prompt injection;
- that Linux CI validates physical Windows/Ollama behavior;
- that provider failure means no external computation occurred;
- that a route, model, session, context, diagnostic or continuity policy grants
  tool authority;
- that active history is a persistent or complete memory;
- that diagnostics are telemetry, monitoring, provider health or repair;
- that one physical success establishes general reliability; or
- that any FORWARD question is approved future work.

## FINAL CONTINUITY STATEMENT

At canonical commit `721f088c5a9728cac5ce923688300d219242f678`,
IRIS retained the earlier planning, execution, intelligence-routing, temporary
conversation and exact contextual-disclosure boundaries documented by
ACC-WP065. WP066 composed one authorized local CPU/RAM observation into that
context path; WP067 added exact-model, opt-in Ollama direct generation; WP068
added one conservative natural-language resource intent with preliminary
observation consent; WP069 added explicitly enabled, atomic bounded rollover;
and WP070 added coherent content-free session diagnostics and bounded failure
presentation.

The causal boundary remains: IRIS owns observation, validation, session state,
consent and commit; the selected model receives only the authorized request and
returns candidate text. Inspection is not monitoring, continuity is not
memory, and information is not permission to act. This document freezes that
historical state and stops. It does not authorize WP071, runtime change or
merge.
