# Research: корпус, обучение и оценка

[Карта append mapping](append_mapping_owner_20260915.md) отделяет boundary KB
извлечения helper из append-цикла от ремонта поиска по mapping path. Профиль и
контраст принадлежат новому плагину; field trial/evidence остаются в Research.
Staged-статусы и прежние provenance не повышаются регистрацией.

[Pickle promotion preparation](pickle_promotion_20260915.md): owner 0.4.0
готовит и валидирует документ через read-only `prepare_promotion`; governance
сохраняет девять guards, atomic write и reload. `prepared` не разрешает запись.
Независимая оценка и registry refresh остаются отдельными действиями.

[Контракты pickle-каталогов](pickle_catalogs_20260915.md): application и blocker
intelligence читают явные исследовательские документы через registered validator.
Отсутствие документа не заменяется установленной активной KB; config doctor
использует отдельный installed-read API. Promotion и outer evidence gates прежние.

[Подбор pickle-образцов](pickle_samples_20260915.md): правила и source analysis
принадлежат плагину 0.2.0, девять потребителей используют
`runtime.exception_pickle_sample_contract`. Чтение файлов, materialization,
semantic replay и независимая оценка остаются в Research / Replay.
Classifier больше не получает sample helper через shadow-исполнение.

[Карта оставшихся pickle-потребителей](pickle_consumers_20260915.md) отделяет
контракт предложений от research catalog, sample inference, replay и promotion.
Три потребителя патча уже используют registry; чтение явного экспериментального
каталога и полномочия promotion пока сохраняют прежние API и guards.

Назначение: находить пригодные задачи, учитывать exposure, получать обучающие
данные и независимо измерять способности/продуктовый эффект.

Проверка narrow certification заново вычисляет допуск по ledger, привязанной
оценке и текущей policy. `runtime/narrow_type_evidence_binding.py` задаёт общий
digest и числовую проверку; без evidence root или bindings сертификат не
авторизует новые эксперименты. Исторические v2 сохраняются для переоценки.
Негативные controls и границы доверия — в
[role_97_progress_20260912](role_97_progress_20260912.md).

Начинать с `runtime/local_historical_defect_mining.py`,
`runtime/historical_defect_qualification.py`, `runtime/three_route_evaluation.py`.
Политики: `config/local_historical_defect_mining.json`,
`evaluation/protocol_v2_manifest.json`; протокол — `evaluation/PROTOCOL_V2.md`.
Загрузка и проверка mining policy вынесены в
`runtime/local_historical_defect_policy.py`; прежний mining-модуль сохраняет
совместимые imports. Это внутренняя граница ответственности, без нового пакета.

`HypothesisValidationPlan` связывает post-training admission с проверкой
как минимум одного newly discovered match; large blind corpora remain release/calibration.
Полный действующий протокол: [SELF_IMPROVEMENT.md](../../SELF_IMPROVEMENT.md).
`SelfDevelopmentChangeProposal` учитывает границы L0-L4; unknown target kind
не получает автоматического допуска. Проспективный сбор остаётся в
`waiting_for_evidence`, пока требуемое независимое доказательство не получено.

Зависимости: Replay для исполнения одного известного дефекта, Roles для решения
задач, Evidence для связывания inputs/results. Наличие корпуса не означает его
семантическую пригодность. `runtime/library_admission.py` допускает кандидатов
по метаданным пакета, исходникам API и вызывающим их тестам. CLI:
`python tools/library_admission.py --project PATH --output REPORT.json`.
Анализ статический и ограниченный; ошибки чтения/синтаксиса и усечение закрывают
допуск. README и имя проекта не заменяют код. Receipt содержит хеши прочитанных
файлов и ограничения: это кандидат, а не доказательство чистоты функций.
SDK и приложения с функциями преобразования требуют проверки конкретного случая;
независимость forks и пригодность исторического baseline отдельно проверяет evaluator.
Если исторический commit меняет только общую test fixture, mining выбирает
ограниченный набор настоящих pytest-модулей из baseline. Изменённые данные и
запускаемые тесты хранятся раздельно; отсутствие воспроизведения закрывает допуск.

