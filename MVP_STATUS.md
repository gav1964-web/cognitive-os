# MVP_STATUS.md
**Current snapshot: Cognitive OS foundation and Local Automation MVP target**

Updated August 27, 2026 after the role-by-project-type evaluation, role-chain interaction trials, and bounded no-safe-candidate recovery work. Older benchmark sections below remain historical evidence for their named runs.

## Current Verdict

Status: `8/8 role contract gates are MVP-ready; bounded supervised pilot admitted; operational telemetry is implemented and awaiting 5 reviewed runs`.

The system can accept a bounded user goal, classify it through Level 4, plan known routes through Level 3.5, execute deterministic capability chains through runtime, produce project-analysis reports, run the role pipeline, produce an isolated programmer-executor `PatchPackage`/`TestResult`, prepare a Foundry candidate, build Stage 2 verified packages, and wrap a release-ready package into a Stage 3 `ProductSliceSpec` without modifying the analyzed source project or changing the runtime registry automatically. The current quality push is end-to-end handoff integrity: adversarial Reviewer coverage, the remaining Implementer Planner external gap, Executor re-evaluation on a mature planner input, and a comparable Researcher benchmark.

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

Latest targeted recovery/role-chain verification: `29 passed`. Latest `python tools/config_doctor.py --root .`: `39/39 passed, 0 warnings`. Historical full-suite results below retain the command and scope of their original run.

Stage 2 prompt-to-product now includes a product-facing `GeneratedProductQuality` gate. The generated working package is the user-facing output; intermediate role artifacts remain internal API contracts. Current gate threshold is `0.92`.

Latest web extraction correction: `news_site_scraper_cli` now uses a generated `SiteProfile` contract rather than one hardcoded site scraper. Known hosts may provide stricter article path patterns; unknown hosts receive a generic profile with navigation/service exclusions, same-host checks, article-like path rules, RSS/Atom fallback and controlled failure if the requested top count cannot be parsed. Generic extraction is `release_ready_with_risks`, not proof that an arbitrary live site is supported.

## Verified Layers

| Layer | Current state | Evidence |
| --- | --- | --- |
| L1 capabilities | Plugin catalog, schemas and contract tests pass | `tools/check_plugins.py --root .` |
| L2 runtime | Sync/async pipeline execution, checkpointing, process boundary and queue/worker pool emit correlated execution-event/interrupt packets; durable jobs persist recovery traces | `tests/runtime/test_goal_runtime.py`, `tests/runtime/test_async_executor.py`, `tests/runtime/test_worker_pool.py` |
| L2.5 registry | Capability Registry and read-only Contract Registry validate active capabilities, packet routes and role artifact APIs | `tools/registry_doctor.py --root .`, `tests/runtime/test_contract_registry.py` |
| L3 interrupt/policy | Quarantine, fallback, repeated fallback failure, adaptation-budget stop and blocked escalation are exercised in sync/async paths | MVP acceptance and vertical runtime tests |
| L3.2 Foundry | Spec/candidate/dry-run promotion path works; promotion still requires explicit approval | `project_transform.py` |
| L3.5 spinal layer | Mandatory goal-runtime facade selects memory/deterministic/graph/optional-LLM routes, emits MotorPlanPacket/SignalPacket, receives correlated L2 events/interrupts and applies bounded recovery without executing plugins | `runtime/spinal_planner.py`, `runtime/goal_runtime.py`, `tools/spinal_benchmark.py` |
| L4 cortex/roles | All eight measured roles pass their MVP contract gates; Researcher readiness covers bounded planning/quarantine and does not imply production research accuracy | `tools/role_mvp_readiness.py`, `tools/role_project_type_evaluation.py`, role curriculum and adversarial gates |
| L4/L4.5 config-first diagnostics | Config catalogs load cleanly, cross-references are checked, Stage 2 decisions carry `RuleTrace`, and config mutation proposals validate in sandbox before application | `tools/config_doctor.py --root .`, `tools/config_coverage.py --root .`, `tests/runtime/test_config_diagnostics.py` |
| Stage 3 product slice | `ProductSliceSpec` wraps a verified package with requirements, scenarios, architecture decision, task graph, documentation/scenario review, executable product debug loop, 8-case benchmark and release decision | `tools/product_slice.py`, `tools/product_debug_loop_probe.py`, `tools/product_slice_benchmark.py` |
| Memory/dialogue | Advisory memory and dialogue context exist, but do not execute or mutate runtime state | MVP acceptance |
| Knowledge Gap Loop | Installed-package probe, official-docs fetch, optional GitHub metadata evidence and explicit KB usage telemetry are implemented | knowledge tests, knowledge usage telemetry tests |

The portable CI gate runs repository-contained deterministic checks only. Live L4 evaluation is opt-in through `--live-l4`; Local-3 and downloaded GitHub corpora are opt-in through `--local-project-trials`.

## Role Readiness

Foundation self-improvement now includes an autonomous hypothesis-validation
step. After a staged measured hypothesis, Cognitive OS can derive a portable
failure signature, discover a bounded unseen reserve through the
`GitLab -> GitHub` fallback chain, probe it, train only two or three projects
with a matching diagnosed failure class and portable signature, run post-training admission, and then verify or roll back
the promotion on the original corpus. The discovery selection is frozen under
`artifacts/hypothesis_holdouts/<hypothesis_id>/`; provider failure is reported as
a blocked capability only after provider-chain exhaustion and does not count
against the hypothesis. Complete and blocked validation trials are durable JSON artifacts.

The implementation is locally verified by 159 focused self-improvement,
executable-acceptance, corpus, and discovery tests plus Config Doctor `37/37`.
This is implementation evidence, not a new role-readiness score. Live validation
`hvp_af4117f08dcf` used the GitLab-to-GitHub fallback and probed six unseen projects.
Two shared the broad `side_effectful_target` class, but none matched the staged
`side_effectful_target|memory_state|no_value_return` signature. The strict rerun
therefore ended `blocked / insufficient_matching_holdouts`, trained no unrelated
project, and persisted `hypothesis_validation_20260821T061834122084Z.json`.
Existing role minima below remain historical measured corpus results.

The follow-up live multi-round trial probed 16 new projects across frozen selections
`hvp_af4117f08dcf`, `_r2` and `_r3` (`6 + 6 + 4`). Every previously probed repository
was excluded and per-round/per-probe progress remained visible. Zero projects matched
the complete `side_effectful_target|memory_state|no_value_return` signature, so the
trial correctly ended `blocked / insufficient_matching_holdouts` without training or
promotion. The durable report is
`hypothesis_validation_20260821T070819226402Z.json`. This is discovery-quality evidence,
not role-readiness evidence: repository-metadata queries remain too broad for this
function-level signature.

Signature-aware v7 then separated adaptive eligibility from the 300-star release
floor and used a 20-star holdout floor. It produced six new eligible projects and
found the first exact independent match: `saurabhwadekar/FletX` at baseline `8.8`.
Its metadata (`global state management library`, `state-management`) provides a
portable vocabulary signal. With only one exact match, the gate correctly withheld
training and promotion; report:
`hypothesis_validation_20260821T072517405457Z.json`.

V8 expanded the configuration vocabulary to six queries and measured six further
projects. It found a nearby but distinct
`side_effectful_target|memory_state|explicit_return_annotation` case and no second
exact `no_value_return` match, so training remained blocked. The runtime now
re-probes and reuses FletX from durable exact evidence after planner evolution
instead of excluding it from search and forgetting it. V8 report:
`hypothesis_validation_20260821T073240035636Z.json`.

