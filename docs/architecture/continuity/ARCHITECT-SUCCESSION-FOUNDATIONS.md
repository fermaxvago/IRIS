# IRIS Architect Succession Foundations

**Foundation checkpoint:** [ACC-WP055](ACC-WP055.md)
**Foundation date:** 2026-10-09
**Represented canonical `main`:**
`bf471a070754eb0be53a969d3eda302686d169b4`
**Status:** documentation foundation only; no Architect is trained, certified,
appointed or authorized by this document

## 0. Purpose and limits

This document preserves evidence-oriented foundations for a possible future
IRIS Architect succession program. Its purpose is to make architectural
recovery and judgment possible when a conversation, workspace, report or
individual working context is no longer available.

The goal is not merely to describe IRIS. A future candidate must be able to:

- recover current canonical state independently;
- identify the authority that owns a behavior;
- trace exact artifacts and immutable Run revisions;
- understand why accepted boundaries exist;
- challenge instructions that contradict repository evidence;
- reject abstractions that add no justified capability;
- delegate bounded engineering work; and
- review real implementation evidence before recommending merge.

This document creates no executable training machinery, scoring policy,
credential, runtime role or automatic authority transfer. It does not authorize
WP056 or any other feature.

The labels used here are:

- **FROZEN:** durable principles evidenced by accepted repository history.
- **CURRENT:** process practices or architecture facts at the represented
  WP055 state.
- **FORWARD:** non-binding training ideas, questions or possible stages.

# PART I --- EVIDENCE AND AUTHORITY

## 1. Evidence priority

The candidate must apply this priority:

```text
REPOSITORY
    > LIVE GITHUB STATE
    > VERIFIED ARTIFACTS
    > REPORTS
    > CHAT MEMORY
    > ASSUMPTIONS
```

An Architect instruction is an authorization and design artifact, not a
guarantee that every historical or technical claim remains correct. When it
conflicts with canonical behavior, the correct response is to stop, preserve
state, report evidence and obtain an explicit correction.

## 2. Independent verification

Each check proves only its own proposition:

```text
tests pass           != correct base or ancestry
clean worktree       != current remote main
branch published     != PR opened
PR open              != merged
merge reported       != canonical post-merge state verified
tree equality        != identical commit identity
valid model          != reachable canonical path
handler success      != PlanStep outcome satisfied
control selected     != execution authorized
preparation exists   != HandlingNeed exists
```

Succession training must reward independent, differently scoped evidence rather
than one large plausibility claim.

## 3. Repository recovery baseline

A candidate should be able to perform a recovery without relying on chat:

1. identify the repository, canonical remote and branch;
2. fetch without mutating canonical history;
3. compare local and remote state;
4. locate [LATEST](LATEST.md) and verify, rather than assume, its target;
5. inspect the latest checkpoint as a historical snapshot;
6. reconstruct first-parent history, merge parents and accepted tips;
7. distinguish an implementation tip from its merge commit;
8. check tree equality and ancestry where those facts matter;
9. inspect the current source and tests for contracts that may supersede a
   checkpoint's CURRENT statements; and
10. leave an auditable explanation of uncertainty or contradiction.

# PART II --- FOUNDATIONAL COMPETENCIES

## 4. A. Repository recovery

The candidate can locate canonical `main`, reconstruct a bounded Git interval,
identify pull-request heads and merge commits, verify current remote state and
find the latest valid continuity checkpoint.

Evidence of competence should include exact commands or API queries, full SHAs,
parent relationships, a scope-limited diff and an explanation of what each
check proves.

## 5. B. Authority mapping

The candidate can identify the current owner of:

- deterministic and intelligence routing;
- Plan and PlanStep structure;
- immutable PlanRun state and reduction;
- selection and control;
- handling preparation;
- WorkSubject and WorkOrigin identity;
- Context construction;
- orchestration decisions;
- execution requests and bindings;
- activation and execution;
- observation adaptation and recording;
- complete evidence assessment;
- transition policy;
- progress-update synthesis; and
- one-update advancement with fresh control.

The candidate must distinguish a composition layer that invokes an authority
from the lower component that owns the semantics.

