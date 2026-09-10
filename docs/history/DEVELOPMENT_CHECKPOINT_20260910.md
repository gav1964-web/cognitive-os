> Исторический снимок до выделения пакетов. Текущий статус: [DEVELOPMENT_STATUS](../../DEVELOPMENT_STATUS.md). Пути в примерах отсчитываются от корня репозитория.

# Cognitive OS: проверка разработки — 10 сентября 2026

Продолжение разработки в тот же день: qualification v2 получил изолированные
wheel-окружения, структурированные результаты pytest, два baseline replay и
проверку прохождения исходно упавших nodes. Исправлено завершение дочерних процессов
в общем Windows native-failure runner. Расширенная регрессия — **111 passed**.
Чистый экспорт исходников без прежнего `artifacts/` прошёл **64/64** теста нового
контура; 1691 Python-файл совпадал с рабочей копией на момент этого прогона. Отчёт проверки экспорта:
`artifacts/verification/qualification_clean_export.json`.
Текущий результат qualification: **CLI 2 / library 0**. Локальный CPython 3.13.15
снял блокировку Granny: два baseline replay дают 2 failed / 4 passed, после
upstream fix проходят 6/6 тестов. Rosbags повторно подтверждён на том же Python.
Оба case имеют отдельные wheel-профили и lock-файлы с SHA-256; environment blockers
больше нет. Receipt — `public_manifest_20260910T055018172748Z.json` в
`artifacts/self_development/historical_defect_mining/`.

В последующем mining исправлено ложное исключение `gui` внутри `guide` и
`guidelines`. Добавлены выбор типа проекта и ограниченный размер локального
сканирования; параметры сохраняются в manifest. Отдельный поиск библиотек
не резервирует дополнительные CLI-кандидаты. Узкие тесты mining — **13 passed**.
Весь затронутый контур после этих изменений — **72 passed** за 132 секунды;
JUnit — `artifacts/verification/qualification_progress_20260910.xml`.
Структурный preflight — **4/4**, включая Config Doctor **48/48** и лимит 400 строк.

Полный поиск библиотек охватил все **1858** оставшихся eligible projects:
**0** подходящих дефектов. Четыре предварительных библиотечных кандидата имеют
историю без подходящего production + test fix; десять имеют только один коммит,
без packaging manifest и Python test files. Аудит показал ложные категории
библиотек у приложений и шаблонных README. Отчёт поиска:
`artifacts/self_development/historical_defect_mining/public_manifest_20260910T060200773775Z.json`.
Следующий этап — проверяемый допуск библиотек по API/package/test evidence
и точечное пополнение корпуса. Два независимых библиотечных дефекта пока не получены.

Полный canonical verify v2 до этих изменений mining завершился: **6/6 этапов**,
**2961 core tests passed** за 19 минут
17 секунд и **183 plugin tests passed**. Осталось одно прежнее предупреждение
о повторном импорте NumPy. Текущий отчёт — `artifacts/verification/canonical_latest.json`.
Команды, ограничения и evidence — в
[HISTORICAL_DEFECT_QUALIFICATION.md](../../HISTORICAL_DEFECT_QUALIFICATION.md).

## Состояние рабочей копии

Исходная точка проверки — `581df1b93` (`Harden fresh holdouts and validate Invoke repair`).
В отслеживаемых файлах изменений не было; обнаружено 37 неотслеживаемых файлов:

- 12 файлов нового контура historical defect mining: пять runtime-модулей,
  три CLI, три тестовых модуля и политика;
- 22 файла `benchmark_corpora/` и один manifest target-scope contrasts;
- архитектурное summary и локальный `config.json`.

Часть новых fixtures уже используется отслеживаемыми тестами и инструментами:
`project_development_boundary_field_trial` и `test_project_target_scope_contrast`.
Поэтому успешная проверка этой рабочей копии сама по себе ещё не подтверждает
воспроизводимость в чистом checkout. Политика historical mining также ссылается
на локальный индекс из игнорируемого `artifacts/`.

## Исправления по результатам ревью

1. Qualification проверяет `oracle_digest`, помимо digest публичного manifest
   и связи между ними. Изменённый или отсутствующий digest блокирует запуск.
2. Дубли `candidate_id`, повторные проекты (включая альтернативные записи одного
   пути) и повторные владельцы внутри типа отклоняются до sandbox. Дубли больше
   не могут увеличить число независимых cases.
3. History acquisition проверяет digest manifest, уникальность типов и разрешённых
   проектов, соответствие strata, независимость владельцев и допустимость origins
   до обращения к Git. Неуспешные или отсутствующие selection checks блокируют
   загрузку. Пути сравниваются после разрешения относительно workspace.
