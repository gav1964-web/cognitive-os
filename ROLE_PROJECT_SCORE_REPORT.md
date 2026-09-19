> Датированный отчёт. Текущий статус: [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md); карта исходников: [PROJECT_MAP.md](PROJECT_MAP.md).

# Cognitive OS: оценки ролей и проектов

Последний assisted [Toml-sort с внутренним контекстом](docs/architecture/toml_internal_model_20260914.md):
**0 принятых ремонтов**, 6 новых регрессий отклонённого кандидата. Повторная
calibration дала **8/5/6/4/0/2** в порядке ролей ниже. Более полный контекст
не повысил измеренный результат; независимых 9.7+ нет.

Локальный этап [14 сентября](docs/architecture/internal_targets_20260914.md)
дал два ручных reference repairs (1098/0 и 34/0), без новых модельных вызовов.
Это evidence для исправления диагностики; приведённые ниже уровни не повышены.

## Новые случаи 14 сентября: первая серия и assisted повтор

Первая серия: **0/4 ремонтов**. Pathspec/Wcmatch/Toml-sort остановлены intake,
Pyupgrade получил отклонённый модельный кандидат. После исправлений Analyzer
и окружения повтор Toml-sort тоже отклонён; полная suite выявила 19 новых регрессий.

| Роль | Pyupgrade, первая попытка | Toml-sort, assisted повтор |
|---|---:|---:|
| Project Analyzer | 8.0 | 8.0 |
| Architect | 5.0 | 5.0 |
| SpecWriter | 6.0 | 6.0 |
| Implementer | 4.0 | 4.0 |
| Tester | 0.0 | 0.0 |
| Reviewer | 2.0 | 2.0 |

Неизменённая calibration-рубрика, не сертификат. Ноль Tester означает отсутствие
принятого изменения, хотя native tests выполнялись и отклонили неверные кандидаты.
Остальные первые остановки не получили выдуманных ролевых баллов. Это новый набор,
не сопоставимое повторное измерение прежних учебных 9.0/8.8/8.8.
[Результаты, расходы, source hashes](docs/architecture/fresh_direct_batch_20260914.md).

## Измерение 14 сентября 2026: перенос direct

Humanize: **720 passed / 74 прежних skipped**; vblf: **44 passed**.
Оба ремонта дошли до финального Reviewer `approve`; vblf потребовал настройки
baseline-протокола после первой остановки. Это consumed development.

| Роль | Humanize, training caps | vblf, training caps | Независимые 9.7+ |
|---|---:|---:|---|
| Project Analyzer | 8.0 | 8.0 | Нет |
| Architect | 5.0 | 5.0 | Нет |
| SpecWriter | 6.0 | 6.0 | Нет |
| Implementer | 9.0 | 9.0 | Нет |
| Tester | 8.8 | 8.8 | Нет |
| Reviewer | 8.8 | 8.8 | Нет |

Неизменённый calibration evaluator даёт последним трём ролям 10.0 на этих
доставках; выше применены существующие ограничения использованных учебных случаев.
Первые три роли не предъявляют все необходимые diagnosis/design/delta artifacts.
Researcher сопоставимо не измерен. Новый CLI/holdout здесь не запускался.
[Полный отчёт и receipts](docs/architecture/direct_transfer_20260914.md).

Ниже — прежние измерения на 10 сентября; их значения сохранены как история.

## Дополнение: независимые CLI-попытки и учебный vblf

| Роль | Granny: первая попытка | Rosbags: первая попытка | Подтверждено 9,7+ |
| --- | ---: | ---: | --- |
| Project Analyzer | 8,0 | 3,33 | Нет |
| Architect | 5,0 | 0,0 | Нет |
| SpecWriter | 6,0 | 0,0 | Нет |
| Implementer | 4,0 | 4,0 | Нет |
| Tester | 0,0 | 0,0 | Нет |
| Reviewer | 2,0 | 2,0 | Нет |

Granny воспроизводится и связан с `aws_costs_by_service`, но проверенного
исправления нет. Rosbags воспроизводится, однозначной production-цели нет.
Это первые попытки ролей после qualification, без обучающей авторизации и без
чтения production fix. Область — два случая CLI; не blind same-task сравнение.
[Manifest](config/cli_role_results_20260910.json),
`artifacts/verification/cli_role_semantics_20260910.json`.

