# IRIS

IRIS is an early-stage personal intelligent system for computing, automation,
and device interaction. The project is currently a small Python foundation,
not yet an autonomous assistant or an LLM application.

## Current state

IRIS 0.1 currently provides:

- a local interactive terminal interface;
- `estado`, `ayuda`, and `salir` commands;
- best-effort host information for CPU, memory, disk, battery, operating system,
  Python version, device name, and time;
- typed `Request` and `RouteDecision` models;
- deterministic routing for the current terminal commands;
- a separate command-dispatch boundary that coordinates routing decisions;
- an explicit registry and runtime for executable capabilities;
- a structured capability result model for inspectable success and failure;
- `system.status` as the first registered technical tool;
- provider-independent contracts, models, registry, and runtime for future
  generative intelligence;
- an optional Ollama provider for explicit local model discovery and text
  inference through that Intelligence boundary;
- typed intelligence needs, routable resources, hard-constraint candidate
  resolution, and a deterministic replaceable routing policy;
- structured `EXACT`, `DEGRADED`, and `UNSATISFIED` intelligence routes;
- explicit local memory persistence through a domain service and versioned
  SQLite backend, with provenance, temporal validity, lifecycle and relations;
- work-subject-scoped, bounded Context snapshots built deterministically from
  explicitly supplied, traceable evidence;
- a deterministic single-step Orchestrator that binds WorkSubject, exact
  ContextSnapshot, explicit needs, and availability into traceable decisions;
- a single-step Execution Coordinator with explicit handlers for system,
  memory, capability, and intelligence decisions;
- immutable execution requests/results with end-to-end identity, structured
  failures, and an explicit side-effect boundary;
- explicit adaptation of PLAN_STEP execution results into raw, append-only
  PlanRun observations without outcome interpretation or progress mutation;
- bounded recording of one WP025 execution result as exactly one canonical
  PlanRun observation and one immutable Run revision, without changing
  StepProgress or continuing execution;
- complete structural collection of one PlanStep's canonical evidence from an
  explicitly supplied immutable Run revision, followed by exactly one existing
  outcome-evaluator invocation and no Run mutation;
- immutable PlanStep outcome assessments over explicitly selected, canonical
  PlanRun evidence, with a conservative replaceable evaluator;
- immutable StepProgress transition decisions that separate assessment
  applicability, operational policy, and future progress mutation;
- bounded PlanRun progress advancement that applies one StepProgressUpdate,
  derives one new immutable Run revision, makes one post-mutation control
  decision, and stops;
- immutable Goal, Plan, and PlanStep representations with explicit constraints,
  success criteria, assumptions, expected outcomes, and dependency validation;
- a provider-independent Planner contract plus an explicit-rule deterministic
  implementation for side-effect-free, reproducible planning;
- immutable PlanRun revisions with explicit step progress, append-only
  observations, step-scoped blockers, optimistic revision checks, and derived
  availability/structural conditions;
- typed architectural contracts for future skills and actions;
- automated tests for the existing behavior and contracts.

IRIS does **not** bundle a model or connect one automatically. It also does not
include retry or fallback after execution failure, an iterative agent loop,
autonomous planning/execution, a PlanRun Controller, authorization, semantic
retrieval, voice, vision, or complex system actions. Ollama is an optional,
replaceable backend; it is not IRIS or IRIS's identity. The intelligence router
is deterministic and specialized; it is not an LLM-based Brain Router.

## Platform and product direction

IRIS 0.1 is **Windows-first, core-portable**. Windows is the initial supported
product target, while core code avoids unnecessary Windows coupling and degrades
gracefully when an operating-system metric is unavailable. Full Linux and macOS
support is not claimed.

The long-term direction is **local-first, cloud-augmented**. Future local and
cloud models will be interchangeable resources used by IRIS; identity, context,
memory, routing, permissions, and state belong conceptually to IRIS itself.
IRIS is not a model. Models and their providers are resources behind an IRIS-
owned boundary. WP005 provides the first real adapter, for Ollama, while keeping
provider and model selection explicit.

## Requirements

- Python 3.11 or newer
- Windows for the officially targeted 0.1 experience
- Ollama only when running the optional physical local-inference path

## Installation

Create and activate a virtual environment, then install the project:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

For development and tests, install the `dev` extra:

```powershell
python -m pip install -e ".[dev]"
```

Dependencies are declared in `pyproject.toml`; no manual installation of
`psutil` is required.

## Run IRIS

From the repository root:

```powershell
python -m iris
```

The installed console entry point is also available:

```powershell
iris
```

Current commands:

| Command | Behavior |
| --- | --- |
| `estado` | Shows a best-effort system snapshot. |
| `ayuda` | Lists available commands. |
| `salir` | Closes IRIS cleanly. |

Individual system metrics may display `No disponible` when the platform,
permissions, or runtime cannot provide them. This is an expected recoverable
condition and does not terminate the CLI.

## Local inference with Ollama

`OllamaProvider` uses Ollama's native local HTTP API with Python's standard
library. It discovers installed models through `/api/tags`, verifies their
declared `completion` capability through `/api/show`, and performs
non-streaming text inference through `/api/generate`. No Ollama SDK or new
runtime dependency is required.

Configuration is explicit per provider instance:

| Setting | Default | Purpose |
| --- | --- | --- |
| `provider_id` | `ollama-local` | Stable identity; independent of location. |
| `endpoint` | `http://127.0.0.1:11434` | Ollama server root URL. |
| `timeout` | `120` seconds | Finite discovery and inference timeout. |

Multiple Ollama instances can therefore be registered with different provider
IDs and endpoints. IRIS does not select between them automatically. Use only
trusted local or private endpoints; WP005 adds no public exposure, LAN discovery,
authentication, or Resource Mesh.

The shortest physical smoke test on the Windows development machine is:

```powershell
ollama pull qwen3:8b
python -m iris.intelligence.providers.ollama_smoke --model qwen3:8b
```

`qwen3:8b` is only the reference smoke model. It is not hardcoded into the
provider or treated as IRIS's model. Once Ollama and the selected model are
available locally, this inference path needs no cloud service or Internet
connection.

## Tests

```powershell
pytest
```

Normal tests mock HTTP and never require, start, or download Ollama models. A
real integration test is explicitly opt-in:

```powershell
$env:IRIS_RUN_OLLAMA_INTEGRATION="1"
pytest -m integration tests/integration/test_ollama_integration.py
```

The integration test defaults to `qwen3:8b`. `IRIS_OLLAMA_ENDPOINT`,
`IRIS_OLLAMA_PROVIDER_ID`, `IRIS_OLLAMA_MODEL`, and `IRIS_OLLAMA_TIMEOUT` can
override its physical test configuration without changing repository files.

## Module direction

The current request path for `estado` is:

```text
Raw terminal input → Request → DeterministicRouter → RouteDecision
                   → CommandDispatcher → CapabilityRuntime
                   → system.status tool → CapabilityResult → CLI output
```

The Router only decides a target and records a reason. It does not execute
system information, actions, skills, or other effects. `CommandDispatcher`
handles the interface-only `ayuda`, `salir`, and unknown-command responses;
for executable capabilities it delegates to `CapabilityRuntime`. It does not
implement `system.status` itself.

Capabilities are registered explicitly in process. There is no plugin loading,
filesystem discovery, or dynamic import mechanism. The registry rejects
duplicate identifiers and unknown lookups. The runtime accepts explicit input,
locates the selected capability, and returns a structured `CapabilityResult`.
Expected operational failures are represented by failed results; unexpected
programming exceptions remain visible.

