# Execution: исполнение и восстановление

Назначение: исполнить проверенный Pipeline через зарегистрированные возможности,
сохранить журнал и управлять очередью/worker lifecycle.

Начинать с `runtime/executor.py`, `runtime/durable_queue.py`,
`runtime/worker_pool.py`. Контракты: `runtime/models.py`,
`registry/interface_contracts.json`, capability registry и plugin schemas.
QueueLock, lease token и execution journal — части общего протокола очереди.

Зависимости: Evidence и process helpers пакета Replay; плагины загружаются
динамически через registry. Изменение execution semantics может затронуть роли,
хотя этот brief не перечисляет все возможные динамические пути.

Проверки: durable_queue, durable_queue_lock, worker_pool, executor_acceptance.
Сохранять отказ при неверном lease и отсутствие успешного результата без
фактического исполнения/acceptance evidence. Нагрузочные SLO и полнота поведения
при сбоях для отдельного queue product пока не доказаны.

Это внутренняя подсистема. Выделение отдельного пакета сейчас добавило бы API
до того, как проверена самостоятельность полного recovery/execution контура.
