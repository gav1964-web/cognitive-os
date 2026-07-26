# MVP_STATUS.md
**Baseline snapshot: Cognitive OS foundation and Local Automation MVP target**

Updated after the July 25, 2026 strict three-role foundation hardening pass.

## Current Verdict

Status: `foundation-ready for controlled analysis/planning; active hardening focus is Project Analyzer -> Architect -> SpecWriter above MVP`.

The system can accept a bounded user goal, classify it through Level 4, plan known routes through Level 3.5, execute deterministic capability chains through runtime, produce project-analysis reports, run the role pipeline, produce an isolated programmer-executor `PatchPackage`/`TestResult`, prepare a Foundry candidate, build Stage 2 verified packages, and wrap a release-ready package into a Stage 3 `ProductSliceSpec` without modifying the analyzed source project or changing the runtime registry automatically. The current quality push is narrower than the full product MVP: make `ProjectMapReport -> ArchitectureDecisionRecord -> TechnicalSpec` strong enough to act as reliable API artifacts before expanding downstream roles again.

Greenfield planning is now separated from existing-project analysis. `tools/greenfield_role_run.py` and `tools/verified_system_package.py --planning-only` produce `ProductArchitectureRecord` and `ProductTechnicalSpec` directly from a user prompt, so prompts like "создай сервер для работы с клиентом OpenVPN" no longer need to be forced through a synthetic project-analysis extraction path. Open questions now control Architect mode: default `continue_with_assumptions` proceeds to SpecWriter, while `ask_user_before_spec` returns `needs_clarification` and a clarification prompt without starting SpecWriter. Greenfield architecture patterns live in `config/greenfield_architecture_patterns.json`; they now carry advisory `ResearchHints` and explicit chosen/rejected `ArchitectureOptions`, so OpenVPN planning records Management Interface / Access Server / PKI checks and rejects protocol-from-scratch implementation before SpecWriter handoff. Missing greenfield patterns now stop before SpecWriter as `greenfield_pattern_missing`, pass through L4.5 semantic fallback, and produce `DeveloperImprovementRequest` instead of a generic ТЗ. `tools/greenfield_prompt_benchmark.py` currently passes the 22-case planning corpus with `GreenfieldArtifactQualityReport` quality gates and without implementation/source/registry mutation.

## Product MVP Target

Target: `Prompt -> Verified Local Automation Package`.

In scope: Python CLI tools, local small services without GUI, file/document/image/text/archive/table/structured-data automation, OCR/vision flows with fixture/injectable tests, web/API clients or scraping with fixture/mock tests, project analysis and improvement planning.

Out of scope for this MVP: GUI applications, SQL databases as required runtime state, production deployment, uncontrolled dependency installation, mandatory live-network acceptance, direct source mutation without explicit approval, and free execution of LLM-generated code.

Smoke command:

```bash
python tools/local_automation_mvp_trial.py --root . --write
```

Current smoke corpus: `registry/local_automation_mvp_cases.json`, 39 cases across Python CLI, image automation, document automation, local small service, operation composition, sandbox atomic operations, controlled refusal and `needs_clarification` routing. Latest local run: `39/39 passed`, pass rate `1.0`.

Latest repository verification: `$env:PYTHONUTF8='1'; python -X utf8 -m pytest -q` -> `520 passed`; `python tools/config_doctor.py --root .` -> `8/8 passed, 0 warnings`; `python tools/config_coverage.py --root .` -> `52/52 config entities covered`.

Latest web extraction correction: `news_site_scraper_cli` is now profile-gated through `config/web_extraction_profiles.json`; unknown hosts such as `zindi.africa` must block with L4.5/developer-improvement for site profiling instead of receiving a generic release-ready scraper package.

## Verified Layers

