# IRIS — ARCHITECTURE CONTINUITY CHECKPOINT — ACC-WP075

**Represented canonical `main`:** `7692fef6d1d3638c770986489b26d088b94d4cd1`

**Represented Git tree:** `eda6776dce18ebb04ee3f76f5072507ba767508a`

**Checkpoint date:** 2026-11-11

**Previous checkpoint:** [ACC-WP070](ACC-WP070.md)

**Succession foundation:** [ARCHITECT-SUCCESSION-FOUNDATIONS](ARCHITECT-SUCCESSION-FOUNDATIONS.md)

## 0. How to read this checkpoint

This is an immutable historical photograph of IRIS **after WP075's canonical merge and before this documentation commit**. Publication of this file and the accompanying `LATEST.md` update is a separate Git operation, not part of the represented state.

- **FROZEN** means a retained architectural or authority boundary supported by accepted source history.
- **CURRENT** means evidence tied to the represented canonical SHA.
- **FORWARD** means a question, risk or proposal, never authorization for implementation.

Canonical repository files and Git objects outrank PR narrative. Tests establish behavior only for exercised cases. CI validates its evaluated revision and environment; it does not certify live physical Windows or Ollama behavior. This checkpoint does not grant runtime, planning, execution, merge, publication or successor-Architect authority.

# PART I — CANONICAL ANCHOR AND INTEGRATION LINEAGE

## 1. Represented WP075 merge

