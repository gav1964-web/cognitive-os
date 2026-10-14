# Pickle: подготовка promotion-документа, 15 сентября 2026

Плагин `exception_pickle` версии 0.4.0 владеет предметной сборкой документа
каталога. Решение о допуске и запись остаются в runtime-транзакции.
Это функциональное разделение; рабочая KB не продвигалась и не изменялась.

## Граница ответственности

| Компонент | Ответственность |
|---|---|
| `plugins/exception_pickle/src/promotion.py` | Чистая сборка кандидата по readiness/evaluator/holdout и явному timestamp |
| `prepare_promotion` в зарегистрированном entrypoint | Сборка и существующая owner-валидация; ответ `status: prepared` |
| `runtime/exception_pickle_promotion_contract.py` | Типизированный клиент, проверка результата операции; без fallback и записи |
| `runtime/exception_pickle_promotion_transaction.py` | Прежние девять условий допуска, затем подготовка, сериализация, atomic write и reload |
| CLI / независимые проверки | Получение явного разрешения и результатов checks; прежние аргументы и поведение |

Контракт получает `readiness`, `evaluator`, `holdout` как объекты и
`generated_at` как строку. Путь записи и флаг approval не принимаются.
Плагин не читает evidence-файлы, не запускает оценку и не записывает каталог.
Проверяется его зарегистрированная identity; корень установки и корень
исследовательских inputs/записи могут различаться.

Для сохранения байтов кандидат содержит прежние поля `status: active`,
`activated_at` и `promotion_authority`. До успешной governance-транзакции это
данные подготовленного документа, не свидетельство выполненного promotion.
Оболочка `prepared` явно отличает подготовку от записи. Даже неполные evidence
объекты можно передать чистому builder, как прежде; это не обходит внешние gates.
Новый output-contract запрещает выдавать absent-каталог как подготовленный active.

Транзакция вызывает плагин только после всех условий: explicit approval,
readiness status/review/activation/no-direct-promotion, independent evaluator,
holdout readiness, regression и config doctor. `source_apply` остаётся запрещён.
Обновление registry автоматически не выполняется: запись live KB сделала бы
прежний registry hash неактуальным до отдельного проверенного обновления.

## Сохранение и проверки

AST всех governance-функций, включая checks, сериализацию и atomic writer,
совпадает с исходным. Изменён import функции сборки. Бывшая `_catalog` остаётся
совместимым alias зарегистрированного клиента; алгоритм builder совпадает по AST.
Исходники/hashes сохранены в `artifacts/verification/pickle_promotion_before_20260915.json`.
Два legacy-документа зафиксированы до извлечения в
`tests/fixtures/exception_pickle_promotion_legacy.json`; это development fixtures.

- Фокус: `artifacts/verification/pickle_promotion_focused_20260915.xml` — 25 passed.
  Проверены точные байты, каждый из девяти запретов, отказ admission, небезопасный
  или отсутствующий результат builder и ошибка atomic replace.
- Успешная запись проверена только во временном test root; registry не изменяется.
  При проверенных отказах прежний файл сохраняется. Это не новая гарантия для
  всех возможных ошибок диска или гонок; writer сохранён в прежнем виде.
- Финальный scope и size gate: `artifacts/verification/development_stage_pickle_promotion_20260915.json`.
- Архитектура: `artifacts/verification/pickle_promotion_architecture_20260915.json`.
- Пакеты: `artifacts/verification/pickle_promotion_packages_20260915.log`.
- AST/hash evidence: `artifacts/verification/pickle_promotion_preservation_20260915.json`.
- Актуальность снимка и local-corpus checks: `artifacts/verification/pickle_promotion_final_audit_20260915.json`.

Условия допуска сохранены, включая существующую глубину проверки переданных
результатов. Перенос не превращает их в независимую повторную проверку evidence
и не повышает ролевые оценки. Генератор патчей, samples, активная KB, общий
provider/interpreter и CLI сохранены; LLM-вызовов нет.

## Далее

Основной pickle-пилот теперь охватывает локальную KB, предложения патчей,
sample inference, проверку документов и preparation. Research orchestration,
object-contract classification, independent evaluation и запись намеренно
сохраняют отдельную ответственность; весь pickle research в плагин не перенесён.

Следующий кандидат на карту владельца — оставшиеся `nested_loop_mapping_boundary`
profile/source contrast и механизмы mapping descent. Сначала проверить их
фактическую связь и потребителей; не объединять разные операции по одному имени.
`cross_reducer_ambiguity` и unsupported-shape fallback могут относиться к общему
протоколу, поэтому не переносить их автоматически вместе с предметным знанием.