## 6. C. Causal reasoning

The candidate can trace an artifact through exact immutable revisions without
conflating:

- object identity and value equality;
- currentness and identifier equality;
- causal position and unique `step_id`;
- execution status and semantic outcome;
- a transition decision and its later update;
- an update and the Run produced by applying it; or
- a fresh selection and permission to execute it.

A correct explanation names the exact source Run for every revision-sensitive
artifact and avoids fixed global revision offsets when upstream branches are
optional.

## 7. D. Contract analysis

The candidate can inspect real constructors, signatures, dataclass invariants,
validators, delegated calls, timestamps, optional branches and errors. A
Contract Pass should answer:

- Which exact inputs are accepted and when are they validated?
- Which authority is invoked, with which exact artifacts, and how often?
- What absence and abstention shapes are canonical?
- Which object owns identities and timestamps?
- Which Run revision is observed or expected?
- What is mutated, if anything?
- Which errors propagate and which contradictions become local invariant
  errors?
- Where does the composition stop?

## 8. E. Architectural skepticism

The candidate actively tests whether a proposal:

- duplicates an existing authority;
- creates a wrapper with no independent consumer or enforcement role;
- mistakes model representability for reachable behavior;
- silently changes validation order;
- upgrades invocation-local cardinality into a global guarantee;
- adds a new policy under the label of validation;
- collapses decision, synthesis and application; or
- widens a bounded WP to repair unrelated debt.

Skepticism must produce evidence and a smaller architectural question, not
reflexive rejection.

## 9. F. Comparative research

The candidate can learn mechanisms from external systems without treating
their documentation as proof that they fit IRIS. Comparative work should:

1. describe analogous mechanisms before recommending adoption;
2. separate pattern, terminology and implementation dependency;
3. identify which IRIS boundaries are stronger or materially different;
4. state what is adopted, adapted or rejected; and
5. return to canonical repository contracts before freezing a design.

## 10. G. Safety and STOP discipline

The candidate recognizes when progress requires abstention:

- the authorized base differs from live `main`;
- history or contract evidence is contradictory;
- the task requires authority not granted;
- a side effect may already have happened and retry safety is unknown;
- a proposed repair lies outside scope;
- exact currentness cannot be established; or
- publication, merge or credentials require separate authorization.

A STOP should preserve the workspace and report exact evidence, observed
behavior and the smallest decision needed to resume.

## 11. H. Engineering delegation

The candidate can write bounded implementation instructions that specify:

- exact authorized base and contradiction protocol;
- public API and dependency ownership;
- invocation cardinality and exact operands;
- presence, identity, revision and temporal invariants;
- error propagation and non-guarantees;
- forbidden authorities and STOP boundary;
- focused, adversarial and regression coverage;
- Git publication permissions; and
- a truthful Engineer report.

The instruction must not grant broader authority accidentally through phrases
such as "finish the pipeline" or "continue automatically."

## 12. I. Independent review

The candidate can review implementation without trusting the Engineer report
as proof. Review should compare:

- diff scope against authorization;
- source behavior against the frozen contract;
- tests against important positive and adversarial branches;
- Git base, ancestry, remote head and PR state;
- public API and installed-package behavior when relevant;
- quality-gate output and environmental failures; and
- known debt versus newly introduced failures.

Merge authorization remains a separate human or explicitly designed authority.

## 13. J. Continuity preservation

The candidate can write a checkpoint that remains truthful after later changes
by separating:

- FROZEN implemented contracts;
- CURRENT represented-state facts;
- FORWARD hypotheses;
- code-proven behavior;
- Architect-provided decision history;
- implementation reports; and
- unresolved uncertainty.

A checkpoint must not rewrite older checkpoints merely because their CURRENT
state later became obsolete.

# PART III --- TRAINING DATA CLASSIFICATION

## 14. Canonical source evidence

Examples: source files, tests, full Git objects, merge parents, trees, merged PR
metadata and installed public APIs. This is the strongest material for claims
about implemented behavior or canonical history.

Every extracted lesson should retain a path, commit, PR or other reproducible
locator where possible.

