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
- typed architectural contracts for future skills, actions, and memory;
- automated tests for the existing behavior and contracts.

IRIS does **not** bundle a model or connect one automatically. It also does not
include a Brain Router, fallback, agent loop, autonomous planning, semantic
memory, voice, vision, or complex system actions. Ollama is an optional,
replaceable backend; it is not IRIS or IRIS's identity.

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

WP005 implements `OllamaProvider` behind this boundary. Ollama protocol details
remain inside the adapter; they do not become IRIS core types. Discovery
failures use specific operational exceptions because `list_models()` has no
result envelope. Inference failures use a structured failed
`IntelligenceResult`. Unexpected programming errors and contract violations
remain visible.

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
  provider contracts, explicit registry, runtime, and structured results;
- `iris.intelligence.providers`: optional concrete adapters, currently Ollama;
- `iris.skills`: `Skill` contract for named capabilities or procedures;
- `iris.actions`: `Action` contract for concrete environment operations;
- `iris.memory`: model-independent `Memory` storage contract owned by IRIS.

The contracts use Python protocols so later implementations can remain modular
without requiring inheritance from framework-specific base classes.

## Configuration and secrets

Local Ollama requires no secret. Its endpoint, provider identity, and timeout
are constructor arguments rather than machine-specific committed configuration.
Future provider credentials must remain outside version control, supplied
through the environment or ignored local files. Common `.env`, credential,
certificate, and key files are excluded by `.gitignore`; a sanitized
`.env.example` may be committed when configuration is introduced.
