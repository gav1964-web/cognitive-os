# COGNITIVE_OS_TECHNICAL_BASELINE.md
**Инженерная спецификация и требования к MVP**

### 1. Спецификация контрактов (Уровень 1)
* **Single Responsibility:** Один плагин — одна capability с одним внешним entrypoint. Запрещен вызов плагина из плагина.
* **Plugin Isolation:** Плагин не знает о существовании других плагинов, не импортирует их код, не вызывает их entrypoint и не принимает решений о pipeline routing. Композиция capabilities выполняется только runtime-уровнем через Pipeline DSL и Capability Registry.
* **Plugin Layout:** Плагин является каталогом с кодом, manifest, схемами и контрактными тестами. Минимальная структура: `plugin.json`, `schemas/input.json`, `schemas/output.json`, `src/`, `tests/`.
* **Правило 400 строк:** Физический размер одного Python-файла внутри плагина <= 400 строк. Все, что больше — декомпозируется на модули внутри `src/`, но внешний entrypoint capability остается один. Нарушение правила блокирует загрузку capability.
* **Интерфейс:** Строгая валидация вход/выход через `JSON Schema` и typed runtime artifacts. Схемы хранятся как отдельные артефакты плагина. Никакого сквозного проброса всего стейта.

Project-to-capability extraction проходит dependency extraction policy до sandbox build. Self-contained functions допускаются; stdlib dependencies из allowlist могут быть импортированы в generated wrapper; unresolved local/domain calls, unsafe runtime boundaries (`subprocess`, network, secrets/database/write-side effects) и instance/class-bound methods без object adapter policy блокируют конкретный candidate, пока не появится явная политика bundling локальных project modules, process isolation или адаптации объектов. Грубая analyzer-метка `filesystem` сама по себе не блокирует candidate, потому что может означать read-only context; реальные ограничения filesystem фиксируются в side-effect manifest и downstream gates. Foundry обязан пройти ranked candidate list: если первый candidate не самодостаточен, он фиксируется в `skipped_candidates` с `dependency_policy_blocked`, после чего система пробует следующий ranked candidate. Proposal полностью блокируется только если все подходящие candidates нарушают dependency policy. Foundry не имеет права молча копировать соседние модули проекта или превращать несамодостаточную функцию в полурабочий plugin.

MVP capability library должна содержать не только demo HTML pipeline, но и базовые атомарные file/text/html/json/pdf/project transforms, чтобы planner мог строить полезные DAG без генерации нового кода на каждый шаг. Первые новые capabilities, проведенные через Foundry generate/validate/candidate/promote цикл, фиксируются как `translate_text` и `parse_pdf`. `parse_pdf` допускает optional production backend (`pypdf`) при наличии в окружении, но обязан иметь deterministic builtin fallback без обязательной внешней зависимости. File-conversion pack включает `markdown_to_text`, `markdown_to_rtf`, `csv_to_spreadsheet` и `spreadsheet_to_csv`; modern `.xlsx`/`.csv` paths исполняются как deterministic capabilities, а legacy `.xls`/`.xlwt`-зависимые paths должны останавливаться через Knowledge Gap preflight, если optional backend отсутствует. Project-analysis pack начинается с intake chain: `scan_project_tree` выполняет bounded read-only обход дерева с исключением noise directories, лимитами глубины/количества файлов, расширениями, notable files и признаками truncation; `detect_project_stack` извлекает языки, framework signals, dependency files, entrypoints, scripts и large artifacts, но исключает packaged-copy каталоги вида `*_install_package` из entrypoints/scripts; `read_many_files` безопасно читает выбранные текстовые файлы с лимитами и поддерживает `auto_discover` для README/config/start/API files без чтения noise directories вроде reports/artifacts/scratch; `extract_python_structure` строит AST summary по Python-файлам, imports, functions/classes, Flask/FastAPI routes, central nodes, broad functions, pure transform candidates, type-hint contracts, schema-like fields, import graph hints, test surface counters, explicit raise/try/except hints и external dependency categories. Pure transform candidate не считается чистым, если он напрямую вызывает локальную функцию с side effects: такой wrapper относится к orchestration/boundary анализу, а не к pure capability. `extract_runtime_commands` извлекает команды запуска/установки/пересборки из scripts; `project_map_report` собирает итоговый Markdown/JSON отчет с summary, risks и answer-oriented sections по scope, execution, capabilities, contracts/data, errors/state/reproducibility и runtime extraction readiness: data lifecycle, mixed responsibilities, hidden orchestrators, long-lived state, idempotency risks, quarantine candidates, process boundaries, contract-test strategy, resume/reuse plan, source strata и minimal extraction plan. Для первого extraction plan действует core-first policy: тесты, `conftest.py`, scratch/examples/docs/generated/tools, packaged copies, legacy analyzer branches и build/package helper scripts учитываются как контекст или шум, но не предлагаются как первые reusable core capabilities. `source_strata` обязан явно разделять `active_core`, `legacy_noise`, `context_only` и `packaged_copy`; ArchitectSkill использует это разделение как evidence при выборе first extraction candidates.

### 2. Capability Registry (Уровень 2.5)
Каждый плагин на диске обязан иметь паспорт в системном реестре, содержащий:
* `Determinism Grade`: Класс надежности от Grade A (чистая математика) до Grade E (внешняя нестабильная среда/LLM).
* `Side-effect Manifest`: Декларация разрешений на доступ к файловой системе (`write_scoped`, `read_only`), сети (`allowlist`, `none`) и системным секретам.
* `Lifecycle Status`: Текущее состояние capability: `active`, `degraded`, `quarantined`, `rebuilding`, `retired`.

Registry обязан предоставлять scoring выбора capabilities. Минимальный порядок предпочтения: `active` выше `degraded`, более высокий `Determinism Grade` выше низкого, меньшие side effects выше широких разрешений. `quarantined`, `rebuilding` и `retired` не участвуют в выборе для новых pipeline.

Registry quality metrics дополняют scoring после жестких lifecycle/contract ограничений: failure rate, success count и latency используются как операционный сигнал, но не могут сделать quarantined capability исполнимой.

Registry selection report должен объяснять порядок выбора capabilities через status, determinism grade, side effects, quality и latency.

### 2.1 Contract Registry

Capability Registry отвечает на вопрос "какие инструменты существуют и в каком они lifecycle-состоянии". Contract Registry отвечает на другой вопрос: "какие входы, выходы, side effects и межслойные маршруты разрешены runtime прямо сейчас".

