# Text splitting и граница автономности, 16 сентября 2026

## Ответ о самостоятельной разработке

Способность COS самостоятельно создать систему собственного масштаба и затем
длительно развивать её пока не подтверждена. Есть ролевой pipeline, ограниченные
генераторы/исправления, sandbox/native проверки, review и очередь задач.
Эти компоненты ещё не доказывают полный цикл разработки неизвестного механизма.

Текущую структурную миграцию проектирует и реализует внешний coding assistant.
COS предоставляет инструменты и проверяет внесённые изменения; regression receipt
не является свидетельством самостоятельного проектирования системой.
В [текущем evidence index](../../DEVELOPMENT_STATUS.md) последняя серия свежих
ремонтов содержит 0/4 принятых результатов; последующий Toml-sort кандидат
сохранил дефект и добавил 6 регрессий. Успехи отдельных других сценариев
сохраняются в их receipts, но не обобщаются до разработки такой платформы.

Проверяемый следующий критерий автономности: на изолированной копии добавить
новую, заранее не реализованную компетенцию от задачи до конечного review,
с внешними acceptance/preservation tests, учётом затрат и всех вмешательств
ассистента. Отдельно оценивать анализ, дизайн, реализацию и восстановление после
неудач. Это предложение эксперимента, не выполненный прогон и не новый бюджет
модельных вызовов. Оценки ролей текущим разделением не повышаются.

## 1. Владение и исходные результаты

Text splitting владеет извлечением единственного вызова `.splitlines()` без
аргументов. Распознавание синтаксическое: не доказывает тип receiver или I/O.
Recipe остаётся bounded; keyword/positional variants и неоднозначность сохраняют
прежние отказы. Boundary profile/source-contrast для этого механизма отдельно
не существовали; новая KB содержит фактически перенесённый recipe.

12 frozen случаев дают 5 proposals и 7 refusals: inline, CRLF/no-final-newline,
аргументы, kwargs, несколько вызовов, existing helper, invalid source,
missing origin, async, другой split и Unicode literal. Это regression fixture.

## 2. Плагин

`plugins/text_splitting` 0.1.0 владеет прежними recipe, extractor AST,
metadata `text_expression`/`split_line` и причиной неприменимости.
Контракты: `patch_recipes`, `propose_patch`, `propose_helper` с существующим
`helper_proposal.v1`. Используется прежний Inspect parser/AST API.
Плагин не импортирует runtime, не исполняет входной source и не применяет патч.
15 прямых проверок прошли до подключения рабочих вызовов.

## 3. Подключение

Registered client обслуживает recovery и legacy alias. Общая конфигурация больше
не содержит копии recipe; весь составной каталог сохраняет прежние значения.
Raw-document test учитывает четыре переданных recipe. В общем helper module
остались только compatibility imports, а dispatcher вызывает четырёх владельцев:
append_mapping, json_serialization, json_parsing, text_splitting.

Это завершает перенос четырёх текущих helper extractors, а не всех механизмов COS.
Planning/research recognition, recipe selection/ambiguity, sandbox/compile/write,
differential verification и source authority остаются в прежних слоях.
Остальные generators, Inspect и generic provider/interpreter не менялись.
Registry получает только новую read-only capability; это не promotion знаний.
Профильная интеграционная проверка: 100 passed.

Доказательства:

- `artifacts/verification/text_splitting_begin_20260916.json`
- `artifacts/verification/text_splitting_before_20260916.json`
- `tests/fixtures/text_splitting_legacy.json`
- `artifacts/verification/text_splitting_step2_20260916.xml`
- `artifacts/verification/text_splitting_focused_20260916.xml`
- `artifacts/verification/text_splitting_preservation_20260916.json`
- `artifacts/verification/text_splitting_architecture_20260916.json`
- `artifacts/verification/text_splitting_packages_20260916.log`
- `artifacts/verification/development_stage_text_splitting_20260916.json`
- `artifacts/verification/text_splitting_final_audit_20260916.json`

После трёх шагов остановка. Далее — измерить повторные чтения recipe catalog в
одном recovery-вызове и убрать лишнюю работу с сохранением freshness/identity
и отказов; постоянный кеш KB по умолчанию не вводить. Отдельно продолжить карту
planning recognition и подготовку проверяемого автономного development trial.
Map отложен; новые модельные запросы в этом этапе не выполняются.