На **потреблённом учебном vblf** новый диагностический probe указал на потерю
хвоста в `BlfWriter._flush_container`. Ограниченный оператор построил sandbox patch,
диагностический тест и полная native suite (**44 passed**) прошли. Это
`experiment_validated` с явной training authority; fresh-баллы vblf ниже сохранены.
Receipt: `artifacts/verification/vblf_buffer_training_20260910.json`.

## Дополнение: свежая библиотечная диагностика 10.09

| Роль | vblf | anitopy | Подтверждено 9,7+ |
| --- | ---: | ---: | --- |
| Project Analyzer | 8,0 | 3,33 | Нет |
| Architect | 5,0 | 0,0 | Нет |
| SpecWriter | 6,0 | 0,0 | Нет |
| Implementer | 4,0 | 4,0 | Нет |
| Tester | 0,0 | 0,0 | Нет |
| Reviewer | 2,0 | 2,0 | Нет |

Оба upstream-дефекта прошли повторный replay и проверку исправления.
Самостоятельные попытки ролей не дали проверенного patch: у vblf —
`no_verified_failure_reducer`, у anitopy — `reproducible_unbound_failure` и
отсутствие полного набора ролевых артефактов. Частичные баллы внутренней рубрики
не подтверждают выполнение соответствующей роли. Mirror anitopy учтён как
исходная линия `igorcmoura/anitopy`; новых CLI-попыток в этом срезе нет.

Источники: [manifest и ограничения](config/library_role_results_20260910.json),
[семантический отчёт](artifacts/self_development/narrow_type_role_semantics_20260910T113042436921Z.json).
Следующие разделы сохраняют предыдущий срез 8 сентября для сравнения разных задач.

Подтверждённой зрелости 9,7+ на новых дефектах сейчас нет. В последнем семантическом
holdout все шесть обязательных ролей ниже порога. Повторы известных исправлений
успешны, но опубликованные оценки ограничены правилами training replay и также
ниже 9,7. Granny и Rosbags прошли qualification upstream-дефекта; ролевой прогон
на этих cases ещё не выполнен.

Это сохранённые оценки внутреннего evaluator. Сертификация требует отдельного
набора независимых случаев, проверяемых ролевых артефактов и оценки изменения проекта.
Баллы ниже порога, отсутствие оценки и неприменимость роли обозначены отдельно.

## Роли: действующий семантический срез

| Роль | Новые дефекты, holdout 08.09 | Известные исправления, replay 08.09 | 9,7+ подтверждено |
| --- | ---: | ---: | --- |
| Project Analyzer | 8,0 | 9,4 | Нет |
| Architect | 5,0 | 8,5 | Нет |
| SpecWriter | 6,0 | 8,5 | Нет |
| Implementer | 4,0 | 9,0 | Нет |
| Tester | 0,0 | 8,8 | Нет |
| Reviewer | 2,0 | 8,8 | Нет |
| Researcher | Нет сопоставимой оценки | Нет сопоставимой оценки | Не подтверждено |

Programmer Executor не имеет отдельной строки в этой шестиролевой семантической
рубрике: завершение executor и подготовка patch учитываются в проверках Implementer.

В holdout у Analyzer отсутствует причинный диагноз; у Architect — конкретный
дизайн исправления и готовый путь реализации; у SpecWriter — конкретное действие
и готовый implementation delta. Implementer не подготовил подтверждённый patch,
Tester не получил проверенного исправления с targeted/regression outcomes,
Reviewer — подтверждённого результата изменения. Значение Tester 0,0 относится
именно к этому отсутствующему результату в данном holdout.

Все пять training cases имеют structural scores 10,0 для каждой роли. После
ограничений `training_replay` опубликованы значения из таблицы. Это два разных
набора задач; улучшение replay не пересчитывает предыдущий независимый holdout.

Источники: [семантический holdout](artifacts/self_development/narrow_type_role_semantics_20260908T033758449554Z.json),
[последний training replay](artifacts/self_development/narrow_type_role_semantics_20260908T102129049063Z.json),
[manifest replay](config/narrow_type_training_replay_20260908.json).