V9 kept the evaluator unchanged and expanded only discovery vocabulary with
portable repository signals observed around the first exact match: state-management,
global-state descriptions, event-driven systems, state machines and caches. The
trial re-probed three durable projects, including the still-exact FletX result at
`8.8`, and measured six new projects. Four new projects reached `9.7`; the two
remaining failures had different signatures (`observability` at `8.8` and
`dependency_boundary` at `7.5`). No second exact
`side_effectful_target|memory_state|no_value_return` match was found, so Cognitive OS
correctly withheld training and promotion after three rounds. Report:
`hypothesis_validation_20260821T081215897018Z.json`. That immutable report predates
the counter clarification and records `discovered_project_count=9` as the aggregate
`6 new + 3 prior`; subsequent reports keep new discovery and prior evidence separate.

V10 replaces further keyword tuning with two-stage retrieval. Each round can freeze
18 metadata candidates, scan at most 120 product Python files and 3000 callables per
project, then freeze no more than six projects for the full role probe. Structural
matches are ranked first; a bounded fallback preserves recall when fewer than two
matches are visible. The screen shares source-contract inference with the role
pipeline, but remains non-scoring retrieval evidence and cannot trigger training or
promotion. Its live result is recorded below.

Live v10 froze 18 new GitHub candidates and sent only six through the full probe.
None matched the exact raw signature, but `lzjever/routilux` produced the same
`side_effectful_target|memory_state` failure with an explicit `None` annotation.
This showed that retrieval reduced full-probe cost threefold while the raw output
basis over-specialized evidence. Report:
`hypothesis_validation_20260821T083806084781Z.json`.

V11 moved that equivalence into policy as the semantic `void_side_effect` family.
The durable evidence loader then found and re-probed `FletX` and `routilux` without
new network discovery. Both remained at baseline `8.8`; training changed neither
score, verified zero projects and promoted nothing. Cognitive OS grouped them with
the original `numerous/report-generator` failure and autonomously emitted
`CapabilityDevelopmentRequest cdr_84e96967eadb` for a
`candidate_selection_discriminator_plugin`. Final decision:
`capability_development_required`; report:
`hypothesis_validation_20260821T085307658091Z.json`. This is progress in the
self-improvement control loop, not an improvement in role readiness.

V12-v17 implemented the requested capability rather than raising a score by hand.
`candidate_selection_discriminator` now tests existing ranked, reselection and ADR
targets; `ImprovementPluginFoundryReport` binds the typed request to that plugin.
A fixed shadow-treatment handoff raised `numerous/report-generator` and FletX from
`8.8` to `9.6`. Expanding the bounded candidate window raised `python-memoization`
from `8.8` to `9.7`; an initial policy promotion was invalidated after operational
testing exposed an `hfos` regression to `5.0`, and the active KB record was removed.

The corrected admission path requires matching regression projects, consumes the
frozen measured treatment, synthesizes pairwise effect differences, snapshots KB
state, and rolls back on score/status regression. Discovery requires a fresh match
and clones with four bounded workers. V16 found unseen `Jarvis-v13` and improved it
`8.8 -> 9.7`, but admission was withheld while measured-effect handoff was repaired.
V17 then full-probed eight further unseen projects and ended honestly with
`blocked / insufficient_new_matching_holdouts`; no policy is active and no readiness
score is increased. Durable report:
`hypothesis_validation_20260821T111943672167Z.json`.

V18 improves recovery evidence rather than role scores. Hypothesis plans now carry
a structured diagnosis envelope, metadata queries compose effect and output-basis
terms before broad fallback, and full probes preserve exact, compatible, near-
contrast and unrelated outcomes. Recovery reports publish matching yield and
signature discrimination; contrasts remain non-training evidence. The focused
self-improvement suite passes `128` tests and Config Doctor remains `37/37`. No role
readiness increase is claimed without a new live holdout result.

The first live v18 recovery probe revalidated four of five prior projects and
reported matching yield/signature discrimination `0.8 / 0.8`, but found no fresh
candidate. It also exposed two defects: normalized `void_side_effect` lacked query
vocabulary, and known-regression `hfos` was treated as compatible despite an added
filesystem write. V19 adds the missing composite-query vocabulary and policy-defined
forbidden additional effects. This is a recovery correction, not a readiness gain.

The probe-only v19 replay excluded `hfos`, retained four safe prior matches, and
improved measured matching yield/signature discrimination from `0.8 / 0.8` to
`1.0 / 1.0`; it still found zero fresh projects and remained correctly blocked.
The remaining discovery defect was loss of provider-page position after a plan
version change. V20 adds a durable semantic search cursor, so the next run resumes
after pages 1-6 instead of scanning them again. No readiness increase is claimed.

Live v20 correctly resumed at pages 7-12 and still found zero fresh eligible
projects. It also exposed intermittent loss of FletX's redundant diagnosis class
while its classified baseline signature remained intact. V21 restores a missing
class from that portable signature only; effect/output and forbidden-effect gates
remain strict. The forge candidate supply is still the active blocker.

V22 replaced the shared cursor with per-query durable cursors, rotated bounded query
batches, translated provider syntax, expanded portable state vocabulary, and lowered
only adaptive-discovery star floors. Live probe-only validation supplied 16 new full
probes instead of zero and preserved one near contrast, but found no fresh exact
match. It remained `blocked / insufficient_new_matching_holdouts`; role readiness
is unchanged. The active blocker is now first-slice alignment precision in the
structural prescreen, not forge candidate supply.

Latest MVP readiness command: `python tools/role_mvp_readiness.py --root . --write`. The current report is `artifacts/field_trials/role_mvp_readiness_20260827T080846711504Z.json`: aggregate readiness `1.0`, with 8 of 8 measured roles MVP-ready. Generated reports under `artifacts/` are machine-local evidence and are not committed as repository fixtures.

| Role | Status | Score |
| --- | --- | ---: |
| Project Analyzer | `MVP-ready; regression maintenance` | `1.0` |
| Architect | `MVP-ready; regression maintenance` | `1.0` |
| SpecWriter | `MVP-ready; regression maintenance` | `1.0` |
| Implementer Planner | `MVP-ready; external evidence handoff closed` | `1.0` |
| Programmer Executor | `MVP-ready; sandbox and rollback contract` | `1.0` |
| Tester | `MVP-ready; regression maintenance` | `1.0` |
| Reviewer | `MVP-ready; six adversarial mutations detected` | `1.0` |
| Researcher | `MVP-ready for bounded planning/quarantine; low production confidence` | `1.0` |

These values are MVP-readiness gate signals, not excellence or production-confidence scores. The stricter foundation gate is `tools/role_foundation_excellence.py`; role-by-project-type maturity is measured separately by `tools/role_project_type_evaluation.py`. The bounded `deterministic_filesystem_read_pilot` is now `eligible`: blind confirmation `pilot_transfer_trial_20260827T085921925543Z.json` passed two executable projects from two independent owner lineages with zero handoff loss and zero source changes. Admission remains supervised, source apply is disabled, and network/subprocess/stateful/concurrent/provider-LLM risks remain prohibited.

Operational pilot evidence uses `PilotRunRecord -> digest-bound human review -> PilotTelemetryReport`. The first telemetry snapshot `artifacts/pilot/pilot_telemetry_20260827T091030436759Z.json` contains zero real supervised runs and therefore reports `insufficient_observations`. Health requires five reviewed runs, first-pass rate at least `0.8`, zero handoff loss, zero pending review, and zero source changes; automatic approval is forbidden.

