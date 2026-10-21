# IRIS --- ARCHITECTURE CONTINUITY CHECKPOINT --- ACC-WP065

**Represented canonical `main`:** `7f60284a6a1eec4dab6776a825803d23c30b1b84`

**Checkpoint date:** 2026-10-20

**Previous checkpoint:** [ACC-WP060](ACC-WP060.md)

**Succession foundation:** [ARCHITECT-SUCCESSION-FOUNDATIONS](ARCHITECT-SUCCESSION-FOUNDATIONS.md)

## 0. How to read this checkpoint

This is an immutable historical photograph of IRIS **after the WP065 merge and
before this documentation commit**. The ACC-WP065 documentation commit and any
later merge are not part of the represented state.

- **FROZEN** identifies established responsibility boundaries and contracts at
  the represented state.
- **CURRENT** identifies a fact verified specifically at
  `7f60284a6a1eec4dab6776a825803d23c30b1b84`.
- **FORWARD** identifies an open question, risk or non-binding hypothesis.

Later source can supersede a CURRENT claim without changing this historical
record. Preserve the reasoning; do not blindly preserve the prediction.
Canonical source and Git objects outrank PR prose, tests, reports and design
history. Tests establish their exercised cases, not universal correctness.
This checkpoint grants no implementation, publication, merge or autonomous
Architect authority.

# PART I --- CANONICAL ANCHOR AND GIT LINEAGE

## 1. Represented commit

**CURRENT:** fetched `origin/main` resolved to the represented WP065 merge. Its
tree is `9439c65b1b56571d7f62cfcc2ca6abf1a7ec1b33`; its parents, in order, are:

1. `c6ff27e1d1ea670fca3f9c8d66df319b56fae58c` — canonical post-WP064 main.
2. `fc2620208a1e7bce04d81ad1c3f203092626cad5` — accepted WP065 implementation.

