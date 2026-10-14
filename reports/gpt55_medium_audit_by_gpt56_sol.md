# Strict technical audit: GPT-5.5 medium changes

Audit date: 2026-09-04  
Auditor mode: independent architecture/code audit; no production fixes applied

## 1. Audit scope

The audit covers the current workspace against Git `HEAD` `e0b7db44d3131b0fc883186f45419416835859dd` (`2026-08-25T12:22:03+03:00`, `Plan evidence before compiling improvement plugins`). This is the last reproducible committed state. There are no later commits, so all tracked modifications and architecture-relevant untracked files were reviewed as the candidate GPT-5.5 medium period.

The boundary contains 144 modified tracked files and 238 untracked files under `runtime`, `tools`, `plugins`, `config`, `knowledge`, and `registry`: 382 architecture-relevant files in total. The tracked diff is 5,879 insertions and 5,891 deletions. Attribution confidence is **medium**, not high: Git records neither model identity nor intermediate checkpoints, and the whole period is still an uncommitted working tree. Findings are therefore facts about the candidate period/current state; model attribution is qualified where baseline provenance cannot be proved.

Reviewed material includes Git history/diff/status; README, technical baseline and MVP status; runtime roles, routing and execution; schemas/config/manifests/registry; KB catalogs and matchers; self-development mechanisms; production and plugin tests; generated evaluation evidence; source-line and post-split audits; LLM call sites and fallback policy.

## 2. Reconstructed baseline

The committed baseline already had a contract-driven role pipeline, deterministic-first routing, capability registry, KB-backed role behavior, evaluator/guard layers, explicit human/Foundry boundaries, and a 400-line production-file rule. The candidate period primarily adds or extends:

- semantic target selection and project/archetype knowledge;
- role-chain evidence, curricula, field trials and benchmark accounting;
- bounded self-development classification and proposal gates;
- project-development and exception-pickle reconstruction knowledge;
- generated-product acceptance, patch synthesis and recovery paths;
- broad mechanical decomposition to satisfy the line limit;
- token-aware/field-weighted KB matching and deterministic routing refinements.

The baseline cannot be reconstructed as a clean GPT-5.6-vs-GPT-5.5 series because 238 current production-relevant files have never been committed. This itself is a traceability defect (M1).

## 3. Executive verdict

**Verdict: ONLY FOR LOCAL/BOUNDED CHANGES.**

GPT-5.5 medium preserved most of the architecture's intent and produced substantial, generally well-tested capability. It did not globally replace deterministic/KB logic with LLM reasoning, did not weaken the 400-line gate, and kept source mutation and deep self-development fail-closed. However, the current batch is not integration-ready: registry integrity is red, 11 canonical tests remain reproducibly failing, evidence-backed self-development accepts caller assertions instead of independently verified evidence, and essential evaluation artifacts are excluded from version control. The speed of the period appears to have exceeded contract synchronization and integration discipline.

Overall score: **6.8/10**.

## 4. Changes reviewed

- Project recognition, unknown/ambiguous routing, target-scoped admission and archetype matching.
- Role artifacts and transitions across analyzer, researcher, architect, spec writer, implementer, tester and reviewer.
- External/local curricula, role pipeline benchmark and no-safe-candidate recovery.
- `synthetic_role_kb` extraction and weighted matcher behavior.
- L0-L4 self-development proposal/classification/admission and generated-stub guard.
- Patch synthesis, executable acceptance, generated-product quality and stage-2 package paths.
- Exception-pickle knowledge, audits and opt-in LLM advisory.
- Plugin capability changes, registry hashes and release smoke.
- Source-size enforcement and post-split structure.
- Documentation synchronization and evidence references.

Test growth is real rather than merely cosmetic: top-level test definitions in `tests + plugins` rose from 2,240 at `HEAD` to 2,860 (+620). In the tracked test diff, 108 test functions and 263 assertions were added while 33 test functions and 78 assertions were removed. No repository-wide pattern of weakening assertions or replacing integration tests with mocks was found.

## 5. Critical findings

None.

No evidence was found of uncontrolled source rewriting, automatic deep architecture mutation, silent registry promotion, or unconditional LLM execution in a critical path.

## 6. High findings

### H1. Active capability registry integrity is broken

