# IRIS --- ARCHITECTURE CONTINUITY CHECKPOINT --- ACC-WP045

**Checkpoint:** ACC-WP045  \
**Date:** 2026-10-04  \
**Canonical repository:** `fermaxvago/IRIS`  \
**Canonical branch:** `main`  \
**Represented canonical state:** WP045 merged through pull request 49  \
**Represented canonical `main` SHA:** `3381fab81c2780708c74ab9c37c554ee573d1e26`  \
**WP045 implementation SHA:** `a2caf505fa9bddbca89e189a830a50e2f3fab9ae`  \
**Prior continuity checkpoint:** [ACC-WP040](ACC-WP040.md)

## 0. Purpose and interpretation

ACC-WP045 is an immutable historical architecture checkpoint. It records the
implemented contracts, authority boundaries, causal distinctions, current
frontier and open seams visible in the exact canonical repository state named
above. It is not a changelog, roadmap or authorization for later behavior.

The continuity vocabulary is:

- **FROZEN** --- implemented contracts, distinctions, responsibility
  boundaries and decisions proven by the represented canonical state. They
  are not to be casually reopened.
- **CURRENT** --- facts about IRIS at represented canonical commit
  `3381fab81c2780708c74ab9c37c554ee573d1e26`. Later repository state may
  supersede these statements without rewriting this checkpoint.
- **FORWARD** --- unresolved seams, open architectural questions or possible
  future directions. FORWARD is neither authorization nor scheduling, does
  not define a WP046 contract and does not guarantee which seam is next.

The governing continuity rule remains:

> Preserve the reasoning; do not blindly preserve the prediction.

Repository code at the represented commit is authoritative. The represented
SHA is the runtime and architecture state photographed here. The later commit
that adds this document is only the durable historical record of that state;
it is not part of the state represented by ACC-WP045.

# PART I --- VERIFIED HISTORY AND ERA EXTENSION

## 1. Canonical anchor and checkpoint lifecycle

The exact represented commit was independently verified as canonical `main`
after WP045. Its Git tree is:

`4b7e88006076ecff074a471aff4301548b4acbd6`

It is the two-parent merge of:

1. canonical pre-WP045 `main`:
   `099f986a9de4a16192e582148e1ab6221b656c2b`; and
2. accepted WP045 implementation tip:
   `a2caf505fa9bddbca89e189a830a50e2f3fab9ae`.

The accepted implementation tip is an ancestor of the merge. The merge
subject identifies pull request 49, and the WP045 package
`iris.plan_step_execution_context_materialization_composition` exists in the
represented tree.

**FROZEN:** checkpoint identity has two distinct commits:

- the canonical commit whose architecture is represented; and
- a later documentation implementation commit that records the checkpoint.

The second does not retroactively become the represented runtime state.

## 2. Continuity from ACC-WP040

ACC-WP040 represented canonical state:

`ce5d5a3ac8cda37bf039f546380f10ef04509f46`

Its documentation implementation tip was:

`882362f2242b038e0299902d42c143eea76b880b`

That documentation entered canonical history through pull request 44 at merge
commit:

`c2f7670c6d90f2955a90f4c76b26fbc116f0dd31`

The merge has the represented ACC-WP040 state as its first parent and the
documentation implementation tip as its second parent. WP041 began from this
post-checkpoint canonical repository state.

**FROZEN:** the state represented by ACC-WP040 is not the later commit that
contains the ACC-WP040 document. This same lifecycle distinction applies to
ACC-WP045.

## 3. Accepted WP041--WP045 lineage

The interval was verified from Git history rather than copied from handoff
prose:

| Package | PR | Accepted implementation tip | Canonical merge |
| --- | ---: | --- | --- |
| WP041 | 45 | `cae6f072f749aa037419edc4a0a305368fb0c98e` | `ea43d647583fbc39117371c9c71aef490b69c9b4` |
| WP042 | 46 | `f8df5431ec36e7aee3c6ba5a6438b1e787843b00` | `143e7ebd852c1933455b5ed10b44c539edb108ad` |
| WP043 | 47 | `2436ca6833a5840197a6f11a6a909fcdda70b0de` | `5d466baad609cc622e4e94fe533390a9484b1628` |
| WP044 | 48 | `a58ee64293d1b319ed74b6198f0bbcb69ded2fc7` | `099f986a9de4a16192e582148e1ab6221b656c2b` |
| WP045 | 49 | `a2caf505fa9bddbca89e189a830a50e2f3fab9ae` | `3381fab81c2780708c74ab9c37c554ee573d1e26` |

