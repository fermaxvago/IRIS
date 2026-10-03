# IRIS --- ARCHITECTURE CONTINUITY CHECKPOINT --- ACC-WP035

**Checkpoint:** ACC-WP035\
**Date:** 2026-10-03\
**Canonical repository:** `https://github.com/fermaxvago/IRIS`\
**Canonical branch:** `main`\
**Canonical state:** WP035 merged through pull request 37\
**Canonical main SHA:** `006f908677466231d4fba77954aac683f840847f`\
**WP035 implementation SHA:** `0b73aa2f0a9fe33ca3cb9fdaa06d1d92ce8e0d21`\
**WP035 merge parent:** `da44ed7d46d6043579c31a28e4994ed738e26fde`

## 0. Purpose and interpretation

ACC-WP035 is a durable architectural history artifact. It records the system
that canonical `main` proves through WP035, the responsibility and authority
boundaries established by WP031--WP035, the causal and currentness invariants
later work must preserve, and the publication incident that strengthened the
continuity method.

Interpret this document with three labels:

- **FROZEN:** implemented decisions and contracts that should not be reopened
  casually.
- **CURRENT:** repository state at the represented canonical commit.
- **FORWARD:** a non-binding unresolved seam. It is neither authorization nor a
  Work Package design.

**Preserve the reasoning; do not blindly preserve the prediction.**

Repository code remains authoritative. This checkpoint is historical: later
work may supersede statements labeled **CURRENT**, but must not rewrite this
record of the architecture at `006f908677466231d4fba77954aac683f840847f`.

# PART I --- VERIFIED CANONICAL LINEAGE

## 1. Accepted WP031--WP035 history

The following merge lineage was verified in canonical `main`:

| Work Package | Pull request | Merge commit | Accepted implementation tip |
| --- | ---: | --- | --- |
| WP031 | 33 | `5f0378e3e5a8b82ebde4b88eaec52136a896fdb2` | `942bce399b0e4f40f721f4c6c3fb7100f28fd06f` |
| WP032 | 34 | `53da3c80425168b56309b00e5e4e04b015daba11` | `5da74395e3fdcd7fc3386bb4cdd3674a6c857863` |
| WP033 | 35 | `6fc21d958d2861640a1eb03519494967277a4a62` | `e17e7cd54c22ce7e16c29f3bad111325ae908208` |
| WP034 | 36 | `da44ed7d46d6043579c31a28e4994ed738e26fde` | `aad30a45fccb05164cc3961c37f7942caabed253` |
| WP035 | 37 | `006f908677466231d4fba77954aac683f840847f` | `0b73aa2f0a9fe33ca3cb9fdaa06d1d92ce8e0d21` |

The implementation tips are the accepted branch tips merged by the listed
merge commits. ACC-WP035 begins from the exact post-WP035 merge, not from an
implementation branch or recovery artifact.

## 2. Era extension

ACC-WP030 ended at one optional PlanRun advancement and one fresh inert
`ControlDecision`. The accepted architecture now adds:

```text
ERA I --- Fresh-selection materialization    WP031--WP033
ERA J --- Orchestration and request boundary WP034--WP035
```

These eras describe bounded composition seams. They are not an autonomous
lifecycle, scheduler or execution loop.

# PART II --- CURRENT BOUNDED PIPELINE

## 3. Accepted cumulative chain

**CURRENT/FROZEN:** the durable post-execution pipeline through WP035 is:

```text
ExecutionResult
    -> PlanObservation
    -> recorded observation/evidence
    -> StepOutcomeAssessment
    -> StepProgressTransitionDecision
    -> optional StepProgressUpdate
    -> optional one-revision PlanRun advancement
    -> fresh ControlDecision
    -> optional selected-step handling preparation
    -> optional canonical selected-step WorkSubject
    -> optional WorkSubject-owned ContextSnapshot
    -> optional OrchestrationDecision
    -> optional canonical ExecutionRequest
    -> STOP
```

The Work Package boundaries are:

```text
WP026  ExecutionResult -> recorded evidence and new Run revision -> STOP
WP027  current Run evidence -> StepOutcomeAssessment -> STOP
WP028  assessment -> StepProgressTransitionDecision -> STOP
WP029  actionable transition -> optional StepProgressUpdate -> STOP
WP030  optional update -> optional N+1 Run + fresh control -> STOP
WP031  fresh selected control -> optional handling preparation -> STOP
WP032  selected step -> optional canonical WorkSubject -> STOP
WP033  WorkSubject -> optional ContextSnapshot -> STOP
WP034  prepared handling + subject + context + availability
       -> optional OrchestrationDecision -> STOP
WP035  optional OrchestrationDecision
       -> optional canonical ExecutionRequest -> STOP
```

No arrow in this description implies recursive or automatic continuation.

## 4. Authority map through WP035

| Responsibility | Canonical owner |
| --- | --- |
| Plan structure | `iris.planning` |
| PlanRun validation and mutation | `iris.plan_runs` |
| PlanRun control and selection | WP013, `iris.plan_control` |
| Selected-step handling preparation | WP014, `iris.plan_handling` |
| Stable operational work identity | WP015, `iris.work_identity` |
| Explicit context construction and selection | WP016, `iris.context` |
| Orchestration policy and decision | WP017, `iris.orchestrator` |
| Canonical execution-facing request model | WP018, `iris.execution.ExecutionRequest` |
| Current PLAN_STEP execution binding | WP024 |
| PLAN_STEP admission, activation and start | WP025 |
| Post-execution evidence-to-control chain | WP026--WP030 |
| Fresh selection to handling composition | WP031 |
| Fresh selection to stable work identity | WP032 |
| Selected work to explicit ContextSnapshot | WP033 |
| Contextualized prepared work to orchestration | WP034 |
| Orchestration decision to ExecutionRequest | WP035 |

# PART III --- WP031--WP035 ACCEPTED AUTHORITIES

## 5. WP031 --- selected-step handling preparation

**FROZEN:** `iris.plan_step_handling_preparation` invokes WP030 exactly once
and consumes only its exact post-advancement artifacts.

It:

- returns no handling preparation when advancement is absent;
- returns no handling preparation when fresh control is not `STEP_SELECTED`;
- invokes WP014 exactly once when the fresh decision is `STEP_SELECTED`;
- passes the exact successor Run and exact fresh `ControlDecision`;
- obtains the selected step identity only from fresh control;
- accepts and resolves no `StepHandlingSpecification`;
- preserves the exact WP014 result; and
- stops before orchestration or execution.

`HANDLING_UNSPECIFIED`, `INSUFFICIENT_DETAIL` and `PREPARED` are legitimate
bounded outcomes. Neither `PREPARED` nor `STEP_SELECTED` is execution
authorization.

```text
ControlDecision != HandlingNeed != execution permission
```

## 6. WP032 --- selected-step WorkSubject materialization

**FROZEN:** `iris.plan_step_work_subject_materialization` invokes WP031 exactly
once. Fresh `STEP_SELECTED` control, not caller prediction, determines whether
selected work exists and which step is materialized.

It:

- produces no `WorkSubject` outside the fresh selected path;
- invokes WP015 `work_subject_from_plan_step(...)` exactly once when selected
  work exists;
- passes the exact successor Run as validation context;
- uses the fresh selected `step_id`, which may differ from the processed input
  `step_id`;
- does not gate identity on handling status;
- synthesizes no `WorkOrigin`; and
- stops before Context, orchestration or execution.

Canonical PLAN_STEP work identity is stable over:

```text
plan_id + run_id + step_id
```

It contains no PlanRun revision. Therefore:

```text
stable WorkSubject identity != current PlanRun revision witness
```

## 7. WP033 --- selected-step ContextSnapshot materialization

**FROZEN:** `iris.plan_step_context_materialization` invokes WP032 exactly
once.

When no `WorkSubject` exists, `context_snapshot` is `None` and
`ContextEngine.build(...)` is not called. When the subject exists, WP033 calls
the ContextEngine exactly once with:

- the exact WP032 `WorkSubject`;
- caller-supplied `ContextCandidate` values;
- caller-supplied `ContextBudget`;
- caller-supplied `ContextUncertainty` values; and
- caller-supplied `created_at`.