- **Location:** `registry/capabilities.json` entries `project_map_report` (around line 342) and `read_many_files` (around line 374); `tools/registry_doctor.py::check_registry` (diagnostic at line 37).
- **Evidence:** `python tools/registry_doctor.py --root .` returns `hash_drift:project_map_report` and `hash_drift:read_many_files`. Runtime smoke also fails on these diagnostics. Actual loader hashes no longer match the stored registry hashes.
- **Architectural impact:** the registry is the executable contract and promotion boundary. Changing active plugin code without synchronizing its digest defeats identity/integrity guarantees and blocks the project's own release gate.
- **Consequence:** current state cannot pass runtime smoke or be treated as a releasable capability set; consumers may reject valid code or run a capability different from the registered artifact.
- **Direction:** regenerate and review hashes only after plugin behavior/contracts are frozen, then require registry doctor in the same atomic change/commit.

### H2. The supported regression boundary is red after the candidate batch

- **Location:** `tests/runtime/test_implementer_curriculum.py::test_implementer_curriculum_external_three_when_projects_exist`; `tests/runtime/test_spec_writer_curriculum.py::test_spec_writer_curriculum_external_three_when_projects_exist`; `tests/runtime/test_role_pipeline_benchmark.py`; `tests/runtime/test_stage2_verified_system_package.py`; `tests/tools/test_local_automation_mvp_trial.py`.
- **Evidence:** with a project-valid `TMP` and `--basetemp=.pytest-tmp...`, the final failed-only rerun reports **11 failed**. External case `test5` scores 0.963 for Implementer but misses `required_evidence_scope_covered`; Spec Writer scores 0.8 and misses both ranked-candidate and source-evidence coverage. The role benchmark scores 0.9688 implementation and fails because `fastapi_service_with_pydantic` now selects `main.py:price_item` instead of the frozen expected candidate. Four news-scraper package cases return `blocked`. Runtime smoke and local automation MVP also fail.
- **Architectural impact:** these are project-native contract/evaluation tests, not style checks. They directly cover role handoffs, frozen evidence, generated-product release and the integrated runtime gate.
- **Consequence:** claimed role maturity and current-state readiness are ahead of the executable evidence. A downstream release can be internally consistent at unit level while violating the frozen evaluator expectations.
- **Direction:** triage by root cause, update implementation or frozen expectations only with explicit evidence, and do not promote role maturity while the external and benchmark gates are red.

### H3. Self-development admission trusts self-reported verification claims

- **Location:** `runtime/self_development_change.py::build_self_development_change_proposal` (line 102), `interpret_self_development_change` (line 152), `_gate_passed` (line 315); corresponding fixtures in `tests/runtime/test_self_development_change.py`.
- **Evidence:** `_gate_passed` treats proposal fields such as `regression_passed`, `independent_holdout_passed`, `independent_evaluator` and a non-empty `evaluator_fingerprint` as proof. The proposal digest binds the submitted claims, but no report digest, evaluator receipt, replay, provenance check or independent artifact lookup validates that the claims are true. Tests construct these booleans directly and obtain an allowed decision.
- **Architectural impact:** bounded self-development is explicitly evidence-driven. Authenticating a statement is not validating its evidence, especially when the mechanism under change can submit the statement.
- **Consequence:** wiring the current admission decision to real L1/L2 mutation would allow fabricated evaluation claims to cross the gate. Current `apply=false`/shadow behavior limits immediate damage but does not make the gate sufficient.
- **Direction:** bind each claim to immutable report digests and evaluator identity, independently load/recompute them, enforce disjoint holdout provenance, and retain external review for L2+.

### H4. Active KB/readiness claims depend on ignored, non-reproducible evidence

- **Location:** `.gitignore` line 29 (`/artifacts/`); `knowledge/role_knowledge/exception_pickle_reconstruction_patterns.json` (for example lines 18, 149-213 and 386-408); documentation contract checks in `tests/runtime/test_documentation_contract_sync.py`.
- **Evidence:** no file under `artifacts/` is tracked, while 16 active config/knowledge/documentation files reference artifact paths. The exception-pickle KB records numerous `latest_*` reports under ignored artifacts but generally does not bind their contents by digest. Documentation tests compare marker/file-name strings, not artifact existence, content hash or replayability.
- **Architectural impact:** evidence is part of the acceptance contract, not disposable build output, once it supports promotion, maturity or current-state claims.
- **Consequence:** a clean clone preserves conclusions but loses their proof; another architect cannot independently reproduce or audit promotions, and a same-name local artifact may silently change meaning.
- **Direction:** separate disposable artifacts from promoted evidence; version or content-address the latter with schema, digest, producer/evaluator fingerprint and replay command.