The first five-project operational batch is recorded in `artifacts/pilot/pilot_run_batch_20260827T092011703158Z.json`. Human review completed with `approve=1`, `rework=2`, `stop=2`; reviewed telemetry `pilot_telemetry_20260827T100335500605Z.json` remains `attention_required` at first-pass rate `0.2`. Both rework signatures were subsequently closed diagnostically by generalized callable inference: mixed subscript/`.get()` mapping paths and unpacked object attributes now produce executable fixtures. The independent five-owner confirmation batch `pilot_run_batch_20260827T110808502633Z.json` did not pass: first-pass rate is `0.0`, with four eligible nominal/protocol fixture gaps and one correctly blocked filesystem/subprocess project. Human review confirmed `rework=4`, `stop=1`; final telemetry `pilot_telemetry_20260827T112019244368Z.json` has five reviewed runs, valid digests, pending `0`, handoff loss `0`, and source changes `0`. Run artifact names now include `run_id`, and ephemeral Python bytecode no longer creates false source-mutation signals. No profile boundary is widened from these results.

Latest independent GitLab iteration 11 used 40 previously unseen projects across five strata. The blind Foundation baseline produced role minima Project Analyzer `9.7`, Architect `8.33`, SpecWriter `6.47`. After generalized parser and contract-family treatment, the same corpus produced `9.7 / 9.7 / 9.8` over 30 Python-owned projects; 10 projects were explicitly out of scope. This treatment result is diagnostic and still requires confirmation on a new blind corpus.

The new downstream command is:

```bash
python tools/role_pipeline_min_field_trial.py --root . --projects-dir <corpus>/src --foundation-report <foundation-report.json> --target-score 9.7 --write
```

On the 30 iteration-11 Python-owned projects it produced raw role minima: Implementer `10.0`, Task Tree Builder `10.0`, Programmer Executor `5.83`, Tester `10.0`, Reviewer `8.33`. These raw `10.0` values mean all currently configured gates passed and expose that those rubrics are not yet discriminating enough; they are not excellence claims. Programmer Executor produced executable-callable evidence on `8/30`, meta-only evidence on `22/30`, completed successfully on `14/30`, and produced no sandbox candidate on `30/30`. The next downstream hardening priority is therefore executable fixture/profile coverage and bounded sandbox candidate synthesis, followed by stricter Implementer, Task Tree, and Tester quality rubrics.

Latest strict scorer runs after switching to worst-case methodology:

* `python tools/role_foundation_excellence.py --root . --github-projects-dir benchmarks/github_architect_10` -> Project Analyzer `9.63`, Architect `9.63`, SpecWriter `10.0`, average `9.75`, status `ok`.
* `python tools/role_foundation_excellence.py --root . --github-projects-dir benchmarks/github_full_trial_10` -> Project Analyzer `9.63`, Architect `9.63`, SpecWriter `10.0`, average `9.75`, status `ok`.
* `python tools/role_foundation_field_trial.py --root . --projects-dir benchmarks/github_foundation_holdout_10d --target-score 9.2 --write` -> status `ok`, 10 projects scored, below target `0`, readiness minimum `10.0`, role minimums: Project Analyzer `10.0`, Architect `10.0`, SpecWriter `10.0`, source changes `0`, LLM invocations `0`.
* `python tools/role_foundation_field_trial.py --root . --projects-dir benchmarks/github_foundation_holdout_10e --target-score 9.2 --write` -> status `ok`, 10 projects scored, below target `0`, readiness minimum `9.4`, role minimums: Project Analyzer `10.0`, Architect `9.4`, SpecWriter `9.4`, source changes `0`, LLM invocations `0`.
* Fresh GitHub corpus `benchmarks/github_foundation_holdout_15f` was cloned from 15 Python-first projects: FastAPI, Django REST framework, HTTPie, isort, flake8, Bandit, Hypothesis, coverage.py, NetworkX, seaborn, Bokeh, Dask, PyInstaller, pre-commit and Paramiko. Initial run exposed the real floor: `6.9` because broad KB rules misclassified coverage.py, NetworkX, Hypothesis and pre-commit, and SpecWriter had no semantic contract families for several valid domain targets. A later strict ADR-to-SpecWriter alignment gate briefly dropped the floor to `7.5`, because SpecWriter could choose a plausible candidate from the broad brief outside `ArchitectureDecisionRecord.first_slice_contract.targets`. After KB/profile hardening, semantic-profile expansion, config-driven first-slice scope enforcement, source-noise handoff policy and sampled-source KB evidence, `python tools/role_foundation_field_trial.py --root . --projects-dir benchmarks/github_foundation_holdout_15f --target-score 9.5 --write` -> status `ok`, 15 projects scored, below target `0`, readiness minimum `9.6`, readiness average `9.81`, role minimums: Project Analyzer `10.0`, Architect `10.0`, SpecWriter `9.6`, source changes `0`, LLM invocations `0`.
* Fresh GitHub corpus `benchmarks/github_foundation_holdout_15g` was cloned from 15 Python-first packaging/testing/library projects: Alembic, Black, Click, python-dateutil, Hatch, itsdangerous, pip, Pluggy, Poetry, poetry-core, pytest-xdist, tox, Twine, virtualenv and wheel. Initial run exposed a smaller but real floor: `8.4` on Alembic, pytest-xdist and wheel because migration diffing, distributed pytest scheduling and wheel artifact/tag handling were not first-class KB/profile families. A stricter `9.5` run later exposed Pluggy, Poetry, dateutil and wheel gaps. After adding a plugin hook runtime KB archetype, tightening broad archive/ML UI matchers, and adding semantic profiles for hook dispatch, pyproject initialization, datetime parsing and wheel artifacts, `python tools/role_foundation_field_trial.py --root . --projects-dir benchmarks/github_foundation_holdout_15g --target-score 9.5 --write` -> status `ok`, 15 projects scored, below target `0`, readiness minimum `9.6`, readiness average `9.87`, role minimums: Project Analyzer `10.0`, Architect `10.0`, SpecWriter `9.6`, source changes `0`, LLM invocations `0`.
* `python tools/role_foundation_field_trial.py --root . --projects-dir benchmarks/github_foundation_holdout_20c --target-score 9.5 --write` -> status `ok`, 20 projects discovered, 19 scored, 1 out-of-scope, below target `0`, readiness minimum `9.6`, readiness average `9.85`, role minimums: Project Analyzer `10.0`, Architect `10.0`, SpecWriter `9.6`, source changes `0`, LLM invocations `0`. The strict run exposed and then closed semantic-profile gaps for SDK resource factories, websocket callback backends, dataset module factories, framework template generation, ML/UI app launch, data-expectation metric backends, workflow work-pool submission, SQL select translation and tokenizer/model native conversion.
* Current strict foundation holdout: `python tools/role_foundation_field_trial.py --root . --projects-dir benchmarks/github_foundation_holdout_20b --target-score 9.5 --write` -> status `ok`, 20 projects scored, below target `0`, readiness minimum `9.6`, readiness average `9.88`, role minimums: Project Analyzer `10.0`, Architect `10.0`, SpecWriter `9.6`, source changes `0`, LLM invocations `0`.
* `python tools/role_foundation_field_trial.py --root . --projects-dir benchmarks/github_foundation_holdout_20b --target-score 9.2 --write` -> status `ok`, 20 projects scored, below target `0`, readiness minimum `9.2`, readiness average `9.74`, role minimums: Project Analyzer `10.0`, Architect `9.33`, SpecWriter `9.2`, source changes `0`, LLM invocations `0`.

