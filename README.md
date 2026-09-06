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

Code is not the only carrier of system knowledge. If requirements, architecture,
contracts, and acceptance criteria are explicit enough, an implementation can be
reproduced, checked, and improved as code generators evolve without changing the
architecture itself.

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

## Documentation Authority

When documents disagree, use this order of authority:

1. Runtime code, JSON contracts, and validated configuration define executable behavior.
2. `COGNITIVE_OS_TECHNICAL_BASELINE.md` is the normative engineering specification.
3. This README is the current operational overview.
4. `KB_COGNITIVE_OS_ARCHITECT_SUMMARY.md` is the dated architecture assessment and roadmap.
5. Timestamped reports under `artifacts/field_trials/` are measurement evidence for a specific run.
6. Curriculum verdicts, evaluation notes, and older status sections are historical evidence, not current runtime authority.

Readiness, role-by-project-type maturity, and production confidence are separate measures and must not be substituted for one another.

## Canonical Verification

Run `python tools/canonical_verify.py --root .` before a release or architecture checkpoint. The command uses project-local temporary directories and checks registry/config integrity, the 400-line source limit, compilation, the core test suite, and plugin contract tests. Use `--skip-tests` only for a fast structural preflight; it is not release evidence.

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

### Unified Entry Route

Normal user prompts should enter through one configured entrypoint:

```bash
python tools/cognitive_os.py --root . --prompt "..."
```

`tools/cognitive_os.py` calls `runtime/cognitive_os_entry.py`, which builds a
`CognitiveOSEntryRouteDecision` before any pipeline starts. The route decision is
selected from `config/cognitive_os_entry_routes.json`, using prompt adequacy,
Stage 2 template availability, optional `--project-dir`, and explicit mode. The
current configured pipelines are:

- `prompt_to_product`: `PromptAdequacyGate -> Stage2TemplateRoute -> VerifiedSystemPackage`
- `greenfield_architect_spec`: `UserPrompt -> ProductArchitectureRecord -> ProductTechnicalSpec`
- `project_foundation_analysis`: `ProjectMapReport -> ArchitectureDecisionRecord -> TechnicalSpec`
- `clarification`: `PromptAdequacyGate -> ClarificationPacket`

Older commands such as `tools/verified_system_package.py`,
`tools/greenfield_role_run.py`, `tools/role_foundation_run.py`, and
`tools/goal_run.py` remain useful as lower-level runners and diagnostics, but
they are no longer the intended product-facing dispatcher. This prevents Codex
or a human operator from silently choosing the first module by hand.

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

This is the practical meaning of the project philosophy: durable knowledge about
the system lives in requirements, architecture decisions, technical contracts,
test plans, review findings, policies, and evidence trails. Source code is an
important materialization of that knowledge, but it is not the only source of
truth.

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
| Implementer Planner | TechnicalSpec / ProductTechnicalSpec | `ImplementationPlan` | does not write code |
| Programmer Task Builder | ImplementationPlan | `ProgrammerTaskTree` | planning-only; decomposes target, gates and handoff |
| Sandbox Programmer | `ProgrammerTaskTree` + ImplementationPlan | `PatchPackage` + `TestResult` | sandbox/no-source-edit; LLM strategy is proposal-only |
| Tester | TechnicalSpec + ImplementationPlan | `TestPlan` | defines normal verification; executes only bounded recovery checks in the sandbox harness |
| Reviewer | spec + plan + tests + optional result | `ReviewFindings` | reviews, does not patch or promote |
| Researcher | audit/gap/failure evidence | bounded hypothesis + Architect gate | no patch authority; evidence remains provisional |

The normal artifact contour is `Project Analyzer -> Architect -> SpecWriter -> Implementer Planner -> Tester (TestPlan) -> Sandbox Programmer (PatchPackage/TestResult) -> Reviewer`. When no semantically safe candidate remains, the controlled recovery contour is `Reviewer -> Researcher -> Architect -> Developer -> Tester -> Architect`; it cannot bypass the normal Architect gate or human approval for source apply.
Foundation Roles 1-3 are scored only inside a selected **Python-owned boundary**. The promotion candidate does not claim primary ownership of C/C++/Rust/native implementation, frontend-owned product surfaces, or data/ML correctness beyond Python orchestration; those cases are either narrowed to a Python-facing adapter/package or marked `out_of_scope` for this contour.
The foundation contour must produce more than MVP-shaped placeholders:

- `ProjectMapReport` must contain source-backed purpose, boundaries, entrypoints, execution path, reusable capabilities, contract/data observations, errors/state/reproducibility notes, data lifecycle and a minimal extraction plan.
- `ArchitectureDecisionRecord` must turn those facts into subsystem boundaries with inputs/outputs, architecture options with tradeoffs, chosen/rejected decisions, rejected-option score deltas and deferral conditions, source-linked risks with impact/mitigation/evidence, data/state models and a typed brief for SpecWriter.
- `TechnicalSpec` must preserve the chosen scope as an API artifact: requirements, interface contracts, data lifecycle, error model, acceptance criteria, traceability, state/replay policy and bounded implementation handoff.
- Project type coverage is KB-driven. `knowledge/architecture_patterns/project_archetypes.json` contains scenario/input/output summaries for project archetypes such as SDKs, workflow runtimes, web frameworks, ML UI frameworks, scientific/media libraries, observability tooling, services, CLI tools and generic Python packages. Analyzer code interprets these records; new project types should be added as KB/config records and validated by field trials, not hard-coded as role branches.
- First-slice semantics are config-driven. `config/semantic_target_profiles.json` currently contains 272 contract-family profiles, including compute graphs, import graphs, crawler settings, workflow triggers, chat-template rendering, URL-query mutation, source-file parsing, framework dependency analysis, SSH connection boundaries, template project generation, runtime message dispatch, static-site build, web raw-data rendering, CLI option processing, pipeline registry composition, isolated build environment lifecycle, websocket protocol-send, plugin hook dispatch, package distribution-name parsing, SDK resource factory, dataset loading, app launch, data-expectation metric, SQL translation and tokenizer conversion boundaries. These profiles enrich ranking, contracts, validation gates and failure modes without adding role-specific Python branches.
- For untyped Python, SpecWriter may emit conservative inferred shapes such as `RequestLike`, `MappingLike`, `ParsedStructure`, `RenderContext` or `InferredValue`; it must not hand off raw `Any -> Any`. Inferred contracts are implementation obligations, not proof: Implementer/Tester must confirm or refine them with source evidence and negative tests.
- `TechnicalSpec.human_review` carries decision points, non-goals and review notes for people while the JSON artifact remains the machine API for the next role.
- `TechnicalSpec.extraction_contract.semantic_quality` is a separate advisory signal. It distinguishes a well-formed contract from an architecturally useful first slice and flags meta-infrastructure, runtime-boundary, trivial accessor and support/helper targets for review.
- `ArchitectRedTeamReport` is the deterministic handoff gate before SpecWriter. It rejects ADRs without option tradeoffs, explained rejected options, bounded source-backed first slice with selection policy, actionable risk model, actionable SpecWriter brief, source context for brief targets, source-linked traceability and explicit forbidden-action enforcement. An `ArchitectureDecisionRecord` is ready for SpecWriter only with `handoff_verdict=ready_for_spec_writer`.

Foundation corpus measurement and training are separate operations. Use
`tools/role_foundation_field_trial.py` for an immutable measurement, and use the
self-improving route when failures should become bounded training examples:

```bash
python tools/self_improving_foundation_trial.py --root . \
  --projects-dir artifacts/corpora/example --target-score 9.7
```

The self-improving route measures first, selects the weakest in-scope projects,
uses already-passing projects as regression cases, invokes Cognitive OS
diagnosis/trials, and verifies the corpus again. Successful KB experience is
staged as a candidate; it is not activated without promotion evidence.

When a measured hypothesis is promising but has too little independent evidence,
Cognitive OS now builds a portable `HypothesisValidationPlan`, discovers a
bounded reserve of unseen similar Python projects, freezes them under
`artifacts/hypothesis_holdouts/<hypothesis_id>/`, and validates the hypothesis on
only projects whose measured diagnosis matches both the staged
failure class and portable structural signature. Probe results are reused by training. This small adaptive
holdout is for one hypothesis; large blind corpora remain release/calibration
evidence. The current replaceable provider chain is `GitLab -> GitHub`; timeout,
rate limit or shortage at one provider automatically falls through to the next,
with cross-forge repository deduplication and recorded provenance. Exhaustion of
all working providers' candidate pools is a normal empty round; unavailability of
the complete chain is reported as a blocked discovery capability, not as a disproved
hypothesis. Every completed or blocked validation is persisted under
`artifacts/self_improvement/hypothesis_validation_*.json`. Use
`--no-hypothesis-discovery` only for fixed-corpus diagnostics.
Use `tools/foundation_transfer_exam.py` for an independent transfer check. Its
`freeze` phase creates a deterministic stratified train/holdout manifest with
repository and engine fingerprints; `run` records pre-training scores, permits
autonomous learning only from the train partition, and evaluates the unchanged
holdout afterward. Interrupted measurement stages leave a hash-checked checkpoint;
resume them with `run --resume`. An interruption during training rolls back its
promotion state and requires a fresh exam run.
`tools/hypothesis_compiler.py` reuses accumulated self-improvement reports without rerunning their projects. It groups
portable failure signatures, requires three independent projects, attaches existing-corpus counterexamples, and emits
typed `HypothesisCandidate` records for the plugin foundry. Optional local-LLM abstraction is hypothesis-only; strict
contracts reject code, patches, scoring changes and unbound evidence before any plugin trial.
Clusters without two consistent measured actions compile to a read-only `HypothesisEvidenceCollectionPlan`, not a
speculative runtime plugin. The evidence planner records the next bounded measurement and completion gate; only a
subsequent recompilation with sufficient independent support may request plugin implementation.
`tools/hypothesis_compiler_trial.py` dispatches compiled hypotheses through existing admission plugins and the plugin
foundry. Without `--promote` it performs read-only preflight; with `--promote` it requires a measured holdout, repeated
counterexamples and rollback on regression or incomplete execution before a candidate can enter KB. Timeout retries
repeat the complete gate with bounded config-driven budgets; they do not weaken evidence requirements. A final
repository regression command runs after each provisional promotion and restores all promotion KB snapshots on
failure.
If one reserve has fewer than two class-and-signature matches, Cognitive OS starts
the next bounded discovery round with a new frozen selection and excludes every
already probed repository. CLI progress reports every discovery round, probe and
holdout training transition.
Successive rounds also advance the provider page window instead of rescanning the
same star-sorted results (`1-2`, `3-4`, `5-6` with the default policy).
V22 carries per-query cursors across plan-version changes by normalized failure
signature. Existing expressions resume after their durable provider window, new
vocabulary starts at page one, and bounded query batches rotate between rounds.
GitHub qualifiers are translated to plain terms at the GitLab provider boundary.
Adaptive holdouts may use bounded provider-policy overrides such as a lower star
floor; release-corpus policy remains unchanged and independently stricter.
Exact probes from durable prior validation reports are re-measured from their
bounded local checkout after search-policy evolution. They remain excluded from
network discovery without losing valid accumulated evidence.
Discovery queries first compose configurable effect and output-basis terms, then
interleave their individual terms in
`project_evolution_policy.json`; adding a signature vocabulary does not require a
role or orchestrator source change.
V10 discovery uses those metadata queries only to freeze a wider candidate pool.
`runtime/hypothesis_structural_screen.py` then scans bounded product Python files
with the same source-contract inference used by the roles, ranks projects by the
portable signature's side effects and output basis, and freezes a smaller shortlist
in `structural_screen.json`. This report is retrieval evidence only: every selected
project still needs the complete role probe, exact failure-class/signature match,
training gate and admission checks. Pool size, scan limits, excluded directories,
weights and shortlist bounds live under `hypothesis_holdout.structural_prescreen`.
Portable signatures may also normalize syntax-level output evidence into a policy
family. V11 treats implicit no-value return and explicit `None` annotation as the
same `void_side_effect` contract while preserving raw evidence in probe reports.
V18 preserves the same strict admission rule while adding a structured diagnosis
envelope and auditable signature assessments. Near contrasts are retained as
negative evidence rather than silently discarded or incorrectly trained, and every
trial publishes retrieval yield and signature-discrimination metrics.
V19 adds normalized-family query vocabulary and keeps provider syntax out of
composite queries. It also rejects policy-defined high-risk additional effects from
otherwise compatible subset matches.
Repeated unresolved candidate-selection attempts across that semantic family emit
a `CapabilityDevelopmentRequest` for a bounded discriminator plugin.
The plugin catalog resolves that request through `ImprovementPluginFoundryReport`.
The discriminator may shadow-test only existing ranked, reselection, or ADR targets.
Confirmed contrast records now act as a non-authoritative prior for that bounded search: shared atomic structural
differences prioritize candidates with complete bodies, bounded inputs, and fewer runtime calls. The current project is
excluded from prior support, and every candidate still has to win an executable shadow trial. The lower search-support
threshold does not weaken the independent holdout, reproduction, regression, or promotion thresholds.
Validation requires at least one newly discovered match and trains it before prior
evidence projects. Clone work uses a bounded four-worker pool; one failed clone does
not block the remaining frozen selection.