## 15. Accepted architecture

Verified invariants, responsibility boundaries, failure semantics and explicit
non-guarantees accepted by canonical merges and continuity checkpoints.

Accepted architecture can later be superseded, but not silently. Training
material should state the represented commit and supersession relationship.

## 16. Decision history

Adopted, adapted and rejected alternatives, including their evidence level and
reasoning. Some history may come from an accepted Architect handoff rather than
Git. Such provenance must remain explicit.

Decision history teaches judgment; it must not be confused with runtime
behavior.

## 17. Adversarial examples

Malformed returns, stale decisions, foreign identities, incomplete evidence,
noncanonical ordering, hidden retries and duplicated authorities. Adversarial
fixtures prove defensive behavior, not necessarily canonical reachability.

## 18. Incident lessons

Verified engineering failures, contradictions, interruptions or publication
mistakes and the mechanism that prevented or limited harm. Incident summaries
must distinguish repository evidence from historical reports.

## 19. Open questions

Unresolved architectural seams, recovery concerns and methodological choices.
Open questions are FORWARD; they are not backlog commitments or authorization.

## 20. Superseded guidance

Older instructions, predictions or process practices that later evidence
corrected. Superseded material should be retained as history with an explicit
status, not allowed to override later canonical behavior.

# PART IV --- SEED CASE STUDIES

## 21. Case study 1: authority contradiction

**Verified evidence source:** the contradiction protocol preserved in
[ACC-WP050](ACC-WP050.md), together with any specific Git objects named by the
exercise.
**Initial problem:** a written instruction identifies a base, predecessor or
lineage inconsistent with canonical Git evidence.
**Architectural risk:** implementation from a plausible but unauthorized state
can produce correct-looking code with invalid ancestry.
**Relevant authority:** canonical repository and live GitHub state.
**Accepted reasoning:** stop before modification, verify full identities and
parentage, preserve the workspace, and request explicit correction.
**Rejected alternative:** silently substitute a nearby or content-equivalent
commit.
**Transferable lesson:** authorization is bound to verified state, not intent
reconstructed from prose.
**Evaluation question:** what exact evidence would justify resuming after the
discrepancy is corrected?

## 22. Case study 2: WP050-C1 observation ordering

**Verified evidence source:** [ACC-WP050](ACC-WP050.md), canonical PlanRun
sorting in [plan_runs/models.py](../../../iris/plan_runs/models.py), and the
remaining positional check in
[WP038 composer](../../../iris/plan_step_execution_result_recording_composition/composer.py).
**Initial problem:** an inherited instruction assumed that a newly recorded
observation must be last.
**Architectural risk:** copying the assumption would reject valid canonical
Runs whose IDs sort the new observation before prior evidence.
**Relevant authority:** WP012 PlanRun ordering and WP026 recording semantics.
**Accepted reasoning:** preserve every exact prior observation and the exact new
observation under canonical ordering; position is not contract.
**Rejected alternative:** copy WP038's positional invariant or repair WP038
inside WP050 without authorization.
**Transferable lesson:** semantic preservation is stronger and safer than an
accidental fixture-dependent position.
**Evaluation question:** how would a test distinguish canonical ordering from
append-order coincidence?

## 23. Case study 3: WP055 redundant eligibility layer

**Evidence source:** accepted Architect design history in
[ACC-WP055](ACC-WP055.md), with WP011 control kinds verified in source. This
hypothesis sequence is not claimed to be fully reconstructable from Git.
**Initial problem:** a proposed continuation-eligibility component would
classify the fresh WP054 control outcome.
**Architectural risk:** duplicating `ControlDecisionKind` interpretation creates
parallel authority and inconsistent future policy.
**Relevant authority:** WP011 `PlanRunController` and its canonical
`ControlDecision`.
**Accepted reasoning:** use the existing decision directly at the bounded
composition seam.
**Rejected alternative:** a second classifier that renames current control
semantics.
**Transferable lesson:** a new WP must contribute a distinct capability, not a
new noun for an existing decision.
**Evaluation question:** what independent policy or enforcement role would be
required before a new eligibility authority could be justified?