| Layer | Current state | Evidence |
| --- | --- | --- |
| L1 capabilities | Plugin catalog, schemas and contract tests pass | `tools/check_plugins.py --root .` |
| L2 runtime | Sync/async pipeline execution, checkpointing, process boundary and queue/worker pool emit correlated execution-event/interrupt packets; durable jobs persist recovery traces | `tests/runtime/test_goal_runtime.py`, `tests/runtime/test_async_executor.py`, `tests/runtime/test_worker_pool.py` |
| L2.5 registry | Capability Registry and read-only Contract Registry validate active capabilities, packet routes and role artifact APIs | `tools/registry_doctor.py --root .`, `tests/runtime/test_contract_registry.py` |
| L3 interrupt/policy | Quarantine, fallback, repeated fallback failure, adaptation-budget stop and blocked escalation are exercised in sync/async paths | MVP acceptance and vertical runtime tests |
| L3.2 Foundry | Spec/candidate/dry-run promotion path works; promotion still requires explicit approval | `project_transform.py` |
| L3.5 spinal layer | Mandatory goal-runtime facade selects memory/deterministic/graph/optional-LLM routes, emits MotorPlanPacket/SignalPacket, receives correlated L2 events/interrupts and applies bounded recovery without executing plugins | `runtime/spinal_planner.py`, `runtime/goal_runtime.py`, `tools/spinal_benchmark.py` |
| L4 cortex/roles | Project Analyzer, Architect and SpecWriter now have stricter foundation quality gates; downstream roles remain available but are not the active hardening target | `tools/role_foundation_excellence.py`, `role_foundation_run.py`, `role_artifact_quality.py` |
| L4/L4.5 config-first diagnostics | Config catalogs load cleanly, cross-references are checked, Stage 2 decisions carry `RuleTrace`, and config mutation proposals validate in sandbox before application | `tools/config_doctor.py --root .`, `tools/config_coverage.py --root .`, `tests/runtime/test_config_diagnostics.py` |
| Stage 3 product slice | `ProductSliceSpec` wraps a verified package with requirements, scenarios, architecture decision, task graph, documentation/scenario review, executable product debug loop, 8-case benchmark and release decision | `tools/product_slice.py`, `tools/product_debug_loop_probe.py`, `tools/product_slice_benchmark.py` |
| Memory/dialogue | Advisory memory and dialogue context exist, but do not execute or mutate runtime state | MVP acceptance |
| Knowledge Gap Loop | Installed-package probe, official-docs fetch, optional GitHub metadata evidence and explicit KB usage telemetry are implemented | knowledge tests, knowledge usage telemetry tests |

The portable CI gate runs repository-contained deterministic checks only. Live L4 evaluation is opt-in through `--live-l4`; Local-3 and downloaded GitHub corpora are opt-in through `--local-project-trials`.

## Role Readiness

Latest MVP readiness command: `python tools/role_mvp_readiness.py --root .`. Generated reports under `artifacts/` are machine-local evidence and are not committed as repository fixtures.

| Role | Status | Score |
| --- | --- | ---: |
| Project Analyzer | `above-MVP foundation hardening` | `1.0` |
| Architect | `above-MVP foundation hardening` | `1.0` |
| SpecWriter | `above-MVP foundation hardening` | `1.0` |
| Implementer Planner | `unchanged; downstream context` | `1.0` |
| Programmer Executor | `unchanged; sandbox/no-source-edit by default` | `1.0` |
| Tester | `unchanged; downstream context` | `1.0` |
| Reviewer | `unchanged; downstream context` | `1.0` |

These `1.0` values are MVP-readiness pass signals, not 9.5 excellence scores. The stricter gate is `tools/role_foundation_excellence.py`. Its scoring is now worst-case based: a role score is capped by the weakest project/case floor, so one `8.5` project makes the role score `8.5` even if the average is higher. Aggregate averages remain diagnostics only.

Latest strict scorer runs after switching to worst-case methodology:

* `python tools/role_foundation_excellence.py --root . --github-projects-dir benchmarks/github_architect_10` -> Project Analyzer `9.63`, Architect `9.63`, SpecWriter `10.0`, average `9.75`, status `ok`.
* `python tools/role_foundation_excellence.py --root . --github-projects-dir benchmarks/github_full_trial_10` -> Project Analyzer `9.63`, Architect `9.63`, SpecWriter `10.0`, average `9.75`, status `ok`.

This is acceptance on the current local/GitHub corpora, not a claim of general reasoning ability or source-edit safety. The external-teacher backlog remains visible in metrics and must continue to drive new cases.

The first three roles now include stricter checks for ProjectMapReport source health, data lifecycle/runtime readiness, ADR subsystem I/O/data/state/tradeoff reasoning, source-backed first-slice evidence density, and TechnicalSpec interface/error/state/replay contracts. `ProjectMapReport.source_health` distinguishes `single_project`, `multi_project_workspace` and `dirty_portfolio`, and records syntax errors, inaccessible paths, generated/duplicated run signals and the required sanitation recommendation. Package/API libraries are no longer reduced to one fake CLI scenario just because a package `__init__.py` or internal `main.py` exists; they get import/API/data-transform/error-boundary scenarios. Architect now falls back from `ProjectMapReport.minimal_extraction_plan` to a conservative `architecture_synthesis` only when explicit source-backed extraction facts exist, preventing empty first-slice ADR artifacts. SpecWriter also emits `TechnicalSpec.extraction_contract.semantic_quality`, an advisory signal that distinguishes a structurally valid contract from an architecturally useful first slice and flags meta-infrastructure/runtime-boundary/accessor/support targets for review; ranked candidates must carry selection reasons and the selected candidate must be source-backed. The Project Analyzer GitHub probe distinguishes explicit runtime entrypoints from `library_surface_present`; package/API-first libraries are accepted only when Python package evidence and a capability model are present. Downstream scores are retained as existing MVP evidence only; they were intentionally not expanded in this pass. None of these scores mean the system is generally intelligent, self-learning, or safe to edit arbitrary projects without review.