Candidate-selection admission consumes the already measured control/treatment pair,
synthesizes structural policy from repeated paired contrasts, and requires regression
projects before promotion. Promotion is transactional: regression causes rollback;
a bounded sequence of evidence-derived refinements is allowed, and budget exhaustion
rejects the policy. Holdout and controls use the same complete execution-feedback route
as the outer corpus, with configurable repeated control verification. Shared trigger
constraints remain AND-ed across every OR alternative. A promoted rule enters normal
SpecWriter preflight and can request the existing Architect first-slice reselection loop
when approved scope hides a challenger; policy provenance is retained through that rebuild.
Repeated diagnosis-matched failures are returned as a typed
`CapabilityDevelopmentRequest`, rather than another manual project-search task.

Post-training admission runs after candidate trials, so it can consume the best
measured challenger. Raw KB candidates still cannot merge themselves. Only
registered improvement plugins may promote narrow allowlisted policy/config
targets, and only after repeated independent evidence, holdout improvement, no
role regression, unchanged source projects, and corpus-level rollback checks.
- `SpecWriterRedTeamReport` is the deterministic handoff gate before Implementer. It rejects weak `Any -> Any` contracts, side-effecting targets without validation/idempotency/process/retry gates, missing candidate acceptance, missing interface contract for the selected target, first-slice traceability gaps, and `TechnicalSpec.extraction_contract.candidate` values outside `ArchitectureDecisionRecord.first_slice_contract.targets`. A `TechnicalSpec` is implementation-ready only with `handoff_verdict=ready_for_implementer`.
- With `write=True`, the contour writes human-readable Markdown documents for review: `human_documents.architecture_analysis` and `human_documents.technical_spec`. These documents are reading surfaces over the typed JSON artifacts, not replacement protocols. `HumanRoleDocumentQualityReport` checks that they preserve the machine chain (`ProjectMapReport -> ArchitectureDecisionRecord -> TechnicalSpec`), Russian human-readable sections, evidence/traceability, validation gates, acceptance criteria, and implementation handoff.

Implementer Planner and Tester now have explicit curriculum gates. Implementer readiness is measured by `tools/implementer_curriculum.py`; Tester readiness is measured by `tools/tester_curriculum.py`. Both reports publish `avg_score`, `worst_case_score`, `ready_threshold=0.92` and `ready_by_worst_case`, and progression is judged by the worst project rather than by average score. Tester must preserve `writable_scope`, keep `evidence_scope` as read-only context, produce contract/negative/acceptance tests, and default filesystem/network/provider/subprocess boundaries to fake/fixture-backed tests.

Reviewer now has the same curriculum gate style through `tools/reviewer_curriculum.py`. It checks that `ReviewFindings` confirms target coverage, preserves scope, reports no contract violations or architecture drift, distinguishes residual risks from blocking rework, and uses worst-case readiness instead of average-only scoring.

Programmer Executor is split internally into `ProgrammerTaskTree` planning and sandbox programming. The task-tree builder decomposes the implementation target into bind-target, writable-scope, contract-input, acceptance and verifier-gate nodes, then hands that bounded tree to the sandbox programmer. The sandbox programmer emits an advisory `PatchStrategyProposal` in both `PatchPackage` and `TestResult`. The deterministic proposal classifies whether the next move is patch verification, fixture/profile refinement, contract rebinding, dependency-boundary profiling, or review blocking. If `COGNITIVE_OS_EXECUTOR_USE_L45_LLM=1`, L4.5 may add a hypothesis-only strategy proposal. A shape-valid `SandboxPatchCandidate` can be applied only inside an isolated sandbox and must pass the same verifier gates. If that verified sandbox attempt fails, Executor may request one bounded L4.5 repair hypothesis and apply it in a second sandbox; it still cannot mutate the source project or registry.

Greenfield prompts use a separate planning contour. A request such as "create a server" must not be forced through `ProjectMapReport -> extraction_contract` for an existing source tree. The supported planning path is:

```text
UserPrompt
-> ProductArchitectureRecord
-> ProductTechnicalSpec
```

`ProductArchitectureRecord` describes product scenarios, components, interfaces, data model, external boundaries, research hints, architecture options, chosen/rejected decisions, security policy, state/replay policy, risks and open questions. `ResearchHints` are advisory evidence requests, not claims that external research has already been performed. `ArchitectureOptions` force the architect to compare a chosen path with rejected alternatives, for example choosing an OpenVPN management/profile service over implementing the OpenVPN protocol in application code. `ProductTechnicalSpec` turns that into requirements, component contracts, primary contract, selected architecture option, error model, acceptance criteria and implementation handoff. This contour still does not write code or mutate the registry; it prepares reviewed architecture and ТЗ for the Implementer Planner.

Implementer Planner now has two explicit modes. For existing projects it consumes `TechnicalSpec.extraction_contract` and produces a bounded extraction/refactor `ImplementationPlan`. For greenfield prompts it consumes `ProductTechnicalSpec` and produces `implementation_target.mode=greenfield_project`, `greenfield_project_plan`, expected package files, component implementation units, adapter boundaries, fixture-first verification commands, dependency policy, acceptance mapping and sandbox-first `ExecutorHandoff`. This is still a plan artifact, not code generation and not permission to edit user source.

Open questions are also part of the machine contract. The default Architect mode is `continue_with_assumptions`: open questions are carried into the human architecture document, TechnicalSpec manual review section, risks and handoff, but the pipeline still proceeds to SpecWriter. For stricter intake, `tools/greenfield_role_run.py --question-mode ask_user` runs Architect only, writes `ProductArchitectureRecord`, returns `status=needs_clarification` and emits a `clarification_prompt` that can be shown to the user before generating `ProductTechnicalSpec`.

Greenfield architecture knowledge is configuration-driven. `config/greenfield_architecture_patterns.json` defines prompt markers, product summaries, components, contracts, research hints, architecture options, risks, open questions and acceptance focus for supported planning patterns such as OpenVPN service, FastAPI CSV aggregation, file converters, OCR/image CLI and JSON diff CLI. Python code interprets those records; adding a new greenfield architecture pattern should not require role-specific source edits.

A missing greenfield pattern is not treated as success. If Architect can only select `generic_product`, the planning contour stops before SpecWriter, records `greenfield_pattern_missing`, creates a bounded `SemanticHypothesisRequest` for L4.5, validates the returned proposal through L4.0, and emits `DeveloperImprovementRequest` when existing means are insufficient. `--use-l45-llm` may ask the configured L4.5 model for a hypothesis, but model output still cannot write code, mutate configuration, promote KB records or bypass the gate.

The same planning contour is available from the normal Stage 2 CLI without invoking Implementer:

```text
python tools/verified_system_package.py --root . --prompt "..." --planning-only
python tools/verified_system_package.py --root . --prompt "..." --planning-only --question-mode ask_user
python tools/verified_system_package.py --root . --prompt "..." --planning-only --use-l45-llm
```

Greenfield planning quality is measured by a dedicated corpus:

```text
python tools/greenfield_prompt_benchmark.py --root . --write
```

The benchmark checks Architect/SpecWriter artifacts only: selected pattern, required components, primary contract, open-question policy, expected research/option markers, forbidden actions and no source/registry/implementation mutation. It also attaches `GreenfieldArtifactQualityReport` for each case, checking that architecture/spec artifacts contain specific components, interfaces, data lifecycle, research hints, chosen/rejected architecture options, risk mitigations, error model, acceptance criteria, verification strategy and bounded handoff instead of generic placeholders. The quality gate now checks the human-readable Markdown too: architecture docs must include an explicit architecture decision, research hints, architecture options, first useful slice, assumptions before clarification, verification plan and open questions; TechnicalSpec docs must include implementation decision, selected architecture option, research hints, primary contract, data lifecycle, verification strategy and review questions. The current corpus contains 22 planning prompts.

