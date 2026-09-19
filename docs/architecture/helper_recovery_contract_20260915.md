# Recovery: три шага разделения, 15 сентября 2026

## 1. Карта зависимостей и прежние результаты

Recovery последовательно читает четыре recipe: append mapping, JSON dumps,
JSON loads, splitlines. Выбор по candidate symbol и development-правило одного
prepared результата остаются снаружи компетенции. AST-генераторы JSON/text
находятся в runtime; append generator, recipe и KB уже принадлежат плагину.
Низкоуровневые aliases остаются совместимыми. Differential verification читает
recipe независимо и сохраняет compile/наблюдения/source-backed проверки.

До изменений сохранены 18 полных RecoveryPatchPackage результатов: 12 append
случаев и positive/refusal для трёх остальных reducers. Девять prepared.
В fixture нормализован только абсолютный `sandbox_project`; source, diff,
metadata, refusal, hashes, patch digest и policy сравниваются полностью.
`tests/fixtures/helper_recovery_packages_legacy.json` — тестовый эталон, не KB.

## 2. Общий контракт

`runtime/helper_proposal.py` проверяет envelope `helper_proposal.v1`:
`status`, `source`, `operation_details`, `reason`. Proposed содержит source и
null reason; not_applicable содержит null source, пустые details и причину.
Неизвестные поля/версии/status отклоняются. Metadata не может подменить
`artifact_type`, `kind`, `target`, `file`, `created_target`, `diff`.
Результат копируется; принятие envelope не даёт полномочия записи.
Контракт структурный: корректность программы остаётся задачей compile/replay.

## 3. Подключение владельца

Append mapping 0.4.0 предоставляет `propose_helper`: `ok` + `proposal`.
Плагин определяет свои четыре поля metadata и причину неприменимости;
старый `propose_patch` сохраняет прежний результат. Input source/symbols/limit
прежние, алгоритм один. Плагин не импортирует runtime и не пишет исходники.

`helper_extraction_dispatch` содержит ограниченную таблицу четырёх механизмов.
Append использует registered client, остальные — adapters к прежним генераторам.
Нет исполняемых имён функций из KB, динамических импортов или приватного fallback.
Recovery получает общий envelope, проверяет его до compile/write и собирает
прежний пакет. Выбор кандидатов, sandbox, hashes и полномочия остаются у него.
Метаданные трёх ещё не выделенных механизмов остаются в их local adapter.

## Доказательства и продолжение

Исходники до переноса: `artifacts/verification/append_result_before_20260915.json`.
Шаг 2: `artifacts/verification/helper_proposal_step2_20260915.xml`.
Шаг 3: `artifacts/verification/helper_recovery_focused_20260915.xml`.
Фокус: 82 passed; structural contract step 2 отдельно — 14 passed.
AST/hash preservation: `artifacts/verification/helper_recovery_preservation_20260915.json`.
Финальная регрессия: `artifacts/verification/development_stage_helper_recovery_20260915.json`.
Актуальность и сохранение: `artifacts/verification/helper_recovery_final_audit_20260915.json`.
Архитектура: `artifacts/verification/helper_recovery_architecture_20260915.json`.

Первый expanded snapshot: `artifacts/development/stage-519382134f/report.json`,
483 passed, 1 failed, 2 local-corpus skipped. Соседний Reviewer обращался к
`intent=null` как к словарю в blocked legacy recovery. Исправление внутри
проверки шага 3 нормализует отсутствие intent; model-delivery claim без causal
comparison по-прежнему отклоняется. Целевые проверки и прежний упавший сценарий:
`artifacts/verification/helper_recovery_review_fix_20260915.xml`.
Это обнаруженный дефект Reviewer, отдельно от функционального переноса.

Три шага завершаются этим подключением и проверками. Следующая отдельная задача —
карта владельца JSON serialization: собственные recipe/KB/algorithm при том же
proposal-контракте. JSON parsing и text splitting заранее не объединяются с ним.
Native/model исследования независимы; Map отложен. Оценки качества не повышаются,
модельные вызовы не требуются. Sandbox здесь — копия trusted-кода, не OS isolation.
