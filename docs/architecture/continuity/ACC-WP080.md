# IRIS — ARCHITECTURE CONTINUITY CHECKPOINT — ACC-WP080

**Represented canonical `main`:** `69dd93636f0e5d3fe3f7610781122a27c9df9c96`

**Represented Git tree:** `34dfdbfa7d82a6a975aa310fdd9e6639a4a4df6b`

**Checkpoint date:** 2026-11-15

**Previous checkpoint:** [ACC-WP075](ACC-WP075.md)

**Succession foundation:** [ARCHITECT-SUCCESSION-FOUNDATIONS](ARCHITECT-SUCCESSION-FOUNDATIONS.md)

## 0. How to read this checkpoint

This is an immutable historical photograph of IRIS **after WP080's canonical
merge, including the WP080.1 correction, and before this documentation
commit**. Publication of this file and the accompanying `LATEST.md` update is
a later Git operation and is not part of the represented state.

- **FROZEN** means an inherited architectural or authority boundary.
- **CURRENT** means a fact verified at the represented canonical commit.
- **FORWARD** means a possible risk or question. It grants no implementation
  authority.

Canonical Git objects and repository source outrank PR narrative. Tests
establish only exercised behavior. CI establishes results for its exact
evaluated revision and environment; it is not physical deployment evidence.
ACC documentation preserves knowledge continuity. It does not transfer
architectural, execution, publication, merge, or successor-work authority.

# PART I — CANONICAL ANCHOR AND INTEGRATION LINEAGE

## 1. Represented post-WP080 state

