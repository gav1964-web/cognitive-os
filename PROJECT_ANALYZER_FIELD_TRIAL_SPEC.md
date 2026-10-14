# Project Analyzer Field Trial v0.1

## Цель

Стабилизировать один вертикальный use case Cognitive OS:

```text
Python project
-> scan_project_tree
-> detect_project_stack
-> read_many_files
-> extract_python_structure
-> extract_runtime_commands
-> project_map_report
-> L3.5 signals
-> L4 interpretation
-> analysis_tasks
-> architecture_synthesis
```

Цель этапа - повторяемый анализ Python-проектов, а не расширение архитектуры вширь.

## Benchmark Corpus

Контролируемые проекты находятся в `benchmarks/project_analyzer/projects/`.

Каждый проект содержит:

* минимальный Python-код;
* заложенные архитектурные признаки: entrypoints, side effects, weak contracts, hidden orchestrators, idempotency risks, fallback/retry/cache;
* `expected_analysis.json` с эталонными ожиданиями.

## Слои Вывода

Project Analyzer обязан разделять:

* deterministic facts: найденные файлы, entrypoints, функции, схемы, side effects, routes, runtime commands;
* L3.5 signals: короткие machine impulses;
* L4 interpretation: человекочитаемая интерпретация;
* analysis_tasks: proposed backlog с evidence и acceptance criteria;
* architecture_synthesis: проектный диагноз, целевая архитектурная форма, top bottlenecks, first slice, deferred scope и verification plan.

Утверждение без evidence считается hypothesis, а не fact.

## Главный Результат

Главный результат анализа - `minimal_extraction_plan`:

```json
{
  "goal": "Build first Cognitive OS pipeline from this project",
  "capabilities_to_extract": [],
  "runtime_needed": [],
  "contracts_to_write": [],
  "side_effects_to_isolate": [],
  "first_pipeline_dsl_candidate": {},
  "blocked_by": []
}
```

Summary и markdown являются вспомогательными слоями.

## Architecture Synthesis

`architecture_synthesis` не должен повторять общий checklist. Он обязан:

* классифицировать форму проекта по evidence: API gateway, web GIS/data app, codegen toolkit, advisory runtime, CLI/tool;
* объяснить главный архитектурный риск через конкретные файлы/functions;
* выбрать один первый slice, который можно проверить контрактными тестами;
* назвать, что пока не трогать, чтобы не расширить scope раньше проверки;
* описать verification plan для выбранного slice.

Синтез строится через knowledge-backed rule engine. Декларативные записи находятся в `knowledge/architecture_patterns/project_archetypes.json` и описывают match-признаки, diagnosis template, target architecture shape, first slice recipe, deferred scope и verification hints. Дополнительные advisory knowledge files: `capability_patterns.json` (типовые capability contracts/tests), `risk_patterns.json` (риски и mitigations) и `project_lessons.json` (уроки внешнего учителя/корректировщика по локальным и GitHub-прогонам). `source_scope_policy` в этой же базе знаний считает docs/examples/tests/extras/docs_src context-only evidence и не должен выбирать такие пути как first-slice targets при наличии core-source альтернатив. Runtime-код только загружает, валидирует, индексирует и применяет эти записи; knowledge base не содержит произвольного исполняемого кода.

Кандидаты на следующие паттерны фиксируются в `knowledge/architecture_patterns/backlog.json` или как staged `KnowledgeCandidate`. Это backlog внешнего учителя/корректировщика, а не самообучение и не ground truth. Активное пополнение KB допускается только после нескольких подтвержденных кейсов, approval внешнего teacher/corrector и approval Codex/developer. `teacher_reference` является проверяемым ориентиром, а не истиной.

Если `architecture_synthesis` остается generic (`python_project`) или low-confidence, project interpreter обязан вернуть `KnowledgeGapPacket` и `ResearchPlan`. Этот plan может включать GitHub repository search, official docs fetch или user clarification, но не выполняет внешний поиск автоматически. Результаты external research сохраняются как `SourceDigest` и могут породить только KB candidate, не активный record.

Этот артефакт остается advisory: он не создает Pipeline DSL, не исполняет tasks и не меняет source/registry.

## Scoring

Runner `tools/project_analyzer_benchmark.py` сравнивает фактический отчет с `expected_analysis.json` по категориям:

* entrypoints;
* capability candidates;
* broad functions;
* hidden orchestrators;
* side effects;
* idempotency risks;
* checkpoint candidates;
* minimal extraction plan.

Отчет пишет hits, misses, false positives и recall по проектам и категориям.

## Команда

```text
python tools/project_analyzer_benchmark.py --root . --write
```

Итоговый отчет сохраняется в `artifacts/field_trials/project_analyzer_field_trial_<timestamp>.json`.

## Первый Transformation Step

После успешного benchmark следующий безопасный шаг:

```text
python tools/project_extraction_proposal.py --root . --project-dir benchmarks/project_analyzer/projects/simple_cli_tool --write --write-spec
```

Команда не меняет исходный проект и не регистрирует capability. Она:

* запускает deterministic Project Analyzer chain;
* выбирает безопасную candidate capability из `minimal_extraction_plan`;
* создает dry-run proposal в `artifacts/extractions/`;
* опционально создает Foundry spec в `generated/specs/`.

Это граница между diagnostic architect и transformation architect: L4 уже не только объясняет, но и формирует проверяемый следующий артефакт для controlled Foundry lifecycle.

Следующий controlled step превращает proposal в проверенный sandbox candidate:

```text
python tools/project_transform.py --root . --project-dir benchmarks/project_analyzer/projects/simple_cli_tool --force
```

Команда выполняет `PROPOSE -> SANDBOX_BUILD -> TEST -> PROMOTION_READY`, создает `generated/candidates/<id>/`, contract/negative tests, transformation report и Foundry dry-run promotion result. Она не меняет анализируемый проект и `registry/capabilities.json`; реальный promote требует явного флага `--promote`.