For every row, the implementation tip is the second parent of the listed
merge, is an ancestor of that merge, and has the same content tree as the
merge. The first parent of each merge is the preceding canonical state.

**FROZEN:** an accepted implementation checkpoint and a canonical merge are
separate historical identities even when their trees are equal.

## 4. What changed after ACC-WP040

ACC-WP040 stopped at an optional post-recording
`StepProgressTransitionDecision`. WP041--WP045 extended that frontier through
five existing lower authorities:

```text
post-recording StepProgressTransitionDecision
    -> WP041: optional inert post-recording StepProgressUpdate
    -> WP042: optional one-revision PlanRun advancement
              + fresh post-mutation ControlDecision
    -> WP043: optional handling preparation for freshly selected Step C
    -> WP044: optional canonical PLAN_STEP WorkSubject for Step C
    -> WP045: optional WorkSubject-owned ContextSnapshot for Step C
    -> STOP
```

Each package owns bounded composition and defensive lineage validation. None
replaces the behavioral authority it delegates to. The cumulative shape now
returns to an identity-and-Context layer for successor work, but it remains a
single bounded traversal, not an autonomous loop.

# PART II --- CURRENT CUMULATIVE PIPELINE AND CAUSAL LINEAGE

## 5. Cumulative bounded path through WP045

At the represented state, the cumulative path is:

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
    -> optional PlanStepExecutionBinding
    -> optional PlanStep execution-start
    -> exact PlanStepExecutionStartResult
    -> optional execution-result recording
    -> recorded PlanRun
    -> optional complete post-recording Step evidence assessment
    -> optional post-recording StepProgressTransitionDecision
    -> optional post-recording StepProgressUpdate
    -> optional post-recording one-revision PlanRun advancement
    -> fresh post-recording ControlDecision
    -> optional Step C handling preparation
    -> optional canonical Step C WorkSubject
    -> optional Step C WorkSubject-owned ContextSnapshot
    -> STOP
```

Every `optional` label reflects a canonical branch in the composition family.
No arrow implies recursion, scheduling, retry, recovery, persistence, durable
transactionality or automatic consumption of the final snapshot.

## 6. Step A, Step B and Step C

The labels A, B and C explain causal positions; they are not additional stored
runtime identifiers.

- Step A may be described by the earlier assessment, transition, update and
  advancement artifacts inherited by the cumulative result.
- Step B is the freshly selected step whose handling, identity, Context,
  orchestration, request, binding, start, execution, recording and
  post-recording progression are composed in the central path.
- Step C may be selected by the fresh control decision produced after Step B's
  post-recording progress advancement. WP043--WP045 produce inert handling,
  identity and Context artifacts for this newly selected step.

A, B and C may all differ. In particular, these pairs occupy distinct causal
positions and remain distinct result fields:

```text
handling_preparation
    != post_recording_handling_preparation

work_subject
    != post_recording_work_subject

context_snapshot
    != post_recording_context_snapshot