Role identities, descriptions, capabilities, order, chain settings, builder settings and policies are not source-code constants. The active source of truth is `config/role_directory.json`. Its v2 entries also declare role contracts, gates, fallback policy, LLM policy, KB admission policy, stop conditions and quality criteria. Runtime code interprets that directory through generic loaders, `runtime/configured_role_pipeline.py` runs configured prefixes by artifact type, `runtime/role_operational_policy.py` validates operational completeness, `runtime/role_gate_runner.py` executes configured gates/quality criteria against produced artifacts, and `runtime/role_skills.py` exposes only `run_role_skill(role_id, **inputs)`. Legacy split files such as `roles/*.json`, `config/artifact_builders.json`, `config/role_artifact_pipeline.json` and `config/role_record_defaults.json` may remain as migration/import material, but they are not the active authority for which roles exist.

`RoleGateReport` is also a control artifact. It supports `advisory`, `strict`, and `release_required` modes: advisory mode records failed gates without blocking, strict mode blocks role-chain acceptance on failed gates, and release-required mode is the package/release gate that requires clean role artifacts before downstream promotion.

The same configuration-first invariant is now monitored directly. `tools/config_doctor.py` emits `ConfigDoctorReport` for loader and cross-reference integrity; `tools/config_coverage.py` emits advisory `ConfigCoverageReport` for templates, rules, transforms and sandbox profiles exercised by tests/trial registries; every `VerifiedSystemPackage` embeds a `RuleTrace` that names the config sources behind the decision; and `tools/config_mutation_sandbox.py` validates a proposed JSON config replacement without touching the active file.

First-slice target scoring is also configuration-driven. `config/semantic_target_profiles.json` stores semantic contract families, including ML generation, agent consensus and LLM repair hypothesis boundaries, while `config/target_quality_policy.json` stores the target-quality and SpecWriter-ranking policy groups used to reward bounded contracts and demote support, bootstrap, liveness, mutation and runtime-boundary candidates. `config/technical_spec_policy.json` stores SpecWriter source-scope, snippet-analysis, inferred type, side-effect boundary, semantic-rerank policy and strict first-slice scope enforcement: when Architect provides `first_slice_contract.targets`, SpecWriter must choose the best candidate inside that bounded set instead of widening the handoff from `spec_writer_brief`. `config/architecture_decision_policy.json` stores Architect fallback archetype/slice and source-selection policy. `config/architecture_synthesis_policy.json` stores architecture synthesis defaults: bottleneck ordering, task-focus priority, fallback first-slice shape, verification steps, defer policy and confidence thresholds. `config/foundation_semantic_quality_policy.json` stores the three-role semantic quality thresholds, generic-text guards, source-reference markers and minimum evidence counts used by the field-trial scorer. Runtime modules interpret these records; new recurring first-slice knowledge should be added as policy/profile data with regression evidence, not hardcoded into role logic.

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
-> GeneratedProductQuality
-> release decision
```

The `PromptAdequacyGate` is not only a report. It is an API input to the L4.0 control plane. Stage 2 now advances only when `CognitiveControlPlaneDecision.role_transition.next_action` is `build_verified_system_package`; vague prompts route to clarification, unsupported prompts stop, and bounded-but-unknown package requests can escalate to L4.5 as a hypothesis request without bypassing contracts. If intake is uncertain but the prompt still looks like a bounded implementation request, L4.0 emits `prompt_intake_uncertainty` and asks L4.5 to interpret it before a developer changes Cognitive OS. If the prompt is a bounded behavior or limitation question about a supported domain, L4.0 emits `behavior_question_uncertainty`; L4.5 must either answer from evidence or return a `DeveloperImprovementRequest` for fact-based behavior-question answering.

The user-facing result of Stage 2 is the generated working project directory, not the intermediate role artifacts. `GoalSpec`, `TechnicalSpec`, `ImplementationPlan`, tester review and other records are internal API artifacts between layers and roles. The release report now includes `GeneratedProductQuality`: a product-level gate with threshold `0.92` that checks runnable source layout, CLI/service entrypoint, visible input/output contract, controlled error paths, README run/test instructions, project-scoped verification, clean release directory and case-specific behavior. A package should not be presented as above-MVP ready only because files and tests exist.

Current deterministic package classes include:

- JSONL log-filter CLI utility;
- text statistics CLI utility;
- CSV sort CLI utility;
- OCR image CLI utility;
- image contents CLI utility with optional vision backend;
- image table to Excel/CSV/HTML/DOC/RTF CLI utility with injectable OCR/text backend, `--ocr-text-file`, optional OpenAI-compatible vision/OCR backend, stdlib XLSX writer, CSV writer, legacy XLS-compatible HTML writer, plain HTML writer, DOC-compatible HTML writer and RTF writer;
- generic file conversion CLI utility driven by `GenericFileConversionRecipe`, `LibraryBindingRecipe` and `AdapterImplementationPlan`, for prompts such as `.xls -> .png`, `.md -> .rtf`, `.txt -> .html` or `.jpg -> .doc`, with adapter boundary, advisory library candidates, implemented stdlib adapters where safe and dependency-free fixture tests;
- profile-gated news-site scraper CLI utility for prompts such as `https://3dnews.ru/ -> CSV`, with a `SiteProfile` contract, allowlisted `STRATEGY_REGISTRY` (`html_links`, `json_ld`, `rss_atom`, `sitemap`, `browser_dom`, diagnostic-only `api_probe`), optional known-host article patterns, generic unknown-host discovery, schema.org JSON-LD extraction, RSS/Atom fallback, sitemap discovery, bounded LLM fallback over fetched evidence, explicit `--browser auto|always|off` modes backed by an optional Playwright browser-render adapter for `browser_required` diagnoses, `NewsExtractionFailureReport` for unsupported/live-blocked pages, navigation/service-link rejection, fixture-first parser tests, stable CSV/Markdown/JSON contracts, bounded fetcher adapter, timeout/user-agent and optional live smoke only;
- web research summarizer CLI utility that accepts a search phrase, limits results to top 15, uses fixture-only tests by default, supports an explicit live JSON search endpoint adapter, extracts article text, summarizes results, and writes Markdown or JSON with source links;
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

Verified packages include a `ProgrammerSandboxGate` that records project directory presence, verification status, tester approval, and the invariant that user source and registries were not modified. They also include `GeneratedProductQuality`; this is the product-facing readiness signal for whether Cognitive OS produced a usable package at the current threshold.

For bounded implementation prompts that pass adequacy but have no supported deterministic package template, Stage 2 may invoke `runtime/llm_sandbox_implementation.py`. This is not free-form source editing: the model is treated as a hypothesis source, executable code is generated only from an allowlisted sandbox contract, verification runs inside `artifacts/llm_sandbox_implementations/*`, and the result keeps `promotion_allowed=false`. The allowlist is data-driven by `registry/sandbox_programmer_operations.json`; runtime validates stored `text_expression` operations with AST hardening and supports allowlisted stdlib profiles such as line sort/unique, CSV row count/sort/filter/select/sum/JSON records, HTML table to CSV, JSON extract/keys/pretty-print. If deterministic registry matching fails and `use_model=true`, the configured L4.5 profile may normalize the prompt to one existing `operation_id` from that registry; invalid ids, low confidence and provider errors remain controlled blocks. Each sandbox implementation plan now includes a `SandboxOperationGraph` from `runtime/sandbox_operation_graph.py`: a typed read/parse/transform/serialize/write/verify chain with parser/serializer choices, side-effect boundaries, evidence links, and invariants. The graph is an API artifact for L4/L4.5, programmer, tester and admission gates, not prose explanation and not an execution permission. The registry is configurable, but it is not an arbitrary-code execution channel. A verified sandbox result then passes through `runtime/sandbox_programmer_admission.py`; if tester/reviewer admission succeeds, Stage 2 may mark it `release_ready_with_risks` while still forbidding user-source, registry, and KB mutation. With `--write`, the success is also staged as a weak `KnowledgeCandidate` under `artifacts/knowledge_candidates`; repeated verified cases plus teacher/Codex approval are still required before any KB/template crystallization.

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

Current snapshot: **all eight measured roles pass their MVP contract gates, and the bounded deterministic/filesystem-read pilot has passed its independent blind transfer gate. The active frontier has moved from role completeness to supervised pilot operation and semantic-boundary validation. The product MVP target remains `Prompt -> Verified Local Automation Package`, with source mutation sandboxed and human-gated.**

The current aggregate gate index is `1.0` (8 of 8 measured roles MVP-ready) in `role_mvp_readiness_20260827T080846711504Z.json`. Treat this as contract readiness, not production confidence. Reviewer passes six adversarial artifact mutations, Planner passes its external gate, Executor has a mature input contract, and Researcher readiness is explicitly limited to bounded planning and quarantine.

The first executable transfer baseline exposed two general defects: optional callable factories were incorrectly assigned a strict missing-input negative case, and project/risk classification treated broad archetype prose and disabled side-effect switches as active evidence. After correcting those rules, the contaminated baseline corpus was used only for regression diagnosis. A newly frozen corpus then passed on its first run: `tw-legal-rag` and `cerberus` completed 2/2 executable full chains with two independent owner lineages, zero handoff loss, zero source changes, and eligible candidate admissions. The authoritative reports are `pilot_blind_confirmation_20260827_20260827T085921771186Z.json` and `pilot_transfer_trial_20260827T085921925543Z.json` under `artifacts/field_trials`.

This opens only the `deterministic_filesystem_read_pilot` profile in supervised `analysis`/`sandbox_patch` modes. Network, subprocess, stateful, concurrent, and provider-LLM risks remain prohibited; source apply remains disabled. It does not grant arbitrary-project or unattended production operation.

Reproduce a fresh transfer gate with a new corpus directory and iteration:

```powershell
python tools/github_blind_corpus.py select --root . --corpus-dir artifacts/github_pilot_blind_transfer_next --iteration 30 --policy config/pilot_blind_corpus_strata.json
python tools/github_blind_corpus.py clone --root . --corpus-dir artifacts/github_pilot_blind_transfer_next --iteration 30 --policy config/pilot_blind_corpus_strata.json
python tools/pilot_blind_transfer.py --root . --corpus-dir artifacts/github_pilot_blind_transfer_next --readiness-report artifacts/field_trials/role_mvp_readiness_20260827T080846711504Z.json --label pilot_blind_confirmation_next --write
```

Supervised operation is deliberately split into execution, human review, and telemetry. An automatic run can only reach `awaiting_human_review`; approval is stored in a new digest-bound artifact and never enables source apply:

```powershell
python tools/pilot_supervised_run.py --root . --projects-dir <pilot-projects-dir> --readiness-report artifacts/field_trials/role_mvp_readiness_20260827T080846711504Z.json --transfer-report artifacts/field_trials/pilot_transfer_trial_20260827T085921925543Z.json --write
python tools/pilot_review.py --root . --run-record <pilot-run-record.json> --decision approve --reviewer <reviewer-id> --note "review evidence" --write
python tools/pilot_telemetry.py --root . --run-record <reviewed-run-record.json> --write
```

