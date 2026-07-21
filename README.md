# Cognitive OS

**Experimental contract-driven runtime for turning human software goals into structured specifications, role artifacts, executable capability pipelines, sandbox implementation packages, tests, and review reports.**

Cognitive OS is an R&D project exploring a practical alternative to the common "one big agent does everything" pattern.

Instead of letting an LLM freely plan, execute, rewrite code, mutate state, and explain itself in one unbounded loop, Cognitive OS separates meaning, planning, contracts, and execution into explicit layers.

It is best understood as a **contract-driven intent-to-engineering pipeline and verification harness for LLM-assisted software work**, not as a replacement for ChatGPT Work, Codex, Copilot, Cursor or an IDE.

The core idea is:

```text
human goal
-> GoalSpec
-> architecture decision
-> technical specification
-> implementation plan
-> test plan
-> review findings
-> optional sandbox patch package / Foundry capability candidate
-> controlled execution artifacts
```

This repository is currently a **research preview / executable architecture prototype**, not a production framework.
The near-term MVP target is narrower and more concrete: **Prompt -> Verified Local Automation Package**.

## Why This Exists

Many LLM-agent systems collapse into the same failure mode:

```text
prompt -> agent -> tools -> more prompts -> more tools -> hope
```

Cognitive OS takes a stricter route:

- deterministic code handles contracts, queues, timeouts, schemas, registries, and execution;
- LLMs are used only where ambiguity and semantic judgment are useful;
- every layer communicates through typed artifacts rather than hidden agent chatter;
- roles such as Architect, SpecWriter, Implementer, Tester, and Reviewer produce bounded artifacts with forbidden actions;
- generated or extracted capabilities go through sandbox build, tests, and explicit promotion gates.

The guiding principle is:

```text
The lower the layer, the less freedom.
The higher the layer, the more semantic judgment, but fewer direct execution rights.
```

## Positioning

Modern workspace agents and coding assistants are already good at reading projects, editing files and running tools. Cognitive OS should not compete with them on UI surface area or raw convenience.

The project is useful only where it adds control:

- explicit prompt adequacy and clarification gates;
- portable contracts instead of hidden chat state;
- role artifacts that act as APIs between layers rather than prose-only reports;
- explicit separation of facts, judgments, plans, tests and reviews;
- fixture-first or sandbox-first implementation;
- source immutability checks and release decisions;
- reproducible evaluation against direct-agent baselines.

See `POSITIONING.md` for the full positioning statement and `EVALUATION_PLAN.md` for the comparison plan.

## Architecture

```text
                    Human Goal
                       |
                       v
              Goal Intake / GoalSpec
                       |
                       v
+-----------------------------------------------------+
| L4: Cortex / Liquid Graph                            |
| Strategic decisions, interpretation, role artifacts  |
| Architect / SpecWriter / Implementer / Tester /      |
| Reviewer                                             |
+-----------------------------------------------------+
                       |
                       v
+-----------------------------------------------------+
| L3.5: Spinal Planner                                 |
| IntentPacket -> MotorPlanPacket/SignalPacket         |
| deterministic route, optional local LLM proposal     |
| validated Pipeline DSL, no direct plugin execution   |
+-----------------------------------------------------+
                       |
                       v
+-----------------------------------------------------+
| L2.5: Capability + Contract Registries               |
| What exists, what is active, what contracts allow    |
+-----------------------------------------------------+
                       |
                       v
+-----------------------------------------------------+
| L2: Runtime                                          |
| Durable queue, workers, checkpoints, process boundary|
| execution journal, interrupts, replay artifacts      |
+-----------------------------------------------------+
                       |
                       v
+-----------------------------------------------------+
| L1: Capabilities / Plugins                           |
| Isolated deterministic tools with JSON schemas       |
+-----------------------------------------------------+

              Separate build lifecycle:

+-----------------------------------------------------+
| L3.2: Capability Foundry                             |
| spec -> sandbox build -> contract tests ->           |
| dry-run promotion -> explicit promote                |
+-----------------------------------------------------+
```

The user-goal path is enforced by `runtime/goal_runtime.py`: `goal_run.py`
cannot call a graph or LLM planner directly. It sends an `IntentPacket` through
the spinal planner, validates the returned `MotorPlanPacket`, then allows L2 to
execute. L2 emits correlated execution events and typed interrupts back to L3.5;
motor adaptation is bounded by an explicit budget.

The same packet/recovery contract is used by synchronous goal execution,
`execute_pipeline_async()`, and durable worker jobs. Queue results persist their
`layer_packets` and `level35_adaptations`, so recovery decisions survive process
boundaries and can be audited after a worker finishes.

## Key Concepts

### Crystal / Liquid Split

Cognitive OS uses a "crystal/liquid" split:

- **Crystal:** contracts, schemas, deterministic plugins, runtime state, queues, validation, and tests.
- **Liquid:** semantic interpretation, architecture decisions, unknown handling, and human-readable reasoning artifacts.

The liquid layer may decide what should happen next. It cannot bypass the crystal layer.

### Typed Artifacts

Important transitions are represented as explicit artifacts. These artifacts are not just reports; they are the system's internal APIs between layers and roles.

For example:

```text
GoalSpec
-> ArchitectureDecisionRecord
-> TechnicalSpec
-> ImplementationPlan
-> TestPlan
-> ReviewFindings
```

Each artifact defines what the next layer may rely on, what it must not invent, and what evidence or constraints must survive the handoff.

The current artifact set includes:

- `GoalSpec`
- `IntentPacket`
- `MotorPlanPacket`
- `SignalPacket`
- `ExecutionEventPacket`
- `InterruptPacket`
- `ProjectMapReport`
- `ArchitectureDecisionRecord`
- `TechnicalSpec`
- `ImplementationPlan`
- `TestPlan`
- `ReviewFindings`
- `PatchPackage`
- `TestResult`