4. После неуспешного fetch исходный Git snapshot читается повторно. Неизменность
   HEAD и worktree больше не объявляется константами; недоступный snapshot
   не считается подтверждением сохранности.
5. Очистка qualification sandbox удаляет только созданный worktree. Глобальный
   `git worktree prune` убран, чтобы сохранить посторонние prunable-записи.
6. Нулевой exit code pytest без пройденных тестов получает `no_tests_executed`,
   а не `passed`; skip-only и xfail-only запуск не подтверждает upstream fix.

Это проверки целостности и корректности evidence. Они не повышают оценки ролей.

## Проверки

- Исходный focused suite: **13 passed**.
- После исправлений: **36 passed**, включая реальные временные Git-репозитории,
  воспроизведение failure/fix и сохранение чужой prunable worktree-записи.
- Структурная проверка итогового Python-кода: **4/4** — Registry Doctor без
  замечаний, Config Doctor **48/48**, лимит 400 строк, compileall.
- Первичная полная каноническая проверка: **6/6 этапов**, **2910 core tests passed**
  за 18 минут 37 секунд и **183 plugin tests passed**. Одно предупреждение —
  повторный импорт NumPy в `test_executable_acceptance_adaptive_samples`.
  Эти числа относятся к первоначальному ревью; актуальный v2-прогон указан выше.

Первичный прогон был начат до исправлений и собирал исходный набор тестов.
На том этапе изменения проверялись отдельным focused suite из 36 тестов и повторным
структурным preflight. После реализации v2 выполнен новый полный прогон итогового кода.

Команды:

```text
python tools/canonical_verify.py --root . --write
python -m pytest tests/runtime/test_historical_defect_qualification.py tests/runtime/test_local_historical_defect_mining.py tests/runtime/test_local_history_acquisition.py -q --basetemp=.pytest-tmp/review-hdm-final2 --tb=short
python tools/canonical_verify.py --root . --skip-tests
```

## Измеренный прогресс и следующий этап

До реализации v2 последний сохранённый qualification receipt от 9 сентября
(`artifacts/self_development/historical_defect_mining/public_manifest_20260909T234113322224Z.json`)
имеет `insufficient_qualified_defects`: два CLI-кандидата проверены, оба
`environment_blocked`, qualified counts **CLI 0 / library 0**. Причины collection
failure — отсутствующие `botocore` и `ruamel`. Эти результаты не являются
свидетельством слабости или улучшения ролей.

Порядок дальнейшей работы:

1. **Qualification runner v2 реализован.** Отдельные venv с проверяемыми wheel-профилями,
   `src/` bootstrap, ограниченные процессы, structured node outcomes и два baseline
   replay подтверждены регрессией. Rosbags и Granny проходят qualification на
   локальном controller Python 3.13.15. Отдельные frozen wheelhouse и lock-файлы
   проверены офлайн; автоматического fallback интерпретатора нет.
2. **Два свежих независимых дефекта на каждый узкий тип.** Сначала использовать
   локальный корпус и измерить нехватку — полный поиск завершён, CLI 2 / library 0.
   Исправить семантический допуск библиотек: приложения и шаблонные README
   не должны становиться основанием для acquisition только по ключевым словам.
   Затем пополнить библиотечный корпус; новые загрузки проводить в пределах
   зафиксированного manifest. Не переименовывать ранее consumed cases в holdout.
   Зафиксировать публичный baseline и отдельный oracle до ролевого прогона.
3. **Ролевой holdout с причинным контрактом.** Провести цепочку Analyzer → Architect
   → SpecWriter → Implementer → Tester → Reviewer, сохранить полные артефакты,
   проверить исходный failure, regression и отсутствие generated stubs.
   Доступ к oracle для оценки результата — после фиксации ролевого outcome.
   До этого unseen scores остаются **8.0 / 5.0 / 6.0 / 4.0 / 0.0 / 2.0**.
4. **Проверка продуктовой ценности по protocol v2.** Получить сопоставимые
   direct/short/full receipts и независимые blind scorecards для 20 product tasks.
   Единичные успешные исправления и contract scores не заменяют эту проверку.

Перед оформлением коммитов fixtures следует включить вместе с использующими их
контрактами, historical mining — отдельным завершённым изменением с тестами.
Локальный `config.json` и датированное архитектурное summary требуют отдельного
решения о назначении; автоматически включать всю рабочую копию в коммит не следует.
