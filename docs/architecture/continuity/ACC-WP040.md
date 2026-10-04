# IRIS --- ARCHITECTURE CONTINUITY CHECKPOINT --- ACC-WP040

**Checkpoint:** ACC-WP040\
**Date:** 2026-10-03\
**Canonical repository:** `https://github.com/fermaxvago/IRIS`\
**Canonical branch:** `main`\
**Represented canonical state:** WP040 merged through pull request 43\
**Represented canonical main SHA:** `ce5d5a3ac8cda37bf039f546380f10ef04509f46`\
**WP040 implementation SHA:** `b5f3566902a2a7e23b3af3259eb3df400859c3ab`\
**Prior continuity checkpoint:** ACC-WP035

## 0. Purpose and interpretation

ACC-WP040 is a durable architectural history artifact. It records the exact
system proven by canonical `main` after WP040, the WP036--WP040 extension of the
ACC-WP035 frontier, the responsibility and lineage boundaries that extension
preserves, the engineering lessons that protect continuity, and the point at
which the architecture deliberately stops.

Interpret this document with three labels:

- **FROZEN:** implemented contracts, distinctions and decisions proven by the
  represented repository state and not to be casually reopened.
- **CURRENT:** what is true of IRIS at the represented canonical commit.
- **FORWARD:** an unresolved seam, question or future possibility. It is not
  authorization, scheduling, design, assignment to a Work Package, or a
  guarantee that the seam will remain next.

**Preserve the reasoning; do not blindly preserve the prediction.**

Repository code remains authoritative. Later architecture may supersede
statements labeled **CURRENT**, but it must not rewrite this historical record
as though later facts had already been true at
`ce5d5a3ac8cda37bf039f546380f10ef04509f46`.

# PART I --- VERIFIED HISTORY AND ERA EXTENSION

## 1. Canonical anchor and checkpoint lifecycle

The hard base for this checkpoint was independently verified as:

```text
origin/main = ce5d5a3ac8cda37bf039f546380f10ef04509f46
```

That WP040 merge has exactly these parents:

```text
563779287578dab563a9b64ce7af5dca9e310343
b5f3566902a2a7e23b3af3259eb3df400859c3ab
```

The second parent is the accepted WP040 implementation tip and is an ancestor
of the represented canonical main.

ACC-WP035 described runtime state at
`006f908677466231d4fba77954aac683f840847f`. The checkpoint document was then
added by implementation commit
`a57a8bfe5a2ad2431baf8436c12f3ba2de79af7a` and merged through pull request 38
at `04b20ff9f33b907c4056df8372c0baa11faf4329`.

This establishes a durable historical distinction:

```text
canonical state represented by a checkpoint
    !=
later canonical commit that adds the checkpoint document
```

ACC-WP040 follows the same model. It photographs the post-WP040 runtime state;
the later documentation commit is not part of the state it describes.

## 2. Accepted WP036--WP040 lineage

The following history and merge-parent relationships were verified from the
repository:

| Work Package | PR | Merge commit | Accepted implementation tip |
| --- | ---: | --- | --- |
| WP036 | 39 | `82bbe3049b55775aa93943f215e2af521daad18b` | `cd934c8caba37dd8869339acb3989491c5104e33` |
| WP037 | 40 | `c43a89837558e0e0f025733c17eac229671a2b2a` | `25e5d94ae1dbba10dc2b68288d2991f5e86ad2d2` |
| WP038 | 41 | `e7fd501344994ea787a150de021127d9e44dcbae` | `52cf2b495a26bcbf182f8c7a897248d40ef2a244` |
| WP039 | 42 | `563779287578dab563a9b64ce7af5dca9e310343` | `3bc202830098668e78015552747a118e00b39d31` |
| WP040 | 43 | `ce5d5a3ac8cda37bf039f546380f10ef04509f46` | `b5f3566902a2a7e23b3af3259eb3df400859c3ab` |