The system does not rely on hidden free-form conversations between agents as its machine protocol.

### Role-Separated L4 Skills

Level 4 contains role skills, not autonomous all-powerful agents:

| Role | Input | Output | Restriction |
| --- | --- | --- | --- |
| Project Analyzer | project files | `ProjectMapReport` | reports evidence, does not rewrite source |
| Architect | project report + goal | `ArchitectureDecisionRecord` | does not write code or mutate registry |
| SpecWriter | ADR | `TechnicalSpec` | does not broaden chosen architecture scope |
| Implementer Planner | TechnicalSpec | `ImplementationPlan` | does not write code |
| Programmer Executor | ImplementationPlan | `PatchPackage` + `TestResult` | MVP mode is sandbox/no-source-edit |
| Tester | TechnicalSpec + ImplementationPlan | `TestPlan` | defines verification, does not execute tests |
| Reviewer | spec + plan + tests + optional result | `ReviewFindings` | reviews, does not patch or promote |

Role identities, descriptions, capabilities, order, chain settings, builder settings and policies are not source-code constants. The active source of truth is `config/role_directory.json`. Its v2 entries also declare role contracts, gates, fallback policy, LLM policy, KB admission policy, stop conditions and quality criteria. Runtime code interprets that directory through generic loaders, `runtime/configured_role_pipeline.py` runs configured prefixes by artifact type, `runtime/role_operational_policy.py` validates operational completeness, `runtime/role_gate_runner.py` executes configured gates/quality criteria against produced artifacts, and `runtime/role_skills.py` exposes only `run_role_skill(role_id, **inputs)`. Legacy split files such as `roles/*.json`, `config/artifact_builders.json`, `config/role_artifact_pipeline.json` and `config/role_record_defaults.json` may remain as migration/import material, but they are not the active authority for which roles exist.

`RoleGateReport` is also a control artifact. It supports `advisory`, `strict`, and `release_required` modes: advisory mode records failed gates without blocking, strict mode blocks role-chain acceptance on failed gates, and release-required mode is the package/release gate that requires clean role artifacts before downstream promotion.

The same configuration-first invariant is now monitored directly. `tools/config_doctor.py` emits `ConfigDoctorReport` for loader and cross-reference integrity; `tools/config_coverage.py` emits advisory `ConfigCoverageReport` for templates, rules, transforms and sandbox profiles exercised by tests/trial registries; every `VerifiedSystemPackage` embeds a `RuleTrace` that names the config sources behind the decision; and `tools/config_mutation_sandbox.py` validates a proposed JSON config replacement without touching the active file.

### Capability Foundry

Foundry is the controlled lifecycle for turning extracted or generated functionality into reusable capabilities:

```text
PROPOSE -> GENERATE_SPEC -> SANDBOX_BUILD -> TEST -> PROMOTION_READY -> explicit PROMOTE
```

In MVP mode, Foundry can prepare sandbox candidates and promotion reports. It does not silently modify analyzed source projects or mutate the runtime registry.

### Stage 2: Prompt To Verified System Package

Stage 2 explores bounded prompt-to-package generation:

```text
adequate prompt
-> PromptAdequacyGate
-> L4.0 CognitiveControlPlaneDecision
-> isolated generated package
-> tests
-> tester review
-> release decision
```

The `PromptAdequacyGate` is not only a report. It is an API input to the L4.0 control plane. Stage 2 now advances only when `CognitiveControlPlaneDecision.role_transition.next_action` is `build_verified_system_package`; vague prompts route to clarification, unsupported prompts stop, and bounded-but-unknown package requests can escalate to L4.5 as a hypothesis request without bypassing contracts. If intake is uncertain but the prompt still looks like a bounded implementation request, L4.0 emits `prompt_intake_uncertainty` and asks L4.5 to interpret it before a developer changes Cognitive OS. If the prompt is a bounded behavior or limitation question about a supported domain, L4.0 emits `behavior_question_uncertainty`; L4.5 must either answer from evidence or return a `DeveloperImprovementRequest` for fact-based behavior-question answering.

Current deterministic package classes include:

- JSONL log-filter CLI utility;
- text statistics CLI utility;
- CSV sort CLI utility;
- OCR image CLI utility;
- image contents CLI utility with optional vision backend;
- image table to Excel/CSV/HTML/DOC/RTF CLI utility with injectable OCR/text backend, `--ocr-text-file`, optional OpenAI-compatible vision/OCR backend, stdlib XLSX writer, CSV writer, legacy XLS-compatible HTML writer, plain HTML writer, DOC-compatible HTML writer and RTF writer;
- generic file conversion CLI utility driven by `GenericFileConversionRecipe`, `LibraryBindingRecipe` and `AdapterImplementationPlan`, for prompts such as `.xls -> .png`, `.md -> .rtf`, `.txt -> .html` or `.jpg -> .doc`, with adapter boundary, advisory library candidates, implemented stdlib adapters where safe and dependency-free fixture tests;
- FastAPI CSV aggregation service;
- FastAPI in-memory key/value CRUD service.

Generic file converters are intentionally not stored as one KB/template per extension pair. Stage 2 extracts source/target extensions into `GenericFileConversionRecipe`, derives advisory backend candidates into `LibraryBindingRecipe`, then records `AdapterImplementationPlan`. Safe stdlib backends such as `.txt -> .html`, a bounded `.md -> .rtf` subset and `.jpg/.jpeg/.png -> .doc` as DOC-compatible HTML with embedded image are implemented inside generated `file_converter_cli/adapters.py`; heavier backends remain explicit candidates behind the same adapter contract. Candidate libraries do not grant permission to install dependencies, call network or bypass tests. Repeated verified recipes may later become KB candidates, but the default path is recipe-driven rather than format-template-driven.

