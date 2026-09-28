# Stateful acceptance: 12 сентября 2026

Закрыт конкретный разрыв SpecWriter → Tester → executor: контракт `failure_repair`
передаёт исходный native-тест и его fixture через новый формат
`native_failure_acceptance.v1`. Подготовка общего вызова `exc="sample"` для этого
контракта больше не используется. Это targeted behavioral acceptance.

## Контракт и границы

FailureEvidencePacket содержит digest допустимого source inventory и полные
hashes production/test файлов. TestPlan сохраняет packet, точные nodeid и IDs
исходных replay criteria; контракт имеет собственный digest. Исторический packet
без новых bindings остаётся историческим evidence и не допускается к этому запуску.

Исполнитель допускает изменение только одного связанного production `.py` файла.
Тесты, данные и конфигурация должны совпадать с исходным inventory. В отдельных
копиях дважды запускается baseline; должны совпасть failure signature первоначального
intake и повторяемая JUnit-сигнатура. Затем тот же набор тестов проходит на patch
без skips и изменения collection. Проверяется сохранность копий и входных проектов.

Поддержано 1–8 nodeid, ограничение subprocess 20 секунд по умолчанию, максимум 120.
Зависимости должны быть доступны в выбранном interpreter; автоматической установки
и обращения к моделям этот механизм не делает. Pytest autoload отключён, явные
plugins проверяются. Выполнение доверенного кода в subprocess не является sandbox ОС.
Inventory использует существующие исключения private/config.json, .env и generated
artifacts; это не резервная копия всей файловой системы проекта.

Prepared-patch gate требует успешных paired checks и точного покрытия целей плана.
Сигнал `native_failure_replay` отделён от `executable_callable`: generated tests = 0,
учитываются только AC-FAILURE-REPLAY IDs. Проверка границ поведения, полная native
регрессия и окончательный review не становятся доказанными от одного targeted pass.
Evaluator, promotion policy и требования независимости не ослаблены.

## Реальное исполнение и отрицательные проверки

Сохранённый RPC development case использует реальные Future, `send_request` и
унаследованный `ClientProtocol.connection_lost`. Диагностический subclass, тесты,
bounded training operator и causal pattern ранее подготовлены ассистентом;
случай потреблён и не является blind holdout. Upstream fix не переносился в COS.

- Ролевая цепочка создала новый TestPlan с native contract; executor вернул `ok`.
  Исходный тест дважды упал с сохранённой intake signature, на patch прошёл: **1/1**.
- Новый сгенерированный patch прошёл **9 компонентных и message проверок**, включая
  completed/cancelled futures, повторный callback, пустую очередь и причины ошибки.
- Неизменённый код, очистка map без завершения Future и успешный результат вместо
  ошибки отклонены и native acceptance, и внешней компонентной регрессией.
- Исходный корпус и source-копия не изменены. Новых вызовов LLM в этой доработке нет.

Receipts в `artifacts/causal_trials/rpc_disconnect_20260912/`:
`role_handoff_native.json`, `native_acceptance_execution.json`,
`native_acceptance_review.json`. Первый execution содержит COS/source inventory
конкретного запуска; последующие изменения отчётных полей проверяются регрессией
этапа, а не задним числом приписываются его source version.

## Регрессия COS

20 проверок нового механизма включают реальные subprocess, stateful fixture,
неверный patch, подмену тестов/данных/config, устаревший packet, изменённые digest,
потерю source bindings, mismatch nodeid, skip, timeout, изменение файлов из теста,
ошибку collection и вызов через executor. Receipt:
`artifacts/verification/native_acceptance_final_20260912.xml`.

Расширенный Windows-прогон переходов проекта, native intake, executor и role pipeline:
**204 passed**, `artifacts/verification/native_acceptance_broad_20260912.xml`.
Linux-проверка: **59 passed**,
`artifacts/verification/linux_native_acceptance_v2_20260912.xml`.
Первый Linux-прогон сохранил 39 passed / 20 setup errors в
`artifacts/verification/linux_native_acceptance_20260912.xml`: pytest fd-capture
получил FileNotFoundError при truncate временного файла на `/mnt/f`. Перенос
временного каталога тестов в `/var/tmp` устранил эту ошибку среды; acceptance
не принял collection error за воспроизведение дефекта.
Архитектурный checkpoint: **5/5**, без запуска общего CI,
`artifacts/verification/canonical_native_checkpoint_20260912.json`.
Проверки итогового snapshot, 400-line gate и queue handoff:
`artifacts/verification/development_stage_native_20260912.json`.
Это объявленная регрессионная область; полный CI не запускался повторно.

## Что осталось

Полный RPC suite/TCP integration ранее заблокирован средой создания event loop;
старые тайм-ауты сохранены. Не повторяем весь suite до рабочего loopback runner.
Stateful acceptance подтверждён на потреблённом RPC, перенос оператора на второй
реальный development case ещё не проверен. После этого нужны независимый CLI/library
holdout и review фактических результатов всех шести ролей. Новых баллов 9.7+ нет.