Operational telemetry requires five reviewed runs, at least `0.8` first-pass acceptance, zero handoff loss, zero pending reviews, and zero source changes. Pending review, handoff loss, or any source mutation immediately produces `attention_required`. The initial zero-run snapshot is `artifacts/pilot/pilot_telemetry_20260827T091030436759Z.json` and correctly remains `insufficient_observations`.

Use `tools/pilot_review_queue.py` to turn multiple run records into a compact advisory decision surface. The first real five-project batch was reviewed as one approval, two reworks, and two stops. `pilot_telemetry_20260827T100335500605Z.json` confirms five valid digest-bound reviews, zero pending reviews, zero handoff loss, and zero source changes, but first-pass acceptance was only `0.2`. Generalized nested-mapping and attribute-unpack samples closed both reviewed rework cases diagnostically as executable callables. A new five-owner operational corpus then produced `0/5` first-pass in `pilot_run_batch_20260827T110808502633Z.json`: four eligible cases required rework and one filesystem/subprocess case was correctly outside the current profile. Human review confirmed `rework=4` and `stop=1`; `pilot_telemetry_20260827T112019244368Z.json` records five valid reviews, pending `0`, handoff loss `0`, and zero source changes.

The four rework cases now pass the configured Architect -> SpecWriter -> Implementer -> Tester -> Reviewer chain with bounded Executor feedback. Failed or meta-only executable evidence rejects the current target, Architect reorders source-backed alternatives by fixture readiness, and downstream target authority is clamped to the selected first slice before rerun. The matcher also derives scalar samples from normalized literal-membership contracts such as `value.lower() in [...]`. `operational_rework_feedback_status_final4_20260827_20260827T121440571185Z.json` records `4/4` executable callables, zero architecture drift, zero contract violations, zero source changes, and worst-case score `1.0`. A started harness is no longer treated as success when executable acceptance itself fails. These results are diagnostic closure of reviewed rework, not a retrospective change to first-pass telemetry. The next gate is a newly frozen unseen operational corpus followed by digest-bound human review; the pilot profile and source-apply prohibition remain unchanged.

That unseen gate is frozen at `artifacts/github_pilot_operations_unseen2_20260827` with five unique owners across three selected CLI and two selected library slots. `pilot_run_unseen2_20260827_20260827T121841223780Z.json` completed four full-chain cases as `ok` and one stateful CLI case as `needs_review`, with zero source changes and zero handoff loss. Runtime classification and admission remained independent of search strata: only deterministic `vertti__daffy` was eligible for approval, while provider/network, framework/plugin, data-platform/network, and stateful cases stopped outside the current profile. The digest-bound human decisions are complete as one approval and four stops.

Project recognition now occurs once, immediately after Project Analyzer and before Architect. `ProjectRecognitionDecision` records the authoritative classification, confidence, ambiguity evidence, role route, and pilot route, and is attached to ProjectMapReport as downstream role context. Risk inference combines archetype evidence with source-backed central-flow effects and pure-candidate presence; this distinguishes a deterministic CLI/library surface from `filesystem + memory_state` lifecycle risk even when both projects share an imperfect archetype label. Supervised pilot execution stops unsupported or ambiguous cases after recognition and does not run Architect or Executor for them; ordinary diagnostic full-chain probes remain unrestricted. `pilot_recognition_risk_unseen2_20260827_20260827T124300418371Z.json` confirms one full `ok` chain and four early `blocked_ok` routes with zero source changes.

Corpus discovery and project recognition are now separate stages. `python tools/project_corpus_qualification.py --projects-dir <dir> --expected-stratum <stratum> --minimum-qualified <n> --write` runs only language scope, Project Analyzer, and the recognition gate, preserves rejected search candidates, and emits the exact `qualified_projects` manifest before expensive role-chain execution. Analyzer confidence below `0.70` remains `ambiguous`; evidence-match confidence is no longer promoted above the Analyzer evidence. Broad KB rules for terminal rendering and code generation require source anchors, while documentation generators and package-publishing actions have explicit KB archetypes.

The qualified framework/plugin holdout is recorded in `framework_plugin_qualification5_20260827_20260827T130226559993Z.json`: five qualified projects from five owners, zero review cases, one preserved out-of-scope search result, and no replacement debt. After target/effect and executable-sample hardening, `framework_plugin_hardened5_final_20260827_20260827T144802017184Z.json` passed `5/5`, with worst-case quality `0.95`, executable acceptance `5/5`, zero contract violations, zero architecture drift, zero source changes, zero failed checks, and zero execution reselections. Cache invalidation/reload is now classified as `memory_state`; undeclared observed effects cap target quality and fail Reviewer conformance; mapping/introspection fixtures and source-path anchoring close the pdoc, publishing-action and pluggy execution gaps.

The independent owner holdout is frozen at `artifacts/github_framework_plugin_owner_holdout_20260827`. Discovery policy now supports explicit case-insensitive `excluded_owners`, and Project Analyzer treats root-document purpose markers as a distinct high-authority evidence channel instead of letting incidental dependency words dominate recognition. `framework_plugin_owner_holdout_ready_20260827_20260827T152026835684Z.json` qualified six of eight discovered projects; two ambiguous projects remained stopped. `framework_plugin_owner_holdout_full_chain_20260827_20260827T152226750638Z.json` records five complete executable chains and one controlled `blocked_no_safe_candidate`, with `5/5` executed acceptance passes, zero contract violations, zero architecture drift, and zero source changes. The role-specific confirmation `role_foundation_min_field_trial_20260827T152744316021Z.json` exposes the remaining gap instead of promoting the whole stratum: the five executable projects pass, while the stateful AutoDoc case scores Architect `8.33` and SpecWriter `6.47`. The next hardening target is the `Architect -> SpecWriter` handoff for stateful docs/codegen projects with no safe bounded first slice; mature Implementer, Tester, and Reviewer cells should remain regression-only.

The project-development contour now sits above recognition and the configured role chain. `tools/project_development.py` produces typed `ProjectDevelopmentDiagnosis`, `ProjectDevelopmentOptionPortfolio`, `ProjectDevelopmentDecision`, `ProjectDevelopmentOutcomeContract`, and an optional `Architect -> SpecWriter -> Implementer -> Tester -> Reviewer` handoff. With `--run-sandbox-experiment`, an allowlisted deterministic issue reducer may additionally produce `ProjectDevelopmentExperiment -> ProjectDevelopmentReassessment -> ProjectDevelopmentValidatedMemory`. Admission is fail-closed: unknown reducers, unaligned handoffs, non-ready implementation deltas, failed verification, out-of-scope patches, or a changed source digest cannot promote memory. Exhausted issue-aligned targets return `needs_replanning`; unknown, damaged, or dirty inputs route to research. The FORD holdout remains a useful negative control because its aligned plan has no supported patch pattern; `artifacts/project_development/project_development_20260827T194009645243Z.json` verifies `weak_contracts -> insert_required_input_guard`. Four bounded mixed-responsibility subtypes are validated: one inline `json.dumps` inside `write_text` (`project_development_20260828T021205600886Z.json`), one inline `json.loads` around `read_text` (`project_development_20260828T024351616482Z.json`), one inline `splitlines` call (`project_development_20260828T040000419241Z.json`), and one dict-literal mapping appended inside a loop (`project_development_20260828T062025813058Z.json`). Their two-site contrasts (`project_development_20260828T021221796243Z.json`, `project_development_20260828T024141759350Z.json`, `project_development_20260828T040036188331Z.json`, and `project_development_20260828T062101648866Z.json`) produce no patch and no memory. When several reducers are allowed, each is evaluated in a separate sandbox and exactly one must be prepared. The mapping reducer additionally requires one mapping site whose loaded names are exactly the simple loop variable and whose accumulator is the function's sole returned value. A loop-local conditional field is validated by `project_development_20260828T070645103118Z.json`; the external-fallback contrast `project_development_20260828T070723270674Z.json` produces no patch or memory because an additional free variable would widen the helper contract. The adjacent `record = {...}; accumulator.append(record)` shape is validated by `project_development_20260828T072338364901Z.json`; its temporary must have exactly one store and one load, so the reuse contrast `project_development_20260828T072433082449Z.json` fails closed. The config-backed `maximum_mapping_fields=12` edge is validated by `project_development_20260828T080840365016Z.json`; the 13-field contrast `project_development_20260828T080915669163Z.json` produces no patch or memory. The nearest loop must be a synchronous `for` with no enclosing `for` or `async for`: `project_development_20260828T083944554908Z.json` validates the simple-loop path, while nested-loop contrast `project_development_20260828T084003587919Z.json` produces no patch or memory. Broader mapping and other pure-helper shapes remain outside development authority. Source apply and automatic KB promotion remain disabled.

```powershell
python tools/project_development.py --root . --project-dir <python-project> --goal "Understand the project, identify its highest-value evidence-backed deficiency, and prepare the smallest safe development experiment" --run-sandbox-experiment --write
```

Failed sandbox experiments now emit typed `ProjectDevelopmentExecutionFeedback` instead of ending at a generic non-validated status. Config-backed classification routes `no_unique_development_helper_extraction`, cross-reducer ambiguity, and `*_pattern_not_proven` to `research_required` with `Researcher -> Architect`; a prepared patch that fails verification returns `needs_replanning` to Architect; unknown or admission failures produce `controlled_stop`. Feedback preserves the selected target evidence and reducer attempts while forbidding automatic retry, scope expansion, and source apply. Durable negative run `project_development_20260828T090705601690Z.json` demonstrates the research route with memory `not_promoted`; validated contrast `project_development_20260828T090747254502Z.json` emits `not_required/completed` feedback and verified memory.

Research feedback now has a read-only continuation through typed `ProjectDevelopmentResearchHypothesis`, `ProjectDevelopmentArchitectFeedbackDecision`, and `ProjectDevelopmentFeedbackContinuation`. Researcher resolves only the feedback target, records bounded AST facts, and proposes an allowlisted hypothesis kind. Architect can decide only `replan`, `research_more`, or `controlled_stop` after source identity, confidence, and no-retry checks. Nested mapping report `project_development_20260828T093240287559Z.json` demonstrates `research -> nested_loop_mapping_boundary -> replan`, yielding top-level `needs_replanning` with `executor_rerun=false` and memory `not_promoted`. Validated contrast `project_development_20260828T093325940127Z.json` keeps continuation `not_required` and memory validated. Continuation does not create an ImplementationPlan, invoke Developer, or retry Executor.

Architect `replan` is now materialized as typed `ProjectDevelopmentReplanRevision`, not as execution. It preserves the authority `ProjectDevelopmentDecision.selected_option`, increments Decision and OutcomeContract revisions by exactly one, keeps the original target and required checks, and changes only the planning adjustment and expected research outcome. Missing baselines, target drift, check drift, or execution-enabling policy produce a blocked revision and `controlled_stop`. Durable report `project_development_20260828T100823826409Z.json` records planning-only revision `2` for `nested_loop_mapping_boundary` with `execution_authorized=false`, no Developer handoff, no Executor rerun, unchanged source, and memory `not_promoted`. Validated contrast `project_development_20260828T100905579561Z.json` keeps `replan_revision=null`.