When a bounded prompt cannot be handled by the deterministic intake/KB route, Stage 2 now uses a fallback autonomy loop instead of immediately asking a developer to patch Cognitive OS:

```text
unknown or uncertain prompt
-> L4.5 SemanticHypothesisProposal
-> L4SemanticValidationResult
-> SandboxAttemptSpec
-> bounded sandbox attempt for an existing mapped route
-> tester verification
-> SuccessfulResolutionCandidate or DeveloperImprovementRequest
```

The loop lives in `runtime/fallback_autonomy_loop.py`. It is deliberately narrow: L4.5 may propose a route, but it still cannot build packages, execute arbitrary code, edit source, mutate the registry or promote KB records. Stage 2 may only attempt an already known generated-package route inside the isolated sandbox. Before execution, `runtime/sandbox_attempt_spec.py` creates `SandboxAttemptSpec`: a typed API artifact that names the attempt kind, case, runner, project-scoped verification commands, allowed operations, forbidden operations and invariants. The attempt policy is data-driven through `registry/sandbox_attempt_policy.json`; if that registry file is missing or invalid, the runtime falls back to a minimal safe default rather than granting extra authority. The first active policy supports `existing_stage2_case` for mapped cases such as `image_contents_cli` and `csv_sort_cli`, plus `bounded_adapter_recipe` for `generic_file_converter_cli`. The adapter recipe path embeds `GenericFileConversionRecipe`, `LibraryBindingRecipe` and `AdapterImplementationPlan`; it may select only fixture or stdlib adapter backends and still forbids dependency install, network, registry mutation, user source edits and model-generated code execution. Non-allowlisted routes block before any package attempt. If model-backed L4.5 gives a valid but weaker hypothesis while deterministic evidence already maps the prompt to an existing route, proposal hardening records `deterministic_existing_route_rescue=true` and uses the verified route candidate. If that attempt passes verification, the release report is marked ready and the loop writes a staged `KnowledgeCandidate` with `auto_promote=false`; if it fails or has no executable mapping, the output remains a developer handoff.

Verified packages include a `ProgrammerSandboxGate` that records project directory presence, verification status, tester approval, and the invariant that user source and registries were not modified.

For bounded implementation prompts that pass adequacy but have no supported deterministic package template, Stage 2 may invoke `runtime/llm_sandbox_implementation.py`. This is not free-form source editing: the model is treated as a hypothesis source, executable code is generated only from an allowlisted sandbox contract, verification runs inside `artifacts/llm_sandbox_implementations/*`, and the result keeps `promotion_allowed=false`. The allowlist is data-driven by `registry/sandbox_programmer_operations.json`; runtime validates stored `text_expression` operations with AST hardening and supports allowlisted stdlib profiles such as line sort/unique, CSV row count/sort/filter/select/sum/JSON records, HTML table to CSV, JSON extract/keys/pretty-print. If deterministic registry matching fails and `use_model=true`, L4.5/GigaChat Lite may normalize the prompt to one existing `operation_id` from that registry; invalid ids, low confidence and provider errors remain controlled blocks. Each sandbox implementation plan now includes a `SandboxOperationGraph` from `runtime/sandbox_operation_graph.py`: a typed read/parse/transform/serialize/write/verify chain with parser/serializer choices, side-effect boundaries, evidence links, and invariants. The graph is an API artifact for L4/L4.5, programmer, tester and admission gates, not prose explanation and not an execution permission. The registry is configurable, but it is not an arbitrary-code execution channel. A verified sandbox result then passes through `runtime/sandbox_programmer_admission.py`; if tester/reviewer admission succeeds, Stage 2 may mark it `release_ready_with_risks` while still forbidding user-source, registry, and KB mutation. With `--write`, the success is also staged as a weak `KnowledgeCandidate` under `artifacts/knowledge_candidates`; repeated verified cases plus teacher/Codex approval are still required before any KB/template crystallization.

The prompt-normalization field trial is runnable with:

```powershell
python tools\sandbox_prompt_field_trial.py --root . --use-model --write
```

It runs natural-language prompt variants through deterministic matching plus the L4.5 registry-operation normalizer and reports verified packages, controlled blocks, selected operations and strategy counts.

The first bounded composition recipes are also supported through `registry/sandbox_programmer_compositions.json`: CSV rows can be filtered, column-selected and serialized as JSON records, and text can be trimmed then uppercased. Composition remains deterministic and allowlisted; runtime validates that every step references an existing operation record, represents the chain in `SandboxOperationGraph` as multiple transform nodes, and does not allow arbitrary DAG generation.

If tester review requests rework, Stage 2 uses a bounded contract debug loop:

```text
FailureAnalysis -> ReworkPlan -> sandbox repair -> verification -> tester review
```

This is not a free-form retry loop. Only allowlisted deterministic repairs are applied inside the isolated generated package.
The loop is acceptance-tested as a separate L4 programmer capability: a probe intentionally damages a generated FastAPI package, the tester flags the contract failure, and the loop applies a bounded repair before re-running project-scoped verification.
The same probe path also covers CLI input/output contract repair for generated file-processing utilities.
It also covers missing negative or edge-case evidence, such as empty text input and malformed JSONL fixture handling.

### Stage 3: Prompt To Verified Product Slice

Stage 3 starts the post-MVP track:

```text
adequate prompt
-> ProductSliceSpec
-> RequirementSet
-> ArchitectureDecisionRecord
-> implementation task graph
-> documentation and scenario review
-> Stage 2 verified package
-> product release decision
```

