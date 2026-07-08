# RUNTIME_OPERATIONS.md
**Операционный контур Cognitive OS Runtime**

### 1. Быстрый обзор состояния

```text
python tools/runtime_report.py --root . --journal-tail 20
```

Отчет показывает:

* queue counts и stale running jobs;
* registry status counts;
* quality metrics по capabilities;
* последние failure events;
* хвост execution journal.

### 2. Очередь

Поставить pipeline в durable queue:

```text
python tools/enqueue_pipeline.py --root . --pipeline pipelines/fetch_parse_save.json --input-json "{\"url\":\"mock://ok\",\"output_path\":\"artifacts/outputs/queued.json\"}" --priority 10 --max-attempts 3
```

Посмотреть очередь:

```text
python tools/queue_status.py --root .
python tools/queue_status.py --root . --status failed
```

Архивировать terminal jobs:

```text
python tools/queue_cleanup.py --root . --archive-terminal
```

### 3. Jobs

Посмотреть конкретный job:

```text
python tools/job_inspect.py --root . --id <job_id>
```

Отменить job:

```text
python tools/job_cancel.py --root . --id <job_id> --reason manual_cancel
```

Вернуть non-terminal job в очередь:

```text
python tools/job_requeue.py --root . --id <job_id>
```

Вернуть stale/lease-expired running jobs:

```text
python tools/job_requeue.py --root . --older-than-seconds 60
```

### 4. Workers

Разово обработать очередь до idle:

```text
python tools/run_worker_pool.py --root . --workers 2
```

Bounded daemon-like loop:

```text
python tools/run_worker_pool.py --root . --workers 2 --loop-cycles 10 --idle-sleep 1 --requeue-stale-seconds 60
```

По умолчанию worker pool форсирует `process_boundary=true`. Для диагностики можно отключить это:

```text
python tools/run_worker_pool.py --root . --workers 1 --allow-in-process
```

### 5. Registry

Проверить drift registry относительно plugin-каталогов:

```text
python tools/registry_doctor.py --root .
```

Проверить plugin contracts:

```text
python tools/check_plugins.py --root .
```

Понять, почему registry выбирает capabilities в таком порядке:

```text
python tools/registry_selection_report.py --root .
```

### 6. Smoke

Полный smoke-набор:

```text
python tools/runtime_smoke.py --root .
```

Быстрый smoke без pytest:

```text
python tools/runtime_smoke.py --root . --skip-pytest
```