**CURRENT:** canonical `main` is
`69dd93636f0e5d3fe3f7610781122a27c9df9c96`, with tree
`34dfdbfa7d82a6a975aa310fdd9e6639a4a4df6b`. The commit is the canonical
merge of [PR #91](https://github.com/fermaxvago/IRIS/pull/91),
`WP080 — Bounded Explicit Planning Context Submission`, and has these
ordered parents:

1. `e51893a5366df8a64dc620aadb52b44c63bb180e` — canonical post-WP079
   `main`.
2. `a16d042685711d687cf990aba314a7c5518363ad` — final WP080/WP080.1
   implementation head.

The second parent and merge have the same tree, `34dfdbfa...`. Their
merge-base is the first parent, `e51893a...`.

WP080's branch contains two ordered implementation commits:

| Commit | Parent | Tree | Role |
| --- | --- | --- | --- |
| `abbcd910f4602bd623cafc754011f47b8500a8ae` | `e51893a5366df8a64dc620aadb52b44c63bb180e` | `64767e26f3c4391444a3942bdb7a3aa71143b11b` | Original WP080 implementation |
| `a16d042685711d687cf990aba314a7c5518363ad` | `abbcd910f4602bd623cafc754011f47b8500a8ae` | `34dfdbfa7d82a6a975aa310fdd9e6639a4a4df6b` | WP080.1 corrective continuation |

WP080.1 is part of PR #91. It is not an independent PR or merge.

## 2. Verified lineage from ACC-WP075 publication through WP080

Each stage below is a merged PR with exactly two merge parents: canonical base
first and final implementation/documentation head second. For every row, the
merge-base between the head and canonical base equals that base, and the final
head tree equals the canonical merge tree.

| Stage and verified PR title | Canonical base | Final head | Canonical merge | Tree |
| --- | --- | --- | --- | --- |
| [ACC-WP075 #86](https://github.com/fermaxvago/IRIS/pull/86) — Architecture Continuity Checkpoint | `7692fef6d1d3638c770986489b26d088b94d4cd1` | `eb17956afd49dd2f39ad435dea39866968de2e52` | `6c3da0e55bfc0843b09a9b0cfd83577c3d9d7279` | `b6c767bb64c9cc878042c5aad01dc1caaf5f8269` |
| [WP076 #87](https://github.com/fermaxvago/IRIS/pull/87) — Bounded Planning Strategy Discovery and Selection | `6c3da0e55bfc0843b09a9b0cfd83577c3d9d7279` | `a2a4244aab6f1f0bb5aa6c892f9d538af845ad8a` | `e398f5a42a0155eadda687c8cb768b472641f37e` | `9f005cdedf490d7092e2a5a3e912d3cca116e5c5` |
| [WP077 #88](https://github.com/fermaxvago/IRIS/pull/88) — Planning Context Requirement Disclosure and Result Integrity | `e398f5a42a0155eadda687c8cb768b472641f37e` | `883933a25fa6abd8e7af73707288b3a54828dfc9` | `e6d3c490bbcb7f0de36eae8733becaadd30b770d` | `a67c1b1917e456a7b796dc0730648d27c45f16ca` |
| [WP078 #89](https://github.com/fermaxvago/IRIS/pull/89) — Bounded Structured Planning Result Output | `e6d3c490bbcb7f0de36eae8733becaadd30b770d` | `8795efbadaf312bbebed6e6e42ca567dce496426` | `e332b79f1f7f4828fe737e989e5c890ae9b62647` | `a780e3787f81ea857a534f1076040ac1af997d53` |
| [WP079 #90](https://github.com/fermaxvago/IRIS/pull/90) — Bounded Structured Planning Strategy Discovery | `e332b79f1f7f4828fe737e989e5c890ae9b62647` | `b66de56c6cb57848496d022446d6e92808bb5b34` | `e51893a5366df8a64dc620aadb52b44c63bb180e` | `656a7694af2061518c1c067e4dd73350744191a7` |
| [WP080 #91](https://github.com/fermaxvago/IRIS/pull/91) — Bounded Explicit Planning Context Submission | `e51893a5366df8a64dc620aadb52b44c63bb180e` | `a16d042685711d687cf990aba314a7c5518363ad` | `69dd93636f0e5d3fe3f7610781122a27c9df9c96` | `34dfdbfa7d82a6a975aa310fdd9e6639a4a4df6b` |

`ACC-WP075` represents post-WP075 commit `7692fef...`; its later publication
merge is `6c3da0e...`. Likewise, this ACC represents `69dd936...`; its future
documentation commit and merge are intentionally excluded.

```text
implementation commit != pull request != synthetic PR merge
implementation tree equality != commit identity
canonical merge != later ACC publication
represented historical state != future live main
```

# PART II — CAUSAL ARCHITECTURAL EVOLUTION

## 3. Starting point inherited from ACC-WP075

**FROZEN:** [ACC-WP075](ACC-WP075.md) established the first explicit
`planificar --objetivo` path into the existing deterministic Planning
contracts and exactly one built-in conceptual study-session strategy. That path
constructed traceable `Request`, `Goal`, and `PlanningRequest` values,
evaluated one `PlanningResult`, rendered it, and stopped.

It did not create a `PlanRun`, activate handling, invoke Execution, access
Memory, call Ollama, or treat a conceptual Plan as completed work. WP076–WP080
extend the input and presentation surface around that same Planning authority;
they do not bridge Planning to execution.

## 4. WP076 — one canonical strategy manifest

**CURRENT:** [`strategy_manifest.py`](../../../iris/planning/strategy_manifest.py)
defines validated `StrategyDescriptor` and `StrategyManifest` values.
The manifest is the single production source for discovery, exact strategy-ID
selection, and the rule set supplied to `DeterministicPlanner`.

The CLI gained:

- `planificar --listar` for deterministic human-readable discovery;
- `planificar --estrategia estudio` for exact-ID selection.

Strategy IDs are exact lowercase ASCII identifiers. Manifest construction
rejects invalid descriptors, duplicate IDs, and duplicate normalized
objectives. Selection records literal input `estudio` in the CLI `Request`
and derives the `Goal.objective` from the selected rule. This preserves:

```text
literal user selection
  -> Request
  -> validated descriptor
  -> canonical PlanningRule objective
  -> Goal
  -> PlanningRequest
  -> PlanningResult
```

The sole production entry remains `estudio`, backed by the four-step
[`study_session_rule`](../../../iris/planning/study_strategy.py). Discovery
does not authorize selection, and selection does not authorize execution.

## 5. WP077 — requirement disclosure and context-aware integrity

**CURRENT:** `planificar --requisitos estudio` reads the selected rule's
canonical `required_context` without constructing Planning state or calling
`Planner.plan()`. The current production rule declares no requirements, so
the command truthfully reports none.

WP077 also corrected selected-result validation to calculate actual missing
requirements from the rule and supplied `ContextSnapshot`, using exact
`(kind, key, scope)` identity. It distinguishes no requirements, all missing,
partially satisfied, and fully satisfied requirements. A resolved snapshot is
not assumed to satisfy a rule merely because its resolution status is
`RESOLVED`.

The shared deterministic precedence remains:

1. conflicting constraints;
2. exact normalized objective lookup;
3. missing required context;
4. no decomposition or canonical Plan creation.

Context presence does not establish truth, verification, fitness, or execution
authority.

## 6. WP078 — public Planning-result JSON 1.0

**CURRENT:** `--formato json` is available for result-producing
`--objetivo` and `--estrategia` modes. The bounded serializer in
[`public_json.py`](../../../iris/planning/public_json.py) emits exactly one
complete document only after the canonical result and public structure have
been validated:

```text
format_version
input
planning_request
planning_result
```

The input object distinguishes literal objective input from explicit
strategy-ID selection. Existing model serializers remain authoritative, while
field allowlists prevent later internal fields from silently expanding public
JSON 1.0. Valid abstentions remain successful evaluations with exit code 0;
CLI selection errors use exit code 2; contract or serialization failures use
exit code 1 and emit no partial JSON.

The document carries a conceptual Planning result. It is not an execution
request, execution status, or downstream authorization.

## 7. WP079 — public strategy metadata JSON 1.0

**CURRENT:** [`discovery_json.py`](../../../iris/planning/discovery_json.py)
adds two separate read-only metadata documents:

- `planificar --listar --formato json` returns
  `strategy_catalog / 1.0`;
- `planificar --requisitos estudio --formato json` returns
  `strategy_requirements / 1.0`.

Both derive directly from a deeply revalidated `StrategyManifest`, preserve
canonical ordering and exact descriptor or requirement values, serialize the
whole document before emission, and stop. They do not construct a
`Request`, `Goal`, `PlanningRequest`, `PlanningResult`, or call
`DeterministicPlanner.plan()`.

Declared requirements are strategy metadata. They are not missing-context
results, currently available values, verification claims, or permission to
acquire context.

## 8. WP080 — explicit bounded caller context

**CURRENT:** WP080 adds one explicit route:

```text
iris planificar --estrategia ID --contexto-stdin --formato json
```

The route is accepted only for an exact registered strategy that declares at
least one requirement. All manifest and CLI checks possible without input occur
before stdin is read. [`context_stdin.py`](../../../iris/planning/context_stdin.py)
then enforces:

- strict UTF-8 and exactly one JSON document;
- exact top-level, item, and scope fields;
- at most 32,768 input bytes, 1–16 items, and no unbounded read;
- exact declared `(kind, key, MemoryScope)` identities and no duplicates;
- scalar-only values: bounded integers, finite floats, booleans, or nonblank
  strings of at most 1,024 Unicode code points;
- no caller-supplied identities, evidence status, relevance, freshness, or
  eligibility.

Accepted values become canonical `ContextCandidate` values with
`EvidenceSource.CALLER`, request identity as evidence reference,
`EpistemicStatus.UNKNOWN`, `Relevance.REQUIRED`, `Freshness.UNKNOWN`, and
`eligible=True`. The existing `ContextEngine` constructs one ephemeral,
request-owned `ContextSnapshot`. WP080 validates cardinality, identity,
scope, exact scalar value and type, evidence, budget, ownership, conflicts,
exclusions, and UTC chronology before constructing the `PlanningRequest`.

One deterministic Planning evaluation then reuses WP077 result integrity and
WP078 JSON. The public document may expose `context_snapshot_id`; it does not
expose submitted values, candidate metadata, or evidence contents.

Partial submissions are permitted, but every supplied item must be declared.
The planner may therefore return exact missing requirements. Context presence
still does not semantically interpret or verify a value.

## 9. Composition and stopping boundary

```text
StrategyManifest
  -> discovery or exact strategy selection
  -> optional declared-requirement inspection
  -> strict caller JSON matched to that selected rule
  -> Request + Goal with request-bound provenance
  -> CALLER/UNKNOWN ContextCandidates
  -> ContextEngine
  -> ephemeral request-owned ContextSnapshot
  -> PlanningRequest
  -> DeterministicPlanner.plan() exactly once
  -> validated PlanningResult
  -> bounded text or public JSON
  -> STOP
```

The chain stops before `PlanRun`, handling activation, binding, Execution,
capabilities, Memory persistence, provider inference, network services, or
automatic continuation.

**CURRENT limitation:** the only production strategy, `estudio`, declares no
context requirements. Therefore the production
`--estrategia estudio --contexto-stdin --formato json` combination is
rejected before stdin is read. Positive context-to-Planning behavior is
demonstrated with synthetic injected test strategies; this is not production
personalization.

# PART III — WP080.1 CORRECTIVE HISTORY

## 10. Findings and verified closure

The original WP080 commit passed its then-current tests and CI, but independent
review identified three bounded gaps:

| Finding | Original defect or evidence gap | Closure at `a16d042...` |
| --- | --- | --- |
| AUD080-01 | Python `float()` could convert a nonzero decimal such as `1e-9999` to `0.0` silently. | The parser uses standard-library `Decimal` to distinguish mathematical zero and rejects nonzero-to-zero underflow. Legitimate positive or negative zero and representable subnormals remain accepted. |
| AUD080-02 | Dataclass/scalar equality treats `-0.0 == 0.0`, so a ContextEngine sign mutation could escape integrity checks. | Snapshot validation compares float values through exact `float.hex()` representation after type equality. Adversarial tests reject both signed-zero mutation directions before Planning. |
| AUD080-03 | Real subprocess tests covered production rejection but not a successful stdin-to-Planning-to-JSON path. | A child-process test loads the installed package entrypoint, injects a synthetic manifest through the existing programmatic seam, submits valid stdin, verifies a successful Planning result and snapshot ID, and confirms value privacy. |

The corrective code is visible in
[`context_stdin.py`](../../../iris/planning/context_stdin.py); adversarial and
subprocess evidence is in
[`test_planning_context_stdin.py`](../../../tests/test_planning_context_stdin.py).
The final canonical source, test suite, PR CI, and post-merge CI all contain the
correction. No production strategy, public schema, Planning authority, or
runtime dependency was added by WP080.1.

# PART IV — FROZEN RESPONSIBILITY AND AUTHORITY BOUNDARIES

## 11. Core responsibility map

| Owner | Current responsibility | Does not establish or grant |
| --- | --- | --- |
| `StrategyManifest` | Static validated descriptors, exact IDs, canonical rules and deterministic ordering | Dynamic plugins, external discovery, strategy recommendation, or execution approval |
| Explicit Planning CLI | Mode validation, traceable Request/Goal construction, one Planning evaluation, bounded output | Authenticated human identity, conversational intent, arbitrary Planning, or operational permission |
| `PlanningRule` / `DeterministicPlanner` | Exact normalized objective matching, requirement presence, deterministic abstention or conceptual decomposition | Semantic interpretation, context acquisition, PlanRun creation, or task completion |
| `ContextEngine` | Bounded candidate selection into an immutable request-owned snapshot | Factual verification, Memory persistence, Planning sufficiency by status alone, or execution authority |
| WP078 serializer | Versioned result representation with bounded provenance and privacy | A second Planning model, execution status, or permission for a consumer |
| WP079 serializers | Read-only catalog and declared-requirement representations | Planning evaluation, current context, missing-context calculation, or acquisition authority |
| `iris.plan_runs` and control components | Programmatic immutable Run state, revision and selection contracts | Implicit creation from a PlanningResult or CLI accessibility |
| Execution and handling components | Separate binding, activation and invocation contracts | Authority inferred from strategy discovery, context submission, Plan, or handler metadata |
| Memory subsystem | Explicit storage and retrieval contracts | Automatic persistence of caller context, plans, or CLI state |
| Conversational resource paths | Existing separate observation and disclosure approvals | Planning authority or consent reuse from caller context |

## 12. FROZEN distinctions

```text
strategy discovery          != strategy authorization
strategy selection          != arbitrary Planning
caller context              != verified factual knowledge
ContextSnapshot             != persistent Memory
PlanningRequest             != PlanningResult
PlanningResult              != PlanRun
Plan                        != execution
required handling metadata  != handler activation
successful CLI evaluation   != completed real-world task
CI success                  != physical deployment validation
```

Request provenance `source="cli"` and `actor=None` do not authenticate a
human. A caller-supplied value has `CALLER` provenance and `UNKNOWN`
epistemic status. Scope identifies the declared requirement and context owner;
it is not access control.

WP076–WP080 did not alter the independent human approvals retained by the
resource-consultation and comparison paths described in
[ACC-WP075](ACC-WP075.md). Planning context input is explicit data submission,
not observation approval, contextual-disclosure approval, capability
authorization, or execution consent.

# PART V — EVIDENCE LEDGER

## 13. GitHub Actions and synthetic checkout identities

For each PR run, GitHub Actions checked out a synthetic merge commit distinct
from both implementation head and canonical merge. Run metadata and job logs
were checked for event, head/base identity, completed status and success.
Post-merge runs were checked as `push` events on the exact canonical merge.

| Stage | PR CI: head / synthetic checkout / result | Post-merge CI: canonical head / result |
| --- | --- | --- |
| ACC-WP075 | [43111679195](https://github.com/fermaxvago/IRIS/actions/runs/43111679195): `eb17956...` / `e0b5a479...` / success, 2,816 passed, 1 skipped | [43114090619](https://github.com/fermaxvago/IRIS/actions/runs/43114090619): `6c3da0e...` / `push`, success |
| WP076 | [43148411167](https://github.com/fermaxvago/IRIS/actions/runs/43148411167): `a2a4244...` / `9f5e1c00...` / success, 2,844 passed, 1 skipped | [43245095166](https://github.com/fermaxvago/IRIS/actions/runs/43245095166): `e398f5a...` / `push`, success |
| WP077 | [43287296482](https://github.com/fermaxvago/IRIS/actions/runs/43287296482): `883933a...` / `445829a9...` / success, 2,876 passed, 1 skipped | [43289849239](https://github.com/fermaxvago/IRIS/actions/runs/43289849239): `e6d3c49...` / `push`, success |
| WP078 | [43611451465](https://github.com/fermaxvago/IRIS/actions/runs/43611451465): `8795efb...` / `c1f9a80d...` / success, 2,918 passed, 1 skipped | [43640219058](https://github.com/fermaxvago/IRIS/actions/runs/43640219058): `e332b79...` / `push`, success |
| WP079 | [43654403019](https://github.com/fermaxvago/IRIS/actions/runs/43654403019): `b66de56...` / `6cb875b6...` / success, 2,953 passed, 1 skipped | [43654924848](https://github.com/fermaxvago/IRIS/actions/runs/43654924848): `e51893a...` / `push`, success |
| WP080/WP080.1 | [43739912660](https://github.com/fermaxvago/IRIS/actions/runs/43739912660): `a16d042...` / `d2337af4...` / success, 3,041 passed, 1 skipped | [43740404512](https://github.com/fermaxvago/IRIS/actions/runs/43740404512): `69dd936...` / `push`, success |

## 14. Exact WP080 validation evidence

The post-merge quality job evaluated checkout
`69dd93636f0e5d3fe3f7610781122a27c9df9c96`. Its logs report:

- **3,041 passed, 1 skipped**;
- Ruff lint passed;
- Ruff format reported **365 files already formatted**;
- strict mypy passed for **269 source files**;
- wheel and source distribution built successfully.

The skipped test is
`tests/integration/test_ollama_integration.py`, which requires explicit
`IRIS_RUN_OLLAMA_INTEGRATION=1` and a real Ollama server. It was skipped, not
passed.

The successful subprocess test proves the bounded package entrypoint can carry
synthetic declared context through validation, `ContextEngine`, one Planning
evaluation, and private WP078 JSON output. It does not prove that the production
`estudio` rule is personalized, because that rule declares no required
context. It also does not prove live physical Windows, Ollama, hardware,
network, or deployment readiness.

## 15. Source and test evidence ledger

| Evidence | Demonstrates | Does not demonstrate |
| --- | --- | --- |
| [Strategy manifest](../../../iris/planning/strategy_manifest.py) and [manifest tests](../../../tests/test_planning_strategy_manifest.py) | One static production manifest, exact selection, provenance and no operational calls | Dynamic strategy loading or arbitrary Planning |
| [Deterministic planner](../../../iris/planning/deterministic.py) and [requirement tests](../../../tests/test_planning_context_requirements.py) | Exact requirement identity, missing-context calculation and result integrity | Truth or semantic adequacy of values |
| [WP078 serializer](../../../iris/planning/public_json.py) and [JSON tests](../../../tests/test_planning_json_output.py) | Bounded result JSON, provenance, shape validation and complete emission | Execution interface or private context disclosure |
| [WP079 serializers](../../../iris/planning/discovery_json.py) and [discovery tests](../../../tests/test_planning_discovery_json.py) | Canonical catalog/requirements metadata and no Planning evaluation | Current availability or satisfaction of requirements |
| [WP080 input boundary](../../../iris/planning/context_stdin.py) and [stdin tests](../../../tests/test_planning_context_stdin.py) | Bounded strict input, caller provenance, snapshot integrity, privacy, float fidelity and subprocess path | Production personalization, semantic verification, persistence or execution |
| [CLI integration](../../../iris/__main__.py) | Explicit mode precedence, request construction, one result path and bounded errors | Conversational Planning or automatic continuation |

# PART VI — CURRENT LIMITATIONS, RISKS AND FRONTIER

## 16. CONFIRMED limitations

1. The production manifest contains exactly one strategy, `estudio`.
2. `estudio` is a generic four-step conceptual study-session template with no
   declared context requirements.
3. No current production strategy can take the positive
   `--contexto-stdin` path; that path is positively exercised with synthetic
   test strategies only.
4. Context matching validates identity and presence, not truth, timeliness,
   semantic fitness, or personalization quality.
5. Caller context is ephemeral and request-owned. It is not written to Memory,
   persisted, or exposed in public JSON.
6. Public JSON contracts are bounded presentation interfaces; they carry no
   authority for downstream action.
7. Planning remains separate from chat and does not create a `PlanRun`,
   invoke handling, bind an execution request, or execute a step.
8. No automatic context acquisition, Memory lookup, model inference, network
   discovery, dynamic strategy registration, retry, scheduling, or background
   service was added.
9. Existing conversational CPU/RAM consultation and comparison retain their
   separate consent, session, disclosure, and local-observation boundaries.
10. CI is Ubuntu/Python 3.11 automated evidence. It is not current physical
    Windows/Ollama or real-device verification.
11. This checkpoint's documentation commit and PR CI are outside the represented
    canonical state.

## 17. POTENTIAL risks, not demonstrated defects

- A future strategy with real context requirements could invite overclaiming
  personalization or truth from presence-only matching.
- Public JSON evolution could accidentally expose internal fields unless the
  existing allowlists and compatibility review are preserved.
- New scalar types or transformations could create fidelity risks similar to
  the corrected float cases.
- A future conversational entry could blur recognition, confirmation,
  Planning, and execution permission.
- Users or downstream programs could misread conceptual steps as completed or
  authorized work.

These are review triggers. They are not open defects established by this
checkpoint and do not authorize corrective or feature work.

## 18. FORWARD questions (non-authorizing)

- What production need would justify a strategy with declared context, and what
  evidence would prevent presence from being misrepresented as truth?
- What compatibility process should govern a future JSON contract revision?
- If context acquisition is ever proposed, which source, consent, provenance,
  freshness, privacy, and persistence authorities must remain separate?
- If a PlanningResult is ever proposed as input to operational work, how are
  PlanRun creation, currentness, selection, binding, authorization, handler
  activation, and execution independently gated?
- Which physical Windows/Ollama scenarios are required before any deployment
  readiness claim?

Each question requires separate architectural authorization. This document
does not authorize WP081 or any implementation.

# PART VII — CONTINUITY AND RECOVERY

## 19. Recovery procedure for a future Architect

1. Fetch live `main`; verify its SHA and tree before treating this checkpoint
   as current.
2. Read `LATEST.md` and verify the latest immutable ACC rather than assuming
   ACC-WP080 remains current.
3. Verify represented commit `69dd936...`, tree `34dfdbfa...`, ordered
   parents, PR #91, two implementation commits, and post-merge CI
   `43740404512`.
4. Distinguish each implementation head, synthetic PR checkout, canonical
   merge, and later ACC documentation merge.
5. Read [ACC-WP075](ACC-WP075.md), [ACC-WP070](ACC-WP070.md), and
   [ACC-WP065](ACC-WP065.md) for inherited Planning, conversation, resource,
   consent, session, Memory, PlanRun, and Execution boundaries.
6. Reconstruct current ownership from source: manifest, deterministic planner,
   context models/engine, serializers, CLI, PlanRun, handling, and Execution.
7. Re-run or inspect evidence appropriate to the claim. Never equate controlled
   tests, CI, historical reports, and live physical verification.
8. Treat confirmed limitations, potential risks, and forward questions as
   different evidence classes.
9. Preserve human-only publication and merge authority.

This recovery procedure supports knowledge continuity. It is not executable
training, credential issuance, automatic appointment, or authority transfer.

## 20. Explicit non-claims

This checkpoint does not establish that IRIS authenticates a human, selects or
creates arbitrary strategies, plans arbitrary objectives, verifies
caller-supplied facts, personalizes the production study strategy, stores
context in Memory, integrates Planning into conversation, creates or advances
a PlanRun, executes conceptual steps, invokes capabilities from Planning,
monitors resources, runs Ollama in every environment, or has achieved physical
deployment readiness.

## FINAL CONTINUITY STATEMENT

At canonical post-WP080 `main`
**`69dd93636f0e5d3fe3f7610781122a27c9df9c96`**, IRIS extends the bounded
Planning-only CLI introduced by WP075 with one validated strategy manifest,
exact discovery and selection, requirement disclosure, context-aware result
integrity, versioned result and metadata JSON, and an explicit bounded
caller-context path through the existing `ContextEngine`. WP080.1 closes
float-underflow, signed-zero fidelity, and subprocess-evidence gaps inside the
same PR lineage.

**Caller context is not verified knowledge; Planning is not PlanRun or
execution; successful evaluation is not completed work.** This checkpoint
freezes that historical state, grants no operational or merge authority, and
stops.