Contract Registry реализуется в `runtime/contract_registry.py` как производный источник истины поверх plugin manifests, JSON Schemas, межслойных packet routes и API-контрактов ролевых артефактов. Он не дублирует `registry/capabilities.json` вручную и не становится вторым mutable registry. `GoalSpec`, `ProjectMapReport`, `ArchitectureDecisionRecord`, `TechnicalSpec`, `ImplementationPlan`, `TestPlan`, `PatchPackage`, `TestResult` и `ReviewFindings` публикуются в том же read-only catalog с producer/consumer и обязательными полями. Причина: один mutable реестр быстро приведет к drift, а производный contract catalog можно пересобрать и проверить в любой момент.

Минимальное enforcement-правило: Pipeline DSL валиден только если каждая node ссылается на capability с существующим executable contract (`active` или `degraded`), object input/output schemas и допустимым side-effect manifest. `quarantined`, `rebuilding` и `retired` contracts не исполняются даже если plugin-каталог физически существует. Межслойные packets валидируются по route/payload contract до сохранения как replay/debug artifact.

### 2.2 Skill Registry

Skill Registry отвечает за профессиональные когнитивные роли верхних уровней, а не за исполняемые инструменты. `registry/skills.json` описывает role skill id, слой, входные/выходные артефакты, entrypoint и forbidden actions. Он не заменяет Capability Registry и не участвует в выборе runtime plugins.

Минимальный набор начинается с `architect`: `ProjectMapReport + GoalStatement -> ArchitectureDecisionRecord`. ArchitectSkill живет на Уровне 4, может формировать subsystem boundaries, capability model, risks, non-goals, open questions, traceability, architecture options, chosen option, rejected options и brief для SpecWriterSkill, но не имеет права писать код, менять Capability Registry, исполнять pipeline или выполнять promote.

Следующая роль `spec_writer` преобразует `ArchitectureDecisionRecord -> TechnicalSpec`: bounded scope, requirements, acceptance criteria, preserved non-goals, traceability table и implementation handoff.

Роль `implementer` в текущем MVP является `Implementer Planner` и преобразует `TechnicalSpec -> ImplementationPlan`: patch scope, expected files, ordered implementation steps, verification commands, rollback plan и acceptance mapping. Она не пишет код сама; ее задача — подготовить bounded work package для отдельного исполнения.

Роль `programmer_executor` является отдельной ролью: `ImplementationPlan -> isolated patch package -> verification run -> TestResult -> Reviewer handoff`. В MVP она готова только в sandbox/no-source-edit режиме: `runtime/programmer_executor.py` и `tools/apply_implementation_plan.py` создают `PatchPackage`, копируют writable files в `source_snapshot`, запускают allowlisted verification commands, сохраняют `TestResult` и передают его Reviewer через role pipeline `--run-executor`. Общий executor блокирует прямое изменение source project даже при явном `--apply-source`. Отдельный специализированный контур `tools/sandbox_patch_review.py --apply-approved` не является частью общего executor: он может применить только валидированный sandbox package после явного human approval, проверки source identity/registry invariants и создания timestamped backup. Это узкий reviewed patch applier, а не универсальное разрешение на автономные source edits. Роль нельзя подменять `Implementer Planner`, Foundry dry-run или ручной работой Codex внутри сессии.

Для развития настоящей роли программиста вводится Rebuild Trial Loop: `source project -> Project Analyzer -> ProjectRebuildSpec -> generated project_x -> comparison report -> tooling/role backlog`. Первый полигон — `map -> map_x`. Цель этого контура не копировать проект побайтно, а строить архитектурно эквивалентный минимальный проект по evidence: entrypoints, routes, data artifacts, core capabilities, scenarios и runtime boundaries. `runtime/project_rebuild.py` и `tools/project_rebuild_trial.py` создают scaffold и сразу оценивают соответствие. `runtime/project_rebuild_app_templates.py` выбирает MVP-режим по evidence: `map_flask`, `api_fastapi` или `tooling_cli`, но behavioral layer не должен быть набором частных сравнителей по framework. `runtime/project_rebuild_behavior.py` строит общий behavioral probe plan из `ProjectRebuildSpec`: safe HTTP probes для read-only routes и capability-manifest probe для tooling/library проектов. Технологические различия скрываются в adapters, которые приводят Flask/FastAPI/etc. к единой форме response shape. До генерации scaffold система может снять source response blueprints по safe probes и использовать их как контракт формы ответа generated проекта. `runtime/project_rebuild_samples.py` переносит в rebuild только тонкие read-only срезы source JSON, а не synthetic-only fixtures. `runtime/project_rebuild_ui.py` выполняет статический UI smoke только там, где generated app имеет UI surface. Низкий или пограничный score является полезным сигналом для развития аналитика, архитектора, спецификатора, программиста, тестера и reviewer; система не должна считать stub scaffold полноценной реализацией.

Роль `tester` преобразует `TechnicalSpec + ImplementationPlan -> TestPlan`: acceptance tests, negative tests, smoke checklist, regression risks и reproducibility notes. Она не запускает тесты сама; execution остается за явным runtime/tooling шагом.

Роль `reviewer` преобразует `TechnicalSpec + ImplementationPlan + TestPlan + optional TestResult -> ReviewFindings`: findings, risk assessment, contract violations, architecture drift, rework tasks и recommendation. Ролевые skill-тесты в MVP являются deterministic artifact-contract tests и не обязаны обращаться к LLM. Если LLM backend будет добавлен в роль позже, его выход обязан проходить через тот же typed contract и deterministic fallback.

Ближайший стабильный gate верхнего контура — Role Foundation Pipeline: `ProjectMapReport -> ArchitectureDecisionRecord -> TechnicalSpec`. Он реализован в `runtime/role_foundation_pipeline.py` и `tools/role_foundation_run.py`, прогоняется минимум на одном benchmark-проекте и не запускает Implementer/Tester/Reviewer, Foundry, source edits или registry changes. Gate считается успешным, если ProjectMapReport содержит structured answers, ADR содержит chosen option, traceability и source context, а TechnicalSpec содержит requirements, source-linked acceptance criteria, traceability table, `source_evidence` и `extraction_contract`. `extraction_contract` выбирает ranked best-first candidate, содержит `ranked_candidates`, `candidate_score` и `selection_reason`; выбранный `candidate` должен быть первой строкой ранжирования. Benchmark corpus задает `expected_best_extraction_candidate`, а foundation field trial проверяет `candidate_match_score`.