The separate Intelligence path established in WP004 is:

```text
IntelligenceRequest → IntelligenceRuntime → ProviderRegistry
                    → IntelligenceProvider → IntelligenceResult
```

`IntelligenceRequest` carries text, an explicitly requested model identifier,
correlation identity, and extensible metadata. The runtime receives an explicit
provider identifier, verifies that provider/model pairing, performs inference
through a structural provider contract, and validates the returned identity.
It does not choose a provider or model, fall back automatically, call tools, or
participate in the CLI request path. Providers are registered explicitly per
registry instance; there is no global registry or discovery mechanism.
Intelligence providers are not Tools, and `IntelligenceRuntime` does not execute
capabilities; orchestration between those subsystems remains future work.

WP006 adds a selection layer above that runtime:

```text
IntelligenceNeed + IntelligenceResource values
    → CandidateResolver (hard requirements only)
    → RoutingPolicy (soft preferences only)
    → IntelligenceRoute
    → caller constructs IntelligenceRequest
    → IntelligenceRuntime
```

An `IntelligenceNeed` describes one cognitive need rather than an entire user
request. Its requirements contain demonstrable model capabilities and an
optional execution-location constraint. Its ordered preferences use separately
declared model affinities such as reasoning, code, fast response, or resource
efficiency. Affinities are routing evidence supplied by configuration; they are
not inferred from provider/model names and are not represented as technical
capabilities. The current capability vocabulary can describe text generation
and embedding, but no embedding provider or embedding runtime is implemented.

`CandidateResolver` removes unavailable resources and those that violate a
required capability or location. It never selects the preferred candidate.
`DeterministicRoutingPolicy` runs only over this valid candidate set, prioritizes
ordered affinity matches, and resolves ties by stable provider/model identity.
The same need, resources, and policy therefore produce the same route regardless
of input order.

An `EXACT` route satisfies every requirement and preference. `DEGRADED` still
satisfies every hard requirement but records unmet preferences. `UNSATISFIED`
selects no resource because no candidate satisfies all requirements. A
preference can never authorize a forbidden resource, and the router does not
silently fall back from local to cloud. Provider failure during inference is an
execution result, not a routing outcome; retry and fallback policy remain future
orchestration concerns.

Locality is represented only as execution location. It does not assert trust,
privacy, authorization, or data sensitivity. Those are future security and
resource-management boundaries. The router also does not decide between a
model, tool, action, or memory; a future Orchestrator will create individual
`IntelligenceNeed` values when intelligence is appropriate. Multi-resource
plans, adaptive/learned routing, benchmarks, and operational telemetry are not
implemented.

WP005 implements `OllamaProvider` behind this boundary. Ollama protocol details
remain inside the adapter; they do not become IRIS core types. Discovery
failures use specific operational exceptions because `list_models()` has no
result envelope. Inference failures use a structured failed
`IntelligenceResult`. Unexpected programming errors and contract violations
remain visible.

## Memory foundation

`MemoryCandidate` is explicit caller-supplied evidence. `MemoryService` assigns
a stable ID and UTC `recorded_at`, then persists a `MemoryRecord` through the
backend-independent `MemoryStore` contract. `SQLiteMemoryStore` uses a
caller-supplied local path and SQLite schema version 1 (`PRAGMA user_version`).
Existing databases reopen without resetting data; unsupported future versions
or unversioned nonempty databases fail without automatic modification. No
database path, capture source, or automatic persistence is wired into the CLI.

Each record retains its class (working/episodic/semantic), extensible kind,
subject, scope, retention, provenance, epistemic status, acquisition mode,
source/artifact references and distinct `observed_at`, `recorded_at`,
`valid_from`, `valid_until` timestamps. Times must be timezone aware and are
stored in UTC. Unknown times stay unknown. References are identifiers; the
memory backend does not access or copy artifacts.

`MemoryService.query(MemoryQuery(...))` defaults to `ACTIVE` records and orders
results by `recorded_at` then ID. A temporal query filters `observed_at` using
the half-open interval `[observed_from, observed_until)`; unknown observation
times do not match that range. Explicit `statuses=None` includes history.
`get(id, include_history=True)` can inspect a hidden record. Supersession
atomically stores a new record, marks the old one `SUPERSEDED`, and saves a
`SUPERSEDES` relation. `retract`, `forget` and explicit `expire` change lifecycle
without physically deleting evidence. Retention is metadata, with no daemon.

`current(subject, kind, scope, as_of)` considers only active, temporally valid
records for that exact scope. It compares effective validity/observation time,
never insertion time. Missing event time or tied latest observations produce
`AMBIGUOUS`; no matching active evidence produces `NONE`. Its `FOUND` result
identifies current **stored evidence**, not verified external truth. Historical
queries can inspect superseded or retracted records, but `current` is not a
historical state reconstruction API.

Memory does not convey authorization, instructions or automation. Acquisition
modes such as ambient can be represented without implementing perception or
permission to persist. There is no MemoryPolicy, automatic learning, vector
search, RAG, graph database, cloud sync or privacy erasure engine. Memory does
not automatically drive Context. Local databases contain readable plaintext;
the caller controls where they are stored and who can access them.

## Context foundation

`iris.context` constructs an ephemeral `ContextSnapshot` owned by an explicit
`WorkSubject` from caller-supplied `ContextCandidate` values. The canonical
snapshot stores the small immutable subject value and derives `subject_id` from
it; `request_id` remains a compatibility accessor only for `REQUEST` subjects.
The legacy `request_id` build input is adapted immediately into the same
subject-based pipeline, and cannot be supplied together with `subject`.

Each candidate has a
scoped kind/key, simple scalar value, traceable evidence reference and epistemic
status, plus independent relevance and freshness categories. Available evidence
must be explicitly eligible to be selected; Context never grants permission or
turns a claim into verified truth. Timestamps are timezone aware and normalized
to UTC, while unknown observation times stay unknown. Scope uses the same
explicit `MemoryScope` identifiers as Memory, without implicit inheritance.

The replaceable selection policy first excludes ineligible candidates, then
orders by relevance (`REQUIRED`, `HIGH`, `NORMAL`, `LOW`) and freshness
(`CURRENT`, `RECENT`, `STALE`, `UNKNOWN`). Scope, kind, key and candidate ID
break ties consistently regardless of input order. Identical candidate IDs
deduplicate; incompatible reuse of an ID fails explicitly. Equal-priority,
incompatible values for the same scoped key yield a conflict with evidence
references, not an arbitrary latest-value choice. Callers may declare other
uncertainties, including multiple plausible interpretations or missing evidence.
Snapshots report `RESOLVED`, `PARTIAL`, `AMBIGUOUS` or `CONFLICTED` accordingly.
An explicit item budget bounds every snapshot; excluding high or required
evidence due to budget reports a partial result.

`MemoryContextSource` offers an optional read-only bridge from an exact
`MemoryQuery` (subject, kind and scope) to candidates. Normal lookup includes
only active records and supplies a record ID instead of its content; content
expansion and historical lookup both require explicit caller opt-in. Multiple
matching records in reference-only mode require a narrower query or explicit
content expansion, so unrelated IDs cannot masquerade as conflicting facts.
The source does not select relevant memories or alter their lifecycle.

Context is selected evidence for the current work subject: it is separate from
persistent Memory, Session continuity and external State. Ownership does not
constrain general evidence provenance. `REQUEST` evidence must, however, match
the `REQUEST` subject or the Request root explicitly recorded in a `PLAN_STEP`
subject's `WorkOrigin`; this verifies causal compatibility, not truth or trust.
A derived subject never inherits its origin's Context—relevant evidence must be
supplied again explicitly.