WP033 performs no retrieval, MemoryService query, context-source discovery,
origin synthesis or enrichment. The exact subject owns the snapshot.

An empty snapshot is a real snapshot. Snapshot absence means no subject existed
for contextualization; it does not mean no item was selected. Canonical status
values such as `RESOLVED`, `PARTIAL`, `AMBIGUOUS` and `CONFLICTED` are preserved
without operational continuation.

```text
Context ownership != PlanRun revision currentness
Context status    != orchestration decision
context issue     != handling relevance
```

## 8. WP034 --- post-Context PlanStep orchestration

**FROZEN:** `iris.plan_step_orchestration` invokes WP033 exactly once and
preserves all cumulative artifacts.

Its public surface is:

- `PlanStepOrchestrationComposer`;
- `PlanStepOrchestrationResult`;
- `PlanStepOrchestrationError`; and
- `PlanStepOrchestrationInvariantError`.

Its gate is exact handling-preparation status:

| Upstream state | WP017 calls | Result |
| --- | ---: | --- |
| No selected subject/context | 0 | no decision |
| `HANDLING_UNSPECIFIED` | 0 | no decision |
| `INSUFFICIENT_DETAIL` | 0 | no decision |
| `PREPARED` | exactly 1 | exact WP017 decision |

For `PREPARED`, WP034 validates the exact revision-sensitive preparation and
constructs one transient `OrchestrationInput` containing:

- the exact `WorkSubject`;
- the exact `ContextSnapshot`;
- a one-element tuple holding the exact prepared `HandlingNeed`; and
- the exact caller-supplied `HandlerAvailability`.

It invokes WP017 exactly once, validates the returned decision against the
exact subject and snapshot, preserves that decision and stops.

`HandlerAvailability` is an explicit declaration. It is not discovery,
authorization, a reservation or durable evidence of later availability. WP034
does not discover capabilities, enrich handling, synthesize `ContextBlocker`
values, construct an execution request, bind, activate, execute, mutate,
retry, fall back or continue.

An unavailable prepared handler still crosses WP017 and yields a canonical
`UNSATISFIED` decision. `UNSATISFIED` is a real decision, not orchestration
absence or a programming failure.

```text
Context status                    != OrchestrationDecision
HandlingNeed                      != HandlerAvailability
availability declaration         != availability discovery
availability declaration         != durable availability proof
UNSATISFIED                       != orchestration failure
CLARIFY                           != immediate user interaction
OrchestrationDecision            != ExecutionRequest
OrchestrationDecision            != execution
WorkSubject identity              != HandlingNeed identity
decision currentness              != availability currentness
decision currentness              != PlanRun revision currentness
```

Exact ContextSnapshot instance identity matters. A decision bound to one
snapshot is not current for a different snapshot of the same WorkSubject.

## 9. WP035 --- post-orchestration ExecutionRequest materialization

**CURRENT/FROZEN:**
`iris.plan_step_execution_request_materialization` invokes WP034 exactly once
and appends at most one canonical WP018 `ExecutionRequest`.

Its public surface is:

- `PlanStepExecutionRequestMaterializer`;
- `PlanStepExecutionRequestMaterializationResult`;
- `PlanStepExecutionRequestMaterializationError`; and
- `PlanStepExecutionRequestMaterializationInvariantError`.

Its primary inputs include the exact WP034 inputs plus explicit
`ExecutionInput | None`. Its constructor owns or injects:

- the WP034 composer;
- the request clock; and
- the execution-ID factory.

WP035 defensively validates the entire delegated causal lineage before request
construction. Its exact branch is:

```text
orchestration_decision is None
    -> execution_request=None
    -> execution-ID factory calls=0
    -> request-clock calls=0
    -> STOP

orchestration_decision exists
    -> reuse exact WorkSubject
    -> reuse exact ContextSnapshot
    -> reuse exact OrchestrationDecision
    -> generate exactly one independent execution_id
    -> read request clock exactly once
    -> construct exactly one canonical ExecutionRequest
    -> preserve exact caller-supplied execution_input
    -> STOP
```

The causal ordering is frozen:

```text
WP034 -> execution ID -> request clock -> ExecutionRequest -> STOP
```

The request timestamp is not obtained before the decision exists. WP035 does
not clamp or replace a clock value that predates the decision; canonical WP018
validation rejects the invalid temporal ordering.

WP035 neither invokes WP024 nor pre-applies WP024 bindability policy. It does
not bind, admit, activate, execute, invoke an `ExecutionCoordinator`, discover
a handler, retry, persist, mutate or continue.

# PART IV --- EXECUTION-REQUEST SEMANTICS

## 10. Terminal decisions still have requests

**FROZEN correction established during WP035:** canonical WP018 supports an
`ExecutionRequest` for executable and terminal orchestration targets.

Executable targets are:

- `SYSTEM`;
- `MEMORY`;
- `CAPABILITY`; and
- `INTELLIGENCE`.

Terminal targets are:

- `CLARIFY`; and
- `UNSATISFIED`.

Terminal requests carry `execution_input=None`. Consequently:

```text
terminal decision != request absence
UNSATISFIED       != no request
```

WP035's successful result shape is:

```text
orchestration_decision exists iff execution_request exists
```

This does not mean every valid request is later bindable or executable.

## 11. Request validity is not PlanStep bindability

WP018 owns canonical request validity. WP024 separately owns PLAN_STEP binding
rules and admits only executable targets for binding.

A terminal WP018 request can therefore be valid and later be rejected as
non-bindable by WP024. WP035 must not use the later boundary's policy to
suppress request construction.

The authority wall is:

```text
Decision
    != Request
    != Binding
    != Admission
    != Activation
    != Execution
```

## 12. ExecutionInput remains explicit

WP035 receives execution operands explicitly. It does not infer them from
Context, PlanStep text or any upstream artifact.

```text
ExecutionInput != Context
ExecutionInput != PlanStep objective
ExecutionInput != expected outcome
```

WP035 does not derive inputs from `ContextSnapshot`, Memory, `HandlingNeed`,
availability, capability metadata or the orchestration reason. WP018 owns
target-specific input validation, including the rule that terminal decisions
must not contain an execution input.

## 13. Current generic CAPABILITY reachability

WP031 calls WP014 without a `StepHandlingSpecification`. Under the current
canonical handling contract:

| `PlanStep.required_handling` | Preparation result |
| --- | --- |
| `None` | `HANDLING_UNSPECIFIED` |
| `SYSTEM` | `INSUFFICIENT_DETAIL` |
| `MEMORY` | `INSUFFICIENT_DETAIL` |
| `INTELLIGENCE` | `INSUFFICIENT_DETAIL` |
| `CAPABILITY` | `PREPARED` generic need |

The generic capability need has `capability_id=None` and `blockers=()`.
Therefore the natural executable WP034/WP035 path at this checkpoint is
primarily generic CAPABILITY.

A caller may provide a canonical `CapabilityExecutionInput` and obtain a valid
WP018 request even when `capability_id` is absent. WP035 does not discover or
enrich capability identity. Later binding or execution boundaries retain their
own authority to reject what they cannot bind or execute.

## 14. Natural UNSATISFIED path

The current cumulative path can naturally produce:

```text
PREPARED generic CAPABILITY handling
    + capability availability declared false
    -> WP017 invoked once
    -> UNSATISFIED OrchestrationDecision
    -> WP035 canonical ExecutionRequest
    -> execution_input=None
    -> STOP
```

```text
UNSATISFIED != no request
UNSATISFIED != retry
UNSATISFIED != fallback
UNSATISFIED != automatic clarification
```

# PART V --- CROSS-WP INVARIANTS

## 15. Exact-artifact preservation

Each composition preserves delegated causal artifacts rather than replacing
them with equivalent-looking values:

- WP031 preserves WP030 assessment, transition, update and advancement;
- WP032 preserves WP031 artifacts and the exact WP015 subject;
- WP033 preserves WP032 artifacts and the exact WP016 snapshot;
- WP034 preserves WP033 artifacts and the exact WP017 decision; and
- WP035 preserves all WP034 artifacts and constructs one exact WP018 request.

