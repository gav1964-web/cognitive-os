# Пять шагов к 9.7+: результат 14 сентября 2026

Лимит пользователя исчерпан: оценены ровно пять заранее объявленных шагов.
Уровень 9.7+ не достигнут. Четыре инженерных изменения реализованы; реальный
ремонт markdownify в шаге 4 не принят. Новый независимый holdout не проводился,
исторические баллы и критерии сертификации не изменены.

| Шаг | Результат | Доказательства и границы |
|---|---|---|
| 1. Достигнутая ветвь | Реализован | Две трассы markdownify: строки 445–446, R1 — `return ""`. Без значений locals и без утверждения об единственной причине |
| 2. Analyzer → Architect → SpecWriter | Реализован | Гипотеза ссылается на source-bound return IDs; branch digest и факты доходят до Spec/Plan. Scripted full chain проходит native regression и Reviewer. Это не доказательство верности текста модели |
| 3. Native-контрпример → новый диагноз | Реализован | Один явно включаемый повтор после проверенного неуспешного native вмешательства. Сохранены обе попытки. Проверено scripted ответами с реальными subprocess-тестами |
| 4. Реальный ремонт markdownify | Неуспешный эксперимент | Три DeepSeek-вызова, ноль принятых ремонтов. Итоговый кандидат отклонён до native execution: модульная константа нарушает single-function scope |
| 5. Маршрут, расход и аудит готовности | Реализован; реальные metadata ещё не измерены | COS сохраняет разрешённые заголовки шлюза; transport tests проходят. Косметического платного запроса не делали. Billing и независимая provider identity не подтверждены |

## Контракты

`runtime/repair_branch_trace_probe.py` расширяет прежний probe только для явно
выбранного внутреннего метода. `runtime/repair_branch_evidence.py` проверяет
repair packet, исходники, probe hash, повторяемость, границы метода и достигнутый
AST Return. Исключение, неоднозначность или превышение бюджета блокируют evidence.
В `run_project_development` необязательный `repair_branch_evidence` требует
`repair_nomination` и повторной проверки.

Гипотеза получает `reached_returns` и `branch_digest`; JSON Schema условно требует
`reached_return_ids`. Дизайн передаёт данные в `repair_grounding` у implementation
intent; Spec/Plan должны совпадать. Ссылка на R1 не доказывает, что предлагаемый
код исправляет ветвь: native gates сохранены.

Policy `model_native_counterexample_retries` допускает 0 (default) или 1.
Повтор разрешён только после `no_supported_candidate` с проверенными baseline,
patch inventory и pytest output. Он не совмещается с format retry; максимум
четыре логических вызова в таком цикле, transport failover учитывается отдельно.
Ошибка формата или провайдера не становится semantic counterexample.
`runtime/repair_counterexamples.py` не предоставляет execution authority.

`runtime/inference_route_evidence.py` допускает только ограниченные cache/route/
duration поля из известных заголовков. `runtime/local_inference.py` сохраняет
их как `gateway_route` с authority `gateway_reported_not_provider_attested`.
Отсутствующий заголовок не означает cache miss. Reported usage, cache claims
и нулевые поля не являются счётом провайдера. Секретные заголовки не сохраняются.

## Реальные попытки и моя ошибка

Использован прежний frozen consumed assisted case markdownify. Исходный проект
сохранён; upstream oracle не читался. Ранее известный ручной reference patch
не передавался модели. Это development, не независимый holdout.

| Попытка | Вызовы | Reported tokens | Результат |
|---|---:|---:|---|
| attempt_01 | 1 | 6780 | Модель правильно указала ранний возврат и structured R1, но моя избыточная проверка требовала повторить буквальный R1 ещё и в prose. Исходный отказ сохранён |
| attempt_final | 2 | 9232 | После удаления избыточного prose-требования гипотеза принята; patch отклонён с `replacement_must_be_single_function` |
| Всего | 3 | 16012 | Принятых ремонтов 0; billing неизвестен |

Structured ID validation сохранена и проверена отрицательными тестами. Ответы
модели вручную не исправлялись. Последний кандидат также удалял inline-ветвь;
исправление только формата ещё не означало бы успешный ремонт. Полная native
suite и Reviewer для реального нового кандидата не запускались.

## Receipts и остановка

Корень опыта: `artifacts/causal_trials/five_steps_20260914/`.
`progress.json` фиксирует пять шагов и `five_step_limit_reached`;
`branch_evidence.json` — реальные трассы; `accounting.json` — вызовы;
`readiness.json` — ограничения и хеши исторических semantic receipts.
Точные ответы, telemetry и source checks находятся в `model_trial/`.

Focused checks: `artifacts/verification/five_steps_01_20260914.xml` (30 passed),
`five_steps_02_03_20260914.xml` (36 passed), `five_steps_05_20260914.xml`
(56 passed), `five_steps_final_focused_20260914.xml` (40 passed после последней
правки; наборы пересекаются, результаты не суммируются).
Итоговая snapshot regression и 400-line finalization:
`artifacts/verification/development_stage_five_steps_20260914.json`.
Итоговая сверка: `artifacts/verification/five_steps_final_audit_20260914.json`.

В очередь следующего подхода оставлены согласованность design → candidate,
дисциплина single-function ответа и проверенный format feedback, затем точный
модельный patch, полная native regression и Reviewer на том же consumed случае.
Независимый holdout остаётся отдельным этапом; map отложен. После пяти шагов
выполняется только финализация, новых модельных попыток в этом этапе нет.