WP038's accepted tip includes its initial implementation commit and the later
delegated-lineage hardening commit. The table records the accepted branch tip,
not merely the first feature commit.

Each listed merge was also verified as a two-parent merge whose first parent
is the preceding canonical main and whose second parent is the accepted
implementation tip shown above.

## 3. What changed after ACC-WP035

ACC-WP035 ended with an optional canonical `ExecutionRequest` for freshly
selected successor work. WP036--WP040 extended that bounded path through
already-existing lower authorities:

```text
optional ExecutionRequest
    -> WP036: optional PlanStepExecutionBinding
    -> WP037: optional PlanStepExecutionStartResult
    -> WP038: optional execution-result recording
    -> WP039: optional complete post-recording Step evidence assessment
    -> WP040: optional post-recording transition decision
    -> STOP
```

This is a chain of bounded compositions, not an autonomous execution loop. No
stage silently absorbed the authority of the stage below it, and no stage
authorized automatic consumption of its final artifact.

# PART II --- CURRENT CUMULATIVE PIPELINE AND AUTHORITY

## 4. Cumulative bounded path through WP040

**CURRENT/FROZEN:** canonical IRIS contains this separated cumulative path:

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
    -> optional PlanStep execution start
    -> exact PlanStepExecutionStartResult
    -> optional execution-result recording
    -> recorded PlanRun
    -> optional complete post-recording Step evidence assessment
    -> optional exact StepProgressTransitionDecision
    -> STOP
```

The optionality is defined by canonical upstream artifacts and delegated
authorities. It is not a license for a composition layer to suppress a valid
artifact or convert an exception into absence.

No arrow implies recursive continuation, scheduling, automatic consumption of
the final decision, another progress update, another Run advancement,
re-control, retry, recovery or a durable workflow transaction.

## 5. Authority map at WP040

| Responsibility | Canonical owner at this checkpoint |
| --- | --- |
| Plan structure and canonical `PlanStep` resolution | `iris.planning` |
| PlanRun validation and mutation | `iris.plan_runs`, especially `PlanRunReducer` |
| PlanRun control and selection | `iris.plan_control` |
| Step outcome evaluation | WP020 evaluator authority |
| StepProgress transition policy and currentness | WP021 `StepProgressTransitionDecider` and validator |
| StepProgressUpdate synthesis | WP022 |
| One update, one successor Run, one fresh control pass | WP023 |
| PlanStep execution binding | WP024 |
| Execution-start validation, handler resolution, activation and invocation | WP025 |
| Execution-result recording as PlanRun evidence | WP026 |
| Complete Step-scoped evidence assessment | WP027 |
| Request-to-binding bounded composition | WP036 |
| Binding-to-start bounded composition | WP037 |
| Start-result-to-recording bounded composition | WP038 |
| Recording-to-complete-evidence-assessment bounded composition | WP039 |
| Post-recording-assessment-to-transition-decision bounded composition | WP040 |

Higher composition modules validate the lineage needed to compose safely. That
defensive validation does not transfer behavioral authority to them.

# PART III --- ACCEPTED WP036--WP040 COMPOSITION SEAMS

## 6. WP036 --- request to PlanStep execution binding

**FROZEN:** `iris.plan_step_execution_binding_composition` invokes the WP035
request materializer exactly once and conditionally delegates binding to WP024.

- With no `ExecutionRequest`, WP024 is invoked zero times,
  `execution_binding` is `None`, all WP035 artifacts are preserved, and WP036
  stops successfully.
- With a request, WP036 validates the cumulative lineage and invokes WP024
  exactly once with the exact Plan, exact successor pre-activation Run, exact
  fresh `ControlDecision`, exact handling preparation, and exact request.
- The Run supplied to WP024 is `advancement_result.updated_run`, not the source
  Run received by the cumulative operation.
- The selected step comes from fresh control; it need not be the processed
  input step.
- The exact canonical binding returned by WP024 is preserved, then WP036 stops.

WP036 does not recreate WP024's executable-target, lifecycle, currentness or
lineage policies. A canonical terminal `CLARIFY` or `UNSATISFIED` request is
still a request. It reaches WP024 exactly once, and WP024's canonical
non-executable-request rejection propagates rather than becoming a successful
no-binding result.

```text
valid ExecutionRequest != bindable PlanStep ExecutionRequest
request != binding != admission != activation != execution
```

## 7. WP037 --- binding to execution start

**FROZEN:** `iris.plan_step_execution_start_composition` invokes WP036 exactly
once and conditionally delegates execution start to WP025.

- Without a binding, WP025 is invoked zero times,
  `execution_start_result` is `None`, all WP036 artifacts are preserved, and
  WP037 stops.
- With a binding, WP037 invokes WP025 exactly once with the exact Plan, exact
  successor pre-activation Run, exact binding and exact `ExecutionRequest`.
- The exact `PlanStepExecutionStartResult` is preserved and validated against
  the request, binding and source revision, then WP037 stops.
- Canonical WP036 and WP025 errors propagate without retry or fabricated
  success.

WP025 remains owner of start-boundary currentness, handler resolution, the
NOT_STARTED-to-ACTIVE mutation, handler invocation and start-result
construction. WP037 constructs no runtime, handler registry, reducer or
activation update.

A normal handler-unavailable result is a real start result with canonical
`REJECTED` execution evidence, no active Run, no activation update and no
handler reference. For an invoked handler, `SUCCEEDED`, `FAILED` and `REJECTED`
normal results all preserve the ACTIVE Run produced before invocation. Those
statuses do not themselves complete or fail the PlanStep.

The existence of a start result alone therefore does not prove that a handler
was invoked or completed; its canonical activated/non-activated lineage must be
preserved and inspected.

The possible revision path is:

```text
source reaction Run N
    -> successor pre-activation Run N+1
    -> optional ACTIVE Run N+2
