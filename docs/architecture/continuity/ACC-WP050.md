# IRIS --- ARCHITECTURE CONTINUITY CHECKPOINT --- ACC-WP050

**Checkpoint:** ACC-WP050  \
**Date:** 2026-10-06  \
**Canonical repository:** `fermaxvago/IRIS`  \
**Canonical branch:** `main`  \
**Represented canonical state:** WP050 merged through pull request 55  \
**Represented canonical `main` SHA:** `cbae08200111848c778e382a068b6fcd4dda6b32`  \
**WP050 implementation SHA:** `f2506f0860f4fbd5465e9630cc679a75af943683`  \
**Prior continuity checkpoint:** [ACC-WP045](ACC-WP045.md)

## 0. How to read this checkpoint

ACC-WP050 is an immutable historical snapshot, recovery aid, authority map and
reasoning record for the exact repository state named above. It is not a
changelog, roadmap, feature design, WP051 contract or permission to continue
the pipeline.

The continuity labels have their established meanings:

- **FROZEN** records canonical implemented contracts, distinctions and
  responsibility boundaries proven by the represented repository.
- **CURRENT** records facts at commit
  `cbae08200111848c778e382a068b6fcd4dda6b32`. Later canonical work may
  supersede them without making this historical checkpoint incorrect.
- **FORWARD** records unresolved seams, debt, questions or possible directions.
  It is non-binding: no authorization, schedule, prediction or next-WP promise
  follows from it.

The governing continuity rule is:

> Preserve the reasoning; do not blindly preserve the prediction.

Repository code at the represented commit remains authoritative. The future
commit that adds this document is only a durable description of that state; it
is not part of the state represented by ACC-WP050.

# PART I --- CANONICAL ANCHOR AND VERIFIED LINEAGE

## 1. Represented state and previous checkpoint

**CURRENT:** the represented commit is the two-parent merge of:

1. pre-WP050 canonical `main`,
   `e0ae1ad550e2b050d3c4dea3fe520e6a3d023983`; and
2. WP050 implementation tip,
   `f2506f0860f4fbd5465e9630cc679a75af943683`.

Its tree is `528535a8e8560b6e2952b5e2054afc9e1543260d`. The merge subject identifies
pull request 55. The implementation tip is its second parent and has the same
tree as the merge.

ACC-WP045 represented the earlier runtime state at
`3381fab81c2780708c74ab9c37c554ee573d1e26`. Its documentation implementation
tip was `445685a841bfec8607b1e459cec0b3bcf25f6e19`, and that documentation entered
canonical history through pull request 50 at merge
`1fbefbe410c05badc9bc50240ae8caddc001efa4`.

**FROZEN:** the commit represented by an ACC, the later commit implementing its
documentation and the still-later merge containing that documentation are
different historical identities even when their content relationship is
straightforward.

## 2. Accepted WP046--WP050 lineage

The lineage below was recovered from commit parentage, ancestry and trees, not
from abbreviated handoff identifiers:

| Package | PR | Accepted implementation tip | Canonical merge |
| --- | ---: | --- | --- |
| WP046 | 51 | `eee142498cf00c1a9c435b430dc1805ecfe100ff` | `979e2fa902011afe27b3ee472a03a12c5104f8cd` |
| WP047 | 52 | `23f5484c2b592ac707bc00166d486a476bde8bb5` | `d8ea5c5aca9cae86835775cdf793729c575c0535` |
| WP048 | 53 | `8d8ed33d80dc5d43b61221c9fc215d88bfbd5e4c` | `d971c80567dfe5d115f371cdf67f23ce33afe5b4` |
| WP049 | 54 | `e433e5a1bd33859baea895eab63204b467b737d1` | `e0ae1ad550e2b050d3c4dea3fe520e6a3d023983` |
| WP050 | 55 | `f2506f0860f4fbd5465e9630cc679a75af943683` | `cbae08200111848c778e382a068b6fcd4dda6b32` |

For every row, the implementation tip is the second parent of the listed
merge, is an ancestor of represented `main`, and has the same content tree as
that merge. The first parent is the preceding canonical state.