GitHub reports PR #73 merged. The required post-merge workflow run
[`39505132508`](https://github.com/fermaxvago/IRIS/actions/runs/39505132508)
completed with conclusion `success`, event `push`, and exact head SHA
`7f60284a6a1eec4dab6776a825803d23c30b1b84`.

At this represented commit, `LATEST.md` still points to ACC-WP060 and this file
does not yet exist. Updating those documents is later documentation activity,
not part of the photograph.

## 2. Verified integration lineage

The table was reconstructed from local commit, parent and tree objects and
cross-checked against GitHub PR metadata. In every row, the implementation
commit has the stated base as its sole parent; the merge parents are exactly
**base, implementation**; and the merge tree equals the implementation tree.
The first-parent merges are consecutive, with no intervening first-parent
architectural merge.

| Stage | PR and verified title | Base / first parent | Implementation / second parent | Canonical merge | Merge and implementation tree |
| --- | --- | --- | --- | --- | --- |
| ACC-WP060 | #68 `ACC-WP060 — Architecture Continuity Checkpoint` | `8d6d5cdac11f5b01af3f94c0e47e85aa7baa4bc3` | `de38bc2fd26d39ca1bc92df0b9e5232646ab5ebb` | `1855c9675c9e01d99badfd024d89ee9dc091f241` | `c6d1eab36f263a2b6e56b90e5cb46619aa4ba5fc` |
| WP061 | #69 `WP061 — Correct Canonical PlanRun Observation Preservation Validation` | `1855c9675c9e01d99badfd024d89ee9dc091f241` | `a74357c63fe49f5b02e10be82eeeeaaee77b16fb` | `a55f08ec0542b4ef38bb1133ee292db53352cdcb` | `b39f6f7f77afb55f1facdac5285fa476bfda5cae` |
| WP062 | #70 `WP062 — Automated Repository Quality Gates` | `a55f08ec0542b4ef38bb1133ee292db53352cdcb` | `7e0a38882d8a58dbda7967a8f26d51a822beab7f` | `1eed9aa613b5826096f1a77c9041cf57863f73a4` | `c393acdcdabe67356d88a4376f571916c33b634d` |
| WP063 | #71 `WP063 — Bounded Local Conversational Session` | `1eed9aa613b5826096f1a77c9041cf57863f73a4` | `40b3e8ff9aadd2f6edcbfb21b4a27ac4afcb9930` | `27c1476009356ec5108b7cf812b1b583d293d6d1` | `fb3411142656268ba2a03c404c9951af7acbe8e8` |
| WP064 | #72 `WP064 — Bounded Conversational Intelligence Route Binding` | `27c1476009356ec5108b7cf812b1b583d293d6d1` | `cd1a4cd68171b043d1cb4081d0866eaab54cbebe` | `c6ff27e1d1ea670fca3f9c8d66df319b56fae58c` | `8fe1774b6668744997f376dcea31089cd8a7a322` |
| WP065 | #73 `WP065 - Bounded Conversational Context Binding` | `c6ff27e1d1ea670fca3f9c8d66df319b56fae58c` | `fc2620208a1e7bce04d81ad1c3f203092626cad5` | `7f60284a6a1eec4dab6776a825803d23c30b1b84` | `9439c65b1b56571d7f62cfcc2ca6abf1a7ec1b33` |

All six PRs are reported by GitHub as merged. Matching trees establish equal
file contents for each accepted implementation and canonical merge; they do
not make the commits, PR identity, test merge, review event or lifecycle event
identical. PR numbering alone does not prove continuity. In particular:

```text
implementation commit
    != PR number
    != PR test-merge commit
    != canonical merge commit
    != represented ACC state
    != later ACC documentation commit
```

The represented state is the canonical WP065 merge, not PR #73's test merge
checkout and not the future ACC-WP065 documentation merge.

# PART II --- FROZEN ARCHITECTURAL FOUNDATION

## 3. Responsibility walls retained from ACC-WP060

**FROZEN:** the following distinctions remain supported by canonical source in
the represented tree:

| Distinction | Meaning at the represented state |
| --- | --- |
| Routing != Execution | Candidate selection or a route does not invoke the selected operation. |
| Planning != Plan Execution | Plan construction does not perform a PlanStep. |
| Selection != Activation | A selected step can remain `NOT_STARTED`. |
| Decision != ExecutionRequest | A routing decision is not an executable request object. |
| ExecutionRequest != ExecutionBinding | Request materialization and exact Plan/Run binding are separate. |
| ExecutionBinding != Authorization | A binding witnesses lineage; it is not a cryptographic or policy authorization token. |
| Authorization != Execution | An admitted operation still requires its execution authority. |
| ExecutionResult != PlanObservation | Operational output and recorded Plan evidence remain distinct. |
| Observation != Assessment | Recorded evidence does not itself establish a Step outcome. |
| Assessment != Transition Decision | Evidence interpretation does not itself choose progress. |
| Transition Decision != Progress Update | A decision and the update it proposes remain distinct. |
| Progress Update != Updated PlanRun | Synthesis does not itself create the next canonical revision. |
| Updated PlanRun != Fresh ControlDecision | A changed revision requires fresh control evaluation. |
| Handling Preparation != Execution Permission | A prepared `HandlingNeed` does not execute work. |
| Currentness != Identity | Matching identifiers cannot replace revision-currentness checks. |
| Structural Completion != Goal Satisfaction | Completed structure is not proof that the Goal is satisfied. |
| Domain-valid != Canonically reachable | A valid object may still be causally invalid in the cumulative lineage. |
| Invocation-local exactly-once != Global exactly-once | Call-count guards do not provide durable distributed idempotency. |

The earlier status distinctions also remain: `ExecutionStatus.SUCCEEDED` is not
`StepOutcomeStatus.SATISFIED`; execution failure or rejection does not by
itself imply every Plan progress failure; `ACTIVE` is not completed. Nothing in
WP061–WP065 adds rollback, distributed transactions, durable continuation or
global recovery.

## 4. Conversational responsibility walls

**FROZEN:** WP063–WP065 add bounded conversational seams without collapsing
their authorities:

| Distinction | Verified consequence |
| --- | --- |
| Model discovery != Model selection | Registry enumeration supplies candidates; the deterministic router evaluates them. |
| Model recommendation != Human confirmation | A proposal does not create a session or call a model. |
| Model confirmation != Inference | Binding creates a temporary session; the first user turn invokes the provider. |
| Conversation history != ContextSnapshot | The session's completed messages and the Context authority's evidence snapshot have separate identities and contracts. |
| Context evidence != Verified external truth | Epistemic and freshness metadata do not prove real-world correctness. |
| Context eligibility != Disclosure approval | A resolved and fresh snapshot still requires an exact approval. |
| Disclosure proposal != Authorization | The proposal is inspectable evidence for a trusted caller; it cannot invoke inference. |
| Approval != Authentication | WP065's process-local trusted-caller contract is not a user identity system. |
| Approval consumption != Durable permission | Approval is one-turn, process-local and consumed before use. |
| Contextual data != System instructions | Ollama receives encoded context in the final user-role content, never a privileged system/tool message. |
| Information access != Execution authority | Disclosed facts do not grant tools, memory mutation or workflow transitions. |
| Model output != Permission to act | Generated text is returned to the user and is not dispatched as an IRIS command. |
| Conversation session != Persistent memory | Completed turns live only in the process-local session. |
| Model-local inference != Proof of physical locality | Declared `LOCAL` metadata and a loopback endpoint do not independently prove hardware location. |
| CI PASS != Physical Windows/Ollama validation | Linux automated checks do not demonstrate every physical deployment environment. |

# PART III --- WP061 AND REPOSITORY CORRECTNESS

## 5. Canonical observation preservation correction

WP061 changed only
[`iris/plan_step_execution_result_recording_composition/composer.py`](../../../iris/plan_step_execution_result_recording_composition/composer.py)
and its focused test module. The defect was local to WP038 defensive validation:
`PlanRun` canonically sorts observations by `observation_id`, while the previous
postcondition required old observations to remain a positional prefix and the
new observation to occupy the final tuple position.

The corrected `_validate_recording_result` computes the expected tuple as the
recording base's observations plus the new observation, sorted by canonical
identifier. It then requires:

- a previously unused new observation identifier;
- exactly one additional observation;
- the canonical sequence to contain the exact expected observation objects in
  order, not merely equal IDs or equal cardinality;
- unchanged blockers and exact `StepProgress` preservation;
- preserved Plan, Run and Goal identities;
- revision equal to the recording base plus one; and
- the existing step, execution, evidence-source and observation lineage.

Tests cover observations sorting before, between and after existing evidence,
the empty base, the real recorder/reducer path, and adversarial deletion,
replacement, mutation, insertion, identity, revision and lineage cases.

**FROZEN:** `PlanRun` in
[`iris/plan_runs/models.py`](../../../iris/plan_runs/models.py) remains the
canonical representation and ordering authority;
[`PlanRunReducer`](../../../iris/plan_runs/reducer.py) remains the revision
transition authority; WP026's
[`PlanStepExecutionResultRecorder`](../../../iris/plan_step_execution_result_recording/recorder.py)
remains the execution-result recording authority. WP061 made WP038's
composition postcondition compatible with those authorities. It added no
execution, observation, rollback or transaction authority.

# PART IV --- WP062 AND REPOSITORY QUALITY VERIFICATION

## 6. Automated quality workflow

WP062 added
[`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml) and made a
format-only correction to `iris/core/system.py`.

**CURRENT workflow contract:**

- Trigger: `pull_request` on opened, synchronized and reopened PRs; `push` on
  `main`.
- Job: stable name `quality`, GitHub-hosted `ubuntu-24.04`, Python 3.11,
  30-minute timeout.
- Permissions: explicit `contents: read`; no repository-write, PR-write,
  OIDC-write or secret-dependent authority.
- Checkout: pinned full action SHA, with credential persistence disabled.
- Python setup: pinned full action SHA.
- Concurrency: newer runs may supersede the same PR; distinct PRs do not share
  that group, and main pushes are grouped by commit SHA.
- Environment: `IRIS_RUN_OLLAMA_INTEGRATION=0`; ordinary CI does not start,
  install or contact Ollama.
- Installation: editable project development dependencies plus `build`.
- Required commands: `python -m pytest -q`, `python -m ruff check .`,
  `python -m ruff format --check .`, `python -m mypy iris`, and
  `python -m build` for wheel and source distribution.
- Result propagation: no `continue-on-error`, `|| true` or artificial required
  PASS. Cancelled work is not represented as completed success.
- Evidence: event, checkout SHA, GitHub SHA and PR head/base or pushed SHA are
  printed so the evaluated revision is attributable.

The workflow generates repository quality evidence. It does not merge, deploy,
modify branch protection, publish packages, test Windows hardware or provide a
comprehensive supply-chain sandbox. Pull-request CI, canonical push CI, local
verification and physical deployment validation are separate evidence sources.

# PART V --- WP063 CONVERSATIONAL FOUNDATION

## 7. Conversation contracts

WP063 introduced the bounded session in
[`iris/intelligence/conversation.py`](../../../iris/intelligence/conversation.py),
extended the intelligence contracts and runtime, added Ollama `/api/chat`, and
integrated explicit `chat --model` CLI entry.

`ConversationMessage` is immutable and accepts only `user` and `assistant`
roles with nonblank text. Role-looking text inside a user message remains user
data. `ConversationRequest` requires alternating roles, starts with user and
ends with the currently uncommitted user message. `ConversationSession` owns a
process-local tuple of completed user/assistant pairs and an explicit
provider/model identity.

The numerical conversation limits at the represented state are:

| Limit | Value |
| --- | ---: |
| Previous completed turns | 8 |
| User-message characters | 2,000 |
| Aggregate conversational characters | 6,000 |
| Requested output tokens | 256 |

These are counts and requested output bounds, not exact tokenizer accounting or
a guarantee of the provider's context window. The session does not silently
truncate or summarize completed turns. Reset explicitly clears temporary
history; WP065 later added a generation increment to invalidate approvals.

The session sends a request through `IntelligenceRuntime.chat()`, validates a
successful assistant result, and only then commits exactly one user/assistant
pair. Provider failures, malformed or empty responses, model mismatches,
interruptions and budget rejection leave prior local history unchanged. If a
provider has already computed a response before local validation fails, IRIS
does not claim the external computation was rolled back.

[`OllamaProvider`](../../../iris/intelligence/providers/ollama.py) uses
non-streaming `/api/chat`, includes no tools, requests the bounded output,
checks model identity, completion, assistant role and nonblank content, and
rejects tool-call structures. Its earlier `/api/generate` path remains intact.

The CLI preserves the legacy loop and `estado`, `ayuda`, `salir`; inside chat,
`/reiniciar` resets and `/salir` returns to that loop. No transcript persistence,
automatic memory, automatic routing, tool execution or action authorization was
introduced.

# PART VI --- WP064 MODEL SELECTION AND BINDING

## 8. Discovery, routing, confirmation and binding

WP064 added
[`iris/intelligence/conversation_routing.py`](../../../iris/intelligence/conversation_routing.py)
and the additive `chat --select` path.

`ConversationRouteBinder` enumerates only explicitly registered providers from
[`ProviderRegistry`](../../../iris/intelligence/registry.py). It calls their
existing `list_models()` operations deterministically, validates descriptor and
provider identity, rejects duplicate `(provider_id, model_id)` pairs, and fails
closed if a required provider discovery fails. Operational discovery failure is
therefore not disguised as a successfully evaluated `UNSATISFIED` inventory.

Descriptors are adapted to existing `IntelligenceResource` objects while
preserving provider, model, location, capabilities, availability, context
window and metadata. The adapter does not fabricate quality, latency, hardware
or reliability claims. Affinities are optional explicit configuration keyed to
the exact provider/model identity; missing affinity means unknown, not false,
and no affinity is inferred from model names.

The conversational need requires `CONVERSATION` and `LOCAL`. Existing
`CandidateResolver`, `DeterministicRoutingPolicy` and `IntelligenceRouter`
produce `EXACT`, `DEGRADED` or `UNSATISFIED`; WP064 does not implement a second
selection algorithm. A frozen `ConversationRouteProposal` preserves the need,
selected identity, route status, actual explanation, rejections, preference
shortfalls and `policy_recommendation` provenance. Proposal creation performs
no inference and creates no session.

The assisted CLI identifies the proposed provider/model and asks for explicit
acceptance. Cancellation creates no session. After acceptance, binding
re-discovers and revalidates the exact provider/model, availability,
conversation capability, locality and provider chat capability. It neither
reroutes nor falls back if that resource changed. A successful bind creates the
existing `ConversationSession`; the first later user message is the first
inference.

`chat --model` remains the explicit path. `chat --select` is additive and
mutually exclusive with it. Recommendation, confirmation, session binding and
inference are four distinct events. Declared model metadata is not an
independent hardware benchmark or proof of physical locality.

# PART VII --- WP065 CONTEXTUAL DISCLOSURE BINDING

## 9. Reuse of canonical context

WP065 added
[`iris/intelligence/context_binding.py`](../../../iris/intelligence/context_binding.py)
and extended the existing request, runtime, provider and session contracts.
It consumes an already constructed canonical `ContextSnapshot`; it does not
create a second context engine, retrieve memory automatically or change global
Context semantics.

`ConversationContextBinder` implements this programmatic sequence:

1. Validate an exact `ContextSnapshot`, subject, session and proposed user
   content at a point in time.
2. Produce an immutable `ContextDisclosureProposal` containing exact snapshot,
   subject, session generation and turn, destination, item IDs, scopes,
   serialized payload and validity times.
3. Accept an approval from a trusted caller only for the proposal's exact item
   tuple and scope set; no `authorized=True` shortcut exists.
4. Consume the approval before use and revalidate destination, session object,
   generation, turn, content, expiration, snapshot/evidence freshness and
   budgets.
5. Construct a contextual `ConversationRequest` and invoke the existing
   `IntelligenceRuntime`.
6. Require an explicitly contextual-capable conversational provider.
7. Commit the ordinary user/assistant pair only after a validated success.

Both explicitly selected WP063 sessions and WP064-bound sessions use the same
session type and therefore the same path.

## 10. Eligibility, identity and freshness

The initial eligibility policy accepts only a structurally valid `RESOLVED`
snapshot with at least one selected item, no conflicts, uncertainties or
budget-excluded evidence, and no more than eight contextual items. Every item
must be approved, have a covered scope, have an observation timestamp, and be
classified `CURRENT` or `RECENT`. Snapshot and observations cannot be in the
future or older than the configured policy.

The exact identities kept separate and rechecked at use include:

- snapshot ID and exact snapshot object;
- WorkSubject and subject ID;
- session object, `session_id`, generation and intended turn;
- provider and model ID;
- proposed user content;
- selected contextual item IDs and scopes; and
- approval ID, issue time and expiration.

Equal values or identifiers do not establish authentication or authority. The
registries are process-local replay guards, not cryptographic credentials or a
multi-user access-control service.

Default policy values verified in source:

| Policy | Default / maximum |
| --- | ---: |
| Contextual items | 8 |
| Serialized contextual section | 1,500 characters |
| Combined transmitted messages and context | 6,000 characters |
| Snapshot/evidence age | 10 minutes |
| Approval validity | 2 minutes |
| User message | 2,000 characters |
| Previous completed turns | 8 |
| Requested output | 256 tokens |

`ContextBudget.max_items` remains a canonical ContextEngine selection bound.
The eight-item and character limits are additional disclosure/transport bounds;
they do not replace ContextBudget and are not tokenizer counts. Payload overhead,
metadata and delimiters count toward the contextual and combined limits. No
history or evidence is silently truncated.

## 11. Informational transport and atomicity

The canonical JSON payload preserves snapshot and subject identity, selected
item identity and value, evidence source/reference, epistemic state, scope,
freshness and observation time. Angle brackets in untrusted values are encoded,
and the section is delimited as IRIS context data.

`OllamaProvider.chat_with_context()` appends that section to the final user-role
wire message. It does not synthesize `system`, `tool` or tool-call messages. The
original user message remains unchanged in IRIS history; the contextual payload
is not committed or copied to later turns. A provider lacking the contextual
protocol rejects the request explicitly rather than silently dropping context
and performing ordinary chat.

Approval is one turn only. It is consumed before contextual use, so failure does
not create reusable authorization. Reset increments session generation, making
an earlier proposal/approval ineligible even when `session_id` is unchanged.
Missing approval, substitution, wrong destination, stale/unresolved evidence,
budget failure or unsupported provider prevents the provider call. Provider or
assistant-result failure preserves prior session history. A successful turn
commits one ordinary user/assistant pair.

Formatting contextual data as JSON reduces delimiter ambiguity; it does not
guarantee prompt-injection immunity. The decisive protection is that model text
has no execution authority. The assistant response may repeat disclosed facts,
which is an information-exposure limit rather than persistence of the context
payload itself.

## 12. Explicit WP065 limits

**CURRENT limitations:** approval relies on a trusted process-local caller that
is responsible for obtaining the human decision. It is not authentication,
durable permission or a complete human-facing CLI consent workflow. WP065 adds
no automatic memory retrieval, persistent chat, RAG framework, summarizer,
provider fallback, tool execution, memory mutation or workflow continuation.
Provider-mocked tests validate contracts but do not prove operation against a
physical Ollama deployment.

# PART VIII --- CAUSAL PHOTOGRAPH AND AUTHORITY MAP

## 13. Historical and runtime shape

WP061–WP065 are consecutive integration history, but they are not five stages
of one runtime pipeline:

```text
CANONICAL IRIS AT ACC-WP060
    |
    +-- PlanRun / execution-result recording composition
    |       |
    |       `-- WP061: canonical observation-preservation correction
    |
    +-- Repository verification
    |       |
    |       `-- WP062: PR and main quality evidence
    |
    `-- Intelligence runtime + explicit providers
            |
            `-- WP063: bounded process-local conversation
                    |
                    +-- WP064: discovery -> existing deterministic route
                    |          -> human confirmation -> exact session bind
                    |
                    `-- WP065: existing ContextSnapshot -> disclosure proposal
                               -> trusted-caller approval -> one contextual turn

REPRESENTED STATE -> STOP
```

The historical arrows show canonical integration order. Runtime arrows show
actual dependencies. Repository CI is not a runtime coordinator. WP061 is not a
conversation stage. WP064 selection is not model inference. WP065 context
eligibility is not disclosure approval, and disclosure approval is not tool
authorization. None of these seams creates an automatic continuation loop.

## 14. Authority ownership matrix

| Authority | Canonical owner at represented state | Inputs -> outputs | Mutates state | Invokes model | Grants permission | Persists data | Relevant interval change |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Planning / Goal | `iris.planning` | Goal/plan definitions -> canonical Plan | No operational mutation | No | No | No new persistence here | Unchanged |
| PlanRun state/revision | `iris.plan_runs`, `PlanRunReducer` | current Run + explicit update -> new immutable Run revision | Produces new state | No | No | No | WP061 preserved |
| Observation recording | WP026 recorder | exact execution lineage/result -> PlanObservation + recorded Run | Produces new Run | No | No | No durable store | WP061 corrected WP038 validation only |
| Recording composition validation | WP038 composer | delegated recording result -> accepted cumulative result or invariant error | No | No | No | No | WP061 changed preservation postcondition |
| Repository CI | `.github/workflows/ci.yml` | checked-out commit -> native check/log evidence | Ephemeral runner only | No | No merge authority | Build artifacts only in runner | WP062 introduced |
| Provider registry/discovery | `ProviderRegistry`, provider `list_models()` | explicit registrations -> descriptors | Registry setup only | No inference | No | No inventory persistence | WP064 integrated |
| Intelligence routing | `CandidateResolver`, `DeterministicRoutingPolicy`, `IntelligenceRouter` | need + resources -> route | No | No | No | No | Reused by WP064 |
| Route proposal/binding | `ConversationRouteBinder` | registry + need -> proposal; accepted exact proposal -> session | Creates session object | No | Narrow session selection only | No | WP064 introduced |
| Conversational session | `ConversationSession` | completed history + user turn -> validated pair | Process-local history/reset generation | Through runtime | No action permission | No | WP063; generation extended WP065 |
| Work identity | `iris.work_identity.WorkSubject` | owning work identifiers -> immutable subject | No | No | No | No | Reused WP065 |
| Context construction | `ContextEngine` | subject, candidates, budget, uncertainty -> ContextSnapshot | No external mutation | No | No disclosure permission | No | Reused WP065 |
| Memory evidence | canonical Context/Memory models | scoped evidence -> selected contextual item metadata | No automatic retrieval in this path | No | No | WP065 writes none | Reused WP065 |
| Disclosure proposal/approval | `ConversationContextBinder` | exact snapshot/session/content/destination -> proposal/one-use approval | Process-local registries | No | Grants one bounded disclosure use, not execution | No | WP065 introduced |
| Contextual serialization | context binder + contextual provider contract | approved items -> bounded JSON section | No | No | No additional authority | Not in history | WP065 introduced |
| Intelligence execution validation | `IntelligenceRuntime` | registered destination + request -> structured result | No session commit itself | Yes, through provider | No tools/actions | No | WP063/WP065 extended compatibly |
| Ollama transport | `OllamaProvider` | validated request -> `/api/generate` or `/api/chat` response | External computation may occur | Yes | No | Provider behavior outside IRIS not claimed | WP063 chat; WP065 context operation |
| Tool/action execution | Existing execution authorities outside conversation | authorized operational artifacts -> effects | Potentially | Not from this chat path | Separate authority | Authority-specific | Not extended |

A composer or binder that validates another authority's result does not become
the owner of the validated semantics. No unified autonomous control plane is
present.

# PART IX --- FAILURE, IDENTITY, TIME AND AUTHORIZATION

## 15. Failure and abstention semantics

| Condition | Category | Observable boundary | Local state after failure |
| --- | --- | --- | --- |
| No eligible model after successful discovery | Expected route absence (`UNSATISFIED`) | WP064 route | No session; no inference |
| User declines recommendation | Explicit abstention | CLI confirmation | No session; no inference |
| Provider discovery fails | Operational failure | WP064 discovery | No partial-inventory route |
| Duplicate/contradictory descriptors | Invariant/contract failure | WP064 discovery | No proposal |
| Model disappears or changes before binding | Explicit binding rejection | WP064 revalidation | No substitution/session |
| Invalid user input or conversation budget exhausted | Explicit request rejection | WP063 session | Existing history unchanged; no provider call where prevalidated |
| Provider unavailable/timeout | Provider failure | runtime/provider | Existing history unchanged; no fallback |
| Invalid/empty/incomplete/wrong-model assistant response | Provider contract failure | runtime/session | Existing history unchanged |
| Missing/expired approval | Explicit contextual rejection | WP065 binder | No contextual provider call; no history change |
| Wrong session/generation/turn/model/snapshot/content | Invariant or authorization mismatch | WP065 binder | No contextual provider call |
| Partial, ambiguous, conflicted, stale or future context | Eligibility rejection | WP065 proposal/use | No provider call |
| Unsupported contextual provider | Capability rejection | runtime | No ordinary-chat fallback; no history change |
| Context/combined payload over budget | Explicit rejection | WP065 proposal/use | No truncation, provider call or commit |
| Successful external generation then failed local validation | Partial external state | session validation | No local turn commit; external computation is not rolled back |
| Physical service not tested | Incomplete verification | evidence ledger | No claim of physical PASS |

An expected absence is not a successful result, a domain rejection is not
abstention, and malformed successful output is an invariant failure. Fail-closed
validation does not imply retry, recovery or rollback.

## 16. Identity and temporal validity

Canonical object identity is used where causal provenance requires the exact
artifact; canonical identifiers connect immutable model fields; Run revision
checks establish currentness; and timestamps establish bounded temporal
compatibility. These mechanisms are complementary:

```text
object identity != cryptographic authenticity
equal identifiers != proven authorization
snapshot eligibility != human approval
approval issuance != inference
approval consumption != successful inference
freshness classification != independently verified real-time truth
```

WP061 requires the exact prior and newly recorded observation objects in the
canonical sequence. WP064 carries exact provider/model identity from proposal
through revalidation and session creation. WP065 binds exact snapshot,
WorkSubject, session object/ID/generation/turn, destination, content, item IDs,
scopes and time window. Its process-local, one-use registries limit accidental
replay and substitution within the process. They do not defend against a
compromised trusted caller, establish human identity, survive process restart
or constitute a general authorization service.

# PART X --- ARCHITECTURAL DECISION HISTORY

## 17. Evidence provenance

The following decision history is preserved from accepted Architect contracts
and PR records. It explains intent but is not itself proof of runtime behavior;
the source-backed sections above describe the final implementation.

| WP | Problem / hypothesis | Adopt / adapt | Rejected or deferred | Implemented boundary |
| --- | --- | --- | --- | --- |
| WP061 | Canonical sorting and WP038's positional append assertion conflicted. | Keep PlanRun ordering, reducer and WP026; adapt WP038 to exact canonical evidence preservation. | Insertion order, timestamp sorting, weak membership-only checks, new recorder. | Local validation correction and adversarial tests. |
| WP062 | Manual Engineer reports were insufficiently independent and repeatable. | GitHub Actions, existing pytest/Ruff/mypy/build, least privilege, explicit commit evidence. | Auto-merge/deploy, write permissions, secrets, broad matrices/dependency changes. | One Linux `quality` workflow and nonsemantic formatting correction. |
| WP063 | Existing intelligence infrastructure lacked a practical bounded textual interface. | IRIS-owned structured session, explicit local provider/model, atomic turns, bounded history. | Tools, autonomous routing, persistence, fallback, summarization, voice/GUI. | Temporary multi-turn chat through runtime and Ollama `/api/chat`. |
| WP064 | Deterministic router and conversation existed but were disconnected. | Explicit discovery, descriptor adaptation, existing router, explainable proposal, confirmation, revalidation. | Second router, LLM routing, fabricated metrics, silent fallback, automatic installation/cloud discovery. | Assisted local model selection and exact session binding. |
| WP065 | Conversation needed optional context without collapsing evidence, consent and execution authority. | Reuse ContextSnapshot; separate proposal, trusted-caller approval, one-turn binding; typed contextual provider capability. | New Context/RAG/memory system, privileged system prompt, durable permission, auto retrieval, persistence, tools. | Exact process-local disclosure approval and bounded informational transport. |

The evolution is `Conversation -> Model Selection -> Contextual Conversation`,
not `Conversation -> autonomous agent`. Rejected scope in this interval is not
a permanent prohibition on future separately designed work.

# PART XI --- CURRENT FRONTIER AND EVIDENCE-CLASSIFIED DEBT

## 18. Implementation frontier

| Capability | Classification at represented state | Evidence / limit |
| --- | --- | --- |
| Deterministic legacy CLI/router/dispatcher | IMPLEMENTED AND TEST-VERIFIED | Existing automated suite and preserved commands. |
| Structured memory and ContextEngine snapshots | IMPLEMENTED AND TEST-VERIFIED | Canonical models/engine and tests; not automatically joined to every chat. |
| Planning and bounded execution compositions | IMPLEMENTED AND TEST-VERIFIED | Cumulative packages through WP060; not an automatic durable loop. |
| PR/main repository quality CI | IMPLEMENTED AND TEST-VERIFIED | Successful GitHub-hosted runs from WP062 onward. |
| Process-local bounded chat | IMPLEMENTED AND TEST-VERIFIED | Deterministic provider mocks and contract tests. |
| Ollama conversational adapter | IMPLEMENTED BUT NOT PHYSICALLY VALIDATED for this interval | `/api/chat` code and tests; no recovered physical Ollama PASS. |
| Model recommendation, confirmation and binding | IMPLEMENTED AND TEST-VERIFIED | Deterministic offline tests; physical inventory not proven. |
| One-turn contextual approval and transport | IMPLEMENTED AND TEST-VERIFIED | Programmatic path and mocked provider serialization. |
| Human-facing contextual consent UI | NOT IMPLEMENTED | Trusted caller must obtain approval; no new CLI consent workflow. |
| Automatic memory retrieval/RAG | NOT IMPLEMENTED | Explicitly outside WP065. |
| Conversational model autonomous tools/actions | NOT IMPLEMENTED | No tools supplied; output has no dispatch authority. |
| Persistent chat or durable approvals | NOT IMPLEMENTED | Process-local state only. |
| Distributed/multi-node resource coordination | NOT IMPLEMENTED | Registry is explicit; no network discovery/scheduler. |
| Durable cross-process continuation/recovery | NOT IMPLEMENTED | No persistent transcript or approval recovery. |

An internal API is not automatically a user-facing capability. Mock-backed
provider tests are not physical deployment evidence. The implemented seams do
not amount to the full IRIS product vision.

## 19. Debt, risks and limitations

### CONFIRMED

- Cumulative earlier execution compositions retain broad input/result surfaces
  and repeated cross-layer validation; source and tests visibly carry that
  maintenance cost.
- The automated suite grew from 2,381 passing tests at WP062 to 2,474 at WP065,
  increasing CI execution and maintenance surface.
- WP065 approval depends on a trusted caller and is not authentication or a
  complete consent UI.
- Context may be reproduced in assistant output even though the payload is not
  stored in session history.
- JSON/delimiter encoding is not prompt-injection immunity.
- Character limits are not tokenizer/model-window guarantees.
- No physical Ollama run was recovered for WP063–WP065; ordinary CI explicitly
  disables that opt-in path.
- GitHub CI uses Ubuntu 24.04; it is not Windows deployment verification.
- A historical Windows isolated-build permission problem was reported during
  WP065 verification, while wheel and sdist succeeded using an authorized
  writable/short-path workaround and canonical CI subsequently passed. This is
  environment evidence, not proof of a canonical packaging defect.
- Sessions, approvals and replay registries are process-local; durable recovery
  and cross-process transactions are absent.

### POTENTIAL

- Repeated validation across context, runtime, provider and session layers may
  drift if future contracts evolve independently.
- Runtime character accounting and a provider's real tokenizer window may
  diverge for some models.
- A compromised or mistaken trusted caller can undermine the intended approval
  decision despite exact process-local binding.
- Future provider implementations may interpret contextual transport
  differently unless compatibility tests stay strict.
- Larger inventories or multi-device resources may expose assumptions not
  exercised by the current explicit local registry.

### FORWARD

- Whether and how to add a genuine contextual-consent interface.
- Whether durable conversations, recovery or approval audit require a separate
  persistence and identity design.
- Whether physical Windows/Ollama, hardware and multi-device verification
  should gain distinct test environments.
- Whether cumulative composition boilerplate can be reduced without moving
  authority or weakening exact lineage.

These are classifications, not remediation plans or authorizations.

# PART XII --- VERIFICATION HISTORY

## 20. Evidence ledger

| Stage | Local/report evidence recoverable | PR CI | Canonical post-merge CI | Physical integration |
| --- | --- | --- | --- | --- |
| WP061 | PR report: focused WP038 `66 passed`; recording/PlanRun regressions `264 passed`; full `2381 passed, 1 skipped`; Ruff lint and mypy pass; wheel/sdist pass outside the Windows sandbox; repository-wide format still identified the then-known `system.py` debt. These are report evidence, not re-executed ACC evidence. | Not available: workflow not yet present. | Not available: workflow not yet present. | Not reported as executed. |
| WP062 | Implementation report records controlled failure propagation and AST-equivalent `system.py` formatting. | [run 39268230739](https://github.com/fermaxvago/IRIS/actions/runs/39268230739): success; `2381 passed, 1 skipped`; Ruff lint/format, mypy and build successful. | [run 39269011808](https://github.com/fermaxvago/IRIS/actions/runs/39269011808): success with the same test counts and required steps. | Ollama skipped by contract. |
| WP063 | Focused conversational tests reported in PR; canonical counts independently visible in workflow logs. | [run 39462446229](https://github.com/fermaxvago/IRIS/actions/runs/39462446229): success; `2413 passed, 1 skipped`; Ruff lint/format, mypy and build successful. | [run 39477117177](https://github.com/fermaxvago/IRIS/actions/runs/39477117177): success with the same test counts. | Not executed/recovered. |
| WP064 | Deterministic discovery/routing/binding coverage recorded in source tests. | [run 39486809207](https://github.com/fermaxvago/IRIS/actions/runs/39486809207): success; `2448 passed, 1 skipped`; Ruff lint/format, mypy and build successful. | [run 39487683926](https://github.com/fermaxvago/IRIS/actions/runs/39487683926): success with the same test counts. | Not executed/recovered. |
| WP065 | Focused context-binding implementation run reported `26 passed`; full canonical counts independently visible in CI. | [run 39504183320](https://github.com/fermaxvago/IRIS/actions/runs/39504183320): success; `2474 passed, 1 skipped`; Ruff lint/format, mypy and build successful. | [run 39505132508](https://github.com/fermaxvago/IRIS/actions/runs/39505132508): event `push`, exact canonical head, completed `success`; `2474 passed, 1 skipped`; required quality/build steps successful. | Not executed/recovered. |

The skipped test is the explicit physical Ollama integration boundary. A skip is
not an executed physical validation. Counts and outcomes above come from the
named sources; unavailable evidence is not inferred from adjacent WPs.

### ACC-WP065 authoring verification

These checks belong to the later documentation work, not the represented
historical state. A fresh Windows sandbox run initially reached `2453 passed,
1 skipped` with 21 setup errors because pytest could not create its default
temporary directory. Repeating the unchanged suite with an explicit writable
base directory completed with `2474 passed, 1 skipped`. Repository-wide Ruff
lint passed; Ruff reported 340 files already formatted; strict mypy reported no
issues in 260 source files.

The ordinary isolated local build could not download its isolated setuptools
requirement because this sandbox has no package-index network access. A
no-isolation fallback completed the source-distribution phase, then the wheel
phase encountered the known Windows long-path environmental limit. This is not
reported as a local build PASS. The canonical WP065 PR and post-merge Linux CI
builds above did pass; the later ACC pull request must supply its own fresh CI
evidence.

# PART XIII --- ARCHITECT SUCCESSION, LIMITS AND NON-CLAIMS

## 21. Recovery procedure

The durable succession rules remain those in
[ARCHITECT-SUCCESSION-FOUNDATIONS](ARCHITECT-SUCCESSION-FOUNDATIONS.md):

```text
architectural memory != architectural judgment
continuity documentation != autonomous Architect
historical CURRENT != present-day CURRENT
verified contract != permanent future design
recovered intent != implemented behavior
```

A future Architect should:

1. Verify canonical repository access and identify the current branch tip.
2. Locate the latest valid ACC rather than assuming this is still latest.
3. Verify the checkpoint's represented historical SHA and Git objects.
4. Reconstruct integration lineage and distinguish implementation, PR, merge,
   represented and documentation commits.
5. Inspect source at the represented SHA before accepting code claims.
6. Recover the authority map and frozen responsibility boundaries.
7. Separate source-proven facts from report and design-history evidence.
8. Inspect confirmed limitations, potential risks and forward questions.
9. Inspect present-day canonical source before making new decisions.
10. Run a separate Q1 -> Q2 -> Q3 -> Contract Pass for new work.
11. Require independent review of future implementation and evidence.
12. Preserve human-only merge authority.

This procedure supports recovery when the original conversation is unavailable;
it does not authorize a successor to act autonomously.

## 22. Verification limits and explicit non-claims

This checkpoint does not claim:

- that passing tests prove factual model output or complete security;
- that declared local resources are physically local in every deployment;
- that approval proves human identity or informed consent;
- that contextual formatting prevents all prompt injection;
- that Linux CI validates Windows, hardware or physical Ollama behavior;
- that a route, session, approval, request or binding authorizes tools;
- that local atomic history rolls back provider computation;
- that process-local guards provide durable distributed exactly-once behavior;
- that IRIS has persistent conversational memory, autonomous resource
  management, automatic recovery or a production-ready agent loop; or
- that any FORWARD question is approved future work.

## FINAL CONTINUITY STATEMENT

At canonical commit `7f60284a6a1eec4dab6776a825803d23c30b1b84`,
IRIS preserves the execution and lineage walls recorded by ACC-WP060; corrects
canonical observation preservation without moving recording authority; produces
commit-associated Linux repository-quality evidence; supports bounded,
process-local conversation; can recommend and bind an explicitly confirmed
local conversational resource through the existing deterministic router; and
can disclose exact, fresh, approved ContextSnapshot evidence to that exact
resource for one turn through a contextual-capable provider.

It does not thereby acquire persistent chat, authentication, automatic memory
retrieval, physical-deployment proof, autonomous tools, automatic continuation,
durable recovery or human-independent merge authority. Context remains
information, approval remains bounded disclosure permission, and model output
remains text rather than permission to act.

**ACC-WP065 stops at this historical photograph.**