```

The Step C artifacts neither overwrite nor reinterpret the inherited Step B
artifacts. The top-level processed `step_id` and the post-recording update's
step identity are not substitutes for the fresh control decision's selected
Step C identity.

## 7. Verified authority map

| Responsibility | Canonical authority |
| --- | --- |
| Plan structure and PlanStep resolution | Plan model and validation in `iris.plans` |
| PlanRun validation and immutable mutation | `iris.plan_runs`, including `PlanRunReducer` |
| Control and selection | `iris.plan_control.PlanRunController` |
| Handling preparation | `iris.plan_handling.PlanStepHandlingPreparer` |
| PLAN_STEP WorkSubject identity | `iris.work_identity.work_subject_from_plan_step` |
| Context construction | `iris.context.ContextEngine` |
| Orchestration | `iris.orchestrator.Orchestrator` |
| ExecutionRequest construction | established request-construction composition and `iris.execution.ExecutionRequest` model |
| Execution binding | `iris.plan_step_execution_binding.PlanStepExecutionBinder` |
| Execution start | `iris.plan_step_execution_start.PlanStepExecutionStartCoordinator` |
| Execution-result recording | `iris.plan_step_execution_result_recording.PlanStepExecutionResultRecorder` |
| Complete Step evidence assessment | `iris.plan_step_evidence_assessment.PlanStepEvidenceAssessor` |
| Step transition policy | `iris.step_progress_transition.StepProgressTransitionDecider` |
| StepProgressUpdate synthesis | `iris.step_progress_update_synthesis.StepProgressUpdateSynthesizer` |
| One-update/one-successor/fresh-control advancement | `iris.plan_run_advancement.PlanRunProgressAdvancer` |
| Post-recording update composition | WP041 |
| Post-recording advancement composition | WP042 |
| Post-recording handling composition | WP043 |
| Post-recording WorkSubject composition | WP044 |
| Post-recording Context composition | WP045 |

Higher composition modules defensively validate lineage and currentness. This
does not transfer lower behavioral authority into those composition modules.

# PART III --- ACCEPTED WP041--WP045 COMPOSITION SEAMS

## 8. WP041 --- post-decision progress update

`iris.plan_step_execution_progress_update_composition` composes the exact
WP040 result with WP022's `StepProgressUpdateSynthesizer`.

**FROZEN:** decision absence and an explicit `NO_TRANSITION` decision are
distinct upstream outcomes. Both stop without a post-recording update, while
the inherited decision field preserves the distinction. A `TRANSITION` may
produce one exact inert `StepProgressUpdate` bound to the exact recorded Run
revision.

WP041 does not apply the update, mutate the Run, control again or continue
execution.

## 9. WP042 --- post-recording advancement and fresh control

`iris.plan_step_execution_progress_advancement_composition` composes WP041
with WP023's `PlanRunProgressAdvancer`.

When the post-recording update is absent, WP023 is not invoked and the
post-recording advancement result is absent. When the exact update exists,
WP023 is invoked once within that composer invocation with the exact Plan,
the exact `execution_recording_result.recorded_run`, and the exact update.
The original top-level Run is not substituted for the recorded Run.

The exact result may contain one immutable successor `PlanRun` revision and
one fresh `ControlDecision` over that successor. WP042 stops at this inert
decision. It performs neither a second control pass nor continuation.

## 10. WP043 --- Step C handling preparation

`iris.plan_step_execution_handling_preparation_composition` examines only the
exact fresh post-recording control boundary exposed by WP042.

- no post-recording advancement means no WP014 call;
- a non-`STEP_SELECTED` fresh decision means no WP014 call; and
- an exact fresh `STEP_SELECTED` decision invokes
  `PlanStepHandlingPreparer` once within that composer invocation with the
  exact Plan, successor Run and fresh decision.

No `StepHandlingSpecification` is silently resolved or supplied. Canonical
statuses including `PREPARED`, `HANDLING_UNSPECIFIED` and
`INSUFFICIENT_DETAIL` are preserved as real preparation results. Preparation
is inert and is not execution authorization.

## 11. WP044 --- Step C WorkSubject materialization

`iris.plan_step_execution_work_subject_materialization_composition` uses the
canonical WP015 adapter `work_subject_from_plan_step` for an exact fresh
post-recording `STEP_SELECTED` decision.

The adapter receives the exact Plan, exact successor Run and exact freshly
selected Step C identifier. WP044 synthesizes no `WorkOrigin`; the resulting
canonical subject has `origin is None`. It preserves the exact returned
`WorkSubject` rather than rebuilding an equivalent object.

The canonical `PlanStepWorkReference` contains `plan_id`, `run_id` and
`step_id`; it does not encode PlanRun revision. Stable WorkSubject identity is
therefore distinct from revision-sensitive currentness evidence carried by
the successor Run, control decision and handling preparation.

Handling status does not gate identity. `PREPARED`, `HANDLING_UNSPECIFIED` and
`INSUFFICIENT_DETAIL` can all coexist with a valid stable Step C WorkSubject.
A WorkSubject proves neither handling readiness nor permission to execute.

## 12. WP045 --- Step C Context materialization

`iris.plan_step_execution_context_materialization_composition` invokes the
exact WP044 composer once per WP045 invocation and preserves its cumulative
result.

When `post_recording_work_subject` is absent, `ContextEngine` is not called,
`post_recording_context_snapshot` is `None`, and composition stops. When the
exact subject exists, WP045 validates its inherited Step C lineage and calls
the canonical `ContextEngine` once within that invocation with:

- the exact WP044 `post_recording_work_subject` object;
- explicit `post_recording_candidates`;
- explicit `post_recording_budget`;
- explicit `post_recording_uncertainties`; and
- explicit `post_recording_created_at`.

The exact returned `ContextSnapshot` is preserved. Its `subject` must be the
same WorkSubject object, not merely a structurally equal reconstruction.

For successful delegated materialization:

```text
post_recording_context_snapshot exists
    IFF