Полный Role Pipeline Orchestrator связывает роли в расширенный контур: `ProjectMapReport -> ArchitectureDecisionRecord -> TechnicalSpec -> ImplementationPlan -> TestPlan -> ReviewFindings`. В базовом режиме он сохраняет общий отчет и возвращает `next_action`, но не исполняет Foundry, не меняет registry и не пишет код. Явный режим `--run-transform` может запустить Project Transform только до `promotion_ready`; promote остается отдельным осознанным действием. Это coordination layer для L4 artifacts, а не новый executor. ImplementerSkill становится основным следующим шагом только после стабилизации foundation-перехода `ProjectMapReport -> ADR -> TechnicalSpec`.

Role Pipeline Field Trial прогоняет этот контур по benchmark corpus и измеряет качество рельсов: наличие всех role artifacts, валидный `next_action`, отсутствие source/registry changes, отсутствие Foundry/LLM invocation по умолчанию. Дополнительный `implementation_score` проверяет, что `ImplementationPlan` явно связан с `TechnicalSpec.extraction_contract`: target совпадает с selected candidate, input/output contract перенесен в `contract_binding`, а benchmark target совпадает с `expected_best_extraction_candidate`. `qa_score` проверяет следующий переход: `TestPlan` покрывает тот же `implementation_target` через `test_target`, `contract_test_matrix` и negative tests, а `ReviewFindings` подтверждает coverage и отсутствие contract violations. Это quality gate перед подключением LLM backend к отдельным ролям.

Формулировки L4-артефактов считаются частью контракта качества. `runtime/role_artifact_quality.py` детерминированно оценивает ADR, TechnicalSpec, ImplementationPlan, TestPlan и ReviewFindings по конкретности, source-linked evidence, actionable handoff, verifiable acceptance criteria, ranked extraction contract, bounded writable scope, contract test matrix, review coverage и отсутствию generic placeholder-фраз. Gate `tools/role_artifact_quality.py` прогоняется по project-analyzer corpus; успешный результат требует `avg_score >= 0.9` и ноль warnings. Это не teacher ground truth и не LLM-судья, а защитный фильтр против красивого, но непригодного к реализации текста.

Тот же gate закреплен для External-3 (`map`, `5`, `004`) и GitHub-10. Эти corpus зависят от локальных/загруженных проектов, не входят в чистый checkout и запускаются в полном acceptance только через `--local-project-trials`; portable CI использует только версиированные benchmark fixtures. Model-backed GitHub L4 quality probe также не является deterministic CI gate и подключается отдельно через `--live-l4`. Для native-heavy или не Python-first проектов допустим явный `blocked_no_safe_candidate` handoff: система должна честно остановить implementation path, сохранить причину блокировки во всех L4-артефактах и не выдумывать source target ради прохождения проверки.

Architect Curriculum Local-3 является отдельным малым gate для teacher-reference улучшения только связки `Project Analyzer + ArchitectSkill`. Corpus живет в `curricula/architect_local_3`; runner `tools/architect_curriculum.py` строит fresh `ProjectMapReport`, затем deterministic `ArchitectureDecisionRecord`, сравнивает их с `teacher_reference.json` и пишет отчет в `artifacts/curricula/`. Teacher reference делится на `facts` и `judgments` и не считается абсолютной истиной: он нужен как проверяемый ориентир качества. Gate измеряет fact recall/precision и judgment score; improvement backlog должен указывать на конкретный недобор анализатора или архитектора, а не на необходимость расширять роли или подключать GitHub.

Важно: curriculum-контур не является самообучающейся системой. Он не генерирует себе ground truth, не принимает свои текущие ответы как эталон и не меняет код автоматически по собственному выводу. Улучшение выполняется как внешний teacher/corrector loop: человек или внешний корректировщик задает или правит reference, запускает прогон, анализирует расхождения, затем инженерно дорабатываются extractor/scorer/ranking/role logic и снова прогоняются тесты. Любые LLM artifacts в этом контуре являются advisory evidence, а не authority.

LLM в Cognitive OS трактуется как ограниченный источник гипотез внутри проверяемой инженерной машины. Модель может предложить интерпретацию, риск, архитектурную опцию, knowledge gap, repair candidate или semantic tie-break, но такой результат не становится истиной и не получает права на исполнение без evidence, typed artifact contract, deterministic hardening, conformance checks и тестов. Рабочий принцип развития: `LLM discovers; Code repeats; Contracts constrain; Tests decide`. Если повторяемый LLM-маршрут можно описать схемами, графом, правилами выбора и машинной проверкой качества, он должен постепенно вытесняться deterministic planner/rule/capability/repair operator, а LLM остается fallback для неизвестных или семантически неоднозначных случаев.

Приоритет вытеснения LLM закрепляется так: сначала L3.5 planning/recovery, затем Tester executable acceptance и Reviewer conformance checks, затем Implementer planning, фактическая часть Project Analyzer, knowledge acquisition planning и memory/template reuse. Architect остается L4-семантической ролью дольше остальных: код готовит evidence, ограничения и варианты, но смысловые компромиссы и новые архитектурные гипотезы допускают LLM или human review. Любой model-backed результат обязан сохранять раздельно raw model output, hardened output, `model_output_clean`, quality warnings, hardening actions и необходимость human review.

Controlled LLM fallback допускается только при отказе deterministic-схемы получить валидный результат. Такой fallback не повышает полномочия модели: LLM возвращает bounded proposal, который снова проходит тот же слой проверок. Для L3.5 это Pipeline DSL validation и MotorPlanPacket contract; для L4 — evidence hardening и raw-vs-hardened audit; для Tester — executable acceptance obligations; для Reviewer — deterministic conformance checks. Если proposal не проходит проверку, система возвращает blocked/needs_human_review, а не исполняет догадку.

Tester executable acceptance v0.2 реализует первый исполняемый слой поверх `TestPlan.executable_acceptance`: `runtime/executable_acceptance.py` генерирует pytest scaffold, запускает его в sandbox/work directory и сохраняет `ExecutableAcceptanceResult`. В v0.2 scaffold проверяет структуру obligations, наличие positive contract case, controlled malformed-input case и side-effect boundary case. Это не универсальный вызов произвольного project symbol; такой harness добавляется позже поверх уже существующего result contract. Reviewer читает `ExecutableAcceptanceResult` из `TestResult.executable_acceptance_result` и переводит failed result в conformance failure.

Порядок развития role curriculum фиксируется как обязательный safety rail:

1. Стабилизировать `Architect Curriculum Local-3`.
2. Довести `Project Analyzer + ArchitectSkill` по локальным reference gaps.
3. Прогнать и стабилизировать `Architect Curriculum External-3` на `map`, `5`, `004`.
4. Только после этого вводить `SpecWriter curriculum`.
5. После стабилизации SpecWriter переходить к `Implementer`, `Tester`, `Reviewer`.