A valid replan revision now emits `ProjectDevelopmentBoundedExperimentProposal` and passes a separate `ProjectDevelopmentBoundedExperimentAdmission`. This gate admits planning only: one primary target plus at most one immutable allowlisted contrast source, at most three evidence requirements, zero execution runs, zero source changes, and a closed read-only action set. Target drift, contrast identity drift, evidence budget overflow, missing stop conditions, unallowlisted actions, or any execution authorization block the proposal. Durable report `project_development_20260828T104947964126Z.json` records the original planning admission; the current source-paired evidence is recorded by the later report below.

An admitted proposal is executed by an embedded read-only Researcher and returned as `ProjectDevelopmentBoundedExperimentEvidence`; Architect closes it with `ProjectDevelopmentArchitectEvidenceDecision`. The collector reads the primary target and one digest-pinned in-workspace contrast, records both SHA-256 values before and after, uses no network or subprocess, and emits at most three observations. Nested-loop characterization now uses paired source AST: the nested negative and validated simple-loop positive are both source-backed. This is bounded implementation evidence, not KB-promotion evidence, so acceptance leads only to `human_review_bounded_implementation_candidate`. Durable report `project_development_20260828T113702427711Z.json` records the paired evidence, unchanged sources, zero execution authorization, and memory `not_promoted`. Validated contrast `project_development_20260828T113733891395Z.json` keeps evidence and Architect closure null.

Paired evidence now produces `ProjectDevelopmentImplementationApprovalRequest`, bound to the canonical evidence SHA-256 and proposal identity. A separate `ProjectDevelopmentHumanApprovalDecision` can be supplied with `--human-approval`; runtime records `ProjectDevelopmentImplementationApprovalValidation` before materializing `ProjectDevelopmentBoundedImplementationCandidate`. Missing approval remains `pending`; reject, authority mismatch, request mismatch, or digest replay cannot create a candidate. Even approved candidates are `approved_not_executable`, with Developer, Executor, source changes, and memory promotion still forbidden behind a separate future design admission. Durable report `project_development_20260828T115407964184Z.json` is the real pending request; no approved report was fabricated without a human decision. Validated contrast `project_development_20260828T115440020888Z.json` keeps all approval artifacts null.

An approved candidate can produce `ProjectDevelopmentImplementationDesignRequest`, checked by `ProjectDevelopmentImplementationDesignAdmission`. An explicitly supplied `ProjectDevelopmentImplementationDesign` is then checked by `ProjectDevelopmentImplementationDesignValidation` against candidate, proposal, evidence, target, and source-snapshot identities. The design permits only interface boundary, transformation steps, acceptance mapping, and rollback strategy; forbidden output keys are rejected recursively. Source patches, ImplementationPlan, executor tasks, automatic role invocation, execution, and memory promotion remain forbidden. The historical pending report `project_development_20260828T120640182121Z.json` correctly contains no candidate or design artifacts; the current human-approved design is recorded in `artifacts/project_development/project_development_20260831T080044961164Z.json` as `accepted_not_executable` with its own canonical digest.

Implementation is a separate digest-bound lane. `ProjectDevelopmentImplementationAuthorizationRequest` binds the accepted design, evidence, target source snapshot, and relevant execution-policy digest; `ProjectDevelopmentImplementationAuthorizationDecision` and `ProjectDevelopmentImplementationAuthorizationValidation` authorize at most one sandbox-only run. The strict `preserve_exception_constructor_reconstruction` operator requires the exact custom-exception constructor shape, rejects an existing reconstruction method or state, and cannot enter the global failure-reducer catalog through this run. `artifacts/project_development/authorized_implementation_20260831T081035446426Z.json` records the first real result: targeted pickle replay passed, the full pytest-socket suite passed with `103 passed, 9 skipped`, only the approved sandbox source file changed, no generated stub appeared, and the original project digest stayed unchanged. This is one supervised verified transformation, not autonomous execution or KB promotion.

The second supervised transfer is `urllib3.LocationParseError`. Corpus audit first exposed a semantic defect hidden by an upstream type-only pickle assertion: reconstruction preserved the class but changed `location` and prefixed the message twice. The matcher now excludes local inherited reconstruction hooks, removing the false-positive isort lineage. The design-bound `reuse_direct_assignments` recipe may only replay constructor inputs already stored by exact `self.<attribute> = <input>` assignments. `artifacts/project_development/authorized_implementation_20260831T110602578287Z.json` records semantic equality, the parametrized targeted test (`17 passed`), the bounded exception regression (`19 passed`), one changed sandbox source file, no stubs, unchanged corpus source, and no promotion. The supervised ledger is now `2/3`; autonomous transformations remain `0/3`.

The third supervised transfer is `python-redmine.UnknownError`, selected from the existing exposed corpus without downloading new projects. Direct semantic evidence showed that pickle replay preserved the type and `status_code` but duplicated the rendered message. The same `reuse_direct_assignments` recipe inserted only a local `__reduce__` in the sandbox. `artifacts/project_development/authorized_implementation_20260831T115835185733Z.json` records semantic equality, targeted replay (`1 passed`), bounded regression (`405 passed`), no generated stubs, one changed sandbox source file, and unchanged original source. The runner now removes sandbox-only `build/lib` files produced by local wheel builds before scope comparison. The supervised ledger reached `3/3`; this satisfies the supervised threshold but still does not enable autonomous execution, source apply, or KB promotion.

Promotion readiness is now explicit. `tools/exception_pickle_promotion_readiness.py` reads the supervised ledger plus implementation reports and emits `ExceptionPicklePromotionReadiness`. The current report `artifacts/project_development/exception_pickle_promotion_readiness_20260831T124021424040Z.json` is `eligible_for_promotion_review`: three independent supervised projects and targets are verified, one independent autonomous shadow case has project-native semantic replay evidence, and semantic/native/stub/source gates pass. It deliberately keeps `kb_promotion_allowed=false` because direct promotion from readiness is forbidden.

The holdout/autonomous/evaluator gates are now materialized. `exception_pickle_holdout_transaction_20260831T124242422603Z.json` finds 586 applicable holdout candidates across 229 projects, passes the focused regression slice and Config Doctor `44/44`, and keeps source apply / KB promotion / autonomous activation false. `exception_pickle_autonomous_shadow_20260831T123815742912Z.json` lets Cognitive OS choose and patch `anyio.BrokenWorkerInterpreter` in a sandbox, then imports the patched project module and verifies pickle roundtrip state fidelity. `exception_pickle_independent_evaluator_20260831T125714581827Z.json` independently confirms the autonomous case is not one of the supervised projects and that no source or KB mutation occurred during evaluation.

The manual promotion transaction `exception_pickle_promotion_transaction_20260831T132156422950Z.json` passed `20` focused regression tests plus Config Doctor `45/45` and activated `knowledge/role_knowledge/exception_pickle_reconstruction_patterns.json`. The promoted pattern remains narrow: `preserve_exception_constructor_reconstruction` with `__reduce__`, `reuse_direct_assignments`, stored constructor inputs only, maximum four required inputs, existing reconstruction hooks blocking, generated stubs forbidden, sandbox patch required, source apply disabled and automatic runtime mutation disabled. The active catalog is now consumed by the boundary interpreter as an overlay, so future matching sees this boundary as `active` with `validated_active` operator authority while still requiring sandbox verification. The operator is propagated through `ProjectDevelopmentBoundedExperimentProposal`, `ProjectDevelopmentBoundedImplementationCandidate` and `ProjectDevelopmentImplementationDesignRequest` as a suggested implementation recipe; design validation blocks if Architect changes that recipe.