This is acceptance on the current local/GitHub corpora, not a claim of general reasoning ability or source-edit safety. The worst-case floor on the latest strict-alignment independent holdouts is currently `9.2`, not `9.5`; Architect and SpecWriter still define the lower bound. The external-teacher backlog remains visible in metrics and must continue to drive new cases.

The first three roles now include stricter checks for ProjectMapReport source health, data lifecycle/runtime readiness, ADR subsystem I/O/data/state/tradeoff reasoning, source-backed first-slice evidence density, strict ADR-to-SpecWriter target alignment, and TechnicalSpec interface/error/state/replay contracts. `ProjectMapReport.source_health` distinguishes `single_project`, `multi_project_workspace` and `dirty_portfolio`, and records syntax errors, inaccessible paths, generated/duplicated run signals and the required sanitation recommendation. Package/API libraries are no longer reduced to one fake CLI scenario just because a package `__init__.py` or internal `main.py` exists; they get import/API/data-transform/error-boundary scenarios. `knowledge/architecture_patterns/project_archetypes.json` now carries scenario/input/output summaries for all 57 project-archetype rules, including narrow profiles for async-context detection, coverage measurement/reporting, property-based testing/data generation, graph algorithms, Git hook automation, database migration/autogeneration, distributed pytest running and wheel packaging. `config/semantic_target_profiles.json` now carries 62 target profiles, including FastAPI route registration, coverage analysis/reporting, code-quality option/plugin parsing, property-strategy generation, graph algorithm execution, plot semantic mapping, pre-commit hook execution, migration comparison/revision parsing, distributed pytest scheduling, wheel tag/artifact handling, compute-graph blockwise construction, module import-graph resolution, crawler settings application, workflow DAG trigger, chat-template rendering, URL query mutation, source-file parsing, framework dependency analysis, SSH connection boundaries, template project generation, runtime message dispatch, static-site build, web raw-data rendering and CLI option processing. Project Analyzer can produce richer boundaries for SDKs, workflow runtimes, web frameworks, ML UI frameworks, scientific/media libraries, observability tooling, CLI tools, services and generic Python packages without adding role-specific code branches. Multi-agent matching now requires stronger agent evidence and no longer captures ordinary observability SDKs such as Sentry by generic `agent/pipeline` words; broad map/GIS and distributed-graph matching now require stronger domain evidence. Architect preserves the original Analyzer `domain_profile` inside `ProjectArchitectureSynthesis.project_profile` even when its KB-backed architecture archetype differs, making disagreements auditable instead of silent. ADR source context now includes module-level context for selected `file.py:symbol` targets, so small libraries are not judged from one isolated function only. SpecWriter emits `TechnicalSpec.human_review` and `TechnicalSpec.extraction_contract.semantic_quality`, separates human review material from machine handoff, chooses the best candidate inside the Architect first-slice target set when that set exists, and distinguishes a structurally valid contract from an architecturally useful first slice. Ranked candidates must carry selection reasons and the selected candidate must be source-backed. Downstream scores are retained as existing MVP evidence only; they were intentionally not expanded in this pass. None of these scores mean the system is generally intelligent, self-learning, or safe to edit arbitrary projects without review.

Crystallization note: the latest 15f/15g/20b improvements were intentionally implemented as KB/project-archetype records, semantic target profiles and config policy, not as role-specific branches. The first ranking-policy pass moved target-quality and SpecWriter ranking token groups from `runtime/target_quality.py` and `runtime/role_spec_writer_ranking.py` into `config/target_quality_policy.json`, with `config_doctor` coverage. The next SpecWriter policy pass moved context-only source filters, snippet unresolved-name guards, inferred contract-type rules, side-effect process-boundary markers, semantic-rerank thresholds, architecture-shape score markers and first-slice scope enforcement from `runtime/technical_spec_builder.py` into `config/technical_spec_policy.json`. The Architect policy pass moved fallback archetype/slice rules, context-only source filters, domain-evidence source tokens, provider-parser discovery markers and brief-source sorting weights from `runtime/architecture_decision_builder.py` into `config/architecture_decision_policy.json`. The architecture synthesis pass moved bottleneck ordering, task-focus priority, fallback first-slice shape, verification/defer defaults and confidence thresholds from `runtime/project_architecture_synthesis.py` into `config/architecture_synthesis_policy.json`. The foundation semantic quality pass moved three-role threshold/check parameters from `runtime/foundation_semantic_quality.py` into `config/foundation_semantic_quality_policy.json`. The remaining SpecWriter contract-family fallbacks for ML generation, agent consensus and LLM repair hypothesis, plus confirmed holdout families for Dask/DRF/PyInstaller/Scrapy/Airflow/Transformers/Bokeh/DRF/Paramiko/Cookiecutter/Locust/MkDocs/Mypy, now live in `config/semantic_target_profiles.json`. Remaining candidates for the next crystallization pass are richer architecture synthesis recipes and any new scoring signals confirmed across multiple projects.

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

Current evidence update (2026-08-29): two project-native development loops are validated. `platformdirs` passed its repeated failing nodeid after a bounded registry-to-environment fallback and then the full suite (`895 passed, 79 skipped`). `marshmallow` passed its timestamp overflow contract nodeid after bounded error normalization and then the full suite (`1184 passed`). Both ran in patch sandboxes with unchanged source-project digests. This counts as `2/3` native transformations for `library_pure_transform`; CLI remains `0/3`. The current matrix is `artifacts/field_trials/role_project_type_evaluation_20260829T035206805890Z.json`. Clean baselines, environment blockers and reproducible failures without a unique production target are recorded but do not count as transformation evidence.

Native execution hardening update (2026-08-29): Windows intake copies now use a short `.nfi` root and hermetic user directories; this converted the apparent `installer` bytecode failure into a clean baseline. Full-suite timeout falls back to six deterministic file shards, and a timed-out file shard can be refined through bounded collection and pytest argument files. The `click` calibration collected 30,163 nodeids and passed them in 16 refined shards; nodeid path normalization preserves escaped parameter payloads. `typer` reached a repeatable subprocess dependency-isolation blocker instead of a generic suite timeout. These are execution-layer advances, not project transformations, so the role matrix remains `2/3` pure-transform and `0/3` CLI.

Subprocess/cache update (2026-08-29): the probe virtual environment is retained after editable-install fallback and carries a controlled path bootstrap for sandbox source plus the dependency overlay. The previous Typer `shellingham` child-process blocker is closed; both copies now reach the same tutorial formatting assertion, which remains reproducible but unbound and therefore grants no patch authority. Passed shard outcomes use a content-addressed cache keyed by project, overlay, interpreter/platform, pytest arguments and nodeids. Failures are never cached and project-native patch verification disables the cache. A real Click shard measured `5.751s` on cache miss and `0.001s` on the identical cache hit. Maturity counts remain unchanged.

Causal-intake update (2026-08-29): assertion-only failures are now sliced backward through local assignments. Only one project-production call can authorize repair; test observers, external dependencies, unresolved instance calls and unrelated setup remain diagnostic exclusions. The repeated Typer formatting failure therefore stays unbound (`runner.invoke` plus `normalize_rich_output`), as recorded in `project_native_failure_intake_20260829T101438223637Z.json`. Explicit pip-install hints and all `ModuleNotFoundError` outcomes are dependency blockers even when the traceback contains production frames. Git discovery is capped at the sandbox boundary to prevent parent-workspace ownership from breaking editable metadata.

