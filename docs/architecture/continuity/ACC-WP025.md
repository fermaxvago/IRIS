# IRIS --- ARCHITECTURE CONTINUITY CHECKPOINT --- ACC-WP025

**Checkpoint:** ACC-WP025\
**Date:** 2026-09-30\
**Canonical repository:** `https://github.com/fermaxvago/IRIS`\
**Canonical branch:** `main`\
**Canonical state:** WP025 merged\
**Canonical main SHA:** `ea3e2fc6de1162377370254799498b40b6f9f540`\
**WP025 implementation SHA:** `430600efc84f0a335d6ef87fe4fab97c11fc1a43`

## 0. Purpose

ACC-WP025 is not a changelog. It is an architectural continuity
artifact. It exists so a future Architect can recover not only what IRIS
contains at WP025, but why it has this shape, what each WP was trying to
isolate, which responsibilities belong to which subsystem, which
patterns were rejected, which risks are consciously accepted, how
Architect and Engineer work together, and what future direction was
visible at this checkpoint.

Interpret the document with three labels:

-   **FROZEN:** implemented decisions/contracts that should not be
    reopened casually.
-   **CURRENT:** canonical state at the WP025 merge.
-   **FORWARD:** hypotheses and expected seams, not a committed roadmap.

**Preserve the reasoning; do not blindly preserve the prediction.**

# PART I --- PROJECT IDENTITY

## 1. What IRIS is trying to become

IRIS is not being designed as a collection of commands, a thin LLM
wrapper, a giant prompt, a pile of tools, a monolithic autonomous agent,
or one independent assistant per device.

The direction is a personal intelligent system capable over time of
combining deterministic system behavior, tools/capabilities, multiple
intelligence providers, memory/context, planning, execution,
observation/evidence, uncertainty, policy/safety, recovery, distributed
resources/devices, multimodal interaction and controlled evolution.

The long-term creative direction is one IRIS identity present through
many nodes/providers. A device should normally be a point of presence or
capability provider, not a separate IRIS.

The project intentionally builds foundations before autonomy. We are not
trying to build the final MARK immediately; we are building the system
that can responsibly support later MARKs.

## 2. Architectural philosophy

### 2.1 Separate claims that are not equivalent

``` text
routing != execution
planning != plan execution
selection != activation
execution != observation
observation != assessment
assessment != transition policy
transition decision != state mutation
binding != admission
ACTIVE != completion
execution SUCCEEDED != expected outcome SATISFIED
```

### 2.2 Explicit evidence before certainty

Observations are evidence, not truth. The architecture should permit
UNKNOWN, UNCERTAIN, CONTRADICTORY, INDETERMINATE and
INSUFFICIENT_EVIDENCE when evidence does not justify stronger claims.

### 2.3 One authority per responsibility

At WP025:

``` text
ExecutionCoordinator -> concrete handler registry/resolution
PlanRunReducer       -> PlanRun mutation semantics
WP013                -> PlanRun control/selection semantics
WP024                -> current PlanStep execution binding proof
WP025                -> execution-start composition
```

Later WPs should compose existing authorities rather than create
competing ones.

### 2.4 Composition before monolithic autonomy

IRIS deliberately prefers explicit seams such as observe→STOP,
assess→STOP, decide transition→STOP, synthesize update→STOP and advance
run→STOP over an autonomous loop whose semantics have not yet been
understood.

### 2.5 Never claim guarantees the system does not possess

At WP025 IRIS does not claim exactly-once execution, durable
transactionality, distributed crash recovery, automatic rollback,
durable scheduling, persistent workflow replay or safe autonomous
self-modification.

# PART II --- ARCHITECTURAL EVOLUTION

## 3. Era map

``` text
ERA A — Core and deterministic foundations        WP001–WP003
ERA B — Capabilities / intelligence / information WP004–WP010
ERA C — Goals, plans and explicit run state       WP011–WP014
ERA D — Work-subject pipeline                     WP015–WP019
ERA E — Evidence → assessment → progress          WP020–WP023
ERA F — Safe PLAN_STEP execution start            WP024–WP025
```

Repository code remains authoritative. This checkpoint records
architectural intent.