```

WP025 receives the exact N+1 Run. Handler unavailability produces no N+2 Run.

## 8. WP038 --- execution-start result recording

**FROZEN:** `iris.plan_step_execution_result_recording_composition` invokes
WP037 exactly once and conditionally delegates evidence recording to WP026.

- No normal `PlanStepExecutionStartResult` means zero WP026 calls,
  `execution_recording_result=None`, preservation of all WP037 artifacts, and
  STOP.
- Any normal canonical start result means exactly one WP026 call, regardless
  of whether its execution status is `SUCCEEDED`, `FAILED` or `REJECTED`.
- If execution activated, the exact `start_result.active_run` is the recording
  base.
- If the handler was unavailable, the exact
  `advancement_result.updated_run` is the recording base. This is the
  pre-activation successor Run supplied to WP025, not necessarily the source
  Run of the overall cumulative operation.
- The exact WP026 result is preserved and WP038 stops before WP027.

WP026 remains responsible for canonical WorkSubject reconstruction,
`ExecutionResult` adaptation, observation and update identity, temporal
validation, reducer application and the one-revision recorded Run. WP038 does
not call `ExecutionObservationAdapter` or `PlanRunReducer` directly.

Handler unavailability can therefore produce recorded evidence while the
selected step remains `NOT_STARTED`:

```text
pre-activation Run N+1, selected step NOT_STARTED
    -> normal handler-unavailable start result
    -> recorded Run N+2, selected step still NOT_STARTED