## 7. Medium findings

### M1. The development batch is too large and non-atomic to audit or roll back reliably

- **Location:** repository working tree as a whole.
- **Evidence:** 382 architecture-relevant files differ from the last commit, including 238 untracked production/config/KB files; no commit exists after 2026-08-25.
- **Impact/consequence:** bisect, rollback, model attribution and architectural-delta review are unavailable. A clean/packaged checkout can omit essential runtime modules while documentation still describes them.
- **Direction:** checkpoint coherent vertical slices with passing gates and explicit evidence manifests; keep experimental artifacts separate from mainline.

### M2. Several line-limit splits are mechanical namespace composition, not responsibility decomposition

- **Location:** `tools/github_full_chain_probe.py` lines 12-25; `tools/executor_profile_safe_role_probe.py` lines 11-27; pattern detected by `runtime/post_split_audit.py`.
- **Evidence:** facades import `_PART_NAMES`, merge all public module globals with last-writer-wins `_MERGED.update`, write the combined namespace back into every part via `vars(_part).update`, then expose it through `globals().update`. The post-split report identifies 24 mechanical facades (one is a test false positive; see L2).
- **Architectural impact:** the 400-line limit passes, but dependency direction and ownership become implicit. Duplicate names are silently resolved by part order and modules acquire undeclared cyclic shared state.
- **Consequence:** local edits can change unrelated symbols, static analysis is weakened and future agents must reconstruct a synthetic namespace across many files.
- **Direction:** retain the hard line gate, but replace high-risk facades incrementally with explicit imports and responsibility-oriented APIs; add collision detection meanwhile.

### M3. Target-scoped effect admission checks only direct call names

- **Location:** `runtime/project_recognition.py::_target_scoped_admission` (line 185; direct count returned around line 237).
- **Evidence:** AST scanning compares calls in the selected function to a forbidden-name list but does not resolve local callees. A wrapper `parse -> persist`, where `persist` performs the forbidden effect, reports zero direct forbidden effects and can be admitted if aggregate classification under-reports the risk.
- **Architectural impact:** admission is intended to narrow a stateful project to a safe first slice; transitive local effects are part of that slice's behavior.
- **Consequence:** underclassification plus a thin wrapper can bypass the intended safety boundary.
- **Direction:** add bounded local call-graph propagation and explicit unresolved-call uncertainty; fail closed when effect provenance is incomplete.

### M4. Exception-pickle LLM advisory has competing implementations

- **Location:** `runtime/exception_pickle_object_contract_advisory.py::llm_advisory` (line 19) and `runtime/exception_pickle_object_contract_audit.py::_llm_advisory` (line 152).
- **Evidence:** both implement near-identical `call_json_chat` error handling/validation rather than the audit delegating to the advisory module.
- **Architectural impact:** this duplicates an inference boundary where deterministic-first, advisory-only semantics must stay identical.
- **Consequence:** timeout, schema validation or fallback policy can drift between CLI/audit paths and alter token use or conclusions.
- **Direction:** keep one advisory adapter and one validator, with both callers consuming the same typed result.

### M5. Test execution boundaries are fragile and repository state is polluted by temp trees

- **Location:** `pytest.ini`; top-level `.pytest-tmp*`, `.nfi`, `.nft`; tests that copy the complete plugin tree.
- **Evidence:** 1,383 top-level `.pytest-tmp*` directories exist. Bare `pytest` is protected by `testpaths=tests`, but explicit repository-wide collection captures corpora/generated tests. Tests also require temp paths inside project scope, while the default system temp causes scope errors; copying plugin trees includes volatile `__pycache__` files and produced six repeatable setup errors in that environment.
- **Architectural impact:** verification depends on undocumented invocation/environment details, and status/audit visibility is degraded by thousands of local directories.
- **Consequence:** false red/green results, slow scans and accidental inclusion of generated suites are likely.
- **Direction:** codify one canonical test command, set an ignored in-root basetemp in configuration, exclude caches when copying fixtures, and implement bounded cleanup/retention.

## 8. Low findings

### L1. Blocker reason codes are semantically inverted