# PART III --- WP-BY-WP ARCHITECTURAL VIEW

## WP000 --- Reconnaissance

**Problem:** extend IRIS without first understanding the repository and
existing contracts.\
**Decision:** establish reconnaissance and treat the repository as
source of truth.\
**Why:** later WPs should preserve contracts instead of repeatedly
reinventing the system.\
**Unlocked:** incremental WPs with explicit ancestry and scope.\
**State:** historical foundation.

## WP001 --- Core foundation

**Problem:** IRIS needed a stable system core before intelligent/agentic
behavior.\
**View:** explicit Core/System foundations and deterministic behavior.\
**Why:** intelligence should sit on a coherent system rather than become
the system.\
**Unlocked:** routing, commands and later runtime composition.\
**State:** FROZEN foundation.

## WP002 --- Deterministic routing foundation

**Problem:** requests/actions needed explicit routing rather than ad-hoc
branching.\
**View:** deterministic routing is infrastructure separate from
intelligence.\
**Why:** not every decision requires an LLM.\
**Unlocked:** separation between interpretation, routing and execution.\
**State:** FROZEN foundation.

## WP003 --- Action & Tool Runtime foundation

**Problem:** a route/command needs a disciplined way to represent and
invoke actions/tools.\
**View:** explicit runtime boundary instead of arbitrary direct calls.\
**Why:** tools eventually carry side effects and require stable
contracts.\
**Unlocked:** capability and execution-oriented work.\
**State:** FROZEN foundation.

## WP004 --- Intelligence foundation

**Problem:** intelligence access without making one provider/model the
architectural center.\
**View:** provider-independent intelligence contracts, models, registry
and runtime, without a bundled provider.\
**Why:** IRIS should not be inseparable from OpenAI, Ollama or one
model.\
**Unlocked:** concrete provider adapters and intelligence routing.\
**State:** FROZEN principle.

## WP005 --- Ollama Provider foundation

**Problem:** the generic Intelligence boundary needed a first concrete
provider implementation.\
**View:** an optional Ollama adapter behind the WP004 boundary, with
explicit provider and model selection.\
**Why:** prove local inference without making Ollama IRIS's identity.\
**Unlocked:** real local inference while preserving provider
replaceability.\
**State:** FROZEN adapter boundary; provider set remains extensible.

## WP006 --- Intelligence routing foundation

**Problem:** multiple intelligence resources require selecting an
appropriate one.\
**View:** describe the intelligence need and let routing select a
resource.\
**Why:** selection may depend on capability, availability, cost, latency
and difficulty.\
**Unlocked:** future local/remote intelligence composition.\
**State:** FROZEN separation; policy may evolve.

## WP007 --- Memory foundation

**Problem:** personal continuity cannot depend on loading all history
into active context.\
**View:** Memory is persistent information managed separately from
Context.\
**Why:** long-term continuity and current reasoning have different
needs.\
**Unlocked:** context can retrieve relevant information without becoming
memory.\
**State:** FROZEN separation; automatic memory management remains future
work.

## WP008 --- Context foundation

**Problem:** memory/request/environmental data must become a bounded
current view.\
**View:** Context is a constructed snapshot/input, not Memory itself.\
**Why:** work needs traceable bounded inputs.\
**Unlocked:** explicit orchestration input.\
**State:** FROZEN concept.

## WP009 --- Orchestration foundation

**Problem:** knowing work/context does not decide where/how it should be
handled.\
**View:** orchestration decides a target/path without becoming
execution.\
**Why:** decision and side effect must remain separable.\
**Unlocked:** generic execution.\
**State:** FROZEN boundary.

## WP010 --- Execution foundation

**Problem:** an orchestration decision must become an explicit execution
attempt.\
**View:** execution contracts/results instead of side effects inside
orchestration.\
**Why:** execution needs independent identity, status, failure semantics
and handlers.\
**Unlocked:** planning could later reuse generic execution.\
**State:** FROZEN generic foundation, later extended compatibly.

## WP011 --- Goal & Planning foundation

**Problem:** single actions are insufficient for multi-step work.\
**View:** represent Goals, Plans and PlanSteps explicitly.\
**Why:** planning structure should be inspectable and independent from
execution state.\
**Unlocked:** PlanRun and progress semantics.\
**State:** FROZEN planning foundation.