Инвариант этого порядка: `teacher_reference != ground truth`; `teacher_reference` является проверяемым ориентиром. `facts` проверяются по evidence и считаются отдельно от `judgments`; `judgments` оцениваются отдельными checks. Код не правится автоматически по собственному выводу системы.

SpecWriter Curriculum Local-3 допускается только после зеленого Architect Local/External gates. Его задача — проверить не реализацию и не тестирование, а качество `TechnicalSpec`: extraction contract выбран из ADR evidence, candidate стоит первым в ранжировании, acceptance criteria ссылаются на source evidence, non-goals сохранены, а handoff ограничен следующим role artifact. Implementer/Tester/Reviewer остаются вне scope этого gate.

SpecWriter Curriculum External-3 расширяет этот gate на `map`, `5` и `004` через `curricula/spec_writer_external_local_3`. Он проверяет, что SpecWriter не выбирает первый контракт только по формальной "pure" метке, а учитывает evidence: framework request/response helpers, middleware, global/memory state и broad runtime boundaries должны проигрывать маленьким deterministic helpers. Для `map` ожидаемый первый контракт — `app.py:parse_bbox`, для `5` — `app/core/cache.py:build_key`, для `004` — `p004_family_registry.py:is_codegen_supported_family`. Этот gate остается teacher/corrector benchmark: source projects не правятся, reference не является ground truth, а расхождения ведут к доработке evidence extraction или ранжирования.

Implementer Curriculum Local-3 является следующим узким gate после SpecWriter. Он проверяет только `TechnicalSpec -> ImplementationPlan`: implementation target совпадает с `TechnicalSpec.extraction_contract`, input/output contract перенесены в `contract_binding`, patch scope и expected files ограничены evidence из spec, rollback покрывает expected files, verification commands присутствуют, acceptance mapping перенесен, registry защищен policy, а handoff идет только к Tester. Этот gate не пишет код, не запускает Foundry, не делает promote и не меняет registry; он проверяет качество work package перед будущим исполнительным шагом.

Implementer Curriculum External-3 переносит тот же gate на `map`, `5` и `004` через `curricula/implementer_external_local_3`. Он проверяет, что implementation plan удерживает target, выбранный SpecWriter External-3, и не превращает соседние risky helpers в основную цель: `map -> app.py:parse_bbox`, `5 -> app/core/cache.py:build_key`, `004 -> p004_family_registry.py:is_codegen_supported_family`. Для грязных проектов patch scope может включать соседние evidence sources, но expected files и rollback остаются ограниченными, registry policy запрещает неявные изменения, а live provider/local LLM calls, source edits, Foundry и promote остаются вне scope.

Architect Curriculum External-3 расширяет тот же gate на три живых локальных проекта: `map`, `5` и `004`. Corpus хранится в `curricula/architect_external_local_3` и намеренно остается локальным benchmark, завязанным на абсолютные пути `F:/ubuntu/test/...`; он не должен становиться обязательным portable тестом. Его задача - проверять качество на более шумных проектах: packaged copies, tests/tools/scratch filtering, active-vs-legacy ambiguity, route/API boundaries, LLM/provider orchestration и idempotency risks. Reference может включать `teacher_review`: описание грязного состояния проекта, ожидаемое поведение архитектора, известный шум и `tooling_improvement_targets`. Этот слой фиксирует не обучение модели, а benchmark-driven tool improvement: проекты остаются неизменными, а расхождения ведут к доработке анализатора, ранжирования, фильтров и evidence extraction. Для грязных multi-version проектов, таких как `004`, обязательный expected behavior: не чистить исходник, выделить active source family, пометить legacy analyzer branches как `legacy_noise` и исключить их из first extraction plan/dataflow при сохранении как evidence.

ArchitectSkill может иметь optional LLM advisory backend, но только как bounded overlay поверх deterministic ADR. Advisory backend получает уже построенные options/capabilities/risks, выбирает существующий option id и может добавить короткие risk notes. Он не имеет права генерировать новый исполнительный маршрут, требовать registry mutation или запускать Foundry. При сбое LLM фиксируется deterministic fallback.

### 3. Протокол прерываний (Interrupt Packet)
При падении плагина или пробое лимитов Уровень 3 формирует компактный JSON-пакет прерывания, а не текстовое описание:
```json
{
  "type": "CRITICAL_INTERRUPT",
  "source": "plugin_identity",
  "error_class": "timeout_or_exception",
  "state_ref": "checkpoint_id",
  "input_hash": "hash_string"
}
```

Асинхронное ядро исполняет Pipeline DSL как DAG: узлы без неудовлетворенных зависимостей могут запускаться параллельно, а ссылки `$nodes.<id>.output...` допустимы только на upstream dependency. При interrupt ядро приостанавливает планирование новых задач в текущем конвейере, фиксирует checkpoint состояния и корректно завершает, отменяет или дожидается уже запущенных операций по заданной политике. Snapshot должен быть достаточным для последующего воспроизведения (Replayability): версия pipeline, входные данные, ссылки на артефакты, параметры плагинов, hashes входа/выхода и причина прерывания.

Для каждого node должна быть применима node-level execution policy: timeout, retry budget и controlled cancellation. Timeout классифицируется как `transient`, проходит через общий interrupt/retry путь и не должен превращаться в скрытую бесконечную блокировку worker.

Runtime обязан вести durable execution journal: lifecycle событий pipeline/node (`resumed`, `started`, `completed`, `failed`, `retried`, `switched`) с timestamp, pipeline id, node id, capability id и latency. Journal нужен для replay, аудита и диагностики, а не для свободного текстового рассуждения.

Checkpoint должен поддерживать восстановление выполнения: completed nodes и их outputs не выполняются повторно, downstream nodes продолжают работу по тому же Pipeline DSL после `resume_pipeline(checkpoint_id)`.

Для небезопасных или потенциально зависающих capabilities должен быть доступен process boundary: запуск entrypoint в отдельном child process с kill-on-timeout. In-process режим допустим только для быстрых deterministic capabilities, где риск зависания контролируем.

Runtime должен иметь durable queue для pipeline jobs. Queue сохраняет Pipeline DSL snapshot, root input, priority, attempt count, max attempts, worker id, lease expiration, heartbeat timestamp, status, result/error и timestamps на диск. Claim job выполняется атомарно под lock, terminal statuses не перезаписываются повторным worker completion. Приоритеты jobs учитываются при claim: меньший priority number означает более ранний запуск.

