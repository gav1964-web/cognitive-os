# Append mapping: второй владелец KB, 15 сентября 2026

Выделен `plugins/append_mapping` версии 0.1.0 с локальными boundary profile и
source contrast. Этот этап переносит знания о границе применимости; исполняющий
извлекатель остаётся в runtime до разделения его общих AST-зависимостей.

## Карта предметной области

| Элемент | Фактическая задача | Решение |
|---|---|---|
| `nested_loop_mapping_boundary` | Характеризация отказа `extract_append_mapping_helper` при вложенном цикле и dict append | Локальная KB `append_mapping` |
| `simple_loop_mapping_validated_o` | Положительный контраст с одним циклом, исходным hash и provenance | Перенесён тому же владельцу |
| `_extract_append_mapping_helper` | Извлечение построения словаря в helper `normalize_record` | Связанный механизм; пока в runtime |
| `guard_mapping_path_descent` | Исправление преждевременного возврата при поиске по пути в mapping | Другая компетенция, не объединена с append extraction |
| `cross_reducer_ambiguity`, unsupported-shape и fallback | Общий выбор дальнейшего исследования при неоднозначности/неподдержанной форме | Сохранены в общем каталоге протокола |

Связь первых трёх элементов подтверждают `applies_to_reducers`, predicate
`reducer_attempts.operation_kind`, source contrast, recipe и вызовы recovery.
Одного слова mapping в названии было недостаточно для объединения с path descent.

## Контракт и поведение

Плагин отдаёт `boundary_profiles`, `source_contrasts` и сохраняющий данные
`decorate_profile`. Специального active overlay нет. Он подключён вторым provider
через `config/knowledge_providers.json`; ядро и общий интерпретатор не изменены.
Registry проверяет текущую identity кода и KB, lifecycle и схемы. Изменённая KB
или карантин не обходятся приватным вызовом.

Lifecycle плагина `active` разрешает read-only вызов; профиль остаётся `staged`,
contrast — `staged_evidence`, `promotion_ready: false`. Сохранены все поля,
приоритет, требования evidence, hashes, counts и provenance. Регистрация не
повышает качество знания и не разрешает применение патча.

В shared profiles остаются три общих записи и исходная promotion policy.
Shared contrasts теперь содержит пустой список: default composite loader
получает контрасты от владельцев. Оба составных каталога совпадают с прежними
полностью, включая порядок записей. Explicit-path loader по-прежнему проверяет
только переданный файл и не является способом получить composite catalog.
Рабочих прямых читателей прежнего файла contrasts, обходящих loader, не найдено.

Потребители — boundary interpreter, field trial, feedback/replan и config doctor
— используют существующий provider-протокол. Исследовательские проверки,
semantic/differential replay и sandbox/source-application условия сохранены.
Копия записи в shared KB удалена: редактируемый владелец один.

## Проверка и границы результата

До переноса сохранены исходники/hashes:
`artifacts/verification/append_mapping_before_20260915.json`.
`tests/fixtures/append_mapping_boundary_legacy.json` содержит hashes исходных
составных каталогов/записей и результаты шести маршрутов. Это development
регрессия, не новая независимая оценка.

- Фокус: `artifacts/verification/append_mapping_focused_20260915.xml` — 37 passed.
- Финальный snapshot/regression/400-line gate:
  `artifacts/verification/development_stage_append_mapping_20260915.json`.
- Архитектура: `artifacts/verification/append_mapping_architecture_20260915.json`.
- Пакеты: `artifacts/verification/append_mapping_packages_20260915.log`.
- Hash/record preservation: `artifacts/verification/append_mapping_preservation_20260915.json`.
- Актуальность снимка и local-corpus checks:
  `artifacts/verification/append_mapping_final_audit_20260915.json`.

Проверены составные каталоги, nested/simple/unsupported/ambiguous/fallback routes,
неприменимость nested-boundary к path-descent reducer, сохранение staged-состояния
и отказ при изменённой identity. Ядро, patch algorithms и recipe config сохранены
побайтно. Второй владелец подключён без изменения общего кода; LLM-вызовов нет.

## Следующий шаг

Граф `artifacts/verification/append_mapping_dependencies_20260915.json` показывает:
извлекатель использует `_enclosing_loop`, `_returns_name`, `_parent_map` и
`_find_top_level_function`. Первые две функции нужны только ему. Parent map
использует также JSON-dumps reducer, поиск функции — все четыре extractors.
Совместимый parser уже принадлежит пакету Inspect.

Перед переносом алгоритма определить общий API двух нейтральных AST-утилит,
сохранить parser semantics и не копировать общие реализации внутрь плагина.
Затем оформить contract исходник/символы/лимит → предложение или отказ и
перевести recovery/development consumers с прежними sandbox/differential gates.
Recipe ещё хранится в общей policy; её владение и cross-reducer selection следует
разделить явно. Перенос path-descent механизма относится к отдельной задаче.