## WP012 --- Plan Run & Progress State foundation

**Problem:** Plan describes intended work but not a particular run.\
**Decision:** PlanRun, StepProgress, StepProgressState,
StepAvailability, PlanRunCondition, PlanObservation, updates and
PlanRunReducer.\
**Key semantics:** immutable/derived run state, optimistic revision
semantics, append-only evidence, explicit terminal evidence references;
PlanRunReducer owns mutation.\
**Why:** execution history/current progress require identity and
lineage.\
**Unlocked:** control and safe transitions.\
**State:** FROZEN authority boundary.

## WP013 --- Plan Run Control Decision foundation

**Problem:** current PlanRun needs an explicit decision about pending
work, selection, completion, inability to advance or unresolved
selection.\
**Decision:** explicit current ControlDecision plus selection policy
where needed.\
**Why:** selection is a decision, not mutation/activation.\
**Frozen:** `STEP_SELECTED != step ACTIVE`.\
**Unlocked:** handling preparation.\
**State:** FROZEN control authority.

## WP014 --- Plan Step Handling Preparation foundation

**Problem:** a selected PlanStep still needs an explicit handling
requirement.\
**Decision:** preparation result with PREPARED or explicit inability to
prepare.\
**Why:** selection alone must not imply executability.\
**Unlocked:** WorkSubject construction.\
**State:** FROZEN seam.

## WP015 --- Work Subject & Origin Identity foundation

**Problem:** generic downstream layers should not be coupled directly to
PlanStep.\
**Decision:** WorkSubject and WorkOrigin identity.\
**Why:** PLAN_STEP is one work subject, not all work.\
**Unlocked:** reusable Context/Orchestration/Execution.\
**State:** FROZEN abstraction.

## WP016 --- Work-Subject Context foundation

**Problem:** WorkSubject needs explicit contextualization.\
**Decision:** construct bounded context while preserving lineage.\
**Why:** context assembly should not hide inside
orchestration/execution.\
**Unlocked:** work-subject orchestration.\
**State:** FROZEN seam.

## WP017 --- Work-Subject Orchestration foundation

**Problem:** contextualized work needs a target decision.\
**Decision:** reuse orchestration for WorkSubjects while keeping
decision separate from execution.\
**Why:** SYSTEM/MEMORY/CAPABILITY/INTELLIGENCE/CLARIFY/UNSATISFIED
decisions are not execution.\
**Unlocked:** work-subject execution.\
**State:** FROZEN boundary.

## WP018 --- Work-Subject Execution foundation

**Problem:** valid orchestration must become ExecutionRequest handled by
a concrete runtime.\
**Decision:** ExecutionCoordinator and registered handlers are canonical
generic execution.\
**Why:** execution must serve PLAN_STEP and other WorkSubjects without
making PlanRun part of the generic runtime.\
**Authority:** ExecutionCoordinator owns handler registry/resolution.\
**Not solved:** PlanStep activation/completion, retry, recovery,
exactly-once.\
**Unlocked:** ExecutionResult for observation.\
**State:** FROZEN generic authority.

## WP019 --- Execution Observation foundation

**Problem:** ExecutionResult is operational output, not plan evidence.\
**Decision:**
`ExecutionResult + WorkSubject(PLAN_STEP) + Plan + PlanRun → ExecutionObservationAdapter → PlanObservation → STOP`.\
**Frozen:** ExecutionResult != PlanObservation; PlanObservation !=
OutcomeAssessment; execution status does not directly determine
StepProgress; evidence recording != interpretation/mutation.\
**Why:** record what happened before interpreting what it means.\
**Unlocked:** evidence-based assessment.\
**State:** FROZEN epistemic boundary.

## WP020 --- Step Outcome Assessment foundation

**Problem:** recorded evidence must be evaluated against expected
outcome without mutating progress.\
**Decision:** explicit selected PlanObservation\[\] →
StepOutcomeEvaluator → StepOutcomeAssessment → STOP.\
**Rules:** Evidence != Assessment; Assessment != StepProgressUpdate;
execution success != outcome satisfaction; no evidence != negative
evidence; inability to prove SATISFIED != NOT_SATISFIED; evaluator
failure is not an assessment status.\
**Why:** avoid false semantic certainty.\
**Unlocked:** separate transition policy.\
**State:** FROZEN assessment boundary.