The active-application contour now records post-promotion reuse separately from promotion. Follow-up passes have raised the active application ledger to `applied=178`, `blocked=414`; recent accepted targets include `maxteabag__sqlit / CredentialsStoreError`, six `ctripcorp__flybirds` exceptions, `setuptools / LinkOutsideDestinationError`, `calf-ai__calfkit-sdk / ToolRetryError`, two `leptonai__leptonai` API errors, two `aiohttp` connector errors, `mercadopago__sdk-python / InvalidWebhookSignatureError`, `eddyzzl__marvis-risk-agent / IllegalTransition`, three CPython `tarfile` destination/link errors, `not-sekiun__consortium / AgentGeneratorBuildStepOverridesFinalMethodError`, `abhinavsingh__proxy-py / ProxyConnectionFailed`, `dj-bolt__django-bolt / ComponentNameCollisionError`, `pybotters__pybotters / OutOfBoundsError`, two `shy3130` tickflow `CapabilityDenied` targets, two `nats-io__nats-py` client errors, `nerevu__riko / PipelineStateError`, `withceleste__celeste-python / UnsupportedParameterError`, `reloadware__reloadium / RedefinedVarError`, two `benoitc__gunicorn` stash errors, `vonage__vonage-python-sdk / PartialFailureError`, `software-mansion__starknet-py / OutOfBoundsError`, `reloadware__reloadium / NoTypeError`, `supabase__supabase-py / StorageApiError`, `disnakedev__disnake / MaxConcurrencyReached`, `mosaik__mosaik / InvalidNextStepTypeError`, `nextcord__nextcord / MaxConcurrencyReached`, two `rapptz__discord-py` command errors, and `treeverse__dvc / BaselineMismatchError`. The blocker taxonomy covers constructor replay mismatch, unavailable dependency/import replay, unsupported semantic samples, behavior mismatch, sandbox-copy failure and static patch shape. The materializer hardening added primitive, path, exception, process-error, named-object, cooldown-like, bounded method-object and source-aware sliced-string/rendered-body sample forms, plus `topics`, `domain`, `service`, `bucket`, string-membership, `.lower()`, source-backed attribute-object samples such as `.name`, `.content`, `.tool_name` and `.value`, bounded nested data objects such as `request.settings.ERROR_URI`, richer `connection_key` samples, recursive nested named-object replay, CPython `frozendict` replay compatibility, `types.GenericAlias` replay shim and suffix-based `*_filepath` string samples. The replay subprocess now injects sandbox import paths only after stdlib bootstrap, so local files such as `src/types.py` cannot shadow stdlib modules before compatibility shims are installed. The patcher admits stored-state constructors whose single `super().__init__` call has zero or multiple arguments, and any direct-state keyword-only constructor case through an explicit state-only `BaseException.__new__` reducer flag. Self-referential exception args such as `super().__init__(self, message)` are normalized in semantic replay only when class state still matches, stdlib imports are never target-stubbed, same-package absolute imports can be stubbed directly, and readmission is blocked for target files with imported attribute-base class definitions. `exception_pickle_object_contract_audit_20260902T095949529132Z.json` and `exception_pickle_object_contract_admission_20260902T100010126192Z.json` closed the source-backed object-materializer tail enough to admit four additional replay candidates while keeping opaque contracts held. `exception_pickle_blocker_intelligence_20260903T065159200878Z.json` classifies the latest-blocker frontier at 146 cases; the sample-supported readmission frontier is 0, class-state contract research is separated at 6 cases, and import/dependency isolation is still the priority lane at 25 cases. The import-isolation summary splits those 25 into dependency unavailable 9, import failed 5, attribute-base/metaclass risk 10 and one dependency-heavy sample-supported case, with direct-file replay preferred for 14; missing-import kinds are external dependency 11, project-local dependency 2 and stdlib symbol compat 2. Top recurrent missing import is now `librt` at 2; `authlib`, one `yarl` target and one `voluptuous` target were closed, while report-only probes marked `aiohttp`, `async_timeout`, `sqlalchemy`, `app` and `common` as diagnosis-required rather than direct-write clusters. The reproducible batch selector `--import-isolation-batch-profile dependency_heavy_direct_file` narrows external-dependency work to direct-file preferred targets with target replay risk `<=3`; `--import-isolation-cluster` further limits a pass to one dependency cluster. Batch-run policy adds `--maximum-accepted-applications`, records `selected_applications`, reports `stop_reason`, and `--write-report` persists probe evidence without updating the ledger. The latest project-local exact-target writes accepted `langchain-ai__langchain / SSRFBlockedError`, `shy3130__tick-stock-panel / JobCancelledError`, and `astronomer__agents / NotFoundError` after a report-only project-local batch probe. Report-only probes are now persisted with `--write-report` without ledger mutation; saved probes marked `aiohttp`, `async_timeout`, `sqlalchemy`, `app` and `common` as failed direct-file probes, while planner report `exception_pickle_import_cluster_planner_20260903T065218069738Z.json` marks the next `unknown:attribute_base_metaclass_risk` cluster as `not_batch_ready` with `class_state_contract_research_before_replay`. Failed-probe analyzer `exception_pickle_failed_probe_analyzer_20260903T065213416880Z.json` classifies 2 latest failed probes and now recommends `constructor_state_contract_research`; behavior-contrast, reprobe and replay-capture repair lanes were closed by this cycle. Mapping-object admission is implemented for bounded literal-key contracts, and method-object admission is limited to source-backed zero-arg methods with safe return profiles. The active-application CLI also has `--maximum-replay-blockers`, `--only-readmission-frontier`, `--only-import-isolation-frontier`, `--import-isolation-missing-kind`, `--readmission-subtype`, precheck-aware ordering, patchability dry-run ordering, dependency-light replay ordering, per-project static-patch blocker budgeting, per-project replay blocker budgeting and true no-ledger-update dry-run when `--write` is absent. Import/dependency isolation preserves package context during direct-file replay without executing package `__init__`, adds relative-import target stubs, uses hashable enum-like stub values, treats stdlib imports as non-target stubs, and uses residual target-file side-effect risk for direct-file/stub replay. LLM support is intentionally advisory-only (`--use-l45-llm`), cannot grant source apply, and cannot promote KB. Every accepted case changed only the sandbox target file, introduced no generated stubs, preserved semantic replay state, and left original source unchanged.
Latest sync marker: `exception_pickle_active_application_20260903T065054426561Z.json` latest exact-target repair ledger accepted `astronomer__agents / astro-airflow-mcp/src/astro_airflow_mcp/adapters/base.py:NotFoundError.__init__` after exact promotions for Alembic range/head errors, JMComic base error, two Redis HTTP errors, Pact interaction verification, Discord command invoke and GraphQL WS response errors; latest intelligence `exception_pickle_blocker_intelligence_20260903T065159200878Z.json` uses latest-blocker frontier accounting and reports `applied=178`, ledger `blocked=414`, latest-blocker frontier `146`, readmission frontier `0`, next lane `import_dependency_isolation_candidate:25`; latest planner `exception_pickle_import_cluster_planner_20260903T065218069738Z.json` marks `unknown:attribute_base_metaclass_risk` as `not_batch_ready`; latest failed-probe analyzer `exception_pickle_failed_probe_analyzer_20260903T065213416880Z.json` recommends `constructor_state_contract_research`. The current cycle also closed the `graphql`, `overrides`, `platformdirs` and `pydantic_settings` one-target clusters; Chroma exposed and verified narrow `dir`/`version` materializer coverage plus decorator-factory stub replay. The current cycle also closed `volcengine` and `vonage_jwt`; Volcengine verified `missing_services` list samples, and Vonage verified a bounded response-object sample with `status_code`, `url`, `content`, `text` and `json()`. The current project-local cycle added `project_local_direct_file`, filters out attribute-base and target self-attribute-gap cases, scopes failed-probe evidence by profile/cluster, and promoted `langchain-ai__langchain / SSRFBlockedError`, `shy3130__tick-stock-panel / JobCancelledError`, and `astronomer__agents / NotFoundError`; stub path joins now use the platform temp directory and `endpoint` string samples are supported. Class-state audit `exception_pickle_class_state_contract_audit_20260903T070847705234Z.json` splits the 10 attribute-base/metaclass-risk cases into 7 `base_constructor_passthrough_contract`, 2 `attribute_base_state_contract`, and 1 `target_self_state_gap_research`; the next narrow lane is parent-constructor argument/state preservation research before replay. Source line-limit audit `source_line_limit_audit_20260903T230204065085Z.json` now passes across the scanned Python corpus: 1513 Python files checked, 0 files exceed the 400-line limit. Post-split audit `post_split_audit_20260903T230640450590Z.json` records 24 mechanical facades and 55 helper-backed tests as design-debt inventory. The final cleanup kept runtime clean, split the two remaining tool probes behind stable facades, split the project-map domain-profile plugin tests, and moved oversized runtime test suites into helper-backed context-bounded test modules. This records the 400-line rule as enforced for runtime, tools, plugins and tests, not as optional refactoring guidance.
Derived-message sync marker: `exception_pickle_derived_message_audit_20260902T045536203364Z.json` reports 0 derived-message cases; source apply and KB promotion remain false.
Derived-import sync marker: `exception_pickle_derived_import_audit_20260902T045554559495Z.json` reports 0 derived import-isolation cases; source apply and KB promotion remain false.

Project-development boundary knowledge is now configuration-first. Staged hypotheses, typed source-fact predicates, confidence, research strategy, evidence requirements, and paired-shape rules live in `knowledge/role_knowledge/project_development_boundary_profiles.json`; immutable source contrast identity and provenance live in `knowledge/role_knowledge/project_development_source_contrasts.json`. `runtime/project_development_boundary_interpreter.py` evaluates only the closed `eq | gt | suffix` predicate language and fails closed to a knowledge-gap fallback. The frozen six-case corpus under `benchmark_corpora/project_development_boundaries` includes two blind cases and six lineages; its field trial must remain `not_promoted` until the independent-report and no-regression promotion gates are also satisfied.

Role-by-project-type development uses an explicit sequencing lane. The historical pre-certification matrix initially left Implementer, Tester, and Reviewer at `usable` because its evidence was limited to bounded derived transformation contracts. That gap is superseded by the 2026-09-04 narrow certificate described below: all 12 required cells for `cli_local_tool` and `library_pure_transform` are now certified at `9.7+` on disjoint multi-lineage evidence. Web/API, provider SDK, framework/plugin, data/scientific/ML, async, stateful, external-I/O, and LLM/multi-agent strata remain required deferred work.

The historical foundation gap was `SpecWriter x cli_local_tool = 9.6` on `dbcli__pgcli`. Its source-isolated bound-method harness incorrectly treated synthetic `receiver_state` as required user input; strict-negative analysis now excludes that key only for method-owned fixtures, while explicit receiver-state contracts remain strict. Fresh foundation reports plus independent `black` and `cattrs` reports close that multi-project threshold. The stricter consolidated matrix `role_project_type_evaluation_20260828T134957310326Z.json` no longer lets derived mutation benchmarks claim project-native downstream maturity: it records 38 mature cells and exposes `minimum_project_native_transformations` as the current narrow-lane gap.

Project-development diagnosis now includes AST/token-aware `SourceIncompletenessEvidence`. A sole `pass`, `raise NotImplementedError`, `TODO`, broad function, risky import, or security-shaped filename is an observation, not defect authority. The classifier separates marker exception types, abstract/interface boundaries, deliberate exception suppression, declared future work, and ambiguous stubs; promotion to an actionable contract failure requires a target-bound failing test, executable acceptance failure, or explicit user failure. High and medium project risks likewise require scanner/runtime/test authority. External Comfy CLI report `project_development_20260828T173504992818Z.json` is the current negative control: it retains the `CustomNode` TODO, auth/oauth signals, and structural hotspots, but returns `issue_count=0`, `controlled_stop`, no role-chain execution, no source changes, and no memory promotion.

Project recognition also distinguishes product identity from internal capability. When CLI entrypoint identity correctly overrides an incidental parser/library domain signal, `effective_project_identity=cli_local_tool` and `project_archetype_scope=internal_capability`; downstream routing uses the former instead of presenting both labels as competing project types.

Project-development diagnosis also separates structural observations from actionable failures. Untyped functions, mixed-responsibility heuristics, medium-risk imports, and noisy test fixtures remain visible, but they require a source/test/runtime/user failure authority before they can create an issue or authorize a role chain. External `black` report `project_development_20260828T140228581495Z.json` demonstrates the boundary: zero actionable issues, no role execution, no patch, no memory promotion, and unchanged source.

`pilot_telemetry_20260827T124315374515Z.json` confirms five valid reviewed digests, pending review `0`, handoff loss `0`, and source changes `0`. Telemetry now separates breadth from execution quality: overall first-pass and admission coverage are `0.2`, in-profile first-pass is `1.0`, and controlled-stop precision is `1.0`. Its status remains `attention_required` because the unchanged `0.8` breadth threshold is not met. The pilot remains blocked from broader automatic admission, but its recognition, review, and safety control plane is operationally complete.

Verified areas include:

- plugin catalog, schemas, and contract tests;
- pipeline execution, checkpointing, process boundary, and worker queue;
- Capability Registry and Contract Registry validation;
- controlled interrupt, quarantine, and fallback paths;
- Foundry spec/candidate/dry-run promotion path;
- deterministic known-route planner and project signals;
- Project Analyzer, Architect, SpecWriter, Implementer Planner, sandbox Programmer Executor, Tester, and Reviewer readiness gates;
- no-safe-candidate controlled recovery, AST-only recovery pattern audit, differential verification, digest-bound approval, and rollback;
- Researcher hypotheses with an explicit Architect evidence gate for network, subprocess, and structured-stream boundaries;
- evidence-only semantic boundary experiments; all four current families remain blocked from Developer handoff;
- a fail-closed deterministic/filesystem-read pilot profile with source apply disabled;
- an independent executable pilot transfer gate with frozen selection, unique owners, and per-candidate admission decisions;
- advisory memory/dialogue context;
- Knowledge Gap Loop for installed packages, official docs, and optional GitHub metadata evidence;
- human-readable architecture analysis documents generated by role pipelines.

These checks mean the deterministic planning and sandbox execution gates passed. They do **not** mean the system is generally intelligent, self-learning, or safe to let loose on arbitrary projects without review.

### Direct Provider Migration Sandbox

Legacy provider migration is handled as a reviewed sandbox package, not as direct source editing. The historical `map` field trial used a GigaChat-specific sandbox patch generator; it remains as archived trial evidence, but it is not part of the current default L4/L4.5 provider path. New provider-backed trials should use the configured LLM profile in `config/llm_profiles.json` or an explicit CLI/env override:

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
- the external L4 profile is configured through `config/llm_profiles.json` and can be overridden with `COGNITIVE_OS_L4_MODEL` / `COGNITIVE_OS_L4_BASE_URL`;
- the L4.5 intent/semantic fallback profile defaults to `deepseek/deepseek-chat` through the same OpenAI-compatible gateway and can be overridden with `COGNITIVE_OS_L45_MODEL` / `COGNITIVE_OS_L45_BASE_URL`; L4.5 disables `response_format` by default because the current gateway returns contract JSON more reliably without that parameter;
- L4 calls remain explicit and use a controlled deterministic fallback when the configured cortex provider is unavailable;
- LLM outputs are advisory hypotheses or bounded role artifacts, not direct execution authority;
- L4 project interpretation records must distinguish raw model output from hardened output, including quality warnings, hardening actions, and whether the raw model output was clean.
- Programmer Executor may request an L4.5 patch-strategy hypothesis with `COGNITIVE_OS_EXECUTOR_USE_L45_LLM=1`; that hypothesis is recorded as advisory material. If it contains a shape-valid unified diff for the bound target, the diff may be applied inside an isolated sandbox and verified there before it can influence any reviewed executable artifact. Failed sandbox candidate verification permits at most one repair proposal, also sandbox-only and verifier-gated.

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
`config/stage2_template_routes.json`; web extraction host profiles live in
`config/web_extraction_profiles.json`; L4 prompt-to-product transition and
escalation reason rules live in `config/l4_decision_rules.json`; L4.5
existing-means mappings and developer request profiles live in
`config/semantic_resolution_rules.json`; source target semantics and
SpecWriter contract-family hints live in `config/semantic_target_profiles.json`.
`runtime/semantic_target_profiles.py` is only the matcher/interpreter for those
records: profile ids, exact/prefix/contains symbol matchers, path markers,
exclusions, score/ranking adjustments, benign runtime-boundary markers, typed
input/output contracts, side-effect policy, validation gates and failure
modes are data, not role/domain branches in Python. Adding a new bounded
semantic target family should normally be a JSON/profile change plus tests; a
Python change is justified only when the interpreter needs a reusable matcher
primitive or validator that the current schema cannot express. The news-site scraper route is
profile-gated: known hosts can carry stricter article path patterns, while unknown
hosts use a generic `SiteProfile` with same-host checks, navigation/service
exclusions and article-like path rules. A generic profile may build a package,
but live output is still risk-gated: if the requested top count is not parsed, the
CLI must return controlled failure instead of pretending that arbitrary live
HTML is supported. Browser rendering is an explicit operator-controlled mode:
`--browser auto` is the default and tries rendering only after an L4.5
`browser_required` diagnosis, `--browser always` tries rendered extraction before
LLM fallback when deterministic HTML/RSS is insufficient, and `--browser off`
forbids the browser path. The generated package declares `.[browser]` as an
optional dependency and documents `python -m playwright install chromium`; if
that adapter is unavailable or still cannot produce validated same-host news
items, it writes a
`NewsExtractionFailureReport` with diagnosis, strategy type, risks and next
actions instead of placeholder news. Feed and sitemap probing are budgeted with
short per-request timeouts so anti-bot/403 pages cannot stall the whole CLI
before the browser or failure-report path runs. L4.5 may recommend a strategy
type, but only allowlisted strategies in `strategy_registry.py` can be executed;
`api_probe` is diagnostic-only until a concrete adapter contract is added.

In the current implementation, `runtime/semantic_evidence_pack.py` first builds a bounded `SemanticEvidencePack` with prompt facts, failed gates, known templates, forbidden actions and explicit non-authority. `runtime/semantic_reasoner.py` then provides a deterministic runner for the request and an explicit model-backed mode through the configured OpenAI-compatible L4.5 gateway. The default model-backed L4.5 profile uses `deepseek/deepseek-chat`, intentionally separated from local L3.5 profiles and still constrained by L4 validation. If a ready prompt has no supported template, intake is uncertain for a concrete bounded implementation prompt, or the prompt is a bounded behavior/limitation question, L4.5 first tries to map it to existing means. A successful mapping becomes `SuccessfulResolutionCandidate`, which can later become a KB/template rule only after repeated verified successes and review. `runtime/fallback_autonomy_loop.py` can then attempt that mapped existing route in the Stage 2 sandbox and run normal tester verification; this is the intended bridge between "LLM proposed a route" and "the system actually produced a verified package". If model-backed L4.5 misses a route that deterministic evidence can prove, hardening rescues the proposal as an existing-route candidate and records the rescue in audit fields. If existing means cannot solve the prompt, or the sandbox attempt fails, L4.5/Stage 2 emits `DeveloperImprovementRequest` for Codex/human implementation work; it does not immediately mutate templates or KB. Stage 2 CLI can request a real L4.5 model proposal with `tools/verified_system_package.py --use-l45-llm`; provider failure is captured in proposal hardening and falls back to deterministic proposal. Model output is normalized, forbidden actions are stripped, weak route misses may be rescued by deterministic evidence, and the proposal passes through `runtime/l4_semantic_validation.py`, which emits `L4SemanticValidationResult` with policy review and a human-readable explanation. Vague prompts and secret/live-risk prompts still route to clarification without developer work, unsupported product surfaces route to clarification, and no path mutates templates automatically. Otherwise the result becomes clarification, stop, rework, knowledge-gap recording, sandbox-verified package, or blocked output. `runtime/semantic_replay.py` can persist `SemanticProposalReplay` records for model/prompt/hardening comparison, and `runtime/l45_semantic_benchmark.py` plus `tools/l45_semantic_benchmark.py` run a deterministic semantic-loop benchmark. Model usage is explicit through quality modes: `deterministic`, `model_propose_only`, `model_with_human_review`, and `blocked_model_untrusted`.

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

The preferred design is provider-portable and local-first: projects should talk to a configured gateway rather than hardcoding external model API keys. Active model profiles live in `config/llm_profiles.json`; environment variables such as `COGNITIVE_OS_LLM_MODEL` and `COGNITIVE_OS_L45_MODEL` may override the file for one run. The current checked-in defaults are `local_l35.model=local` and `external_l45_intent_resolver.model=deepseek/deepseek-chat`. A live GigaChat smoke test confirmed that gateway ids `GigaChat` and `GigaChat-Pro` work, but the current semantic benchmark was weaker than the Deepseek profile.

Use `tools/llm_profile_eval.py` before changing model profiles:

```powershell
python tools\llm_profile_eval.py --root . --smoke --write
python tools\llm_profile_eval.py --root . --smoke --benchmark-l45 --write
```

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
- L4 external model calls are optional; the default `deepseek/deepseek-chat` profile may fall back to deterministic behavior when its gateway is unavailable;
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

Current evidence snapshot (2026-08-30): `framework_plugin_build` completed three independent project-native sandbox repairs and passed explicit KB promotion (`174` regression tests, Config Doctor `44/44`, zero source-project changes). The current role matrix is `artifacts/field_trials/role_project_type_evaluation_20260830T161442270918Z.json`: framework/plugin scores are `9.7/9.7/9.7/9.8/10.0/9.8`, and workspace portfolio analysis is `9.7` over five blind controlled scope-selection stops. Target-scoped admission passed `4/4` frozen contrasts with two positive lineages while direct writes and subprocess-risk projects remain blocked. These results apply only to the demonstrated bounded contracts; automatic source apply and broad effect-heavy autonomy remain disabled.

Bounded self-development now starts with a digest-bound `SelfDevelopmentChangeProposal`. The policy interpreter classifies changes as `L0-L4` and evaluates `propose`, `sandbox`, `promote`, and `apply` authority separately. An unknown target kind fails closed to L4; evaluator architecture and sensitive admission or promotion changes cannot validate themselves. Repeated capability gaps are attached to field-trial reports as shadow dossiers, with source apply and promotion disabled.

Promotion gates no longer accept self-reported verification booleans. Regression, independent holdout, evaluator identity, and generated-stub claims must resolve through a verified `PromotedEvidenceLedgerEntry`: an immutable copy under `evidence/artifacts/`, a canonical ledger record under `evidence/ledger/`, distinct producer/evaluator fingerprints, and a replay command. Historical files under ignored `artifacts/` remain diagnostic evidence until explicitly promoted into this tracked ledger.

Role-chain evaluation records five digest-bound handoff contracts, arbitration usage, unresolved uncertainty, target continuity, reselections, and human decisions. A working score at `9.2+` is distinct from narrow-lane promotion: only current-lane role/project-type cells at `9.7+` with complete blind, independent, and project-native evidence are `promotion_eligible`; broad strata stay explicitly deferred. Unknown archetype clusters additionally require independent source lineages, unique evidence digests, and coherent markers before external review.

The first read-only backfill trial is `artifacts/self_development/self_development_shadow_trial_20260830T175415849133Z.json`. It reconstructed three L0 dossiers from the independently promoted pure-transform, CLI and framework/plugin repair catalogs. All three scored `1.0`, all `7/7` trial checks passed, and source reports plus catalogs remained unchanged. This validates representation of known good changes; it is not prospective self-development evidence and grants no L0 promotion authority.

Prospective detection is a separate temporal gate. `config/self_development_prospective_detection.json` permits only post-cutoff reports, allowlisted systematic rule families, mature project types and clusters spanning at least three independent projects. The first live report, `artifacts/self_development/self_development_prospective_detection_20260830T180304042531Z.json`, correctly returned `waiting_for_evidence`: all 75 existing reports were pre-cutoff, no candidate was created, and all `5/5` safety checks passed.