Latest dirty-tree field trial: `D:/wsl` is now analyzed without crashing and is classified as `dirty_portfolio + damaged` with 210 entrypoints, 60 dependency files, 3 Python syntax errors and a recommendation to choose a concrete project root before extraction. `D:/wsl/40-6` and `D:/wsl/40-8` classify as `single_project + clean`, identify the LLM-provider-gateway purpose, and select `llm_providers.py:build_providers` as the first extraction candidate. `D:/wsl/0-40/workspace/ai_chat_app` remains `single_project + damaged` because `app/services/context_manager.py` fails AST parsing; this is surfaced as source-health evidence instead of being hidden behind a generic successful report.

Latest VAAT-v4 red-team correction: `F:/ubuntu/VAAT-v4` is now classified as `dirty_portfolio + noisy` because the root mixes active source, `vaat-v4_20250828` snapshot copy, archive/log artifacts and duplicate entrypoints; `ArchitectRedTeamReport` correctly returns `return_to_architect` until an active-root decision is recorded. `F:/ubuntu/VAAT-v4/vaat-v4_20250828` remains `single_project + noisy` because logs/artifacts are present, but passes with a warning instead of a false clean verdict. The architecture archetype is now `multi_agent_orchestration_runtime`, first slice is `agent_consensus_orchestration_slice`, and SpecWriter selects `core/consensus/engine.py:run_consensus` with `agent_consensus_orchestration_boundary` instead of the earlier weak `_validate_requirements` target.

Latest nasty-local red-team corpus: `python tools/nasty_project_redteam.py --root . --write` -> `10/10 passed`. The corpus lives in `benchmarks/nasty_local_projects` and covers dirty snapshot roots, ML/HF competition workspaces, FastAPI provider APIs that are not LLM gateways, broken evaluator snippets with unresolved `pipe/output`, damaged syntax trees, env/secrets, notebook/cache artifacts, true chat-completions LLM gateways, minimal multi-agent runtimes, and simple CLI projects. Fixes from this pass: route evidence is now part of L4 fact digest, `llm_gateway_service` is keyed by explicit chat/completions evidence instead of generic provider/framework text, broad `web_framework_library`/`proxy_security_tool`/`packaging_freezer` rules no longer override chat-completions or one-word `analysis.py` evidence, `.ipynb` is treated as artifact noise, SpecWriter demotes source snippets with high-confidence unresolved names, ADR first-slice evidence density is enforced, and SpecWriter ranked candidates require reasons/source backing.

Latest focused foundation quality gate: `python -m pytest tests/runtime/test_role_artifact_quality.py tests/runtime/test_role_foundation_pipeline.py tests/runtime/test_role_spec_writer_ranking.py -q` -> `22 passed`. This confirms the simple foundation artifact still passes after the stricter gates, while unbacked first-slice/ranking artifacts fail deterministically.

Latest foundation hardening run: `python -X utf8 tools/role_foundation_run.py --root . --benchmark --write` -> `8/8 passed`, `artifact_score=1.0`, `candidate_match_score=1.0`, `warnings=0`, `llm_invoked=0`.

## Field Trial: Project 5

User prompt: `проанализировать проект 5 и дать предложения по улучшению`.

Project path: `F:/ubuntu/test/5`.

Key artifacts:

| Artifact | Path |
| --- | --- |
| Goal report with project analysis and tasks | `artifacts/goals/reports/goal_20260706T133803495769Z_f24fe133aef1.json` |
| Role pipeline report | `artifacts/roles/pipelines/role_pipeline_20260706T133804990545Z.json` |
| Transformation report | `artifacts/transformations/capability_5_build_key_20260706T133804990545Z.json` |
| Generated Foundry spec | `generated/specs/capability_5_build_key.json` |
| Generated candidate | `generated/candidates/capability_5_build_key` |

Observed result:

* Project analysis produced deterministic facts, L3.5 signals, L4 fallback interpretation and `20` proposed improvement tasks.
* Role pipeline selected `app/core/cache.py:build_key` as the first bounded extraction target.
* SpecWriter, Implementer Planner, Tester and Reviewer all remained bound to the same target.
* Foundry built `capability_5_build_key` and reached `promotion_ready`.
* Source project changes: `false`.
* Registry changes: `false`.
* LLM invoked: `false`.