## WP021 --- Step Progress Transition Decision foundation

**Problem:** assessment still does not answer whether progress should
transition.\
**Decision:** explicit transition-decision layer.\
**Why:** epistemic judgment and transition policy are separate
responsibilities.\
**Unlocked:** update synthesis.\
**State:** FROZEN policy boundary.

## WP022 --- Step Progress Update Synthesis foundation

**Problem:** transition decision is still not PlanRun mutation.\
**Decision:** synthesize canonical StepProgressUpdate with
lineage/expected revision.\
**Why:** policy requests mutation through WP012 contracts rather than
mutating directly.\
**Unlocked:** update → reducer → control composition.\
**State:** FROZEN synthesis boundary.

## WP023 --- PlanRun Progress Advancement foundation

**Problem:** safely apply a StepProgressUpdate and evaluate the
resulting run.\
**Decision:**
`Plan + PlanRun(N) + update(N) → PlanRunReducer.apply() once → PlanRun(N+1) → PlanRunController.decide() once → fresh ControlDecision → STOP`.\
**Why:** mutation and subsequent control compose safely without becoming
an autonomous loop.\
**Frozen:** `STEP_SELECTED != activation`.\
**Process incident:** Work hit a usage limit during WP023. Recovery
required inspecting actual state rather than blindly restarting.\
**State:** FROZEN advancement composition.

## WP024 --- PlanStep Execution Binding foundation

**Problem:** selection/preparation/orchestration/request must be proven
to describe the same current work.\
**Decision:** current Plan + Run + STEP_SELECTED + PREPARED handling +
PLAN_STEP ExecutionRequest → PlanStepExecutionBinding(N) → STOP.\
**Why:** valid request alone does not prove current lineage.\
**Not solved:** handler availability, admission, activation, scheduling,
invocation or execution.\
**Frozen:** binding != activation; binding != admission.\
**State:** FROZEN proof/currentness boundary.

## WP025 --- PlanStep Execution Start foundation

**Problem:** when may a real handler be invoked, and when should the
PlanStep become ACTIVE?\
**Decision:** explicit execution-start boundary.

``` text
Plan + PlanRun(N) + current binding(N) + exact ExecutionRequest
→ PlanStepExecutionStartCoordinator
→ ExecutionCoordinator validates + resolves concrete handler
→ no handler: REJECTED, Run N, NOT_STARTED, STOP
→ handler exists
→ execution-start boundary
→ validate binding current again
→ NOT_STARTED → ACTIVE StepProgressUpdate
→ PlanRunReducer.apply()
→ Run(N+1, ACTIVE)
→ invoke exact already-resolved handler
→ ExecutionResult
→ STOP
```

**Core property:**
`handler invocation ⇒ ACTIVE transition succeeded first`.\
**Explicit non-guarantee:**
`ACTIVE transition succeeded ⇏ handler definitely executed user code`.\
**Rejected here:** duplicate handler registry, can_execute→execute
split, premature/late ACTIVE, rollback fiction, unnecessary lifecycle
states, fake transactionality, exactly-once claims, automatic
retry/recovery.\
**Post-activation rule:** if execution raises after activation, the
ACTIVE Run must remain recoverable.\
**State:** CURRENT/FROZEN at ACC-WP025.

# PART IV --- CURRENT ARCHITECTURE

## 4. High-level pipeline

``` text
Goal
→ Plan / PlanStep
→ PlanRun + StepProgress
→ ControlDecision
→ handling preparation
→ WorkSubject
→ Context
→ Orchestration
→ ExecutionRequest
→ PlanStepExecutionBinding
→ Execution Start
→ ExecutionResult
→ ExecutionObservationAdapter
→ PlanObservation
→ record evidence in PlanRun
→ explicit evidence selection
→ StepOutcomeEvaluator
→ StepOutcomeAssessment
→ StepProgressTransitionDecision
→ StepProgressUpdate
→ PlanRunProgressAdvancer
→ new PlanRun + fresh ControlDecision
→ STOP
```