Worker pool исполняет jobs из durable queue до idle или в bounded daemon-like loop, поддерживает ограничение `max_workers` и по умолчанию использует process boundary для параллельного исполнения plugins. Running jobs удерживаются lease/heartbeat; stale или lease-expired jobs должны возвращаться в `queued` через явный requeue policy, пока не исчерпан `max_attempts`, а не теряться после падения процесса. Job-level retry не заменяет node-level retry: job retry перезапускает pipeline job целиком, node retry работает внутри одного execution attempt.

Runtime control plane должен давать оператору минимальные команды наблюдения и управления: queue status, job inspect, job cancel, job requeue и runtime health report. Control plane работает поверх durable artifacts, registry, quality metrics, failures и execution journal; он не исполняет plugins и не меняет Pipeline DSL.

Runtime smoke suite должен запускать стандартные проверки одной командой: tests, compile, plugin check, registry doctor и MVP smoke scenarios.

### 4. Локальный инференс (Уровень 3.5)
Runtime поддерживает подключаемый backend локального инференса через OpenAI-compatible endpoint. `vLLM`, `Ollama`, `llama.cpp` и другие серверы допустимы как реализации за этим gateway, если они отдают совместимый chat/completions JSON API.

Локальная модель класса 7B-14B используется как быстрый транслятор паттернов, а не как автономный агент. Ее разрешенный профиль задач:

1. Генерация графа вызовов плагинов по целевой спецификации и схемам из Capability Registry.
2. Выбор capabilities по совместимости входных и выходных контрактов.
3. Проверка совместимости промежуточных артефактов между шагами pipeline.
4. Первичная моторная адаптация при штатных сбоях: retry policy, alternate parser, fallback source.
5. Компактная нормализация диагностического контекста перед передачей на Уровень 4.
6. Сигнализация по deterministic project-analysis reports: короткие machine impulses о candidate capabilities, broad functions, weak contracts, entrypoints, pipeline candidates, recovery loops, subsystem hotspots, ownership boundaries, architecture hotspots, mixed responsibilities, hidden orchestrators, idempotency risks, quarantine candidates, process-boundary candidates, checkpoint candidates, MVP extraction candidates и местах, где нужно решение человека или Уровня 4.

Выход Уровня 3.5 всегда валидируется через JSON Schema / Pipeline DSL. Невалидный выход не исполняется и превращается в interrupt для Уровня 4. Уровень 3.5 не имеет права напрямую исполнять плагины, изменять Capability Registry, создавать новые capabilities или обходить side-effect manifest.

Local LLM planner path обязан принимать от модели только JSON proposal, преобразовывать его через deterministic planner adapter и запускать `validate_pipeline()` перед любым enqueue/execute. Ошибка локального backend или невалидный JSON является controlled failure, а не поводом исполнять свободный текст.

Основной программный фасад Уровня 3.5 — `runtime/spinal_planner.py`. Он принимает `IntentPacket` от L4, строит валидированный `Pipeline DSL`, выпускает `MotorPlanPacket` для L2 и короткий `SignalPacket` для L4. Порядок выбора: зрелый memory template, deterministic required-capabilities chain, rule-based graph и только затем optional local LLM proposal. Ни один путь не может обойти `plan_from_spec()`/`validate_pipeline()`. При невозможности построить план L3.5 возвращает blocked `SignalPacket` с `needs_l4_decision=true`, а не исполняет частичный или текстовый план.

Для interrupt path `runtime/spinal_planner.py` принимает `InterruptPacket` от L2 и выполняет только моторную адаптацию внутри уже утвержденного намерения: `RETRY`, совместимый `SWITCH_PLUGIN`, controlled `STOP` или сигнал о необходимости `GENERATE_SPEC`. Метрика качества L3.5 задается `runtime/spinal_quality.py`: typed packets, validated pipeline, known capabilities, отсутствие прямого исполнения plugins и bounded escalation.

Обязательный вертикальный координатор пользовательских целей — `runtime/goal_runtime.py`. `tools/goal_run.py` не имеет права напрямую вызывать deterministic, graph или LLM planner и не собирает `MotorPlanPacket` самостоятельно. Координатор валидирует intent/motor/signal contracts, передает Pipeline DSL в L2 и собирает `ExecutionEventPacket`/`InterruptPacket`. Тот же `SpinalRecoveryController` используется sync executor, async executor и durable worker pool. Queue result сохраняет `layer_packets` и `level35_adaptations` как replay/audit trace. Каждый последовательный отказ, включая отказ fallback capability, создает новый `InterruptPacket` и снова проходит через L3.5. Recovery ограничен `max_adaptations`; исчерпание бюджета дает typed blocked `SignalPacket` и `STOP`, а не свободный retry loop.

Project-analysis L3.5 path обязан получать только compact fact digest из уже построенного `project_map_report`, а не читать проект напрямую. Его выход сохраняется в goal report как `level35_project_signals` и является коротким advisory signal packet, а не человеческим объяснением. L3.5 обязан иметь deterministic enrichment fallback для subsystem/hotspot/boundary signals, чтобы сбой локальной модели не обнулял полезные импульсы. Он не может менять Pipeline DSL, registry lifecycle, execution state, memory templates или ответы deterministic report.

### 4.1 Межслойные packet-контракты

Мозг, спинной мозг и runtime общаются не свободным текстом, а typed packets из `runtime/layer_packets.py`. Общий envelope: `schema_version`, `packet_id`, `packet_type`, `source_layer`, `target_layer`, `created_at`, `correlation_id`, `payload`.

Допустимые маршруты:

* `IntentPacket`: L4 -> L3.5. Содержит intent, objective, constraints, expected artifacts и success criteria.
* `MotorPlanPacket`: L3.5 -> L2. Содержит planner, capability chain, execution policy и validation summary.
* `SignalPacket`: L3.5 -> L4. Содержит короткие machine impulses, флаги `needs_l4_decision` и `blocked`.
* `ExecutionEventPacket`: L2 -> L3.5. Содержит node/capability lifecycle event и artifact refs.
* `InterruptPacket`: L2 -> L3.5. Нормализует controlled failure/interrupt без проброса сырого traceback как машинного протокола.

Все packets versioned, correlated через goal/session id, валидируются до сохранения и могут быть положены в goal report как replay/debug artifacts. L4 не имеет права отправлять `MotorPlanPacket` напрямую в L2; L3.5 не имеет права заменять `SignalPacket` человекочитаемой интерпретацией.

### 4.2 Принятые решения по открытым архитектурным развилкам