The current Stage 3 slice deliberately reuses Stage 2 as the execution engine. It does not generate arbitrary products and does not edit user source trees. Its job is to lift a verified package into a product-level contract that names user scenarios, inputs/outputs, architecture decision, implementation tasks, verification evidence, and release decision.
It also derives a small requirement set, task dependencies, documentation review, scenario verification and a bounded product debug-loop plan. If documentation or scenario evidence is incomplete, Stage 3 may request only allowlisted package-local rework such as README rewrite, missing scenario test addition, and project-scoped verification rerun.
The current benchmark covers 8 supported product prompts: FastAPI key/value CRUD, FastAPI CSV aggregation, text stats CLI, JSONL log filter, duplicate file finder, batch renamer, JSON config merger, and static site indexer.

The executable product debug loop can be probed with:

```powershell
python tools/product_debug_loop_probe.py --root . --damage api_contract --write
python tools/product_debug_loop_probe.py --root . --damage cli_ux --write
python tools/product_debug_loop_probe.py --root . --damage readme_api --write
python tools/product_scenario_probe.py --root . --damage core_behavior --write
```

The `core_behavior` probe is intentionally a controlled block: if generated CLI domain logic produces wrong output while the CLI contract still looks valid, Stage 3 reports `core_behavior_drift` and stops for review instead of applying a blind deterministic repair.

Run the current 8-case Stage 3 prompt benchmark with:

```powershell
python tools/product_slice_benchmark.py --root . --write
```

Run it with:

```powershell
python tools/product_slice.py --root . --curriculum-dir curricula/programmer_prompt_stage2 --prompt "Сделай локальную FastAPI-службу с зависимостью fastapi, которая реализует key-value CRUD API, хранит данные в памяти, возвращает JSON, имеет controlled 404 для отсутствующего ключа, README, тесты и команду запуска." --write
```

## Current MVP Status

Current snapshot: **foundation-ready for controlled analysis/planning, sandbox programmer-executor, Foundry, and verified-package field trials. The product MVP target is now `Prompt -> Verified Local Automation Package`; Stage 3 product-slice work remains a controlled post-foundation track.**

Verified areas include:

- plugin catalog, schemas, and contract tests;
- pipeline execution, checkpointing, process boundary, and worker queue;
- Capability Registry and Contract Registry validation;
- controlled interrupt, quarantine, and fallback paths;
- Foundry spec/candidate/dry-run promotion path;
- deterministic known-route planner and project signals;
- Project Analyzer, Architect, SpecWriter, Implementer Planner, sandbox Programmer Executor, Tester, and Reviewer readiness gates;
- advisory memory/dialogue context;
- Knowledge Gap Loop for installed packages, official docs, and optional GitHub metadata evidence;
- human-readable architecture analysis documents generated by role pipelines.

These checks mean the deterministic planning and sandbox execution gates passed. They do **not** mean the system is generally intelligent, self-learning, or safe to let loose on arbitrary projects without review.

### Direct Provider Migration Sandbox

Provider migration is handled as a reviewed sandbox package, not as direct source editing. For the `map` field trial the focused analyzer can find local proxy assumptions, and the GigaChat sandbox patch generator can produce a separate tested package for direct `GigaChat-2-Pro` access:

```powershell
python tools\llm_migration_analysis.py --root . --project-dir F:\ubuntu\test\map --target-model GigaChat-2-Pro --write
python tools\gigachat_sandbox_patch.py --root . --project-dir F:\ubuntu\test\map --target-model GigaChat-2-Pro
```

The patch package writes `package/import_indoc.py`, mocked provider-boundary tests, README and `patch_report.json` under `artifacts/gigachat_sandbox_patches/*`. It keeps `source_code_changes=false` and requires explicit human approval before any source-project apply.

Review the package before applying:

```powershell
python tools\sandbox_patch_review.py --patch-dir artifacts\gigachat_sandbox_patches\<patch-id> --expected-source-project F:\ubuntu\test\map --write-review
```

Actual source apply is a separate explicit step:

```powershell
python tools\sandbox_patch_review.py --patch-dir artifacts\gigachat_sandbox_patches\<patch-id> --expected-source-project F:\ubuntu\test\map --apply-approved
```

The apply gate validates package status, verification status, source-project identity and registry/source invariants. It writes a timestamped backup next to each replaced source file before copying sandbox content into the source project.

The replayable teacher/corrector contour is implemented as a generic project-change trial helper plus the `map` GigaChat scenario:

```powershell
python tools\map_llm_migration_trial.py --root . --source-project F:\ubuntu\test\map --target-model GigaChat-2-Pro --write
python tools\map_gigachat_tester.py --root . --project-dir F:\ubuntu\test\map --live --write
```

The trial copies a baseline into an isolated fixture, applies the reviewed sandbox package only inside that fixture, compares the result with an external teacher reference, and records invariants such as `teacher_reference_is_ground_truth=false` and `source_project_modified=false`.
The portable acceptance probe for the same contour is:

```powershell
python tools\project_change_trial_probe.py --root . --write
```

Declarative project-change scenarios can also be run directly:

```powershell
python tools\project_change_trial_run.py --root . --scenario benchmarks\project_change_trials\direct_provider_probe\scenario.json --write
```

The current scenario interface is intentionally narrow: it supports fixture creation from baseline files, optional context copying, fixture-only teacher/reference apply simulation, text comparison and feature evidence checks.
The runner validates required fields, supported apply type, existing baseline/teacher files, safe relative targets and feature-check shapes before creating the fixture.
Supported apply types are `copy_teacher_to_fixture` and `sandbox_patch_package`. Patch builders are allowlisted in `registry/project_change_builders.json`; the current active builder is `gigachat_sandbox_patch`, which routes the generated package through `sandbox_patch_review` with apply restricted to the fixture:

```powershell
python tools\project_change_trial_run.py --root . --scenario benchmarks\project_change_trials\gigachat_patch_package_probe\scenario.json --write
```

## What This Project Is Good For

Cognitive OS is currently useful as:

- a research platform for contract-driven LLM orchestration;
- a reference architecture for layered agent/runtime separation;
- a project-analysis and capability-extraction test bench;
- a way to experiment with role-separated software development artifacts;
- a local-first environment for studying where LLMs should and should not be used;
- a foundation for prompt-to-tool or prompt-to-small-system generation.

It is focused on this problem:

```text
Given a vague or semi-structured human software goal,
produce a bounded, reviewable engineering chain instead of a free-form agent run.
```

## What This Project Is Not

Cognitive OS is **not** currently:

- a finished production framework;
- a competitor to ChatGPT Work, Codex, Copilot, Cursor or IDE workflows;
- a general autonomous software engineer;
- a safe arbitrary-code auto-patcher;
- a replacement for human review;
- a self-learning system that treats its own outputs as ground truth;
- a multi-agent chatroom where agents debate until something happens.

The general Programmer Executor remains sandbox-only and creates isolated patch/test artifacts. A separate reviewed gate can apply only an explicitly approved, validated specialized sandbox package with source-identity checks and a timestamped backup; Cognitive OS is still not a safe arbitrary-code auto-patcher.

## Safety Model

The safety model is based on explicit boundaries:

- plugins are isolated capabilities with schemas and contract tests;
- plugin-to-plugin calls are forbidden;
- pipeline composition belongs to runtime, not plugins;
- registry mutation requires the controlled Foundry lifecycle;
- promotion requires explicit approval;
- L4 roles cannot execute pipelines or mutate registries;
- L3.5 planner output must validate through Pipeline DSL before execution;
- the goal path cannot bypass the L3.5 facade or fabricate its own motor packet;
- L2 recovery decisions return through typed interrupts and bounded L3.5 adaptation;
- unsafe dependencies, unresolved local/domain calls, and risky side effects are blocked or quarantined;
- generated code is treated as a candidate artifact, not trusted production code.

Inspect generated artifacts before using them in real projects.

## Repository Structure

```text
runtime/                 Core runtime, planning, packets, registries, role pipelines
plugins/                 Isolated capabilities with manifests, schemas, and tests
registry/                Capability and skill registry data
tools/                   CLI tools for tests, reports, queues, role runs, and trials
pipelines/               Pipeline DSL examples
benchmarks/project_analyzer/
                         Small in-repository benchmark fixtures
curricula/               Role curriculum / teacher-reference gates
tests/                   Pytest suite
```

Generated runtime outputs are intentionally ignored by Git:

```text
artifacts/
generated/
benchmarks/github_*/
benchmarks/github_full_trial_*/
```

Those folders are local field-trial outputs or cloned external corpora, not source files for this repository.

Evaluation tasks live under `evaluation/`. They are source-controlled because they define the comparison corpus used to test Cognitive OS against direct-agent baselines.

The corpus can be extended through `tools/evaluation_corpus.py --count 20 --write`. Each generated task preserves the same API shape: `prompt.md`, `direct_agent/`, `cognitive_os/`, `metrics.json`, and `verdict.md`. Empty `not_run` metrics are allowed as placeholders, but every completed task must compare the same prompt and constraints for both routes.

`tools/evaluation_run_cognitive_os.py` runs the Cognitive OS route for selected tasks. `tools/evaluation_run_direct_agent.py` runs a deliberately small direct-agent baseline that does not use Cognitive OS contracts. The direct baseline is allowed to return controlled `blocked`; it must not invent unsupported dependency handling just to look competitive.

## Quickstart

The commands below assume Python 3.10+.

Install development dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

### 1. Check plugin contracts

```bash
python tools/check_plugins.py --root .
```

### 2. Check registry consistency

```bash
python tools/registry_doctor.py --root .
```

### 3. Run runtime smoke checks

```bash
python tools/runtime_smoke.py --root .
```

For a faster smoke pass without pytest:

```bash
python tools/runtime_smoke.py --root . --skip-pytest
```

### 4. Run the full test suite

```bash
python -m pytest -q
```

### 5. Run MVP acceptance

```bash
python tools/mvp_acceptance.py --root .
```

For a faster acceptance pass after pytest has already run:

```bash
python tools/mvp_acceptance.py --root . --skip-pytest
```

The default acceptance gate is deterministic and does not require an external L4 provider. Run the model-backed quality probe explicitly when the configured provider is available:

```bash
python tools/mvp_acceptance.py --root . --skip-pytest --live-l4
```

The machine-local `map`, `5`, and `004` field trials are also opt-in:

```bash
python tools/mvp_acceptance.py --root . --skip-pytest --local-project-trials
```

### 5.1 Run the Local Automation MVP trial

```bash
python tools/local_automation_mvp_trial.py --root . --write
```

This product-facing trial checks `Prompt -> Verified Local Automation Package`:
the registry-driven corpus in `registry/local_automation_mvp_cases.json`,
including verified CLI packages, image/document automation, local FastAPI
services, sandbox operation composition, sandbox atomic operations including
file-transform, `argv -> stdout`, `argv -> file`, `stdin -> stdout`,
`stdin -> file` and `file -> stdout` CLI shapes, controlled refusal for
out-of-scope GUI/SQL/deploy/live-network/source-edit prompts, and
`needs_clarification` routing for underspecified bounded prompts.

