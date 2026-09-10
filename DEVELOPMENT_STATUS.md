# Cognitive OS: текущее состояние

Обновлено 10 сентября 2026. Это текущий индекс возможностей, ограничений,
проверок и следующих задач. Подробные прошлые прогоны — в
[истории](docs/history/README.md); устройство исходников — в
[карте проекта](PROJECT_MAP.md).

## Структура и зрелость

- Платформа в целом — research preview. Преимущество над прямым агентом пока
  не подтверждено независимым same-task сравнением по протоколу v2.
- Inspect и Replay выделены в устанавливаемые alpha-пакеты внутри monorepo.
  Их исходники находятся в `packages/*/src/`, старые imports/entrypoints сохранены
  адаптерами. Mining, role scoring и multi-case admission остаются в COS.
- Execution, Evidence, Roles и Research имеют описанные границы и точки входа,
  но пока сохраняют прежнее расположение исходников. Циклы native-failure intake
  не считаются устранёнными этим изменением.
- Карта и генератор контекста помогают выбрать относящиеся к задаче файлы.
  Эффект на скорость понимания/качество исправлений пока не измерен.

## Что действительно подтверждено

Последняя независимая semantic-проверка новых дефектов (8 сентября):

| Роль | Балл |
|---|---:|
| Project Analyzer | 8.0 |
| Architect | 5.0 |
| SpecWriter | 6.0 |
| Implementer | 4.0 |
| Tester | 0.0 |
| Reviewer | 2.0 |

Это результаты трёх случаев Rich, Click и pytest-httpserver; Tester 0 означает
отсутствие подтверждённого исправления в этом holdout. Здесь нет роли 9.7+.
Обучающий replay и старые структурные оценки не заменяют эти результаты.
Источник: `config/narrow_type_transfer_results_20260908.json`; подробности и
исторические таблицы — [ROLE_PROJECT_SCORE_REPORT](ROLE_PROJECT_SCORE_REPORT.md).

Readiness, role-by-project-type maturity, and production confidence — разные
оси измерения. Техническая готовность контура не заменяет независимую оценку ролей
или производственной надёжности.

Qualification известных upstream fixes: **CLI 2 / library 0**. Granny и Rosbags
подтверждены на локальном CPython 3.13.15 с frozen wheels. Требование двух случаев
каждого типа не выполнено; новые ролевые баллы из этих replay не получены.
Receipt: `artifacts/self_development/historical_defect_mining/public_manifest_20260910T055018172748Z.json`.
Поиск всех 1858 оставшихся eligible snapshots не дал пригодных библиотечных
дефектов в рамках текущих правил. Это ограничение корпуса/допуска, а не доказанное
отсутствие дефектов во всех этих проектах.

## Проверки структурного изменения

Установка каждого пакета проверена в отдельном чистом venv на Windows:

| Python | Inspect | Replay | Импорты из исходного COS |
|---|---:|---:|---:|
| 3.10.11 | 27 passed | 25 passed | 0 |
| 3.13.15 | 27 passed | 25 passed | 0 |

Каждый wheel собран из sdist. Проверены frozen environment, pytest reporting
resource, настоящий Git replay, не исправляющий патч и process lifecycle.
Receipts: `artifacts/verification/subprojects/7adb13a4/report.json` (3.10) и
`artifacts/verification/subprojects/63354c6f/report.json` (3.13).
Структурный preflight — **5/5**, Config Doctor — **48/48**. Все 14 проверенных
документов навигации имеют существующие локальные ссылки. В CI добавлена матрица
Windows/Linux × 3.10/3.13; удалённый CI в этой рабочей сессии не запускался.

Полный canonical-прогон: **2969 core passed / 11 failed**, **52 package passed**,
**183 plugin passed**. Все 11 ошибок относились к перемещённым документационным
контрактам и старому пути исходника сканера в тесте ремонта. После исправления
трёх затронутых тестовых файлов повторная группа — **21 passed**, включая все
исходно упавшие случаи. Последующий структурный preflight — **5/5**.
Известных неустранённых ошибок этого прогона нет; полная suite после локальных
исправлений повторно не запускалась. Одно прежнее предупреждение NumPy сохраняется.
Сводный receipt с соответствием каждого failure успешному повтору:
`artifacts/verification/modularization_verification_20260910.json`.
Первичный полный результат сохранён в
`artifacts/verification/canonical_modularization_initial_20260910.json`;
`canonical_latest.json` остаётся его неизменённой записью, а не сводным вердиктом.

Прошлые 2961 core + 183 plugin tests, 72 qualification tests и 86 tests изолированных
копий относятся к состоянию до выделения пакетов. Прежний canonical receipt
сохранён как `artifacts/verification/canonical_before_modularization_20260910.json`.

Для этой рабочей копии подготовлено локальное development-окружение
`artifacts/tooling/modular-dev/Scripts/python.exe`; оно использует доступные
зависимости контроллера и editable-пакеты. Независимые проверки установки выше
проводились в отдельных venv без системных site-packages.

```bash
python tools/project_context.py --check
python tools/canonical_verify.py --root . --write
python tools/verify_subprojects.py
```

## Следующие задачи

1. Собрать пять наблюдений по обычным задачам: время нахождения точки изменения,
   поздние зависимости, повторные правки и результат тестов. Начальная методика —
   в `docs/architecture/README.md`; численного baseline пока нет.
2. Уточнить library admission по package/API/test evidence и получить два
   независимых подходящих библиотечных дефекта.
3. Провести свежую семантическую ролевую оценку, соблюдая exposure/oracle boundary.
4. Для продуктового утверждения выполнить три независимых маршрута и blind scoring
   по `evaluation/PROTOCOL_V2.md`.
5. Выделять следующие пакеты после подтверждения API и независимых потребителей.
   Самостоятельные Git-репозитории пока не требуются.

Изменения разработки подготовлены к фиксации в Git. Публикация пакетов,
применение исправлений к внешнему корпусу и новая сертификация не выполнялись.