**Граница L3.5/L4 при сбоях.** L3.5 может выполнять только локальную моторную адаптацию внутри уже утвержденного намерения: повторить шаг по retry policy, выбрать совместимый fallback, остановить execution branch и отправить `SignalPacket`. Любое изменение цели, ослабление ограничений, запуск Foundry, пересборка capability или смена пользовательского результата требует L4 decision. Обоснование: это оставляет быстрые реакции быстрыми, но не дает локальному planner незаметно менять смысл задачи.

**Knowledge Gap Loop.** Недостаток знания является отдельным типом состояния, а не поводом для L4-фантазии. L4 фиксирует `KnowledgeGap`: question, needed_for, acceptable_sources, disallowed_sources, confidence_required, expiry_policy и decision_if_unresolved. L3.5 строит bounded acquisition plan из доступных information capabilities. L1 исполняет конкретные действия: read local files, inspect installed packages, fetch allowlisted official docs, query memory/dialogue, run safe probe, ask user или optional docs/web connector. Результат возвращается как `KnowledgeArtifact`: source, evidence, extracted_fact, confidence, collected_at, expires_at, limitations и trace to gap. L3.5 не интерпретирует artifact в человеческом виде; L4 использует его как evidence для route/role decision.

**Session Memory.** На текущем этапе вводится легкая session/dialogue memory как advisory context для L4, но не как исполнительный слой. Она хранит темы, решения, открытые вопросы и связи с прошлыми goal reports. Обоснование: контекст диалога уже влияет на качество L4-решений, но прямой доступ памяти к registry/pipeline создаст скрытую оркестрацию.

**Формат внешнего мышления L4.** Система не сохраняет chain-of-thought. Сохраняются только проверяемые внешние артефакты: `decision_summary`, `chosen_option`, `rejected_options`, `risk_notes`, `open_questions`, `confidence`, ссылки на факты и packets. Обоснование: этого достаточно для replay/debug и аудита без превращения внутреннего рассуждения модели в зависимость runtime.

**Capability Registry как источник истины.** Capability Registry является источником истины для lifecycle/status/quality выбора, но не исполняет контрактную проверку один. Contract Registry является обязательным enforcement-фильтром поверх него. Обоснование: registry хранит состояние инструмента, contract registry проверяет границы использования; разделение уменьшает coupling и делает drift заметным.

**Contract Registry.** Контракты capabilities, packet routes и будущие project-analysis contracts должны иметь единый catalog API. На MVP уровне он производный и read-only. Обоснование: L4/L3.5 должны планировать по формальным входам/выходам, а не по именам файлов или неявным соглашениям.

**MVP benchmark.** Успешность MVP измеряется не красотой одного отчета, а воспроизводимым прогоном на нескольких проектах с одинаковыми вопросами: полнота ответов, корректность evidence, полезность extraction plan, наличие packets/replay artifacts и controlled fallback при сбоях. Обоснование: это проверяет архитектуру как runtime-систему, а не как разовый генератор текста.

Первый закрепленный benchmark - `Project Analyzer Field Trial v0.1`. Corpus хранится в `benchmarks/project_analyzer/projects`, каждый проект имеет `expected_analysis.json`, а `tools/project_analyzer_benchmark.py` считает coverage, misses и false positives по категориям анализа. Следующие улучшения Project Analyzer должны подтягиваться через провалы этого benchmark, а не через добавление новых слоев.

### 5. Кузница возможностей (Уровень 3.2)
Уровень 3.2 отвечает за controlled build lifecycle capabilities. Он не является обычным plugin и не исполняет пользовательские pipeline. Его задача — создавать и пересобирать каталоговые plugins через проверяемый процесс.

Разрешенные операции Уровня 3.2:

1. `GENERATE_SPEC`: создать типизированную спецификацию capability.
2. `SANDBOX_BUILD`: создать candidate directory в изолированной зоне.
3. `TEST`: запустить контрактные тесты candidate.
4. `REGISTER`: обновить Capability Registry после успешной проверки.
5. `PROMOTE`: перенести candidate в `plugins/<plugin_id>/` и сделать capability доступной runtime.
6. `REBUILD_CAPABILITY`: пересобрать quarantined capability с сохранением контрактов.

Уровень 3.2 не имеет права:

* напрямую менять активный plugin без promotion gate;
* обходить sandbox/test/register/promote;
* выбирать стратегическую цель вместо Уровня 4;
* исполнять runtime pipeline вместо Уровня 2;
* создавать скрытые зависимости между plugins.

Admission gate обязан требовать не только happy-path contract tests, но и negative tests для отказа на плохом входе или нарушении контракта. Candidate без negative tests не может пройти promotion.

Каждый candidate обязан иметь `spec.json` и `requirements.lock`. `spec.json` фиксирует reusable purpose, input/output contracts, error policy и side effects. `requirements.lock` фиксирует внешние зависимости; любые внешние зависимости должны быть pinned через `==`. Promotion report обязан включать spec и dependency probe.

Static admission блокирует опасные imports/calls (`subprocess`, raw sockets, dynamic code execution) и filesystem operations без соответствующего side-effect permission. Side-effect manifest является исполняемым gate, а не декоративным описанием.

Foundry обязан поддерживать generate/validate spec tools и dry-run promotion. Dry-run выполняет все admission/probe/test/quality gates без копирования candidate в `plugins/` и без изменения registry.

### 5.1 Жидкий граф (Уровень 4)
Уровень 4 является стратегическим orchestrator, а не executor. Перед входом в Уровень 4 пользовательский prompt проходит Goal Intake: `runtime/goal_intake.py` строит `GoalSpec` со `schema_version`, intent, target, inputs/outputs, constraints, success criteria, allowed actions, assumptions, `ambiguity_score`, `field_confidence` и optional `ClarificationPacket`. `GoalSpec` валидируется JSON Schema contract с `additionalProperties=false`; невалидный или неполный prompt возвращает `ASK_CLARIFICATION` до вызова L4/L3.5. Clarification loop продолжает существующую `goal_id`, сохраняет исходный prompt, answers и `effective_goal`, после чего пересобирает `GoalSpec`.

Уровень 4 принимает валидированный `GoalSpec` как factual input и возвращает строго типизированное route decision: `PLAN_WITH_L35`, `ASK_CLARIFICATION`, `REQUEST_CAPABILITY_SPEC` или `STOP_UNSUPPORTED`.

Если route или role decision требует факта, которого нет в `GoalSpec`, memory, registry или source evidence, Уровень 4 обязан вернуть `NEEDS_INFORMATION`/`KnowledgeGap` вместо домысливания. На MVP этапе этот путь может понижаться до `ASK_CLARIFICATION`, если допустимый источник только человек, или до controlled stop, если нет разрешенной acquisition capability.

Уровень 4 не имеет права:

* напрямую исполнять plugins;
* менять Capability Registry;
* создавать или продвигать candidates;
* обходить validation Pipeline DSL;
* отдавать свободный текст как машинный протокол.

Единственный путь к исполнению: `Level 4 decision -> Level 3.5 planner -> Pipeline DSL validation -> Level 2 runtime`.

Level 4 обязан сохранять goal session trace: исходная цель, `GoalSpec`, clarification answers, `effective_goal`, route decisions, deliberation artifact, L3.5 plan, execution result и final report. Это операционная эпизодическая память, а не долговременное знание.

Level 4 deliberation является auditable reasoning snapshot, а не исполняемым протоколом. Он фиксирует route, capability summary, memory/dialogue context, risk list, route alternatives, selected alternative и recommendation. Deliberation не имеет права заменять typed route decision, Pipeline DSL validation или policy gates.

Для project-analysis целей Уровень 4 отвечает за человеческую интерпретацию результата. Он получает expanded bounded deterministic facts и `level35_project_signals`, после чего сохраняет `level4_project_interpretation`: executive summary, capability decomposition, refactor plan, cognitive loop, open questions и confidence. После интерпретации допускается deterministic synthesis в `analysis_tasks`: proposed backlog с task id, типом, target, priority, evidence и acceptance criteria. Такой backlog помогает превратить анализ в дальнейшую работу, но не является Pipeline DSL, не исполняется автоматически и не меняет registry/runtime state. Уровень 4 может быть подключен только к отдельной cortex model с большим контекстным окном; default-профиль использует `GigaChat-Pro` через OpenAI-compatible gateway `http://127.0.0.1:8000/v1` и переопределяется переменными `COGNITIVE_OS_L4_MODEL` / `COGNITIVE_OS_L4_BASE_URL`. Этот профиль отделен от локального Уровня 3.5, модели которого запрещены для L4. Вызов L4 остается явным; при недоступности cortex provider Уровень 4 обязан использовать controlled deterministic fallback без обращения к локальной LLM. Это речь/смысловой слой и постановщик задач, а не машинный протокол исполнения.

Для project-analysis интерпретаций L4 дополнительно проходит deterministic quality gate. `runtime/project_l4_quality.py` оценивает `summary_grounding`, `capability_grounding`, `actionability` и `uncertainty_honesty`; `tools/github_l4_interpretation_probe.py` применяет этот gate к GitHub benchmark corpus. Успешный gate требует внешнего L4-вызова без fallback, отсутствия context-only capabilities и нулевого списка quality warnings. Это защищает систему от красивых, но незаземленных формулировок.

Route alternatives должны оцениваться прозрачно: risk score, cost score, confidence score, blockers, evidence и total score. Минимальный набор путей: mature memory template, deterministic known capability chain, L3.5 LLM planner fallback и terminal alternatives для clarification/spec/stop. Выбор альтернативы не создает Pipeline DSL и не исполняет plugins; он только объясняет, какой planning path должен быть попробован первым.

Поверх goal reports допускается производный Memory Index. Он пересобирается из сохраненных reports, хранит компактные признаки прошлых goals, route decisions, pipeline ids, использованных capabilities и execution status. Индекс является кэшем/навигацией по опыту, а не самостоятельным authority.

Memory recommendation может подсказать `CONSIDER_REUSE_PREVIOUS_PLAN` для похожей успешной цели, но не имеет права напрямую запускать pipeline, менять registry или обходить `Level 4 decision -> Level 3.5 planner -> Pipeline DSL validation -> Level 2 runtime`.

Memory Index может строить plan templates из успешных reports. Template группируется по цепочке capabilities, форме inputs и edges, хранит support count, success/failure counts, safety status и примеры goals. Это процедурная память, но не исполняемый план.

Template safety policy обязана отличать immature, mature и blocked templates. Template становится mature только после нескольких successful reports той же формы и при отсутствии failed reports той же формы. Любой failed report той же формы блокирует template recommendation до будущей явной repair/decay-политики.

Template instantiation обязана учитывать совместимость с текущим контрактом capability chain. Если mature template был построен до изменения входного контракта critical node, он не должен молча обходить deterministic planner. Для project-analysis chain устаревший template, где `read_many_files` использует фиксированный список путей вместо `auto_discover`, считается stale и отклоняется с fallback к deterministic required-capabilities planner.

Template Instantiator может превратить template в candidate proposal только при достаточном score/support, `safety_status=mature` и строго `active` capabilities. `degraded` capabilities допускаются для обычного planner/recovery, но не для быстрого template path. При любой ошибке template path обязан уступить L3.5 LLM planner или остановиться контролируемо.

Для известных Level 4 routes допускается deterministic required-capabilities planner. Он использует строго заданные capability chains, включая `translate_text` и `parse_pdf`, формирует candidate proposal и прогоняет его через `plan_from_spec()` и Pipeline DSL validation. Этот путь должен использоваться после mature template path и до LLM fallback.

Перед route decision допускается memory preflight: система ищет похожие goal reports/templates и сохраняет результат в session/report. Если цель передается в Уровень 3.5, recommendation может быть использована как deterministic template candidate или planning hint, но любой путь обязан пройти deterministic Pipeline DSL validation.

Knowledge preflight является отдельным будущим шагом после memory/dialogue preflight. Он не заменяет runtime memory: memory отвечает "как мы делали похожее", Knowledge Gap Loop отвечает "какого факта нам не хватает и где его разрешено добыть". Любой найденный факт должен быть привязан к source/evidence и не может автоматически менять registry, benchmark или документацию.

MVP-реализация начинается с `runtime/knowledge.py` и L1 capability `inspect_installed_packages`. Первый закрепленный сценарий: legacy `.xls` conversion требует знания о наличии `xlrd/xlwt`; если backend отсутствует, goal report получает `KnowledgeGap` и `KnowledgeArtifact`, а L4 route останавливается с `L4_KNOWLEDGE_GAP_UNRESOLVED` до запуска spreadsheet pipeline.

Official docs и GitHub-поиск оформляются как external evidence sources, а не как источники автоматических решений. L1 capability `official_docs_fetch` читает только allowlisted documentation URLs и возвращает title, excerpt, domain и content hash; `runtime.knowledge.official_docs_knowledge()` оборачивает это в `KnowledgeArtifact` с confidence cap и ограничениями. L1 capability `github_repository_search` выполняет allowlisted GitHub Repository Search и возвращает только metadata: repository name, URL, description, language, stars, owner и license key. `runtime/knowledge_source_policy.py` ограничивает использование external evidence: official docs применяются для проверки API/library facts, GitHub — для pattern/library/edge-case/test inspiration; запрещены verbatim copy, popularity-as-correctness, override official docs и architecture change без локальных tests.