Fresh pure-transform holdout update (2026-08-29): 31 independent projects from `github_fresh_40h_20260805` and `github_fresh_40i_20260805` were admitted. After declared test extras were supplied, the final disposition is 19 clean baselines, 12 dependency/platform/incomplete-source blockers and zero qualified failures. `markdown-it-py` passed 981 tests and `num2words` passed 1494 tests in each repeated copy after their declared extras were present. The apparent `validators` and `markdown-it-py` repair candidates were correctly withdrawn as optional-dependency failures. No score or maturity promotion is justified; pure-transform remains `2/3`, CLI remains `0/3`.

Source-complete external holdout update (2026-08-29): `benchmarks/github_native_holdout_20260829` adds eight independently cloned pure-transform libraries. The consolidated repeated run is 7 clean baselines, 1 Python-version blocker (`bidict` requires Python `>=3.11` while the probe runs 3.10), 0 qualified failures and 0 source changes; see `project_native_failure_intake_20260829T171056934889Z.json`. Bounded Git metadata preservation for declared dynamic-version backends converted Toolz's false `0.0.0` build into `1.1.0` and `186 passed` twice. Explicit legacy root-suite discovery ran jsonpointer's `tests.py` (`23 passed` twice), and furl passed 77 tests twice after its declared `orderedmultidict` dependency was supplied. This improves execution and diagnosis coverage only; pure-transform remains `2/3`, CLI remains `0/3`.

Observer/process-boundary update (2026-08-29): assertion-causal analysis no longer crosses imported test helpers, external observers or dynamic calls to grant repair authority. Descendant calls remain visible as `opaque_observer_descendant` diagnostics. This withdrew a false Rich candidate: `render(make_test_card())` failed with overlay Pygments `2.21.0`, while the project-locked Pygments `2.19.2` passed the original nodeid. Bounded execution now starts a process group/session and terminates the complete process tree on timeout; the real `pyproject-api` control returned two bounded timeouts instead of retaining child Python processes and inherited pipes.

Failure-discovery strategy update (2026-08-29): two additional current-head pure-transform batches covered 19 previously unmeasured projects. Their consolidated disposition is 12 clean baselines, 7 dependency/platform/incomplete-source blockers, 0 qualified failures and 0 source changes (`project_native_failure_intake_20260829T180555104297Z.json`, `project_native_failure_intake_20260829T183327365876Z.json`). Broad current-head expansion now has enough negative evidence to stop. The next pure-transform corpus must be selected from upstream issue-fix history: source-complete pre-fix commits with an original regression test, independent lineage and a read-only fix commit for comparison. Artificial source damage and weaker authority gates remain forbidden; maturity stays `2/3`.

Historical pre-fix validation update (2026-08-29): Deepmerge commit `f4822dec` plus the original regression test from read-only fix commit `d180db58` produced a repeated, uniquely bound failure at `TypeConflictStrategies.strategy_override_if_not_empty`. The full role chain selected the failure-specific `preserve_falsy_primitive_override` reducer, changed only a patch sandbox, passed the exact parameterized nodeid (`1 passed`) and the complete suite (`34 passed`), and preserved the original source digest. Intake-stratum evidence now survives recognition and reassessment, while parameterized nodeids preserve spaces such as `[zero int]`. This is the third independent native transformation, so the narrow `library_pure_transform` evidence ledger reaches `3/3` and supports a `9.7+` maturity claim; the regenerated matrix is `artifacts/field_trials/role_project_type_evaluation_20260829T194149902566Z.json`. It is not a universal `10/10`. CLI remains `0/3`, broad project strata remain deferred, and KB promotion still requires an explicit no-regression transaction.

Pure-transform promotion update (2026-08-30): the three-pattern repair catalog passed the explicit atomic promotion transaction in `artifacts/role_promotion/project_native_repair_promotion_20260830T000805901553Z.json`. The transaction required all six role cells to retain mature project-native evidence, revalidated Platformdirs, Marshmallow and Deepmerge outcomes, ran `126` regression tests, passed Config Doctor `43/43`, observed zero source-project changes and changed the catalog from waiting to active. This promotes only the narrow `library_pure_transform` repair lane, not broad Python-project autonomy.

First CLI native transformation (2026-08-30): Autoflake parent commit `e2109ba9` plus only the upstream regression test from read-only fix commit `aefc058d` reproduced `IndexError` twice at `autoflake.py:extract_package_name`. The role chain classified `incomplete_import_token_contract`, selected `guard_incomplete_import_tokens`, passed the exact nodeid (`1 passed`) and full project suite (`172 passed`) in a patch sandbox, reassessed the issue as resolved and preserved the original source digest. CLI therefore advances from `0/3` to `1/3`; the regenerated matrix is `artifacts/field_trials/role_project_type_evaluation_20260830T002347353942Z.json`. Its pattern is stored separately in `project_native_cli_failure_repair_patterns.json` as `validated_staged`; activation is forbidden until two additional independent CLI lineages and a dedicated no-regression promotion transaction exist.

CLI admission correction (2026-08-30): subsequent Rich-CLI and Click historical failures exposed a missing handoff constraint. `ProjectRecognitionDecision.pilot_route=analysis_only_stop` was reported but not consumed by `ProjectDevelopmentExperimentAdmission`, allowing an initial Rich sandbox run to claim validated memory despite prohibited project risks. Admission now requires `eligible_for_full_chain`, and memory rejects earlier validated claims produced through a blocked pilot route. The corrected Rich report is `project_development_20260830T052548525604Z.json`: controlled stop, validated memory `0`, rejected stale claim `1`. Click reproduced its intended strict-default failure after an explicit Pytest 9 compatibility retry, but was also correctly stopped for `stateful/subprocess` project risks. Neither case counts toward maturity; CLI remains `1/3`.

Generated stub prohibition (2026-08-30): sandbox patches now pass an AST-delta `GeneratedFunctionStubAdmission` before project-native replay. A newly added function, or an implemented function replaced by a body containing only `pass`, `...`, `raise NotImplementedError` or `return NotImplemented`, makes the experiment fail even if available tests are green. Pre-existing interface stubs are not attributed to the patch. A blocked patch cannot run native verification, enter validated memory or contribute maturity evidence.

Flake8 CLI transformation (2026-08-30): multi-interpreter intake now resolves distribution-bound runtimes without silent fallback; Flake8 is pinned to local Python `3.12.9`. Environment preparation blocks plugin-metadata failures after failed install, supports offline non-editable install, sibling pytest basetemp, ordered project/tool overlays and disabled external pytest plugin autoload. A processor-level witness adapted from the upstream escaped-brace regression gave unique assertion-causal authority to `FileProcessor.build_logical_line_tokens`; tuple-unpack backward slicing and static class-method binding are generic matcher capabilities. Reducer `adjust_fstring_middle_brace_offsets` passed the exact nodeid (`1 passed`), the full suite (`465 passed`, including the untouched upstream end-to-end test), generated-function stub admission and source digest invariant. Report `project_development_20260830T091122601066Z.json` is validated. The regenerated matrix is `artifacts/field_trials/role_project_type_evaluation_20260830T091715502616Z.json`: CLI downstream remains `usable` with exactly `2/3` project-native transformations. One independent lineage and an explicit promotion transaction are still required.

