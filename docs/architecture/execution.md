# Execution: исполнение и восстановление

[Постоянный Windows worker](remote_worker_service_20260928.md):
`runtime/remote_support_daemon.py`, `runtime/remote_support_deployment.py`,
`tools/remote_support_service.py`, `tools/prepare_remote_worker.py`,
`tools/remote_support_install.py`. Проверки `test_remote_support_daemon.py`.
Пакет установлен пользователем. [Проверка](remote_worker_live_20260928.md):
ACL/offline admission проходят. [Продолжение на 8200](remote_worker_8200_20260929.md):
service health200, live role smoke завершён с 23/23 +36/36 приёмки.
Опциональная хешированная история `remote_role_job.known_calls` переносится только
для сверки учёта кэша, без replay ролевых решений. Проверки `test_remote_role_cache.py`.

[Удалённый ремонт через сообщения](remote_support.md):
`runtime/remote_support_supervisor.py` и `tools/remote_support.py` — отдельный
opt-in контроллер над выбранным выпуском COS. Подписанные обращения/контекст/патчи,
локальная приёмка, новый процесс для продолжения и откат указателя.
Транспорт v1 файловый; OS-изоляция проверяется отдельно.
`runtime/remote_role_job.py` связывает цель, исходники, ролевой checkpoint,
принятые тесты и бюджет; `runtime/remote_role_worker.py` повторно проверяет
приёмку и продолжает с Programmer. Команда: `tools/remote_role_worker.py`.
Проверки: `test_remote_support.py`, `test_remote_role_support.py`,
`test_remote_support_worker.py` в `tests/runtime/`.
Следующий [контракт](remote_support_recovery_20260928.md): controller-side ledger
резерв (`remote_support_accounting.py`) и worker под отдельным Windows SID
(`remote_support_exchange.py`, `remote_support_windows.py`, `tools/remote_support_worker.py`).
Проверки `test_remote_support_accounting.py`, `test_remote_support_exchange.py`;
локальный ACL-пилот отделён от проверки полного production-развёртывания.

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