```

For an invoked handler the illustrative lineage is N -> N+1 -> ACTIVE N+2 ->
recorded N+3, with StepProgress still ACTIVE. Revision numbers describe
lineage; semantic artifacts remain authoritative.

If handler invocation raises after ACTIVE was committed, WP025 raises
`PlanStepExecutionInvocationError`; no normal start result exists, WP038 does
not fabricate one, and WP026 is not invoked.

## 9. WP039 --- complete evidence assessment after recording

**FROZEN:** `iris.plan_step_execution_evidence_assessment_composition` invokes
WP038 exactly once and conditionally delegates assessment to WP027.

- Without a recording, WP027 is invoked zero times and
  `post_recording_assessment` is `None`.
- With a recording, WP027 is invoked exactly once with the exact Plan,
  `execution_recording_result.recorded_run`, and
  `execution_recording_result.step_id`.
- WP027 selects the complete canonical evidence basis for that Step on that
  exact recorded Run. WP039 does not assess only the new observation.
- The new execution observation belongs to the returned assessment's evidence
  IDs.
- The exact WP027 assessment is preserved, then WP039 stops before policy.

The cumulative result deliberately contains two assessment concepts:

```text
assessment
    = inherited assessment for the earlier processed reaction

post_recording_assessment
    = complete-evidence assessment for the recorded Step and revision
```

WP039 does not overwrite the inherited assessment, invoke WP028, create a
transition decision, synthesize an update, mutate a Run or continue.

## 10. WP040 --- post-recording assessment to transition decision

**CURRENT/FROZEN:** `iris.plan_step_execution_transition_decision_composition`
is the frontier represented by this checkpoint.

- WP039 is invoked exactly once with the exact operation inputs.
- With no `post_recording_assessment`, WP021 is invoked zero times,
  `post_recording_transition_decision` is absent, exact WP039 artifacts are
  preserved, and WP040 stops.
- With an assessment, WP040 requires its recording, uses the exact
  `recording.recorded_run` and `recording.step_id`, resolves that canonical
  `PlanStep`, and invokes `StepProgressTransitionDecider` exactly once with the
  exact post-recording assessment.
- WP040 calls
  `validate_step_progress_transition_decision_current` against the exact
  recorded Run.
- The decision identifies the same Plan, Run, recorded revision, Step and exact
  assessment ID.
- The exact decision is preserved, then WP040 stops before WP022 or WP028.

WP040 intentionally does not call WP028. WP028 would reassess evidence and
break the required exact lineage from WP039's assessment to WP021's decision.

```text
NO_TRANSITION != no decision
```

`TRANSITION` and `NO_TRANSITION` are both successful decision artifacts. WP040
neither suppresses `NO_TRANSITION` nor consumes `TRANSITION` to create an
update.

# PART IV --- CROSS-LAYER LINEAGE AND SEMANTICS

## 11. Processed Step A and fresh Step B

**FROZEN:** the step whose evidence triggered the cumulative reaction need not
be the step selected after advancement.

```text
earlier assessment and transition decision identify A
    -> progress/advancement/re-control
    -> fresh control selects B
    -> handling, WorkSubject and Context identify B
    -> orchestration, request and binding identify B
    -> execution start and recording identify B
    -> post-recording assessment identifies B
    -> post-recording transition decision identifies B
    -> STOP
