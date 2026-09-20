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
- a separate command-dispatch boundary that executes routing decisions;
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

The current request path is:

```text
Raw terminal input → Request → DeterministicRouter → RouteDecision
                   → CommandDispatcher → CLI output
```

The Router only decides a target and records a reason. It does not execute
system information, actions, skills, or other effects. `CommandDispatcher` is
the minimal execution boundary for the commands that exist today; it is not an
Action Runtime.

The modules below define the current foundation and future boundaries:

- `iris.core`: portable core behavior, `Request`, and system information;
- `iris.router`: routing contracts, decision models, and deterministic rules;
- `iris.dispatch`: execution boundary for current routed CLI commands;
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
