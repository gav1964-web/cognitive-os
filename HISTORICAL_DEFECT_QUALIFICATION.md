# Historical defect qualification v2

Qualification проверяет, что выбранный исторический дефект воспроизводится
на baseline, а upstream production patch исправляет тот же сбой. Это подготовка
evidence для дальнейшей оценки ролей; она не является ролевым holdout.

## Условия qualification

- Публичный manifest и отдельный oracle сохраняют проверяемые digest и связь
  по candidate ID. Environment bundle дополнительно связан с digest manifest.
- Для каждого case создаётся отдельное venv без системных и пользовательских
  site-packages. Устанавливаются только локальные wheel-файлы из профиля.
  Их версии, SHA-256, Python version и итоговый inventory проверяются;
  `pip check` подтверждает полноту обязательных зависимостей.
- Исторический проект не устанавливается как готовый пакет из wheelhouse.
  Bootstrap добавляет baseline source и его `src/` в import path, а локальная
  distribution metadata создаётся внутри sandbox. Сложные build hooks и native
  extensions самого исследуемого проекта этим bootstrap не воспроизводятся.
- Внешние pytest plugins не загружаются автоматически. Нужные plugins явно
  перечисляются при freeze через `--pytest-plugin`; их wheels входят в профиль.
- Один и тот же набор тестов выполняется дважды на baseline. Нужны одинаковые
  collected node IDs, упавшие node IDs и failure signature. После production patch
  collection должна сохраниться, все исходно упавшие nodes должны пройти,
  а выбранный test suite должен закончиться успешно. Skip, xfail, исчезнувший
  тест, collection/setup/teardown error не заменяют прохождение исходного теста.
- Structured JSON пишет отдельный pytest plugin. Отсутствующий, повреждённый
  или противоречивый report блокирует qualification. Текст `N passed` в stdout
  не имеет самостоятельной доказательной силы.
- Каждый subprocess имеет deadline из `--timeout`; это лимит одного процесса,
  а не всей кампании. Для Windows общий native-failure runner использует
  [Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects):
  доверенный bootstrap ждёт назначения job до старта команды. Таймаут и закрытие
  job завершают дочерние процессы. POSIX использует существующую process-group ветку.
- Source HEAD, worktree и реестр worktree сравниваются до и после case.
  Venv, временные результаты и sandbox удаляются; публичный и sealed receipts
  сохраняются отдельно. Worktree/venv изоляция не заменяет изоляцию ОС.

Новые receipts имеют схемы `historical_defect_qualification_receipt.v2` и
`historical_defect_qualification_oracle_receipt.v2`. Исторический v1 receipt
не доказывает выполнение этих дополнительных условий.

## Воспроизведение

1. Подготовить локальный corpus eligibility index. Его путь можно явно передать
   в mining, сохранив остальные правила отбора:

```text
python tools/self_development_corpus_eligibility.py --root . --write
python tools/local_historical_defect_mining.py --root . --corpus-index <eligibility-index.json> --write
python tools/local_historical_defect_mining.py --root . --project-type library_pure_transform --scan-limit 10000 --write
```

Mining выдаёт пути к публичному manifest и отдельному sealed oracle. Следующие
команды используют эту пару; oracle не передаётся ролевому evaluator до фиксации outcome.
`--project-type` ограничивает отбор и предложения загрузки выбранным типом;
общая готовность по-прежнему требует два case каждого типа. `--scan-limit`
допускает 1..10000 локальных проектов. Оба параметра сохраняются в manifest.

2. Подготовить wheelhouse для выбранного Python/платформы. Для уже измеренного
   Rosbags сохранён lock CPython 3.10.11 / Windows amd64:

```text
python -m pip download --only-binary=:all: --require-hashes --no-cache-dir -r config/historical_defect_environments/rosbags_cp310_win_amd64.lock --dest artifacts/qualification_wheels/rosbags
```

Этот шаг загружает пакеты. Сам qualification runner использует только готовые
локальные wheels с `--no-index --no-deps`, проверяет их хеши и не расширяет профиль.
Другой Python или платформа требуют собственного набора wheels и нового freeze.
Runner использует Python, которым запущен CLI; подмена интерпретатора не выполняется.