## Конкретные проекты

Оценка относится к указанному дефекту и прогону проекта. Одна успешная задача не
распространяет оценку на все функции проекта или весь тип проектов.

| Проект / case | Тип | Набор | Analyzer | Architect | SpecWriter | Implementer | Tester | Reviewer |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Rich | library_pure_transform | unseen holdout | 8,0 | 5,0 | 6,0 | 4,0 | 0,0 | 2,0 |
| Click: strict default equality | cli_local_tool | unseen holdout | 8,0 | 5,0 | 6,0 | 4,0 | 0,0 | 2,0 |
| pytest-httpserver: readiness cleanup | framework_plugin_build | unseen holdout | 8,0 | 5,0 | 6,0 | 4,0 | 0,0 | 2,0 |
| Click: strict default equality | cli_local_tool | training replay | 9,4 | 8,5 | 8,5 | 9,0 | 8,8 | 8,8 |
| Autoflake: incomplete import | cli_local_tool | training replay | 9,4 | 8,5 | 8,5 | 9,0 | 8,8 | 8,8 |
| isort: trailing backslash | cli_local_tool | training replay | 9,4 | 8,5 | 8,5 | 9,0 | 8,8 | 8,8 |
| Platformdirs | library_pure_transform | training replay | 9,4 | 8,5 | 8,5 | 9,0 | 8,8 | 8,8 |
| Marshmallow | library_pure_transform | training replay | 9,4 | 8,5 | 8,5 | 9,0 | 8,8 | 8,8 |

Первые три случая завершились `research_required`: на момент независимой проверки
исполняемое исправление не подтверждено. Все пять replay завершили sandbox patch,
исходный failing test и полную native regression. Click представлен дважды:
после первичного holdout этот случай стал известным и использовался для обучения.
Источники — два семантических отчёта выше и
[результаты transfer holdout](config/narrow_type_transfer_results_20260908.json).

| Проект | Подтверждённый результат | Статус относительно 9,7+ |
| --- | --- | --- |
| Invoke | Sandbox patch совпал с upstream source blob; targeted 1 passed, compatibility regression 3 passed | Известный acquisition case; новые role scores не присвоены |
| Granny | Baseline дважды 2 failed / 4 passed; upstream fix 6 passed | Qualified; ролевых оценок ещё нет |
| Rosbags | Baseline дважды 1 failed / 22 passed; upstream fix 23 passed | Qualified; ролевых оценок ещё нет |

Источники: [Invoke](config/historical_defect_acquisition_invoke_20260908.json),
[qualification Granny/Rosbags](artifacts/self_development/historical_defect_mining/public_manifest_20260910T055018172748Z.json).
У обоих qualified cases сохранены source HEAD, worktree и worktree registry,
очистка sandbox подтверждена. Fresh qualification: CLI **2**, library **0**.

Ещё восемь проектов проверены 08.09 на пригодность для нового дефектного holdout.
Их результаты не дали ролевых оценок:

| Проект | Результат intake |
| --- | --- |
| vzd3v/uxon | environment_blocked |
| PennRobotics/shux | environment_blocked |
| aphp-carpem/llm-data-parser | environment_blocked |
| carlosm3011/cross-data-transform | clean_baseline: 31 тест прошёл дважды |
| bagoetadrich/hermes-multi-agent-team | clean_baseline: 22 теста прошли дважды |
| ags4-standard/python_ags4 | environment_blocked |
| sites6821018/dataclass_parser | environment_blocked после коррекции evaluator |
| python-hyper/uritemplate | clean_baseline: 58 тестов и 66 subtests прошли дважды |

Источники: [первая кампания](config/narrow_type_fresh_holdout_results_20260908.json),
[вторая кампания](config/narrow_type_fresh_holdout_results_20260908_b.json).
Их средовые блокировки после подготовки отдельного controller Granny заново не проверялись.

## Откуда появились прежние 9,7–10,0