When a WP035 request exists:

```text
request.subject  is result.work_subject
request.context  is result.context_snapshot
request.decision is result.orchestration_decision
```

For a non-`None` execution input, canonical WP018 also preserves the exact
caller-supplied input object.

## 16. Invocation-local call cardinality

| Composition | Always invoked | Conditional delegated boundary |
| --- | --- | --- |
| WP031 | WP030 exactly once | WP014 once only for fresh `STEP_SELECTED` |
| WP032 | WP031 exactly once | WP015 once only for selected work |
| WP033 | WP032 exactly once | WP016 once only when a subject exists |
| WP034 | WP033 exactly once | WP017 once only for `PREPARED` handling |
| WP035 | WP034 exactly once | WP018 request construction once only when a decision exists |

These guarantees are local to one invocation. They do not establish global
exactly-once processing, persistence, idempotency, leases or deduplication.
Repeated valid WP035 invocations may create distinct request identities over
the same exact subject, context and decision.

## 17. Layered currentness model

Currentness is not one interchangeable boolean. It is proven by different
artifacts at different boundaries.

### 17.1 PlanRun revision currentness

Revision-sensitive update, advancement and control artifacts establish their
exact source or successor Run revision.

### 17.2 WorkSubject identity

A PLAN_STEP `WorkSubject` identifies stable `plan_id + run_id + step_id`. It is
not revision-sensitive and does not independently prove current execution
lineage.

### 17.3 ContextSnapshot ownership

A snapshot owns the exact `WorkSubject`. That ownership does not prove a
particular PlanRun revision.

### 17.4 Handling preparation

`StepHandlingPreparationResult` and its prepared `HandlingNeed` are bound to
the selected-step successor revision.

### 17.5 OrchestrationDecision currentness

The decision is bound to the WorkSubject `subject_id` and exact ContextSnapshot
`snapshot_id`. This does not prove later availability freshness,
authorization, safety or PlanRun revision currentness by itself.

### 17.6 ExecutionRequest validity

The request reuses the exact subject, context and decision, then adds an
independent execution identity, request time and explicit operands. Validity
does not prove bindability, admission, activation, handler availability or
execution.

## 18. Temporal invariants

Canonical time ordering is:

```text
ContextSnapshot.created_at
    <= OrchestrationDecision.created_at
    <= ExecutionRequest.created_at
```

WP035 reads its request clock only after WP034 has returned a decision. Clock
skew is surfaced by model validation; the materializer does not silently use
the decision time or `max(clock(), decision.created_at)`.

## 19. Identity invariants

- WorkSubject identity is independent of request identity.
- ContextSnapshot identity is independent of request identity.
- OrchestrationDecision identity is independent of request identity.
- Every attempted request receives one independently generated `execution_id`.
- `execution_id` must not equal `subject_id`, `snapshot_id` or `decision_id`.
- Invalid or colliding IDs are rejected without retrying the ID factory.
- No hidden request registry or global deduplication exists in WP035.

## 20. Error ownership

Delegated domain errors remain recognizable and normally propagate. A
composition layer owns contradictions at its own seam: wrong delegated types,
foreign source lineage, mismatched optional shape, stale currentness or
cross-artifact identity contradictions.

WP035 does not convert canonical WP018 validation failures into request
absence, `UNSATISFIED`, fallback or retry. `execution_request=None` means only
that WP034 produced no orchestration decision.

## 21. Durable authority-separation wall

The following differences are architectural properties, not wording choices:

```text
Planning             != selection
selection            != handling preparation
handling preparation != WorkSubject identity
WorkSubject          != Context
Context              != orchestration
orchestration        != request construction
request              != binding
binding              != admission
admission            != activation
activation           != handler completion
execution result     != observation
observation          != assessment
assessment           != transition decision
transition decision  != mutation
mutation             != continuation
fresh control        != execution
```

# PART VI --- PUBLIC SURFACES AND DEPENDENCY DIRECTION

## 22. Verified public APIs

### WP031 --- `iris.plan_step_handling_preparation`

- `PlanStepHandlingPreparationComposer`
- `PlanStepHandlingPreparationResult`
- `PlanStepHandlingPreparationError`
- `PlanStepHandlingPreparationInvariantError`