Для Granny подготовлен отдельный controller в `artifacts/tooling/qualification313`.
Использован uv 0.12.12 и CPython 3.13.15 из python-build-standalone. Параметры
установки локального interpreter описаны в [документации uv](https://docs.astral.sh/uv/reference/cli/#uv-python-install):

```powershell
python -m pip install --only-binary=:all: --no-cache-dir --target artifacts/tooling/uv uv==0.12.12
& .\artifacts\tooling\uv\bin\uv.exe python install 3.13.15 --install-dir artifacts/tooling/python --no-bin --no-registry --no-cache --no-config
& .\artifacts\tooling\python\cpython-3.13.15-windows-x86_64-none\python.exe -m venv artifacts/tooling/qualification313
& .\artifacts\tooling\qualification313\Scripts\python.exe -m pip install --no-cache-dir packaging==26.3
& .\artifacts\tooling\qualification313\Scripts\python.exe -m pip download --only-binary=:all: --require-hashes --no-cache-dir -r config/historical_defect_environments/granny_cp313_win_amd64.lock --dest artifacts/qualification_wheels/granny_cp313
& .\artifacts\tooling\qualification313\Scripts\python.exe -m pip download --only-binary=:all: --require-hashes --no-cache-dir -r config/historical_defect_environments/rosbags_cp313_win_amd64.lock --dest artifacts/qualification_wheels/rosbags_cp313
```

Оба CPython 3.13 lock-файла проверены повторным `pip download --no-index
--require-hashes` из локальных wheelhouse. В bundle каждой case назначен свой
профиль: Granny — 27 wheels, Rosbags — 12. Для freeze и qualification этого bundle
нужно запускать CLI через `artifacts/tooling/qualification313/Scripts/python.exe`.
Несколько профилей можно собрать через `freeze_environment_profile` и
`evidence_digest`; структура bundle показана в сохранённом JSON. Старый профиль
CPython 3.10 несовместим с controller 3.13 и остаётся отдельным артефактом.

3. Зафиксировать environment bundle. По умолчанию профиль назначается всем cases
   manifest. `--candidate-id` позволяет явно выбрать подмножество; case без профиля
   останется `environment_blocked`.

```text
python tools/historical_defect_environment.py --root . --public <public-manifest.json> --wheelhouse artifacts/qualification_wheels/rosbags --output artifacts/self_development/historical_defect_mining/environments.json
```

4. Запустить qualification:

```text
python tools/historical_defect_qualification.py --root . --public <public-manifest.json> --oracle <sealed-oracle.json> --environments artifacts/self_development/historical_defect_mining/environments.json --timeout 120 --write
```

Код завершения `0` означает готовность набора: минимум два qualified cases на
каждый узкий тип и все проверки сохранности/окружения. Код `2` означает нехватку
доказательств; успешные и заблокированные cases при этом сохранены в receipt.

## Измеренный результат 10 сентября 2026

Использована прежняя frozen-пара от `20260909T233800263067Z`, без повторного
объявления выбранных проектов новыми. На Python 3.10 Rosbags прошёл qualification,
Granny был заблокирован требованием Python ≥3.13. Повторный запуск обоих cases
на локальном CPython **3.13.15** снял блокировку. Новый environment bundle:
`artifacts/self_development/historical_defect_mining/environments_cp313_20260910.json`.
Его digest — `sha256:e46afa477f2779c99d114cb06b8368afcd18e63a1713785cfe9511b81c8d0881`.
Итоговый публичный v2 receipt:
`artifacts/self_development/historical_defect_mining/public_manifest_20260910T055018172748Z.json`.

| Case | Результат |
| --- | --- |
| `ternaris__rosbags` | `qualified`: дважды 1 failed / 22 passed на baseline; 23 passed после fix; все четыре comparison checks проходят |
| `martin-wieser__granny` | `qualified`: дважды 2 failed / 4 passed на baseline; 6 passed после fix; все четыре comparison checks проходят |

Оба source-проекта и их worktree registries сохранены, sandbox cleanup завершён.
Счётчик frozen strata: **CLI 2 / library 0**, environment blockers — **0**. Общий статус остаётся
`insufficient_qualified_defects`; роли, source apply и KB promotion не запускались.

Изменённый контур и соседние native-intake проверки прошли **111 тестов**.
Отдельный чистый экспорт отслеживаемых и новых исходников без прежних `artifacts/`
прошёл **64 теста qualification**, без ошибок и пропусков. Совпадение 1691 Python-файла
с рабочей копией проверено по SHA-256; JSON и JUnit отчёты находятся в
`artifacts/verification/qualification_clean_export.json` и
`artifacts/verification/qualification_clean_export.xml`.

Полная проверка v2 до последующего изменения mining: **2961 core tests passed**, **183 plugin tests passed**,
все **6/6** этапов canonical verify проходят. Есть одно прежнее предупреждение
о повторном импорте NumPy. Отчёт — `artifacts/verification/canonical_latest.json`.

После исправления границ слов в исключениях mining (`gui` больше не совпадает
с `guide`/`guidelines`) и добавления параметров поиска выполнены **72 теста** всего
затронутого контура, **4/4** структурных проверок и проверки отклонения
`--scan-limit 0` / `10001` до чтения корпуса. JUnit:
`artifacts/verification/qualification_progress_20260910.xml`.
Полный canonical test suite после этого небольшого изменения mining не повторялся.

## Проверка оставшегося библиотечного корпуса

Отдельный поиск с `--project-type library_pure_transform --scan-limit 10000`
обошёл все **1858** незатронутых и незарезервированных проектов исходного индекса.
Публичный manifest:
`artifacts/self_development/historical_defect_mining/public_manifest_20260910T060200773775Z.json`.
В нём нет новых cases; прежние CLI cases сохраняют свои исходные идентификаторы.

| Результат проверки | Количество |
| --- | ---: |
| Доступные Git-репозитории | 1576 |
| Нет Git metadata / snapshot недоступен | 280 / 2 |
| Dirty worktree | 80 |
| Тип не подходит / относится к CLI | 1390 / 92 |
| Предварительно отнесены к библиотекам | 14 |
| Есть история, но нет подходящего production + test fix | 4 |
| История содержит менее двух коммитов | 10 |
| Найденные библиотечные дефекты | **0** |

Дополнительный аудит описаний, packaging и test files сохранён в
`artifacts/self_development/historical_defect_mining/library_identity_audit_20260910.json`.
У всех шести предложенных для history acquisition проектов отсутствуют packaging
manifest и Python test files. Среди них приложения для сбора данных, web app и
проекты с шаблонным GitLab README. У других четырёх одно-коммитных проектов также
нет packaging manifest и тестов. Эти предложения не использованы как доказательство
наличия библиотек или готовности набора; дополнительный fetch не выполнялся.

Ограничение классификатора остаётся явным: слова в README и имени проекта дают
предварительную категорию, но не доказывают наличие библиотечного API с чистым
преобразованием данных. Следующий этап — проверяемый допуск по package/API/test
evidence, затем точечное пополнение корпуса независимыми библиотеками и новый
freeze baseline/oracle до исполнения. Нулевой результат относится к текущему
индексу и правилам, а не доказывает отсутствие любых дефектов в этих проектах.