**FROZEN:** implementation checkpoint, published branch, pull request and
canonical merge are separate lifecycle states. Tree equality can prove content
equivalence for a bounded decision; it does not make distinct commits
historically identical or excuse ancestry verification.

## 3. What changed after ACC-WP045

ACC-WP045 stopped at an optional exact Step C `ContextSnapshot`. WP046--WP050
extended that already-bounded second traversal one explicit seam at a time:

```text
Step C ContextSnapshot
    -> WP046: optional exact OrchestrationDecision
    -> WP047: optional exact ExecutionRequest
    -> WP048: optional exact PlanStepExecutionBinding
    -> WP049: optional exact PlanStepExecutionStartResult
    -> WP050: optional exact PlanStepExecutionResultRecordingResult
    -> STOP
```

Each layer composes an existing lower authority, preserves exact upstream
artifacts and defensively validates its own boundary. Repetition of explicit
seams does not create a recursive continuation engine or autonomous loop.

# PART II --- FROZEN ARCHITECTURAL FOUNDATION

## 4. Core separations

The represented architecture preserves these responsibility walls:

```text
routing != execution
planning != plan execution
selection != activation
execution != observation
observation != assessment
assessment != transition policy
transition decision != state mutation
WorkSubject != WorkOrigin
Context != Memory
OrchestrationDecision != ExecutionRequest

Decision
    != Request
    != Binding
    != Admission
    != Activation
    != Execution
    != Recording
    != Evidence Assessment
    != Step Transition
```

It also preserves:

```text
ExecutionStatus.SUCCEEDED != StepProgressState.SUCCEEDED
ExecutionStatus.FAILED    != StepProgressState.FAILED
ExecutionStatus.REJECTED  != automatically StepProgressState.NOT_STARTED
domain-valid              != canonically reachable
representability          != reachability
ACTIVE                    != completed
handler returned          != expected outcome satisfied
recording                 != durability, audit conclusion, assessment or continuation
invocation-local bounded cardinality != global exactly-once behavior
```

These distinctions are architecture, not documentation style.

## 5. Cumulative second traversal through WP050

The explicit bounded chain now represented is:

```text
earlier execution evidence
    -> assessment
    -> transition decision
    -> optional progress update
    -> optional advancement and fresh control
    -> Step C handling preparation
    -> Step C WorkSubject
    -> Step C ContextSnapshot
    -> optional Step C OrchestrationDecision
    -> optional Step C ExecutionRequest
    -> optional Step C PlanStepExecutionBinding
    -> optional Step C PlanStepExecutionStartResult
    -> optional Step C execution-result recording
    -> STOP
```

The Step B artifacts inherited by the cumulative result remain separate from
their post-recording Step C counterparts. In particular:

```text
orchestration_decision != post_recording_orchestration_decision
execution_request      != post_recording_execution_request
execution_binding      != post_recording_execution_binding
execution_start_result != post_recording_execution_start_result
execution_recording_result != post_recording_execution_recording_result
```

The A/B/C labels explain causal positions; they are not invented runtime
fields, and the architecture does not require their `step_id` values to differ.

## 6. Exact-artifact lineage

**FROZEN:** currentness and provenance depend on exact causal artifacts, not
only equivalent-looking scalar values. The chain preserves the exact current
Run revision, selected-step lineage, WorkSubject, ContextSnapshot,
OrchestrationDecision, ExecutionRequest, binding, active Run, start result,
execution observation and recording result where each exists.

This is not object-identity fetishism. It prevents silent reconstruction from
breaking provenance, authority or revision-sensitive currentness. Defensive
validation does not grant a composition layer ownership of the behavior it
checks.

# PART III --- ACCEPTED WP046--WP050 SEAMS

## 7. WP046 --- Context to orchestration

`iris.plan_step_execution_orchestration_composition` invokes the exact WP045
composer once per composition invocation. A missing Step C WorkSubject or a
non-`PREPARED` handling result produces no Step C orchestration decision. Only
the exact `PREPARED`, blocker-free `HandlingNeed` reaches WP017's canonical
`Orchestrator`.

