# Cognitive OS

**Experimental contract-driven runtime for turning human software goals into structured specifications, role artifacts, executable capability pipelines, sandbox implementation packages, tests, and review reports.**

Cognitive OS is an R&D project exploring a practical alternative to the common "one big agent does everything" pattern.

Instead of letting an LLM freely plan, execute, rewrite code, mutate state, and explain itself in one unbounded loop, Cognitive OS separates meaning, planning, contracts, and execution into explicit layers.

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

This repository is currently an **MVP / research preview**, not a production framework.

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
| Pattern translation, known-route planning, signals   |
| Validated planner proposals only                     |
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

## Key Concepts

### Crystal / Liquid Split

Cognitive OS uses a "crystal/liquid" split:

- **Crystal:** contracts, schemas, deterministic plugins, runtime state, queues, validation, and tests.
- **Liquid:** semantic interpretation, architecture decisions, unknown handling, and human-readable reasoning artifacts.

The liquid layer may decide what should happen next. It cannot bypass the crystal layer.

### Typed Artifacts

Important transitions are represented as explicit artifacts:

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
-> isolated generated package
-> tests
-> tester review
-> release decision
```

Current deterministic package classes include:

- JSONL log-filter CLI utility;
- text statistics CLI utility;
- FastAPI CSV aggregation service;
- FastAPI in-memory key/value CRUD service.

If tester review requests rework, Stage 2 uses a bounded contract debug loop:

```text
FailureAnalysis -> ReworkPlan -> sandbox repair -> verification -> tester review
```

This is not a free-form retry loop. Only allowlisted deterministic repairs are applied inside the isolated generated package.
The loop is acceptance-tested as a separate L4 programmer capability: a probe intentionally damages a generated FastAPI package, the tester flags the contract failure, and the loop applies a bounded repair before re-running project-scoped verification.
The same probe path also covers CLI input/output contract repair for generated file-processing utilities.
It also covers missing negative or edge-case evidence, such as empty text input and malformed JSONL fixture handling.

## Current MVP Status

Current snapshot: **MVP-ready for controlled analysis/planning, sandbox programmer-executor, Foundry, and verified-package field trials.**

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
- a general autonomous software engineer;
- a safe arbitrary-code auto-patcher;
- a replacement for human review;
- a self-learning system that treats its own outputs as ground truth;
- a multi-agent chatroom where agents debate until something happens.

Direct source patch application remains blocked in the MVP. The programmer executor creates isolated patch/test artifacts.

## Safety Model

The safety model is based on explicit boundaries:

- plugins are isolated capabilities with schemas and contract tests;
- plugin-to-plugin calls are forbidden;
- pipeline composition belongs to runtime, not plugins;
- registry mutation requires the controlled Foundry lifecycle;
- promotion requires explicit approval;
- L4 roles cannot execute pipelines or mutate registries;
- L3.5 planner output must validate through Pipeline DSL before execution;
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

In the current MVP:

- many readiness and field-trial paths are deterministic;
- L3.5 planner proposals must validate before execution;
- L4 may use deterministic fallback when no external cortex model is configured;
- LLM outputs are advisory or bounded role artifacts, not direct execution authority.

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

- direct source edits are blocked in MVP;
- Foundry candidates are not promoted without explicit approval;
- L4 external model calls are optional and may fall back to deterministic behavior;
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
5. `PROJECT_ANALYZER_FIELD_TRIAL_SPEC.md` - first vertical field trial.
6. `RUNTIME_OPERATIONS.md` - runtime operation commands.
7. Role specs:
   - `ARCHITECT_SKILL_SPEC.md`
   - `SPEC_WRITER_SKILL_SPEC.md`
   - `IMPLEMENTER_SKILL_SPEC.md`
   - `TESTER_SKILL_SPEC.md`
   - `REVIEWER_SKILL_SPEC.md`

## Status

```text
Research preview / MVP field trial
```

The goal is not to claim general autonomy. The goal is to make the path from human intent to engineering artifacts explicit, typed, inspectable, and safer than a free-form coding-agent loop.

## License

MIT License. See `LICENSE`.