Building a snapshot does not write Memory, mutate PlanRun, invoke providers or
tools, choose actions, plan, grant authorization or construct an LLM prompt. A
PLAN_STEP snapshot does not impersonate its Request origin; it can now enter
Orchestration as its own operational subject.

## Orchestrator foundation

`iris.orchestrator` implements one work-subject-scoped `observe → decide → stop`
step. An `OrchestrationInput` binds one `WorkSubject` to an exact
subject-owned `ContextSnapshot`, explicit `HandlingNeed` values and
caller-supplied `HandlerAvailability`. Ownership is checked through canonical
`subject_id`, so updated origin knowledge does not change identity and a root
Request cannot stand in for a derived PLAN_STEP. Availability is never
discovered through the network, filesystem, provider registries or device
state.

`DeterministicOrchestrationPolicy` produces exactly one immutable,
provider-neutral `OrchestrationDecision`. Targets are `SYSTEM`, `MEMORY`,
`CAPABILITY`, `INTELLIGENCE`, `CLARIFY` and `UNSATISFIED`. Structured reason
codes, need IDs, snapshot identity and context issue references provide
traceability without storing private model reasoning. Each decision records
canonical `subject_id` plus the exact `context_snapshot_id`; a pure validator
rejects decisions used with another subject or snapshot. The existing
deterministic Router can supply a recognized system route; Intelligence needs
are preserved for the separate Intelligence Router; capability IDs and Memory
operation descriptors remain inputs for their established subsystems.

Context ambiguity, conflict or missing information blocks a decision only when
the caller explicitly links that issue to the current need. Unrelated partial or
conflicted Context does not force clarification. An unavailable required handler
produces `UNSATISFIED`; several needs produce the explicit
`COMPOSITE_HANDLING_REQUIRED` result because this version performs one step.

The Orchestrator coordinates IRIS; it does not replace the systems it
coordinates. It does not execute capabilities, access Memory, invoke
Intelligence, choose providers/models, infer authorization, plan, retry or
construct prompts. Execution consumes its decisions through a separate
boundary. `request_id` is retained on REQUEST orchestration decisions solely as
a non-canonical compatibility value, is absent for PLAN_STEP decisions even
when their origin is a Request, and never appears in canonical orchestration or
execution lineage. WP018 Execution uses `subject_id` and the exact Context
snapshot instead. Iterative cognitive loops remain future work.

Memory tells IRIS what has been preserved. Context tells IRIS what is relevant
now. The Orchestrator decides which subsystem should handle the next step.
Execution performs that single step and records what happened.

## Goal and Planning foundation

`iris.planning` represents desired outcomes and possible strategies without
performing them. A `Goal` keeps its own identity, objective, scope, provenance,
constraints and success criteria. A `Plan` has a separate identity and contains
explicit assumptions plus immutable `PlanStep` values. Every step declares its
own objective, dependencies, optional high-level `HandlingKind`, constraints and
expected outcome. Expected outcomes are intentions, not observed results.

Dependencies are semantic edges rather than list ordering. Plan construction
rejects duplicate step IDs, unknown dependencies, self-dependencies, cycles and
zero-step plans. Multiple roots, multiple terminal steps and diamond-shaped DAGs
remain valid. Stable serialization orders steps and dependencies by identity;
this does not authorize concurrent execution.

The provider-independent `Planner` protocol returns one typed `PlanningResult`:
`PLAN_CREATED`, `NO_PLAN_REQUIRED`, `INSUFFICIENT_CONTEXT`, or
`UNSATISFIABLE`. The initial `DeterministicPlanner` uses caller-supplied exact
objective rules. It consumes only its `PlanningRequest` and optional explicit
`ContextSnapshot`; it performs no Memory lookup, provider invocation, tool
discovery, orchestration or execution. Unknown objectives are unsatisfiable only
under that configured rule set, not claims of real-world impossibility.

Goal is not Plan. Plan is not PlanRun, authorization or execution. Planning
answers what would have to be done, validates the representation, and stops.
There is no automatic plan persistence, approval, step dispatch, progress
tracking, retry, replanning, concurrency or cognitive loop in WP011. WP008
Context remains immutable input, WP009 Orchestrator remains the handling
decision boundary, and WP010/WP018 Execution remains the single-step
side-effect boundary.

## PlanRun and progress-state foundation

`iris.plan_runs` represents one operational instance of an immutable WP011
`Plan`. A revision-zero Run contains exactly one `NOT_STARTED` `StepProgress`
for every PlanStep. Each explicit atomic `PlanRunUpdate` is checked against its
expected revision and, when valid, the deterministic `PlanRunReducer` produces
a new immutable revision. It never mutates the Plan or earlier Run snapshot.

Step progress is deliberately small: `NOT_STARTED`, `ACTIVE`, `SUCCEEDED`, and
`FAILED`. Only the documented forward transitions are legal, and terminal
transitions require references to observations already recorded in the same
Run with compatible scope. Recording an observation never changes progress.
An execution failure is therefore not automatically a failed step, and a
successful execution is not automatically a successful step.

Eligibility is derived from `Plan + PlanRun`, not persisted as progress.
`READY`, `WAITING_DEPENDENCIES`, `BLOCKED`, `ACTIVE`, and `TERMINAL` follow a
fixed precedence over progress, explicit active blockers, and dependency
states. Multiple READY steps remain unselected. Dependency failure blocks a
dependent step without manufacturing a redundant blocker.

The derived Run condition is `OPEN`, `STRUCTURALLY_COMPLETE`, or
`CANNOT_ADVANCE`. Structural completion means every step is `SUCCEEDED`; it is
not proof that the Goal is satisfied. Cannot-advance means no step is READY or
ACTIVE under the current snapshot; it is not Goal failure and does not trigger
retry, replanning, abandonment, or execution.

WP012 contains no Controller, next-step selection, Execution bridge, outcome
evaluator, attempts, retry, pause/resume, checkpoint persistence,
authorization, automatic Memory/Context mutation, agent loop, or durable
workflow. Applying one update produces one new state snapshot and stops.

## PlanRun control-decision foundation

`iris.plan_control` observes one validated `Plan + PlanRun` revision, reuses
WP012's canonical availability and Run-condition projections, produces exactly
one immutable `ControlDecision`, and stops. Its outcomes are `STEP_SELECTED`,
`ACTIVE_WORK_PENDING`, `SELECTION_UNRESOLVED`, `RUN_CANNOT_ADVANCE`, and
`RUN_STRUCTURALLY_COMPLETE`.

Control is serial and conservative in WP013. Any `ACTIVE` step takes precedence
over selecting additional `READY` work, including when several steps are
already active. A sole `READY` step is selected directly. Multiple `READY`
steps require an explicit `StepSelectionPolicy`; absence or legitimate policy
abstention produces `SELECTION_UNRESOLVED`, never an ordering-based fallback.
Stable candidate serialization order is not operational priority.

The initial `ExplicitPriorityStepSelectionPolicy` consumes immutable,
caller-supplied integer priorities. It selects only a unique highest-priority
candidate; missing priorities and maximum-priority ties remain unresolved. A
policy result naming an unknown or non-candidate step is rejected rather than
silently repaired.

Every decision records Plan identity, Run identity, observed revision,
structured reason, candidate and active step identities, and controller/policy
provenance. `validate_control_decision_current` rejects decisions for another
Plan or Run and decisions made against an earlier revision. Validation does not
recalculate or update a stale decision.