The exact Step C WorkSubject, ContextSnapshot, HandlingNeed and caller-supplied
`post_recording_availability` form the orchestration input. Step B
`availability` remains distinct. `HandlerAvailability` is caller evidence for
that decision; it is not discovery, admission, authorization, execution
permission or proof of future availability.

WP017 owns target selection. WP046 neither derives policy from Context status
nor fabricates blockers. A real `UNSATISFIED` decision remains a real decision,
not absence. WP046 stops after preserving the exact optional Step C
`OrchestrationDecision`.

## 8. WP047 --- decision to request

`iris.plan_step_execution_request_materialization_composition` invokes WP046
once and materializes a canonical WP018 `ExecutionRequest` only when a real
Step C decision exists. It uses the exact subject, Context and decision,
explicit `post_recording_execution_input`, a fresh execution identity and a
fresh request timestamp. The inherited Step B request/input remain separate.

**FROZEN:** an `ExecutionRequest` is an explicit handoff artifact, not binding,
admission, activation or execution. A terminal `UNSATISFIED` decision may
produce a real request even though a later authority rejects it as
non-executable.

### 8.1 Reachability correction

The general domain model can represent `CLARIFY`, but the canonical Step C
path reaches orchestration only through `PREPARED` PlanStep handling, whose
canonical `HandlingNeed.blockers` is empty. Canonical `CLARIFY` requires
non-empty Context references drawn from supplied blockers. Therefore:

```text
domain-valid CLARIFY != canonically reachable CLARIFY on this Step C path
```

No layer weakens handling or orchestration contracts to make it reachable.

## 9. WP048 --- request to binding

`iris.plan_step_execution_binding_post_recording_composition` invokes WP047
once. An absent validated Step C request yields no binder call and no binding.
Every canonical validated request reaches WP024's
`PlanStepExecutionBinder` once within that invocation using the exact Plan,
post-recording successor Run, fresh control decision, handling preparation and
request.

WP024, not WP048, owns bindability. Consequently:

```text
request exists != request is bindable
binding exists != activation or execution
```

A canonical `UNSATISFIED` request reaches WP024 and raises its canonical
`NonExecutableExecutionRequestError`; the error is not converted to
`binding=None`. A forged CLARIFY-shaped cumulative result is rejected as
noncanonical before the binder. Such an adversarial fixture proves defensive
behavior, not canonical upstream reachability.

## 10. WP049 --- binding to execution start

`iris.plan_step_execution_start_post_recording_composition` invokes WP048
once. An absent binding yields no WP025 call and no Step C start result. With a
canonical binding, it invokes the exact
`PlanStepExecutionStartCoordinator` once using the exact Plan, exact
post-recording successor Run, request and binding.

WP049 crosses a materially stronger boundary than the preceding inert seams:
WP025 may activate Step C and invoke a real handler. WP049 does not pre-resolve
the handler, create its own ACTIVE update or call `PlanRunReducer` directly.

### 10.1 Handler unavailable

Execution-time handler absence is a successful canonical WP025 return:

```text
PlanStepExecutionStartResult exists
active_run = None
activation_update_id = None
ExecutionStatus.REJECTED
handler_reference = None
failure.code = "handler_unavailable"
Step C remains NOT_STARTED
```

This is a real start-boundary fact, not absence of a start result.
Orchestration-time availability does not guarantee execution-time handler
presence.

### 10.2 Activation and normal outcomes

When the handler is resolved, WP025 revalidates currentness, creates and
applies the canonical ACTIVE update, then invokes the handler. The exact active
Run has one revision beyond the Step C pre-activation Run. Normal handler
outcomes `SUCCEEDED`, `FAILED` and `REJECTED` all leave Step C `ACTIVE` at this
boundary. `ExecutionResult.started_at` is not the PlanStep ACTIVE timestamp.

Handler invocation implies that activation succeeded; activation does not
guarantee that a normal `ExecutionResult` returns to the caller.

