# IRIS --- ARCHITECTURE CONTINUITY CHECKPOINT --- ACC-WP030

**Checkpoint:** ACC-WP030\
**Date:** 2026-10-02\
**Canonical repository:** `https://github.com/fermaxvago/IRIS`\
**Canonical branch:** `main`\
**Canonical state:** WP030 merged through pull request 31\
**Canonical main SHA:** `ebb5495771e90ef43ff62db4ff3471dede6aadee`\
**WP030 implementation SHA:** `a5979c69a3845478b56ad5c1537d15db8ae47fbc`\
**WP030 merge parent:** `9baab8b9bdd928c7be0bce24551f74b9202529fb`

## 0. Purpose and interpretation

ACC-WP030 is a durable architectural history artifact. It records the system
that canonical `main` proves through WP030, the accepted responsibility
boundaries, the invariants later work must preserve, the incidents that changed
the development method, and the exact frontier at which this checkpoint stops.

Interpret this document with three labels:

- **FROZEN:** implemented decisions and contracts that should not be reopened
  casually.
- **CURRENT:** repository state at the represented canonical commit.
- **FORWARD:** non-binding questions or possible seams. They are not roadmap
  commitments or authorization to implement them.

**Preserve the reasoning; do not blindly preserve the prediction.**

Repository code remains authoritative. This checkpoint is historical: later
work may supersede statements labeled **CURRENT**, but must not rewrite this
record of the architecture at `ebb5495771e90ef43ff62db4ff3471dede6aadee`.

# PART I --- VERIFIED CANONICAL LINEAGE

## 1. Accepted WP026--WP030 history

The following merge lineage was verified in canonical `main`:

| Work Package | Merge commit | Accepted implementation tip |
| --- | --- | --- |
| WP026 | `f2a120688d9f3fbad9bc491c98f0f01dcbedf6b6` | `802f9c6e0bda29b168977b413b6237e145fa8989` |
| WP027 | `2a24fc6bad24cd4dd115cf485da36f79c0088cc2` | `1879adbc5b9e3ba4ba4edb200ee7824fef2a605d` |
| WP028 | `dc0874041c948f187b03ad2a2ce2ae6e962dd2af` | `a327cde60b84ac88077270bb3e6371d6bdf8870c` |
| WP029 | `9baab8b9bdd928c7be0bce24551f74b9202529fb` | `b2cd482859eaf541f0b3a5ffa2ba27bf37a58ac4` |
| WP030 | `ebb5495771e90ef43ff62db4ff3471dede6aadee` | `a5979c69a3845478b56ad5c1537d15db8ae47fbc` |

The implementation tips are the accepted branch tips merged by the listed
merge commits. WP029 and WP030 each include a focused hardening commit after
their initial feature commit.

## 2. Era extension

ACC-WP025 ended with the safe PLAN_STEP execution-start boundary. The accepted
architecture now adds:

```text
ERA F --- Safe PLAN_STEP execution start             WP024--WP025
ERA G --- Result recording and evidence assessment  WP026--WP027
ERA H --- Bounded assessment-to-re-control seams    WP028--WP030
```

These eras are descriptive, not autonomous lifecycle machinery.

# PART II --- CURRENT END-TO-END SEAMS

## 3. Accepted bounded chain

**CURRENT/FROZEN:** the repository contains the following separated
responsibilities:

```text
execution-start foundation
    -> execution result/evidence recording
    -> complete Step-scoped evidence assessment
    -> StepProgress transition decision
    -> optional inert StepProgressUpdate synthesis
    -> optional canonical PlanRun N -> N+1 advancement
    -> fresh inert ControlDecision
    -> STOP
```

The WP027--WP030 composition is:

```text
Plan + explicit PlanRun revision + step_id
    -> WP027: complete Step-scoped evidence -> StepOutcomeAssessment
    -> WP021: assessment -> StepProgressTransitionDecision
    -> WP022: transition only -> StepProgressUpdate | None
    -> WP023: update only -> PlanRun(N+1) + ControlDecision | None
    -> STOP
```

WP028 composes WP027 with WP021. WP029 composes WP028 with WP022. WP030
composes WP029 with WP023. The higher layers validate delegated outputs, but do
not take ownership of lower-layer semantics.