Selection is not activation, authorization, execution, or step success.
`decide()` does not mutate Plan or PlanRun, increment the revision, create a
`PlanRunUpdate` or `HandlingNeed`, invoke Orchestration or Execution, consult
Intelligence or Memory, modify Context, retry, replan, checkpoint, schedule, or
enter a loop. `RUN_STRUCTURALLY_COMPLETE` is not Goal satisfaction, and
`RUN_CANNOT_ADVANCE` is not Goal failure.

## PlanStep handling-preparation foundation

`iris.plan_handling` accepts one current `ControlDecision(STEP_SELECTED)`,
resolves the exact selected `PlanStep`, reuses WP012's canonical `READY`
projection, and produces one immutable `StepHandlingPreparationResult`. It
reuses the existing `iris.orchestrator.HandlingNeed` contract and stops before
orchestration, handler availability, authorization, activation, or execution.

Preparation is strictly declarative. A missing `required_handling` produces
`HANDLING_UNSPECIFIED`. Declared `SYSTEM`, `MEMORY`, or `INTELLIGENCE` handling
without a complete, compatible `StepHandlingSpecification` produces
`INSUFFICIENT_DETAIL`. `CAPABILITY` alone is sufficient for a generic
capability need whose `capability_id` remains `None`; an explicit compatible
specification may supply the identity. Missing detail is never inferred from
the step objective, expected outcome, constraints, Context, Memory, a model, or
a registry.
Supplying a specification for a step whose handling was not declared is a
contract contradiction and is rejected; a specification cannot silently
override the Plan.

Every prepared need has empty blockers and a deterministic identity derived
from Plan ID, Run ID, observed revision, and step ID. The preparation result
records those same causal identities plus a structured reason and preparer
provenance. `validate_step_handling_preparation_current` rejects another Plan,
another Run, a stale revision, a missing step, a non-`READY` prepared step, or
a noncanonical need identity; it does not refresh or repair the result.

Preparation does not create a synthetic `Request`, convert planning
constraints into authorization, convert expected outcomes into execution
input, call the Orchestrator or ExecutionCoordinator, mutate PlanRun, activate
the step, increment the revision, retry, replan, ask the user, persist state, or
enter a loop. `PREPARED` means only that a valid semantic need can be stated;
it does not mean safe, authorized, available, active, or executed.

## Work subject and origin foundation

`iris.work_identity` represents the current operational unit of work separately
from its known root cause. A `WorkSubject` is either a `REQUEST`, referenced by
`RequestWorkReference(request_id)`, or a `PLAN_STEP`, referenced by
`PlanStepWorkReference(plan_id, run_id, step_id)`. The typed reference must
match the subject kind.

`subject_id` is derived internally from a canonical structured encoding of the
kind and typed reference. It does not include origin, PlanRun revision, state,
Context, handling, time, authorization, or random data. Consequently, one step
in one PlanRun retains its identity across revisions, while another Plan, Run,
or step has a different identity.

An optional `WorkOrigin(source_type, source_id)` records only the known root
causal reference. The Request adapter records the Request itself as its root.
The PlanStep adapter preserves an origin explicitly supplied by the caller or
uses `None`; it never discovers or fabricates one. Origin is descriptive
provenance, not an authenticated principal, permission, trust decision,
authorization, inherited Context, payload, or lineage graph.

The PlanStep adapter reuses WP012 PlanRun validation and verifies that the step
exists, but does not inspect availability or require a ControlDecision. Work
identity creation does not mutate PlanRun, activate work, create a
HandlingNeed, orchestrate, execute, persist, schedule, or introduce lifecycle
state. The subsystem's model layer depends only on identity primitives; its
adapter layer knows the established Request and Plan/PlanRun contracts.

## Execution foundation

`iris.execution` implements `decide → execute once → observe result → stop` for
both REQUEST and PLAN_STEP work subjects. An immutable `ExecutionRequest` binds
an independent execution ID to the complete `WorkSubject`, exact
`ContextSnapshot`, current `OrchestrationDecision`, and explicit handler
operands. Construction reuses WP017 currentness validation: subject ownership
is checked by `subject_id`, while the exact Context snapshot ID must match the
decision. A changed origin description does not change ownership, and a root
Request cannot impersonate derived PLAN_STEP work.

The lightweight `ExecutionResult` records `subject_id`, decision and Context
snapshot IDs, target, handler reference, structured status/output/failure, and
UTC start/completion timestamps. It stores no canonical `request_id`; the four
subject, snapshot, decision, and execution identities remain distinct.

`ExecutionCoordinator` dispatches deterministically from the already-selected
target to one caller-registered handler. `SYSTEM`, `MEMORY`, `CAPABILITY`, and
`INTELLIGENCE` are executable. `CLARIFY` and `UNSATISFIED` are terminal and
produce `NOT_EXECUTED` with zero handler calls. A missing executable handler is
reported as `REJECTED`; it never selects another subsystem.

The handlers are deliberately small adapters. They reuse `CommandDispatcher`,
`MemoryService`, `CapabilityRuntime`, and the existing Intelligence Router plus
`IntelligenceRuntime`. Intelligence routing still selects provider/model;
degraded but admissible routes execute once, while an unsatisfied route never
reaches the runtime. Memory executes only the operation and operands explicitly
carried by the decision/request. SYSTEM execution consumes a neutral immutable
`CapabilityInput` rather than a Request. `CommandDispatcher.dispatch_route()`
is the single Request-neutral route implementation; the legacy
`dispatch(request, decision)` API only adapts Request data into neutral
operands, preserving existing CLI behavior without synthetic Requests. No
automatic memory write occurs.

Execution is the explicit side-effect boundary of IRIS. Within one coordinator
call the selected handler is invoked at most once. This is not a global
exactly-once guarantee: there is no durable execution ledger, deduplication, or
idempotency framework. A failed execution is an observation, not permission to
retry: WP018 performs no retry, fallback,
rerouting, second orchestration, response synthesis, Context mutation, planning,
workflow decomposition, rollback, or automatic persistence. This is
at-most-once invocation within one process call, not distributed exactly-once
semantics.

Expected domain/operational outcomes are represented as `FAILED` or `REJECTED`;
contract violations and unexpected programming defects propagate. Explicit
dependency wiring and immutable trace data leave room to insert authorization,
confirmation, audit, cancellation, or policy checks around this boundary later,
without claiming any of those systems exist today. The Cognitive Loop comes
later.

## Execution observation foundation

`iris.execution_observation` adapts one completed `ExecutionResult` belonging
to a `PLAN_STEP` WorkSubject into one generic `PlanObservation`, then stops. It
validates the Plan/PlanRun pair with WP012, reads Plan/Run/step ownership only
from the typed `PlanStepWorkReference`, and requires the result's `subject_id`
to match. `WorkOrigin` is never used to repair or infer ownership.

The observation records `source="execution"`, `kind="execution_result"`, and
the concrete `execution_id` as `source_reference`. Its independent
`observation_id` identifies the evidence record. The payload is an explicit,
stable serialization of decision/context lineage, target and reason, execution
status, handler reference, timing, output, failure, and metadata; it does not
copy the result trace wholesale or duplicate execution/subject identity.

All four execution statuses are observable facts. `SUCCEEDED`, `FAILED`,
`REJECTED`, and `NOT_EXECUTED` are recorded without assessing a PlanStep's
expected outcome. In particular, Execution success is not Step success, and
failed, rejected, or non-executed work is not automatically PlanStep failure.
`ExecutionResult` and `PlanObservation` remain distinct contracts;
`PlanObservation` is not an outcome assessment.