## 11. Post-activation invocation failure

**FROZEN:** if handler invocation raises after activation, the ACTIVE Run is
already committed. `PlanStepExecutionInvocationError` preserves the exact
`active_run`, `activation_update_id` and `execution_id`.

The architecture does not roll ACTIVE back, retry the handler, fabricate a
FAILED `ExecutionResult`, fabricate a `PlanObservation`, fabricate a recording
result or continue as if a normal start result existed. Truthful partial
progress is preserved instead of inventing transactional history.

## 12. WP050 --- execution-result recording

Canonical package:

`iris.plan_step_execution_result_recording_post_recording_composition`

Canonical public surface:

- `PlanStepExecutionResultRecordingPostRecordingComposer`
- `PlanStepExecutionResultRecordingPostRecordingCompositionResult`
- `PlanStepExecutionResultRecordingPostRecordingCompositionError`
- `PlanStepExecutionResultRecordingPostRecordingCompositionInvariantError`

WP050 extends the exact WP049 cumulative result and adds only:

`post_recording_execution_recording_result`

The inherited `execution_recording_result` retains its earlier Step B causal
meaning. The result is frozen, slotted and serializes the exact optional WP026
artifact without hidden continuation state.

For one invocation reaching delegation, WP049 is invoked exactly once. If the
Step C start result is absent, WP026 is not called and the Step C recording
result is absent. If the start result exists, WP026's
`PlanStepExecutionResultRecorder` is invoked exactly once. These are
invocation-local call counts, not global exactly-once guarantees.

## 13. Exact WP050 recording base and local revisions

Let `C_pre` be the exact
`post_recording_advancement_result.updated_run`.

### 13.1 No Step C start

```text
start absent
    -> recorder not called
    -> no Step C execution observation
    -> no recording revision
    -> recording result absent
    -> STOP
```

### 13.2 Handler unavailable

When the real start result has no `active_run`, WP050 records against exact
`C_pre`:

```text
C_pre revision N, Step C NOT_STARTED
    -> recording
recorded revision N+1, Step C NOT_STARTED
```

No activation does not mean no execution fact. The canonical REJECTED
handler-unavailable result is recorded.

### 13.3 Activated execution

When `start_C.active_run` exists, that exact object is the recording base:

```text
C_pre revision N, Step C NOT_STARTED
    -> activation
active revision N+1, Step C ACTIVE
    -> recording
recorded revision N+2, Step C ACTIVE
```

Normal execution status may be `SUCCEEDED`, `FAILED` or `REJECTED`; recording
does not translate it into terminal StepProgress. Revision relationships are
local to the exact recording base. Earlier optional branches prohibit a fixed
offset from the original top-level Run.

## 14. Execution facts become evidence

WP050 delegates the canonical recording chain to WP026:

```text
ExecutionResult
    -> ExecutionObservationAdapter
    -> PlanObservation
    -> RecordObservationUpdate
    -> PlanRunReducer
    -> recorded successor PlanRun
```

The Run contains canonical `PlanObservation` evidence, not the raw
`ExecutionResult` as its evidence object. The execution observation preserves:

```text
source = "execution"
source_reference = execution_id
kind = "execution_result"
```

WP026 owns adaptation, update construction and Run reduction. WP050 validates
the returned causal relationships but does not own those behaviors. Its rule
is:

> RECORD THE FACT. DO NOT INTERPRET THE FACT.

# PART IV --- WP050-C1 AND CANONICAL ORDERING

## 15. Contradiction discovered during WP050

The WP050 implementation instruction initially inherited WP038's positional
assumption about newly recorded observations. Canonical WP012 `PlanRun`
construction instead sorts observations by `observation_id`, while WP026
requires one additional exact adapter-produced observation without requiring
the final tuple position.

WP038 additionally requires the prior observations to remain a tuple prefix
and the new observation to be the last element. These contracts are not
universally compatible. For example:

```text
existing: evidence-a
new:      aaa-execution-observation

canonical PlanRun order:
    aaa-execution-observation
    evidence-a
```