## 4. Authority map at WP030

| Responsibility | Canonical owner |
| --- | --- |
| Plan structure | `iris.planning` |
| PlanRun validation and mutation | `iris.plan_runs`, especially `PlanRunReducer` |
| PlanRun control/selection | WP013, `iris.plan_control` |
| Concrete execution handler registry/resolution | `ExecutionCoordinator` |
| Execution fact to PlanObservation adaptation | WP019, `ExecutionObservationAdapter` |
| Step outcome interpretation | WP020, `StepOutcomeEvaluator` |
| Progress transition policy/decision/currentness | WP021, `StepProgressTransitionDecider` and its validator |
| Inert StepProgressUpdate synthesis | WP022, `StepProgressUpdateSynthesizer` |
| One update, one successor Run, one fresh control pass | WP023, `PlanRunProgressAdvancer` |
| Current PLAN_STEP execution binding | WP024 |
| PLAN_STEP execution-start composition | WP025 |
| Execution-result recording into exact Run lineage | WP026 |
| Complete Step-scoped evidence assessment | WP027 |
| Assessment-to-transition composition | WP028 |
| Optional progress-update preparation | WP029 |
| Optional advancement and re-control composition | WP030 |

# PART III --- WP026--WP030 ACCEPTED AUTHORITIES

## 5. WP026 --- execution-result recording

**FROZEN:** `iris.plan_step_execution_result_recording` consumes one
already-produced WP025 `PlanStepExecutionStartResult` and its exact authorized
recording-base Run.

It:

- validates Plan, Run, step, execution and WorkSubject lineage;
- reconstructs the deterministic canonical PLAN_STEP `WorkSubject`;
- delegates execution-fact adaptation to `ExecutionObservationAdapter`;
- creates exactly one `RecordObservationUpdate`;
- applies exactly that update through `PlanRunReducer`;
- derives exactly the next immutable Run revision;
- preserves the complete `StepProgress` collection; and
- returns the observation, update identity and recorded Run lineage, then
  stops.

For a started execution, the exact recording base is WP025's returned ACTIVE
Run. For canonical handler unavailability, it is the original NOT_STARTED Run
at the WP025 source revision.

WP026 records an execution fact. It does not assess the PlanStep expected
outcome, change progress, re-execute a handler, retry, select work or continue
the Plan.

### 5.1 Exact recording-base decision

The exact recording base is an authorization constraint. After successful
recording, the derived Run is a descendant of that base. Submitting the same
WP025 start result with that descendant is therefore rejected by WP026 as a
recording-lineage mismatch before observation adaptation.

This does not make WP026 a duplicate-evidence authority.
`ExecutionObservationAdapter` remains the canonical detector of duplicate
execution evidence whenever it is legitimately invoked with a Run that already
contains the execution ID. Validation order is not changed merely to force a
deeper duplicate error to take precedence.

## 6. WP027 --- complete Step evidence assessment

**FROZEN:** `iris.plan_step_evidence_assessment` assesses one explicitly
supplied immutable PlanRun revision. It:

- validates Plan/Run lineage;
- resolves the canonical `PlanStep` from the Plan;
- selects every canonical observation whose `step_id` exactly matches the
  target step;
- preserves PlanRun observation ordering;
- excludes Run-level observations and observations for other steps;
- excludes blockers, dependencies and `StepProgress` from the evidence tuple;
- permits an empty evidence basis;
- invokes exactly one existing `StepOutcomeEvaluator`;
- validates assessment identity, exact evidence IDs and temporal bounds; and
- returns the existing `StepOutcomeAssessment` directly, then stops.

Selection here is structural, not semantic. WP027 does not rank evidence,
privilege execution evidence, or infer outcome from progress. It creates no
observation or update and performs no Run mutation, transition, execution,
retry or continuation.

The assessment describes the supplied immutable revision. It does not establish
a global latest-Run authority. Historical epistemic validity is distinct from
later operational applicability, which remains a WP021 concern.

## 7. WP028 --- evidence assessment to transition decision

**FROZEN:** `iris.plan_step_evidence_transition` composes WP027 and WP021 over
the same explicit PlanRun revision. It:

- invokes `PlanStepEvidenceAssessor` exactly once;
- preserves the exact assessment artifact;
- resolves the canonical `PlanStep`;
- invokes `StepProgressTransitionDecider` exactly once;
- calls the canonical decision-currentness validator against that exact Run;
- returns the immutable assessment/decision pair; and
- stops before update synthesis or mutation.

A valid `NO_TRANSITION` is a successful result, not an error. WP028 does not
invoke WP022, synthesize a `StepProgressUpdate`, mutate a Run, or continue
execution.

## 8. WP029 --- optional inert update preparation

**FROZEN:** `iris.plan_step_progress_update_preparation` extends WP028 only far
enough to prepare an optional inert `StepProgressUpdate`. It:

- invokes WP028 exactly once;
- preserves the exact WP028 assessment and transition-decision objects;
- branches exclusively on `transition_decision.action`;
- invokes WP022 zero times for `NO_TRANSITION`;
- invokes WP022 exactly once for `TRANSITION`;
- preserves the exact returned WP022 update;
- returns `progress_update=None` exactly when the decision requests no
  transition; and
- stops before application or advancement.

WP022 failure propagates; failure is not converted into absence. Repeated
independent preparations are legal and may produce different update IDs. WP029
does not deduplicate, apply an update, invoke WP023, mutate a Run, execute,
retry, schedule or continue.

## 9. WP030 --- optional advancement and re-control

**CURRENT/FROZEN:** `iris.plan_step_progress_advancement` is the current
orchestration frontier. It:

- invokes WP029 exactly once;
- validates the preparation against the supplied Plan, Run revision and step;
- preserves WP029's exact assessment, decision and optional update objects;
- branches exclusively on `preparation.progress_update`;
- invokes WP023 zero times when the update is absent;
- invokes WP023 exactly once when the update exists;
- passes the exact WP029 update object to WP023;
- preserves the exact WP023 result;
- validates source update/revision and successor Plan/Run/Goal lineage;
- validates exactly one revision of advancement;
- validates the target `StepProgress` state, timestamp and evidence IDs;
- validates non-target progress, observations and blockers are unchanged;
- validates the fresh `ControlDecision` against the successor revision; and
- returns the bounded artifacts, then stops.

The result enforces:

```text
progress_update is None
    iff
advancement_result is None
```

WP030 does not directly reduce the Run or generate control. Those operations
remain inside WP023 through `PlanRunReducer` and `PlanRunController`.

# PART IV --- FROZEN CROSS-CUTTING INVARIANTS

## 10. Evidence, assessment, policy and mutation remain distinct

```text
ExecutionResult != PlanObservation
PlanObservation != StepOutcomeAssessment
evidence != interpretation
assessment != transition decision
transition decision != StepProgressUpdate
StepProgressUpdate != PlanRun mutation
ExecutionStatus.SUCCEEDED != StepProgressState.SUCCEEDED
ExecutionStatus.FAILED != StepProgressState.FAILED
ExecutionStatus.REJECTED != StepProgressState.FAILED
```

The execution-result recorder advances knowledge/history without changing
progress. The evidence assessor interprets existing evidence without mutation.
Transition policy does not itself mutate. An update is inert until consumed by
the reducer through an authorized boundary.

## 11. Control is not execution

**FROZEN:** every `ControlDecision` returned through WP030 is inert.

`STEP_SELECTED` does not activate, schedule, dispatch or execute the selected
step. `ACTIVE_WORK_PENDING` does not resume or manage active work.
`SELECTION_UNRESOLVED` does not authorize WP030 to select a step itself.

Any future boundary that consumes a `ControlDecision` to perform work requires
separate architectural authorization.

## 12. Run structure is not Goal outcome

**FROZEN:** structural control conditions do not establish Goal outcome:

```text
RUN_STRUCTURALLY_COMPLETE != automatic Goal success
RUN_CANNOT_ADVANCE        != automatic Goal failure
```

Goal completion/failure semantics require an explicit authority not present at
this checkpoint.

## 13. Immutable revision causality

`PlanRun` revisions are immutable. A canonical WP023 application has the form:

```text
source Run revision N
    + StepProgressUpdate(expected_revision=N)
    -> successor Run revision N+1
```

The source Run remains unchanged. Assessment, decision and update artifacts are
bound to their explicit source revision; higher composition layers do not
silently rebase them onto a descendant. The fresh post-advancement
`ControlDecision` observes the successor revision exactly.

