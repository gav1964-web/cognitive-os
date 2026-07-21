# MVP_STATUS.md
**Baseline snapshot: Cognitive OS foundation and Local Automation MVP target**

Updated after the July 21, 2026 configuration-first diagnostics and verification pass.

## Current Verdict

Status: `foundation-ready for controlled analysis/planning, sandbox programmer-executor and Foundry field trials; product MVP target is Prompt -> Verified Local Automation Package`.

The system can accept a bounded user goal, classify it through Level 4, plan known routes through Level 3.5, execute deterministic capability chains through runtime, produce project-analysis reports, run the role pipeline, produce an isolated programmer-executor `PatchPackage`/`TestResult`, prepare a Foundry candidate, build Stage 2 verified packages, and wrap a release-ready package into a Stage 3 `ProductSliceSpec` without modifying the analyzed source project or changing the runtime registry automatically. This is not yet a general product MVP. The next concrete MVP target is a locally verifiable automation contour: prompt intake, sandbox package generation, tests, README, verification report, review/release decision, and controlled refusal outside scope.

## Product MVP Target

Target: `Prompt -> Verified Local Automation Package`.

In scope: Python CLI tools, local small services without GUI, file/document/image/text/archive/table/structured-data automation, OCR/vision flows with fixture/injectable tests, web/API clients or scraping with fixture/mock tests, project analysis and improvement planning.

Out of scope for this MVP: GUI applications, SQL databases as required runtime state, production deployment, uncontrolled dependency installation, mandatory live-network acceptance, direct source mutation without explicit approval, and free execution of LLM-generated code.

Smoke command:

```bash
python tools/local_automation_mvp_trial.py --root . --write
```

Current smoke corpus: `registry/local_automation_mvp_cases.json`, 39 cases across Python CLI, image automation, document automation, local small service, operation composition, sandbox atomic operations, controlled refusal and `needs_clarification` routing. Latest local run: `39/39 passed`, pass rate `1.0`.

Latest repository verification: `python -X utf8 -m pytest -q` -> `505 passed`; `python tools/config_doctor.py --root .` -> `8/8 passed, 0 warnings`; `python tools/config_coverage.py --root .` -> `50/50 config entities covered`.

## Verified Layers

| Layer | Current state | Evidence |
| --- | --- | --- |
| L1 capabilities | Plugin catalog, schemas and contract tests pass | `tools/check_plugins.py --root .` |
| L2 runtime | Sync/async pipeline execution, checkpointing, process boundary and queue/worker pool emit correlated execution-event/interrupt packets; durable jobs persist recovery traces | `tests/runtime/test_goal_runtime.py`, `tests/runtime/test_async_executor.py`, `tests/runtime/test_worker_pool.py` |
| L2.5 registry | Capability Registry and read-only Contract Registry validate active capabilities, packet routes and role artifact APIs | `tools/registry_doctor.py --root .`, `tests/runtime/test_contract_registry.py` |
| L3 interrupt/policy | Quarantine, fallback, repeated fallback failure, adaptation-budget stop and blocked escalation are exercised in sync/async paths | MVP acceptance and vertical runtime tests |
| L3.2 Foundry | Spec/candidate/dry-run promotion path works; promotion still requires explicit approval | `project_transform.py` |
| L3.5 spinal layer | Mandatory goal-runtime facade selects memory/deterministic/graph/optional-LLM routes, emits MotorPlanPacket/SignalPacket, receives correlated L2 events/interrupts and applies bounded recovery without executing plugins | `runtime/spinal_planner.py`, `runtime/goal_runtime.py`, `tools/spinal_benchmark.py` |
| L4 cortex/roles | Project Analyzer, Architect, SpecWriter, Implementer Planner, sandbox Programmer Executor, Tester and Reviewer pass readiness gates | `role_mvp_readiness.py` |
| L4/L4.5 config-first diagnostics | Config catalogs load cleanly, cross-references are checked, Stage 2 decisions carry `RuleTrace`, and config mutation proposals validate in sandbox before application | `tools/config_doctor.py --root .`, `tools/config_coverage.py --root .`, `tests/runtime/test_config_diagnostics.py` |
| Stage 3 product slice | `ProductSliceSpec` wraps a verified package with requirements, scenarios, architecture decision, task graph, documentation/scenario review, executable product debug loop, 8-case benchmark and release decision | `tools/product_slice.py`, `tools/product_debug_loop_probe.py`, `tools/product_slice_benchmark.py` |
| Memory/dialogue | Advisory memory and dialogue context exist, but do not execute or mutate runtime state | MVP acceptance |
| Knowledge Gap Loop | Installed-package probe, official-docs fetch and optional GitHub metadata evidence are implemented | knowledge tests |

The portable CI gate runs repository-contained deterministic checks only. Live L4 evaluation is opt-in through `--live-l4`; Local-3 and downloaded GitHub corpora are opt-in through `--local-project-trials`.

## Role Readiness

Latest verified command: `python tools/role_mvp_readiness.py --root .` on July 14, 2026. Generated reports under `artifacts/` are machine-local evidence and are not committed as repository fixtures.

| Role | Status | Score |
| --- | --- | ---: |
| Project Analyzer | `MVP-ready` | `1.0` |
| Architect | `MVP-ready` | `1.0` |
| SpecWriter | `MVP-ready` | `1.0` |
| Implementer Planner | `MVP-ready` | `1.0` |
| Programmer Executor | `MVP-ready; sandbox/no-source-edit by default` | `1.0` |
| Tester | `MVP-ready` | `1.0` |
| Reviewer | `MVP-ready` | `1.0` |

These scores mean the deterministic planning and sandbox execution gates are green. They do not mean the system is generally intelligent, self-learning, or safe to edit arbitrary projects without review. The general Programmer Executor creates isolated patch/test artifacts and rejects `--apply-source`; only the separate reviewed patch gate may apply a validated specialized package after explicit approval and backup.

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

The next engineering step is to compare deterministic and live local-LLM L3.5 proposals on the same benchmark corpus, including route quality, latency and controlled invalid-output fallback.