Every persisted `ProjectDevelopmentRun` now feeds an incremental digest checkpoint and reruns prospective detection once per new report. Derived signals cover target handoff loss, human rejection and validated-memory authority outside an eligible route. The fresh no-hint batch is `artifacts/self_development/self_development_fresh_blind_trial_20260830T183308224089Z.json`: coverage is `3+3+3` for pure-transform, CLI and framework/plugin, nine cases matched, one out-of-scope contrast was retained, and the result is `evidence_exhausted` with zero fabricated candidates. Report `artifacts/self_development/self_development_prospective_detection_20260831T031558750274Z.json` covers 114 reports: 34 are eligible, 32 contain no allowlisted systematic issue, and the existing recognition-gap signature still has only two independent framework/plugin projects. Candidate count remains zero. The L0 lifecycle can stage or quarantine only after unseen holdout, no-regression, independent evaluation and reviewer approval; staging remains outside active KB and includes rollback rehearsal.

Local corpus reuse is governed by `config/self_development_corpus_eligibility.json`. `SelfDevelopmentCorpusEligibilityIndex` deduplicates repository lineage, records prospective and historical exposure, builds bounded content fingerprints, and freezes owner/content-independent acquisition and holdout partitions before any run. Report `artifacts/self_development/self_development_corpus_eligibility_20260831T052410743974Z.json` covers 4903 physical copies and 4321 unique projects, including 644 untouched packaging-marker candidates; both replacement local partitions remain `3/3` and all `7/7` checks pass. The three network fallback revisions are now provenance-indexed as exposed while the existing frozen holdout remains untouched.

Owned build-backend recognition now uses the KB rule `owned_packaging_build_backend` and the generic matcher operator `required_source_contains_all`. A provider must expose the project-owned `build_wheel`, `build_sdist`, and `prepare_metadata_for_build_wheel` source contract; merely declaring an external backend does not match. Real no-hint verification moved `pypa/setuptools` from config-parser classification to `framework_plugin_build/packaging_build_backend` at confidence `0.79`, retained the consumer-only contrast, and transferred to `flit` and `poetry-core`.

Every project-development run now carries `ClassificationConsistencyEvidence` from an independent AST contract evaluator. A recognized decision that conflicts with an owned source contract becomes the research-only issue `classification_contradiction`; ambiguous recognition remains under `recognition_gap`, and projects without an independent contract remain neutral. The new rule family is allowlisted for prospective clustering but still requires three independent projects before any lesson candidate can exist.

The second narrow owned contract is `owned_pytest_plugin`: matcher authority requires `pytest11` plus a production pytest fixture or lifecycle hook; the registered module may be `plugin.py` or a package module. Config intake reads bounded `.cfg`/`.ini` manifests and prioritizes `setup.cfg` and `plugin.py`. Training evidence covers three owner-independent durable runs, while the frozen unseen report `artifacts/pytest_plugin_holdout_20260831/holdout_report.json` adds pytest-randomly, pytest-httpserver and pytest_httpx at exact SHAs. Holdout recognition and independent consistency pass `3/3`; executable foundation minima are Project Analyzer `9.7`, Architect `9.7`, SpecWriter `9.8`, with zero source changes. Implementer/Tester/Reviewer promotion is not claimed.

The first downstream pytest-plugin defect trial is deliberately non-promotional. On the parent `c9181c28607e990123ee480200ae2e684f58e7b6` of upstream fix `49c8c1bb487d03ca1bda2ac7567e4205bf82aae6`, the original Faker-disabled regression test produced the same failure twice and bound it to `src/pytest_randomly/__init__.py:faker_seed`; see `artifacts/field_trials/project_native_failure_intake_20260831T060005886998Z.json`. Targeted intake, explicit nested-plugin isolation, nested-sandbox traceback rebinding, and module-feature-guard AST resolution are now supported. The role chain stops before implementation because `disabled_pytest_plugin_symbolic_seed_contract` has no verified reducer, then routes to staged `unsupported_reducer_shape` research at confidence `0.68`; `artifacts/project_development/project_development_20260831T060548304438Z.json` records zero source changes and zero executor reruns. The upstream contrast is hypothesis evidence only: at least two more independent contrasts and three verified project-native transformations remain required before downstream maturity can be reconsidered.

A second owner-independent defect now qualifies the stateful lifecycle path. The original readiness-failure test from pytest-httpserver fix `96bbe1990c985df132f21f243d5bb4fe1f33a7ba` fails twice on parent `b937308278bd191e01640aaea29c22cb2840b240` and binds through a bounded receiver state-transition slice to `HTTPServer.start`; see `artifacts/field_trials/project_native_failure_intake_20260831T062053744758Z.json`. Failure-backed target locking prevents SpecWriter from drifting to a fixture, and network-risk blocks sandbox execution without blocking read-only research. `artifacts/project_development/project_development_20260831T062528187092Z.json` again ends at `unsupported_reducer_shape` confidence `0.68`, with no patch, source changes, or executor rerun. The downstream evidence is therefore two real defect types and zero autonomous transformations.

The third independent defect comes from pytest-socket fix `2bf8608adfc79f0e4ba1e44b42164cd658aa877a`. A unique named-constructor binder maps the repeated pickle reconstruction `TypeError` to `SocketConnectBlockedError.__init__`; intake is `artifacts/field_trials/project_native_failure_intake_20260831T071448820513Z.json`. Constructor-shape interpretation distinguishes the failing formatted-message exception from the directly replayable `SocketBlockedError` contrast. The staged `exception_pickle_reconstruction_boundary` profile reached read-only evidence acceptance at confidence `0.88`. Digest-bound human approval covered candidate creation, Architect design, and one execution-policy-bound sandbox implementation. Report `artifacts/project_development/authorized_implementation_20260831T081035446426Z.json` passes the targeted replay and full suite (`103 passed, 9 skipped`) with one changed sandbox file, no stubs, and unchanged original source. Discovery breadth is `3`; supervised verified transformations are `1/3`, while autonomous transformations remain `0/3` and KB promotion remains forbidden.

The 400-line source gate is now enforced by Config Doctor through `source_line_limit_gate`. Latest report `artifacts/project_development/source_line_limit_audit_20260903T230204065085Z.json` scanned 1513 authoritative Python files across runtime, tools, plugins and tests with zero violations. Post-split design debt is tracked separately by `artifacts/project_development/post_split_audit_20260903T230640450590Z.json`: 24 mechanical split facades and 55 helper-backed split tests remain visible as refactoring backlog, not as release blockers.

## Interpreter Authority

Interpreter Authority v1 makes the decision path independently inspectable. `InterpreterDecisionTrace` binds the goal, target, scope, evidence, complete candidate set, selected rule, transition and prior trace by SHA-256. Recovery is a typed `RoleRecoveryContract`: at most two role returns, no target replacement, no scope expansion and no automatic retry or execution authority.

Narrow maturity is separate from certification. `NarrowTypeCertification` covers only `cli_local_tool` and `library_pure_transform`; every required role cell must be at least `9.7`, promotion eligible and backed by a disjoint multi-lineage holdout receipt with zero generated function stubs and zero role regression. Broad strata remain explicitly deferred. `SelfDevelopmentExperiment` compares baseline and candidate metrics for L0/L1 and rejects any regression or generated function stub before L0 reviewer staging can begin.

`SelfDevelopmentExperimentQueue` now joins prospective detection to that certification boundary before an experiment can be planned. It verifies the certification and its underlying holdout receipt, rejects tampered certificate payloads, digest-binds the detector result, maps allowlisted error families to target metrics and defers candidates outside the certified lane. Current receipt `sha256:f6c568fc4346e3b02c7cf35685004620a6fe65241a282846cc2f4e8c1a860e83` records `waiting_for_certified_candidate`: zero narrow candidates are ready and one repeated `framework_plugin_build` recognition gap is deferred because that stratum is not certified. This is a truthful negative result, not evidence of self-improvement.

`SelfDevelopmentChallengeCampaign` operationalizes the corpus plan. It scanned 1,386 eligible local projects, used token-boundary project-name matching, excluded exposed and content-duplicate records, and froze owner/content-disjoint holdout before acquisition. Only three local CLI candidates survived strict filtering, leaving a measured shortage of two; external fallback was then admitted and revision-bound. Manifest receipt is `sha256:b01df241df1bca962975959e5f18c51e0cf7aae13df6384a638c41da9dd369a1`. The first run exposed classifier error rather than a self-development success: declared `[project.scripts]` entrypoints were not carried into project identity. Structural TOML parsing now propagates that evidence, and two independent repositories without `cli` in their names are recognized as `cli_local_tool`; both currently report `no_actionable_issue`.

`SelfDevelopmentExperimentRunner` is implemented but deliberately has no successful execution receipt yet. It accepts only a ready queue candidate, binds baseline and candidate to the same frozen holdout and protocol, requires distinct verified ledger evidence and an independent evaluator, isolates the candidate overlay, rejects every measured regression and generated function stub, and leaves source apply and promotion disabled.

Static boundary audit receipt `sha256:d516e1c47a637b7b213942c4c73e96a7d1ac64ce68debc5f7ad2b5e85a354fb8` found five transition-producing runtime modules and zero interpreter-authority call sites. The interpreter contract is therefore implemented but not yet the governing path. The next architecture milestone is to require a verified `InterpreterDecisionTrace` at those five orchestrator/recovery boundaries.

`framework_plugin_build` remains a separate lane. Its repeated recognition-gap candidate now spans four independent projects, and all current role scores meet the configured target, but readiness receipt `sha256:7ff38f68833c526ba62991a32589fa7b98435591332868dcc62a4439199c4155` withholds certification until an independent holdout, generated-stub gate receipt and no-role-regression receipt exist.

Web UI is not a current milestone. It remains deferred until interpreter authority, role recovery, narrow certification and bounded self-development operate on a stable architecture; see `config/interpreter_authority.json` and `knowledge/role_knowledge/cognitive_os_evolution_authority.json`.

Current narrow-lane audit (2026-09-04): a fresh evaluation replaced the historical blind sources with four digest-bound reports over two independent corpus lineages. All 12 required CLI/pure-transform role cells are promotion eligible at `9.7+`, each has at least two blind projects, acquisition and holdout lineages are disjoint, and the role benchmark remains `8/8` with interaction score `1.0` and handoff loss `0`. The AST audit covers every contributing blind report and found zero generated function stubs or parse failures. Seven input receipts preserve immutable copies of the evaluation, pipeline, audit and four blind reports. Holdout receipt `3a8e427d...6f1d` and certificate receipt `ca0bdda7...d657` both verify in the evidence ledger; `NarrowTypeCertification.status` is now `certified`. This certification is limited to `cli_local_tool` and `library_pure_transform`; broad strata, automatic source apply and Web UI remain deferred.

## License

MIT License. See `LICENSE`.
