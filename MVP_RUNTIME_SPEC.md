# MVP_RUNTIME_SPEC.md
**Минимальная исполнимая спецификация Cognitive OS Runtime**

### 1. Цель MVP
Проверить не интеллект верхнего слоя, а надежность нижней runtime-механики:

1. Запустить pipeline из нескольких детерминированных plugins.
2. Зафиксировать сбой в одном plugin.
3. Приостановить pipeline и сохранить checkpoint.
4. Сформировать typed interrupt packet.
5. Обновить Capability Registry при необходимости quarantine.
6. Принять решение через deterministic policy stub.
7. Завершить pipeline или продолжить через альтернативный plugin.

Базовый MVP не требует LLM для исполнения известных chains. Вероятностные пути подключаются как optional advisory/planning layers поверх проверяемых фактов и всегда имеют deterministic fallback.

### 2. Минимальная структура проекта
```text
plugins/
  __init__.py
  fetch_html/
    plugin.json
    schemas/
      input.json
      output.json
    src/
      __init__.py
      main.py
    tests/
      test_contract.py
  parse_title/
    plugin.json
    schemas/
      input.json
      output.json
    src/
      __init__.py
      main.py
    tests/
      test_contract.py
  parse_title_fallback/
    plugin.json
    schemas/
      input.json
      output.json
    src/
      __init__.py
      main.py
    tests/
      test_contract.py
  save_json/
    plugin.json
    schemas/
      input.json
      output.json
    src/
      __init__.py
      main.py
    tests/
      test_contract.py
  normalize_text/
    ...
  hash_payload/
    ...
  json_select/
    ...
  read_text_file/
    ...
  write_text_file/
    ...
  list_files/
    ...
  json_transform/
    ...
  extract_links/
    ...
  markdown_to_text/
    ...
  markdown_to_rtf/
    ...
  translate_text/
    ...
  parse_pdf/
    ...
  csv_to_spreadsheet/
    ...
  spreadsheet_to_csv/
    ...
  inspect_installed_packages/
    ...
  official_docs_fetch/
    ...
  github_repository_search/
    ...
  scan_project_tree/
    ...
  detect_project_stack/
    ...
  read_many_files/
    ...
  extract_python_structure/
    ...
  extract_runtime_commands/
    ...
  project_map_report/
    ...

registry/
  capabilities.json

runtime/
  models.py
  async_executor.py
  durable_queue.py
  worker_pool.py
  plugin_loader.py
  plugin_lint.py
  integrity.py
  registry.py
  pipeline.py
  executor.py
  checkpoint.py
  execution_journal.py
  interrupt.py
  quarantine.py
  failure_log.py
  quality.py
  control_plane.py
  process_runner.py
  registry_events.py
  local_inference.py
  deterministic_goal_planner.py
  graph_planner.py
  llm_graph_planner.py
  goal_orchestrator.py
  goal_intake.py
  level4_deliberation.py
  goal_session.py
  goal_report.py
  memory_index.py
  template_instantiator.py
  role_skills.py
  planner_stub.py
  policy_stub.py

pipelines/
  fetch_parse_save.json

artifacts/
  checkpoints/
  outputs/

generated/
  candidates/

tools/
  foundry_admission.py
  check_plugins.py
  generate_plugin_candidate.py
  promote_candidate.py
  rebuild_capability.py
  registry_doctor.py
  enqueue_pipeline.py
  run_worker_pool.py
  queue_status.py
  job_inspect.py
  job_cancel.py
  job_requeue.py
  runtime_report.py
  queue_cleanup.py
  registry_selection_report.py
  runtime_smoke.py
  mvp_acceptance.py
  generate_capability_spec.py
  validate_capability_spec.py
  llm_plan_pipeline.py
  goal_intake.py
  goal_run.py
  memory_rebuild.py
  memory_search.py
  memory_templates.py
  memory_instantiate.py
  dialogue_memory.py
  field_trial_report.py
  project_analyzer_benchmark.py
  project_extraction_proposal.py
  project_transform.py
  role_skill_run.py
  role_foundation_run.py
  architect_curriculum.py
  spec_writer_curriculum.py
  stage2_debug_loop_probe.py
```

### 3. Capability Passport
Plugin является каталогом, а не одиночным файлом. Каталог содержит код, схемы, локальный manifest и контрактные тесты. Это позволяет не раздувать entrypoint, держать схемы отдельно от исполнения и декомпозировать код, если реализация приближается к лимиту 400 строк.

Минимальный plugin layout:

```text
plugins/<plugin_id>/
  plugin.json
  schemas/
    input.json
    output.json
  src/
    __init__.py
    main.py
  tests/
    test_contract.py
```

Правило ответственности остается прежним: один plugin предоставляет одну capability. Если код capability становится крупнее одного файла, он разбивается внутри `src/` на модули, но внешний entrypoint остается один.

Plugin isolation является обязательным инвариантом: plugin не знает о существовании других plugins, не импортирует их код, не вызывает их entrypoint, не хранит fallback routing и не строит pipeline. Любая композиция capabilities выполняется только runtime-уровнем через Pipeline DSL, Capability Registry и policy layer.

Каждый plugin обязан иметь локальный `plugin.json` и агрегированную запись в `registry/capabilities.json`.

Contract Registry реализуется в `runtime/contract_registry.py` как производный read-only catalog поверх plugin manifests, JSON Schemas, межслойных packet routes и role artifact APIs. Pipeline validation обязана проверять capability не только по наличию в Capability Registry, но и по executable contract: lifecycle `active|degraded`, object input/output schemas, `additionalProperties=false` и допустимый side-effect manifest. Packet contracts используют тот же enforcement-подход: route/payload валидируются до сохранения в goal report. Role artifacts публикуют producer, consumers и required fields; это API между ролями, а не каталог произвольных отчетов.

Knowledge Gap Loop вводится как контрактный контур поверх существующих слоев. Минимальные артефакты: `KnowledgeGap` (`question`, `needed_for`, `acceptable_sources`, `confidence_required`, `decision_if_unresolved`) и `KnowledgeArtifact` (`source`, `evidence`, `extracted_fact`, `confidence`, `collected_at`, `expires_at`, `limitations`, `gap_id`). L4 создает gap, L3.5 планирует acquisition path, L1 capabilities выполняют чтение/поиск/probe, а L4 интерпретирует artifact. Этот контур не дает L4 прямого доступа к filesystem/web/shell. MVP реализует локальный installed-package сценарий через `runtime/knowledge.py` и capability `inspect_installed_packages`: legacy `.xls` conversion проверяет наличие `xlrd/xlwt`, сохраняет evidence и останавливается до исполнения, если backend отсутствует. Для внешних фактов добавлен allowlisted `official_docs_fetch`: он читает только явно разрешенные official docs URLs и возвращает excerpt/hash metadata как evidence, а не свободный web browsing.

Корневой `plugins/__init__.py` существует только как package marker и не выполняет тяжелую загрузку при import. Загрузка manifests, schemas и entrypoints выполняется явным runtime-компонентом `runtime/plugin_loader.py`, чтобы import Python-модуля не имел скрытых side effects.

Задачи `plugin_loader.py`:

1. Просканировать `plugins/*/plugin.json`.
2. Загрузить и провалидировать `schemas/input.json` и `schemas/output.json`.
3. Сверить локальные manifests с `registry/capabilities.json`.
4. Подготовить in-memory catalog активных capabilities.
5. Не импортировать код plugin до момента фактического исполнения node.

```json
{
  "id": "parse_title",
  "version": "0.1.0",
  "entrypoint": "plugins.parse_title.src.main:run",
  "input_schema_ref": "plugins/parse_title/schemas/input.json",
  "output_schema_ref": "plugins/parse_title/schemas/output.json",
  "determinism_grade": "B",
  "side_effects": {
    "filesystem": "none",
    "network": "none",
    "secrets": "none"
  },
  "lifecycle_status": "active",
  "version_hash": "sha256:..."
}
```

Пример `schemas/input.json`:

```json
{
  "type": "object",
  "required": ["html"],
  "properties": {
    "html": { "type": "string" }
  }
}
```

Пример `schemas/output.json`:

```json
{
  "type": "object",
  "required": ["title"],
  "properties": {
    "title": { "type": "string" }
  }
}
```

Обязательные статусы:

* `active`: plugin доступен для новых pipeline.
* `degraded`: plugin доступен для исполнения, но имеет предупреждения или повышенный failure rate; planner должен предпочитать `active` alternative при равной совместимости.
* `quarantined`: plugin исключен из новых pipeline.
* `rebuilding`: plugin проходит sandbox/test/register/promote.
* `retired`: plugin больше не используется.

Capability selection использует registry scoring: `active` предпочтительнее `degraded`, высокий `determinism_grade` предпочтительнее низкого, минимальные side effects предпочтительнее широких разрешений. `quarantined`, `rebuilding` и `retired` исключаются из выбора.

### 4. Pipeline DSL
Pipeline описывается декларативным JSON-графом.

```json
{
  "id": "fetch_parse_save",
  "version": "0.1.0",
  "nodes": [
    {
      "id": "fetch",
      "capability": "fetch_html",
      "input": {
        "url": "$input.url"
      }
    },
    {
      "id": "parse",
      "capability": "parse_title",
      "input": {
        "html": "$nodes.fetch.output.html"
      }
    },
    {
      "id": "save",
      "capability": "save_json",
      "input": {
        "data": "$nodes.parse.output",
        "path": "$input.output_path"
      }
    }
  ],
  "edges": [
    ["fetch", "parse"],
    ["parse", "save"]
  ],
  "retry_policy": {
    "max_attempts": 2,
    "retry_on": ["transient"],
    "node_timeout_seconds": 10,
    "process_boundary": false
  }
}
```

Runtime поддерживает конечный DAG без циклов. Узлы без неудовлетворенных dependency edges могут запускаться параллельно в async executor. Ссылка `$nodes.<id>.output...` допустима только на upstream node, связанный dependency edge напрямую или транзитивно. Циклы, self-edge, duplicate edges и ссылки на unrelated node блокируют запуск pipeline на этапе validation.

`retry_policy` может включать `node_timeout_seconds`. Timeout трактуется как `transient` failure и проходит через общий interrupt/retry/degraded путь.

`process_boundary=true` запускает plugin entrypoint в отдельном child process. Это дает kill-on-timeout для зависших plugins, но дороже обычного in-process режима и не используется по умолчанию для дешевых deterministic capabilities.

### 5. Runtime State Machine
Runtime имеет фиксированный набор состояний:

```text
READY -> RUNNING -> PAUSED -> INTERRUPTED -> ADAPTING -> RUNNING
                                      |             |
                                      v             v
                                   STOPPED       FAILED
```

Смысл состояний:

* `READY`: pipeline загружен, registry проверен, входные данные валидны.
* `RUNNING`: executor выполняет ready nodes по dependency order.
* `PAUSED`: новые nodes не запускаются, текущий execution context фиксируется.
* `INTERRUPTED`: сформирован interrupt packet.
* `ADAPTING`: policy выбирает действие и runtime применяет его.
* `STOPPED`: pipeline остановлен контролируемо.
* `FAILED`: runtime не смог восстановиться или нарушен системный инвариант.

Перед переходом в `RUNNING` runtime валидирует Pipeline DSL: все node ids уникальны, capabilities существуют и имеют `active` или `degraded` status, edges образуют acyclic DAG, а `$nodes.<id>.output...` ссылки указывают только на upstream dependencies.

### 6. Error Classification
При падении plugin executor классифицирует ошибку:

* `transient`: timeout, rate limit, временная сеть, временный 403.
* `input_error`: плохой вход или несовместимый формат.
* `contract_error`: output не проходит schema validation.
* `dependency_error`: `ImportError`, `ModuleNotFoundError`, `AttributeError`, несовместимая версия библиотеки.
* `runtime_error`: прочая непредвиденная ошибка.

Правило MVP:

* `transient` может идти в retry.
* `input_error` останавливает pipeline без quarantine.
* `dependency_error` сразу переводит capability в `quarantined`.
* `contract_error` переводит capability в `quarantined` только после повторения на валидных входах.
* `runtime_error` создает interrupt без автоматического quarantine.

### 7. Checkpoint
Checkpoint сохраняется при каждом interrupt.

```json
{
  "checkpoint_id": "chk_2026_06_29_001",
  "pipeline_id": "fetch_parse_save",
  "pipeline_version": "0.1.0",
  "state": "PAUSED",
  "current_node": "parse",
  "completed_nodes": ["fetch"],
  "node_outputs": {
    "fetch": {
      "artifact_ref": "artifacts/outputs/fetch.json",
      "output_hash": "sha256:..."
    }
  },
  "input_hash": "sha256:...",
  "registry_hash": "sha256:..."
}
```

Checkpoint не обязан хранить большие payload прямо в JSON. Большие данные сохраняются как artifacts, а checkpoint содержит ссылки и hashes.

Runtime поддерживает `resume_pipeline(checkpoint_id)`: восстановление root input, completed nodes и node outputs из checkpoint с продолжением только незавершенных downstream nodes.

Execution journal пишется в `artifacts/execution/journal.jsonl` и фиксирует `pipeline_resumed`, `node_started`, `node_completed`, `node_failed` с pipeline id, node id, capability id и latency.

Quality metrics пишутся в `artifacts/registry/quality.json`: runs, successes, failures, failure_rate и average latency по capability. Эти данные участвуют в registry scoring после lifecycle status, determinism grade и side-effect score.

L4 role artifacts additionally pass a wording-quality gate. `runtime/role_artifact_quality.py` checks `ArchitectureDecisionRecord`, `TechnicalSpec`, `ImplementationPlan`, `TestPlan` and `ReviewFindings` for concrete source-linked statements, actionable handoff, ranked extraction contract, verifiable acceptance criteria, bounded writable scope, contract test matrix, review coverage and absence of generic placeholder phrases. `tools/role_artifact_quality.py` runs this gate on the project-analyzer benchmark corpus and fails if average score is below `0.9` or any artifact emits warnings. This is a deterministic evaluator: it does not call LLM and does not claim semantic ground truth; it only protects the role pipeline from vague, non-implementable prose.

The same role-quality gate can also be run on External-3 (`map`, `5`, `004`) and GitHub-10. These machine-local/downloaded corpora are enabled in full acceptance only through `--local-project-trials` and are not portable CI fixtures. Native-heavy or non-Python-first projects may produce an explicit `blocked_no_safe_candidate` handoff. This is a valid L4 result when the block is carried through Architect, SpecWriter, Implementer, Tester and Reviewer without inventing a source target or widening writable scope.

Durable queue хранит jobs в `artifacts/queue/jobs/<job_id>.json`. Каждый job содержит Pipeline DSL snapshot, root input, статус (`queued`, `running`, `succeeded`, `stopped`, `failed`, `cancelled`), priority, attempt count, max attempts, worker id, lease expiration, heartbeat timestamp, result/error и timestamps. Claim выполняется под lock-файлом, чтобы несколько workers не взяли один job. Jobs с меньшим `priority` выбираются раньше.

Worker pool забирает queued jobs через `runtime/worker_pool.py`, исполняет их через runtime executor и записывает terminal status обратно в durable queue. По умолчанию worker pool форсирует `process_boundary=true`, чтобы параллельные workers не делили in-process plugin imports и могли убивать зависшие plugin executions по timeout.

Running job удерживается worker lease. Worker обязан обновлять heartbeat и продлевать lease; если lease истек или job стал stale, явная requeue policy возвращает job в `queued`, пока не исчерпан `max_attempts`. После исчерпания attempts job становится `failed`.

Worker pool поддерживает два режима:

* `run_until_idle`: обработать доступную очередь и завершиться.
* `run_loop`: bounded daemon-like loop с `max_cycles`, `idle_sleep`, stale requeue и ограничением jobs per cycle.

Минимальные CLI:

```text
python tools/enqueue_pipeline.py --pipeline pipelines/fetch_parse_save.json --input-json "{\"url\":\"mock://ok\",\"output_path\":\"artifacts/outputs/queued.json\"}" --priority 10 --max-attempts 3
python tools/run_worker_pool.py --workers 2 --loop-cycles 5 --requeue-stale-seconds 60
python tools/runtime_report.py --journal-tail 20
```

Операционные команды описаны в `RUNTIME_OPERATIONS.md`. Control plane является read/control surface над уже существующими durable artifacts; он не подменяет runtime executor и не пишет свободный текст в машинные протоколы.

### 8. Interrupt Packet
Interrupt packet является единственным машинным сообщением между runtime и decision layer.

```json
{
  "type": "CRITICAL_INTERRUPT",
  "pipeline_id": "fetch_parse_save",
  "failed_node_id": "parse",
  "capability_id": "parse_title",
  "error_class": "dependency_error",
  "error_fingerprint": {
    "exception_type": "ImportError",
    "traceback_hash": "sha256:...",
    "input_hash": "sha256:...",
    "version_hash": "sha256:..."
  },
  "state_ref": "chk_2026_06_29_001",
  "capability_status": "quarantined",
  "suggested_actions": ["SWITCH_PLUGIN", "GENERATE_SPEC", "STOP"]
}
```

MVP допускает только действия:

* `RETRY`
* `SWITCH_PLUGIN`
* `STOP`

`GENERATE_SPEC` фиксируется в schema как action Уровня 3.2. Runtime не исполняет его напрямую: действие передается в Capability Foundry через controlled lifecycle.

### 9. Policy Stub
До подключения локальной LLM Уровня 3.5 и Уровня 4 решения принимает deterministic planner/policy stub.

Минимальная политика:

1. Если `error_class = transient` и retry budget не исчерпан, выбрать `RETRY`.
2. Если capability в `quarantined` и есть active fallback с совместимыми схемами, выбрать `SWITCH_PLUGIN`.
3. Если fallback нет, выбрать `STOP`.
4. Передавать `GENERATE_SPEC` только в явный Foundry flow, не исполняя свободный текст или непроверенный код.

Пример ответа:

```json
{
  "action": "SWITCH_PLUGIN",
  "replacement_capability": "parse_title_fallback",
  "reason_code": "QUARANTINED_CAPABILITY_WITH_COMPATIBLE_FALLBACK"
}
```

### 9.5 Goal Intake и Clarification Loop
Перед Level 4 любой пользовательский prompt нормализуется в `GoalSpec`. Этот слой не планирует pipeline и не исполняет capabilities; его задача - превратить человеческий запрос в проверяемое мини-ТЗ или остановить маршрут до уточнения.

Минимальный `GoalSpec` содержит:

* исходный и нормализованный prompt;
* `schema_version`;
* `intent`, `target`, inputs/outputs;
* constraints, success criteria и allowed actions;
* assumptions и `ambiguity_score`;
* `field_confidence` по ключевым полям;
* optional `ClarificationPacket`.

`GoalSpec` является typed artifact и валидируется JSON Schema contract до передачи дальше по маршруту. Схема использует `additionalProperties=false`; неизвестные поля считаются ошибкой контракта, а не advisory metadata. `field_confidence` показывает, какие части мини-ТЗ получены из явного входа (`root_input`, path, placeholder), а какие являются эвристической интерпретацией prompt.

Если обязательных полей не хватает, runtime возвращает `ASK_CLARIFICATION` с `ClarificationPacket`, а не вызывает L3.5/L4 для домысливания недостающих фактов. Ответ пользователя добавляется в существующую goal session, из него строится `effective_goal`, после чего `GoalSpec` пересобирается и маршрут продолжается в той же session. Исходный prompt, clarification history и effective goal сохраняются отдельно для аудита.

Инварианты:

1. Размытый prompt не должен попадать в L3.5 planner или executor.
2. Внешний L4 может быть вызван только после того, как `GoalSpec.status = ready` и schema validation пройдена.
3. Clarification loop продолжает существующую `goal_id`, не создает новую цель.
4. `root_input` сохраняется в session и переиспользуется при продолжении.
5. Уточнение не имеет права обходить Pipeline DSL validation, registry checks или Foundry gates.
6. L4 получает валидированный `GoalSpec` как factual input; сырой prompt остается audit trail, а не единственный источник решения.

Минимальные CLI:

```text
python tools/goal_intake.py --prompt "help me"
python tools/goal_run.py --root . --goal "help me"
python tools/goal_run.py --root . --goal-id <goal_id> --clarification "Normalize input text and hash it"
```

### 10. Quarantine Protocol
При quarantine runtime выполняет действия строго в таком порядке:

1. Переводит state machine в `PAUSED`.
2. Сохраняет checkpoint.
3. Обновляет `lifecycle_status` capability на `quarantined`.
4. Записывает `failure_fingerprint` в registry или отдельный failure log.
5. Формирует interrupt packet.
6. Передает interrupt в policy stub.
7. Применяет выбранное действие.

Quarantined capability не может использоваться в новых pipeline до успешного lifecycle `SANDBOX_BUILD -> TEST -> REGISTER -> PROMOTE`.

Failure events пишутся в `artifacts/failures/events.jsonl`. Каждая строка содержит timestamp, pipeline id, failed node id, capability id, error class, traceback hash, checkpoint id, capability status и принятое policy decision.

Registry использует single-writer policy: запись `registry/capabilities.json` выполняется под lock-файлом и через atomic replace временного файла. Это защищает registry от битого JSON при случайных параллельных smoke-запусках.

Изменения registry пишутся в `artifacts/registry/events.jsonl`: status transitions, quarantine, reset-from-plugins и promote/rebuild причины.

### 11. Plugin Generator Strategy
Plugin generator относится к Уровню 3.2: **Кузница возможностей (Capability Foundry)**. Это controlled build subsystem между decision layers и registry/plugin layer. Он создает и пересобирает capabilities, но не является обычным plugin и не исполняет пользовательские pipeline.

Seed plugins (`fetch_html`, `parse_title`, `parse_title_fallback`, `save_json`, `normalize_text`, `hash_payload`, `json_select`) созданы вручную, чтобы проверить runtime-петлю без зависимости от LLM code generation. Capability Foundry предоставляет controlled path для candidate generation, promotion и rebuild quarantined capability.

Foundry generator создает не активный plugin, а candidate directory:

```text
generated/candidates/<candidate_id>/
  plugin.json
  spec.json
  requirements.lock
  schemas/
    input.json
    output.json
  src/
    __init__.py
    main.py
  tests/
    test_contract.py
    test_negative.py
  README.md
```

Генератор должен быть совместим с каталоговым plugin layout и не должен встраивать схемы, metadata и тесты внутрь одного Python-файла.

В текущем MVP skeleton генератора представлен командой:

```text
python tools/generate_plugin_candidate.py --id normalize_text
```

Команда создает candidate layout, но не регистрирует и не продвигает capability.

Promotion выполняется отдельной командой:

```text
python tools/promote_candidate.py --id normalize_text
```

Promotion gate выполняет:

1. Проверку candidate layout.
2. Проверку `spec.json`: reusable capability, purpose, input/output contract, error policy и side effects.
3. Проверку manifest, schema shape, entrypoint boundary и side-effect policy.
4. Dependency probe по `requirements.lock`; внешние зависимости должны быть явно pinned через `==`.
5. Static admission: запрет опасных imports/calls и запрет filesystem operations без side-effect permission.
6. Проверку наличия contract tests и negative tests.
7. Запуск всех candidate tests в изолированном candidate-каталоге.
8. Копирование candidate в `plugins/<plugin_id>/`.
9. Перевод `lifecycle_status` в `active`.
10. Пересборку `registry/capabilities.json` из plugin manifests.
11. Запись отчета в `artifacts/promotions/<plugin_id>_<timestamp>.json`, включая spec и dependency probe.

Повторный promote существующего plugin запрещен без `--force`.

Rebuild quarantined capability запускается отдельной командой:

```text
python tools/rebuild_capability.py --id parse_title
```

MVP rebuild flow требует, чтобы capability уже была в `quarantined`. Команда создает rebuild candidate с тем же id, сохраняет прежние input/output schemas, прогоняет candidate tests и выполняет promote с `--force`. В текущем MVP ремонт является deterministic skeleton, а не LLM-генерацией.

Registry doctor представлен командой:

```text
python tools/registry_doctor.py --root .
```

Он сверяет `registry/capabilities.json` с фактическими каталогами plugins, вычисленными hashes и lifecycle status. Это maintenance tool, а не фоновый worker: он запускается явно в smoke/test/release flow.

Уровень 3.5 представлен контрактным фасадом `runtime/spinal_planner.py`, vertical coordinator `runtime/goal_runtime.py`, deterministic recovery stub `runtime/planner_stub.py` и rule-based graph planner `runtime/graph_planner.py`. `spinal_planner.py` принимает `IntentPacket` от L4, строит валидированный `Pipeline DSL`, возвращает `MotorPlanPacket` для L2 и короткий `SignalPacket` для L4; он не исполняет plugins и не меняет registry. `goal_runtime.py` является обязательной точкой планирования и исполнения для `goal_run.py`: CLI не выбирает planner напрямую и не фабрикует motor packet. `planner_stub.py` переводит interrupt packet в одно из действий `RETRY`, `SWITCH_PLUGIN`, `GENERATE_SPEC`, `STOP` по rule table. `graph_planner.py` строит простые pipeline по целевым rule ids и схемам известных capabilities. `GENERATE_SPEC` передается в L4 как решение, требующее верхнего уровня; L2 не запускает Foundry самостоятельно.

Graph Planner 2.0 добавляет structured goal spec:

```json
{
  "id": "spec_hash",
  "steps": [
    {"id": "normalize", "capability": "normalize_text", "input": {"text": "$input.text"}},
    {"id": "hash", "capability": "hash_payload", "input": {"value": "$nodes.normalize.output.text"}}
  ]
}
```

Planner возвращает Pipeline DSL и selection explanation по registry scoring. Итоговый Pipeline все равно проходит runtime validation перед enqueue/execute.

Spinal Planner contract:

```text
IntentPacket(L4 -> L3.5)
-> runtime.spinal_planner.plan_from_intent_packet()
-> validated Pipeline DSL
-> MotorPlanPacket(L3.5 -> L2)
-> SignalPacket(L3.5 -> L4)
```

Порядок выбора route: mature memory template, deterministic required-capabilities chain, deterministic known graph, optional local LLM proposal, затем blocked `SignalPacket` с `needs_l4_decision=true`. LLM-backed route возвращает только JSON proposal; `runtime/spinal_planner.py` повторно собирает Pipeline object и запускает `validate_pipeline()`. Interrupt path работает отдельно:

```text
InterruptPacket(L2 -> L3.5)
-> runtime.spinal_planner.adapt_from_interrupt_packet()
-> SignalPacket(RETRY | SWITCH_PLUGIN | GENERATE_SPEC | STOP)
```

Качество L3.5 проверяет `runtime/spinal_quality.py`: typed packets, validated pipeline, known capabilities, no direct plugin execution и bounded escalation.

`runtime/goal_runtime.py` передает в executor packet sink и recovery handler. L2 выпускает `NODE_STARTED`, `NODE_COMPLETED`, `NODE_RETRIED`, `NODE_RECOVERED` и `InterruptPacket`, сохраняя общий `correlation_id`. Каждый interrupt возвращается в L3.5; число адаптаций ограничено `max_adaptations` (default `2`). `SpinalRecoveryController` является общей реализацией для sync, async и queue workers. Если retry или fallback capability также падает, executor создает следующий checkpoint/interrupt и повторно вызывает controller; исчерпание бюджета завершается `L35_ADAPTATION_BUDGET_EXHAUSTED`. Async DAG не записывает исходный exception как node output после успешной адаптации. Durable worker использует `job_id` как correlation id и сохраняет packet/adaptation trace внутри terminal job result.

CLI probe:

```text
python tools/spinal_plan.py --root . --intent NORMALIZE_AND_HASH --objective "Normalize input text then hash it" --route-goal normalize_then_hash
python tools/spinal_plan.py --root . --intent CUSTOM_CHAIN --objective "Select JSON value and hash it" --allow-local-llm
python tools/spinal_benchmark.py --root . --write
```

Foundry spec tools:

```text
python tools/generate_capability_spec.py --id new_capability --purpose "Reusable purpose"
python tools/validate_capability_spec.py --spec generated/specs/new_capability.json
python tools/promote_candidate.py --id new_capability --dry-run
```

Stabilization tools:

```text
python tools/runtime_smoke.py --root .
python tools/registry_selection_report.py --root .
python tools/queue_cleanup.py --root . --archive-terminal
```

Local LLM planner path:

```text
python tools/llm_plan_pipeline.py --root . --base-url http://127.0.0.1:8000/v1 --model local --goal "Normalize input text from $input.text and hash it"
python tools/llm_plan_pipeline.py --root . --base-url http://127.0.0.1:8000/v1 --model local --goal "Normalize input text from $input.text and hash it" --execute --input-json "{\"text\":\" hello \"}"
```

Для известных Level 4 routes существует deterministic required-capabilities planner `runtime/deterministic_goal_planner.py`. Он строит candidate proposal для фиксированных capability chains (`list_files`, `read_text_file -> markdown_to_text -> write_text_file`, `read_text_file -> markdown_to_rtf -> write_text_file`, `fetch_html -> extract_links`, `normalize_text -> hash_payload`, `translate_text`, `parse_pdf`, `spreadsheet_to_csv`, `csv_to_spreadsheet`, project-analysis chain) и прогоняет его через `plan_from_spec()` и `validate_pipeline()`. Этот путь используется после compatible mature memory template и до LLM fallback. Для project-analysis chain planner использует `read_many_files.auto_discover=true`, чтобы выбирать README/config/start/API files по фактическому дереву проекта, а не по жесткому списку, пришитому к одному проекту.

LLM planner получает goal и registry catalog, возвращает только JSON proposal, затем `runtime/llm_graph_planner.py` преобразует proposal через deterministic `plan_from_spec()` и запускает `validate_pipeline()`. LLM не исполняет plugins, не пишет registry и не создает capabilities. Если локальная модель возвращает невалидный JSON, это controlled failure; для известных chains runtime должен предпочитать deterministic required-capabilities planner.

Project-analysis reports могут иметь optional двухступенчатую LLM-надстройку. Уровень 3.5 `runtime/project_signals.py` получает compact digest deterministic `project_map_report` и возвращает короткие машинные импульсы в `level35_project_signals`: `CAPABILITY_CANDIDATE`, `BROAD_FUNCTION`, `WEAK_CONTRACT`, `ENTRYPOINT_FOUND`, `PIPELINE_CANDIDATE`, `RECOVERY_LOOP_CANDIDATE`, `UNKNOWN_BOUNDARY`, `NEEDS_HUMAN_DECISION`, `SUBSYSTEM_HOTSPOT`, `OWNERSHIP_BOUNDARY`, `ARCHITECTURE_HOTSPOT`, `MIXED_RESPONSIBILITY`, `HIDDEN_ORCHESTRATOR`, `IDEMPOTENCY_RISK`, `QUARANTINE_CANDIDATE`, `PROCESS_BOUNDARY_CANDIDATE`, `CHECKPOINT_CANDIDATE`, `MVP_EXTRACTION_CANDIDATE`. Это не человекочитаемый отчет, а ограниченный signal packet. L3.5 обязан иметь deterministic enrichment path: даже если локальная модель возвращает невалидный JSON, runtime сохраняет subsystem/hotspot/boundary/runtime-safety signals из deterministic facts.

Человекочитаемая интерпретация относится к Уровню 4: `runtime/project_deliberation.py` получает expanded bounded deterministic facts плюс `level35_project_signals` и возвращает `level4_project_interpretation` с ключами `executive_summary`, `capability_decomposition`, `refactor_plan`, `cognitive_loop`, `open_questions`, `confidence`. Поверх этого `runtime/project_tasks.py` детерминированно синтезирует `analysis_tasks`: proposed backlog из сигналов L3.5 и L4 refactor/open-question hints. Каждая задача имеет `task_id`, `type`, `title`, `target`, `priority`, `status=proposed`, `source`, `evidence`, `acceptance`; она не исполняется автоматически и не меняет runtime state. Уровень 4 может использовать только отдельную cortex model с большим контекстным окном через `--l4-model`, `--l4-base-url`, `--l4-api-key-env` и `--l4-context expanded|compact`; default-профиль L4 использует `GigaChat-Pro` через OpenAI-compatible gateway `http://127.0.0.1:8000/v1`, а `COGNITIVE_OS_L4_MODEL` и `COGNITIVE_OS_L4_BASE_URL` позволяют его явно переопределить. Локальные модели Уровня 3.5 (`local`, `qwen-local`, GGUF-профили) для L4 запрещены. Если expanded context не помещается в выбранную cortex model, L4 может один раз повторить запрос в compact mode и пометить `context_mode=compact_after_overflow`. Если cortex model недоступна, L4 возвращает controlled `deterministic_fallback` и не выполняет локальный LLM-вызов. Все project-analysis LLM artifacts advisory: они не меняют Pipeline DSL, Capability Registry, execution state и не подменяют фактические секции отчета.

Качество человекочитаемой L4-интерпретации проверяется отдельно от факта успешного вызова модели. `runtime/project_l4_quality.py` считает deterministic score по четырем шкалам: `summary_grounding`, `capability_grounding`, `actionability`, `uncertainty_honesty`. `tools/github_l4_interpretation_probe.py` применяет этот scorer к GitHub benchmark corpus и требует, чтобы capabilities не ссылались на context-only paths (`bench/`, `tests/`, `integration/`, docs/CI), summary не был placeholder/self-reference, refactor plan был actionable, а uncertainty соответствовала плотности фактов. `tools/mvp_acceptance.py` включает этот probe как L4 quality gate; успешный acceptance требует `quality_passed == project_count`, `quality_warnings == 0`, `fallbacks == 0` и `avg_quality_score >= 0.9`.

Межслойная связь фиксируется typed packets из `runtime/layer_packets.py`, а не свободным текстом. Envelope содержит `schema_version`, `packet_id`, `packet_type`, `source_layer`, `target_layer`, `created_at`, `correlation_id`, `payload`. Минимальный набор: `IntentPacket` (L4 -> L3.5), `MotorPlanPacket` (L3.5 -> L2), `SignalPacket` (L3.5 -> L4), `ExecutionEventPacket` и `InterruptPacket` (L2 -> L3.5). `goal_run.py` сохраняет packet artifacts в `layer_packets` goal report: intent перед планированием, motor plan после L3.5 planning, signal packet после project-analysis L3.5 signals.

Level 4 MVP представлен `runtime/goal_orchestrator.py`. Он принимает human goal и возвращает typed decision:

* `PLAN_WITH_L35`: передать цель в локальный planner Уровня 3.5.
* `ASK_CLARIFICATION`: запросить уточнение.
* `REQUEST_CAPABILITY_SPEC`: существующих capabilities недостаточно, нужен Foundry spec.
* `STOP_UNSUPPORTED`: цель небезопасна или вне границ MVP.

CLI:

```text
python tools/goal_run.py --root . --goal "Normalize input text from $input.text and hash it" --execute --input-json "{\"text\":\" hello \"}"
python tools/goal_run.py --root . --goal "Analyze project map" --execute --interpret-project-llm --input-json "{\"path\":\"F:\\\\ubuntu\\\\test\\\\map\"}"
python tools/goal_run.py --root . --goal "Analyze project map" --execute --interpret-project-llm --input-json "{\"path\":\"F:\\\\ubuntu\\\\test\\\\map\"}" --l4-model GigaChat-Pro
python tools/interpret_project_report.py --root . --report artifacts/goals/reports/<goal_id>.json --base-url http://127.0.0.1:8000/v1 --model local
python tools/project_tasks.py --root . --project "F:\\ubuntu\\test\\map" --priority P1
python tools/project_tasks.py --root . --task-id analysis_<id> --write-spec --spec-id extract_candidate
```

Уровень 4 не исполняет plugins напрямую, не меняет registry, не пишет candidates и не обходит validation. Его выход является route decision, а не свободным планом исполнения.

Goal sessions пишутся в `artifacts/goals/sessions/<goal_id>.json`, reports — в `artifacts/goals/reports/<goal_id>.json`. Сессия хранит исходную цель, root input, clarification answers, route decisions, Level 4 deliberation artifact, L3.5 plan refs, execution status и event trace.

Level 4 deliberation является наблюдаемым, но не исполняемым артефактом. Он фиксирует выбранный route, capability summary, memory/dialogue context, risk list, candidate route alternatives, selected alternative и recommendation (`continue_to_level35`, `return_route_decision`, `stop_or_request_capability`). Deliberation не может заменить route decision, Pipeline DSL validation или policy gates.

Route alternatives являются стратегической оценкой путей, а не планами исполнения. Минимальный набор альтернатив: `memory_template`, `deterministic_required_capabilities`, `llm_planner_fallback`, terminal alternatives для clarification/spec/stop. Каждая альтернатива содержит route, rationale, risk score, cost score, confidence score, blockers, evidence и total score. Selected alternative выбирается по прозрачному score с предпочтением вариантов без blockers.

Memory Index хранится в `artifacts/memory/memory_index.json`. Это производная, пересобираемая память поверх goal reports, а не новый источник истины. Индекс извлекает goal, route decision, pipeline id, использованные capabilities, execution status и completed nodes из `artifacts/goals/reports/*.json`.

Поиск памяти в MVP детерминированный: запрос и goals токенизируются, ранжирование выполняется через Jaccard similarity. Если лучший похожий report был успешно исполнен и имеет pipeline capabilities, индекс возвращает рекомендацию `CONSIDER_REUSE_PREVIOUS_PLAN`. Эта рекомендация не исполняется напрямую: Level 4/L3.5/L2 validation остаются обязательными.

Memory Index также строит plan templates из successful reports. Template группируется по цепочке capabilities, форме node inputs и edges, хранит `support_count`, `success_count`, `failure_count`, `safety_status`, `goal_ids`, пример goal и `pipeline_template`. Template является процедурной памятью, но не исполняемым артефактом.

Template safety policy:

* `immature`: меньше двух successful reports; template виден в индексе, но не рекомендуется.
* `mature`: два или больше successful reports и нет failures той же формы; template может быть рекомендован.
* `blocked_by_failures`: есть failed report той же формы; template не рекомендуется до явного восстановления через будущую политику repair/decay.

Template Instantiator может превратить рекомендованный template в candidate proposal только при достаточном score/support, `safety_status=mature` и строго `active` capabilities. `degraded` capabilities остаются допустимыми для обычного planner/recovery, но не для быстрого template path. Candidate проходит тот же deterministic `plan_from_spec()` и `validate_pipeline()`. Если template отсутствует, недостаточно похож или невалиден, система падает обратно на L3.5 LLM planner.

`goal_run.py` выполняет memory preflight перед route decision, пишет краткий результат в goal session event trace и включает полный `memory_preflight` в goal report. Если цель идет в Level 3.5, runtime сначала пробует deterministic template instantiation, затем deterministic required-capabilities planner для известных chains, и только после этого LLM planner. Модель может учитывать прошлый успешный plan/template, но обязана вернуть новый JSON proposal, который снова проходит deterministic `plan_from_spec()` и `validate_pipeline()`.

`knowledge_preflight` работает иначе, чем memory preflight. Он запускается только при явном `KnowledgeGap` или при route/role policy, где missing fact блокирует решение. Разрешенные MVP-источники: user clarification, local files already in scope, installed package probe, allowlisted official docs fetch, goal/dialog memory, existing reports. Реализованные sources: `inspect_installed_packages` для локальных backend facts и `official_docs_fetch` для official documentation excerpts с source policy и content hash. External L4 lookup допускается позже как отдельная information capability с freshness policy и audit trail.

GitHub evidence source добавляется как optional external acquisition path. `plugins/github_repository_search` использует GitHub Repository Search API и возвращает metadata, не кодовые фрагменты. `runtime/knowledge_source_policy.py` задает source policy: GitHub можно использовать для поиска библиотек, паттернов, edge cases и тестовых идей; official docs имеют более высокий confidence cap, но тоже не подменяют локальные contract tests. Нельзя использовать GitHub для копирования кода, замены официальной документации или автоматического архитектурного решения. `tools/github_knowledge_probe.py` выполняет live probe и пишет `KnowledgeArtifact` в `artifacts/knowledge/`; этот probe не входит в обязательный offline acceptance из-за внешней сети/rate limit.

CLI:

```text
python tools/memory_rebuild.py --root .
python tools/memory_search.py --root . --query "normalize and hash text" --rebuild
python tools/memory_templates.py --root . --rebuild --min-support 2
python tools/memory_instantiate.py --root . --goal "normalize and hash text" --rebuild
```

MVP acceptance runner:

```text
python tools/mvp_acceptance.py --root .
```

По умолчанию runner выполняет portable layer-oriented acceptance scenarios только на версиированных fixtures: plugin contracts, registry doctor, happy path, quarantine/fallback, controlled stop без fallback, durable queue/worker pool, Foundry spec/candidate dry-run, dialogue memory, deterministic memory seeding/templates/instantiation, Level 4 goal execution/deliberation, field-trial report, Project Analyzer benchmark, Knowledge Gap probe и known deterministic L4 routes (`list_files`, project-tree scan/analysis, markdown-to-text file, markdown-to-RTF file, fetch-links, translate-text, parse-pdf, spreadsheet-to-CSV, CSV-to-spreadsheet). GitHub L4 interpretation quality probe добавляется только через `--live-l4`; External-3 и загруженный GitHub-10 corpus - только через `--local-project-trials`. Runner пишет JSON/Markdown reports в `artifacts/acceptance/`.

Knowledge Gap acceptance проверяется через `tools/knowledge_gap_probe.py`: L4 фиксирует unknown fact для legacy `.xls`, L3.5 выбирает локальный information capability, L1 добывает evidence через `inspect_installed_packages`, `KnowledgeArtifact` сохраняется в goal report, L4 честно останавливается по `decision_if_unresolved`.

Clarification loop:

```text
python tools/goal_run.py --root . --goal "help me"
python tools/goal_run.py --root . --goal-id <goal_id> --clarification "Normalize input text from $input.text and hash it" --execute --input-json "{\"text\":\" hello \"}"
```

Если Level 4 возвращает `REQUEST_CAPABILITY_SPEC`, `goal_run.py` создает typed spec request в `generated/specs/<capability_id>.json`, но не генерирует plugin code и не меняет registry.

Level 4 может использовать LLM только для route decision:

```text
python tools/goal_run.py --root . --goal "..." --use-l4-llm
```

Ответ модели валидируется по enum `PLAN_WITH_L35 | ASK_CLARIFICATION | REQUEST_CAPABILITY_SPEC | STOP_UNSUPPORTED`; невалидный ответ понижается до deterministic route decision.

Из старого контура `004` переиспользуются идеи, но не переносится архитектура целиком:

1. `dry_run`: сначала показать решение и candidate plan без регистрации.
2. `admission gate`: блокировать генерацию, если запрос небезопасен, слишком широк или не является reusable capability.
3. `register/probe`: регистрировать только после успешной сборки и первичной проверки.
4. `quality signal`: записывать результат runtime-использования capability.
5. `generator_repair_needed`: отличать плохой plugin от поломанного генератора.

Generated candidate не имеет права напрямую попадать в `plugins/` или `registry/capabilities.json`. Разрешенный путь:

```text
GENERATE_SPEC -> SANDBOX_BUILD -> TEST -> REGISTER -> PROMOTE
```

Только шаг `PROMOTE` переносит candidate в `plugins/<plugin_id>/` и делает capability доступной runtime. В текущем MVP `GENERATE_SPEC` не исполняется автоматически внутри runtime pipeline, но доступен как явный Foundry flow через tools.

### 12. MVP Acceptance Criteria
MVP считается успешным, если выполняются условия:

1. Pipeline успешно проходит happy path.
2. Искусственный `ImportError` в `parse_title` приводит к quarantine.
3. Runtime создает checkpoint и interrupt packet.
4. Policy stub выбирает `SWITCH_PLUGIN`, если доступен `parse_title_fallback`.
5. Pipeline завершается через fallback plugin.
6. При отсутствии fallback runtime контролируемо завершает pipeline через `STOP`.
7. Quarantined plugin больше не выбирается для новых pipeline.
8. Все входы и выходы plugins проходят schema validation.
9. `degraded` plugin остается исполнимым для retry/recovery, но получает registry event и не должен быть предпочтительным при наличии `active` alternative.
10. Registry doctor обнаруживает drift между registry и plugin-каталогами.
11. Минимальный graph planner строит проверяемый Pipeline DSL для известных deterministic goals.
12. Runtime может продолжить pipeline из checkpoint без повторного выполнения completed nodes.
13. Execution journal и quality metrics обновляются при выполнении nodes.
14. Process boundary режим выполняет plugin entrypoint в child process и поддерживает kill-on-timeout.
15. Durable queue сохраняет pipeline jobs на диск, поддерживает claim/complete/fail/cancel и requeue stale running jobs.
16. Worker pool обрабатывает durable queue до idle и сохраняет результаты выполнения в job records.
17. Worker lease/heartbeat не дает потерять `running` jobs после падения worker.
18. Job-level retry переводит failed attempt обратно в `queued` до исчерпания `max_attempts`.
19. Priority ordering выбирает более важные jobs раньше при claim.
20. Runtime control plane показывает queue/registry/quality/failure/journal состояние и позволяет inspect/cancel/requeue jobs.
21. Capability Foundry не продвигает candidate без `spec.json`, `requirements.lock`, pinned dependencies, negative tests и successful dependency probe.
22. Static admission блокирует опасные imports/calls и filesystem operations без заявленных side effects.
23. Runtime smoke suite запускает pytest/compile/check_plugins/registry_doctor/MVP smoke одной командой.
24. Queue cleanup умеет архивировать terminal jobs, а registry selection report объясняет scoring capabilities.
25. Capability library содержит базовые file/text/html/json/project transform plugins, Foundry-promoted text capability `translate_text`, PDF text extraction capability `parse_pdf` с optional `pypdf` backend и deterministic builtin fallback, а также project-analysis pack: `scan_project_tree`, `detect_project_stack`, `read_many_files`, `extract_python_structure`, `extract_runtime_commands` и `project_map_report`. Project-analysis report обязан включать summary/risks и структурированные answers по назначению проекта, entrypoints/execution path, candidate capabilities, contracts/data, errors/state/reproducibility и `6_runtime_extraction_readiness`: data lifecycle, mixed responsibilities, hidden orchestrators, long-lived state, idempotency risks, quarantine candidates, process-boundary candidates, contract-test strategy, resume/reuse plan, source strata и minimal extraction plan. `source_strata` обязан разделять `active_core`, `legacy_noise`, `context_only` и `packaged_copy`; first extraction plan, best-effort dataflows и evidence claims используют active core как первичный источник, а legacy/context сохраняют как evidence. `read_many_files` обязан поддерживать dynamic auto-discovery ключевых файлов. `extract_python_structure` обязан отдавать не только routes/functions/classes, но и central/broad function hints, schema fields, error-handling hints, import graph hints и test surface counters, включая `*_seen` counters для файлов, не попавших в AST лимит.
26. Graph Planner принимает structured goal spec и возвращает Pipeline DSL с selection explanation.
27. Foundry поддерживает generate/validate spec tools, dry-run promotion и sample quality gate.
28. Local LLM planner path принимает JSON proposal от OpenAI-like backend и исполняет его только после deterministic Pipeline DSL validation.
29. Level 4 goal orchestrator возвращает typed route decision и передает исполнение только через L3.5/L2 boundaries.
30. Goal sessions/reports сохраняют trace Level 4 decisions, clarifications, L3.5 plan и execution result.
31. Clarification loop продолжает существующую goal session вместо старта с нуля.
32. REQUEST_CAPABILITY_SPEC создает typed spec request для Foundry без генерации plugin code.
33. L4 LLM decision может выбирать только route enum и имеет deterministic fallback.
34. Memory Index пересобирается из goal reports и умеет находить похожие успешные цели.
35. Memory recommendation может предлагать reuse previous plan, но не обходит Level 4/L3.5/L2 validation.
36. `goal_run.py` сохраняет memory preflight в session/report и передает recommendation в L3.5 только как planning hint.
37. Memory Index строит reusable plan templates из успешных reports и отдает их в L3.5 только как template hint.
38. Template Instantiator может построить candidate proposal из mature template только через `plan_from_spec()` и `validate_pipeline()`, с fallback на L3.5 LLM.
39. Template safety policy блокирует immature templates, templates с failed reports той же формы и templates с не-`active` capabilities.
40. MVP acceptance runner проходит ключевые сценарии по слоям и пишет JSON/Markdown отчет.
41. Deterministic required-capabilities planner закрывает простые известные L4 routes без зависимости от LLM JSON quality.
42. Dialogue Memory поддерживает durable session/topic/decision/open-thread/principle records, recall/summary CLI и может передаваться в `goal_run.py` только как contextual hint.
43. Field-trial report агрегирует последние goal reports, показывает L4 actions/recommendations/selected alternatives, planners, execution status и несовместимые решения.
44. Level 4 сохраняет `level4_deliberation` в goal report: route, capabilities, memory/dialogue summary, risk list, route alternatives, selected alternative и recommendation.
45. Project-analysis LLM path разделен по слоям: L3.5 сохраняет короткий advisory signal packet `level35_project_signals` по compact deterministic fact digest, включая deterministic subsystem/hotspot/boundary/runtime-safety enrichment при сбое локальной модели. L4 сохраняет человекочитаемый advisory artifact `level4_project_interpretation` по expanded bounded deterministic facts и L3.5 signals. После интерпретации deterministic task synthesizer сохраняет `analysis_tasks` как proposed backlog для subsystem boundary, capability extraction, contract hardening, recovery-loop, mixed-responsibility split, idempotency guard, quarantine policy, process boundary, checkpoint/reuse policy и human-decision follow-up. L4 может использовать только отдельную cortex model с большим контекстным окном; она может вызываться через общий local gateway, но локальная LLM Уровня 3.5 для L4 запрещена. Эти артефакты не имеют права менять план, registry или execution artifacts.
45.1. L4 project interpretation имеет отдельный quality scorer: summary должен быть заземлен в фактах, capabilities не должны ссылаться на context-only paths, refactor plan должен содержать actionable шаги, а confidence/open questions должны честно отражать неполноту фактов. GitHub L4 quality probe является model-backed field trial и входит в acceptance только при явном `--live-l4`; portable CI gate не зависит от доступности внешнего L4 provider и вариативности его формулировок.
46. `tools/project_tasks.py` умеет читать `analysis_tasks` из goal reports, фильтровать proposed backlog по project/type/priority/task_id и создавать typed Foundry spec request из выбранной задачи. Создание spec request не генерирует plugin code, не регистрирует capability и не обходит Foundry gates.
47. Межслойные packet-контракты реализованы в `runtime/layer_packets.py`: L4 передает `IntentPacket` в L3.5, L3.5 сохраняет `MotorPlanPacket` для L2 и `SignalPacket` для L4, L2 events/interrupts имеют typed envelope. Packets versioned, correlated через goal/job id, валидируются по route/payload и сохраняются в goal report или durable job result как replay/debug artifacts. `runtime/goal_runtime.py` делает этот маршрут обязательным для `goal_run.py`; sync, async и worker-pool recovery возвращаются в L3.5 через общий bounded adaptation handler.
48. Contract Registry реализован в `runtime/contract_registry.py` и подключен к Pipeline DSL validation. Pipeline не считается валидным, если node ссылается на capability без executable contract, с невалидной schema shape или с недопустимым lifecycle status. Packet routes и role artifact APIs также доступны через contract catalog и валидируются как runtime contracts.
49. Project Analyzer Field Trial v0.1 имеет controlled benchmark corpus в `benchmarks/project_analyzer/projects`, `expected_analysis.json` для каждого проекта и runner `tools/project_analyzer_benchmark.py`. Runner прогоняет deterministic facts -> L3.5 signals -> L4 interpretation -> analysis_tasks, затем считает hits/misses/false positives по entrypoints, capabilities, broad/hidden orchestration, side effects, idempotency, checkpoint candidates и minimal extraction plan.
50. Transformation Architect v0.1 не переписывает исходный проект автоматически. Он выбирает безопасную candidate capability из `minimal_extraction_plan`, формирует dry-run extraction proposal и, при явном флаге, Foundry spec request. CLI: `tools/project_extraction_proposal.py --project-dir <path> --write --write-spec`. Proposal обязан включать source evidence, safety mode, proposed spec, next steps и не менять runtime registry/source project. Перед sandbox build применяется dependency extraction policy: если ranked candidate зависит от unresolved local/domain calls, он попадает в `skipped_candidates` с `dependency_policy_blocked`, а система пробует следующий ranked candidate; весь proposal блокируется только когда не остается безопасных кандидатов.
51. Transformation Engineer v0.1 превращает одобренный extraction proposal в sandbox candidate через `tools/project_transform.py --project-dir <path> --force`. Flow выполняет `PROPOSE -> SANDBOX_BUILD -> TEST -> PROMOTION_READY`, пишет candidate code/tests/spec/report и выполняет Foundry dry-run promotion. Исходный проект и registry не меняются; реальный promote требует явного флага `--promote`.
52. Role Skills v0.5 разделяют профессиональные когнитивные роли от runtime capabilities. `registry/skills.json` описывает L4 role skills, `runtime/role_skills.py` экспортирует deterministic ArchitectSkill v0.2, SpecWriterSkill v0.1, ImplementerSkill v0.1, TesterSkill v0.1 и ReviewerSkill v0.1. CLI `tools/role_skill_run.py` строит отдельные шаги цепочки `ProjectMapReport -> ArchitectureDecisionRecord -> TechnicalSpec -> ImplementationPlan -> TestPlan -> ReviewFindings`. Role skill не имеет права писать код, менять Capability Registry, исполнять pipeline или promote candidates. MVP acceptance проверяет deterministic role-skill path без обязательного LLM-вызова; LLM может быть добавлен позже как advisory backend роли, но typed artifact contract остается обязательным. ImplementerSkill в этой цепочке означает только Implementer Planner. Роль `programmer_executor` представлена `runtime/programmer_executor.py` и `tools/apply_implementation_plan.py`: она берет `ImplementationPlan`, создает isolated `PatchPackage`, сохраняет `source_snapshot`, запускает allowlisted verification commands, пишет `TestResult` и может быть включена в role pipeline через `--run-executor`, после чего Reviewer получает `test_result`. Общий executor не применяет изменения к source: `--apply-source` возвращает controlled block. Отдельный узкий контур `tools/sandbox_patch_review.py --apply-approved` может применить только прошедший проверку специализированный sandbox package после явного одобрения, проверки source identity/invariants и создания timestamped backup; это не универсальный Programmer Executor и не разрешение на автономное редактирование произвольного проекта.

52.0.1. Programmer Field Trial представлен `runtime/programmer_field_trial.py` и `tools/programmer_field_trial.py`. Он прогоняет реальные проекты через `Role Pipeline + Programmer Executor` и оценивает именно программиста: `planning_score`, `execution_score`, `coding_score`, `safety_score`, `maturity_score`. Verdicts: `planner_only`, `executor_only`, `programmer_active`. На текущем MVP роль программиста ожидаемо классифицируется как `executor_only`: она умеет принимать bound ImplementationPlan, создавать PatchPackage/source snapshot и запускать verification, но не создает patch operations и не применяет source edits. Field trial также проверяет `verification_project_scoped`; passing root-level smoke вроде `mvp_acceptance` не считается доказательством, что проверен целевой проект.

52.0.2. Programmer Prompt Curriculum представлен `runtime/programmer_prompt_curriculum.py`, `tools/programmer_prompt_curriculum.py`, стартовым corpus `curricula/programmer_prompt_local_3/*/teacher_reference.json` и расширенным corpus `curricula/programmer_prompt_local_10/*/teacher_reference.json`. Он фиксирует внешний teacher/corrector trace для пользовательских промптов вида "напиши скрапер ixbt в CSV", "напиши Markdown->RTF CLI", "напиши XLS/XLSX<->CSV converter", а также задач JSONL filter, text stats, duplicate finder, batch renamer, JSON config merger, URL status checker без live network и static site indexer. Это не самообучение и не ground truth: `teacher_reference_not_ground_truth` означает проверяемый ориентир, а не автоматическое право править код. Curriculum оценивает prompt intake, greenfield scaffold, генерацию файлов, fixture-based tests, project-scoped verification, code generation, dependency policy и trace capture. Live web scraping и URL checks не являются обязательными для default tests: сетевые сценарии должны иметь fixture/injectable tests и optional live smoke. При `write=False` ожидаемый verdict остается `prompt_intake_only`; при `write=True` Local-3 и Local-10 получают `programmer_ready` только если закрыты capabilities, artifacts, acceptance и project-scoped verification. Фразовый `missing_steps` остается diagnostic trace и не блокирует readiness, когда проверяемые gates уже покрыты. MVP acceptance включает `programmer_prompt_curriculum_local_10` как L4 gate.

52.0.3. Greenfield Scaffold + Code Generation v0.1 представлен `runtime/greenfield_scaffold.py`, базовым `runtime/greenfield_templates.py`, расширенным `runtime/greenfield_local10_templates.py` и Stage 2 шаблонами `runtime/greenfield_stage2_templates.py`; он включается в Programmer Prompt Curriculum при `write=True`. Scaffold отвечает за sandbox root, path safety, запись файлов и verification; templates отвечают за содержимое generated modules/tests. Для стартовых трех curriculum cases генератор пишет минимальную deterministic реализацию: ixbt fixture parser + CSV writer, Markdown->RTF converter + CLI, XLSX<->CSV adapter на стандартной библиотеке (`zipfile` + XML) с явной legacy `.xls` policy `unsupported_without_adapter`. Для Local-10 он генерирует небольшие CLI/package проекты с чистыми core transforms, fixtures, CLI entrypoint и project-scoped tests. Для Stage 2 он также умеет генерировать FastAPI CSV aggregator package с `app.py`, core aggregator, API tests, fixture CSV и README/run command. После записи запускаются project-scoped `python -m compileall -b .` и `python -m pytest tests -q`; `code_file_generation`, `dependency_policy` и `project_scoped_tests` считаются покрытыми только если verification прошла. Все пути артефактов валидируются и не могут выйти за пределы scaffold root; source tree и registry не меняются.