Sandbox programmer packages now carry an explicit interface contract selected
from `registry/interface_contracts.json`. The first active contracts are
`argv_stdout_numeric_expression`, `argv_to_file_numeric_expression`,
`stdin_to_stdout_text_transform`, `stdin_to_file_text_transform`,
`file_to_stdout_text_transform` and `file_to_file_text_transform`; they are API
artifacts between intake, programmer, tester and reviewer, not prose comments.
Each package also carries an `OperationRecipe`: a contract artifact that binds
the selected interface, transform, optional expression, input/output shapes and
evidence before code generation. Deterministic recipe parsing handles clean
input-channel/output-channel/transform prompts without adding a new registry
operation for every combination. L4.5 may propose an OperationRecipe only after
deterministic matching and operation-id normalization fail with a clean no-match;
invalid ids, low confidence, unsupported interfaces and unsupported transforms
remain controlled blocks.
Allowed OperationRecipe contracts, transforms, deterministic markers,
contract-to-profile bindings, transform expressions and the L4.5 recipe prompt
are loaded from `config/operation_recipe_rules.json`.
Sandbox programmer profile policy, parser shape, graph family and tester
admission shape are loaded from `config/sandbox_programmer_profiles.json`.
Sandbox release/admission/evaluation policy, including required evidence checks,
release decision labels, limitations and forbidden actions, is loaded from
`config/sandbox_release_policy.json`.
Verified sandbox packages also include `GeneratedPackageEvaluation`: a compact
evidence score over prompt presence, selected operation evidence, interface
contract, recipe/contract match, operation graph, README, tests, sandbox
verification, tester admission, and no-mutation invariants. It is an additional
release-facing artifact, not a substitute for pytest or reviewer admission.

### 6. Run the Project Analyzer benchmark

```bash
python tools/project_analyzer_benchmark.py --root . --write
```

### 7. Create a safe extraction proposal

```bash
python tools/project_extraction_proposal.py \
  --root . \
  --project-dir benchmarks/project_analyzer/projects/simple_cli_tool \
  --write \
  --write-spec
```

This command should not modify the analyzed project or mutate the runtime registry.

### 8. Build a sandbox Foundry candidate

```bash
python tools/project_transform.py \
  --root . \
  --project-dir benchmarks/project_analyzer/projects/simple_cli_tool \
  --force
```

This performs a controlled path toward `PROMOTION_READY`. Real promotion requires an explicit promotion action.

### 9. Generate a verified system package

```bash
python tools/verified_system_package.py \
  --root . \
  --curriculum-dir curricula/programmer_prompt_stage2 \
  --prompt "Сделай локальную FastAPI-службу с зависимостью fastapi, которая принимает CSV, валидирует колонки category/value, считает агрегаты по category, сохраняет JSON-отчёт, имеет README, тесты и команду запуска." \
  --write
```

### 10. Exercise the Stage 2 debug loop

```bash
python tools/stage2_debug_loop_probe.py \
  --root . \
  --case fastapi_kv_store \
  --write
```

## Operating The Runtime

Common operational commands:

```bash
python tools/queue_status.py --root .
python tools/run_worker_pool.py --root . --workers 2
python tools/job_inspect.py --root . --id <job_id>
python tools/job_cancel.py --root . --id <job_id> --reason manual_cancel
python tools/job_requeue.py --root . --id <job_id>
python tools/registry_selection_report.py --root .
```

The runtime uses durable artifacts for queues, execution journals, checkpoints, and reports. These are intended for replay, audit, and debugging.

## LLM Usage

Cognitive OS is designed to work with local or gateway-based LLM access, but LLM calls are not required for every path.

The architectural rule is: **LLM is a bounded hypothesis source inside a verifiable engineering machine**. It may propose an interpretation, risk, option, missing fact, or repair candidate, but it does not receive execution authority merely because the text is plausible. Runtime code, schemas, evidence links, deterministic hardening, conformance checks, and tests decide whether the hypothesis can become a role artifact or an executable step.

In the current MVP:

- many readiness and field-trial paths are deterministic;
- L3.5 planner proposals must validate before execution;
- the external L4 profile defaults to `GigaChat-Pro` through `http://127.0.0.1:8000/v1` and can be overridden with `COGNITIVE_OS_L4_MODEL` / `COGNITIVE_OS_L4_BASE_URL`;
- the L4.5 intent/semantic fallback profile defaults to the lightweight GigaChat model id `GigaChat Lite` through the same OpenAI-compatible gateway and can be overridden with `COGNITIVE_OS_L45_MODEL` / `COGNITIVE_OS_L45_BASE_URL`;
- L4 calls remain explicit and use a controlled deterministic fallback when the configured cortex provider is unavailable;
- LLM outputs are advisory hypotheses or bounded role artifacts, not direct execution authority;
- L4 project interpretation records must distinguish raw model output from hardened output, including quality warnings, hardening actions, and whether the raw model output was clean.

The preferred replacement path is:

```text
LLM discovers.
Code repeats.
Contracts constrain.
Tests decide.
```

When a repeated LLM-backed pattern becomes machine-checkable, it should be promoted into deterministic code, a planner rule, a capability, a repair operator, or a conformance check. The LLM remains as an out-of-distribution fallback or semantic proposer, not as the default executor.

The upper layer is split into:

- `L4.0 Cognitive Control Plane`: deterministic policy, role transitions, artifact promotion gates, semantic-escalation decisions and crystallization backlog;
- `L4.5 Semantic Reasoner`: LLM or human-assisted reasoning for ambiguous goals, semantic trade-offs, unknown routes and new capability designs.

This is the "crystallizing cortex" rule: repeated decisions migrate from L4.5 into L4.0 policies, templates, gates or tests. Known routes stay in code; unknown or conflicting routes escalate. The same rule now applies to prompt-to-product flow: `PromptAdequacyGate` enters L4.0, and only a passed `prompt_product_gate` can trigger Stage 2 package construction.