The pieces now exist for much of an eventual cognitive/work loop. They
deliberately remain explicit rather than being collapsed into one
autonomous loop.

## 5. Authority map

  Responsibility                          Canonical owner
  --------------------------------------- ------------------------
  Plan structure                          Goal/Planning
  Run/progress mutation                   PlanRunReducer
  PlanRun control/selection               WP013
  Handling preparation                    WP014
  Generic work identity                   WorkSubject/WorkOrigin
  Context construction                    Context subsystem
  Target decision                         Orchestration
  Concrete handler registry/resolution    ExecutionCoordinator
  Execution observation                   WP019
  Outcome assessment                      WP020
  Transition policy                       WP021
  Update synthesis                        WP022
  Apply update + fresh control            WP023
  Current PLAN_STEP execution binding     WP024
  PLAN_STEP execution-start composition   WP025

## 6. Frozen cross-cutting invariants

``` text
Plan != PlanRun
selection != activation
handling preparation != execution
WorkSubject != WorkOrigin
Context != Memory
orchestration != execution
ExecutionRequest != handler availability
binding != admission
execution != observation
observation != truth
evidence != assessment
assessment != policy
transition decision != mutation
ExecutionStatus != StepProgressState
Execution SUCCEEDED != expected outcome SATISFIED
Execution FAILED != StepProgress FAILED
handler invocation ⇒ activation succeeded
activation succeeded ⇏ handler definitely executed user code
```

# PART V --- DEBT, RISKS, OPEN SEAMS

## 7. Technical debt

Known historical global Ruff-format debt: `iris/core/system.py`. Do not
mix unrelated cleanup into a WP merely to turn a global format check
green.

WP025 reported no new technical debt.

## 8. Accepted risks

-   ACTIVE may exist even if a crash prevents handler user code from
    running.
-   No exactly-once guarantee exists.
-   No durable transaction connects PlanRun with external side effects.
-   No generic crash recovery exists yet.
-   External effects may be non-reversible even though PlanRun is
    immutable.
-   Deterministic lineage does not imply distributed durability.

## 9. Open seams

The immediate visible seam is no longer safe start. WP025 answered that.
FORWARD questions now include ACTIVE-step interruption/reconciliation,
evidence of whether execution really began, retry/idempotency safety,
durable execution/recovery, controlled continuation,
persistence/checkpointing and eventually the cognitive/work loop.

These are questions, not WP026 requirements.

# PART VI --- DEVELOPMENT METHOD

## 10. Architect / Engineer roles

**Architect owns:** framing, research, responsibility separation,
invariants, adopt/adapt/reject decisions, contract pass, WP
specification, merge gate and continuity checkpoints.

**Engineer / Work owns:** repository inspection, implementation, tests,
quality gates, packaging, technical verification, progress report,
bundle production and surfacing contradictions.

Engineer may use implementation judgment inside frozen architecture, but
must not silently redesign it for convenience.

## 11. Standard WP flow

``` text
Q1 — What would we do blind?
→ derive from IRIS contracts

Q2 — What did comparable systems do?
→ research mechanisms

Q3 — What do we change for IRIS?
→ adopt / adapt / reject

CONTRACT PASS
→ inspect exact repository contracts
→ freeze ownership/APIs/invariants/negative boundaries

WORK PACKAGE
→ Engineer implementation

PROGRESS REPORT
→ bundle/push

PR
→ Architect merge gate

MERGE
→ canonical main
```

Q1 before Q2 reduces reflexive copying. Q2 tests our design. Q3 is
synthesis.

## 12. Research discipline

External systems are references, not templates. Registry entries should
distinguish FACT, INFERENCE and IRIS DECISION, with classifications such
as INFLUENCED, REVIEWED and REJECTED_PATTERN.

Important reference families at this checkpoint include OpenJarvis,
OpenClaw, Letta, Mem0, LangGraph, Microsoft Agent Framework, AutoGen,
OmniRoute and PersonalJarvis, plus focused references in the repository
registry.

# PART VII --- CONTINUITY AND INCIDENT RECOVERY