52.0.4. Programmer Project Review v0.1 представлен `runtime/programmer_project_review.py` и `tools/programmer_project_review.py`. Это первый явный handoff `programmer -> tester` для реально сгенерированного sandbox-проекта: programmer создает `GreenfieldScaffold` с файлами проекта, tester читает manifest, verification output, acceptance coverage и структуру файлов, после чего возвращает `TesterProjectReview` с `recommendation`, `checks`, `coverage`, `findings` и `risk_assessment`. Этот контур не заменяет независимое ручное QA и не объявляет teacher reference ground truth; он проверяет, что сгенерированный код существует как проект, имеет package/CLI/tests/fixtures, проходит project-scoped compile + pytest, покрывает заявленные acceptance criteria и не меняет source tree или registry. Начиная с v0.1.1 tester также инспектирует содержимое файлов: наличие core/CLI tests, negative или edge-case evidence, `argparse` CLI с input/output аргументами и согласованность README с пользовательским prompt. MVP acceptance включает `programmer_project_review` как L4 gate на кейсе `json_log_filter_cli` и требует эти quality checks, а не только успешный pytest.

52.0.5. Stage 2: Verified System Package является следующим целевым рубежом поверх MVP, а не заменой текущего runtime. Он представлен `runtime/prompt_adequacy.py`, `tools/prompt_adequacy.py`, `runtime/verified_system_package.py` и `tools/verified_system_package.py`. Входом является bounded adequate prompt; первым шагом всегда выполняется `PromptAdequacyGate`, который классифицирует prompt как `ready`, `needs_clarification`, `unsupported` или `too_broad` по проверяемым полям: понятная цель, определенный тип системы, входы/выходы, ограничения, dependency policy, проверяемые success criteria и bounded scope. `PromptAdequacyGate` не является текстовым отчетом: это API-вход для `L4.0 CognitiveControlPlaneDecision` в режиме `prompt_to_product`. Stage 2 может продолжить сборку только если `prompt_product_gate.status=passed` и `role_transition.next_action=build_verified_system_package`; иначе возвращается clarification/blocker или controlled stop вместо генерации. Если prompt `ready`, но нет поддержанного package template, L4.0 фиксирует `no_supported_package_template` как bounded semantic escalation candidate для L4.5, а не разрешение обходить contracts. Если gate `ready` и template поддержан, Stage 2 строит isolated working package: source files, tests, README/run instructions, verification report, known limitations, tester review и release decision. Поддержанные классы в текущем MVP: `CLI / file-processing utility` для JSONL log filter, text stats CLI и CSV sort CLI без внешних зависимостей, а также `FastAPI / small local service` для CSV aggregation service и in-memory key/value CRUD service с dependency policy `fastapi`. FastAPI packages обязаны иметь health/domain endpoints, JSON responses, controlled HTTP errors и project-scoped API/core tests. Stage 2 corpus живет в `curricula/programmer_prompt_stage2/*/teacher_reference.json`; acceptance включает `verified_system_package_cli`, `verified_system_package_fastapi`, `verified_system_package_text_stats`, `verified_system_package_fastapi_kv`, `stage2_template_admission_csv_sort` и `verified_system_package_csv_sort`. Если tester запрашивает rework, запускается только bounded contract debug loop `runtime/stage2_debug_loop.py`: `FailureAnalysis -> ReworkPlan -> sandbox repair -> verification -> tester review`. Loop применяет только allowlisted deterministic repairs внутри isolated generated package: восстановление README prompt/run-command alignment, dependency policy в `pyproject.toml` для FastAPI package, CLI entrypoint contract (`argparse`, positional `input/output`, вызов `run_cli`), negative/edge test evidence (`empty` для text stats, malformed `not-json` для JSONL filter) и controlled HTTP error (`400` для CSV validation, `404` для key/value missing item); неизвестные сбои остаются `blocked`. `tools/stage2_debug_loop_probe.py` намеренно повреждает generated package, проверяет, что tester фиксирует failure, затем требует successful bounded repair и повторную project-scoped verification; MVP acceptance включает FastAPI, CLI и edge-case probes как отдельные L4 programmer gates. Direct modification of the user's source project remains forbidden until explicit human approval: `VerifiedSystemPackage.invariants.direct_user_source_modification=false`, `human_approval_required_for_source_apply=true`.

52.0.5.1. Project Change Trial v0.1 обобщает контур "внешний учитель/корректор -> изолированная фикстура -> sandbox patch -> review/apply в фикстуру -> tester verdict" без превращения его в самообучение. Общий каркас живет в `runtime/project_change_trial.py`: он создает fixture из baseline-файлов, переносит optional context files, сравнивает результат с teacher reference по exact diff и feature evidence, пишет отчет и фиксирует invariants `source_project_modified=false`, `fixture_only_apply=true`, `teacher_reference_is_ground_truth=false`, `automatic_code_changes_from_own_output=false`. Конкретные сценарии, например `tools/map_llm_migration_trial.py`, подключают собственный analyzer/patch generator/tester поверх этого каркаса. Teacher reference остается проверяемым ориентиром, а не ground truth: исправление runtime/codebase выполняется отдельным инженерным изменением, а не автоматическим самопатчем по собственному выводу системы.

52.0.5.2. Project Change Scenario Interface v0.1 описывает такие trials декларативным JSON-сценарием и исполняется через `runtime/project_change_scenario.py` / `tools/project_change_trial_run.py`. Поддержанные apply-типы: `copy_teacher_to_fixture` и `sandbox_patch_package`. Для `sandbox_patch_package` builder обязан быть active-записью в `registry/project_change_builders.json`; scenario не может импортировать произвольный модуль или вызвать произвольную shell-команду. Текущий allowlisted builder `gigachat_sandbox_patch` строит sandbox package для fixture, затем проводит `sandbox_patch_review` и применяет результат только в fixture. Source-project immutability проверяется snapshot/hash до и после apply.

52.0.6. Stage 3: Verified Product Slice является первым post-MVP контуром и представлен `runtime/product_slice.py` и `tools/product_slice.py`. Он не расширяет права LLM и не включает прямое редактирование пользовательского проекта. Входом остается bounded adequate prompt; `PromptAdequacyGate` обязателен. Если Stage 2 package не достиг `release_ready`, `ProductSliceSpec` блокируется. Если package готов, Stage 3 формирует продуктовый контракт: `ProductSliceSpec`, `RequirementSet`, `ArchitectureDecisionRecord`, список user scenarios, input/output lifecycle, implementation task graph с зависимостями, documentation review, scenario verification, bounded product debug-loop plan, verification summary и `slice_ready` release decision. Stage 2 остается execution engine: он создает isolated source/tests/docs package, а Stage 3 поднимает результат на уровень проверяемого product slice. Если базовый `GoalSpec` не смог явно выделить входы/выходы для поддержанного класса, Stage 3 может дообогатить `inputs_outputs` из prompt/system type, например `HTTP JSON item payload`, `path key` и `controlled HTTP 404 response` для FastAPI key/value CRUD. Инварианты Stage 3: `stage2_package_is_execution_engine=true`, `prompt_adequacy_gate_required=true`, `sandbox_only=true`, `direct_user_source_modification=false`, `arbitrary_product_generation=false`, `scenario_rework_is_bounded=true`. Acceptance gate `product_slice_spec` проверяет, что для FastAPI key/value prompt строится Stage 3 artifact с satisfied requirements, complete task graph, ok documentation review, covered scenarios, `not_needed` product debug loop, release decision и ссылкой на written report в `artifacts/product_slices`.

52.0.7. Stage 3 Product Debug Loop исполняется через `runtime/product_debug_loop.py` и проверяется `tools/product_debug_loop_probe.py` / `tools/product_scenario_probe.py`. Loop принимает `VerifiedSystemPackage`, reference contract и выполняет только bounded package-local rework: `ProductFailureAnalysis -> ProductReworkPlan -> package repair -> project-scoped verification -> tester review -> refreshed package`. Поддержанные repairable blockers v0.1: `documentation_review`, `scenario_verification`, `api_contract_drift`, `cli_ux_drift`, `readme_api_mismatch`. Поддержанный non-repairable boundary blocker v0.1: `core_behavior_drift`, когда CLI interface contract выглядит корректно, но project-scoped verification падает из-за доменной логики/output semantics. Поддержанные repair actions v0.1: `rewrite_readme_from_verified_package`, `add_missing_scenario_test_inside_generated_package`, `repair_api_contract_drift`, `repair_cli_ux_drift`, `repair_readme_api_mismatch`, `rerun_project_scoped_verification`. Loop запрещает `edit_user_source_tree`, `edit_registry` и `promote_candidate`; инварианты результата: `sandbox_only=true`, `source_tree_changes=false`, `registry_changes=false`, `bounded_rework=true`. Acceptance gates намеренно повреждают FastAPI API contract (`/items/{key}` -> `/broken/{key}`), CLI entrypoint (`argparse`/input-output contract), README/API alignment и CLI core behavior; первые три требуют successful bounded repair, а core behavior drift должен завершиться controlled `needs_rework` с blocked rework plan.

52.0.8. Stage 3 Product Slice Benchmark исполняется через `tools/product_slice_benchmark.py` и проверяет текущий ограниченный corpus из восьми product prompts: FastAPI key/value CRUD, FastAPI CSV aggregator, CLI text stats, JSONL log filter, duplicate file finder, batch renamer, JSON config merger и static site indexer. Для каждого case требуется `status=ok`, `release_decision=slice_ready`, `requirements=satisfied`, `task_graph=complete`, `documentation_review=ok`, `scenario_verification=covered` и `product_debug_loop=not_needed`. Acceptance gate `product_slice_benchmark` требует `case_count=8`, `ok=8`, `failed=0`. Сетевые и spreadsheet-heavy prompts (`ixbt_news_scraper`, `url_status_checker_cli`, `xlsx_csv_converter`) остаются отдельными risk/adapter probes до явной политики live network, optional smoke и внешних spreadsheet-зависимостей.

52.1. Project Rebuild Trial v0.1 является отдельным development loop для выращивания роли программиста и связанных инструментов. CLI `tools/project_rebuild_trial.py --source-dir <project>` запускает analyzer, строит `ProjectRebuildSpec`, генерирует `<project>_x` scaffold в `artifacts/rebuild_projects/`, затем пишет comparison report в `artifacts/rebuild_trials/`. Генератор выбирает MVP-режим по evidence: `map_flask` для map-like web apps, `api_fastapi` для проектов с HTTP routes и `tooling_cli` для tooling/library projects без routes. Behavioral comparison при этом является общим probe contract, а не отдельным сравнителем под каждую технологию: `runtime/project_rebuild_behavior.py` строит safe probe plan из routes/capabilities, выполняет read-only HTTP probes через adapters, нормализует ответы к response shape (`status_code`, `json_kind`, `json_keys`, `field_types`, bounded `sample`) и сравнивает source/target по этой форме. Перед генерацией scaffold safe source probes могут сохранить `behavior_blueprints` в `ProjectRebuildSpec`; generated endpoints используют эти blueprints как контракт формы ответа. Для tooling/library projects без HTTP routes применяется capability-manifest probe. Generated data artifacts строятся из тонких read-only срезов source JSON, а не только из синтетических fixtures. Static UI smoke применяется только к generated apps с UI surface. Этот loop не меняет source project и не объявляет teacher/reference ground truth.