L4.5 is represented as a bounded contract, not as an implicit model call. When L4.0 cannot route an otherwise bounded request, it may emit a `SemanticHypothesisRequest`:

```text
CognitiveControlPlaneDecision.semantic_escalation.l4_5_required=true
-> SemanticEvidencePack
-> SemanticHypothesisRequest
-> SemanticHypothesisProposal
-> L4SemanticValidationResult
-> optional SuccessfulResolutionCandidate / DeveloperImprovementRequest / clarification / stop / rework
-> optional SandboxAttemptSpec and FallbackAutonomyLoop sandbox verification for an existing route
-> optional SemanticProposalReplay
-> deterministic L4.0 gates
```

The request names allowed hypothesis types, forbidden actions, output contract and return path. L4.5 may propose an existing-route resolution, developer improvement request, template mapping, clarification, unsupported reason, legacy new template candidate, architecture option, risk interpretation, rework target or knowledge gap. It may not execute pipelines, edit source, mutate registry, build packages, promote capabilities or bypass L4.0/L3.5/L2 contracts.

L4/L4.5 are configuration-first layers. The active policy lives in
`config/runtime_interpreter_policy.json`: new prompt variants, roles,
role policies, interface combinations, architecture patterns and supported
bounded recipes should be expressed as configuration, registry, curriculum,
recipe or KB records by default. Python changes are reserved for reusable
interpreter primitives, safe adapter boundaries, validators, bug fixes and
verification harnesses. The explicit target is that at least 90 percent of new
task support at this layer should avoid Python-code changes.
Prompt intake markers and boundary groups live in
`config/prompt_intake_rules.json`; prompt-to-Stage-2-template routing lives in
`config/stage2_template_routes.json`; L4 prompt-to-product transition and
escalation reason rules live in `config/l4_decision_rules.json`; L4.5
existing-means mappings and developer request profiles live in
`config/semantic_resolution_rules.json`.

In the current implementation, `runtime/semantic_evidence_pack.py` first builds a bounded `SemanticEvidencePack` with prompt facts, failed gates, known templates, forbidden actions and explicit non-authority. `runtime/semantic_reasoner.py` then provides a deterministic runner for the request and an explicit model-backed mode through the configured OpenAI-compatible L4.5 gateway. The default model-backed L4.5 profile uses the lightweight GigaChat model id `GigaChat Lite`, intentionally separated from the larger L4 cortex profile. If a ready prompt has no supported template, intake is uncertain for a concrete bounded implementation prompt, or the prompt is a bounded behavior/limitation question, L4.5 first tries to map it to existing means. A successful mapping becomes `SuccessfulResolutionCandidate`, which can later become a KB/template rule only after repeated verified successes and review. `runtime/fallback_autonomy_loop.py` can then attempt that mapped existing route in the Stage 2 sandbox and run normal tester verification; this is the intended bridge between "LLM proposed a route" and "the system actually produced a verified package". If model-backed L4.5 misses a route that deterministic evidence can prove, hardening rescues the proposal as an existing-route candidate and records the rescue in audit fields. If existing means cannot solve the prompt, or the sandbox attempt fails, L4.5/Stage 2 emits `DeveloperImprovementRequest` for Codex/human implementation work; it does not immediately mutate templates or KB. Stage 2 CLI can request a real L4.5 model proposal with `tools/verified_system_package.py --use-l45-llm`; provider failure is captured in proposal hardening and falls back to deterministic proposal. Model output is normalized, forbidden actions are stripped, weak route misses may be rescued by deterministic evidence, and the proposal passes through `runtime/l4_semantic_validation.py`, which emits `L4SemanticValidationResult` with policy review and a human-readable explanation. Vague prompts and secret/live-risk prompts still route to clarification without developer work, unsupported product surfaces route to clarification, and no path mutates templates automatically. Otherwise the result becomes clarification, stop, rework, knowledge-gap recording, sandbox-verified package, or blocked output. `runtime/semantic_replay.py` can persist `SemanticProposalReplay` records for model/prompt/hardening comparison, and `runtime/l45_semantic_benchmark.py` plus `tools/l45_semantic_benchmark.py` run a deterministic semantic-loop benchmark. Model usage is explicit through quality modes: `deterministic`, `model_propose_only`, `model_with_human_review`, and `blocked_model_untrusted`.

Run the deterministic L4.5 loop benchmark:

```powershell
python tools\l45_semantic_benchmark.py --root . --write
```

Run the same corpus through the configured L4.5 model and compare:

```powershell
python tools\l45_semantic_benchmark.py --root . --use-model --model-quality-mode model_propose_only --write
python tools\l45_semantic_compare.py --deterministic-report artifacts\l45_semantic_benchmark\l45_semantic_benchmark_deterministic.json --model-report artifacts\l45_semantic_benchmark\l45_semantic_benchmark_model_propose_only.json --write
```

The current local trial corpus has 22 prompt-boundary and unknown-template cases. In the latest recorded run, deterministic routing passed `22/22`; the live propose-only run invoked the model on 13 escalated cases, matched deterministic action on 19/22 cases, passed L4 validation on 10/13 model proposals, and did not beat the deterministic route. The conclusion is intentionally conservative: use L4.5 as a bounded proposal source with replay and validation, then crystallize useful repeated patterns into L4.0 code.

For broader local field trials, generate a seeded matrix corpus instead of hand-maintaining hundreds of static cases:

```powershell
python tools\l45_semantic_benchmark.py --root . --generated-corpus-size 200 --seed 45 --write
python tools\l45_semantic_benchmark.py --root . --generated-corpus-size 200 --seed 45 --corpus-profile risk_heavy --write
python tools\l45_semantic_analytics.py --report artifacts\l45_semantic_benchmark\l45_semantic_benchmark_deterministic_generated_risk_heavy.json --write
python tools\l45_policy_gap.py --report artifacts\l45_semantic_benchmark\l45_semantic_benchmark_deterministic_generated_risk_heavy.json --write
python tools\l45_semantic_eval_suite.py --root . --generated-corpus-size 50 --profiles balanced risk_heavy unknown_template_heavy known_template_regression --write
python tools\l45_semantic_eval_suite.py --root . --generated-corpus-size 20 --profiles risk_heavy unknown_template_heavy --include-model --model-quality-mode model_propose_only --write
python tools\l45_model_failure_analysis.py --suite-report artifacts\l45_semantic_benchmark\l45_semantic_evaluation_suite_model.json --write
```

The curated corpus remains the default smoke/acceptance set. The generated corpus is intended for local/nightly measurement and can be resized while keeping reproducibility through `--seed`. Supported generated profiles are `balanced`, `risk_heavy`, `unknown_template_heavy`, and `known_template_regression`; analytics and policy-gap reports are typed artifacts used to prove that risky or unsupported prompts do not enter normal template backlog. The evaluation suite wraps those runs into `L45SemanticEvaluationSuiteReport`; model-backed runs remain opt-in and compare model proposals against the deterministic route without granting action authority. `L45ModelFailureAnalysisReport` groups blocked model cases by L4 validation failed codes.

If a deterministic schema, planner, or conformance path cannot produce a valid result, the system may ask an LLM for a bounded proposal. That proposal must re-enter the same validation path: Pipeline DSL validation for L3.5, hardened evidence checks for L4 interpretation, executable acceptance obligations for Tester, and conformance checks for Reviewer. A failed deterministic path is a reason to request a hypothesis, not a reason to bypass contracts.

Tester executable acceptance v0.3 turns `TestPlan.executable_acceptance` into a generated pytest scaffold and writes an `ExecutableAcceptanceResult`. The scaffold always executes obligation and boundary meta-checks; for simple `file.py:function` targets inside the project it also imports the function, calls it with sample kwargs from the positive contract case, checks the output shape, and verifies that malformed input is rejected. Classes, methods, async functions and framework handlers remain meta-checked until a later harness stage. Reviewer consumes the result through `TestResult.executable_acceptance_result` and blocks failed executable acceptance.

The deterministic L3.5 gate can be measured independently:

```powershell
python tools\spinal_benchmark.py --root . --write
```

The preferred design is provider-portable and local-first: projects should talk to a configured gateway rather than hardcoding external model API keys.

## Knowledge Gap Loop

When the system lacks a required fact, it should not invent it.

Instead, it creates a typed knowledge gap and collects bounded evidence:

```text
KnowledgeGap
-> allowed acquisition capability
-> KnowledgeArtifact
-> L4 decision based on evidence and confidence
```

Supported MVP evidence sources include installed-package probes, allowlisted official documentation fetches, and optional GitHub repository metadata. GitHub evidence is metadata/inspiration, not authority.

## Development Philosophy

Cognitive OS intentionally rejects several shortcuts:

- no hidden plugin-to-plugin orchestration;
- no registry mutation from L4 role output;
- no free-form text as machine protocol;
- no automatic self-training on the system's own answers;
- no silent benchmark rewriting to match current output;
- no promotion without sandbox build, tests, and explicit gate;
- no broad rewrite when a bounded extraction target is available.

The project grows by adding verified capabilities, better analyzers, stricter role artifacts, and reproducible field trials.

## Known Limitations

Current known limits:

- the general Programmer Executor blocks source apply; only explicitly approved, validated specialized sandbox packages can be applied through the reviewed backup-producing patch gate;
- Foundry candidates are not promoted without explicit approval;
- L4 external model calls are optional; the default `GigaChat-Pro` profile may fall back to deterministic behavior when its gateway is unavailable;
- analysis tasks are proposed backlog items, not automatic edits;
- native-heavy or non-Python-first projects may produce controlled `blocked` outcomes;
- local/domain helper bundling and instance-bound extraction are not fully supported yet;
- generated artifacts still require human review.

A controlled block is considered a valid outcome when the project cannot be safely transformed under current policies.

## Suggested Reading Order

Start with:

1. `COGNITIVE_OS_MANIFESTO.md` - core philosophy and layered model.
2. `COGNITIVE_OS_TECHNICAL_BASELINE.md` - engineering requirements and MVP architecture.
3. `MVP_RUNTIME_SPEC.md` - runtime and role implementation details.
4. `MVP_STATUS.md` - current readiness snapshot and known limits.
5. `POSITIONING.md` - why this exists alongside workspace/coding agents.
6. `EVALUATION_PLAN.md` - how to prove value against direct agent usage.
7. `ARCHITECTURE_HYPOTHESES.md` - which architectural claims must be proven, simplified or removed.
8. `PROJECT_ANALYZER_FIELD_TRIAL_SPEC.md` - first vertical field trial.
9. `RUNTIME_OPERATIONS.md` - runtime operation commands.
10. Role specs:
   - `ARCHITECT_SKILL_SPEC.md`
   - `SPEC_WRITER_SKILL_SPEC.md`
   - `IMPLEMENTER_SKILL_SPEC.md`
   - `TESTER_SKILL_SPEC.md`
   - `REVIEWER_SKILL_SPEC.md`

## Status

```text
Research preview / MVP field trial
```

The goal is not to claim general autonomy. The goal is to make the path from human intent to typed engineering interfaces explicit, inspectable, and safer than a free-form coding-agent loop.

## License

MIT License. See `LICENSE`.