Duplicate execution evidence is rejected locally when the same PlanRun already
contains an observation whose source is `execution` and whose source reference
is the same execution ID. This is evidence deduplication, not execution
deduplication, durable replay protection, idempotency, or exactly-once delivery.
Different executions for the same subject or decision remain distinct facts.

The adapter neither builds nor applies a Run update. A caller may explicitly
wrap the returned observation in `RecordObservationUpdate` and pass it to the
generic `PlanRunReducer`; that operation appends evidence and advances the Run
revision while leaving StepProgress and blockers unchanged. Recording evidence
does not invoke execution, assess outcomes, mutate progress, retry, replan,
or enter a control loop.

## Step outcome assessment foundation

`iris.outcome_assessment` evaluates an explicit tuple of already-recorded
`PlanObservation` values against the canonical `PlanStep` definition and
returns one inert `StepOutcomeAssessment`, then stops:

```text
Plan + PlanRun + PlanStep + explicit PlanObservation values
    → StepOutcomeEvaluator
    → StepOutcomeAssessment
    → STOP
```

The assessment records independent assessment identity, Plan/Run/step lineage,
the observed Run revision, exact evidence IDs, evaluator provenance, UTC time,
an epistemic status, and immutable structured details. Evidence must belong to
the same Run and step, must already be present in the immutable PlanRun, and
must equal the canonical recorded observation rather than merely reusing its
ID. Evidence selection remains the caller's responsibility; the evaluator does
not scan the Run to choose evidence.

The initial `ConservativeStepOutcomeEvaluator` is deliberately abstaining. An
empty evidence tuple yields `INSUFFICIENT_EVIDENCE`; valid evidence for which no
explicit deterministic rule exists yields `INDETERMINATE`. It never treats an
execution's `SUCCEEDED` status as proof that the expected outcome was achieved,
and it never treats `FAILED`, `REJECTED`, or `NOT_EXECUTED` as proof that the
outcome was not achieved. `SATISFIED` and `NOT_SATISFIED` remain supported by
the model and replaceable evaluator contract for future explicit verifiers.

Assessment is epistemic, not operational policy. WP020 does not create a
`StepProgressUpdate`, mutate or persist PlanRun, invoke the reducer, derive
availability or Run condition, evaluate Goal success, call Intelligence, chain
evaluators, retry, replan, or select subsequent work. The stored Run revision
is audit lineage only; WP020 introduces no assessment-currentness rule.

## Step progress transition decision foundation

`iris.step_progress_transition` consumes one explicitly supplied
`StepOutcomeAssessment` with the canonical `Plan`, current immutable `PlanRun`,
and canonical `PlanStep`. It validates identity and evidence lineage, checks
whether the assessment can conservatively govern the current step state,
invokes a replaceable transition policy only when applicable, and returns one
inert `StepProgressTransitionDecision`:

```text
StepOutcomeAssessment
    → assessment applicability
    → StepProgressTransitionPolicy
    → StepProgressTransitionDecision
    → STOP
```

Assessment revision and decision revision have deliberately different
semantics. `StepOutcomeAssessment.run_revision` is historical audit lineage;
an older assessment may remain applicable after unrelated Run revisions.
`StepProgressTransitionDecision.observed_revision` is instead a strict
currentness anchor: a later consumer must reject the decision after any Run
revision change.

The conservative applicability rule requires the assessment evidence IDs to
equal the current step-scoped observation IDs. New evidence for the same step
therefore produces `NO_TRANSITION` with
`INCOMPLETE_CURRENT_EVIDENCE_BASIS`; it does not invalidate or overwrite the
historical assessment. Run-level and other-step observations are excluded. An
assessment predating the current `ACTIVE` state's `changed_at` likewise
produces an auditable `NO_TRANSITION` without invoking the policy.

The baseline policy permits exactly one positive result: an applicable
`ACTIVE` + `SATISFIED` assessment requests `SUCCEEDED`. `NOT_SATISFIED` never
means `FAILED`, `NOT_STARTED` never jumps directly to `SUCCEEDED`, and terminal
steps are not reopened or resurrected by later assessments. WP021 creates no
`StepProgressUpdate`, invokes no reducer, mutates no PlanRun state, and performs
no retry, waiting, recovery, replanning, authorization, or external I/O.

## Step progress update synthesis foundation

`iris.step_progress_update_synthesis` binds one current actionable
`StepProgressTransitionDecision` to its explicitly supplied matching
`StepOutcomeAssessment` and returns the existing WP012 `StepProgressUpdate`:

```text
StepOutcomeAssessment + StepProgressTransitionDecision
    → StepProgressUpdateSynthesizer
    → StepProgressUpdate
    → STOP
```

The WP021 currentness validator first anchors synthesis to the exact current
PlanRun revision and observed source state. A `NO_TRANSITION` decision is valid
but non-materializable. For a positive decision, the assessment must match the
decision's Plan/Run/step/assessment identities, be `SATISFIED`, predate the
decision, cover the exact current step-scoped evidence basis, and be no older
than the current `ACTIVE` state.

The decision supplies what changes: step, target state, and observed revision.
The assessment supplies the terminal evidence IDs. The resulting update uses
`expected_revision = decision.observed_revision` and immediate provenance
`source_type="step_progress_transition"` with the decision ID. Decision
currentness protects decision-to-update synthesis; the update's expected
revision separately protects later update-to-Run mutation.

WP022 does not invoke `PlanRunReducer`, mutate PlanRun, rediscover or reevaluate
the assessment, rerun transition policy, deduplicate repeated synthesis, or
continue the plan. A caller may later apply the update explicitly through the
existing reducer; until then the Run remains unchanged.

## PlanRun progress advancement foundation

`iris.plan_run_advancement` composes exactly one existing progress update with
exactly one post-mutation control pass:

```text
StepProgressUpdate
    → PlanRunProgressAdvancer
    → PlanRunReducer
    → PlanRun(N+1)
    → PlanRunController
    → ControlDecision(N+1)
    → STOP
```

The reducer remains the authority for update identity, expected revision,
evidence, legal transitions, and immutable Run derivation. The controller then
observes only the derived `N+1` Run, and its decision is validated current for
that revision. `PlanRunProgressAdvanceResult` preserves the source update ID and
revision together with the new Run and the one resulting control decision.

This is bounded progress advancement, not a transaction or workflow loop. A
selected step remains `NOT_STARTED`: selection does not activate, prepare,
or execute it. The subsystem performs no persistence, retry, recovery,
replanning, Goal evaluation, second update, or automatic continuation.

## PlanStep execution binding foundation

`iris.plan_step_execution_binding` proves that one current selection, one
current prepared handling need, and one existing execution request all describe
the same exact pre-activation PlanStep on the same PlanRun revision:

```text
STEP_SELECTED + PREPARED handling + ExecutionRequest + PlanRun revision N
    → PlanStepExecutionBinder
    → PlanStepExecutionBinding(revision N)
    → STOP
```

The compact immutable binding preserves Plan/Run/step identity together with
the execution attempt, WorkSubject, ContextSnapshot, orchestration decision,
and HandlingNeed identities. Its currentness validator requires the exact Run
revision and confirms that the step remains `NOT_STARTED` and canonically
`READY`; any Run revision change requires a new binding even when the apparent
work identity is otherwise unchanged.

Binding is only a lineage witness. It does not activate the step, create a
`StepProgressUpdate`, invoke the reducer, admit or schedule execution, reserve
a handler, prove current handler availability, call `ExecutionCoordinator`, or
invoke a handler. Selection, preparation, request construction, binding,
runtime admission, and actual execution remain distinct boundaries.