```

The original operation `step_id` may differ from the post-recording decision's
`step_id`. WP036 follows fresh control; WP037 follows the request/binding
lineage; WP038 records the exact start result; WP039 uses the recording's Run
and Step; and WP040 uses that same recording lineage.

The inherited `assessment` and `transition_decision` may identify A while
`post_recording_assessment` and `post_recording_transition_decision` identify
B. These pairs remain distinct rather than being normalized.

## 12. Exact artifact preservation

**FROZEN:** an equivalent-looking replacement is not the exact delegated
artifact. Canonical source and focused tests establish exact preservation where
identity is meaningful:

- WP036 preserves WP035's cumulative artifacts and the exact WP024 binding.
- WP037 preserves every WP036 artifact and the exact WP025 start result.
- WP038 preserves every WP037 artifact and the exact WP026 recording result.
- WP039 preserves every WP038 artifact and the exact WP027 assessment.
- WP040 preserves every WP039 artifact and the exact WP021 decision.

The recorded Run remains the exact immutable Run contained in the recording
result. Defensive validation checks relationships; it does not authorize
serialization/reconstruction or substitution.

## 13. Evidence, execution status and Plan progress

```text
handler execution status != expected-outcome satisfaction
execution completion      != PlanStep completion
ExecutionResult           != PlanObservation
observation               != assessment
assessment                != transition decision
transition decision       != StepProgressUpdate
StepProgressUpdate        != PlanRun mutation
mutation                  != continuation
```

In particular:

```text
ExecutionStatus.SUCCEEDED != StepProgressState.SUCCEEDED
ExecutionStatus.FAILED    != StepProgressState.FAILED
ExecutionStatus.REJECTED  != automatic StepProgress failure
```

WP038 records facts. WP039 asks WP027 to interpret the complete evidence basis,
not execution status alone. WP040 asks WP021 whether that assessment and
current Step state support a transition. It does not mutate progress.

## 14. Handler-unavailable evidence

**CURRENT/FROZEN:** runtime handler unavailability is neither absence of a
normal start result nor absence of evidence. The canonical path may preserve:

- `ExecutionStatus.REJECTED`;
- `active_run=None` and `activation_update_id=None`;
- `handler_reference=None` and failure code `handler_unavailable`;
- selected StepProgress still `NOT_STARTED`;
- a recorded execution observation;
- a complete post-recording assessment; and
- a WP021 transition decision.

WP040 still invokes WP021 when the assessment exists. Under current canonical
policy this path can yield `NO_TRANSITION` with reason `STEP_NOT_STARTED`.
WP038--WP040 do not encode that policy; WP021 remains authoritative.

## 15. Post-ACTIVE invocation-error frontier

**CURRENT:** if handler invocation raises after ACTIVE was committed, WP025
raises `PlanStepExecutionInvocationError` carrying the active Run,
activation-update identity and execution identity. It propagates through the
bounded chain.

No layer fabricates an `ExecutionResult`, start result, recording, assessment
or decision. No layer rolls back, retries, recovers or compensates. Recording
this exceptional post-ACTIVE incident remains a visible future architectural
frontier, not a defect for this checkpoint to hide.

## 16. Layered currentness through WP040

Currentness is artifact-specific:

| Artifact/layer | What it establishes | What it does not establish |
| --- | --- | --- |
| Source assessment/transition | Explicit source revision and processed Step | Future successor currentness |
| Advancement and fresh control | One successor revision and control over it | Execution authorization |
| Handling preparation | Selected-step preparation for the successor | Handler availability or execution |
| `WorkSubject` | Stable Plan/Run/selected-Step identity | Revision currentness by itself |
| `ContextSnapshot` | Ownership by the exact WorkSubject | Run or handler currentness |
| `OrchestrationDecision` | Canonical subject/context/handling lineage | Later handler freshness |
| `ExecutionRequest` | Canonical request identity and time | Bindability, activation or execution |
| `PlanStepExecutionBinding` | Binding for the successor pre-activation revision | Successful start or future currentness |
| `PlanStepExecutionStartResult` | Exact WP025 normal outcome and source revision | Outcome satisfaction or Step completion |
| Recording result/recorded Run | One-revision descendant carrying execution evidence | Interpretation of that evidence |
| Post-recording assessment | Complete-evidence interpretation on the recorded revision | Progress mutation |
| Post-recording decision | WP021 decision bound to that assessment and Run | Update or continuation |

There is no generic `current` flag that safely substitutes for these witnesses.

## 17. Temporal and identity authority

WP036--WP040 add no hidden composition-layer clocks or identifier factories.
They preserve identities and validate relations owned below them:

- WP035 owns request identity and request time.
- WP024 deterministically binds canonical request lineage.
- WP025 owns start/activation identities and times defined by its contract.
- WP026 and its adapter own recording update, observation identity and time.
- WP027 and its evaluator own assessment identity and time.
- WP021 owns transition-decision identity and time.

WP039 does not add a stronger `assessed_at >= recorded_run.updated_at` rule
where WP027 does not. WP040 has no clock or decision-ID factory and uses
WP021's currentness validator. The compositions reject contradictions; they do
not clamp or rewrite time.

## 18. Invocation-local cardinality and non-guarantees

| Composition | Upstream call | Conditional downstream call |
| --- | --- | --- |
| WP036 | WP035 exactly once | WP024 zero times without request; once with request |
| WP037 | WP036 exactly once | WP025 zero times without binding; once with binding |
| WP038 | WP037 exactly once | WP026 zero times without normal start result; once with one |
| WP039 | WP038 exactly once | WP027 zero times without recording; once with recording |
| WP040 | WP039 exactly once | WP021 zero times without post-assessment; once with one |

Errors propagate without retry. These guarantees are invocation-local. They do
not establish global exactly-once execution, idempotency, durable
deduplication, transactionality, crash recovery, replay protection, leases,
scheduling or persistence.

## 19. Durable authority wall

```text
Planning             != selection
selection            != handling preparation
handling preparation != WorkSubject identity
WorkSubject           != Context
Context               != orchestration
orchestration         != request construction
request               != binding
binding               != admission
admission             != activation
activation            != handler completion
execution result      != observation
observation           != assessment
assessment            != transition decision
transition decision   != StepProgressUpdate
StepProgressUpdate    != PlanRun mutation
mutation              != continuation
```

Composition does not erase these walls. Preserving and validating an artifact
does not make a higher module owner of its policy.

# PART V --- PUBLIC SURFACES AND DEPENDENCY DIRECTION

## 20. Verified public packages

### WP036 --- `iris.plan_step_execution_binding_composition`

- `PlanStepExecutionBindingComposer`
- `PlanStepExecutionBindingCompositionResult`
- `PlanStepExecutionBindingCompositionError`
- `PlanStepExecutionBindingCompositionInvariantError`

### WP037 --- `iris.plan_step_execution_start_composition`

- `PlanStepExecutionStartComposer`
- `PlanStepExecutionStartCompositionResult`
- `PlanStepExecutionStartCompositionError`
- `PlanStepExecutionStartCompositionInvariantError`

### WP038 --- `iris.plan_step_execution_result_recording_composition`

- `PlanStepExecutionResultRecordingComposer`
- `PlanStepExecutionResultRecordingCompositionResult`
- `PlanStepExecutionResultRecordingCompositionError`
- `PlanStepExecutionResultRecordingCompositionInvariantError`

### WP039 --- `iris.plan_step_execution_evidence_assessment_composition`

- `PlanStepExecutionEvidenceAssessmentComposer`
- `PlanStepExecutionEvidenceAssessmentCompositionResult`
- `PlanStepExecutionEvidenceAssessmentCompositionError`
- `PlanStepExecutionEvidenceAssessmentCompositionInvariantError`

### WP040 --- `iris.plan_step_execution_transition_decision_composition`

- `PlanStepExecutionTransitionDecisionComposer`
- `PlanStepExecutionTransitionDecisionCompositionResult`
- `PlanStepExecutionTransitionDecisionCompositionError`
- `PlanStepExecutionTransitionDecisionCompositionInvariantError`

## 21. Verified dependency direction

```text
WP036 -> WP035 request materialization + WP024 binding
WP037 -> WP036 composition + WP025 execution start
WP038 -> WP037 composition + WP026 recording
WP039 -> WP038 composition + WP027 assessment
WP040 -> WP039 composition + WP021 decision/currentness validation
```

The modules also import canonical immutable models and validators needed for
result types and postconditions. That type/model coupling does not move
behavioral authority upward. WP038 does not bypass WP026 to call its adapter or
reducer; WP039 does not invoke WP028; and WP040 does not reassess through WP027
or synthesize an update through WP022.

# PART VI --- ENGINEERING CONTINUITY

## 22. Prospective merge metadata is not canonical state

During WP039 publication, GitHub exposed a prospective merge SHA before the
merge. After the actual merge, the canonical merge commit differed. The
process correctly treated the earlier value as non-canonical and performed a
fresh post-merge verification.

This was a verification-boundary lesson, not code loss or corruption:

```text
prospective merge SHA != verified final merge commit
```

## 23. Independent verification principle

**FROZEN engineering rule:** each verification proves only what it checked.

```text
implementation tests       != artifact integrity
artifact integrity         != remote publication
valid recovery bundle      != publication
pushed branch              != merged main
PR                         != merge
conversation               != repository state
successful report          != canonical state
prospective merge metadata != final canonical merge
final merge SHA            != verified parent lineage
```

Independent boundaries should verify their necessary assumptions. The purpose
is fault containment and resistance to stale state, not ritual duplication.

## 24. Durable checkpoint policy

After implementation reaches a coherent, sufficiently verified state, create a
durable Git checkpoint before long or environmentally fragile gates. It
protects recoverable work; it is not publication, merge approval, or permission
to ignore later failure. If a later check fails, correct the branch and rerun
affected checks. Interruption alone does not prove corruption.

# PART VII --- CURRENT FRONTIER, DEBT AND EVIDENCE

## 25. Exact frontier after WP040

**CURRENT:** the furthest successful new seam is:

```text
WP039
    -> optional exact post-recording StepOutcomeAssessment
    -> optional exact WP021 StepProgressTransitionDecision
    -> STOP
