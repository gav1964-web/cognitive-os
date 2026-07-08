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
* L4 interpretation: человекочитаемая интерпретация и proposed tasks.

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