## 13. ACC cadence

Architect chats can hit conversation-length limits. Create a checkpoint
every five WPs:

``` text
ACC-WP005
ACC-WP010
ACC-WP015
ACC-WP020
ACC-WP025
ACC-WP030
...
```

Changing chats/desktops must not mean changing architecture.

## 14. Work interruption lesson

During WP023, Work reached a usage limit during execution.

``` text
interrupted execution != known failure
interrupted execution != known success
```

Recovery: inspect actual artifacts/state, identify the last verified
boundary, avoid blind replay, resume only after understanding what
happened, then verify final branch/bundle/commit as an incident
recovery.

## 15. Git/bundle fast path

``` text
Engineer clean commit
→ self-contained bundle if push unavailable
→ local repo
→ git bundle verify
→ fetch bundle branch
→ switch
→ verify ancestry
→ verify clean status
→ push
→ PR
→ Architect merge gate
```

A downstream ancestry failure after a failed bundle import does not
prove the bundle is bad; diagnose the first failure first.

# PART VIII --- RESOURCE-AWARE ENGINEERING

## 16. Objective: maximize useful capacity

The goal is not minimum model usage. It is maximum useful, correct
progress from available engineering capacity.

``` text
EFFICACY > EFFICIENCY > SAVING CAPACITY
```

Choose enough capability to produce the required quality reliably. Then
remove compute/effort that does not improve the result. Do not degrade
quality merely to preserve quota, and do not spend maximum reasoning on
mechanical work that gains nothing from it.

Two hundred weak WPs full of patches are worse than fewer sound
foundations.

## 17. Model / reasoning selection

Model capability and reasoning effort are separate tools. Treat
selection as choosing the right screwdriver, not as a fuel gauge.

Historical process:

``` text
earlier IRIS → Luna sufficient for simpler work
architecture grew → GPT-5.6 Sol appropriate
around WP025 → GPT-5.6 Sol High is proven baseline for complex WP implementation
future → stronger models such as Astra only when complexity genuinely justifies escalation
```

This is not a permanent model lock.

Practical guideline:

``` text
mechanical verification / known Git work → lower reasoning may suffice
well-specified local implementation      → moderate reasoning may suffice
normal complex IRIS WP                   → 5.6 Sol High baseline
difficult architecture/recovery/concurrency → consider higher reasoning
problem exceeds reliable Sol capability  → consider stronger model (e.g. Astra)
```

More reasoning is not automatically better. Less reasoning is not
efficient if it creates defects and rework.

## 18. Limits and resets

Capacity limits are operational constraints, not architectural goals.
Know 5-hour/weekly capacity and reset expiration; avoid wasting expiring
resets when valuable prepared work exists; avoid burning resets on
low-value work; prepare useful backlog before intentional reset use;
avoid starting huge WPs near hard limits when interruption risk is
unnecessary; preserve recovery information.

A reset is valuable when it becomes verified engineering progress.
Unused capacity is not inherently virtuous; consumed capacity is not
inherently productive.

# PART IX --- FORWARD ARCHITECTURAL VIEW (NON-BINDING)

## 19. Warning

This section records how architecture was understood at ACC-WP025. It is
not a committed roadmap. Future code, experiments, operational evidence,
references or contradictions may invalidate it.

**Preserve the reasoning; do not blindly preserve the prediction.**

## 20. Near-term pressure

WP012--WP025 constructed explicit semantics for:

``` text
plan → run → select → prepare → contextualize → orchestrate
→ bind → activate → execute → observe → assess
→ decide transition → update → advance
```

The next pressure is likely to move from "can these pieces exist
safely?" toward interruption/recovery, ACTIVE-work reconciliation,
retry/idempotency semantics, durable execution evidence, controlled
continuation and eventually a cognitive/work loop.

Why: WP025 exposes the real crash window
`ACTIVE committed → crash → handler may or may not have run`. IRIS
should not solve that by lying, blindly rolling back or assuming
failure.

## 21. Cognitive loop direction

Eventually the explicit stages may compose into
`decide → act → observe → evaluate → decide next action`, but only after
explicit answers exist for continuation authority, stop conditions,
budgets, uncertainty, retries, human gates, side-effect safety,
persistence/recovery, evidence, policy and observability.