## 24. Case study 4: WP055 continuation-intent hypothesis

**Evidence source:** accepted Architect design history in
[ACC-WP055](ACC-WP055.md); no claim is made that a complete conversation is a
repository artifact.
**Initial problem:** an inert intent binding was proposed between fresh control
and later continuation.
**Architectural risk:** the artifact had no specified consumer or enforcement
role and duplicated identity/currentness checks.
**Relevant authority:** existing control currentness and downstream bounded
composition contracts.
**Accepted reasoning:** defer any genuine admission/authorization model until a
consumer, policy and safety property justify it.
**Rejected alternative:** introduce an intent object solely because it appears
conceptually neat.
**Transferable lesson:** conceptual novelty is not demonstrated architectural
necessity.
**Evaluation question:** which concrete failure would the proposed artifact
prevent that current authorities cannot detect?

## 25. Case study 5: WP043 precedent

**Verified evidence source:**
[WP043 composer](../../../iris/plan_step_execution_handling_preparation_composition/composer.py)
and [WP055 composer](../../../iris/plan_step_execution_handling_preparation_post_recording_composition/composer.py).
**Initial problem:** identify the correct next bounded seam after WP054 fresh
control.
**Architectural risk:** invent a parallel continuation model while a canonical
analogous composition already exists.
**Relevant authority:** WP014 `PlanStepHandlingPreparer`, composed earlier by
WP043.
**Accepted reasoning:** reuse WP014 for exact `STEP_SELECTED` successor control,
while retaining WP054's deferred validation order.
**Rejected alternative:** new eligibility or intent authority.
**Transferable lesson:** analogy can reveal a canonical owner, but precedent
must be adapted where upstream contracts differ.
**Evaluation question:** which WP043 behavior must not be copied mechanically
into WP055, and why?

## 26. Case study 6: execution versus assessment

**Verified evidence source:**
[WP051 composer](../../../iris/plan_step_execution_evidence_assessment_post_recording_composition/composer.py),
[WP027 assessor](../../../iris/plan_step_evidence_assessment/assessor.py) and
[WP021 decider](../../../iris/step_progress_transition/decider.py).
**Initial problem:** a handler can return `ExecutionStatus.SUCCEEDED` while the
expected PlanStep outcome remains unproven.
**Architectural risk:** direct status mapping collapses operational fact,
canonical evidence, semantic meaning and transition policy.
**Relevant authority:** WP026 recording, WP027 complete-evidence assessment and
WP021 transition decision.
**Accepted reasoning:** record the execution fact, assess all Step-scoped
evidence, then let transition policy decide separately.
**Rejected alternative:** map handler success directly to
`StepProgressState.SUCCEEDED`.
**Transferable lesson:** execution success answers what happened operationally,
not whether the PlanStep's expected outcome was satisfied.
**Evaluation question:** identify every authority crossed between a handler
return and an updated succeeded Run.

# PART V --- PRELIMINARY EVALUATION FRAMEWORK

## 27. Evaluation principles

**FORWARD:** future competency assessment should use reproducible evidence,
adversarial ambiguity and bounded tasks. It should evaluate reasoning and STOP
discipline, not fluency alone.

This section proposes exercises; it does not define scores, certification or
authority transfer.

## 28. Candidate exercises

1. **Reconstruct a WP interval:** recover full tips, parents, trees and PR state
   from Git and GitHub; explain each check's limit.
2. **Map mutation authority:** given a requested behavior, identify the one
   canonical owner and reject unauthorized direct mutation.
3. **Explain stale currentness:** trace why a decision or update valid at one
   revision fails at a later revision.
4. **Reject a redundant WP:** compare a proposed component with existing
   authorities and state the missing independent capability.
5. **Separate valid from reachable:** construct a domain-valid state and prove
   whether the canonical upstream path can actually produce it.
6. **Audit a PR:** ignore its report initially, inspect base/diff/tests/API and
   identify any unsupported claim.
7. **Write a checkpoint:** separate source-proven facts, accepted decision
   history, CURRENT debt and FORWARD possibilities.
8. **Handle a side-effect failure:** explain what can and cannot be retried after
   execution succeeds but recording fails.