## PlanStep execution start foundation

`iris.plan_step_execution_start` composes a still-current WP024 binding with
the exact bound `ExecutionRequest` at the real in-process handler boundary:

```text
current PlanStepExecutionBinding + exact ExecutionRequest
    → ExecutionCoordinator resolves the concrete handler
    → no handler: REJECTED, no activation, STOP
    → handler exists: revalidate currentness
    → StepProgressUpdate(NOT_STARTED → ACTIVE)
    → PlanRunReducer derives Run(N+1)
    → invoke that exact handler once
    → ExecutionResult
    → STOP
```

The generic `ExecutionStartGate` knows nothing about plans or `ACTIVE`; it only
lets a higher composition commit required start state after concrete handler
resolution and immediately before invocation. Existing execution callers that
omit the gate retain WP018 behavior.

`ACTIVE` means that a concrete handler was resolved and the local start
transition succeeded while execution was crossing toward invocation. It does
not mean that handler code completed, produced side effects, or achieved the
PlanStep outcome. Handler `SUCCEEDED`, `FAILED`, and invoked-handler `REJECTED`
results all leave the step `ACTIVE`; WP019-WP023 remain responsible for later
evidence interpretation and progress advancement.

This boundary guarantees only that handler invocation implies prior successful
activation. The reverse is intentionally false: a process failure can occur
after Run(N+1) is derived and before or during handler user code. WP025 has no
durable transaction, rollback, retry, reservation, queue, checkpoint, recovery,
or exactly-once guarantee. Escaping post-activation exceptions preserve the
derived ACTIVE Run and activation update identity for the caller.

## PlanStep execution-result recording foundation

`iris.plan_step_execution_result_recording` records one already-produced WP025
execution result into the exact immutable Run revision that result is authorized
to extend:

```text
PlanStepExecutionStartResult + exact recording-base PlanRun
    → reconstruct canonical PLAN_STEP WorkSubject
    → ExecutionObservationAdapter creates one PlanObservation
    → one RecordObservationUpdate
    → PlanRunReducer derives Run(N+1)
    → unchanged StepProgress
    → STOP
```

For a started attempt, the exact base is WP025's returned `ACTIVE` Run. For
handler unavailability, it is the original `NOT_STARTED` Run at the WP025 source
revision. Reusing the same start result against WP026's descendant Run is a
lineage error before observation adaptation.

Recording preserves the execution fact; it does not assess the expected
outcome, synthesize a progress transition, invoke a handler, retry execution,
select subsequent work, or continue the Plan. Execution `SUCCEEDED`, `FAILED`,
and `REJECTED` therefore leave the recording-base StepProgress state unchanged.

## PlanStep complete evidence assessment foundation

`iris.plan_step_evidence_assessment` evaluates the complete canonical evidence
basis of one PlanStep in one explicitly supplied immutable PlanRun revision:

```text
Plan + explicit PlanRun revision + step_id
    → validate PlanRun lineage
    → resolve the canonical PlanStep
    → collect every observation scoped exactly to that step
    → invoke one StepOutcomeEvaluator
    → validate assessment identity, evidence basis, and time
    → StepOutcomeAssessment
    → STOP
```

Evidence collection is structural: it preserves canonical Run ordering and
does not rank, filter semantically, or privilege execution observations. Run-
level observations, other-step observations, blockers, dependencies, and
StepProgress state do not enter the Step evidence basis.

The assessor establishes no global latest-Run authority. An assessment remains
an epistemic artifact of its recorded Run revision; WP021 separately determines
later operational applicability. WP027 performs no observation creation,
PlanRun mutation, progress transition, update synthesis, retry, execution, or
automatic continuation.

## PlanStep evidence-assessment transition composition

`iris.plan_step_evidence_transition` composes the existing WP027 and WP021
boundaries over one explicitly supplied immutable PlanRun revision:

```text
Plan + explicit PlanRun revision + step_id
    → PlanStepEvidenceAssessor produces one complete-basis assessment
    → resolve the canonical PlanStep
    → StepProgressTransitionDecider produces one operational decision
    → validate decision currentness against that same Run revision
    → assessment + transition decision
    → STOP
```

The assessment and decision remain distinct artifacts and observe the same Run
revision. A valid `NO_TRANSITION` is returned normally. WP028 creates no
`StepProgressUpdate`, invokes no reducer or controller, mutates no Run, and does
not continue execution; WP022 and WP023 retain those later responsibilities.

## PlanStep progress-update preparation

`iris.plan_step_progress_update_preparation` composes WP028 with WP022 over one
explicit immutable PlanRun revision. It preserves WP028's exact assessment and
transition decision, branches only on the decision action, and invokes WP022
exactly once only for `TRANSITION`. A `NO_TRANSITION` result carries no update.

The optional `StepProgressUpdate` is inert and revision-bound. WP029 does not
apply it, invoke a reducer or WP023, mutate the Run, retry, or continue the Plan.

## PlanStep progress advancement composition

`iris.plan_step_progress_advancement` composes WP029 with WP023 over one
explicit immutable PlanRun revision. It runs WP029 exactly once and, only when
an update exists, passes that exact update through WP023 exactly once to obtain
one successor Run and one fresh ControlDecision.

The returned ControlDecision is inert. WP030 does not activate selected work,
execute a step, retry, persist state, recompute control, or continue the Plan.

## Post-advancement PlanStep handling preparation

`iris.plan_step_handling_preparation` composes WP030 with WP014. It invokes
WP030 exactly once and stops without handling preparation when no advancement
exists or when the exact fresh post-advancement `ControlDecision` is not
`STEP_SELECTED`. Only `STEP_SELECTED` authorizes exactly one WP014 preparation
against the exact successor Run and exact fresh decision, without accepting or
resolving a `StepHandlingSpecification`.

The exact WP014 result is returned whether its status is `PREPARED`,
`HANDLING_UNSPECIFIED`, or `INSUFFICIENT_DETAIL`. WP031 performs no additional
control, specification lookup, orchestration, activation, execution, mutation,
retry, or continuation. Fresh control and prepared handling remain inert
artifacts at this boundary.

## Post-advancement selected-Step WorkSubject materialization

`iris.plan_step_work_subject_materialization` composes WP031 with the existing
WP015 PlanStep identity adapter. It invokes WP031 exactly once and produces no
subject when there is no advancement or when fresh post-advancement control is
not `STEP_SELECTED`. Only `STEP_SELECTED` authorizes exactly one WP015 call,
using the exact successor Run and the freshly selected Step identity. The
processed Step and newly selected Step may differ.

`PREPARED`, `HANDLING_UNSPECIFIED`, and `INSUFFICIENT_DETAIL` handling outcomes
all remain compatible with stable work identity. The resulting canonical
`PLAN_STEP` `WorkSubject` has no synthesized `WorkOrigin`, and its identity does
not encode PlanRun revision; successor revision currentness remains represented
by the advancement and fresh control artifacts. WP032 creates no Context,
orchestration, execution request, binding, activation, execution, second
control pass, or continuation.

## Post-selection WorkSubject Context materialization

`iris.plan_step_context_materialization` composes WP032 with the existing WP016
`ContextEngine`. It invokes WP032 exactly once and builds no snapshot when no
selected `WorkSubject` exists. When a subject exists, WP033 invokes WP016
exactly once with that exact subject and the caller's explicit candidates,
uncertainties, budget, and creation time, then stops.