CLI promotion update (2026-08-30): isort parent `3ca9255` plus only the upstream regression test from read-only fix `b288021` reproduced `IndexError` twice at `isort/parse.py:file_contents`. Intake added bounded Git-worktree metadata, pyproject distribution identity, explicit plugin allowlists, deterministic Hypothesis seed and short Windows basetemp. Target-scoped admission waived only aggregate `stateful` risk for the repeated AST-checked function; direct external effects and network/subprocess/concurrent/provider risks remain blocking. Reducer `guard_trailing_backslash_index` passed the exact nodeid (`1 passed`), local regression suite (`548 passed, 5 skipped`), generated-stub gate and source invariant. Matrix `artifacts/field_trials/role_project_type_evaluation_20260830T104433802113Z.json` records CLI `3/3`; explicit transaction `artifacts/role_promotion/project_native_repair_promotion_20260830T104614251822Z.json` ran `167` regression tests, Config Doctor `44/44` and promoted Autoflake, Flake8 and isort patterns to `validated_active`.

Target-scope contrast update (2026-08-30): frozen source-backed cases matched `3/3` across two owner lineages. The isort pure failure target was admitted, isort `File._open` was rejected for a direct external effect, and a pure Click target was still rejected because project-level `subprocess` risk is not waivable. All target digests remained unchanged; report `artifacts/field_trials/project_target_scope_contrast_20260830T145348614957Z.json`. This validates the current boundaries but does not expand them: independent positive transfer remains pending at `1/2` lineages.

Framework/plugin foundation update (2026-08-30): the apparent `SpecWriter 6.47` floor came from one AutoDoc case where Architect had exhaustively rejected all 21 candidates, but semantic and feedback scorers still demanded a fabricated candidate and impossible execution confirmation. A controlled stop now receives credit only when `blocked_no_safe_candidate`, absent candidate, terminal Architect-owned exhaustion, positive expanded set, complete viability evidence, zero qualified candidates and no selected targets all agree. The fresh eight-project owner holdout produced `7 executable_callable + 1 evidence-bound blocked_ok`, role minima `9.7/9.7/9.7`, and zero source changes (`role_foundation_min_field_trial_20260830T150833324291Z.json`). Matrix `role_project_type_evaluation_20260830T150846767817Z.json` has 672 observations, 46 mature cells and zero weak cells; `framework_plugin_build` Analyzer/Architect/SpecWriter are mature over 12 blind projects.

Next role-by-type work is split deliberately. Within `framework_plugin_build`, Implementer/Tester/Reviewer remain only `usable` until three independent project-native transformation subtypes exist, regardless of raw `10.0` structural scores. The next foundation-only gap is `workspace_portfolio / Project Analyzer 9.2`; broad effect-heavy strata remain deferred.

Framework/plugin native promotion and workspace update (2026-08-30): the previous paragraph is superseded by three independent historical repairs. Pluggy `HookCaller.call_extra` passed targeted `1` and project regression `106`; PyPA Build `ProjectBuilder.metadata_path` passed the build-tag wheel contract; MkDocs `Theme._load_theme_config` passed the empty-YAML contract through a literal read-only target. All three experiments passed role handoff, generated-stub admission, targeted replay, configured regression, reassessment and source-digest invariants. The explicit transaction `artifacts/role_promotion/project_native_repair_promotion_20260830T160749995978Z.json` passed all promotion checks, `174` regressions and Config Doctor `44/44`, activating only `knowledge/role_knowledge/framework_plugin_failure_repair_patterns.json`.

## Bounded self-development protocol, 2026-08-30

Добавлен digest-bound `SelfDevelopmentChangeProposal` и fail-closed интерпретатор классов `L0-L4`. Он отдельно проверяет authority и gates для propose/sandbox/promote/apply, переводит неизвестные target kinds в L4 и требует внешнего Architect review для runtime и чувствительных evaluator/admission изменений. Повторяющиеся capability gaps теперь формируют `SelfDevelopmentShadowDossier` в foundation report. Контур пока строго shadow-only: source apply, runtime auto-promotion и неявное внешнее решение запрещены.

Read-only backfill `artifacts/self_development/self_development_shadow_trial_20260830T175415849133Z.json` восстановил три L0 dossier по ранее подтверждённым каталогам `library_pure_transform`, `cli_local_tool` и `framework_plugin_build`. Результат `3/3`, minimum score `1.0`, trial checks `7/7`, input/catalog digests unchanged. Это проверка schema/interpreter/evaluator на известных положительных изменениях, а не prospective self-development; autonomous L0 promotion остаётся выключен.

Prospective detector использует temporal cutoff, только зрелые `library_pure_transform`, `cli_local_tool`, `framework_plugin_build`, allowlisted system rule families и минимум три независимых проекта. Live report `artifacts/self_development/self_development_prospective_detection_20260831T031558750274Z.json` имеет статус `waiting_for_evidence`: из 114 reports 75 исключены как pre-cutoff, 34 входят в зрелый scope, 32 не содержат системной ошибки, а общий `recognition_gap` двух независимых проектов сохранён в watchlist и требует ещё один проект. Candidates `0`, safety checks `5/5`.

Локальный corpus теперь индексируется через `SelfDevelopmentCorpusEligibilityIndex`. Report `artifacts/self_development/self_development_corpus_eligibility_20260831T052410743974Z.json` охватывает 4903 физических копии, 4321 уникальный проект и 644 untouched packaging-marker candidates. Acquisition и frozen holdout остаются `3/3`, проверки `7/7`; три обоснованно загруженных pytest-plugin revisions теперь отмечены как exposed.

Matcher получил data-driven правило `owned_packaging_build_backend` и оператор `required_source_contains_all`. Owned provider определяется по совместному source contract `build_wheel + build_sdist + prepare_metadata_for_build_wheel`, а не по одному `build-backend` в manifest. `setuptools` исправлен с ложного config-parser типа на `framework_plugin_build/packaging_build_backend` с confidence `0.79`; перенос подтверждён на `flit` и `poetry-core`, consumer-only contrast не повышен.

В `ProjectDevelopmentRun` добавлен `ClassificationConsistencyEvidence`: независимый AST evaluator сравнивает owned contract с финальной классификацией. Несовпадение recognized-решения создаёт research-only `classification_contradiction`; ambiguous/unknown остаются в recognition lifecycle, отсутствие контракта нейтрально. Сигнатура включена в prospective detector и требует обычный порог `3+` независимых проектов.

Второй узкий profile `owned_pytest_plugin` требует `pytest11` и production fixture/lifecycle-hook evidence; entry point может вести на package module, а не только `plugin.py`. Training runs закрыты на трёх проектах. Отдельный SHA-frozen holdout `artifacts/pytest_plugin_holdout_20260831/holdout_report.json` прошёл на pytest-randomly, pytest-httpserver и pytest_httpx: recognition/consistency `3/3`, executable callable `3/3`, minima Analyzer/Architect/SpecWriter `9.7/9.7/9.8`, source changes `0`. Downstream promotion не заявлен.

Первый downstream-кейс теперь проверен на реальном историческом дефекте pytest-randomly. Intake `artifacts/field_trials/project_native_failure_intake_20260831T060005886998Z.json` дважды воспроизвёл исходный regression test на pre-fix SHA `c9181c28607e990123ee480200ae2e684f58e7b6` и однозначно связал leaf `TypeError` с `faker_seed`. Цепочка в `artifacts/project_development/project_development_20260831T060548304438Z.json` корректно остановилась без reducer и перевела случай в staged research (`unsupported_reducer_shape`, confidence `0.68`), без патча, изменений source и executor rerun. Это не автономная трансформация и не основание повышать Implementer/Tester/Reviewer.

