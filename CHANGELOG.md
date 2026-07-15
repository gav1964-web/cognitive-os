# Changelog

## Unreleased

- Added PromptBoundaryClassification, expanded the L4.5 semantic benchmark to 22 cases, added deterministic-vs-model comparison reports, and ran a live `GigaChat-Pro` propose-only trial with replay-backed results.
- Added the L4/L4.5 semantic-loop toolkit: `SemanticEvidencePack`, `SemanticProposalReplay`, `L4DecisionTable`, L4.5 model quality modes, deterministic semantic benchmark and acceptance gate.
- Added `L4SemanticValidationResult` as the explicit L4.0 gate for L4.5 proposals; Stage 2 template backlog items are now created only after accepted L4 validation.
- Promoted `csv_sort_cli` from L4.5 template backlog candidate to admitted deterministic Stage 2 template with project-scoped tests.
- Added Stage 2 template admission gate and optional model-backed L4.5 semantic proposal mode with deterministic fallback.
- Added deterministic L4.5 semantic runner, `SemanticHypothesisProposal` validation, and Stage 2 template backlog items for bounded unsupported prompts.
- Added explicit L4.5 `SemanticHypothesisRequest` contracts for bounded semantic escalation from L4.0 back into deterministic gates.
- Routed Stage 2 prompt-to-product through L4.0 `CognitiveControlPlaneDecision`, so `PromptAdequacyGate` is now an API input to deterministic build/clarify/stop transitions.
- Added L4.0 Cognitive Control Plane v0.1 with deterministic artifact promotion, role transition, semantic-escalation policy and crystallization backlog.
- Extended Tester executable acceptance to v0.3 with project-specific invocation for simple `file.py:function` targets, output-shape checks and malformed-input rejection.
- Added Tester executable acceptance v0.2: TestPlan obligations now generate a pytest scaffold, Programmer Executor records ExecutableAcceptanceResult, and Reviewer conformance blocks failed executable acceptance.
- Added deterministic L3.5 selection diagnostics, Tester executable acceptance obligations, Reviewer conformance checks, L4 raw-model quality status, and documented controlled LLM fallback after deterministic failure.
- Documented the LLM Replacement Policy: LLMs are bounded hypothesis sources inside a verifiable engineering machine, while contracts, deterministic hardening, conformance checks and tests decide promotion to artifacts or execution.
- Switched the explicit external L4 gateway default from a provider routing alias to `GigaChat-Pro`; all L4 CLIs now share the same environment-overridable profile.
- Portable MVP acceptance is now self-contained: external L4 and machine-local project corpora are explicit opt-in field trials, memory evidence is seeded deterministically, and queue summaries expose packet counts without leaking full results.
- Documentation now distinguishes the sandbox-only general Programmer Executor from the explicit reviewed specialized patch-apply gate.
- Positioning and evaluation-plan documents clarifying that Cognitive OS is a contract-driven intent-to-engineering pipeline and verification harness, not a competing chat/workspace agent UI.
- Documentation now states that role artifacts are APIs between layers, not prose-only reports.
- Evaluation corpus scaffold with task template, metrics contract and validation CLI.
- Initial 6-task evaluation corpus and summary CLI for direct-agent vs Cognitive OS comparison.
- Architecture hypothesis track documenting role, registry, artifact, layering, Stage 3, memory, Foundry and debug-loop claims plus four seed evaluation tasks.
- First completed evaluation run for `task01_project5_improvement_plan`, recording a direct-agent win on human-readable analysis breadth and Cognitive OS strengths in artifact traceability/source safety.
- Architecture analysis document now supports current ProjectMapReport answer keys (`1_scope`, `2_execution`), eliminating `n/a` purpose/entrypoint sections in the first evaluation rerun.
- Completed `task02_map_project_analysis`, recording a direct-agent win and a Cognitive OS backlog item for stronger packaged-copy/source-strata filtering.
- Project map reports now exclude packaged-copy paths from active execution evidence, avoid usage/not-included README text as project purpose, and add human-readable improvement recommendations.
- Architecture analysis documents now include a target architecture sketch; `task02_map_project_analysis` was rerun to `no_clear_difference` after the project-analysis fixes.
- Layer 3.5 now has a contract facade in `runtime/spinal_planner.py` for IntentPacket -> validated Pipeline DSL -> MotorPlanPacket/SignalPacket, plus interrupt adaptation and quality checks.
- User goals now pass through mandatory `runtime/goal_runtime.py` coordination; L2 emits correlated execution/interrupt packets and recovery returns through a bounded L3.5 adaptation loop.
- Async execution and durable workers now use the same spinal recovery controller; queue results persist packet and adaptation traces, and async fallback no longer leaks the original exception into node outputs.
- Sync and async executors now re-enter L3.5 when a retry or fallback also fails, producing a second interrupt and a blocked signal when the adaptation budget is exhausted.
- L3.5 deterministic benchmark covers known chains, graph planning, safe blocking, retry, fallback and escalation, with contract and latency metrics.
- Contract Registry now catalogs role artifacts as producer/consumer APIs in addition to capabilities and packet routes.
- `goal_run.py` emits ASCII-safe valid JSON on Windows even when analyzed source contains characters unsupported by the console encoding.
- Stage 3 `Prompt -> Verified Product Slice` contract with `ProductSliceSpec`, architecture decision, task graph, verification summary, CLI and acceptance gate.
- Stage 3 product-slice review fields for requirements, task dependencies, documentation review, scenario verification, bounded product debug-loop plan and inferred input/output lifecycle.
- Executable Stage 3 product debug loop with documentation/scenario failure analysis, bounded package-local rework, project-scoped verification rerun, tester refresh and acceptance probe.
- Stage 3 product debug-loop repair for FastAPI API contract drift and a 3-case product-slice benchmark.
- Stage 3 product debug-loop repairs for CLI UX drift and README/API mismatch, with acceptance probes.
- Stage 3 product-slice benchmark expanded to 8 supported product prompts, with prompt intake and negative-edge evidence hardening.
- Stage 3 product-scenario probe for non-repairable CLI core behavior drift, producing a controlled `needs_rework` boundary instead of blind repair.
- Focused LLM migration analyzer for finding local proxy assumptions and producing direct-provider migration plans.
- GigaChat sandbox patch generator for building reviewed, tested direct-provider migration packages without touching the source project.
- Sandbox patch review/apply gate with diff, risk summary, verification checks, explicit approval flag and source backup.
- Standalone Stage 2 debug-loop probe for damaged FastAPI packages and controlled rework verification.
- CLI input/output contract repair for generated file-processing packages.
- Negative and edge-case test repair for empty text input and malformed JSONL fixtures.

## v0.1.0-mvp - 2026-07-08

Initial public research preview.

- Layered Cognitive OS runtime with capability registry, contract registry, queue, checkpoints, interrupts, and worker pool.
- Capability Foundry flow for spec generation, sandbox candidate build, tests, and dry-run promotion.
- Project Analyzer, Architect, SpecWriter, Implementer Planner, Tester, Reviewer, and sandbox Programmer Executor role artifacts.
- Stage 2 `Prompt -> Verified System Package` path for bounded CLI/FastAPI packages.
- Stage 2 support for JSONL log-filter CLI, text-stats CLI, FastAPI CSV aggregator, and FastAPI key/value CRUD service.
- Bounded Stage 2 debug loop for allowlisted deterministic repairs.
- Human-readable architecture analysis documents generated by role pipelines.
- MVP acceptance suite and project analyzer benchmark fixtures.
- GitHub Actions CI for pytest and MVP acceptance.