```

The broader path can execute freshly selected successor work through existing
authorities, record a normal result, reassess complete Step evidence and obtain
a transition decision.

It does not automatically synthesize or apply another update, advance or
re-control the Run, select another step, prepare or materialize work, rebuild
Context, orchestrate again, construct/bind/start another request, record or
assess another result, retry, recover, schedule, loop or recursively continue.

## 26. Forward question only

**FORWARD:** IRIS now exposes an exact post-recording
`StepProgressTransitionDecision`. A future investigation may ask whether and
how it can be consumed by already-existing progress-update machinery.

This is not WP041 authorization, permission to invoke WP022, mutation,
re-control or continuation. No next Work Package contract is defined here.

## 27. Known repository debt

At this checkpoint repository-wide `ruff format --check .` remains red solely
because of unchanged historical formatting debt in `iris/core/system.py`.
ACC-WP040 does not modify that file or clean unrelated debt.

## 28. Historical WP040 implementation verification landmark

The WP040 Engineer report recorded the following at implementation time. These
are historical evidence, not a permanent guarantee and not a claim that the
ACC reran the runtime suites:

- focused WP040: 37 passed;
- adjacent WP021/WP028/WP039/WP022: 169 passed;
- recent cumulative chain: 556 passed;
- full suite: 1,357 passed, 1 skipped;
- strict mypy: passed across 176 source files;
- Ruff lint and WP040 formatting: passed;
- compileall and dependency compatibility: passed;
- editable install, sdist, wheel and isolated wheel install: passed;
- public import, `python -m iris`, and installed entry-point smoke: passed;
- dependency-direction and forbidden-authority inspections: passed;
- secret scan: zero matches;
- `git diff --check`: passed; and
- `git fsck --full`: passed with only harmless dangling blobs.

## 29. ACC creation verification record

ACC-WP040 was created as documentation-only integration work. Verification
covered the canonical base and WP040 parents, WP036--WP040 merge and
implementation lineage, prior ACC publication lineage, actual public exports,
canonical source/tests/README semantics, the final documentation diff,
`LATEST.md`, repository integrity and the absence of production or WP041
changes.

Runtime behavior modified: no. Historical ACC files modified: no.

**Preserve the reasoning; do not blindly preserve the prediction.**