9. **Find the STOP boundary:** identify the first action requiring new authority
   and refuse to infer it from an existing artifact.

## 29. Evidence expected from an evaluator

An evaluator should retain:

- the exact repository state used;
- the task and authority granted;
- the candidate's evidence trail;
- any assumptions and how they were tested;
- correct STOP decisions as positive outcomes;
- errors distinguished as factual, architectural or procedural; and
- uncertainty that could not be resolved.

No candidate should grade its own output as sufficient proof of readiness.

# PART VI --- SUCCESSION SAFEGUARDS

## 30. No automatic authority

A future Architect does not gain authority merely because it:

- read continuity documents;
- passed a self-generated quiz;
- claims familiarity with IRIS;
- reproduces previous Architect instructions;
- can generate plausible WP names;
- possesses old chat context; or
- successfully modified a local branch.

Authority transfer requires a separately designed, independently reviewed and
explicitly approved process.

## 31. Prohibited implications

These foundations do not authorize:

- autonomous merge permissions;
- hidden or persistent credentials;
- self-modifying architectural policy;
- unrestricted shell, network or production access;
- self-approval of a design or implementation;
- bypass of review or publication gates;
- automatic continuation from one WP to the next; or
- training on private conversational material without an explicit evidence and
  governance decision.

## 32. Separation of roles

Architect reasoning, Engineer implementation, independent review, publication
and merge authorization are separable roles even when one person or system can
perform more than one. A future process must state which role is active and
which authority is granted for each action.

# PART VII --- METHODOLOGY VERSIONING

## 33. Durable principles

**FROZEN:** evidence priority, explicit authority, exact lineage, fail-closed
validation, truthful partial state, bounded side-effect ownership, independent
verification and STOP discipline.

These principles may be refined, but a later process should not discard them
silently.

## 34. Versioned process practices

**CURRENT:** Q1 Blind Design, Q2 Comparable Systems, Q3 Adopt/Adapt/Reject,
Contract Pass, bounded implementation instruction, Engineer PR, independent
review, merge authorization and post-merge verification.

They are current practices, not timeless requirements. Training records should
name the interval in which they were used.

## 35. Historical examples

Case studies preserve how judgment was applied under a particular repository
state. A future candidate should extract the transferable principle and then
recheck current code, rather than reproduce the old answer mechanically.

## 36. Retired or superseded techniques

When later evidence replaces an assumption, the old material should be marked
superseded with the correcting evidence. It should remain available as an
adversarial or incident example but must not control new implementation.

## 37. Unresolved experiments

**FORWARD:** future work may vary research depth, review independence,
adversarial exercises, competency evidence and training cadence. Unresolved
experiments must remain clearly non-binding until separately decided.

# PART VIII --- NON-BINDING SUCCESSION DIRECTION

## 38. Possible staged direction

```text
ACC-WP055
    foundations and case-study seeds
        -> later checkpoint
           evidence-backed competency catalog
        -> later architecture decision
           candidate training protocol
        -> later architecture decision
           evaluations and adversarial exercises
        -> later independent authorization
           controlled Architect succession
```

This is FORWARD only. It assigns no mandatory WP number, schedule or outcome.
A later checkpoint may revisit the idea if separately authorized.

## 39. Open succession questions

- Who supplies independent evaluation evidence?
- What repository and privacy boundaries apply to training material?
- Which competencies are mandatory for which architectural risk levels?
- How are process practices versioned and retired?
- What constitutes sufficient independence for authority transfer?
- How are conflicting evaluators resolved?
- Which actions remain permanently human-gated?
- How is authority revoked or narrowed after a failure?

ACC-WP055 answers none of these by implication.

# FINAL FOUNDATION STATEMENT

IRIS continuity cannot depend on a surviving chat or on plausible repetition of
old instructions. A successor must recover evidence, understand authority,
trace causality, test assumptions, preserve failure truth and know when to stop.

These foundations preserve the material needed to design such training later.
They do not constitute the training, the evaluation, the certification or the
transfer of architectural authority.

Preserve the reasoning. Do not blindly preserve the prediction.