Existing WP038 fixtures happened to use append-compatible identifiers and did
not expose the contradiction. The Engineer stopped before implementation,
reported exact code evidence and waited for correction rather than copying the
defect or widening WP050 into an unauthorized WP038 repair.

## 16. WP050-C1 canonical decision

**FROZEN:** WP012/WP026 ordering authority wins. WP050 validates semantic
preservation rather than positional append:

- recorded observation cardinality is base cardinality plus one;
- the exact new observation object is present;
- every exact prior observation object is present;
- no prior observation is removed or replaced;
- no unrelated observation is introduced;
- observation identities remain unique; and
- the tuple follows canonical PlanRun ordering.

The new observation may appear before, between or after prior observations.
Position is not part of the WP050 contract. Canonical real-object tests cover
all three positions and adversarial replacements/removals/extras.

## 17. CURRENT WP038 debt

At represented `main`, WP038 still checks that prior observations form a tuple
prefix and that the newly recorded observation is last. This conflicts with
canonical `PlanRun` ordering for valid identifiers that sort earlier.

WP050 deliberately did not modify WP038 or its historical tests. The defect is
known CURRENT architectural debt, not an authorization or schedule for repair.

# PART V --- FAILURE SEMANTICS AND NON-GUARANTEES

## 18. External effects may precede WP050 validation

By the time WP050 receives a successful WP049 return, a handler may already
have changed the external world. WP050 validates the cumulative result before
recording; it cannot retroactively guarantee validation before execution.

A malformed WP049 return may therefore be rejected before WP026 while an
external effect has already occurred. The architecture must not claim
otherwise.

## 19. Recording failure after execution

A valid sequence may be:

```text
Step C activation
    -> handler external effect
    -> normal ExecutionResult
    -> WP026 recording failure
```

WP050 propagates the recording failure. It does not rerun WP049, retry the
handler, roll back ACTIVE, compensate external effects, fabricate evidence,
fabricate successful recording or pretend execution did not occur. Recovery
or reconciliation belongs to a future explicit authority.

## 20. Error ownership and fail-closed composition

Owner-specific operational errors propagate unchanged. Composition invariant
errors are reserved for malformed or contradictory delegated artifacts at the
composition boundary. Layers do not silently normalize malformed artifacts,
invent missing history or convert errors into optional absence.

This philosophy preserves truthful partial state, exact causal lineage and
authority ownership even when the resulting state requires later operator or
architectural recovery.

## 21. Explicit non-guarantees

The represented architecture does not claim:

- global or distributed exactly-once execution;
- crash-safe replay or durable scheduler semantics;
- persistent deduplication across arbitrary retries;
- transactional execution plus recording;
- automatic compensation or rollback of external effects;
- self-healing execution or automatic malformed-state repair;
- durable audit-log equivalence for `PlanObservation`;
- recursive Plan execution or autonomous continuation; or
- a generic continuation, retry or recovery engine.

Invocation-local bounded calls must not be described as those stronger
properties.

# PART VI --- AUTHORITY MAP

## 22. Canonical ownership at WP050

| Responsibility | Canonical authority |
| --- | --- |
| Deterministic request routing | `iris.router` |
| Intelligence-provider routing | `iris.intelligence.routing` |
| Plan and PlanStep structure | `iris.planning` |
| Immutable Run/revision/observation semantics and mutation | `iris.plan_runs`, including `PlanRunReducer` (WP012 lineage) |
| Step selection and control | `iris.plan_control.PlanRunController` |
| Handling preparation | `iris.plan_handling.PlanStepHandlingPreparer` |
| Work identity and origin models | `iris.work_identity` |
| Context construction | `iris.context.ContextEngine` |
| Orchestration decision | `iris.orchestrator.Orchestrator` (WP017) |
| Execution request | canonical WP018 `ExecutionRequest` contract |
| PlanStep execution binding | `iris.plan_step_execution_binding.PlanStepExecutionBinder` (WP024) |
| Activation and execution start | `iris.plan_step_execution_start.PlanStepExecutionStartCoordinator` (WP025) |
| ExecutionResult adaptation | `iris.execution_observation.ExecutionObservationAdapter` (WP019) |
| Execution-result recording | `iris.plan_step_execution_result_recording.PlanStepExecutionResultRecorder` (WP026) |
| Complete Step-scoped evidence assessment | `iris.plan_step_evidence_assessment.PlanStepEvidenceAssessor` (WP027) |
| Transition policy | `iris.step_progress_transition.StepProgressTransitionDecider` |
| Progress update synthesis | `iris.step_progress_update_synthesis.StepProgressUpdateSynthesizer` |
| One-update advancement and fresh control | `iris.plan_run_advancement.PlanRunProgressAdvancer` |
| Step C Context-to-decision composition | WP046 |
| Step C decision-to-request composition | WP047 |
| Step C request-to-binding composition | WP048 |
| Step C binding-to-start composition | WP049 |
| Step C start-to-recording composition | WP050 |