Последняя агрегированная матрица от 06.09 содержит 79 измеренных ячеек:
**74 с числом ≥9,7**, **5 ниже 9,7**, ещё 2 неизмеренные и 24 неприменимые.
Это исторический контрактный срез. Его значения и отметки maturity сохраняются
для аудита; они не подтверждают текущую семантическую сертификацию.

| Тип проекта | Analyzer | Architect | SpecWriter | Implementer | Tester | Reviewer |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| CLI / локальные инструменты | 9,7 | 9,7 | 9,7 | 9,8 | 10,0 | 9,8 |
| Библиотеки / чистые преобразования | 9,7 | 9,7 | 9,8 | 9,8 | 10,0 | 9,8 |
| Web / API / middleware | 9,7 | 9,7 | **9,6** | 10,0 | 10,0 | 10,0 |
| SDK / provider integration | 9,7 | 9,7 | **9,6** | 10,0 | 10,0 | 10,0 |
| Framework / plugin / build | 9,7 | 9,7 | 9,7 | 9,8 | 10,0 | 9,8 |
| Табличные данные / pipelines | 9,7 | 9,7 | 9,8 | 10,0 | 10,0 | 10,0 |
| Scientific compute | 9,7 | 9,7 | **9,6** | 10,0 | 10,0 | 10,0 |
| ML inference | 9,7 | 9,7 | 9,8 | 10,0 | 10,0 | 10,0 |
| ML training / checkpoints | 9,7 | 9,7 | **9,6** | 10,0 | 10,0 | 10,0 |
| Async workers / schedulers | 9,7 | 9,7 | **9,6** | 10,0 | 10,0 | 10,0 |
| Stateful / database | 9,7 | 9,7 | 9,8 | 10,0 | 10,0 | 10,0 |
| External process / I/O | 9,7 | 9,7 | 9,8 | 10,0 | 10,0 | 10,0 |
| LLM / multi-agent | 9,7 | 9,7 | 9,8 | 10,0 | 10,0 | 10,0 |
| Workspace / portfolio | 9,7 | Н/П | Н/П | Н/П | Н/П | Н/П |
| Unknown / new archetype | Не измерено | Н/П | Н/П | Н/П | Н/П | Н/П |

Researcher в этой матрице применим только к unknown/new archetype и не измерен.
Сырые downstream 10,0 у широких типов имели maturity `usable`, а не доказанную
полноту независимых native transformations. Число и полнота evidence — разные оси.

Источник: [историческая матрица](artifacts/field_trials/role_project_type_evaluation_20260906T142806413196Z.json).
Сертификат шести ролей narrow lane был
[отозван](artifacts/self_development/narrow_type_certification_reassessment_20260906.json):
первые три роли не имели проверяемых семантических артефактов, derived mutation
probe не доказывал понимание проекта. Runtime functionality и исторические
regression outcomes сохранены.

Отдельная повторная проверка framework/plugin на flake8-pytest-style, kiso-testing
и walnats дала Analyzer **4,0**, Architect **2,0**, SpecWriter **1,67**;
Implementer/Tester/Reviewer — без оценки в этой проверке. Статус
`evidence_required`; semantic quality, chain continuity и оценка изменения проекта
не прошли. Это отдельная рубрика и набор случаев от дефектного holdout
pytest-httpserver 08.09. Источник:
[framework semantic reassessment](artifacts/self_development/framework_plugin_holdout_reassessment_final_20260906.json).

## Что требуется для перехода к 9,7+

1. Получить два qualified независимых библиотечных дефекта. CLI уже имеет Granny
   и Rosbags; библиотечный поиск по всем 1858 оставшимся eligible projects дал ноль
   по текущим правилам. Нужны проверяемая классификация библиотек и пополнение корпуса.
2. На frozen cases выполнить полный ролевой holdout с причинным диагнозом,
   конкретным дизайном и спецификацией, sandbox patch, исходным regression test
   и проверкой сохранённых свойств. Зафиксировать outcome до раскрытия oracle.
3. Оценить каждую обязательную роль по действующей семантической рубрике;
   выполнить проверки независимости и отсутствия регрессий. Широкие типы
   сохраняются в deferred lane до подтверждения narrow lane.

Текущие тесты разработки (72 passed и 4/4 structural checks) проверяют реализацию
контура и также не присваивают ролевые баллы.
