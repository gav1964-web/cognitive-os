# Четвёртый пакет: пять шагов к 9.7+

14 сентября 2026. Предел — пять заранее записанных шагов либо подтверждённые
независимые 9.7+. Результат: принятых ремонтов нет; лимит пяти шагов исчерпан.
Источник измерения — один уже использованный assisted development case markdownify,
а не новый holdout. Прежние role scores и исходный проект не изменены.

## Выполненные шаги

1. Добавлены `runtime/repair_observation_probe.py` и `repair_observations.py`:
   отдельные source-derived equality probes для каждого прямого assertion,
   по два запуска в свежем процессе и копии. Захватываются только явно названные
   аргументы, ограниченные встроенные значения, достигнутые строки и возвраты.
   В настоящем случае `parent_tags` — set; обычный и backslash контексты проходят,
   heading и table теряют пробел на раннем возврате. Всего восемь диагностик.
2. `runtime/repair_diagnostic_context.py` повторно проверяет и передаёт до трёх
   сохранённых native comparisons вместе с точными replacement functions и
   явно обозначенными суффиксами native output. Полные receipts сохраняются.
   Новый API core: `repair_observations`, `repair_counterexample_history`;
   только authorized model trial, без новых обязательных полей ответа модели.
3. Выполнен заранее ограниченный paired pilot: два вызова на режим, максимум
   четыре, format/semantic retries = 0. Исходники COS, исходный проект, модель,
   история трёх ошибок и system prompt одинаковы. Машинная проверка подтвердила,
   что hypothesis input отличается только observations. В обоих режимах prompt
   сохраняет bodies target, observed API и direct callers; остальные методы
   представлены identities/locations, полный nomination packet остаётся в receipt.
4. Проверены native suite и отказ delivery admission. Без наблюдений кандидат
   оставляет ранний empty return перед heading fix. С наблюдениями heading
   исправлен, но table возвращает пустую строку. Оба не допущены; финальный
   Reviewer реального ремонта не запускался. Положительная полная цепочка и
   отрицательные admission cases проверены отдельными scripted regression tests.
5. Сохранены utility/readiness audit, текущий план, очередь, source-bound решения
   и финальный stage handoff с регрессией и обязательным 400-line gate.

## Результат и затраты

| Режим | Вызовы | Reported tokens | Полная native suite | Первый провал |
|---|---:|---:|---|---|
| Исходный проект | 0 | 0 | 80 passed / 1 failed | heading A003 |
| Без observations | 2 | 12 937 | 80 passed / 1 failed | heading A003 |
| С observations | 2 | 14 125 | 80 passed / 1 failed | table A004 |

Итого четыре DeepSeek вызова, 27 062 reported tokens; gateway сообщил cache miss
и отсутствие fallback во всех четырёх. Это не счета и не независимое подтверждение
провайдера. Наблюдения добавили 1188 reported tokens (+9.18%) относительно контроля.
Есть локальный сдвиг до следующего assertion, но accepted repairs остаётся 0/1
в каждом режиме. Одного последовательного запуска на уже использованном случае
недостаточно для причинного вывода о пользе или обобщения на другие проекты.

Конкретный следующий пробел первых трёх ролей: Architect в режиме observations
написал для A004 «returning an empty string» при видимом expected ` foo bar |`
и фактическом ` foobar |`. Полнота списка объяснений не означает согласованности
дизайна с требованием. Следующий этап должен сначала воспроизвести эту потерю
смысла из сохранённых inputs/outputs и проверить дешёвую обратную сверку дизайна
с исходными assertions; не расширять schemas и paid loops без измеримого критерия.
Сопоставление с прямым агентом и свежий независимый CLI/library holdout остаются
отдельными задачами. Map по просьбе пользователя отложен.

## Границы доказательств

Диагностики исполняют выражения отдельных равенств после pytest collection,
не исходное тело теста с fixture/setup/sequence semantics. Поддерживаются только
обычные zero-argument, undecorated, fixture-free функции с прямыми assertions,
до восьми равенств, два повтора каждого. Это доверенный код, не hostile-code sandbox.
Они не заменяют native suite и не дают execution/promotion authority. Повторная
валидация проверяет текущие source/probe hashes, requests, outputs и копии.
Opaque значения не раскрываются через пользовательский repr/итерацию.

Ручное участие: ассистент реализовал probes/history/projection и составил paired
протокол. Case уже consumed; ранее ассистент видел reference. Reference/oracle и
ручной patch модели не передавались. Между режимами код и настройки не менялись,
ручных исправлений ответов, retries и дополнительных модельных запросов не было.
Малый scripted repair подтверждает работоспособность цепочки, не качество LLM.

## Receipts

- `artifacts/causal_trials/five_steps_batch4_20260914/progress.json`: шаги и бюджет.
- Там же `observations/result.json`, `history.json`, `model_trial/*_result.json`,
  `*_transcript.json`, `*_telemetry.json`, `*_source_check.json`: исходные evidence.
- Там же `native_review.json`, `accounting.json`, `readiness.json`: исходы и пределы.
- `artifacts/verification/five_steps_batch4_01_02_20260914.xml`: 23 passed.
- `artifacts/verification/five_steps_batch4_04_20260914.xml`: 40 passed, admission regression.
- `artifacts/verification/development_stage_five_steps_batch4_20260914.json`:
  итоговая регрессия точного snapshot и size gate; статус проверяется в receipt.
- `artifacts/verification/five_steps_batch4_final_audit_20260914.json`:
  итоговые counts, hashes, decisions, бюджет и остановка после пяти шагов.

Первый ручной запуск admission tests остановился до collection из-за повторной
регистрации pytest_asyncio. Повтор с отключённым plugin autoload использует явный
plugin, как штатный stage runner. Ошибка запуска не скрыта и не является тестом продукта.
