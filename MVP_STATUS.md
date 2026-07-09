# MVP_STATUS.md
**Baseline snapshot: Cognitive OS MVP**

Generated after the July 6, 2026 field pass.

## Current Verdict

Status: `MVP-ready for controlled analysis/planning, sandbox programmer-executor and Foundry field trials; Stage 3 product-slice track started`.

The system can accept a bounded user goal, classify it through Level 4, plan known routes through Level 3.5, execute deterministic capability chains through runtime, produce project-analysis reports, run the role pipeline, produce an isolated programmer-executor `PatchPackage`/`TestResult`, prepare a Foundry candidate, build Stage 2 verified packages, and wrap a release-ready package into a Stage 3 `ProductSliceSpec` without modifying the analyzed source project or changing the runtime registry automatically. Direct source patch application is still blocked in MVP.

## Verified Layers

| Layer | Current state | Evidence |
| --- | --- | --- |
| L1 capabilities | Plugin catalog, schemas and contract tests pass | `tools/check_plugins.py --root .` |
| L2 runtime | Pipeline execution, checkpointing, process boundary, queue/worker pool pass acceptance | `tools/mvp_acceptance.py --skip-pytest` |
| L2.5 registry | Capability Registry and Contract Registry validate active capabilities | `tools/registry_doctor.py --root .` |
| L3 interrupt/policy | Quarantine, controlled stop and fallback paths are exercised | MVP acceptance |
| L3.2 Foundry | Spec/candidate/dry-run promotion path works; promotion still requires explicit approval | `project_transform.py` |
| L3.5 spinal layer | Deterministic known-route planner and project signals are operational | goal reports |
| L4 cortex/roles | Project Analyzer, Architect, SpecWriter, Implementer Planner, sandbox Programmer Executor, Tester and Reviewer pass readiness gates | `role_mvp_readiness.py` |
| Stage 3 product slice | `ProductSliceSpec` wraps a verified package with requirements, scenarios, architecture decision, task graph, documentation/scenario review and release decision | `tools/product_slice.py` |
| Memory/dialogue | Advisory memory and dialogue context exist, but do not execute or mutate runtime state | MVP acceptance |
| Knowledge Gap Loop | Installed-package probe, official-docs fetch and optional GitHub metadata evidence are implemented | knowledge tests |

## Role Readiness

Latest readiness report: `artifacts/field_trials/role_mvp_readiness_20260707T053507623879Z.md`.

| Role | Status | Score |
| --- | --- | ---: |
| Project Analyzer | `MVP-ready` | `1.0` |
| Architect | `MVP-ready` | `1.0` |
| SpecWriter | `MVP-ready` | `1.0` |
| Implementer Planner | `MVP-ready` | `1.0` |
| Programmer Executor | `MVP-ready in sandbox/no-source-edit mode` | `1.0` |
| Tester | `MVP-ready` | `1.0` |
| Reviewer | `MVP-ready` | `1.0` |

These scores mean the deterministic planning and sandbox execution gates are green. They do not mean the system is generally intelligent, self-learning, or safe to edit arbitrary projects without review. The programmer executor currently creates isolated patch/test artifacts; direct source edits remain disabled.

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

Additional live extraction cases were run after the project `5` pass:

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
* Stage 3 is currently a product-slice contract and review layer over Stage 2 verified packages, not a general prompt-to-product generator.
* `analysis_tasks` are proposed backlog items, not automatic edits.
* Foundry candidates are not promoted without explicit approval.
* GitHub evidence is metadata only and not authority.
* Official docs fetch is allowlisted excerpt/hash evidence, not free browsing.
* Semantic long-term dialogue memory remains intentionally limited.
* The analyzed external project is treated as read-only.

## Next Best Step

The next engineering step is to turn the Stage 3 product debug-loop plan into an executable bounded rework loop across product scenarios, then add more product prompts to the benchmark.
