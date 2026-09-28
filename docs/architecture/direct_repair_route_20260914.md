# Прямой ремонт в штатной цепочке COS

14 сентября 2026. Выполнен пункт 3 плана после сравнения маршрутов.
**Результат:** прямой кандидат проходит COS до `experiment_validated`, полной
native-suite markdownify (81 passed) и финального Reviewer (`approve`).
Есть сохранённый patch package. Исходный проект не изменён.

## Изменение

Policy `model_proposal_route="direct"` выбирает один patch-запрос вместо
предварительной модельной гипотезы. При отсутствии поля действует прежний
`hypothesis`; смена default для других проектов пока не обоснована переносом.
Поле передаётся из `run_project_development` в `validate_llm_diagnosis_proposals`.
Неизвестный маршрут отклоняется, существующие разрешения на model trial обязательны.

`runtime/upstream_direct_proposals.py` собирает исходные facts/tests, необязательные
observations, историю контрпримеров, reached branches и явный task contract.
Модель возвращает один candidate; исходные assertions нельзя заменить своим
планом. Максимум initial context — 32k символов; превышение останавливает запрос.
При `model_require_assertion_plan=true` direct сохраняет исходный assertion
contract, но не требует свободного модельного пересказа каждого assertion.
В режиме hypothesis прежняя проверка assertion_plan сохраняется.

У direct provenance явно указаны `proposal_route` и `request_context_digest`;
нет выдуманного `hypothesis_response_digest`. Формат исходного candidate response,
единственный target, signature, source identity, native comparison, точные bytes,
полная regression и final Reviewer остаются обязательными. Grounding direct-route
и source obligations передаётся через Spec/Plan и проверяется при доставке.
Удаление grounding сразу из обоих плановых документов не обходит admission.

Существующие format/native retry budgets остаются явными и ограниченными;
direct native retry требует новый patch, а не новый модельный дизайн. В реальном
запуске этого этапа оба retry выключены. Производственные fallback-настройки
не менялись. Сами helpers не предоставляют permission на изменение исходного проекта.

При проверке найден и исправлен handoff-дефект `model_issue_intent`: helper
не переносил grounding в intent для requested delivery. Теперь binding сохраняется
и в этом пути. Исходное падение теста сохранено, затем regression прошла.

## Проверки на реальном markdownify

| Запуск | Обращения наружу | Native suite | Reviewer |
|---|---:|---|---|
| Повтор сохранённого ответа модели через COS | 0 | 81 passed | approve |
| Реальный inference client через новый маршрут | 2 всего | 81 passed | approve |

Во втором запуске одно обращение — старый L3.5 `project_signals` к модели `local`.
Оно получило HTTP 400; анализ продолжился с deterministic fallback. Второе —
repair-запрос к DeepSeek, gateway сообщил cache hit и usage 0. Резервная модель
не использовалась. Обе попытки входят в заранее записанный предел 2.
У local попытки usage неизвестен; нулевой reported usage DeepSeek не означает
нулевой billing. Этот запуск подтверждает новый путь и доставку уже известного
ответа, не новый независимый вывод модели. Дополнительных paid retries не делали.

Оба запуска используют один consumed assisted case. Вход direct запроса проверен
на полное равенство исходным messages успешного предыдущего сравнения; патч не
редактировался вручную. Сохранённый replay помечен как инженерная проверка,
не как новый LLM-вызов. Original/source hashes и копии после native tests сверены.
Следовательно, это одна исправленная задача в двух режимах доставки, не два ремонта.

Тесты также проверяют direct native retry, malformed responses, выход за scope,
отсутствие разрешения, подмену provenance, source obligations и полную цепочку
для явных требований REPAIR/PRESERVE. Старый hypothesis-route проверен рядом.

## Что дальше

Пункт 4: два других development-дефекта из разных проектов, с заранее
зафиксированными исходниками, полными проверками и расходом. Default routing
менять после результатов переноса. Убрать ненужный L3.5 запрос из bounded repair
или явно управлять им — отдельная задача учёта/стоимости, а не новый quality gate.
Затем независимый holdout по исходным критериям 9.7+. Новых role scores здесь нет.
Map остаётся отложен. В этом этапе дальнейших модельных запросов нет.

## Receipts

- `artifacts/causal_trials/direct_repair_delivery_20260914/`: декларации, transcripts,
  transport counter, telemetry, source checks, полные COS results.
- Там же `delivery_audit.json`: все source/native/provenance/accounting checks.
- `live_patch_package.json`, `live_native_result.json`, `live_final_review.json`:
  точные копии выходных receipts штатного executor, сохранённые рядом с опытом.
- `artifacts/verification/direct_repair_route_focused_20260914.xml`: первое
  диагностическое падение handoff, 35 passed / 1 failed.
- `direct_repair_route_handoff_20260914.xml`: 18 passed после исправления;
  `direct_repair_route_requested_20260914.xml`: requested direct chain, 1 passed.
- `artifacts/verification/development_stage_direct_repair_route_20260914.json`:
  итоговый snapshot regression и обязательный gate 400 строк.
- `artifacts/verification/direct_repair_route_final_audit_20260914.json`:
  финальная сверка дерева, receipts, решений, бюджета и ограничения выводов.