### WP032 --- `iris.plan_step_work_subject_materialization`

- `PlanStepWorkSubjectMaterializer`
- `PlanStepWorkSubjectMaterializationResult`
- `PlanStepWorkSubjectMaterializationError`
- `PlanStepWorkSubjectMaterializationInvariantError`

### WP033 --- `iris.plan_step_context_materialization`

- `PlanStepContextMaterializer`
- `PlanStepContextMaterializationResult`
- `PlanStepContextMaterializationError`
- `PlanStepContextMaterializationInvariantError`

### WP034 --- `iris.plan_step_orchestration`

- `PlanStepOrchestrationComposer`
- `PlanStepOrchestrationResult`
- `PlanStepOrchestrationError`
- `PlanStepOrchestrationInvariantError`

### WP035 --- `iris.plan_step_execution_request_materialization`

- `PlanStepExecutionRequestMaterializer`
- `PlanStepExecutionRequestMaterializationResult`
- `PlanStepExecutionRequestMaterializationError`
- `PlanStepExecutionRequestMaterializationInvariantError`

## 23. Verified composition direction

The behavioral dependency direction is:

```text
WP031 -> WP030 + WP014
WP032 -> WP031 + WP015
WP033 -> WP032 + WP016
WP034 -> WP033 + WP017
WP035 -> WP034 + WP018 model
```

Higher layers import canonical models and validators for defensive validation,
but do not acquire lower-layer behavioral authority. WP035 has no behavioral
dependency on WP024, WP025 or `ExecutionCoordinator`.

# PART VII --- PUBLICATION INCIDENT AND CONTINUITY LESSONS

## 24. WP034 publication / WP035 hard-gate incident

The incident sequence was:

1. The Engineer completed WP034 and created a valid recovery bundle.
2. Direct push was unavailable, so local publication instructions were
   prepared.
3. Conversation moved to another topic before publication output was returned.
4. WP034 was later mistakenly treated conversationally as already merged.
5. WP035 began with an independent hard canonical-base gate.
6. The gate fetched `origin/main` and proved that it was still the pre-WP034
   state, that the WP034 implementation commit was not its ancestor and that
   `iris.plan_step_orchestration` was absent.
7. WP035 stopped before creating its implementation branch, changing files or
   performing implementation work.
8. The WP034 bundle was then located, SHA-256 checked, bundle-verified,
   imported and ancestry-verified.
9. WP034 was pushed, pull request 36 was audited and merged, and exact
   post-merge main `da44ed7d46d6043579c31a28e4994ed738e26fde` was verified.
10. WP035 was rerun only after its canonical gate passed.

This was not code loss or implementation corruption. It was a
publication/continuity-state assumption. The independent downstream base gate
contained the error before it could alter architecture on a false base.

## 25. Publication state distinctions

**FROZEN process invariants:**

```text
valid local implementation != canonical merge
valid recovery bundle      != publication
push                       != merge
conversational statement   != repository state
PR URL                     != proof of merge
```

A merge must be verified against canonical `main`. Each downstream Work
Package must independently resolve its authorized base, even when an upstream
report said implementation was complete.

## 26. Independent verification principle

Each verification result proves only what it actually checked:

```text
bundle verify                 != remote publication
remote branch                 != merged main
merged PR                     != assumed local synchronization
successful implementation report != canonical repository state
```

Independent checks should cross-check artifact integrity, ancestry, branch
state, PR diff, merge state, exact canonical main, tests and artifact lineage.
One analysis concluding “valid” does not eliminate the need for verification
at the next trust boundary.

## 27. Durable checkpoint rule

Carry forward the ACC-WP030 continuity rule: after coherent implementation and
focused/relevant verification establish a sane state, create a durable local
Git checkpoint before long or environmentally fragile gates.

The checkpoint is recoverability evidence, not publication approval. A later
failed gate may require a corrective commit and rerunning invalidated checks.
Interruption does not imply corruption; inspect the branch, HEAD, status, diff,
untracked files and completed evidence before reconstructing work.

