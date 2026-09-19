# Сохранённые неудачи: внутреннее место ремонта

14 сентября 2026. Локальный assisted этап после fresh серии 0/4.
Новых модельных запросов нет. Два диагностических исправления выбраны
ассистентом после чтения frozen baseline и применены только в копиях.
Upstream production fixes не читались; исходные проекты и первая серия сохранены.
Это проверка причин и инструмента COS, не автономный ремонт или новые баллы ролей.

## Подтверждённые причины

| Проект | Локальное изменение | Полная native suite до → после |
|---|---|---|
| Pyupgrade | `_plugins/identity_equality.py:_is_literal`: исключать тип `bool`, вместо сравнения значения с `{True, False}` | 1096 passed / 2 failed → 1098 passed / 0 failed |
| Toml-sort | `TomlSort.toml_doc_sorted`: не записывать footer повторно, если документ без элементов уже записан как header | 33 passed / 1 failed → 34 passed / 0 failed |

Точные коллекции сохранены, новых failures/skips нет. Прежние JUnit skipped:
Pyupgrade 7 (1 skip + 6 xfail), Toml-sort 2 xfail. Дополнительные локальные
контроли: числовые `0`, `0.0`, `1`, `1.0`, сохранение `True/False/None`, строки
и обычные числа; четыре сочетания header/footer. Контроли подтверждают механизм,
но не являются частью прежнего native suite или независимым oracle.

Pyupgrade сравнивает элементы множества по равенству: `1 == True`, `0 == False`.
Поэтому не создаётся callback замены `is`, хотя внешний `_fix_plugins` работает
по своему контракту. Сохранены реальные owned call edges и результаты `_is_literal`.
Для Toml-sort отключение любого одного из header/footer убирает дублирование;
оба включены по умолчанию. Изменение newline в `sorted()` не устраняет причину.

## Что действительно получила модель

Аудит точных сохранённых requests: Pyupgrade получил 795 символов `_fix_plugins`,
Toml-sort — 284 символа `sorted()`. Внутренних определений выше не было ни в одном
request. Параметризованные тесты были включены. Сам текст комментария **уже был
виден в observed failure**, хотя файл фикстуры отдельно не приложен. Поэтому
прежняя гипотеза «модели не хватило данных фикстуры» не подтверждается для этого
конкретного входа. Добавлять новый fixture module только ради этого случая оснований нет.
Не доказано и то, что один правильный контекст гарантирует успешный ответ модели.

## Исправление COS

`runtime/repair_target_trace_probe.failing_call_ranges` связывает падающее
равенство с неизменённым локальным результатом вызова. До изменения реальный
Toml-sort trace останавливался: вызов находится в присваивании перед `assert`.
После изменения два одинаковых native replay сохраняют исходную signature,
выделяют `sorted()` и пять внутренних методов, включая `toml_doc_sorted`.

Поддержка намеренно узкая: обычное/аннотированное присваивание вызова,
непосредственное равенство, один вызов observed API. Rebinding, global/nonlocal,
промежуточные обращения к значению, вложенный observer, ветвление и неоднозначная
строка не расширяют диапазон. Два подходящих вызова остаются неоднозначными.
Это синтаксическая связь и execution ancestry, не доказанный произвольный data flow.
Source hashes, два replay, исходный packet, native acceptance и Reviewer сохранены.
Новая версия probe делает прежние trace receipts stale по существующему правилу.

Регрессия: `tests/runtime/test_repair_trace_assignments.py`, nomination, branch,
observations, derived trial, direct route и CLI. Finalization/400-line receipt:
`artifacts/verification/development_stage_internal_targets_20260914.json`.
Профильный scope: 91 passed; 1880 Python-файлов укладываются в 400 строк.
Промежуточный stage `stage-8cbc1ff06f` прошёл все 91 тест, но честно отклонил
handoff после изменения этого отчёта во время проверки. Код снимка не менялся;
причина и сравнение inventories сохранены в
`artifacts/verification/internal_targets_handoff_recovery_20260914.json`.
Итоговый stage выполняется после фиксации документов и очереди.
Архитектурный checkpoint (5 проверок, `--skip-tests`):
`artifacts/verification/internal_targets_architecture_20260914.json`.
Обычный canonical CLI также запускает весь `tests`; этот запуск прерван без
итогового receipt и не считается успешной полной регрессией. Действует прежнее
ограничение полного environment-dependent suite; завершённый профильный scope
фиксируется отдельно в stage receipt.

Все результаты: `artifacts/causal_trials/internal_targets_20260914/`:
`audit.json`, `summary.json`, `{project}/comparison.json`, точные XML,
`values.json` и `intervention_values.json`, `trace_before/result.json`,
`trace_verified_v2/result.json`, `trace_verified_v2_context.json`.
Промежуточные traces сохранены отдельно; текущим является `trace_verified_v2`.

## Следующее действие

Для Toml-sort теперь доступен existing nomination → derived repair trial:
один заранее ограниченный assisted запрос выбора внутреннего метода, затем
кандидат с исходными assertions и полная regression/Reviewer. Не передавать
ассистентский reference patch как модельный результат. Pyupgrade требует
отдельного расширения owned trace на функции и plugin dispatch: нынешний
nomination поддерживает только методы одного класса и один failing nodeid.
Не переписывать исходный target/signature и не отбрасывать второй failing test.
Ручной reference уже известен ассистенту: оба случая остаются consumed assisted.
Группы Wcmatch >8, Pathspec и независимая оценка остаются в очереди.

Автономных принятых ремонтов добавлено **0**, ручных диагностических вмешательств
**2**, дополнительных модельных вызовов **0**. Независимых 9.7+ нет; прежние
calibration уровни 8/5/6/4/0/2 не пересчитывались.