Composition modules may validate exact lineage defensively. They do not inherit
ownership of the lower authority they invoke. WP050 owns neither evidence
assessment nor transition policy.

# PART VII --- CANONICAL REACHABILITY AND DEVELOPMENT DISCIPLINE

## 23. Representability is not reachability

**FROZEN:** a domain type may represent a state that one current canonical
upstream path cannot produce. Unsafe or adversarial construction in a test can
prove downstream rejection behavior; it cannot prove canonical upstream
reachability.

This distinction resolved the CLARIFY analysis across WP047/WP048. Architects
must inspect constructor invariants, preparation status, blocker ownership and
the complete upstream chain rather than infer paths from enum expressiveness.

## 24. Architect/Engineer contradiction protocol

The evidence priority preserved by the project is:

```text
REPOSITORY
    > LIVE GITHUB STATE
    > VERIFIED ARTIFACTS
    > REPORTS
    > CHAT MEMORY
    > ASSUMPTIONS
```

An Architect instruction authorizes work but is not infallible. When it
contradicts canonical repository behavior, the correct response is to stop,
preserve the workspace, report exact evidence and ask the smallest necessary
architectural question. The Architect then verifies, corrects explicitly and
resumes without widening scope. WP050-C1 is the canonical example at this
checkpoint.

## 25. Feature architecture method

Future feature architecture follows separate stages:

1. **Q1 — Blind Design:** reason from IRIS architecture and the current
   frontier; discuss the provisional boundary; stop.
2. **Q2 — Comparable Systems:** research analogous mechanisms without yet
   deciding adoption; stop.
3. **Q3 — Adopt / Adapt / Reject:** decide explicitly while preserving stronger
   IRIS boundaries; stop.
4. **Contract Pass:** inspect exact canonical signatures, types, Run source,
   cardinality, presence, error propagation, lineage, mutation and STOP
   boundary; stop.

Only then may a feature instruction be frozen. ACC creation itself is
historical recovery, not feature design.

## 26. Resource policy

The concise optimization order is correctness/efficacy, quality/safety,
efficiency, then capacity conservation. Critical cross-WP, side-effect and
recovery reasoning must not be weakened merely to save capacity. Capacity may
delay sending fragile implementation work; it does not turn incomplete
reasoning into authority.

# PART VIII --- PROCESS AND RECOVERY CONTINUITY

## 27. Independent verification doctrine

One successful check proves only what it checked:

```text
tests pass             != correct Git ancestry
clean worktree         != correct canonical base
valid bundle           != published branch
published branch       != correct PR
mergeable PR           != merged canonical state
merge                  != post-merge verification
domain-valid fixture   != canonical reachability
handler return         != expected PlanStep outcome satisfied
```

Redundant checks are intentional because their failure modes differ.

## 28. Workspace, repository and conversation are separate

```text
conversation state != workspace state != Git repository state != GitHub state
```

A chat claim does not mutate Git; an attachment is not automatically a local
file; a local branch is not a remote branch; a remote branch is not a merge;
and a merge does not update every local checkout. Every transition requires
fresh evidence.

## 29. Recovery incidents and durable lessons