# PART VIII --- RESEARCH SYNTHESIS AND CORRECTABLE PREDICTIONS

## 28. External architectural pattern

Across the examined agent and orchestration frameworks, a recurring high-level
shape was:

```text
STATE / RESULT
    -> ROUTING / CONTROL
    -> IDENTIFIABLE WORK TARGET
    -> CONTEXT / INPUT
    -> ORCHESTRATION / ROUTING DECISION
    -> EXECUTION-FACING REQUEST / COMMAND / TASK
    -> RUNTIME / SCHEDULER / BINDING
    -> EXECUTION
```

The useful synthesis for IRIS is the separation of work identity, context,
orchestration, request materialization, binding/admission and execution. IRIS
does not import framework-specific semantics when canonical repository
contracts differ.

## 29. Preserve reasoning, not predictions

During WP035 design, an initial provisional prediction suggested terminal
orchestration outcomes might produce no `ExecutionRequest`. Inspection of the
actual repository disproved it:

- WP018 permits terminal `CLARIFY` and `UNSATISFIED` requests; and
- WP024 owns the later rejection of terminal requests as non-bindable.

The design was corrected before implementation. This is desired architectural
behavior: repository evidence can invalidate a prediction without discarding
the reasoning discipline that produced and tested it.

# PART IX --- DEBT, VERIFIED LANDMARK AND STOP CONDITION

## 30. Known repository debt

- Repository-wide `ruff format --check .` remains red solely because of
  unchanged historical formatting debt in `iris/core/system.py`.
- ACC-WP035 documents but does not repair that unrelated file.
- No production semantics are changed by this checkpoint.

## 31. WP035 implementation-time verification landmark

The following is historical evidence recorded by the WP035 Engineer report. It
describes the implementation state when verified; it is not a permanent
guarantee about future repository revisions.

- Focused WP035 suite: 48 passed.
- Adjacent WP031--WP034/WP018/WP024/WP025 suites: 327 passed.
- Full suite: 1,158 passed and 1 integration test skipped.
- Ruff lint: passed.
- Strict mypy: passed.
- Compileall: passed.
- Dependency compatibility: passed.
- Editable installation: passed.
- sdist and wheel builds: passed.
- Isolated wheel installation: passed.
- Public import smoke: passed.
- `python -m iris`: passed.
- Installed `iris` entrypoint: passed.
- Dependency-direction inspection: passed.
- Secret-pattern scan: zero matches.
- `git diff --check`: passed.
- `git fsck --full`: passed with harmless dangling-object notices only.
- Recovery-clone focused suite: 48 passed.

## 32. Current stopping point

**CURRENT:** IRIS has a bounded cumulative post-execution path capable of
reaching one canonical `ExecutionRequest` for newly selected successor work.

It still does not automatically:

- bind that request to its selected PlanStep;
- admit it;
- activate it;
- invoke a handler;
- execute it;
- record a new result; or
- recursively continue the Plan.

The next unresolved architectural seam is between the newly materialized
canonical `ExecutionRequest` and the existing downstream PLAN_STEP
binding/admission/start machinery. This statement is **FORWARD** only. It does
not define or authorize a WP036 contract.

The accepted WP035 boundary remains:

```text
exact WP034 result
    -> optional canonical ExecutionRequest
    -> STOP
```

**Preserve the reasoning; do not blindly preserve the prediction.**

# PART X --- ENGINEER VERIFICATION METADATA

## 33. Checkpoint verification record

- Verified canonical main:
  `006f908677466231d4fba77954aac683f840847f`.
- Verification date: 2026-10-03.
- WP035 merge parent verified:
  `da44ed7d46d6043579c31a28e4994ed738e26fde`.
- WP035 implementation ancestry verified:
  `0b73aa2f0a9fe33ca3cb9fdaa06d1d92ce8e0d21`.
- Architectural body derived from canonical implementation, tests, package
  exports, repository history and the accepted WP035 report.
- Runtime behavior modified: no.
- Production code modified: no.
- WP036 behavior introduced: no.
- Architectural contradictions found: none.
- Reference Registry modified: no; this checkpoint preserves synthesis without
  introducing new external reference entries.
