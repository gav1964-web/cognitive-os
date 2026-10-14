# Перенос native acceptance и завершающий Reviewer

Дата: 12 сентября 2026. Проверен второй реальный проект — vblf, с другим
механизмом дефекта: потеря хвоста буфера при записи контейнера. Это уже известный
учебный дефект с ранее созданными ассистентом диагностическим тестом и оператором.
Проверен перенос нового механизма приёмки, а не независимость ремонта или балл 9.7.

## Что обнаружено в предыдущей реализации

1. `native_failure_acceptance.v1` не публиковал `status=ready`. На vblf Reviewer
   правильно остановил допуск с `executable_acceptance_ready=false`, несмотря
   на полный packet и готовый repair delta. Добавлен статус, обусловленный
   полнотой packet, source hashes и replay obligations; проверка Reviewer сохранена.
2. `ProjectDevelopmentExperiment` разрешал зелёной native suite перекрыть отказ
   executor/acceptance. Reassessment использовал похожие альтернативы и мог
   выдать validated для проваленного experiment. Отрицательный baseline дал
   **11 failed / 1 passed**: `artifacts/verification/transfer_gate_baseline_20260912.xml`.
   Исправлены обязательность отдельных результатов, точное покрытие native целей
   и запрет восстановления failed experiment в validated.
3. Planning Reviewer видел планы до исполнения, но завершающий Reviewer не был
   обязательным шагом перед reassessment. Новый `project_development_review.py`
   передаёт реальные TestResult и native verification, сохраняет финальное решение
   и блокирует валидацию при request_rework. Его verdict детерминированный и не
   является независимым judge для сертификации.

Эти пропуски относятся и к моей предыдущей работе: 508 зелёных тестов прошлого
этапа не доказывали совместимость нового формата со всеми потребителями и
сохранение его условий допуска до конца цепочки. Перенос на другой проект и
контроль с зелёными тестами, но нарушенным evidence, выявили конкретные пробелы.
Предыдущие receipts сохранены; их успешность не расширяется задним числом.

## Результат vblf

Источник: `artifacts/self_development/vblf_buffer_training_20260910/baseline`.
Перед копированием его digest совпал с предыдущим training receipt. Работа шла
в новой копии; upstream fix не использовался, изменений в baseline нет.

`artifacts/causal_trials/vblf_native_transfer_20260912/` содержит:

- `intake.json`: два свежих падения исходного native-теста с plain assertions,
  точный target `src/blf/writer.py:BlfWriter._flush_container`.
- `execution.json`: первая попытка `controlled_stop`, Reviewer не получил readiness.
- `execution_v2.json`: после readiness — `experiment_validated`, полная suite 44/44.
- `execution_v3.json` и `execution_v4.json`: добавлены финальный Reviewer и проверка
  inventory после регрессии; итоговый v4 — **experiment_validated**, acceptance
  passed, native suite **44 passed**, Reviewer **approve**. Встроенные COS/source
  inventories фиксируют версию каждого исполнения, изменения между попытками явны.
- `controls_v4.json`: после подмены теста в копии native suite всё ещё **44 passed**,
  но acceptance failed, experiment failed, reassessment not_validated,
  memory not_promoted. Отдельный вариант со старым зелёным TestResult также получил
  request_rework из-за изменённого inventory. Оригинальная patch-копия сохранена.

Этот повтор использует уже существующий buffer-tail operator. Его перенос на
новое семейство дефектов не доказан. Сопоставление RPC и vblf подтверждает работу
native acceptance на двух потреблённых проектах, с разными состояниями и ремонтом.

## Контракт окончательного допуска

Новый `native_test_result.json` дополняет исходный executor TestResult полной
native verification и сравнением inventory после регрессии; ссылка на исходный
TestResult сохранена. `final_review.json` содержит самостоятельное итоговое решение.
Доступ к исходному проекту остаётся без source apply.

Reviewer сверяет digest TestPlan и acceptance result, format, цели, все paired
checks и положительный replay count. Для review после исполнения также нужны
targeted/native regression passed и совпадение принятого/current inventory digest.
Отказ завершающего Reviewer блокирует experiment и validated memory. Самостоятельная
targeted acceptance не утверждает полноту regression. Planning review без TestResult
допускается как подготовка плана; оно не является итоговым разрешением ремонта.

Проверки выполняются на доверенном коде в subprocess-копиях. Они подтверждают
согласованность файлов и результатов в выбранном окружении, не защищают от
произвольного кода с правами host и не создают независимость self-declared judge.
Private/config.json и generated artifacts по-прежнему вне source inventory.

## Проверки COS и ограничения

- Расширенная регрессия до финальных уточнений digest: **153 passed**,
  `artifacts/verification/transfer_regression_20260912.xml`.
- Финальные gates: **35 passed**,
  `artifacts/verification/transfer_final_gates_20260912.xml`.
- Linux: **92 passed**, `artifacts/verification/linux_transfer_20260912.xml`.
- Итоговый source snapshot, выбранный полный scope этого этапа, 400-line gate и
  handoff: `artifacts/verification/development_stage_transfer_20260912.json`.

Полный RPC-suite не запускался повторно: bounded loopback probes снова не прошли
в Windows CPython 3.13 и WSL CPython 3.10. Receipts:
`artifacts/verification/transfer_loopback_windows_20260912.json` и
`artifacts/verification/transfer_loopback_linux_20260912.json`.
TCP integration и общий CI требуют рабочего runner. Временные файлы Linux-регрессии
создавались в `/var/tmp`, учитывая ранее найденную проблему pytest fd-capture на `/mnt/f`.

Следующий рабочий шаг — новые development cases с сохранением первой попытки,
исходников, interventions и отказов, затем независимый CLI/library holdout.
Баллы, promotion policy и требования независимости не изменены. В этих повторах
не было обращений к шлюзу DeepSeek/GigaChat; это не утверждение нулевых расходов
на работу самого ассистента.