This table records process history supplied through accepted Architect
continuity instructions. These are engineering lessons, not runtime contracts;
repository history was used where the incident has a Git identity.

| Incident | Safety mechanism | Durable lesson |
| --- | --- | --- |
| WP023 usage interruption | inspect surviving state before resuming | interruption requires recovery evidence, not assumption |
| WP026 recording-base contradiction | resolve exact delegated authority and lineage | errors must appear at their owning boundary |
| WP028 workspace loss after tests | rebuild from canonical history and create checkpoints earlier | test output cannot recover missing source; checkpoint before fragile gates |
| WP034/WP035 publication-state mismatch | downstream hard base gate | valid artifact is not canonical merge |
| WP037 publication command lacked repository anchoring | require exact repository path before publication commands | shell context is part of publication safety |
| WP041 instruction named an incorrect predecessor ACC tip | verify canonical Git lineage | repository evidence outranks Architect prose |
| WP044/WP045 unusual tip/base relationships | verify parents, ancestry, merge-base, trees and diff | content and history are separate evidence dimensions |
| WP047 analysis | separate domain-valid CLARIFY from reachable Step C paths | model expressiveness does not prove reachability |
| WP047 publication sequencing | post-merge verification after human action | process must expose human deviation rather than rewrite it |
| WP048 CLARIFY contradiction | stop and issue explicit correction | defensive fixtures are not reachability evidence |
| WP049 execution boundary | validate lineage before delegated start while acknowledging later effects | side-effect boundaries require stronger ordering discipline |
| WP050 positional-observation contradiction | stop, inspect WP012/WP026, issue WP050-C1 | preserve canonical semantics without expanding scope to repair WP038 |

The recurring lesson is to preserve reasoning, not blindly preserve a prior
prediction.

# PART IX --- CURRENT STATE AND DEBT

## 30. CURRENT represented repository state

At this checkpoint's represented state:

- canonical `main` is `cbae08200111848c778e382a068b6fcd4dda6b32`;
- latest canonical feature is WP050;
- WP050 implementation tip is
  `f2506f0860f4fbd5465e9630cc679a75af943683`;
- WP050 entered through pull request 55;
- previous continuity checkpoint is ACC-WP045; and
- the latest continuity pointer before this later ACC document is added still
  names ACC-WP045.

WP050 is canonical. ACC-WP050 itself is not part of the represented state.

## 31. CURRENT WP050 verification landmark

The accepted WP050 implementation report records:

- 97 focused tests passed;
- 390 required regression tests passed;
- 2007 full-suite tests passed and one opt-in external Ollama integration test
  was skipped;
- mypy, Ruff lint, changed-file formatting, compileall, diff integrity, Git
  fsck and authorized-base ancestry passed;
- isolated sdist/wheel build and isolated installation/dependency/API checks
  passed; and
- authority-boundary tests passed.

The initial full-suite run encountered 21 pytest setup errors caused by Windows
temporary-directory allocation. It had no assertion failures. A fresh explicit
workspace-local temporary root produced the successful full run. This is
historical verification evidence, not a new runtime guarantee.

## 32. CURRENT known debt

1. WP038 retains the positional observation invariant described in section 17.
   It is incompatible with canonical ordering for some valid observation IDs.
2. Repository-wide Ruff format checking remains red for unchanged pre-existing
   formatting debt in `iris/core/system.py`.

Neither debt was modified by WP050 or this documentation-only checkpoint.
Known debt does not automatically become the next work item.

## 33. CURRENT STOP boundary

The post-recording Step C path currently reaches canonical execution-result
recording and stops:

```text
exact optional Step C PlanStepExecutionStartResult
    -> exact optional WP026 PlanStepExecutionResultRecordingResult
    -> STOP
```

This cumulative Step C path does not yet establish a subsequent canonical
Step C evidence assessment, transition decision, progress update, advancement,
fresh control, Step D or recursive loop. Analogous lower authorities already
existing elsewhere means possible reuse, not authorization.

# PART X --- FORWARD, NON-BINDING SEAMS