post_recording_work_subject exists
```

Canonical delegated errors remain errors rather than being translated into
absence. A snapshot with zero selected Context items remains a real snapshot.

# PART IV --- CROSS-LAYER INVARIANTS AND DISTINCTIONS

## 13. Step B Context is not Step C Context

**FROZEN:** the inherited Step B Context inputs and the explicit Step C
post-recording Context inputs occupy different causal positions:

| Step B path | Step C path |
| --- | --- |
| `candidates` | `post_recording_candidates` |
| `budget` | `post_recording_budget` |
| `uncertainties` | `post_recording_uncertainties` |
| `created_at` | `post_recording_created_at` |

WP045 forwards the Step B set unchanged to WP044 and supplies only the Step C
set to the post-recording `ContextEngine` call. Equality of caller-provided
values would not collapse their architectural roles.

Context is not implicitly inherited, reused or copied between WorkSubjects.
Relevant evidence for Step C must be explicitly supplied for that exact new
subject.

## 14. Context semantics at the checkpoint

**FROZEN:** Context is not Memory. A `ContextSnapshot` is bounded operational
information selected for one WorkSubject. It is not persistent Memory, an LLM
prompt, routing, orchestration, a request, binding, admission, activation,
execution authorization or continuation permission.

Canonical statuses `RESOLVED`, `PARTIAL`, `AMBIGUOUS` and `CONFLICTED` remain
real Context outcomes. WP045 preserves them and does not translate any status
into downstream action. Likewise, Step C handling status does not gate Context
materialization once the canonical Step C WorkSubject exists.

## 15. Currentness, ownership and temporal causality

WP045 defensively validates the relationship among:

- the exact post-recording successor Run;
- the fresh `ControlDecision` current for that Run revision;
- the exact Step C handling preparation current for the same revision and
  selected step;
- the stable Step C WorkSubject reference;
- the exact ContextSnapshot subject ownership and subject identifier;
- the explicitly supplied Context budget; and
- UTC-normalized creation time.

The exact snapshot subject must be the same object passed to `ContextEngine`.
Its budget must equal `post_recording_budget`, and its creation time must equal
the canonical UTC-normalized `post_recording_created_at`.

WP045 also rejects a post-recording Context creation time that precedes the
completed `ExecutionResult` that made the Step C selection path possible.
This prevents impossible causal ordering; it does not claim transactionality,
durability, distributed ordering or replay safety.

## 16. Exact artifact preservation and error ownership

Every layer preserves exact delegated result objects in the cumulative result.
Equivalent reconstruction is not a substitute for lineage where identity is
part of the contract.

Canonical lower-authority errors propagate as their own errors. Composition
invariant errors are reserved for malformed or contradictory delegated
artifacts at the composition seam. Absence is a successful branch only where
the canonical optionality contract defines it; it is never a fallback for a
delegated failure.

## 17. Invocation-local cardinality

Terms such as "exactly once" in WP041--WP045 describe calls made within one
composer invocation on the branch that requires them. They do not establish:

- durable exactly-once processing;
- replay deduplication;
- crash-safe exactly-once execution;
- transactionally unique workflow actions;
- cross-process idempotency; or
- Python object identity across repeated invocations.

Repeated valid invocations are allowed. In particular, repeated Context builds
may produce distinct snapshot identities even for equivalent inputs.

## 18. Preserved semantic separations

The represented repository preserves these responsibility walls:

```text
routing != execution
planning != plan execution
selection != activation
handling preparation != authorization
WorkSubject identity != Run currentness
Context != Memory
Context != authorization
OrchestrationDecision != ExecutionRequest
Decision != Request != Binding != Admission != Activation != Execution
execution != observation
observation != assessment
assessment != transition policy
transition decision != progress mutation
```

It also preserves the following non-equivalences:

```text
ExecutionStatus.SUCCEEDED != StepProgressState.SUCCEEDED
ExecutionStatus.FAILED != StepProgressState.FAILED
ExecutionStatus.REJECTED != automatically NOT_STARTED
ExecutionResult.started_at != PlanStep ACTIVE timestamp
execution SUCCEEDED != expected outcome SATISFIED
execution FAILED != StepProgress FAILED
```

These distinctions prevent infrastructure outcomes from silently becoming
Plan semantics.

# PART V --- VERIFIED PUBLIC SURFACES AND DEPENDENCY DIRECTION

## 19. Public packages added in the interval

Each package publicly exports exactly its owned composer, immutable cumulative
result, composition error and composition invariant error:

### WP041

`iris.plan_step_execution_progress_update_composition`

- `PlanStepExecutionProgressUpdateComposer`
- `PlanStepExecutionProgressUpdateCompositionResult`
- `PlanStepExecutionProgressUpdateCompositionError`
- `PlanStepExecutionProgressUpdateCompositionInvariantError`

### WP042

`iris.plan_step_execution_progress_advancement_composition`

- `PlanStepExecutionProgressAdvancementComposer`
- `PlanStepExecutionProgressAdvancementCompositionResult`
- `PlanStepExecutionProgressAdvancementCompositionError`
- `PlanStepExecutionProgressAdvancementCompositionInvariantError`

### WP043

`iris.plan_step_execution_handling_preparation_composition`

- `PlanStepExecutionHandlingPreparationComposer`
- `PlanStepExecutionHandlingPreparationCompositionResult`
- `PlanStepExecutionHandlingPreparationCompositionError`
- `PlanStepExecutionHandlingPreparationCompositionInvariantError`

### WP044

`iris.plan_step_execution_work_subject_materialization_composition`

- `PlanStepExecutionWorkSubjectMaterializationComposer`
- `PlanStepExecutionWorkSubjectMaterializationCompositionResult`
- `PlanStepExecutionWorkSubjectMaterializationCompositionError`
- `PlanStepExecutionWorkSubjectMaterializationCompositionInvariantError`

### WP045

`iris.plan_step_execution_context_materialization_composition`

- `PlanStepExecutionContextMaterializationComposer`
- `PlanStepExecutionContextMaterializationCompositionResult`
- `PlanStepExecutionContextMaterializationCompositionError`
- `PlanStepExecutionContextMaterializationCompositionInvariantError`

## 20. Verified dependency direction

The cumulative composition dependency direction is:

```text
WP045 -> WP044 -> WP043 -> WP042 -> WP041 -> WP040
```

At the new seams, WP041 delegates update synthesis to WP022, WP042 delegates
advancement to WP023, WP043 delegates handling preparation to WP014, WP044
delegates identity materialization to WP015, and WP045 delegates Context
construction to WP016.

The structurally analogous earlier compositions are precedents, not behavioral
dependencies. The post-recording packages do not re-enter earlier cumulative
paths to recreate artifacts already present in the exact upstream result.

# PART VI --- CURRENT FRONTIER AND EXPLICIT NON-CLAIMS

## 21. Exact frontier after WP045

**CURRENT:** the bounded frontier is:

```text
freshly selected Step C
    -> handling preparation
    -> stable WorkSubject
    -> explicit WorkSubject-owned ContextSnapshot
    -> STOP