Clarification loop должен продолжать существующую goal session через `goal_id`: `goal_run.py --goal-id <goal_id> --clarification ...` добавляет ответ в session, строит `effective_goal`, пересобирает `GoalSpec` и переиспользует сохраненный `root_input`. Если Level 4 выбирает `REQUEST_CAPABILITY_SPEC`, система может создать typed spec request для Foundry, но не имеет права автоматически генерировать plugin code без Foundry gates.

LLM на Уровне 4 может выбирать только route enum. Невалидный LLM route decision не исполняется и должен иметь deterministic fallback.

LLM route decision проходит post-validation по action-specific invariants: `PLAN_WITH_L35` не может нести `missing_capability_hint` или `clarification_question`, `ASK_CLARIFICATION` обязан иметь вопрос, `REQUEST_CAPABILITY_SPEC` обязан иметь missing capability hint, а `STOP_UNSUPPORTED` не должен переносить executable capabilities. Неконсистентный LLM route понижается до deterministic route decision.

### 5.2 Диалоговая память
Диалоговая память является отдельным слоем и не должна смешиваться с runtime memory. Runtime memory отвечает на вопрос "как выполнить похожую задачу"; dialog memory отвечает на вопрос "о чем мы говорили, что решили, почему и к какой теме нужно вернуться".

Минимальные сущности будущего слоя:

* `dialogue session`: последовательность user/assistant turns и активный рабочий контекст.
* `topic thread`: именованная тема, к которой можно вернуться после переключения контекста.
* `decision record`: принятое архитектурное или продуктовое решение с причиной и датой.
* `open thread`: незакрытый вопрос, гипотеза или отложенная задача.
* `preference/principle memory`: устойчивые правила работы, например "код подтягивается к документации", "templates не обходят validation", "LLM не исполняет, а предлагает".

Dialog Memory не имеет права напрямую менять Capability Registry, строить Pipeline DSL или запускать plugins. Она может давать Level 4 contextual hints: текущая тема, связанные прошлые решения, открытые вопросы и конфликт с ранее принятыми принципами. Любой исполнительный путь остается через `Level 4 decision -> Level 3.5 planner -> Pipeline DSL validation -> Level 2 runtime`.

Статус слоя: thin MVP реализует durable session/topic/decision/open-thread/principle records, recall/summary CLI, deterministic compaction, производный topic graph с merge suggestions и опциональный `dialogue_preflight` в `goal_run.py`. Raw turns остаются источником истины; compact summaries и topic graph являются пересобираемыми contextual hints. Автоматический merge/decay остается следующим этапом; первый успешный Foundry-promote цикл для новой capability закрыт на `translate_text`.

### 6. Сценарий MVP-петли для проверки концепта
Для доказательства жизнеспособности runtime-среды собирается контур из 5 шагов:

**Pipeline:** Запуск цепочки из 3-х простых плагинов: скачать HTML -> распарсить `title` -> сохранить JSON.

**Сбой:** Искусственная подача некорректного URL, битого HTML или имитация блокировки (403 Error).

**Interrupt:** Пороговый фильтр ловит ошибку, приостанавливает pipeline и передает decision layer только JSON-пакет прерывания плюс ограниченный диагностический контекст.

**Decision:** По умолчанию deterministic policy выбирает строго одно действие из системного enum. LLM может подключаться только как optional advisory/route backend поверх typed packets и обязан иметь deterministic fallback.

**Адаптация:** Ядро исполняет выбранное действие через детерминированный контроллер, а не через свободный текстовый ответ LLM.

### 7. Этапы MVP
**Этап 1:** Поддержать только решения `[RETRY, STOP]`. Цель этапа — доказать, что interrupt packet, checkpoint и replay работают без расширения набора инструментов.

**Этап 2:** Добавить `SWITCH_PLUGIN`. Цель этапа — проверить Capability Registry, выбор альтернативного инструмента и совместимость входных/выходных схем.

**Этап 3:** Добавить `GENERATE_SPEC`, но не прямую генерацию исполняемого кода в общий registry. Верхний слой может создать только спецификацию нового capability. Микро-плагин создается в песочнице, проходит тесты, получает паспорт, проверяется по side-effect manifest и только после этого может быть повышен до постоянного инструмента.

### 8. Политика безопасного расширения
Новый capability считается частью системы только после прохождения минимального жизненного цикла:

1. `GENERATE_SPEC`: LLM создает типизированную спецификацию входа, выхода, ошибок и side effects.
2. `SANDBOX_BUILD`: код или адаптер создается в изолированной директории без доступа к секретам и произвольной записи.
3. `TEST`: запускаются контрактные тесты, negative tests и проверка replay на фиксированных входах.
4. `REGISTER`: Capability Registry получает паспорт инструмента, determinism grade, side-effect manifest и hash версии.
5. `PROMOTE`: инструмент становится доступен runtime только после успешной проверки.

### 9. On-Demand Capability Quarantine
Система не запускает постоянный фоновый аудит всех capabilities. Карантин включается только по факту реального сбоя во время исполнения pipeline.

При падении плагина ядро классифицирует ошибку:

* `transient`: timeout, rate limit, временная сетевая ошибка, временный 403.
* `input_error`: плохой вход, несовместимый формат, отсутствующие обязательные поля.
* `contract_error`: плагин нарушил заявленную output schema или вернул несовместимый артефакт.
* `dependency_error`: `ImportError`, `ModuleNotFoundError`, `AttributeError`, несовместимая версия библиотеки или внешний API.
* `runtime_error`: непредвиденное падение без устойчивого fingerprint.

Плагин переводится в `quarantined`, если:

1. Ошибка классифицирована как `dependency_error`.
2. `contract_error` повторяется на валидных входах больше заданного порога.
3. Hash версии capability изменился, а контрактные тесты не проходят.

При переводе в карантин runtime:

1. Приостанавливает текущий pipeline и фиксирует checkpoint.
2. Обновляет `Lifecycle Status` capability в Capability Registry.
3. Записывает `failure_fingerprint`: error class, traceback hash, input hash, version hash и checkpoint id.
4. Исключает capability из новых pipeline до выхода из карантина.
5. Формирует interrupt для Уровня 3.5 или Уровня 4 с рекомендацией `GENERATE_SPEC` / `REBUILD_CAPABILITY`.

Capability может вернуться в `active` только после прохождения цикла sandbox/test/register/promote. Временные ошибки класса `transient` не переводят capability в карантин и обрабатываются retry policy.