Проверки: mining, qualification и three_route_evaluation. Не передавать sealed
oracle решающей роли до завершения её независимой попытки. Не возвращать
потреблённый обучающий случай в fresh holdout. Receipt связывать с исходным
manifest, окружением и точным результатом проверки.

В [отборе второго проекта](second_project_intake_20260913.md) mining дополнен
поддержкой корневого `test.py` и отделением `*_test.py` от production delta.
Тест-only изменение не получает допуск как production fix. Историческая пара
не гарантирует воспроизведение: первый markdownify case прошёл тесты без ремонта,
второй стабильно падает и остаётся unbound через тестовый helper. Проверка:
`tests/runtime/test_historical_root_tests.py`. Отбор и lineage-проверки ограничены
явно указанными metadata/history; достаточность всего корпуса не утверждается.

Готовность входов проверяет `runtime/evaluation_input_readiness.py`:
`python tools/three_route_evaluation.py readiness`. Хеш описания проекта не
заменяет хеш исходников. Для анализа/документации/изменения проекта нужен
`project_tree`; для генерации допустим один prompt с явными ограничениями и
критериями успеха. CLI status/bundle блокируют сравнение при неполных входах.
Это не проверка качества исполнителей и не результат независимого сравнения.

Подготовленные 12 сентября входы и точные хеши выбранных файлов перечислены в
`evaluation/prepared_inputs_20260912.json`. Снимки находятся локально в
`artifacts/evaluation_inputs/20260912`; это ограниченные выборки с явно указанными
исключениями. Прежние определения сохранены в `evaluation/history/inputs_before_20260912`.
`runtime/evaluation_input_snapshot.py` копирует явно выбранные файлы, отклоняет
приватные пути и ссылки и не перезаписывает существующий снимок.
У абляций `supporting_input` связывает workload с хешем отдельной реализации COS;
readiness повторно проверяет оба дерева. Удаление локальных снимков снова блокирует
готовность; одного Git checkout без этих входов недостаточно.

`runtime/evaluation_evidence.py` проверяет конечные числовые метрики, реальные
файлы артефактов и журнал моделей. API bundle/status/score требуют `artifact_root`;
CLI использует корень проекта. Ключ слепого пакета связывает manifest, политику и
receipts; scoring повторно проверяет файлы. Старые записи без журнала остаются
историей и не получают новый допуск. Подробный контракт — в PROTOCOL_V2.md.

Артефакты читать по ссылке из текущего статуса. Не включать весь corpus или
sealed receipts в обычный context bundle. Fresh holdout и same-task three-route
сравнение остаются отдельными обязательствами при соответствующих утверждениях.

Реальные task15 executors запускает `tools/run_evaluation_routes.py`: direct
workspace agent, greenfield plan + agent, native full role pipeline. Общие проверки
и учёт запросов — `runtime/evaluation_route_execution.py`, связывание маршрутов —
`runtime/evaluation_route_adapters.py`. Исполнитель пока поддерживает одну задачу.
`--model-route backup` фиксирует резервную модель только для эксперимента.
Неполные evidence сохраняются как drafts и не допускаются в v2 автоматически.
Результаты, ограничения и ошибки первого harness:
[route_trial_20260912](route_trial_20260912.md).

Следующий этап изменил task15 full adapter на явный native greenfield delivery.
Поддержанный uppercase-пакет доставлен с 6/6 acceptance без LLM-вызовов; это другой
executor (`native_greenfield_bounded_delivery.v1`) и всё ещё не допустимая v2 тройка.
Исторические попытки сохранены. См. [greenfield_delivery_20260912](greenfield_delivery_20260912.md).
