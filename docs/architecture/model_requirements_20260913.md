# Явные требования в модельном ремонте, 13 сентября 2026

`run_project_development` теперь принимает `task_contract` в модельном native
маршруте: `validate_causal_proposals=True`, `authorize_training_replay=True`,
явный `llm_hypothesis_config` и `run_sandbox_experiment=True`. Контракт ограничен
одной source-bound defect-целью, существующими native-тестами и объявленными
baseline expectations. Произвольные constraints и general feature delivery
по-прежнему требуют отдельного дизайна.

## Передача и допуск

Analyzer проверяет готовность запроса и совпадение его source/target с failure
packet до вызова модели. Полный нормализованный контракт поступает как в hypothesis,
так и в candidate prompt; списки требований не обрезаются generic prompt compactor.
При превышении 12 000 символов hypothesis envelope запрос отклоняется без вызова
модели. Для таких остановок `model_invoked=False`, счётчик логических вызовов — 0.
Бюджет candidate prompt остаётся 32 000; model transport failover учитывается
существующим inference client отдельно от логических запросов.

Digest контракта входит в advisory, provenance кандидата и delivery ticket.
Требования нельзя задним числом добавить к failure-only предложению. Сравнение
по исходному сбою по-прежнему выбирает только одно поддержанное вмешательство.
Если оно не удовлетворяет requested acceptance, система возвращает запрос на
уточнение; другие варианты автоматически не пробует.

Для проверки требований создаётся новая копия из исходного inventory и точных
байтов ticket, без чтения изменяемой директории прежнего candidate trial.
Существующий `verify_requested_acceptance` проверяет исходные ожидаемые pass/fail,
прохождение всех указанных nodeid после patch, интерфейс и неизменность источников.
Затем ticket дополнительно связывается с request digest и acceptance receipt digest.
До этой проверки trial имеет `model_candidate_request_review_required` и не
утверждает допуск к доставке. Отказ удаляет ticket из текущего issue и его authority.

SpecWriter сохраняет требования, критерии и traceability. Executor проверяет
связанный requested proof и согласованность Spec/Plan; отсутствие comparison,
контракта или requirement не открывает обход через failure-only маршрут.
Reviewer требует те же bindings даже если task_contract удалён из переданного
Spec. Последующие native regression, проверка patched inventory и финальный
Reviewer остаются обязательными.

## Evidence

Synthetic fixture `invert(bool)` сначала возвращает False: проверка False падает,
проверка True проходит. Скриптованный provider получает требования `REPAIR` и
`PRESERVE` в обоих запросах и предлагает инверсию. Requested replay даёт исходные
**1 pass / 1 fail**, затем **2 passed**; полная native suite и финальный Reviewer
проверяются в сквозном тесте. Исходник сохраняется, дополнительных model calls в
executor нет. Содержимое обоих prompts проверяется на точное равенство контракту.

Контроль, возвращающий True для обоих входов, проходит исходный failing node, но
отклоняется requested acceptance до executor. Неверное baseline expectation тоже
блокирует допуск. Отдельно проверены неподдержанный constraint до любых model calls,
удаление контракта/требования, подмена statement, receipt, ticket binding и попытка
добавить требования после генерации. 13 требований передаются в prompt целиком;
слишком большой envelope даёт контролируемый отказ без вызова провайдера.

Это проверка инженерного контура со скриптованным провайдером, не самостоятельный
модельный диагноз и не подтверждение 9.7+. Семантическая достаточность тестов
остаётся caller-supplied. Нового независимого проекта или живой model campaign
на этом этапе нет.

Receipts: `artifacts/verification/model_requirements_v2_20260913.xml`,
`artifacts/verification/model_requirements_v3_20260913.xml`,
`artifacts/verification/development_stage_model_requirements_20260913.json`
(снимок исходников, регрессии и 400-line gate),
`artifacts/verification/canonical_model_requirements_20260913.json`.

## Продолжение

Следующий инженерный шаг — более точное разрешение callers и согласование
дублирующих наблюдений о native failure и заглушке одной цели. Затем новый реальный
development case с сохранением первой попытки до диагноза ассистента. Gateway
usage, стоимость и независимая оценка остаются отдельной очередью.