- **Location:** `runtime/project_recognition.py::_pilot_route`, lines 158-167.
- **Evidence:** a disallowed stratum appends `project_stratum_allowed`; prohibited risk appends `risk_profile_allowed`. Tests assert the latter for a blocked case.
- **Consequence:** logs and downstream analytics say “allowed” when recording the reason for rejection.
- **Direction:** introduce explicit `*_not_allowed` codes with a compatibility mapping/versioned schema.

### L2. Post-split audit counts its own marker fixture as a mechanical facade

- **Location:** `runtime/post_split_audit.py::_is_split_facade` (line 82); `tests/runtime/test_post_split_audit.py` lines 16-17.
- **Evidence:** marker detection includes raw source strings; the test fixture contains `_PART_NAMES`/import markers and is included in the reported facade count.
- **Consequence:** the reported 24-facade metric is inflated by at least one and cannot be treated as exact production evidence.
- **Direction:** scope production metrics explicitly or classify parsed executable structure rather than marker text alone.

## 9. Architectural drift analysis

The core architecture has **not** been replaced: roles remain contract-producing stages; unknown/ambiguous recognition fails closed; KB is active in selection; LLM remains advisory and opt-in in the reviewed additions; source/registry mutation stays gated; role handoffs and recovery are explicitly traced.

There is nevertheless **moderate cumulative drift** in integration discipline:

- evidence conclusions have moved faster than reproducible evidence packaging;
- mechanical file splitting satisfies the metric while weakening module boundaries;
- a very large uncommitted batch prevents architecture-delta review;
- evaluator and frozen-corpus regressions coexist with optimistic maturity documentation;
- registry synchronization was left behind active plugin edits.

This is not a redesign failure. It is a convergence failure: locally reasonable additions were not closed as one verified, reproducible system state.

## 10. KB/economics analysis

The KB remains an active architectural component. `runtime/synthetic_role_kb_matcher.py` moves matching away from one flat text haystack toward field-weighted lexical evidence, aliases and diagnostics. Project recognition, role selection and known patterns are deterministic-first; reviewed project-development paths do not introduce mandatory LLM reasoning per project.

Only two notable new inference boundaries were found in the exception-pickle object-contract advisory/audit. They are opt-in, advisory-only and run after deterministic source evidence, so there is no material default token-cost regression. The duplicated implementation in M4 is the main future risk.

The larger KB risk is not current token spend but evidence quality and overfitting. Several narrow project-type rules are intentionally project/corpus-specific. That is acceptable for the stated narrow-type strategy only while promotion requires blind cases, multiple lineages/subtypes and reproducible evidence. Current policies use non-trivial thresholds (including multiple blind reports and project-native transformations), which is a good control; ignored evidence artifacts weaken its auditability.

## 11. Self-development analysis

The conceptual shape is sound:

- change depth is classified L0-L4;
- unknown kinds default deep/fail-closed;
- sensitive L1 and L2+ require stronger authority;
- L3/L4 remain external/human/board-governed;
- proposal, impact, regression/holdout fields and evaluator fingerprint exist;
- generated function stubs (`pass`, ellipsis, `NotImplemented`) are admission blockers;
- current application behavior is shadow/staged rather than unrestricted runtime rewriting.

Therefore this is not generic self-modifying code. The decisive gap is H3: the gate validates the shape and digest of claims, not the underlying evidence. The system may safely continue generating hypotheses/specs/patches and running shadow experiments, but autonomous application authority should not expand until evidence receipts are independently resolved and replayed.

## 12. Test/verification results

- `python -m compileall -q runtime tools plugins`: **passed**.
- Config Doctor: **46 passed, 0 failed, 0 warnings**.
- 400-line/source-line audit: **1,513 Python files checked, 0 violations**.
- Plugin suite: **179 passed** in 2.69 s.
- Registry Doctor: **failed**, two hash drifts (H1).
- Runtime smoke without pytest: **failed** because Registry Doctor failed.
- Canonical project test attempt (`tests + plugins`) initially produced 2,830 passed, 46 failed and 7 errors, but this run mixed incompatible temp placement and concurrent compile activity; it is retained only as diagnostic evidence, not the final result.
- Controlled rerun with an in-root `.pytest-tmp*` environment reduced the reproducible set to **11 failed**; failures are summarized in H2.
- `mvp_acceptance --skip-pytest`: compile step passed; acceptance remained non-green because release/repo state was not fully clean during diagnostic runs and Registry Doctor is independently confirmed red.
- `git diff --check`: no whitespace errors; CRLF-to-LF warnings only.
- Ruff: **not run**, package is not installed and not declared in `requirements-dev.txt`.
- Mypy: **not run**, package is not installed and not declared in `requirements-dev.txt`.