Snapshot absence means only that no WorkSubject existed. An empty snapshot is
still a real `ContextSnapshot`, and `RESOLVED`, `PARTIAL`, `AMBIGUOUS`, and
`CONFLICTED` remain legitimate terminal results. WP033 performs no candidate
discovery, Memory retrieval, WorkOrigin synthesis, orchestration, execution,
retry, persistence, or continuation. Context ownership remains stable
WorkSubject ownership and does not prove a PlanRun revision.

## Post-Context selected-Step orchestration

`iris.plan_step_orchestration` composes WP033 with the existing WP017
`Orchestrator`. It invokes WP033 exactly once. No selected WorkSubject/Context,
`HANDLING_UNSPECIFIED`, and `INSUFFICIENT_DETAIL` all stop without
orchestration. `PREPARED` handling invokes WP017 exactly once using the exact
upstream WorkSubject, ContextSnapshot, revision-sensitive HandlingNeed, and
caller-supplied HandlerAvailability, then preserves the resulting decision and
stops. An unavailable prepared handler therefore produces a real canonical
`UNSATISFIED` decision rather than decision absence.

WP034 performs no handler discovery, handling enrichment, ContextBlocker
synthesis, execution request construction, binding, activation, execution,
mutation, retry, or continuation. Context status alone does not authorize
clarification; availability is neither authorization nor a durable freshness
proof; and an `OrchestrationDecision` remains an inert decision bound to the
exact WorkSubject and ContextSnapshot, not permission to execute.

## Post-orchestration ExecutionRequest materialization

`iris.plan_step_execution_request_materialization` composes WP034 with the
existing WP018 `ExecutionRequest` model. It invokes WP034 exactly once. When no
`OrchestrationDecision` exists, no request identity or request timestamp is
generated and the boundary returns `execution_request=None`. When a decision
exists, WP035 creates exactly one request from the exact upstream WorkSubject,
ContextSnapshot, and decision, plus the caller's explicit execution input, and
then stops.

Terminal `UNSATISFIED` (and globally valid `CLARIFY`) decisions still support
real requests with no execution input; request existence is not filtered by
WP024 PlanStep bindability. Executable targets retain WP018's target-specific
input validation. WP035 does not infer operands, enrich generic capability
identity, bind or activate a PlanStep, invoke an `ExecutionCoordinator`, run a
handler, mutate a PlanRun, retry, persist, or continue. An `ExecutionRequest`
is an inert request artifact, not execution authorization or execution itself.

## Post-request PlanStep execution binding composition

`iris.plan_step_execution_binding_composition` composes WP035 with the existing
WP024 `PlanStepExecutionBinder`. It invokes WP035 exactly once. Request absence
stops successfully with no binder call and `execution_binding=None`. Request
presence invokes WP024 exactly once using the exact successor pre-activation
PlanRun, fresh ControlDecision, current handling preparation, and canonical
ExecutionRequest preserved by WP035.

WP024 remains the sole bindability authority. Terminal `CLARIFY` and
`UNSATISFIED` requests therefore reach WP024 and retain its canonical rejection
rather than becoming successful no-binding outcomes. A successful binding is
only a current-revision lineage witness: WP036 performs no admission,
activation, handler resolution, execution, result recording, retry,
persistence, or continuation, and it stops at the exact WP024 binding.

## Post-binding PlanStep execution-start composition

`iris.plan_step_execution_start_composition` composes WP036 with an explicitly
configured WP025 `PlanStepExecutionStartCoordinator`. WP036 is invoked exactly
once. Binding absence stops successfully without calling WP025. Binding
presence passes the exact successor pre-activation Run, binding, and
ExecutionRequest to WP025 exactly once and preserves its exact start result.

WP037 adds no runtime configuration or handler policy. WP025 remains the owner
of revalidation, handler resolution, activation, invocation, and the canonical
handler-unavailable result. A source Run at revision N may yield a bound
pre-activation Run at N+1 and, only after successful activation, an ACTIVE Run
at N+2. Handler `SUCCEEDED`, `FAILED`, and invoked `REJECTED` outcomes all leave
the selected step ACTIVE; WP037 neither records nor assesses the ExecutionResult
and never continues the Plan.

## Post-start PlanStep execution-result recording composition

`iris.plan_step_execution_result_recording_composition` composes WP037 with the
existing WP026 `PlanStepExecutionResultRecorder`. WP037 is invoked exactly once.
Start-result absence stops successfully without calling WP026. A normal start
result invokes WP026 exactly once using the exact `ACTIVE` Run when activation
occurred, or the exact pre-activation successor Run when handler unavailability
left the selected step `NOT_STARTED`, then preserves the exact recording result
and stops.

Handler unavailability is therefore recordable execution evidence rather than
result absence. Invoked `SUCCEEDED`, `FAILED`, and `REJECTED` outcomes are also
recorded as uninterpreted facts against their exact `ACTIVE` Run. Recording
advances the chosen Run by one evidence revision while preserving StepProgress;
it does not assess the expected outcome or map `ExecutionStatus` to a progress
state. A post-ACTIVE `PlanStepExecutionInvocationError` remains exceptional and
is propagated without synthetic result or observation construction. WP038 does
not invoke WP027, retry execution, roll back activation, or continue the Plan.

## Post-recording PlanStep complete-evidence assessment composition

`iris.plan_step_execution_evidence_assessment_composition` composes WP038 with
the existing WP027 `PlanStepEvidenceAssessor`. WP038 is invoked exactly once.
Recording absence stops successfully without calling WP027 and preserves the
earlier cumulative `assessment`. Recording presence invokes WP027 exactly once
with the exact recorded Run and the exact recorded step, preserves its complete
Step-scoped evidence assessment separately as `post_recording_assessment`, and
stops.

The newly recorded execution observation must belong to that complete evidence
basis, but WP039 does not assess only the new observation. Handler-unavailable
evidence and invoked `SUCCEEDED`, `FAILED`, or `REJECTED` results all take the
same assessment path. WP039 does not map `ExecutionStatus` or StepProgress to an
outcome, invoke transition policy, mutate a Run, retry, recover, or continue the
Plan. Post-ACTIVE invocation exceptions remain exceptional and unrecorded.

## Post-assessment PlanStep transition-decision composition

`iris.plan_step_execution_transition_decision_composition` composes WP039 with
the existing WP021 `StepProgressTransitionDecider`. WP039 is invoked exactly
once. Post-recording assessment absence stops successfully without calling the
decider. Assessment presence supplies WP021 with the exact recorded Run, its
exact canonical selected step, and the exact WP039 assessment, then preserves
the current transition decision separately as
`post_recording_transition_decision` and stops.

The earlier cumulative `assessment` and `transition_decision` remain distinct
from the post-recording pair. A valid `NO_TRANSITION` is a real decision rather
than absence, including handler-unavailable evidence over a `NOT_STARTED` step.
WP040 does not reinterpret execution status, reassess evidence, synthesize a
progress update, mutate or advance a Run, re-control, retry, recover, or
continue the Plan.

In the current vocabulary, a **Tool** is a directly invocable technical
capability. A **Skill** is a higher-level procedure that may compose tools in a
future subsystem. An **Action** is a concrete operation against the environment
that a tool may use. WP003 implements only the capability/tool runtime; it does
not add skill orchestration, an Action Runtime, permissions, or plugins.

The modules below define the current foundation and future boundaries:

- `iris.core`: portable core behavior, `Request`, and system information;
- `iris.router`: routing contracts, decision models, and deterministic rules;
- `iris.dispatch`: coordination boundary between routes, CLI behavior, and the
  capability runtime;