```

Step C remains inert and `NOT_STARTED`. WP045 does not automatically invoke
or create orchestration, an `ExecutionRequest`, binding, admission, activation,
execution, result recording for Step C, another assessment cycle, retry,
recovery, persistence or recursive continuation.

The existence of canonical modules for some downstream boundaries does not
mean WP045 composes into them.

## 22. No autonomous-loop claim

The architecture now demonstrates a bounded traversal that can return from
one execution and post-recording path to identity and Context for newly
selected successor work. That is not an autonomous agent loop.

The represented state owns no general continuation authority, loop policy,
termination policy, retry policy, global budget, human-intervention policy,
cancellation system, persistence, crash recovery, scheduling, durable replay
or recursive execution authority.

# PART VII --- ENGINEERING CONTINUITY LESSONS

## 23. Canonical repository evidence overrides an instruction

During the initial WP041 handoff, an instruction named
`28203ad6774c9b68c06d3786d7962a7fc6f75aa0` as the ACC-WP040 documentation
implementation tip. Canonical Git history instead proved the accepted tip was
`882362f2242b038e0299902d42c143eea76b880b`.

The hard gate correctly stopped until the discrepancy was explicitly
corrected. The durable lesson is that instructions can be wrong; canonical
repository evidence remains authoritative. Lineage contradictions must not be
silently repaired.

## 24. Conversation state, workspace state and repository state differ

A conversation may contain complete architectural context while a new
workspace contains no Git checkout. Likewise, a chat attachment is not proof
that a file exists at a local filesystem path.

The correct response is explicit inspection, provisioning or recovery and
fresh verification. Conversational memory is not a substitute for repository
state.

## 25. Artifact validity, publication and merge differ

The interval reinforces:

```text
valid implementation != canonical merge
valid recovery bundle != publication
push != merge
PR URL != proof of merge
conversational "done" != repository state
```

Each state requires its own evidence.

## 26. Prospective merges, tree equality and commit identity

Prospective merge metadata is not the final canonical merge SHA. Canonical
history must be verified after the merge occurs.

Tree equality can establish content equivalence for a bounded decision, but it
does not make two commits historically identical and does not create general
permission to ignore ancestry. History and content are separate evidence
dimensions; both were verified for the WP041--WP045 lineage.

## 27. Independent verification and durable checkpoints

One successful check proves only the property it tested. Artifact integrity,
ancestry, parentage, tree identity, branch state, diff scope, PR state, merge
state and final canonical `main` are independent evidence surfaces.

Local commits and complete verified bundles provide durable recovery points.
They do not publish themselves and do not make their contents canonical.

# PART VIII --- KNOWN DEBT AND FORWARD SEAMS

## 28. Known repository debt

**CURRENT:** the repository-wide Ruff format check remains red solely because
of unchanged pre-existing formatting debt in `iris/core/system.py`. WP045 did
not modify that file, and ACC-WP045 does not repair unrelated runtime code.

## 29. FORWARD architectural state

The following are possible seams visible from the represented architecture,
recorded only as **FORWARD** questions:

- controlled downstream consumption of Step C Context;
- orchestration, request, binding and start boundaries for successor work;
- explicit stop, continue and human-intervention authority;
- budgets, cancellation and retry policy;
- persistence, crash recovery, replay and idempotency where appropriate;
- observability and policy/safety boundaries;
- controlled user ingress and useful outward response composition;
- later integrations, devices, interfaces and multimodality; and
- Memory integration that preserves `Memory != Context`.

This list does not authorize WP046, establish an order or declare orchestration
to be the next package. ACC-WP045 photographs the frontier; it does not
schedule the expedition beyond it.

# PART IX --- CHECKPOINT EVIDENCE AND NON-CLAIMS

## 30. ACC-WP045 creation verification record

The documentation checkpoint was prepared only after verifying:

- exact canonical base, tree and merge parents;
- WP045 implementation-tip ancestry;
- WP041--WP045 PR, implementation-tip and merge lineage;
- ACC-WP040 represented-state/documentation-merge continuity;
- the relevant public packages, result fields, signatures, enums and lower
  authority ownership directly from canonical code;
- the documentation-only changed-file boundary;
- unchanged historical ACC documents;
- public imports for the relevant canonical packages;
- repository lint and format status;
- the final diff and Git object integrity; and
- a clean committed checkpoint recoverable from a complete bundle.

The final Engineer Report accompanying the local checkpoint records the exact
command outcomes, commit identity and recovery artifact.

## 31. Explicit non-claims

ACC-WP045 does not claim that IRIS at the represented commit owns:

- automatic Plan continuation or an autonomous agent loop;
- durable exactly-once behavior, replay suppression or transactionality;
- persistence, checkpoint recovery or distributed ordering;
- automatic retry, replanning, scheduling or cancellation;
- Memory retrieval or implicit Context inheritance;
- automatic orchestration or execution of Step C;
- proof that a structurally complete Run has achieved its Goal; or
- any WP046 behavior, contract or schedule.

Those remain outside the represented canonical authority unless and until
future canonical repository evidence establishes them.