**CURRENT:** GitHub reports [PR #85](https://github.com/fermaxvago/IRIS/pull/85), `WP075 - Bounded Explicit Planning Entry`, merged on 2026-11-11. The canonical merge has exactly the following ordered parents:

1. `edf9cd551615ed42055d0ca56c6f2022cec56911` — post-WP074 canonical `main`.
2. `8ef2f851f4328a466bae6cce1e9c146d8d0da4eb` — accepted WP075 implementation.

The canonical merge and implementation have identical Git trees: `eda6776dce18ebb04ee3f76f5072507ba767508a`. Equality of trees proves identical tracked file content, not identity of commits, tests or lifecycle events.

**Post-merge CI:** [workflow 43107955709](https://github.com/fermaxvago/IRIS/actions/runs/43107955709) was independently checked: `event=push`, exact `head_sha=7692fef6d1d3638c770986489b26d088b94d4cd1`, `status=completed`, `conclusion=success`. The actual job logs report **2,816 passed, 1 skipped**, Ruff lint success, **355 files already formatted**, strict mypy success across **265 source files**, and wheel plus sdist successfully built. The single opt-in physical Ollama test was skipped, not passed.

**PR CI:** [workflow 43107268235](https://github.com/fermaxvago/IRIS/actions/runs/43107268235) succeeded for the implementation head `8ef2f851f4328a466bae6cce1e9c146d8d0da4eb`. Its synthetic PR checkout `f83f6d0e66f6b03b7b4aaa015a717fe9a1c2b303` is a separate Git object, not the implementation head or the canonical merge.

At the represented SHA, `ACC-WP075.md` did not exist and `LATEST.md` still identified ACC-WP070. Any subsequent ACC-WP075 publication cannot retroactively change the represented Git state.

## 2. Verified lineage from ACC-WP070 publication through WP075

All intervening stages are merged PRs. Every canonical merge below has exactly two parents (canonical base, then implementation head); its final implementation-head tree equals its merge tree.

| Stage and verified PR title | Canonical base / first parent | Implementation head / second parent | Canonical merge | Tree |
| --- | --- | --- | --- | --- |
| [ACC-WP070 #80](https://github.com/fermaxvago/IRIS/pull/80) — Architecture Continuity Checkpoint | `721f088c5a9728cac5ce923688300d219242f678` | `69ad5b9f74ee55c1354668b9384a5db9a2a8b2a6` | `d138608e71adf9df9d6fedfffc2b95818782f6e9` | `9a96c92112f9ae528de43ccd672c245b3a21e07f` |
| [WP071 #81](https://github.com/fermaxvago/IRIS/pull/81) — Bounded Conversational Resource Clarification | `d138608e71adf9df9d6fedfffc2b95818782f6e9` | `47c92019353e3424c29f8c7a2a2c1fd94970825c` | `5471bd2ef4287d556202be71d0a5194b0801ea54` | `a99b3cfe98dfbcce285d400b3ebd44a498209771` |
| [WP072 #82](https://github.com/fermaxvago/IRIS/pull/82) — Bounded Local Resource Comparison | `5471bd2ef4287d556202be71d0a5194b0801ea54` | `9de15c746764b0a422a0847212c2c1dfe281b891` | `95196050d94a18a931b0b3a80584fb98c5f6e127` | `de29704862aab2ecadf5f562ebdc7c3b7cd61b2e` |
| [WP073 #83](https://github.com/fermaxvago/IRIS/pull/83) — Bounded Conversational Resource Comparison Intent | `95196050d94a18a931b0b3a80584fb98c5f6e127` | `89b22826aab610a2c3c48dd5f037c2b2715c5062` | `a0e4eadd02f5441e0d8c47c6b52d78cfa3d6f50d` | `e2cf5dd6d71b76254e9630031372ce54b3b68534` |
| [WP074 #84](https://github.com/fermaxvago/IRIS/pull/84) — Bounded Operational Readiness Evidence and Integration Gap Assessment | `a0e4eadd02f5441e0d8c47c6b52d78cfa3d6f50d` | `46614682a08a068cde5cd1d153098bbfac19f789` | `edf9cd551615ed42055d0ca56c6f2022cec56911` | `900b516dbe88cfaf83a6b32f050476b1d1310e7b` |
| [WP075 #85](https://github.com/fermaxvago/IRIS/pull/85) — Bounded Explicit Planning Entry | `edf9cd551615ed42055d0ca56c6f2022cec56911` | `8ef2f851f4328a466bae6cce1e9c146d8d0da4eb` | `7692fef6d1d3638c770986489b26d088b94d4cd1` | `eda6776dce18ebb04ee3f76f5072507ba767508a` |

**WP073 genealogy exception:** Its final head is not a direct child of its base. The first implementation commit `1495fe44a36dea2c058b301e13808ae7360d0b5d` is the direct child of `95196050d94a18a931b0b3a80584fb98c5f6e127`; the final head `89b22826aab610a2c3c48dd5f037c2b2715c5062` is the child of that first implementation commit. Its PR contains two commits. Its merge base, parent ordering and equal tree remain valid. It would be incorrect to claim all final implementation heads in this table are direct children of their canonical bases.

```text
implementation commit != pull request != synthetic PR test merge
implementation tree equality != commit equality
canonical merge != later checkpoint documentation commit
historical represented state != latest live repository state
```

# PART II — RETAINED ARCHITECTURAL AND AUTHORITY WALLS

## 3. FROZEN responsibility distinctions

The detailed pre-WP071 cumulative history resides in [ACC-WP065](ACC-WP065.md) and [ACC-WP070](ACC-WP070.md). The represented source retains these separations:

| Distinction | Architectural consequence |
| --- | --- |
| Input / Request / authentication | A CLI input and its provenance do not authenticate a particular human. |
| Routing / dispatch / execution | Classification and selection alone never grant execution authority. |
| Goal / Plan | An intended outcome is distinct from a conceptual strategy. |
| PlanningRequest / PlanningResult | Input and proposed result are separate, typed, identity-bound values. |
| Plan / PlanRun | Proposed steps do not create operational run state or progress. |
| PlanStep handling metadata / handler activation | An optional handling category is not an invocation instruction or permission. |
| Selection / binding / authorization / invocation | Separate gates with separate owners; one is not equivalent to another. |
| ExecutionResult / PlanObservation | Operational outcome and canonical Run evidence remain distinct. |
| Observation / assessment / transition / update | Interpretation, decision and state advancement are separately controlled. |
| Revision identity / causal currentness | Equal identifiers do not establish the most recent valid Run state. |
| Model selection / provider availability | Binding a model does not prove a live provider is healthy. |
| Local system observation / model disclosure | Observation authority—an explicit `/recursos` request or the natural-language preliminary approval—remains distinct from exact contextual-disclosure approval. |
| Provider output / conversation commit | Only a validated successful provider result may be committed atomically. |
| Contextual disclosure / tool authority | Providing information to a model does not authorize it to operate tools. |
| Conversation rollover / persistent memory | Bounded session continuity is not archival storage or semantic memory. |
| Resource baseline / telemetry | One point-in-time retained baseline is not monitoring or history. |
| CI / physical acceptance | Linux automated checks do not establish live Windows/Ollama reliability. |

No general agent runtime, autonomously advancing loop, persistent monitoring, general user authentication or new permission framework was created by WP071–WP075.

# PART III — WP071–WP073 RESOURCE CONSULTATION AND COMPARISON

## 4. WP071: bounded resource clarification

**CURRENT:** [PR #81](https://github.com/fermaxvago/IRIS/pull/81) added limited clarification for incomplete natural-language CPU/RAM consultation. The recognition path is conservative, with unsupported or ambiguous requests not silently promoted into resource observation. Relevant source: `iris/intelligence/resource_intent.py`, `iris/__main__.py`. Relevant tests: `tests/test_conversational_resource_intent.py`. Clarification != observation approval != permission to disclose readings to a model.

## 5. WP072: one local comparison baseline

**CURRENT:** [PR #82](https://github.com/fermaxvago/IRIS/pull/82) introduced the pure resource comparator and `LocalResourceComparison` in `iris/intelligence/resource_comparison.py`. In chat, `/comparar base` requires explicit approval for a single baseline capture and temporary retention. `/comparar ahora` independently requests approval for a second reading before calculating the local CPU/RAM delta.

- One process-local baseline, scoped to current chat session identity and generation.
- Strict monotonic lifetime `BASELINE_LIFETIME_SECONDS = 600`: expired at age >= 600 seconds.
- Successful comparison consumes the baseline once; reset, invalidation, stale provenance and failed operations follow explicit retention rules.
- Incompatible measurements, capacity changes, timestamps and incomplete observations are validated.
- The local comparison itself calls no model, does not create a conversational turn and does not persist historical telemetry.

Two point measurements do not establish trend, health or cause. Controlled tests are in `tests/test_resource_comparison.py`.

## 6. WP073: limited conversational comparison intent

**CURRENT:** [PR #83](https://github.com/fermaxvago/IRIS/pull/83) added `recognize_resource_comparison_intent` in `iris/intelligence/resource_comparison_intent.py`. Explicit CLI commands take precedence; recognized natural comparison intent is checked before ordinary single-reading intent. A question such as `¿Estoy usando más RAM que antes?` can access the existing comparison only if a valid baseline already exists, and only after new consent for the second reading. It does not implicitly create a baseline, perform LLM disclosure, or add a conversation turn. Tests: `tests/test_resource_comparison_intent.py` and `tests/test_resource_comparison.py`.

# PART IV — WP074 OPERATIONAL EVIDENCE

## 7. Evidence ledger and new cross-path test

**CURRENT:** [PR #84](https://github.com/fermaxvago/IRIS/pull/84) added [WP074_OPERATIONAL_READINESS_EVIDENCE](../WP074_OPERATIONAL_READINESS_EVIDENCE.md) and `test_wp074_cross_path_session_and_baseline_isolation` in `tests/test_resource_comparison.py`. WP074 changed documentation and tests only, not production code.

Its **historical source anchor** was the then-canonical post-WP073 `a0e4eadd02f5441e0d8c47c6b52d78cfa3d6f50d`. R1 ordinary conversation, R2 authorized local resource consultation and disclosure, R3 local baseline comparison were reachable through their examined CLI entries. At that earlier revision R4's Planning/execution components were programmatically present, but no examined CLI input built a `PlanningRequest`. This was a scoped accessibility finding, **not** proof the Planning API was missing.

T-074-01 adds the full approved contextual resource-consultation turn between baseline creation and local comparison, verifying three exact resource captures, separate approval stages, two provider turns, preservation of the original baseline and one successful baseline consumption. It differs from older tests that denied intermediate disclosure.

**Historical boundary:** after WP075, the statement “no CLI Planning entry” is no longer current. The separate full “conversational plan and execute an arbitrary goal” journey still remains unimplemented. Neither controlled cross-path testing nor CI establishes physical deployment readiness.

# PART V — WP075 EXPLICIT PLANNING ENTRY

## 8. First user-facing CLI to Planning path

**CURRENT:** [PR #85](https://github.com/fermaxvago/IRIS/pull/85) introduces one explicit top-level CLI command:

```text
python -m iris planificar --objetivo "Preparar una sesión de estudio"
iris planificar --objetivo "Preparar una sesión de estudio"
```

`iris/__main__.py` uses standard-library `argparse` with an objective that must be nonempty after trimming, no longer than 160 Unicode code points, with Unicode control and formatting characters rejected. Exactly one `--objetivo` is accepted. It does not use LLM semantic matching, automatic synonyms, arbitrary textual goal extraction or a chat Planning command. Existing exact-objective matching ignores case and normalizes whitespace.

```text
explicit CLI objective
  -> bounded input validation
  -> Request(content=objective, source="cli", request_id)
  -> Goal(objective, scope=TASK(request_id),
          provenance=(source_type="request", source_id=request_id, actor=None))
  -> PlanningRequest(goal, independent request ID, UTC created_at, context=None)
  -> DeterministicPlanner.plan(PlanningRequest) exactly once
  -> reject foreign/malformed/temporally inconsistent PlanningResult
  -> render safe conceptual result or truthful abstention
  -> STOP (no PlanRun, binding, handler activation, or execution)
```

Request, Goal and PlanningRequest have independent unique identifiers; task scope is **not** access control, and `actor=None` does **not** assert a recognized user. Goal constraints and success criteria are empty and no ContextSnapshot is fetched. The result must match current request and goal identities, with canonical status/payload structure. Output uses existing terminal-control character escaping.

The CLI distinguishes `PLAN_CREATED`, `NO_PLAN_REQUIRED`, `INSUFFICIENT_CONTEXT` and `UNSATISFIABLE`. `NO_REGISTERED_STRATEGY` means only that the configured rule set lacks a match—not real-world impossibility. `NO_PLAN_REQUIRED` never means the task has been completed. Valid abstention is not a software crash.

## 9. One built-in production conceptual strategy

**CURRENT:** `iris/planning/study_strategy.py` supplies exactly one `PlanningRule` whose canonical objective is **`Preparar una sesión de estudio`**. Its four `PlanStep` values have an acyclic chain, no assumptions, no context requirements, no step constraints and `required_handling=None`:

| Step | Conceptual future human work | Dependencies |
| --- | --- | --- |
| A | Delimit study topic and desired learning result | None |
| B | Identify appropriate study materials and exercises | A |
| C | Organize a review and practice sequence | B |
| D | Establish self-assessment and identify remaining doubts | C |

This is a real built-in limited **plan representation**, not personalized tutoring or autonomous academic planning. The normal installed entrypoint can produce `PLAN_CREATED` using this single template without a test-injected planner or running Ollama. It does not know the student's subject, deadlines, real assignments or course materials. The expected outcomes describe future states, not observed completion.

No general rules catalog, user-supplied strategy plugins, arbitrary-plan model, persistent plan storage, scheduling, or task automation was added.

## 10. WP075 no-execution boundary and test coverage

**CURRENT/FROZEN:** The new command evaluates one `PlanningRequest` and stops after presenting `PlanningResult`. It does **not** create a `PlanRun`, materialize or bind an `ExecutionRequest`, call `ExecutionCoordinator`, activate a handler, access the capability runtime, consult Memory, retrieve files, call Ollama, persist the plan, or perform application-level network operations in the planning workflow.

`tests/test_planning_cli.py` exercises ten acceptance groups and 25 focused cases: production-rule and installed CLI paths, unsupported objectives, invalid and control-character input, deterministic matching, independent identity and provenance, wrong-type and foreign results, legitimate status rendering, forbidden operational boundaries, legacy command regression and packaging/entrypoint behavior. The test suite does not establish exhaustive freedom from every possible future side effect.

# PART VI — CURRENT OWNERSHIP MAP AND ACCESSIBILITY

## 11. Responsibility map at represented main

| Component | Currently owns | Does not grant |
| --- | --- | --- |
| Legacy `IRIS>` and deterministic router/dispatcher | Explicit `estado`, `ayuda`, `salir` and bounded dispatch | Arbitrary Planning and autonomous action |
| `chat --model` / `chat --select` | Bound local conversational session, controlled provider calls and turns | Persistent authenticated user or automatic tools |
| Conversational resource consultation | Narrow recognition, authorized `system.status` capture and separate disclosure approval | Unsolicited observation or model authority |
| `LocalResourceComparison` | One ephemeral authorized baseline and separately authorized local delta | Telemetry, diagnosis, model inference |
| `planificar --objetivo` | User-facing bounded objective, traceable PlanningRequest and one result | Model chat Planning, PlanRun or execution |
| `iris.planning` | Immutable Goal/Plan models and deterministic exact-match strategy evaluation | Device actions or contextual discovery |
| `iris.plan_runs` / Plan control & composition | Programmatic immutable Run revisions, decisions and step preparation | Implicit CLI access or autonomous loop |
| `iris.execution` | Explicit execution under its own preconditions and handler contracts | Authority inferred from a conceptual plan |
| `iris.intelligence` | Provider-independent inference boundaries | Permission to invoke tools |
| `iris.memory` | Explicit storage and retrieval contracts | Automatic archival of user chat and plans |

**Accessibility assessment:** R1 ordinary conversation, R2 authorized consultation and R3 baseline comparison are reachable from their corresponding supported chat CLI paths. WP075 makes *explicit Planning-only* reachable from its own CLI subcommand. This does **not** create the end-to-end conversational Planning-to-Execution path. Programmatic availability of Planning/Execution APIs is separate from the accessibility of an integrated human workflow.

## 12. Causal sketch

```text
                               IRIS command interface
                         /              |              \
                     legacy            chat          planificar
                       |                |                 |
                 router/dispatch   temporary session    validated input
                                        |                 |
                               conversation/resources    Request -> Goal
                                        |                 |
                                approvals as needed   PlanningRequest
                                        |                 |
                               validated turns/delta  DeterministicPlanner
                                                          |
                                                     PlanningResult
                                                          |
                                                      local output
                                                          |
                                                         STOP

        PlanningResult  -X->  PlanRun  -X->  handler activation  -X->  execution
          (No authority granted along these edges by WP075.)
```

# PART VII — VERIFICATION, LIMITS AND FRONTIER

## 13. Canonical workflow ledger

GitHub was queried for each run's trigger, exact canonical head, completed status and success conclusion. WP075's complete quality job log was checked independently. Earlier run conclusions do not by themselves re-establish all former test counts.

| Stage | PR | Exact canonical post-merge CI | Conclusion |
| --- | --- | --- | --- |
| ACC-WP070 | [#80](https://github.com/fermaxvago/IRIS/pull/80) | [39855013971](https://github.com/fermaxvago/IRIS/actions/runs/39855013971) | `push`, success |
| WP071 | [#81](https://github.com/fermaxvago/IRIS/pull/81) | [40041015165](https://github.com/fermaxvago/IRIS/actions/runs/40041015165) | `push`, success |
| WP072 | [#82](https://github.com/fermaxvago/IRIS/pull/82) | [40150431328](https://github.com/fermaxvago/IRIS/actions/runs/40150431328) | `push`, success |
| WP073 | [#83](https://github.com/fermaxvago/IRIS/pull/83) | [42704907877](https://github.com/fermaxvago/IRIS/actions/runs/42704907877) | `push`, success |
| WP074 | [#84](https://github.com/fermaxvago/IRIS/pull/84) | [42904754061](https://github.com/fermaxvago/IRIS/actions/runs/42904754061) | `push`, success |
| WP075 | [#85](https://github.com/fermaxvago/IRIS/pull/85) | [43107955709](https://github.com/fermaxvago/IRIS/actions/runs/43107955709) | `push`, **2,816 passed, 1 skipped**, Ruff, mypy, wheel/sdist success |

The WP075 PR CI [43107268235](https://github.com/fermaxvago/IRIS/actions/runs/43107268235) also succeeded for its implementation head. Local 25 focused and 231 selected regression counts are engineer-reported rather than rerun by this checkpoint author.

The Ubuntu/Python 3.11 automated run omits an opt-in real Ollama integration case. This checkpoint includes fresh source/Git inspection and verified CI, **not** new physical Windows/Ollama/hardware verification or independent live end-to-end provider testing. A skipped case is not a pass.

## 14. Independent implementation, accessibility and validation axes

| Journey | Implementation | Accessibility at represented revision | Validation and missing evidence |
| --- | --- | --- | --- |
| R1 conversational text | PRESENT | REACHABLE from chat | Controlled tests and CI; no current physical model health evidence |
| R2 authorized CPU/RAM consultation | PRESENT | REACHABLE for supported chat requests | Controlled tests and CI; consent separated; no current physical reading certified |
| R3 ephemeral baseline comparison | PRESENT | REACHABLE with explicit baseline and second consent | Controlled tests and CI; not ongoing monitoring |
| R4a explicit conceptual Planning | PRESENT | REACHABLE from independent `planificar` CLI | Built-in study strategy, installed-entry test and CI; no arbitrary planning |
| R4b conversational Planning-to-Execution | PARTIAL internal components | NOT REACHABLE from examined CLI as an end-to-end journey | Programmatic contracts/tests exist; no general authorized user-facing execution route |

Reachability does not mean physical runtime availability, nor does CI alone establish operational readiness. There is no readiness percentage.

## 15. CONFIRMED limitations

1. Exactly one exact-objective study-session strategy is bundled in the new CLI.
2. Unregistered objectives receive a configured-rule abstention; no arbitrary planning or semantics are inferred.
3. The planning CLI is separate from conversational chat and never invokes PlanRun or execution.
4. Chat state is bounded and temporary; rollover is not persistent memory.
5. Comparison retains only one baseline with a strict <600-second lifetime and session-generation binding.
6. Observation consent and contextual disclosure consent are independent.
7. No continuous hardware monitoring or historical trend analysis is provided by comparison.
8. Automated Ubuntu CI does not constitute fresh physical Windows or Ollama deployment validation.
9. No general strategy loader, dynamic tool registry for Planning, agent loop, automated retry, plan persistence or human authentication was added.
10. This checkpoint's eventual publication commit and PR CI are outside its represented canonical state.

## 16. POTENTIAL risks, not verified defects

- Extending strategy catalogs may require stronger provenance, applicability and maintenance review.
- Later natural-language Planning could wrongly elevate recognition into consent or execution authority.
- Users could misinterpret conceptual step descriptions as actions already performed.
- Expanded inputs may require more terminal and model-facing boundary tests.
- Real Windows/Ollama availability, network and locale behavior may differ from Linux CI.

These are review triggers, not established incidents or presently authorized implementation work.

## 17. FORWARD questions (non-authorizing)

- What explicit authority and provenance must a future strategy-registration interface require?
- How can conversational objective detection remain distinct from objective confirmation, Planning and execution admission?
- If a conceptual Plan is later used operationally, how are PlanRun creation, binding, currentness, authorization and handler activation independently gated?
- Which real Windows/Ollama end-to-end scenarios are required before claiming deployment readiness?
- Should future plans address real calendar, documents, or devices, and what separate user and capability approvals would that require?

All new scope requires Q1 independent reasoning, Q2 external research, Q3 ADOPT/ADAPT/REJECT, rigorous Contract Pass, bounded implementation and independent PR audit. This document neither approves WP076 nor appoints future engineers/Architects.

# PART VIII — CONTINUITY AND RECOVERY

## 18. Procedure for a future Architect

1. Independently inspect live `main` before making any claim about present capabilities.
2. Consult `LATEST.md` and check the latest valid immutable ACC rather than assuming ACC-WP075 is still newest.
3. Verify this checkpoint's represented SHA, tree, parents, PR #85 and exact post-merge CI.
4. Distinguish original implementation commits, multi-commit WP073, synthetic PR merges, canonical merges and later checkpoint documentation commits.
5. Read ACC-WP065, ACC-WP070, WP074 evidence and succession foundations for prior contracts and context.
6. Reconstruct identity, consent, context, Planning, Run revision, binding and execution authorities from source.
7. Never mistake historical physical reports, controlled tests, CI passes and live physical verification for interchangeable evidence.
8. Investigate candidate future work independently and preserve human-only merge authority.

This checkpoint is not executable training, credential issuance, automatic appointment, or an authority-transfer protocol.

## 19. Explicit non-claims

This checkpoint does not establish that IRIS is an autonomous personal assistant, can plan arbitrary objectives, authenticates a human from CLI provenance, completes proposed study steps, automatically approves tools, maintains long-term chat memory, monitors resources continuously, diagnoses hardware, can run Ollama in every environment, or has achieved deployment-level safety/reliability. It does not substitute for real-device validation or authorize a successor Work Package.

## FINAL CONTINUITY STATEMENT

At canonical post-WP075 `main` **`7692fef6d1d3638c770986489b26d088b94d4cd1`**, IRIS retains distinct boundaries for routing, contextual observation, approval, memory, planning, PlanRun progression, execution and provider generation. WP071 added bounded resource clarification; WP072 added a one-shot local baseline; WP073 enabled conservative natural-language comparison against an already approved baseline; WP074 added a reproducible readiness ledger and cross-path integration test; and WP075 introduced the first genuinely reachable, explicit, limited **Planning-only** CLI with one production study preparation strategy.

**Planning does not grant execution; a proposed result is not completed work.** This document freezes that historical state, grants no new operational or merge authority, and stops.