STOP-after-each-stage is not a failure; it is how semantics are
understood before autonomy.

## 22. Memory/personal continuity direction

Future memory work may decide what deserves persistence, retrieve
relevant information rather than load everything, supersede stale
knowledge, preserve provenance, and distinguish private personal
learning from generalizable system improvements. Stored memory must not
equal always-loaded context.

## 23. Distributed IRIS / resource fabric

Creative direction: **one IRIS, many nodes**. Nodes may contribute
compute, GPU, storage, camera, microphone, sensors, network presence,
tools and execution providers.

Future questions: node identity, manifests, observed health, trust,
permissions, scheduling, contention, availability, provenance and
principal authority. OpenClaw/OpenJarvis remain useful references.

Avoid separate IRIS personalities per device when one identity plus
distributed providers suffices.

## 24. Multi-agent / specialist direction

Specialists, handoffs and message passing may become useful, but IRIS
should not become multi-agent because the pattern is fashionable.
Introduce specialists only when they provide concrete advantage over one
orchestrator plus typed capabilities/providers.

## 25. Safety / authority direction

As real execution power grows, future architecture may need
permission/authority, policy evaluation, risk classification,
dry-run/simulation, human approval, capability admission, sandboxing,
postcondition verification, compensation where possible and
uncertainty-aware abstention.

A useful recurring safety pattern is:

``` text
observe → evidence → classify → verify → policy → act → verify postcondition
```

Safety should not collapse into asking an LLM "is this safe?".

## 26. MARK evolution direction

MARK represents disciplined evolution, not blind self-modification:

``` text
experience → observe → explain → generalize → design candidate
→ simulate/sandbox → validate → human/policy gate
→ adopt → monitor → re-evaluate
```

A future MARK Lab may propose/test improvements but should not
automatically possess deployment authority. Experience produces evidence
for evolution, not self-authorization.

## 27. Multimodal / ambient direction

Voice, vision, gesture, desktop interaction, ambient presence and
visual/spatial interfaces may become provider/interaction layers around
the core rather than reasons to rewrite the core.

# PART X --- NEXT ARCHITECT BOOT PROCEDURE

## 28. If you are the next Architect

1.  Verify repository and current `main`.
2.  Compare current main against ACC-WP025 SHA.
3.  If later WPs exist, read them before assuming this checkpoint is
    current.
4.  Read authority map and frozen invariants.
5.  Read risks/open seams.
6.  Inspect Reference Registry.
7.  Reconstruct the current unresolved seam from repository reality.
8.  Do not assume the FORWARD direction is mandatory.
9.  Run Q1 → Q2 → Q3 → contract pass before issuing the next WP.
10. Continue the architecture; do not redesign IRIS from scratch because
    the conversation changed.

## 29. Do not infer from this checkpoint

Do not infer that WP026 must implement recovery; IRIS must use
LangGraph; IRIS must become multi-agent; Astra is required; distributed
nodes require multiple IRIS identities; ACTIVE proves handler code ran;
or a cognitive loop should bypass existing stages.

This checkpoint records reasoning, not destiny.

# PART XI --- MAINTENANCE

## 30. Next checkpoint

Unless an emergency checkpoint is needed earlier, next scheduled
checkpoint: `ACC-WP030`.

Preserve ACC-WP025. Create a new checkpoint rather than overwriting this
historical perspective. Explain what changed, which FORWARD hypotheses
survived/changed/were rejected, and update authority/open-seam maps.

# FINAL HANDOFF

At ACC-WP025, IRIS has crossed an important threshold. It now has
explicit architectural pieces spanning:

``` text
intent → planning → run state → control → work identity
→ context → orchestration → execution → observation → evidence
→ assessment → transition policy → mutation → advancement
→ safe execution start
```

The most important achievement is not merely that IRIS can do more. It
is that the system increasingly knows **what each claim means, which
subsystem may make it, and which conclusions it is not yet entitled to
draw**.

That discipline is what should make later autonomy possible without
turning IRIS into a collection of patches.

The next Architect inherits a system, not a pile of WPs.

**END OF ACC-WP025**