Второй независимый defect получен на pytest-httpserver: readiness regression из fix `96bbe1990c985df132f21f243d5bb4fe1f33a7ba` дважды падает на parent и строго связывается с `HTTPServer.start` (`artifacts/field_trials/project_native_failure_intake_20260831T062053744758Z.json`). Failure-backed target больше не теряется между Architect и SpecWriter; network-risk запрещает execution, но не read-only research. Итоговый report `artifacts/project_development/project_development_20260831T062528187092Z.json` также остаётся на staged `0.68`, без patch/source changes/executor rerun. Итого: два квалифицированных downstream defect types, автономных трансформаций `0`.

Третий независимый defect взят из pytest-socket fix `2bf8608adfc79f0e4ba1e44b42164cd658aa877a`. Повторяемый pickle `TypeError` связан с `SocketConnectBlockedError.__init__` через unique named-constructor identity (`artifacts/field_trials/project_native_failure_intake_20260831T071448820513Z.json`). Passing-класс `SocketBlockedError` даёт same-project paired AST contrast, который явно не является KB promotion evidence. Candidate, Architect design и sandbox implementation прошли раздельные digest-bound human gates. `artifacts/project_development/authorized_implementation_20260831T081035446426Z.json` подтверждает targeted replay и полный suite (`103 passed, 9 skipped`), один sandbox source file, отсутствие новых заглушек и неизменность исходного проекта. Discovery breadth теперь `3`, supervised verified transformations `1/3`, autonomous transformations всё ещё `0/3`; source apply и KB promotion запрещены.

Следующий transfer получен из существующего exposed corpus без загрузки новых проектов. `urllib3.LocationParseError` проходил слабый upstream pickle test по concrete type, но executable semantic probe доказал изменение `location` и двойной message prefix. После исключения inherited `__reduce__` matcher удалил ложный isort lineage (`1282 -> 1255` candidates; isort `0`). Digest-bound design разрешил только replay существующего `self.location`. `authorized_implementation_20260831T110602578287Z.json` прошёл semantic check, targeted `17 passed` и bounded regression `19 passed`; original source unchanged, stubs/source apply/promotion отсутствуют. Supervised verified transformations теперь `2/3`, autonomous остаются `0/3`.

Третий supervised transfer также взят из существующего exposed corpus: `python-redmine.UnknownError`. Semantic probe показал, что pickle replay сохраняет `status_code`, но портит message двойным prefix. Sandbox-only implementation `authorized_implementation_20260831T115835185733Z.json` прошёл semantic check, targeted replay `1 passed` и bounded regression `405 passed`; изменён только `redminelib/exceptions.py` в sandbox, исходный project digest неизменён, stubs/source apply/promotion отсутствуют. Runner дополнительно очищает sandbox-only `build/lib` от локальной wheel-сборки, чтобы build noise не ломал single-file scope gate. Supervised threshold достиг `3/3`; autonomous transformations всё ещё `0/3`.

Promotion-readiness gate добавлен отдельно от promotion transaction. `exception_pickle_promotion_readiness_20260831T124021424040Z.json` имеет `eligible_for_promotion_review`: supervised ledger `3/3`, три независимых проекта/target, semantic/native/stub/source gates passed, плюс один независимый autonomous shadow case с project-native semantic replay. Первый pytest-socket report принят только через явный `legacy_pickle_native_replay`, потому что был создан до отдельного semantic verifier. Direct KB promotion из readiness остаётся false by design.

Independent holdout, autonomous shadow и evaluator gates теперь материализованы. `exception_pickle_holdout_transaction_20260831T124242422603Z.json` нашёл 586 применимых holdout-кандидатов в 229 проектах, прошёл focused regression `13 passed` и Config Doctor `44/44`, но не применил promotion. `exception_pickle_autonomous_shadow_20260831T123815742912Z.json` автономно выбрал `anyio.BrokenWorkerInterpreter`, подготовил sandbox patch, прошёл compile/scope/source/stub gates и выполнил import + pickle roundtrip semantic replay внутри sandbox-проекта. `exception_pickle_independent_evaluator_20260831T125714581827Z.json` подтвердил independence и no-mutation gates.

Manual promotion transaction `exception_pickle_promotion_transaction_20260831T132156422950Z.json` прошла `20` focused regression tests и Config Doctor `45/45`, после чего активировала `knowledge/role_knowledge/exception_pickle_reconstruction_patterns.json`. Boundary interpreter теперь потребляет этот catalog как active overlay: matching boundary получает `status=active` и `validated_active` operator authority. Active operator проходит через proposal, candidate и design request как suggested recipe; design validation блокирует подмену recipe. Это KB-level activation узкого pattern-а, а не разрешение менять source: catalog требует sandbox patch, semantic replay, запрещает generated stubs, existing reconstruction hooks и automatic runtime mutation.

Active-application contour использует active catalog на существующем holdout corpus и ведёт отдельный applied/blocked ledger. Последующие passes довели доказанное sandbox-only применение до `applied=178`; ledger теперь `blocked=414`. Последние additions включают `maxteabag__sqlit / CredentialsStoreError`, шесть `ctripcorp__flybirds` exceptions, `setuptools / LinkOutsideDestinationError`, `calf-ai__calfkit-sdk / ToolRetryError`, два `leptonai__leptonai` API errors, два `aiohttp` connector errors, `mercadopago__sdk-python / InvalidWebhookSignatureError`, `eddyzzl__marvis-risk-agent / IllegalTransition`, три CPython `tarfile` destination/link errors, `not-sekiun__consortium / AgentGeneratorBuildStepOverridesFinalMethodError`, `abhinavsingh__proxy-py / ProxyConnectionFailed`, `dj-bolt__django-bolt / ComponentNameCollisionError`, `pybotters__pybotters / OutOfBoundsError`, два `shy3130` tickflow `CapabilityDenied` targets, два `nats-io__nats-py` client errors, `nerevu__riko / PipelineStateError`, `withceleste__celeste-python / UnsupportedParameterError`, `reloadware__reloadium / RedefinedVarError`, два `benoitc__gunicorn` stash errors, `vonage__vonage-python-sdk / PartialFailureError`, `software-mansion__starknet-py / OutOfBoundsError`, `reloadware__reloadium / NoTypeError`, `supabase__supabase-py / StorageApiError`, `disnakedev__disnake / MaxConcurrencyReached`, `mosaik__mosaik / InvalidNextStepTypeError`, `nextcord__nextcord / MaxConcurrencyReached`, два `rapptz__discord-py` command errors, `treeverse__dvc / BaselineMismatchError` и `rluna-iot__home-assistant / RequirementsNotFound`, `pact-foundation__pact-python / InteractionVerificationError`, `rapptz__discord-py / CommandInvokeError`, `psevensas__djangochannelsgraphqlws / GraphqlWsResponseError`, Alembic range/head errors, JMComic base error, two Redis HTTP errors, and `treeverse__dvc / OutputDuplicationError`. Blocker-intelligence report `exception_pickle_blocker_intelligence_20260903T065159200878Z.json` классифицирует latest-blocker frontier в 146 cases; sample-supported readmission frontier равен 0, class-state contract research выделен в 6 cases, а priority lane остаётся import/dependency isolation на 25 cases. Import-isolation summary разделяет эти 25 cases на dependency unavailable 9, import failed 5, attribute-base/metaclass risk 10 и один dependency-heavy sample-supported case; direct-file replay preferred для 14 cases; missing-import kinds: external dependency 11, project-local dependency 2, stdlib symbol compat 2. Top missing imports: теперь только `librt` имеет count 2; `authlib`, один `yarl` target и один `voluptuous` target закрыты, а failed report-only probes пометили `aiohttp`, `async_timeout`, `sqlalchemy`, `app` и `common` как diagnosis-required вместо direct-write clusters. Source-aware sliced-string/rendered-body materializer исправил replay для `line[:100]` и REST `body`; `topics`, `domain`, `service`, `bucket`, string-membership, `.lower()`, source-backed attribute-object samples, `.value`, bounded nested data objects, recursive named-object replay, CPython `frozendict` compatibility, `types.GenericAlias` replay shim и suffix-based `*_filepath` string samples поддержаны. Replay subprocess теперь добавляет sandbox import paths только после stdlib bootstrap, поэтому локальный `src/types.py` не ломает compatibility shims. Active application CLI теперь имеет `--only-import-isolation-frontier`, `--import-isolation-missing-kind`, `--import-isolation-batch-profile dependency_heavy_direct_file`, `--import-isolation-cluster`, `--maximum-accepted-applications` и настоящий no-ledger-update dry-run без `--write`, плюс `--write-report` для сохранения probe evidence без ledger mutation; latest project-local exact-target writes accepted `langchain-ai__langchain / SSRFBlockedError`, `shy3130__tick-stock-panel / JobCancelledError`, and `astronomer__agents / NotFoundError` after a report-only project-local batch probe. Failed-probe analyzer `exception_pickle_failed_probe_analyzer_20260903T065213416880Z.json` классифицирует 2 latest failed probes и теперь рекомендует `constructor_state_contract_research`; behavior-contrast, reprobe и replay-capture repair lanes закрыты текущим циклом. Object-contract audit/admission `exception_pickle_object_contract_audit_20260902T095949529132Z.json` / `exception_pickle_object_contract_admission_20260902T100010126192Z.json` закрыли source-backed object-materializer хвост до нуля в текущем BI. Derived-message и derived-import audits пустые. LLM разрешён только advisory-only через `--use-l45-llm`; source apply authority не расширена.

