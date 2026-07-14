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

Каждая краткая запись job содержит `packet_count` - количество сохраненных межслойных packets в результате. Полный packet trace, adaptations и output конкретного job доступны через `job_inspect.py`.

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

### 7. Acceptance

Portable deterministic gate, используемый CI после pytest:

```text
python tools/mvp_acceptance.py --root . --skip-pytest
```

Живой L4 quality probe и локальные corpus не входят в portable gate и подключаются явно:

```text
python tools/mvp_acceptance.py --root . --skip-pytest --live-l4
python tools/mvp_acceptance.py --root . --skip-pytest --local-project-trials
```

`--live-l4` требует доступный model provider. `--local-project-trials` требует локальные `F:/ubuntu/test/map`, `5`, `004` и загруженный `benchmarks/github_full_trial_10`; эти данные не входят в чистый checkout.

Default-профиль внешнего L4 использует `GigaChat-Pro` через `http://127.0.0.1:8000/v1`. Его можно переопределить без изменения кода:

```powershell
$env:COGNITIVE_OS_L4_MODEL = "GigaChat-Pro"
$env:COGNITIVE_OS_L4_BASE_URL = "http://127.0.0.1:8000/v1"
```

Детерминированный acceptance не вызывает L4. Токены расходуются только при явном `--live-l4`, `--use-l4-llm` или `--interpret-project-llm`.