No persistence, durable replacement or transaction is implied by deriving an
immutable successor value.

## 14. Exact-artifact preservation

The accepted compositions preserve delegated artifacts rather than creating
equivalent-looking replacements:

- WP028 preserves the WP027 assessment and WP021 decision;
- WP029 preserves the WP028 artifacts and the WP022 update;
- WP030 preserves the WP029 artifacts;
- WP030 passes the exact WP029 update object to WP023; and
- WP030 preserves the exact WP023 advancement result.

Defensive postcondition checks do not authorize reconstruction or replacement.

## 15. Invocation-local bounded delegation

| Composition | Required delegated calls per successful invocation |
| --- | --- |
| WP028 | WP027 exactly once; WP021 exactly once; currentness validation once |
| WP029 | WP028 exactly once; WP022 zero times for `NO_TRANSITION`, once for `TRANSITION` |
| WP030 | WP029 exactly once; WP023 zero times without an update, once with an update |

These are invocation-local cardinality guarantees. They are not persistence,
deduplication, idempotency, transaction isolation or distributed exactly-once
guarantees. Independent repeated calls remain permitted unless a lower
authority explicitly rejects a particular artifact lineage.

## 16. Error ownership

Lower-boundary errors remain recognizable and normally propagate. Composition
layers own contradictions introduced at their own boundary, including malformed
delegated result types or cross-artifact lineage that conflicts with the exact
supplied operation.

Defensive validation must not absorb lower-level authority or reorder valid
preconditions merely to produce a preferred deeper error. The WP026 recording
decision demonstrates this rule: invalid exact-base lineage is rejected before
the downstream duplicate detector becomes relevant. A new duplicate subsystem
was neither needed nor authorized.

# PART V --- DEPENDENCY DIRECTION AND PUBLIC SURFACE

## 17. Verified dependency direction

The behavioral composition direction in canonical code is:

```text
WP026 -> WP025 result + WP019 adapter + PlanRun reducer
WP027 -> WP020 evaluator + PlanRun/Planning models
WP028 -> WP027 assessor + WP021 decider/currentness
WP029 -> WP028 composer + WP022 synthesizer
WP030 -> WP029 preparer + WP023 advancer
```

No reverse dependency from WP019--WP029 to WP030 exists. WP030 does not import
or invoke `PlanRunReducer` or `PlanRunController` directly. Its implementation
also imports immutable lower-layer artifact types such as
`StepOutcomeAssessment`, `StepProgressTransitionDecision` and
`StepProgressUpdate` for its public result and defensive validation. This is
type/model coupling; behavioral authority remains delegated through WP029 and
WP023.

## 18. Verified public APIs

Canonical package exports at this checkpoint are:

### WP026 --- `iris.plan_step_execution_result_recording`

- `PlanStepExecutionResultRecorder`
- `PlanStepExecutionResultRecordingResult`
- `PlanStepExecutionResultRecordingError`
- `PlanStepExecutionResultRecordingLineageError`
- `PlanStepExecutionResultRecordingInvariantError`
- `PlanStepExecutionResultRecordingGenerationError`

### WP027 --- `iris.plan_step_evidence_assessment`

- `PlanStepEvidenceAssessor`
- `PlanStepEvidenceAssessmentError`
- `PlanStepEvidenceAssessmentLineageError`
- `PlanStepEvidenceAssessmentInvariantError`

### WP028 --- `iris.plan_step_evidence_transition`

- `PlanStepEvidenceTransitionComposer`
- `PlanStepEvidenceTransitionDecisionResult`
- `PlanStepEvidenceTransitionError`
- `PlanStepEvidenceTransitionInvariantError`

### WP029 --- `iris.plan_step_progress_update_preparation`

- `PlanStepProgressUpdatePreparer`
- `PlanStepProgressUpdatePreparationResult`
- `PlanStepProgressUpdatePreparationError`
- `PlanStepProgressUpdatePreparationInvariantError`

### WP030 --- `iris.plan_step_progress_advancement`

- `PlanStepProgressAdvancementComposer`
- `PlanStepProgressAdvancementResult`
- `PlanStepProgressAdvancementError`
- `PlanStepProgressAdvancementInvariantError`