Incremental collector подключён к `tools/project_development.py`: новый report получает digest checkpoint и один detector run, duplicate игнорируется. Fresh no-chain-hint batch `artifacts/self_development/self_development_fresh_blind_trial_20260830T183308224089Z.json` содержит десять post-cutoff runs: coverage `library=3`, `cli=3`, `framework=3`, matched `9`, out-of-scope contrast `1`, recognized `8`, reports with issues `2`. Только один eligible `recognition_gap` не достиг independent-project floor, поэтому status `evidence_exhausted`, candidates `0`, checks `6/6`. L0 staging/quarantine/rollback lifecycle реализован, но live staging не запускался без кандидата.

Matrix `artifacts/field_trials/role_project_type_evaluation_20260830T161442270918Z.json` records framework/plugin scores `9.7/9.7/9.7/9.8/10.0/9.8` for Analyzer through Reviewer with three native transformations and no evidence gaps. Workspace Analyzer is now `9.7` over five blind portfolio cases and five independent reports; Architect and downstream roles remain `not_applicable` because the correct output is an evidence-complete scope-selection stop. Target-scope contrast `artifacts/field_trials/project_target_scope_contrast_20260830T161826182156Z.json` is `4/4`: two positive lineages (`isort`, `mkdocs`) meet the `2/2` floor, while direct write and project-level subprocess controls remain rejected. Broad effect-heavy strata are still deferred and no source-apply authority was added.

Run the hardened foundation contour on local and cached GitHub Python projects, then use misses to improve only `Project Analyzer`, `Architect` and `SpecWriter` until their outputs are consistently project-specific and implementation-ready without expanding downstream roles.

Current foundation-role target: `Project Analyzer -> Architect -> SpecWriter` is measured by `tools/role_foundation_excellence.py`, not only by MVP readiness. The target is `>= 9.5/10` per role and is not yet met under the stricter scorer. Remaining improvement focus is higher teacher-reference fact precision, closing the Architect curriculum backlog, and increasing genuinely `strong` SpecWriter semantic targets without overfitting to individual project names.

Exception-pickle active sync marker: `exception_pickle_active_application_20260903T065054426561Z.json` latest exact-target repair ledger accepted `astronomer__agents / astro-airflow-mcp/src/astro_airflow_mcp/adapters/base.py:NotFoundError.__init__` after exact promotions for Alembic range/head errors, JMComic base error, two Redis HTTP errors, Pact interaction verification, Discord command invoke and GraphQL WS response errors; latest intelligence `exception_pickle_blocker_intelligence_20260903T065159200878Z.json` uses latest-blocker frontier accounting and reports `applied=178`, ledger `blocked=414`, latest-blocker frontier `146`, readmission frontier `0`, next lane `import_dependency_isolation_candidate:25`; latest planner `exception_pickle_import_cluster_planner_20260903T065218069738Z.json` marks `unknown:attribute_base_metaclass_risk` as `not_batch_ready`; latest failed-probe analyzer `exception_pickle_failed_probe_analyzer_20260903T065213416880Z.json` recommends `constructor_state_contract_research`. The current cycle also closed the `graphql`, `overrides`, `platformdirs` and `pydantic_settings` one-target clusters; Chroma exposed and verified narrow `dir`/`version` materializer coverage plus decorator-factory stub replay. The current cycle also closed `volcengine` and `vonage_jwt`; Volcengine verified `missing_services` list samples, and Vonage verified a bounded response-object sample with `status_code`, `url`, `content`, `text` and `json()`. The current project-local cycle added `project_local_direct_file`, filters out attribute-base and target self-attribute-gap cases, scopes failed-probe evidence by profile/cluster, and promoted `langchain-ai__langchain / SSRFBlockedError`, `shy3130__tick-stock-panel / JobCancelledError`, and `astronomer__agents / NotFoundError`; stub path joins now use the platform temp directory and `endpoint` string samples are supported. Class-state audit `exception_pickle_class_state_contract_audit_20260903T070847705234Z.json` splits the 10 attribute-base/metaclass-risk cases into 7 `base_constructor_passthrough_contract`, 2 `attribute_base_state_contract`, and 1 `target_self_state_gap_research`; the next narrow lane is parent-constructor argument/state preservation research before replay. Source line-limit audit `source_line_limit_audit_20260903T230204065085Z.json` now passes across the scanned Python corpus: 1513 Python files checked, 0 files exceed the 400-line limit. The final cleanup kept runtime clean, split the two remaining tool probes behind stable facades, split the project-map domain-profile plugin tests, and moved oversized runtime test suites into helper-backed context-bounded test modules. Post-split audit `post_split_audit_20260903T230640450590Z.json` records 24 mechanical facades and 55 helper-backed tests as visible design debt. This records the 400-line rule as enforced for runtime, tools, plugins and tests, not as optional refactoring guidance.
Derived-message sync marker: `exception_pickle_derived_message_audit_20260902T045536203364Z.json` reports 0 derived-message cases; source apply and KB promotion remain false.
Derived-import sync marker: `exception_pickle_derived_import_audit_20260902T045554559495Z.json` reports 0 derived import-isolation cases; source apply and KB promotion remain false.
