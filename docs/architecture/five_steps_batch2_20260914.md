# Следующие пять шагов: 14 сентября 2026

Второй ограниченный пакет: пять шагов оценены, 9.7+ не подтверждён.
Реальный модельный patch дошёл до native comparison и исправил assertion для
заголовка, но нарушил следующий assertion для ячейки таблицы. Принятого ремонта
markdownify по-прежнему нет. Ни holdout, ни прежние баллы не изменялись.

| Шаг | Результат |
|---|---|
| 1. Связь design → candidate | Добавлен source-bound `repair_candidate_audit`: исходные достигнутые returns, число синтаксически эквивалентных returns кандидата, хеши дизайна и точного replacement. Проверяется повторно перед native execution/delivery |
| 2. Single-function feedback | Ошибка формата получает ограниченные AST diagnostics, исходный дизайн и требование сохранения поведения. Один opt-in format retry, без ручного исправления ответа и без одновременного semantic retry |
| 3. Реальный trial | Два DeepSeek HTTP-вызова, первый — gateway-reported cache hit. Кандидат с первой попытки соответствует формату, но не проходит native test. Format retry не потребовался |
| 4. Native regression и admission | Полные baseline и candidate suites: обе 80 passed / 1 failed. Доставка отклонена, финальный Reviewer не допущен. Дополнительно закрыто удаление grounding сразу из Spec и Plan |
| 5. Готовность и handoff | Evidence обновлено, следующий конкретный пробел оставлен в очереди. Независимого нового role/type измерения нет; финализация и snapshot regression обязательны |

## Почему диагноз ещё недостаточен

Гипотеза предложила заменить пустой результат для inline-контекста обычным
представлением переноса строки. Кандидат выполнил этот замысел, удалив проверку
`_inline`. Первые три assertions `test_br`, включая заголовок, прошли; четвёртый
для `<td>` получил ` foo   bar |` вместо ` foo bar |`. Остальные 80 native tests
также прошли. Это более точный контрпример, чем прежняя ошибка формата.

Structured acceptance гипотезы не означает её семантическую правильность.
Моя прежняя характеристика «правильный диагноз» была слишком сильной: наличие
R1 подтверждает ссылку на факт исполнения, но не правильный выбор поведения.
Текущий кандидат согласован с дизайном; теперь существенный разрыв находится
в Analyzer/Architect: необходимо учесть все assertions и разные вызывающие
контексты, а не только первый падающий пример. Нет оснований приписывать отказ
одному лишь формату ответа, модели вообще или наличию cache.

| Роль | Evidence этого пакета | Что не подтверждено |
|---|---|---|
| Analyzer | Указан достигнутый return, исходные signature и target сохранены | Механизм исправления не покрывает контекст таблицы |
| Architect | Конкретный дизайн реализован кандидатом | Выбран неверный общий результат для inline-контекстов |
| SpecWriter | Grounding доходит до Spec/Plan; совместное удаление полей блокируется в тесте | Нет принятой реальной repair-спецификации этого trial |
| Implementer | Точный single-function patch принят парсером и исполнен в копии | Все supplied assertions не исправлены |
| Tester | Реальный native тест отклонил patch; полная suite сохранила контрпример | Нет успешного repair outcome |
| Reviewer | Admission отклоняет неподдержанный кандидат; сквозные отрицательные тесты проверяют gates | Реальный финальный review markdownify не достигнут |

Новых численных оценок эти наблюдения не создают. Исторический holdout 08.09:
Analyzer 8.0, Architect 5.0, SpecWriter 6.0, Implementer 4.0, Tester 0.0,
Reviewer 2.0 — остаётся историей, а не измерением нынешнего кода.

## Контракты и ограничения

`runtime/repair_candidate_audit.py` не делает выводов о сохранении ветви по
совпадению текста return: guards могут измениться. Вложенные функции исключены
из подсчёта. Отсутствие прежнего return также не доказывает исправление.
Audit — диагностический артефакт с `execution_authorized=false`; candidate
provenance хранит дизайн и audit, которые повторно проверяются по исходнику.

`runtime/model_candidate_feedback.py` сохраняет весь отвергнутый JSON и даёт
типы/число top-level AST statements. Диагностика ограничена бюджетами; исходный
prompt не обрезается. Никакого автоматически перенесённого кода или переписанных
строк от модели нет. Existing opt-in format retry остаётся максимум одним.

`runtime/upstream_model_delivery.py` сравнивает grounding intent с дизайном
выбранного кандидата. Совпадения Spec и Plan друг с другом теперь недостаточно,
если оба потеряли branch digest или return IDs/facts. Это проверка целостности,
не независимая аттестация происхождения или семантики.

## Расход и receipts

Два логических / два transport calls, **2638 reported tokens**. Гипотеза:
gateway `cache_hit=true`, reported tokens 0; кандидат: `cache_hit=false`,
2638 tokens. Fallback не потребовался. Заголовки впервые наблюдались в реальном
рабочем trial после реализации telemetry; независимый provider billing неизвестен.
После неуспешного trial новых model calls в этом пакете не делали.

Корень: `artifacts/causal_trials/five_steps_batch2_20260914/`.
`model_trial/` содержит точные ответы, source inventories и source checks.
`native_counterexample.json` связывает исходный packet, точный patch и pytest
output; `native_review.json` хранит полные suite probes и отказ допуска.
`accounting.json`, `readiness.json`, `progress.json` сохраняют расход и остановку.

Проверки: `artifacts/verification/five_steps_batch2_01_02_20260914.xml`
(40 passed), `five_steps_batch2_04_20260914.xml` (итоговый focused scope).
Snapshot regression и gate 400 строк:
`artifacts/verification/development_stage_five_steps_batch2_20260914.json`.
Итоговая сверка: `artifacts/verification/five_steps_batch2_final_audit_20260914.json`.

## Следующий подход

Перед следующим модельным запросом использовать сохранённый native counterexample:
новое падение связано с table-cell whitespace, хотя заголовок уже проходит.
Нужны source-bound различающие наблюдения по всем assertions одного теста и
явное сохранение успешных контекстов в диагнозе/дизайне. Затем один заранее
ограниченный semantic-feedback trial на том же consumed случае, полная native
suite и Reviewer. Не смешивать format и semantic budgets, не копировать ручной
reference в запросы и не объявлять consumed case независимым holdout.
Map остаётся отложен. Текущий лимит пяти шагов исчерпан.