## 34. Immediate unresolved frontier

**FORWARD:** the next unresolved causal boundary begins after Step C
execution-result recording. A future Blind Design may consider assessment or a
different concern. ACC-WP050 neither predicts nor authorizes WP051.

## 35. WP038 corrective possibility

**FORWARD:** a separately authorized corrective package may eventually align
WP038 with canonical PlanRun ordering while preserving exact observations,
historical compatibility and regression safety. Known defect is not automatic
schedule; ACC-WP050 authorizes no repair.

## 36. Recovery and reconciliation

**FORWARD:** execution may affect the world while later canonical recording
fails. Future architecture may need explicit detection, reconciliation,
replay/idempotency boundaries, operator intervention, durable execution
journals, recovery evidence or compensation where possible. No solution is
specified here, and WP050 provides none.

## 37. Broader IRIS direction

**FORWARD:** IRIS may evolve toward one coherent identity across multiple
nodes, provider-swappable intelligence, explicit capabilities and authority,
bounded Context, persistent Memory, evidence-backed decisions, controlled
execution, recoverable state and observable provenance. Distributed execution
must preserve or strengthen identity, least authority, currentness, evidence,
side-effect boundaries and recovery semantics.

Candidate safety/recovery primitives remain non-binding concepts: evidence
graphs, artifact provenance, sandboxing, snapshots/diffs, runtime guards,
privilege leases, semantic health checks, watchdogs, incident replay,
minimal-delta repair, restore verification and canaries. They are not CURRENT
implemented subsystems unless later repository evidence proves otherwise.

As impact or uncertainty increases, future work should demand proportionally
stronger evidence, authority, verification, reversibility or human involvement.
This is direction, not an implemented policy engine.

If MARK or self-improvement is revisited, experience may become evidence for
proposals; it does not become self-authorization. A conceptual lifecycle from
observe through design, simulation, validation, gated adoption and monitoring
remains FORWARD, not current autonomous deployment.

# PART XI --- FUTURE ARCHITECT RECOVERY

## 38. Safe recovery procedure

1. Verify the live repository, remotes and current GitHub state.
2. Read this ACC as a historical snapshot, not current truth by default.
3. Compare current repository state with represented commit
   `cbae08200111848c778e382a068b6fcd4dda6b32`.
4. Treat later canonical repository evidence as authoritative over CURRENT
   statements here.
5. Preserve FROZEN reasoning unless later canonical architecture explicitly
   supersedes it.
6. Treat every FORWARD section as non-binding.
7. Do not infer the next package from the last visible pipeline seam.
8. Perform Blind Design before comparable-systems research for a feature.
9. Inspect exact live signatures, types, lineage and authority before issuing
   implementation instructions.
10. If Architect text conflicts with repository behavior, stop, investigate
    and correct explicitly; repository truth wins.

## 39. Foundations before autonomy

IRIS is not becoming autonomous by collapsing boundaries. Its foundations are
being built so any later authorized autonomy must pass through explicit
identity, Context, planning, control, authority, execution, evidence,
assessment, transition, recovery, provenance and verification.

The WP sequence is intentionally explicit because each causal seam establishes
meaning and authority. The bounded seams are the architecture.

# FINAL CONTINUITY STATEMENT

At ACC-WP050, IRIS has explicitly composed a second bounded PlanStep traversal
through handling, WorkSubject, Context, orchestration decision, execution
request, binding, start and execution-result recording, and then it stops.

The architecture records execution facts without prematurely deciding what
they mean for PlanStep progress. It preserves truthful partial state where
execution and recording cannot be treated transactionally, distinguishes
representable states from canonically reachable paths, preserves exact causal
lineage across immutable Run revisions and treats side effects as real when
later bookkeeping fails.

It does not invent rollback, exactly-once or continuation guarantees. When an
Architect instruction contradicted canonical repository behavior, the work
stopped, inspected the evidence, corrected the contract and resumed without
contaminating the bounded package. That discipline is part of the architecture
too.

Preserve the reasoning. Do not blindly preserve the prediction.