52.1.1. GitHub Rebuild Corpus runner `tools/github_rebuild_corpus.py` клонирует внешний набор GitHub projects в `artifacts/github_rebuild_corpus/repos`, запускает Project Rebuild Trial для каждого проекта и пишет агрегированный JSON/Markdown отчет. Отчет обязан разделять общий trial `status/score` и corpus quality: `analysis_score`, `spec_score`, `scaffold_score`, `behavior_score`, `confidence` и `corpus_verdict`. Возможные verdicts: `behavior_checked` только когда source behavior реально исполнялся и confidence высокий; `shape_checked` когда reconstruction/spec/scaffold выглядят согласованно, но поведение не доказано; `needs_review` когда даже shape-level confidence низкий. Отчет также фиксирует глубину проверки: HTTP probes, manifest probes, source executed, source unavailable и количество behavior blueprints. Если проект имеет HTTP probes, но source не удалось исполнить в локальном окружении, rebuild получает missing check `behavior_source_executable`; это предотвращает ложное `ok` для generated scaffold, который не сравнен с реальным source behavior. GitHub corpus используется прежде всего как analysis/spec/rebuild-shape benchmark; source execution является дополнительным доказательством, а не обязательным способом оценки каждого внешнего проекта.

52.1.2. Probe environment readiness представлен `runtime/project_probe_env.py`. Он анализирует failures behavioral probes, извлекает missing modules из controlled import errors, сверяет их с `requirements*.txt`, строит `install_candidates` и маркирует `probe_env.status` как `ready` или `blocked`. MVP policy запрещает автоматическую установку зависимостей внешнего проекта по умолчанию: readiness объясняет блокер и риск (`low` для простых declared packages, `high` для heavy/external data/network packages). Явный флаг `--prepare-probe-env` включает controlled venv setup в `artifacts/probe_envs/<project>` и устанавливает только declared low-risk allowlist packages. После успешной подготовки trial выполняет second pass через venv interpreter (`runtime/project_probe_runner.py`) и заново снимает behavior blueprints/comparison. High-risk packages остаются blocked и не устанавливаются автоматически.
53. Role Pipeline Orchestrator v0.1 представлен `runtime/role_pipeline.py` и `tools/role_pipeline_run.py`. Он запускает deterministic role chain end-to-end, пишет role artifacts и общий отчет `artifacts/roles/pipelines/role_pipeline_<timestamp>.json`, возвращает `recommendation` и `next_action`. При `write=True` дополнительно создается человекочитаемый архитектурный документ `human_documents.architecture_analysis` через `runtime/architecture_analysis_document.py`; он суммирует назначение проекта, границы, выбранное архитектурное решение, capability candidates, extraction contract, риски, открытые вопросы, evidence/traceability и следующий шаг. Документ предназначен для чтения человеком и не заменяет typed JSON contracts. По умолчанию orchestrator является dry-run coordination layer: он не меняет исходный проект, не меняет registry, не вызывает Foundry и не обращается к LLM. Явный флаг `--run-transform` разрешает после review запустить `Project Transform / Foundry` до состояния `promotion_ready`; реальный promote в registry по-прежнему не выполняется.
54. Role Pipeline Field Trial v0.1 представлен `runtime/role_pipeline_benchmark.py` и `tools/role_pipeline_benchmark.py`. Он прогоняет deterministic role pipeline по benchmark corpus, считает `artifact_score`, `safety_score`, валидность `next_action` и отсутствие запрещенных действий по умолчанию. Acceptance требует `artifact_score >= 0.95`, `safety_score == 1.0` и минимум 8 проектов.
54.1. Role Pipeline Field Trial дополнительно считает `implementation_score`. `ImplementationPlan` должен быть явно привязан к `TechnicalSpec.extraction_contract`: `implementation_target.candidate` совпадает с выбранным extraction candidate, `contract_binding` переносит input/output contract, а benchmark corpus проверяет совпадение target с `expected_best_extraction_candidate`. Acceptance требует `implementation_score == 1.0`.
54.2. Role Pipeline Field Trial также считает `qa_score`. `TestPlan` должен иметь `test_target`, `contract_test_matrix`, negative tests и acceptance tests, покрывающие `ImplementationPlan.implementation_target`. `ReviewFindings` должен иметь `review_target`, `coverage_assessment`, не фиксировать contract violations и подтверждать покрытие target. Acceptance требует `qa_score == 1.0`.
55. ArchitectSkill LLM Advisory v0.1 подключается только явным флагом (`--use-architect-llm`) и не заменяет deterministic ADR. Модель может выбрать один из уже существующих architecture options и добавить bounded risk notes; forbidden actions, registry mutation, pipeline execution и promote остаются запрещены. При ошибке backend роль возвращается к deterministic fallback. Field trial scoring считает LLM-вызов нарушением только если он произошел без явного advisory режима.
56. Role Foundation Pipeline v0.1 является ближайшим quality gate для верхнего контура: `ProjectMapReport -> ArchitectureDecisionRecord -> TechnicalSpec`. Он представлен `runtime/role_foundation_pipeline.py` и `tools/role_foundation_run.py`, прогоняется минимум на одном benchmark-проекте и не запускает Implementer/Tester/Reviewer, Foundry, source edits или registry changes. Этот gate считается стабильным, если все три артефакта записаны, ADR содержит chosen option, traceability и source context, а TechnicalSpec содержит requirements, source-linked acceptance criteria, traceability table, `source_evidence` и `extraction_contract`. При `write=True` gate обязан также писать `human_documents.architecture_analysis` - Markdown-документ для человека с executive summary, purpose/boundaries, entrypoints, capability candidates, recommended extraction contract, risks, open questions, evidence/traceability, non-goals и next step. `extraction_contract` обязан выбирать ranked best-first candidate, а не первый валидный symbol: контракт содержит `ranked_candidates`, `candidate_score` и `selection_reason`, а выбранный `candidate` должен совпадать с первой строкой ранжирования. Для benchmark corpus `expected_analysis.json` задает `expected_best_extraction_candidate`; foundation field trial считает `candidate_match_score` и падает, если выбранный candidate не совпал с эталоном. ImplementerSkill подключается к основному пути только после стабилизации этого перехода.
57. Architect Curriculum Local-3 v0.1 является малым контуром teacher-reference проверки только для `Project Analyzer + ArchitectSkill`. Он представлен `curricula/architect_local_3`, `runtime/architect_curriculum.py` и `tools/architect_curriculum.py`; GitHub, Implementer/Tester/Reviewer, Foundry и source edits в этом контуре не участвуют. Каждый `teacher_reference.json` обязан разделять `facts` и `judgments` и иметь `reference_quality=teacher_reference_not_ground_truth`; runner отвергает reference, который пытается объявить себя ground truth. Runner строит fresh `ProjectMapReport`, затем deterministic `ArchitectureDecisionRecord`, считает fact recall/precision и judgment score по entrypoints, capabilities, pure transforms, hidden orchestrators, side effects, idempotency risks, minimal extraction plan, chosen option, risk sources, subsystem boundaries и non-goals. Отчет пишется в `artifacts/curricula/architect_curriculum_<timestamp>.json`, содержит improvement backlog и invariants: `teacher_reference_is_ground_truth=false`, `facts_and_judgments_scored_separately=true`, `automatic_code_changes_from_own_output=false`. При прогоне на внешних локальных проектах действует то же core-first правило: tests/tools/scratch/packaged copies могут быть учтены как контекст, но не должны становиться первыми extraction candidates. Этот механизм является external teacher/corrector loop, а не self-learning loop: reference создается или корректируется человеком/внешним учителем, код меняется отдельным инженерным действием, а не автоматически по собственному выводу системы.

57.1. Порядок развития curriculum фиксирован: сначала `Architect Curriculum Local-3`, затем стабилизация `Project Analyzer + ArchitectSkill`, затем `Architect Curriculum External-3` на `map / 5 / 004`, затем `SpecWriter curriculum`, и только после этого `Implementer / Tester / Reviewer`. Запрещено добавлять следующий role curriculum как основной трек, пока предыдущий gate имеет scoring backlog или не покрывает teacher/corrector invariants.

57.2. SpecWriter Curriculum Local-3 v0.1 является следующим gate после стабилизации Architect. Он представлен `curricula/spec_writer_local_3`, `runtime/spec_writer_curriculum.py` и `tools/spec_writer_curriculum.py`. Вход строится через уже стабилизированный `Project Analyzer + ArchitectSkill`, но scorer оценивает только `TechnicalSpec`: выбранный `extraction_contract.candidate`, ranked-first инвариант, source evidence, acceptance sources, non-goals, отсутствие forbidden actions и ограничение scope до handoff на Implementer. Reference обязан иметь `reference_quality=teacher_reference_not_ground_truth` и `expected_spec`; runner не запускает Implementer/Tester/Reviewer, Foundry, source edits, registry changes или LLM.

57.3. SpecWriter Curriculum External-3 v0.1 переносит тот же gate на реальные локальные проекты `F:/ubuntu/test/map`, `F:/ubuntu/test/5` и `F:/ubuntu/test/004`; corpus живет в `curricula/spec_writer_external_local_3` и запускается через `tools/spec_writer_curriculum.py --curriculum-dir curricula/spec_writer_external_local_3 --write`. Он проверяет, что TechnicalSpec выбирает первый extraction contract по source evidence, а не по поверхностной чистоте функции: global/memory-state helpers, request/middleware handlers, route/API boundaries, packaged copies, tests/tools/scratch и legacy analyzer branches не должны становиться первым candidate. Зафиксированные teacher-oriented ожидания: `map -> app.py:parse_bbox`, `5 -> app/core/cache.py:build_key`, `004 -> p004_family_registry.py:is_codegen_supported_family`. External-3 не является portable обязательным fixture, потому зависит от локальных путей разработчика; тест может быть пропущен, если проекты отсутствуют.

57.4. Implementer Curriculum Local-3 v0.1 является следующим gate, но не включает реальную реализацию. Он представлен `curricula/implementer_local_3`, `runtime/implementer_curriculum.py` и `tools/implementer_curriculum.py`. Runner строит fresh `ProjectMapReport -> ArchitectureDecisionRecord -> TechnicalSpec -> ImplementationPlan`, после чего scorer оценивает только `ImplementationPlan`: candidate совпадает с `TechnicalSpec.extraction_contract`, `contract_binding` содержит input/output contract, patch scope и expected files покрывают bounded work package, rollback plan покрывает expected files, verification commands и acceptance mapping присутствуют, registry policy запрещает неявные registry edits, forbidden actions пусты, handoff идет к Tester. Foundry, promote, source edits, registry changes, Tester и Reviewer не входят в scope gate.