# PART VI --- INCIDENTS AND ENGINEERING CONTINUITY

## 19. WP028 interruption and reconstruction

The original WP028 implementation attempt reportedly reached green focused,
sensitive and complete-suite verification before a later long-running gate
stalled and the execution was manually interrupted. The implementation files,
branch, commit and bundle were not recoverable from the recovered workspace.
Historical test output could not certify source that no longer existed.

The Architect authorized a new canonical reconstruction from:

`2a24fc6bad24cd4dd115cf485da36f79c0088cc2`

The accepted contract was reconstructed independently, freshly verified and
merged as `a327cde60b84ac88077270bb3e6371d6bdf8870c` through WP028 merge
`dc0874041c948f187b03ad2a2ce2ae6e962dd2af`.

No exact source equivalence with the lost attempt is claimed. The lost
implementation is not an architectural authority. The reconstructed and merged
implementation is canonical.

## 20. Durable checkpoint rule

**FROZEN engineering continuity rule:** after implementation correctness and
focused/static verification establish a coherent trustworthy state, create a
durable Git checkpoint before entering long, fragile, packaging-heavy or
environment-heavy verification stages.

The checkpoint may be an implementation commit on the dedicated branch. It is
not permission to commit knowingly broken or incoherent work. Its purpose is to
make an already-valid implementation recoverable so long verification is not
the only place where completed source exists.

# PART VII --- DEBT, RISKS AND STOP CONDITIONS

## 21. Known pre-existing technical debt

- The repository-wide Ruff format check still reports the historical formatting
  debt in `iris/core/system.py`. ACC-WP030 does not repair it.
- No repository GitHub Actions workflow or required CI configuration is present
  in canonical `main` at this checkpoint. Work Package verification is therefore
  primarily Engineer-produced/local evidence rather than an independent
  required GitHub status. ACC-WP030 does not introduce CI.

## 22. Accepted limits and risks

- WP025's crash window remains real: ACTIVE may exist even if a crash prevents
  handler user code from running.
- No global exactly-once guarantee exists for execution, recording,
  assessment, preparation or advancement.
- No durable transaction connects PlanRun state to external side effects.
- Immutable derivation does not itself provide persistence, distributed
  consistency or recovery.
- A fresh `ControlDecision` is not an instruction automatically consumed by
  WP030.

## 23. Current frontier and prohibited silent extension

**CURRENT:** WP030 ends with the assessment, transition decision, optional
inert update, and optional exact WP023 advancement containing a successor Run
and fresh inert control decision.

It stops before:

- selected-step activation;
- execution or handler invocation caused by a control decision;
- automatic continuation or a control loop;
- retry, recovery, scheduling, polling or replanning;
- persistence or hidden deduplication;
- Goal success/failure inference; and
- any second assessment, update, reduction or control pass.

None of these behaviors is authorized by this checkpoint. A later Work Package
must establish any such seam explicitly.

# PART VIII --- FORWARD VIEW (NON-BINDING)

## 24. Frontier question

**FORWARD:** the architecture now exposes a fresh inert `ControlDecision` after
an optional one-revision advancement. A future design may ask whether and how an
explicit caller is allowed to consume such a decision.

This is a question, not a WP031 design, roadmap commitment or implementation
authorization. The current architecture deliberately remains:

```text
bounded preparation
    -> optional one-revision advancement
    -> one fresh control artifact
    -> STOP
```

**Preserve the reasoning; do not blindly preserve the prediction.**

# PART IX --- ENGINEER VERIFICATION METADATA

## 25. Verification record

- Verified against repository commit:
  `ebb5495771e90ef43ff62db4ff3471dede6aadee`
- Verification date: 2026-10-02
- WP030 merge parent verified:
  `9baab8b9bdd928c7be0bce24551f74b9202529fb`
- WP030 implementation ancestry verified:
  `a5979c69a3845478b56ad5c1537d15db8ae47fbc`
- Architectural body created from canonical implementation, tests, public
  package exports and repository history.
- Runtime behavior modified: no.
- Architectural contradictions found: none.
- Later repository advancement found: none.
- Reference Registry modified: no; this checkpoint introduced no new external
  research references and no duplicate registry entries.