Top improvement themes found for project `5`:

1. Add idempotency/replay guards around local LLM availability and executable/model resolution.
2. Split broad mixed-responsibility functions such as `app/api/handlers_openai.py:handle_chat_completions`.
3. Isolate process boundaries for local LLM process startup and heavy request handling.
4. Define quarantine policies for external APIs, subprocesses, risky imports and unpinned dependencies.
5. Clarify `app/api` ownership boundaries and harden request/checkpoint/reuse policies.

## Fixed During This Pass

Project Transform previously chose a framework middleware candidate before the core helper chosen by the role pipeline. This was corrected:

* `runtime/extraction_proposal.py` now penalizes request/response/middleware/handler/async boundaries and prefers parser/normalizer/key-builder shapes.
* `runtime/transformation_flow.py` now adapts JSON `messages` payloads into attribute objects for extracted functions like `build_key`, and imports `hashlib` when the extracted source uses it.
* Regression tests cover the middleware-vs-core-helper ranking and the `build_key` candidate path.

## Foundry Extraction Hardening v0.1

Additional machine-local live extraction cases were run after the project `5` pass. Their projects and generated reports are field-trial evidence, not portable repository fixtures:

| Project | Selected target | Result | Report |
| --- | --- | --- | --- |
| `F:/ubuntu/test/map` | `app.py:parse_bbox` | `promotion_ready` | `artifacts/transformations/map_parse_bbox_20260706T142525725033Z.json` |
| `benchmarks/github_full_trial_10/click` | `src/click/_compat.py:is_ascii_encoding` | `promotion_ready` | `artifacts/transformations/click_is_ascii_encoding_20260706T142526440236Z.json` |
| `F:/ubuntu/test/004` | `p004_family_registry.py:is_codegen_supported_family` | `blocked` | `artifacts/transformations/is_codegen_supported_family_20260706T142541188812Z.json` |

Hardening fixes from these cases:

* Candidate contract tests now use Python literals instead of JSON literals, so `None` does not become invalid Python `null`.
* Candidate wrapper generation imports common stdlib modules used by extracted source, including `codecs` and `hashlib`.
* Sandbox build/promotion failures now produce a controlled `blocked` transformation report instead of an uncaught traceback.
* `runtime/dependency_extraction_policy.py` classifies extraction dependencies before sandbox build: self-contained functions proceed, stdlib imports may be inlined, and unresolved local/domain calls block the proposal.
* Extraction proposal now applies dependency policy per ranked candidate. A blocked top candidate is written to `skipped_candidates`, then the next ranked candidate is tried before the full proposal stops.

The `004` case is intentionally blocked at `PROPOSE` after trying the ranked candidate list. The skipped candidates require local/domain helper bundling, object adapter policy, or process isolation. The current MVP does not yet bundle local project modules into generated capabilities or extract instance/runtime-boundary functions. This is a correct controlled block, not a successful extraction.

## Known Limits

* L4 external model calls are optional and not required for readiness; the latest project `5` pass used deterministic fallback.
* Stage 3 is currently a product-slice contract, review and bounded rework layer over Stage 2 verified packages, not a general prompt-to-product generator.
* `analysis_tasks` are proposed backlog items, not automatic edits.
* Foundry candidates are not promoted without explicit approval.
* GitHub evidence is metadata only and not authority.
* Official docs fetch is allowlisted excerpt/hash evidence, not free browsing.
* Semantic long-term dialogue memory remains intentionally limited.
* The analyzed external project is treated as read-only.
* Direct standalone executor calls retain their deterministic default policy when no recovery handler is supplied; `goal_run.py`, async integration and worker pool use the typed spinal recovery controller.
* Live L4 and machine-local project corpora are evaluation tracks, not mandatory clean-checkout CI dependencies.

## Next Best Step

Run the hardened foundation contour on local and cached GitHub Python projects, then use misses to improve only `Project Analyzer`, `Architect` and `SpecWriter` until their outputs are consistently project-specific and implementation-ready without expanding downstream roles.

Current foundation-role target: `Project Analyzer -> Architect -> SpecWriter` is measured by `tools/role_foundation_excellence.py`, not only by MVP readiness. The target is `>= 9.5/10` per role and is not yet met under the stricter scorer. Remaining improvement focus is higher teacher-reference fact precision, closing the Architect curriculum backlog, and increasing genuinely `strong` SpecWriter semantic targets without overfitting to individual project names.
