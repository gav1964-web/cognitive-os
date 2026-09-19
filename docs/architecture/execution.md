# Execution: исполнение и восстановление

Контракт вкладов KB: `runtime/competency_knowledge.py` и
`config/knowledge_providers.json`. Выбор владельца идёт по метаданным; вызов
использует существующий plugin entrypoint со схемами и сверкой полного hash.
Разрешены active провайдеры с read-only/none filesystem и без network/secrets.
Это trusted in-process выполнение, не OS sandbox. KB читается заново; изменение
уже импортированного кода требует нового процесса. Проверки:
`tests/runtime/test_competency_knowledge.py`, [граница пилота](pickle_competency_20260915.md).

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
