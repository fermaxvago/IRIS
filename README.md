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
- request-scoped, bounded Context snapshots built deterministically from
  explicitly supplied, traceable evidence;
- a deterministic single-step Orchestrator that selects a subsystem through
  structured, traceable decisions;
- typed architectural contracts for future skills and actions;
- automated tests for the existing behavior and contracts.

IRIS does **not** bundle a model or connect one automatically. It also does not
include execution coordination, fallback after inference failure, an iterative
agent loop, autonomous planning, semantic retrieval, voice, vision, or complex
system actions. Ollama is an optional, replaceable backend; it is not IRIS or
IRIS's identity. The intelligence router is deterministic and specialized; it
is not an LLM-based Brain Router.

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

`iris.context` constructs an ephemeral `ContextSnapshot` for an explicit
request ID from caller-supplied `ContextCandidate` values. Each candidate has a
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

Context is selected evidence for the current request: it is separate from
persistent Memory, Session continuity and external State. Building a snapshot
does not write Memory, invoke providers or tools, choose actions, plan, grant
authorization or construct an LLM prompt. The Orchestrator consumes snapshots;
model Context Assembly remains a separate future boundary.

## Orchestrator foundation

`iris.orchestrator` implements one request-scoped `observe → decide → stop`
step. An `OrchestrationInput` links one `Request` to its exact
`ContextSnapshot`, explicit `HandlingNeed` values and caller-supplied
`HandlerAvailability`. Mismatched request/context identities fail before a
decision can be made. Availability is never discovered through the network,
filesystem, provider registries or device state.

`DeterministicOrchestrationPolicy` produces exactly one immutable,
provider-neutral `OrchestrationDecision`. Targets are `SYSTEM`, `MEMORY`,
`CAPABILITY`, `INTELLIGENCE`, `CLARIFY` and `UNSATISFIED`. Structured reason
codes, need IDs, snapshot identity and context issue references provide
traceability without storing private model reasoning. The existing deterministic
Router can supply a recognized system route; Intelligence needs are preserved
for the separate Intelligence Router; capability IDs and Memory operation
descriptors remain inputs for their established subsystems.

Context ambiguity, conflict or missing information blocks a decision only when
the caller explicitly links that issue to the current need. Unrelated partial or
conflicted Context does not force clarification. An unavailable required handler
produces `UNSATISFIED`; several needs produce the explicit
`COMPOSITE_HANDLING_REQUIRED` result because this version performs one step.

The Orchestrator coordinates IRIS; it does not replace the systems it
coordinates. It does not execute capabilities, access Memory, invoke
Intelligence, choose providers/models, infer authorization, plan, retry or
construct prompts. Execution coordination and iterative cognitive loops remain
future work.

Memory tells IRIS what has been preserved. Context tells IRIS what is relevant
now. The Orchestrator decides which subsystem should handle the next step.
Execution comes later.

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
  selection, request-scoped snapshots and an explicit read-only Memory source;
- `iris.orchestrator`: immutable handling needs, explicit availability,
  deterministic single-step policy and traceable coordination decisions.

The contracts use Python protocols so later implementations can remain modular
without requiring inheritance from framework-specific base classes.

## Configuration and secrets

Local Ollama requires no secret. Its endpoint, provider identity, and timeout
are constructor arguments rather than machine-specific committed configuration.
Future provider credentials must remain outside version control, supplied
through the environment or ignored local files. Common `.env`, credential,
certificate, and key files are excluded by `.gitignore`; a sanitized
`.env.example` may be committed when configuration is introduced.
