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
- typed architectural contracts for future skills, actions, and memory;
- automated tests for the existing behavior and contracts.

IRIS does **not** currently include an LLM, agent loop, autonomous planning,
semantic memory, provider integration, voice, vision, or complex system actions.

## Platform and product direction

IRIS 0.1 is **Windows-first, core-portable**. Windows is the initial supported
product target, while core code avoids unnecessary Windows coupling and degrades
gracefully when an operating-system metric is unavailable. Full Linux and macOS
support is not claimed.

The long-term direction is **local-first, cloud-augmented**. Future local and
cloud models will be interchangeable resources used by IRIS; identity, context,
memory, routing, permissions, and state belong conceptually to IRIS itself.
Those systems have not been implemented yet.

## Requirements

- Python 3.11 or newer
- Windows for the officially targeted 0.1 experience

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

## Tests

```powershell
pytest
```

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
- `iris.skills`: `Skill` contract for named capabilities or procedures;
- `iris.actions`: `Action` contract for concrete environment operations;
- `iris.memory`: model-independent `Memory` storage contract owned by IRIS.

The contracts use Python protocols so later implementations can remain modular
without requiring inheritance from framework-specific base classes.

## Configuration and secrets

IRIS has no runtime secrets or provider configuration today. Future secrets must
remain outside version control, supplied through the environment or ignored
local files. Common `.env`, credential, certificate, and key files are excluded
by `.gitignore`; a sanitized `.env.example` may be committed when configuration
is introduced.