The current suite does not support a claim of integration readiness. At the same time, the 2,830 passing tests, plugin suite and all config/line checks show that the batch is substantial and mostly coherent rather than broadly broken.

## 13. Good decisions made by GPT-5.5

- Unknown and ambiguous project types route to analysis/research instead of optimistic downstream execution.
- Classification contradictions become explicit evaluator findings and stop unsafe continuation.
- Role-chain interaction evidence records handoff loss, reselection and required human decisions.
- No-safe-candidate recovery remains bounded and cannot silently replace the architect gate.
- The generated-stub gate correctly treats placeholder implementations as negative admission evidence.
- L0-L4 self-development depth and external escalation boundaries preserve the accepted architecture.
- KB matching became more inspectable and token-aware without inserting an LLM into the default path.
- LLM advisory paths are optional, deterministic-first and do not write authoritative conclusions directly.
- The 400-line rule is enforced across a broad production surface and has no current violations.
- Test and assertion counts increased materially; no broad test weakening was detected.
- Config Doctor's 46 checks provide useful cross-catalog integrity coverage.
- Narrow project-type maturity is guarded by blind/project-native evidence thresholds rather than score alone.

## 14. Model suitability assessment

### A. Primary-model verdict

**ONLY FOR LOCAL/BOUNDED CHANGES** until the current integration debt is closed and at least one clean, committed, fully green vertical slice is independently audited.

### B. Tasks suitable for GPT-5.5 medium

- focused implementation inside an existing module/contract;
- deterministic KB matcher/rule refinements with blind regression cases;
- local tests, schemas and adapters with explicit acceptance criteria;
- L0 knowledge proposals and shadow-only L1 experiments;
- bounded bug fixes where registry/config/docs can be updated atomically;
- responsibility-based extraction under the 400-line rule.

### C. Tasks better assigned to GPT-5.6 Sol/external architect

- role/execution-chain contract changes;
- evaluator, promotion and self-development admission design;
- registry/runtime/schema migrations crossing subsystem boundaries;
- maturity/promotion decisions from corpus evidence;
- broad refactors and mechanical facade replacement;
- final integration audit and release authorization.

### D. Cumulative drift

Yes, moderate: evidence reproducibility, module decomposition and contract synchronization have drifted; the core architectural model remains recognizable and mostly preserved.

### E. Speed versus quality

Yes, there are signs: 382-file throughput and rapid feature/test growth were achieved while registry hashes, frozen evaluator expectations, evidence packaging and commit atomicity remained unfinished. This is not proof that every 5.5 change is weaker, but it is direct evidence that the batch closure discipline was insufficient.

### F. Scores

| Category | Score |
|---|---:|
| Architecture preservation | 7.6 |
| Implementation correctness | 6.7 |
| Test quality | 7.8 |
| Contract discipline | 5.7 |
| KB discipline | 7.4 |
| Self-development design | 6.4 |
| Maintainability | 5.8 |
| Resistance to architectural drift | 6.6 |
| **Overall** | **6.8** |

## 15. Recommended next actions

1. Freeze feature work and establish one clean, committed audit baseline; inventory all 238 untracked architecture-relevant files before any cleanup.
2. Resolve H1 atomically and require Registry Doctor plus runtime smoke before the next commit.
3. Triage the 11 reproducible failures by root cause: external `test5` evidence coverage, FastAPI frozen candidate selection, generated-package cache/release interaction, and downstream MVP effects.
4. Promote required evidence out of ignored artifacts into a content-addressed evidence ledger; make documentation/current-state claims verify digest and replayability.
5. Keep self-development shadow-only while replacing self-reported booleans with independently resolved evaluator receipts and holdout provenance.
6. Define one canonical Windows/Linux verification command and controlled `.pytest-tmp` lifecycle; prevent corpus/artifact recursive collection and volatile `__pycache__` copies.
7. Replace the highest-collision-risk `_MERGED/globals().update` facades with explicit APIs, preserving the 400-line limit.
8. After all gates are green, request a focused GPT-5.6 Sol audit of only the architectural delta; then reconsider upgrading 5.5 medium to `YES, WITH PERIODIC 5.6 AUDIT`.