- `iris.capabilities`: executable capability identity, contracts, registry,
  runtime, structured results, and built-in tool composition;
- `iris.intelligence`: provider-independent inference requests, model identity,
  provider contracts, explicit registry, runtime, structured results, and
  deterministic intelligence-routing boundary;
- `iris.intelligence.routing`: immutable need/resource/route models, candidate
  resolution, routing-policy contract, and initial deterministic policy;
- `iris.intelligence.providers`: optional concrete adapters, currently Ollama;
- `iris.skills`: `Skill` contract for named capabilities or procedures;
- `iris.actions`: `Action` contract for concrete environment operations;
- `iris.memory`: IRIS-owned evidence models, `MemoryService`, backend-independent
  `MemoryStore`, SQLite persistence and the legacy WP001 `Memory` protocol;
- `iris.context`: ephemeral candidates and evidence, deterministic bounded
  selection, WorkSubject-scoped snapshots and an explicit read-only Memory
  source;
- `iris.orchestrator`: immutable subject/context binding, handling needs,
  explicit availability, deterministic single-step policy, currentness
  validation, and traceable coordination decisions;
- `iris.planning`: immutable goals and plans, provider-independent Planner
  contract, deterministic rule templates, typed outcomes and DAG validation;
- `iris.plan_runs`: immutable runtime-state revisions, explicit atomic updates,
  deterministic reduction, evidence/blocker validation, derived availability
  and structural Run conditions;
- `iris.plan_control`: immutable one-shot control decisions, explicit READY-step
  selection policy, revision-current validation, and no execution or mutation;
- `iris.plan_handling`: immutable one-shot preparation from a current selected
  PlanStep to an existing HandlingNeed, with explicit abstention and no
  orchestration, activation, or execution;
- `iris.work_identity`: immutable typed Request and PlanStep operational
  identities, canonical subject IDs, optional root-cause references, and pure
  adapters without runtime or state semantics;
- `iris.execution`: WorkSubject-scoped immutable execution models, deterministic
  coordinator, and adapters to the established system, Memory, Capability, and
  Intelligence boundaries.
- `iris.execution_observation`: side-effect-free PLAN_STEP ExecutionResult
  adaptation into raw PlanObservation evidence, with local duplicate-evidence
  rejection and no outcome assessment or PlanRun mutation.
- `iris.outcome_assessment`: replaceable PlanStep evidence evaluators and
  immutable epistemic assessments, with no progress policy or state mutation.
- `iris.step_progress_transition`: assessment-applicability validation,
  replaceable transition policy, immutable operational decisions, and strict
  decision-currentness validation without progress mutation.
- `iris.step_progress_update_synthesis`: one-shot binding of a current
  actionable transition decision and its matching assessment into the existing
  `StepProgressUpdate`, without reducer invocation or Run mutation.
- `iris.plan_run_advancement`: bounded composition of one StepProgressUpdate,
  one new immutable PlanRun revision, and one current post-mutation
  ControlDecision, without persistence or continuation.
- `iris.plan_step_execution_binding`: exact-current-revision binding of a
  selected and prepared PlanStep to an existing PLAN_STEP ExecutionRequest,
  without activation, handler admission, or execution.
- `iris.plan_step_execution_result_recording`: exact-base composition of one
  WP025 execution result, one canonical execution observation, one
  `RecordObservationUpdate`, and one immutable next Run revision, without
  outcome assessment, StepProgress mutation, or continuation.
- `iris.plan_step_evidence_assessment`: read-only composition of one explicit
  Run revision's complete Step-scoped observation basis with one existing
  `StepOutcomeEvaluator`, returning one validated `StepOutcomeAssessment` and
  stopping before transition policy or mutation.
- `iris.plan_step_evidence_transition`: read-only composition of WP027 complete
  evidence assessment with one WP021 transition decision and canonical decision
  currentness validation, preserving both artifacts without update synthesis,
  Run mutation, or continuation.
- `iris.plan_step_progress_update_preparation`: bounded WP028-to-WP022
  composition that preserves the assessment and transition decision and
  optionally prepares one inert `StepProgressUpdate`, without Run mutation or
  advancement.
- `iris.plan_step_progress_advancement`: bounded WP029-to-WP023 composition
  that conditionally derives one immutable successor Run and preserves its one
  fresh inert ControlDecision, without execution or continuation.
- `iris.plan_step_handling_preparation`: bounded WP030-to-WP014 composition
  that optionally prepares the exact fresh selected PlanStep's declared
  handling without specification resolution, orchestration, execution, or
  continuation.
- `iris.plan_step_work_subject_materialization`: bounded WP031-to-WP015
  composition that optionally materializes the exact fresh selected PlanStep's
  stable work identity against the successor Run, without origin synthesis,
  Context, orchestration, execution, or continuation.
- `iris.plan_step_context_materialization`: bounded WP032-to-WP016 composition
  that optionally builds one exact WorkSubject-owned ContextSnapshot from
  explicit caller inputs, without discovery, retrieval, orchestration,
  execution, persistence, or continuation.
- `iris.plan_step_orchestration`: bounded WP033-to-WP017 composition that
  optionally produces one exact Context-bound OrchestrationDecision for
  canonically prepared selected-step handling, without need enrichment,
  handler discovery, execution, mutation, retry, or continuation.
- `iris.plan_step_execution_request_materialization`: bounded WP034-to-WP018
  composition that optionally materializes one exact ExecutionRequest from
  explicit execution operands, including terminal requests, without binding,
  activation, execution, mutation, retry, persistence, or continuation.
- `iris.plan_step_execution_binding_composition`: bounded WP035-to-WP024
  composition that optionally binds the exact canonical request to the fresh
  selected PlanStep at the successor pre-activation revision, without
  admission, activation, handler resolution, execution, retry, persistence, or
  continuation.
- `iris.plan_step_execution_start_composition`: bounded WP036-to-WP025
  composition that optionally starts the exact bound selected PlanStep through
  an explicitly configured runtime, without result recording, assessment,
  retry, recovery, persistence, or continuation.
- `iris.plan_step_execution_result_recording_composition`: bounded
  WP037-to-WP026 composition that optionally records one normal start result
  against its exact canonical Run, without interpreting execution status,
  changing StepProgress, assessing evidence, retrying, or continuing.
- `iris.plan_step_execution_evidence_assessment_composition`: bounded
  WP038-to-WP027 composition that optionally assesses the exact recorded step's
  complete evidence basis on the exact recorded Run while preserving the prior
  assessment separately, without transition policy, mutation, retry, recovery,
  or continuation.
- `iris.plan_step_execution_transition_decision_composition`: bounded
  WP039-to-WP021 composition that optionally decides against the exact
  post-recording assessment and recorded Run while preserving the earlier
  assessment/decision pair, without reassessment, update synthesis, mutation,
  re-control, retry, recovery, or continuation.

The contracts use Python protocols so later implementations can remain modular
without requiring inheritance from framework-specific base classes.

## Architecture continuity

The [latest Architecture Continuity Checkpoint](docs/architecture/continuity/LATEST.md)
records the system's architectural state, authority boundaries, and forward
hypotheses at a specific canonical commit.

## Configuration and secrets

Local Ollama requires no secret. Its endpoint, provider identity, and timeout
are constructor arguments rather than machine-specific committed configuration.
Future provider credentials must remain outside version control, supplied
through the environment or ignored local files. Common `.env`, credential,
certificate, and key files are excluded by `.gitignore`; a sanitized
`.env.example` may be committed when configuration is introduced.
