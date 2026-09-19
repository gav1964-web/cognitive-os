# Продолжение плана 9.7+: evidence и причинный ремонт

Дата: 12 сентября 2026. Статус: проверенный компонентный ремонт и доработка
границ исполнения; полный ролевой ремонт и независимый holdout не завершены.

## Защита допуска

Негативный baseline выявил 8 ошибок из 10 проверок: verifier принимал
пересчитанный digest при слабом балле, пропавшей/дублированной ячейке, другом
пороге или ссылке на неуспешный ledger; builder принимал infinity, балл выше 10
и дубликат, скрывающий слабую роль. Baseline сохранён:
`artifacts/verification/certification_adversarial_baseline_20260912.xml`.

Теперь сертификат хранит оценку и её canonical digest, связан с digest policy,
а holdout evaluator записывает те же bindings. Verifier заново вычисляет допуск
по проверенному ledger и текущей policy. Без evidence root он возвращает false.
Все требуемые ячейки должны быть уникальны, баллы — конечными числами 0–10.
Дополнены проверки подмены всей оценки, другого успешного holdout и policy.
Порог 9.7 не снижен. Старые v2 без новых bindings остаются историей и требуют
переоценки перед новым допуском; файлы evidence не переписаны.

Это проверка согласованности и целостности доверенного ledger. Она не делает
подписи producer/evaluator доказательством организационной независимости и
не заменяет проверку истинности исходных экспериментальных утверждений.

## Реальный stateful development case

Источник: `MusicScience37Projects__utility-libraries__py-msgpack-rpc`, baseline
HEAD и inventory сохранены в
`artifacts/causal_trials/rpc_disconnect_20260912/provenance.json`.
До выбора метаданные корпуса называли его untouched; после чтения исходников
и написания внешнего теста это **exposed development**, не blind holdout.
Проект — async RPC SDK, вне двух узких CLI/pure-library групп.

Наблюдение: `ClientProtocol.connection_lost` отменяет writer и устанавливает
closed event, но не завершает Future, ожидаемые запросами. Upstream patch не
использован; исходники корпуса не изменены. Среда — Python 3.13.15, msgpack 1.2.1.

| Попытка | Наблюдаемый результат |
|---|---|
| Public AsyncClient.call, Windows | Тайм-аут при создании служебной socketpair asyncio, до утверждения о дефекте; повтор вне sandbox не помог |
| Компонентная проверка с настоящими asyncio Future | Повторяемое падение; reducer сократил JSON с 42 до 5 байт за 26 попыток |
| Исходный intake | `reproducible_unbound_failure`, COS остановился до ремонта |
| Дополнительный диагностический тест ассистента | Существующий state-transition binder связал сбой с `ClientProtocol.connection_lost`; следующая остановка — `no_verified_failure_reducer` |
| Учебный оператор и causal pattern | Analyzer/Architect/SpecWriter/ImplementationPlan/TestPlan/ReviewFindings согласованы; executor создал patch в sandbox |
| Внешний компонентный review patch | 9 passed: исходные message-тесты, два теста дефекта и четыре edge cases; три неверных варианта отклонены |
| Первый полный запуск | Завис во время in-process подготовки acceptance, итогового receipt нет; успех не засчитан |
| Повтор после ограничения подготовки | `needs_replanning`: targeted native test passed, acceptance probe timed out, полная native regression timed out; source inventory COS и проектной копии неизменны |

Основные receipts в `artifacts/causal_trials/rpc_disconnect_20260912/`:
`reduction_state.json`, `intake.json`, `intake_diagnostic.json`,
`development_diagnostic_baseline.json`, `role_handoff.json`,
`component_review.json`, `development_training_v2.json`.
Результат первоначальной зависшей попытки не следует восстанавливать как успех
по существованию её patch. Ролевой planning review `approve_with_risks` также
не является итоговым подтверждением исправления.

Компонентные тесты вручную продвигают синхронное тело coroutine send_request,
используют BaseEventLoop для создания настоящих Future и не запускают сеть.
Это ограниченная проверка состояния, не эмуляция полной TCP-интеграции.
Неверные варианты: отсутствие правки, только clear карты, set_result(None)
вместо ошибки. Наблюдатели сохраняют ссылки на Future, поэтому clear не скрывает
незавершённость. Native RPC server/transport тесты остаются непроверенными.

Оператор `complete_pending_futures_on_disconnect` остаётся training_only и
требует explicit_training_replay. Он поддерживает только узкую AST-форму
cancel-writer → closed-event с одной типизированной Future-картой и записью
Future-параметра. Он сохраняет completed/cancelled futures и причину ошибки.
Аннотации не доказывают реальные типы: обязательны исполняемые проверки.
Поведение поздних ответов, новых запросов после close, освобождение карты и
гонки транспорта этим оператором не подтверждены. Перенос на другой реальный
проект пока не проверен.

## Исправление границы исполнения

Подготовка harness сама импортирует и вызывает код проекта. Ранее host-ветка
делала это в основном процессе; тайм-аут последующих pytest её не ограничивал.
Теперь обе ветки используют отдельный процесс через Replay, default timeout
30 секунд, и возвращают структурированную ошибку. Ошибка подготовки не может
превратиться в passed за счёт одних структурных generated tests.

Первое изменение сломало загрузку runtime при временном workspace root:
широкая проверка дала 88 failed / 115 passed. Исправлено разделение каталога
COS и проверяемого проекта; регрессии выполняются повторно. Сохранены исходный
receipt и отдельная ошибка параллельного pytest из-за общего basetemp. Для
дальнейших прогонов используются отдельные временные каталоги.

Фокусная проверка перед расширением: 90 passed; после исправления runtime root
15 acceptance-тестов passed. Итоговая проверка в неизменяемой копии и gate 400
строк фиксируются в `artifacts/verification/development_stage_causal_20260912.json`.
Полный canonical suite не подменяется этим scope. Полный Linux CI остаётся
в очереди до появления runner с рабочим loopback.

## Следующий переход

1. SpecWriter/Tester должны переносить stateful fixture и native test из
   failure packet в исполняемое acceptance. Сейчас для callback генерируется
   фиктивное `exc="sample"`, а положительный signature sample не проверяет
   ожидающие Future. Исправлять этот переход с отрицательными controls,
   сохраняя требование поведенческого acceptance.
2. Запустить public-call/native integration на поддерживаемой Python 3.12/3.13
   с рабочим asyncio и pytest-asyncio. Прежний regression override не применился
   к скопированному имени проекта: v2 действительно запустил полную suite и
   получил timeout, а не успешный ограниченный набор.
3. Проверить второй development case, затем отделённый CLI/library pilot и
   независимый holdout по принятому плану. Не выдавать SDK-case за pure library.

Текущие независимые баллы шести ролей не пересчитаны. Повторная оценка старых
training artifacts текущим evaluator сохранила прежний digest
`sha256:842b7b88716714054a8a6c0e932a9c6302c5c72ca05ba7e60c00bae25fcb02cb`:
`artifacts/verification/current_semantic_baseline_20260912.json`.
Это rescore сохранённых artifacts, не новый execution baseline известных cases.
В новых RPC-проверках LLM не вызывалась; независимое сравнение маршрутов и
сверка расходов шлюза остаются отдельными задачами.