57.5. Implementer Curriculum External-3 v0.1 использует те же проверки для реальных локальных проектов `F:/ubuntu/test/map`, `F:/ubuntu/test/5` и `F:/ubuntu/test/004`; corpus живет в `curricula/implementer_external_local_3` и запускается через `tools/implementer_curriculum.py --curriculum-dir curricula/implementer_external_local_3 --write`. Зафиксированные teacher-oriented ожидания: `map -> app.py:parse_bbox`, `5 -> app/core/cache.py:build_key`, `004 -> p004_family_registry.py:is_codegen_supported_family`. External gate проверяет, что ImplementationPlan удерживает target из TechnicalSpec, переносит контракты, ограничивает expected files/rollback, не делает source edits, не меняет registry, не вызывает live provider/local LLM и не запускает Foundry/promote. Как и остальные External-3 corpus, он зависит от локальных путей и может быть пропущен в portable test environment.
58. Architect Curriculum External-3 v0.1 является вторым, более тяжелым teacher-reference corpus поверх реальных локальных проектов `F:/ubuntu/test/map`, `F:/ubuntu/test/5` и `F:/ubuntu/test/004`. Он живет в `curricula/architect_external_local_3` и использует тот же runner `tools/architect_curriculum.py --curriculum-dir curricula/architect_external_local_3 --write`. Назначение corpus - ловить регрессии на живых проектах: packaged-copy entrypoints, тестовые/служебные candidates, legacy noise, hidden orchestration, idempotency risks и качество subsystem boundaries. Corpus зависит от локальных путей разработчика и поэтому не является обязательным portable pytest fixture. Каждый reference может содержать `teacher_review`: project condition, expected architect behavior, known noise, architectural focus и tooling improvement targets. Judgments могут задавать `forbidden_capability_sources` и `required_source_strata`, чтобы scorer проверял не только найденные candidates, но и отсутствие неправильных first targets. Для `004` reference требует active-vs-legacy source strata: старые `project_analyzer*` ветки остаются evidence, но не попадают в first extraction candidates/dataflows. Этот блок не меняет pass/fail score напрямую; он превращает расхождения в инструментальный backlog и показывает, какие классы доработок уже покрыты текущим прогоном.
59. LLM Replacement Policy v0.1: LLM является bounded hypothesis source, а не универсальным executor. Любой LLM-backed участок обязан иметь typed input/output contract, evidence boundary, deterministic validation или hardened fallback, audit fields для raw/hardened результата и bounded failure. Повторяемый успешный LLM-паттерн переводится в код только после benchmark-сравнения с прежним маршрутом по качеству, latency, стоимости, воспроизводимости, объяснимости и bounded failure. Рекомендуемый порядок замены: L3.5 planning/recovery -> Tester executable acceptance -> Reviewer conformance checks -> Implementer planning -> Project Analyzer facts/graphs -> Knowledge Gap acquisition planning -> Memory/template reuse -> SpecWriter scaffolding -> Goal Intake supported classes. Architect и выявление новых требований остаются LLM/human-assisted дольше остальных, потому что требуют смыслового выбора при неполных требованиях. Runtime и field-trial reports должны явно различать `raw_model_output`, `hardened_output`, `model_output_clean`, `quality_warnings`, `hardening_actions` и `requires_human_review`.
59.1. Controlled LLM Fallback v0.1: если deterministic route/schema/conformance path не может построить валидный результат, слой может запросить LLM proposal только при явном разрешении соответствующего режима. Proposal не исполняется напрямую и не подменяет contract gate. L3.5 обязан вернуть proposal в Pipeline DSL validation перед MotorPlanPacket; L4 обязан провести evidence hardening и записать hardening actions; Tester обязан преобразовать результат в executable acceptance obligations; Reviewer обязан прогнать conformance checks и может вернуть `request_rework` или `needs_human_review`. Отказ deterministic-схемы является knowledge gap или proposal request, а не разрешением обходить контракты.
59.2. Tester Executable Acceptance v0.3 представлен `runtime/executable_acceptance.py` и `tools/executable_acceptance_run.py`. Вход: `TestPlan.executable_acceptance`. Выход: `ExecutableAcceptanceResult` с generated pytest scaffold, obligations path, command result, source/registry invariants и limitations. Programmer Executor запускает этот scaffold вместе с verification и вкладывает результат в `TestResult.executable_acceptance_result`; Reviewer conformance gate требует passed result, если он присутствует. Scaffold всегда выполняет obligation/boundary meta-checks: positive contract obligations, malformed input obligations и side-effect boundary obligations. Дополнительно v0.3 поддерживает project-specific invocation для простых `file.py:function` targets внутри project root: импорт функции, вызов по sample kwargs, проверка output shape и negative malformed-input rejection. Classes, methods, async functions, framework handlers, fixtures inference и property-based generation являются следующими harness stages.
59.3. L4.0 Cognitive Control Plane v0.1 представлен `runtime/cognitive_control_plane.py`, `runtime/l4_decision_table.py`, `runtime/semantic_evidence_pack.py` и L4 validation gate `runtime/l4_semantic_validation.py`. Он не является новой профессиональной ролью и не вызывает LLM. Вход для role pipeline: goal, role artifacts, ReviewFindings, optional PromptAdequacyGate и флаг llm_invoked. Выход: `CognitiveControlPlaneDecision` с `artifact_promotion_gate`, deterministic `role_transition`, `semantic_escalation` и `crystallization_backlog`. Role Pipeline обязан использовать `role_transition.next_action` как основной next action и сохранять decision в общем отчете. Для Stage 2 есть отдельный режим `prompt_to_product`: вход `PromptAdequacyGate + supported_template`, выход `prompt_product_gate`, deterministic `role_transition` (`build_verified_system_package`, `ask_clarification` или `stop_unsupported`), `semantic_escalation` и crystallization backlog. `runtime/verified_system_package.py` обязан строить package только по решению L4.0, а не по локальной проверке prompt внутри раннера. L4.0 эскалирует в L4.5 только при semantic uncertainty: unclear/unsupported prompt, no safe candidate, failed advisory backend, semantic rework after contracts passed, promotion block без contract failure или bounded prompt без поддержанного template. Перед вызовом L4.5 L4.0 формирует `SemanticEvidencePack`: prompt facts, failed gates, known templates, forbidden actions и authority=false. Любой `SemanticHypothesisProposal` возвращается в L4.0 как `L4SemanticValidationResult`, где проверяются contract validity, evidence, risks, confidence, return path, forbidden actions и отсутствие runtime mutation claims; validation содержит human-readable explanation. Повторяемые approved transitions попадают в crystallization backlog и отражаются в `L4DecisionTable` как candidates для policy/template/gate/test.
59.4. L4.5 Semantic Reasoner v0.1 представлен контрактами `SemanticHypothesisRequest` и `SemanticHypothesisProposal` в `runtime/semantic_reasoner.py`; отдельный CLI `tools/semantic_reasoner_run.py` прогоняет request JSON через bounded runner, L4 validation и optional replay. Это не executor и не новая автономная роль с правами на действие. L4.5 вызывается только когда `CognitiveControlPlaneDecision.semantic_escalation.l4_5_required=true`; входом является source decision, trigger reasons, evidence context, allowed hypothesis types, forbidden actions, output contract и return path. Допустимые outputs: `SemanticHypothesisProposal` с template mapping, clarification question, unsupported reason, new template candidate, risk interpretation, architecture option, rework target или knowledge gap. Запрещенные действия: execute pipeline, edit user source tree, mutate registry, build package, promote capability, bypass prompt_product_gate или artifact_promotion_gate. Любая L4.5-гипотеза обязана вернуться в L4.0 через `L4SemanticValidationResult`; сама по себе она не запускает Stage 2/Stage 3 и не меняет runtime state. `tools/semantic_reasoner_run.py --use-model` включает реальный OpenAI-compatible L4.5 вызов через `COGNITIVE_OS_L45_BASE_URL`/`COGNITIVE_OS_L45_MODEL` с fallback к deterministic proposal при provider failure; raw model output нормализуется и валидируется тем же contract. Model quality modes фиксируются явно: `deterministic`, `model_propose_only`, `model_with_human_review`, `blocked_model_untrusted`. Если proposal имеет тип `new_template_candidate`, Stage 2 может записать `Stage2TemplateBacklogItem` с `requires_human_review=true` только после `L4SemanticValidationResult.status=accepted` и `accepted_action=record_template_backlog`; автоматическое добавление deterministic template, code generation или registry/template mutation запрещены. `runtime/semantic_replay.py` сохраняет `SemanticProposalReplay`, а `runtime/l45_semantic_benchmark.py` / `tools/l45_semantic_benchmark.py` измеряют deterministic semantic-loop cases и входят в portable acceptance.
59.5. Stage 2 Template Admission v0.1 представлен `runtime/stage2_template_admission.py` и `tools/stage2_template_admission.py`. Он превращает L4.5 backlog candidate в поддержанный deterministic template только через внешний инженерный шаг: reference с `teacher_reference_not_ground_truth`, наличие template code, isolated scaffold, project-scoped compile/pytest, tester review, complete acceptance и invariants без source/registry изменений. Первый прошедший полный цикл: `csv_sort_cli`.

### 13. Что намеренно не входит в первый MVP
Первый MVP не включает:

* поставляемую вместе с MVP локальную LLM 7B-14B;
* автономную LLM-генерацию новых plugins без Foundry gate;
* полноценную semantic dialog memory для долгого многотемного человеческого диалога;
* полноценный docs/web Knowledge Gap Loop шире текущих installed-package, allowlisted official-docs и GitHub metadata probes;
* promotion GitHub evidence из optional probe в устойчивый source-policy managed connector с cache/rate-limit handling;
* production-grade контейнерную sandbox-изоляцию;
* автоматический dependency resolver;
* сложные DAG с параллельным исполнением;
* постоянный фоновый аудит capabilities;
* обучение или fine-tuning моделей.
* автономное самообучение, самопереписывание benchmark/reference под текущий результат или принятие собственных LLM-ответов как ground truth без внешнего teacher/reviewer approval.

Эти элементы добавляются только после того, как базовая interrupt/quarantine/rebuild-петля доказала работоспособность.

### 14. Dialog Memory
Dialog Memory является отдельным слоем над runtime memory. Она хранит не pipelines и не templates, а ход разговора: темы, принятые решения, открытые вопросы, причины решений и устойчивые рабочие принципы.

Предварительный layout:

```text
artifacts/dialogue/
  sessions/<dialogue_id>.json
  topics.json
  decisions.json
  open_threads.json
  principles.json
  summaries.json
  topic_graph.json
```

Минимальные операции слоя:

* `dialogue_note`: зафиксировать важный факт, решение или открытый вопрос.
* `dialogue_recall`: найти связанные темы/решения по текущему запросу.
* `dialogue_switch_topic`: сменить активный topic thread без потери предыдущего.
* `dialogue_summary`: собрать компактный контекст для Level 4.
* `dialogue_compact`: создать производный compact summary для длинной сессии без удаления raw turns.
* `dialogue_topic_graph`: построить производный граф связей между topics и merge suggestions по пересечению токенов.

Dialog Memory может давать Level 4 contextual hints, но не имеет права исполнять plugins, менять registry, строить candidates или обходить Pipeline DSL validation.

MVP CLI:

```text
python tools/dialogue_memory.py --root . create --title "Architecture" --topic "memory"
python tools/dialogue_memory.py --root . note --kind decision --topic "memory" --dialogue-id <dialogue_id> --text "..."
python tools/dialogue_memory.py --root . recall --query "memory context"
python tools/dialogue_memory.py --root . summary --dialogue-id <dialogue_id>
python tools/dialogue_memory.py --root . compact --dialogue-id <dialogue_id> --keep-recent-turns 8
python tools/dialogue_memory.py --root . topic-graph --rebuild
python tools/goal_run.py --root . --dialogue-id <dialogue_id> --goal "..."
```

При передаче `--dialogue-id` `goal_run.py` записывает пользовательскую цель как turn, выполняет `dialogue_recall`/`dialogue_summary` и сохраняет `dialogue_preflight` в goal session/report. Этот контекст не меняет route decision автоматически и не подается в executor как входной state.

Compaction и topic graph являются производными артефактами. Они могут быть пересобраны из raw sessions/records и не являются самостоятельным источником истины. `merge_suggestions` в `topic_graph.json` только предлагает возможное объединение близких тем; автоматического merge/decay в MVP нет.
