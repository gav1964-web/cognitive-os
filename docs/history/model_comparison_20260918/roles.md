# Roles: анализ и планирование

Проверен [эффект передачи контекста](../../architecture/handoff_measurement_20260918.md).
Кандидаты с прежней гипотезой и по прямому маршруту получили интерфейсы, но
вернули одинаковый неработающий код: оба native-прогона 33 passed, 1 failed,
2 xfailed, без новых регрессий. Repair запрашивает deepseek-chat, описание —
v3.2; независимая идентичность backend не подтверждена.
Адресный ответ о предусловиях противоречив. Полный текст восстановлен из кеша
после тайм-аута: частичное улучшение, основной критерий не выполнен.
Четыре новых запроса: 24 397 известных токенов и один неизвестный расход.
Следующий приоритет — сравнение явно выбранной модели на замороженном запросе
и согласованность выводов описания. Runtime/defaults и баллы ролей не изменены.


Пакет [поведенческих контрактов](../../architecture/behavioral_contracts_20260918.md):
трасса показала, что добавленная ветка прежнего ремонта не исполнялась. Новый
hypothesis→candidate тоже не исправил Toml-sort:33passed/1failed/2xfail,0новых
регрессий. Исправлена потеря сигнатур прямых callees при сокращении контекста;
новый контекст проверен offline, без нового модельного ремонта.
Project-description0.15.0 различает нормальный возврат и заданный успешный статус,
строит opt-in карту вызовов/валидации/обработки ошибок из исходников. Контроли4/4.
Полный baseline получен; вариант с картой превысил240секунд. Парное сравнение
незавершено, default прежний.8attempts,7ответов31909reported tokens,1unknown usage;
повторов нет. Шлюз запущен, баллы ролей не повышены.


Продолжение после исправления ошибки ассистента: [автозапуск шлюза и результаты](../../architecture/gateway_resume_20260918.md).
Штатный запуск был согласован, но пропущен экспериментальным runner; шлюз запущен.
BudgetedChat теперь проверяет/запускает его до учёта inference и проверяет
настроенный предел выхода4096. Ремонт дошёл до модели, но дефект остался:
33passed/1failed/2xfail, новых регрессий нет. Шесть новых claim-контролей6/6.
Полное сравнение Replay выполнено; расширенная инструкция не улучшила текст,
повторила неоднозначность optional profile и потеряла детали. Default прежний.
Девять ответов35741 reported tokens, отдельный422 и старый transport-сбой
сохранены без утверждения нулевого расхода. Баллы ролей не повышены.


Текущий пакет: [причинный ремонт и предусловия API](../../architecture/causal_and_api_20260918.md).
Восемь контролей подтвердили двойную обработку comment-only через header/footer;
место ремонта переноминировано на координатор toml_doc_sorted. Один запрос оборвался
с URLError, кандидата нет; локальный шлюз127.0.0.1:8000 отказал в соединении.
Расход неизвестен, остальные модельные вызовы остановлены. Плагин0.14.0 добавляет
opt-in проверку конкретного вызова с Boolean/None defaults и keyword-only inputs;
шесть свежих авторских offline-контролей совпали с ожиданиями. Полное описание
подготовлено к сравнению, но живое сравнение заблокировано. Баллы не повышены.


[Native repair и property review](../../architecture/native_and_description_20260918.md): по уточнению
владельца оба направления активны. Toml-sort не исправлен (отказ схемы; отдельно
проверенный код дал 6 новых регрессий). Project-description 0.13.0 фиксирует
свойство до модельного ответа и анализирует нормальные возвраты в ограниченном
домене. Контроли 5/5, контракты 6/6; ложная гарантия Replay понижена до uncertain,
но мнение модели осталось неверным. 7 обращений, 23 924 tokens; баллы не повышены.

[Сравнение после аудита](../../architecture/description_comparison_20260918.md): одинаковый контекст
Replay/Inspect, три стратегии, 8 обращений и 57 110 reported tokens. Адресный
review оставил оба текста неизменными; полный не исправил Replay и удалял детали.
На Inspect он убрал неоднозначность области ошибок вместе с полезным CLI-сценарием.
Общего победителя нет. Default прежний; schema/guarantee research отложен.
Ближайшая работа — native repair Toml-sort и проверяемый результат первых трёх
ролей. Рекомендации новых слоёв в старых записях ниже заменены этим решением.

[Связь утверждений с механизмами](../../architecture/mechanism_review_20260918.md): 0.12.0 —
экспериментальный opt-in. Guard не исправил гарантию Replay и уменьшил
число ожидаемых контрольных итогов с 4/5 сырых оценок до 2/5. Две пары
не показали преимущества над прежним review. 9 обращений, 36 989 tokens,
один cache hit. Не включать автоматически; нужны охват всех возвратов
и фиксированная область свойства. Баллы ролей не повышены.

[Условные модели флагов](../../architecture/return_flags_20260917.md): 0.11.0 добавляет
анализ ограниченного Python-фрагмента, граничные примеры и hash-bound
доставку в review. 8 обращений, 47 827 reported tokens, один cached draft.
4/4 простых контролей верны; целевая гарантия Replay всё ещё ошибочна,
несмотря на доступное свидетельство ложных флагов. Нет прироста баллов
или независимой сертификации. Нужна проверка claim/predicate binding
и внутренней непротиворечивости вывода, не очередной одинаковый review.

[Workflow и неверный README](../../architecture/workflow_review_20260917.md):0.10.0 резервирует
запрошенные секции и убирает точные повторы, поддерживает namespace final,
не допускает documentation-only факты в product_context.7 вызовов65687 tokens.
README-контроль полезен, но смысловые ошибки Replay сохраняются даже при
доступном коде; focused review гарантии отклонён ассистентом. Следующий фокус —
контрпримеры к заявленным постусловиям, не увеличение числа одинаковых review.

[Нормализация описания и Replay](../../architecture/description_shape_20260917.md):0.9.0
сохраняет raw и проверяемое происхождение singleton-адаптации. README читается
как документация. Новый текст Replay получен, но не принят по смыслу;
3 обращения,26610 tokens. Длинная функция теряется при последующем отборе,
а review отдельных claims пока проверяет draft, не новые финальные утверждения.

[Контекст helpers](../../architecture/helper_context_20260917.md):0.8.0 сохраняет доступные секции
и читает до шести helpers рядом с caller. Inspect сохранил2/2 потерянных детали;
Replay отклонён до review из-за формы data_flow.4 запроса,48675 tokens,один
черновик из кеша. Общий перенос и рост ролевого качества не подтверждены.

[Границы частей и реальное описание](../../architecture/claim_transfer_20260917.md): v4 сохраняет
raw response и журнал восстановления пробелов. Контрасты4/5 по смыслу,5/5 по
контракту; полное описание Cognitive Inspect полезно, но теряет две детали
из-за контекста helpers.8 запросов,58972 tokens; три роли получили пять
проверенных утверждений и заметки. Следующий приоритет — полнота review.

[Упрощённый review v3 и общий бюджет](../../architecture/claim_review_v3_20260917.md):
10 запросов,13225 reported tokens. Контракт принял4/5 известных и5/5 новых
синтетических случаев; пригодные вердикты совпали с ожиданиями9/9. Один отказ
из-за потерянного пробела, одна неточная оценка bindings. Это не сертификация
ролей. Новые пакеты ниже миллиона токенов разрешены владельцем без пересогласования.

[Запуск серии и читаемый review](../../architecture/claim_obligations_live_20260917.md):
серия5 выполнена,6763 reported tokens; контракт принял0/5, общие вердикты
совпали с ожиданием3/5. Открытая задача отказа передана трём ролям; успешная
передача модельного предложения не проверена. Бюджет закрыт.

[Проверка составных утверждений](../../architecture/claim_obligations_batch_20260917.md):
части исходного текста, контрпримеры, обязательные связи контекста и отдельные
решения рецензента через product_context. Пять новых синтетических случаев
подготовлены offline; улучшение качества модели ещё не измерено.

[Review одного утверждения](../../architecture/description_resolution_batch_20260917.md):
пять запросов завершены,8310 reported tokens; точность цитат5/5 не предотвратила
ошибочное подтверждение универсальности обработчика. Инженерные проверки не
считаются оценкой качества модели.

[Пакет из пяти шагов claim review](../../architecture/description_claim_batch_20260917.md):
карточки доказательств, компактный review, проверки literal_absent, незавершённые
задачи в product_context и offline CLI; новых запросов к модели нет.

[Ограниченный повтор VR/5](../../architecture/description_repeat_20260917.md): шесть обращений,
VR timeout; на5 ошибка review при наличии полного доказательства. Общий рост
качества и экономия не подтверждены, дальнейшие вызовы этой серии остановлены.

[Offline-контекст и полнота review](../../architecture/description_offline_20260917.md): резерв
выбранных файлов, приоритет импортируемых функций и журнал изменений черновика
для следующих ролей; новых обращений к моделям нет.

[Пять шагов описания и handoff](../../architecture/description_campaign_20260917.md): bounded source
lookup и product_context для трёх ролей; реальные прогоны показали ограничения
review. Inspect CLI реализован внешним ассистентом, автономность не заявлена.

[Общая политика описания и VR](../../architecture/project_description_generic_20260917.md):
предметные подсказки удалены из KB, исправлен приоритет src над tools.
Первый прогон отказал; разрешённый повтор с240с дал полезное описание VR
с фактическими замечаниями. Черновик из кеша; эффект timeout не установлен.

[Project description](../../architecture/project_description_20260916.md): отдельная компетенция
описания продукта, пользовательских действий, движения данных и ограничений.
Запуск: `tools/describe_project.py`; source evidence и owner statements разделены.

[Helper recipe reads](../../architecture/helper_recipe_reads_20260916.md): один живой каталог на
выбор вместо четырёх; свежий допуск на следующих кандидатах и verification.

[Text splitting](../../architecture/text_splitting_20260916.md): плагин 0.1.0 завершает перенос
четырёх текущих helper extractors. Runtime сохраняет orchestration/authority,
а самостоятельная разработка COS остаётся отдельным непроверенным результатом.

[JSON parsing](../../architecture/json_parsing_20260916.md): плагин 0.1.0 владеет read_text/loads
helper, recipe и результатом. Recovery/verification сохраняют полномочия,
planning/research recognition и network boundary не перенесены.

[JSON serialization](../../architecture/json_serialization_20260916.md): плагин 0.1.0 владеет recipe,
extractor и metadata/refusal. Координация, authority и research recognition
сохранены; JSON parsing/text splitting остаются отдельными механизмами.

[Общий recovery-контракт](../../architecture/helper_recovery_contract_20260915.md): append mapping 0.4.0
владеет proposal metadata/refusal, runtime — выбором кандидата и применением.
Три шага завершены с сохранением полных legacy packages и алгоритмов.

[Append mapping 0.3.0](../../architecture/append_mapping_recipe_20260915.md) владеет extraction recipe;
рабочий каталог и Config Doctor читают зарегистрированный вклад. Общий выбор
кандидатов, дифференциальная проверка и разрешения применения сохранены.

[Append mapping 0.2.0](../../architecture/append_mapping_extractor_20260915.md) владеет proposal
алгоритмом; recovery/development вызывают registered client с прежними
sandbox/differential gates. Общие AST-функции — в Inspect, recipe пока в policy.

[Append mapping 0.1.0](../../architecture/append_mapping_owner_20260915.md) владеет staged nested-loop
profile/source contrast. Общий interpreter получает их через второй provider без
изменения кода. Исполняющий extractor ещё в runtime; path-descent repair — другая
задача. Составные каталоги и planning/research полномочия сохранены.

[Pickle 0.4.0](../../architecture/pickle_promotion_20260915.md) владеет подготовкой promotion-каталога.
Рабочие полномочия и запись остаются в governance; `prepared` — кандидат,
а не результат выполненного promotion. Source-application ограничения прежние.

[Pickle 0.3.0](../../architecture/pickle_catalogs_20260915.md) отделяет проверку supplied research
catalog от чтения установленной KB. `active` в переданном документе сохраняется
как данные; новый контракт не выдаёт полномочия promotion или source application.

[Sample-контракт pickle 0.2.0](../../architecture/pickle_samples_20260915.md) переносит выбор
дескрипторов и разбор конструктора в компетенцию. Исходник передаётся текстом;
подбор образцов не исполняет код и не подтверждает native-проверку.

[Потребители pickle-контракта](../../architecture/pickle_consumers_20260915.md): authorized
implementation и три research/application потребителя вызывают
`runtime.exception_pickle_contract.propose_exception_pickle_patch` через registry.
Старый programmer alias использует тот же допуск; native и authorization gates
сохранены. Установка компетенции отделена от корня исследуемого проекта.

[Pickle 0.1.1](../../architecture/pickle_state_20260915.md) отклоняет неполный рецепт конструктора
внутри компетенции. Явно покрытые default-параметры сохраняются в round-trip;
полномочия применения и проверки прежние. Разделение функционала оценивается
по контрактам и сохранению поведения; прирост качества проверяется отдельно.

[Pickle-компетенция](../../architecture/pickle_competency_20260915.md) владеет активным каталогом,
boundary profile, source contrast, overlay и генератором патча в
`plugins/exception_pickle/`. Общий интерпретатор получает вклад через
`runtime/competency_knowledge.py`; специальных pickle-веток в нём нет.
Research/application consumers сохраняют прежние полномочия; временный patch
adapter делегирует владельцу. Продуктовые оценки переносом не повышаются.

[Native fixture observations](../../architecture/native_fixture_observations_20260915.md):
`native_repair_observations.collect_native_repair_observations` дважды исполняет
исходные pytest tests и записывает explicitly selected locals и assertion
reachability. Existing diagnostic input принимает `native_test_observations`;
legacy isolated observations сохранены. Native signature и source/receipt
validation обязательны, новых полномочий нет. Toml-sort evidence собрано,
подготовленный запрос не отправлен; реальные оценки не изменены.

[Модельный Toml-sort с внутренним контекстом](../../architecture/toml_internal_model_20260914.md):
existing nomination → derived trial → direct candidate исполнены без изменения
production кода. Все 6 method bodies дошли до prompt, native preflight пройден;
кандидат сохранил дефект и добавил 6 регрессий, поэтому отклонён. 8474 reported
tokens, 2 task requests / 3 transports. Следом — проверка различающих observations
для fixture/parameterized теста; повтор того же контекста не планируется.

[Локализация сохранённых неудач](../../architecture/internal_targets_20260914.md): traced вызов теперь
может быть результатом простого присваивания перед падающим равенством.
`repair_target_trace_probe.failing_call_ranges` сохраняет guards и неоднозначность;
`test_repair_trace_assignments.py` проверяет actual subprocess и исключения.
Ручные reference interventions дали Pyupgrade 1098/0 и Toml-sort 34/0; новых
модельных вызовов и автономных ремонтов нет. Полный owned method context
Toml-sort доступен; Pyupgrade function/plugin dispatch пока вне nomination.

[Новая серия](../../architecture/fresh_direct_batch_20260914.md): 0/4 ремонтов первой попытки;
один assisted повтор также отклонён. До hypothesis/candidate IO выполняется
`native_failure_acceptance.preflight_native_acceptance` с двумя исходными replay.
`project_native_failure_helper_binding.direct_constructor_method` разрешает
ограниченный observed `Class(...).method()` без объявления root cause.
Parser принимает квадратные subtest labels, сохраняя предел parent nodeids.
Тесты: `test_native_model_preflight.py`, `test_direct_constructor_binding.py`,
`test_native_subtest_labels.py`; измеренные ограничения и расходы — в отчёте.

[Перенос direct на два проекта](../../architecture/direct_transfer_20260914.md): Humanize 720 passed /
74 прежних skipped, vblf 44 passed, оба final Reviewer approve. Vblf потребовал
повторной фиксации baseline без `--assert=plain`; первая попытка сохранена.
Training-уровни 8/5/6/9/8.8/8.8, независимых 9.7+ нет. Следующий приоритет —
native preflight и проверяемые direct-контракты Analyzer/Architect/SpecWriter.

[Прямой repair-route](../../architecture/direct_repair_route_20260914.md): policy
`model_proposal_route=direct`, default `hypothesis`. Helper
`runtime/upstream_direct_proposals.py` передаёт source obligations сразу кандидату.
Direct provenance отличается от hypothesis; Spec/Plan сохраняют grounding,
source/native/exact-delivery/final Reviewer gates общие. Реальная доставка
markdownify прошла 81/0 и approve; live ответ кеширован, holdout не заявлен.
Тесты: `tests/runtime/test_direct_model_route.py`, `test_repair_trial_role_chain.py`,
`test_model_candidate_delivery.py`, `test_model_requested_delivery.py`.

[Сравнение маршрутов](../../architecture/repair_route_comparison_20260914.md): одинаковые исходные
факты и DeepSeek, direct patch дал 81/0, текущий hypothesis→candidate COS дважды
80/1. Это эксперимент без изменения production API. Сбой возникает в combined
LLM hypothesis/design; он не является отдельным измерением трёх первых ролей.
Далее — упростить передачу требований без ослабления native/delivery gates.

[Четвёртый пакет из пяти шагов](../../architecture/five_steps_batch4_20260914.md):
`runtime/repair_observation_probe.py`, `repair_observations.py` исполняют отдельные
source-derived equality diagnostics в свежих копиях и проверяют повторяемость.
`repair_diagnostic_context.py` связывает observations и до трёх native comparisons
с текущим source/packet; API core `repair_observations`, `repair_counterexample_history`
доступен только для authorized model trial. Это opt-in input, не новый native gate.
Тесты: `tests/runtime/test_repair_observations.py`, `test_repair_grounding_feedback.py`,
`test_repair_trial_role_chain.py`. Paired pilot: heading исправлен лишь с observations,
table остался сломан; оба ремонта отклонены. Нет независимых новых баллов.

[Третий пакет из пяти шагов](../../architecture/five_steps_batch3_20260914.md):
`runtime/repair_assertion_contract.py` выделяет все прямые assertions полных
excerpts; opt-in policy `model_require_assertion_plan` требует план каждого ID.
Полный контракт и план доходят до candidate provenance и grounding Spec/Plan.
Новый аргумент core `repair_counterexample_comparison` повторно проверяет saved
native evidence перед запросом. Длинный output сохраняется целиком, в prompt
допускается явно обозначенный exact suffix с хешем полного текста.
Тесты: `tests/runtime/test_repair_assertion_contract.py`,
`tests/runtime/test_repair_grounding_feedback.py`, `tests/runtime/test_repair_trial_role_chain.py`.
Реальный цикл не дал принятого ремонта; новые баллы не заявлены.

[Второй пакет из пяти шагов](../../architecture/five_steps_batch2_20260914.md):
`runtime/repair_candidate_audit.py` сверяет факты дизайна с исходником и точным
кандидатом, без семантического допуска по AST. `runtime/model_candidate_feedback.py`
даёт bounded AST diagnostics для прежнего единственного format retry.
`runtime/upstream_model_delivery.py` связывает grounding Spec/Plan с выбранным
candidate provenance. Тесты: `tests/runtime/test_repair_candidate_audit.py`,
`tests/runtime/test_candidate_scope_feedback.py`, `tests/runtime/test_repair_trial_role_chain.py`.
Реальный markdownify patch прошёл формат, но не table-cell assertion;
полная native suite 80 passed / 1 failed, финальная доставка не допущена.

[Пять шагов, 14 сентября](../../architecture/five_steps_20260914.md):
`repair_branch_trace_probe.py` и `repair_branch_evidence.py` связывают достигнутый
return с выбранным методом и текущим исходником. Параметр `repair_branch_evidence`
у `run_project_development` требует nomination; гипотеза ссылается на return IDs,
Spec/Plan сохраняют `repair_grounding`. `repair_counterexamples.py` обеспечивает
проверенный native output для одного явно включённого повторного диагноза:
policy `model_native_counterexample_retries=1`, default 0, без совместного format retry.
`inference_route_evidence.py` сохраняет ограниченные gateway headers в telemetry,
без provider/billing attestation. Все модули находятся в `runtime/`.
Тесты: `test_repair_branch_evidence.py`, `test_repair_grounding_feedback.py`,
`test_repair_trial_role_chain.py`, `test_inference_route_evidence.py` в `tests/runtime/`.
Реальная попытка markdownify не дала ремонта; достигнут лимит пяти шагов.

[Repair trial, 14 сентября](../../architecture/repair_trial_20260914.md):
`runtime/repair_trial_binding.py` и параметр `repair_nomination` у
`run_project_development` сохраняют исходную observation в отдельном trial packet.
Native replay повторяет старую signature, patch scope — nominated method.
Проверки: `tests/runtime/test_repair_trial_binding.py`,
`tests/runtime/test_repair_trial_role_chain.py`. Scripted full chain проверена;
реальные model repairs markdownify пока отклонены.

[Repair nomination, 14 сентября](../../architecture/repair_nomination_20260914.md):
`runtime/repair_target_nomination.py`, `runtime/repair_target_trace_probe.py`,
`tools/nominate_repair_target.py` отделяют observed API от advisory repair target.
Две source-bound трассы ограничивают кандидатов падающим вызовом того же экземпляра.
Nomination не передаёт patch authority в существующий trial автоматически.
Проверки: `tests/runtime/test_repair_target_nomination.py`,
`tests/tools/test_nominate_repair_target.py`.

Назначение: получить связанные артефакты Project Analyzer, Architect, SpecWriter,
Implementer, Tester и Reviewer с ограниченными правами каждой роли.

Живой библиотечный опыт: [humanize, 13 сентября](../../architecture/fresh_model_20260913.md).
`runtime/upstream_candidate_context.py` ограничивает вход модели статическими
зависимостями, сохраняя целый файл для точного patch. Native replay согласован
с intake по assertion diagnostics и нормализации адресов объектов. Реальный
сквозной ремонт завершён в последующем [этапе humanize](../../architecture/humanize_delivery_20260913.md):
720 native passed, 74 skipped, финальный Reviewer approve. Это development evidence.
`runtime/project_failure_prompt_context.py` группирует повторяющиеся источники
тестов без потери nodeids; evidence packet включает decorators и параметры.
Ответы модели описаны JSON Schema. Policy `model_candidate_format_retries` допускает
0 (по умолчанию) или 1 повтор исправления формата, сохраняя оба ответа и все gates.

Второй проект [markdownify](../../architecture/second_project_intake_20260913.md) выявил остановку
до LLM: native 80 passed / 1 failed, непрозрачный тестовый wrapper не даёт
production-цели. `runtime/project_native_failure_test_imports.py` разрешает
относительные package imports и сохраняет `test_support_sources` с SHA256 и
ограниченным source excerpt. Это diagnostic-only evidence; helper не становится
местом ремонта. Проверки: `tests/runtime/test_native_relative_test_imports.py`.

[Продолжение markdownify](../../architecture/markdownify_helper_20260913.md):
`runtime/project_native_failure_helper_binding.py` поддерживает ограниченный
transparent helper → fresh instance method. Authority — observed API only,
не root cause. Evidence packet повторно проверяет helper и production hashes;
fixture/override/opaque/ambiguous случаи остаются закрытыми. Модельные кандидаты
не прошли native checks; ручной reference выявил необходимость отдельного
repair-target nomination. Проверки: `tests/runtime/test_native_helper_method_binding.py`.
Declared CLI + transform-library capability совместимы; plugin/packaging conflicts
и stateful execution risks сохранены. `project_type_token_matcher.py` теперь
владеет нормализацией текста, старые imports классификатора совместимы.

Приоритет первых трёх ролей и новый контракт планирования описаны в
[upstream roles, 13 сентября](../../architecture/upstream_roles_20260913.md).
Точки входа: `runtime/upstream_task_contract.py`, `runtime/upstream_role_handoff.py`,
`runtime/upstream_role_feedback.py`, `tools/upstream_role_pilot.py`.
Продолжение: [проверка причинных предложений](../../architecture/causal_selection_20260913.md).
`runtime/upstream_causal_selection.py` сравнивает training-предложения через native
Replay до выбора дизайна; `upstream_causal_review.py` связывает исполненный patch
с проверенным вмешательством. Вход: `run_project_development(validate_causal_proposals=True)`
при explicit training replay. Независимый диагноз этим ещё не подтверждён.
Переданные требования и примеры сохраняются; их происхождение явно отмечается.
Свободный текст автоматически в контракт не преобразуется. В общем `run_role_pipeline`
контракт остаётся planning-only. В `run_project_development` реализована
[передача требований в native-ремонт](../../architecture/requested_repair_20260913.md) для одного
failure target и явно привязанных тестов, при существующем explicit training replay.
Точки входа: `runtime/upstream_requested_change.py`, `runtime/upstream_change_impact.py`.

`runtime/upstream_call_bindings.py` разрешает ограниченные статические связи
функций и import aliases, сохраняя неопределённость затенения и динамики.
Диагноз отделяет corroborating stub observations от native packet той же цели;
разные native evidence не сливаются. Верхний статус development сохраняет
остановку handoff. [Проверка на map и ограничения](../../architecture/map_assessment_20260913.md).

В режиме сравнения вместе с `llm_hypothesis_config` вместо KB запускается
[пробный LLM-маршрут](../../architecture/llm_causal_trials_20260913.md): source-bound гипотеза,
1–4 структурированных вмешательства в одну функцию и существующий native Replay.
`runtime/upstream_llm_trials.py` сохраняет ответы и все результаты; без запроса
исполнения Architect и SpecWriter получают сравнение без execution authority.
С `run_sandbox_experiment=True` доступна [доставка точных проверенных байтов](../../architecture/model_delivery_20260913.md):
`runtime/upstream_model_delivery.py` связывает кандидат с исходником, native evidence
и отдельной authority `explicit_model_candidate_replay`; `runtime/programmer_model_delivery.py`
проверяет Spec/Plan и материализует копию без новой генерации. Полная native regression
и финальный Reviewer обязательны. [Явный native task_contract](../../architecture/model_requirements_20260913.md)
теперь передаётся в оба модельных запроса целиком, связывается с provenance и ticket.
`runtime/upstream_model_requirements.py` проверяет требования на точных байтах
выбранного patch. Удаление требований, подмена proof или провал сохраняемого
наблюдения блокируют исполнение; исходные ограничения native-контракта сохранены.
Снимок writable-файлов executor теперь принадлежит `runtime/programmer_source_snapshot.py`;
прежние private imports через `programmer_executor` сохранены.

Новый учебный stateful-ремонт описан в
[role_97_progress_20260912](../../architecture/role_97_progress_20260912.md). Продолжение перехода
SpecWriter → Tester → executor: [stateful acceptance](../../architecture/stateful_acceptance_20260912.md).
`runtime/native_failure_acceptance.py` передаёт исходный native-тест через
TestPlan формата `native_failure_acceptance.v1`: два baseline failure и один
patched pass в копиях, связанные с packet, файлами и inventory digest.
Поддержан один production-файл и до восьми nodeid; изменение тестов, fixture или
конфигурации не допускается. Неактуальный packet требует нового intake/handoff.
Это targeted acceptance; полная native regression и финальный review нужны отдельно.
Перенос на vblf и окончательный допуск описаны в
[native transfer / review](../../architecture/native_transfer_review_20260912.md).
`runtime/project_development_review.py` после native suite сохраняет
`native_test_result.json` и `final_review.json`, перепроверяет inventory sandbox
и делает итог Reviewer обязательным для валидации. Исходный executor TestResult
сохраняется отдельно. Planning review не заменяет этот завершающий проход.
`runtime/review_findings_conformance.py` связывает native результат с digest
TestPlan, целями, paired checks и хешами после регрессии. Зелёная suite не
перекрывает отказ acceptance, executor или experiment.
Generic callable acceptance для остальных контрактов сохраняет прежний путь.
На новом [EnvForge development-пилоте](../../architecture/envforge_development_pilot_20260912.md)
проверен training-only `runtime/programmer_mapping_descent_patch.py`: точный AST
обхода mapping, default при недостижимом пути, сохранение существующего значения.
Intake теперь сохраняет весь подписанный набор до восьми nodeid; превышение числа
или длины блокирует квалификацию. Это исправляет передачу пяти параметризованных
падений в native acceptance. Диагноз, fixture и оператор предоставлены ассистентом;
первая попытка без оператора остаётся `research_required`.
`runtime/programmer_pending_future_patch.py` завершает pending Future только
при поддержанной AST-форме и explicit_training_replay; исходный проект не меняет.
`runtime/executable_acceptance_environment.py` через Replay ограничивает также
подготовку harness: импорт/пробные вызовы больше не выполняются в host-процессе
обычного `run_executable_acceptance`. Ошибка probe не даёт структурного passed.

Начинать с `runtime/configured_role_pipeline.py`,
`runtime/role_artifact_interpreter.py`, `runtime/role_project_analysis.py`.
Pipeline задаётся `config/role_artifact_pipeline.json`; смысловые контракты
связываются с runtime authority и `registry/interface_contracts.json`.

Для свежего дефекта: `runtime/project_native_failure_intake_core.py` запускает
native tests, `runtime/project_native_failure_binding.py` связывает падение с
целью. `runtime/project_development_core.py` строит диагноз и запускает попытку.
`reproducible_unbound_failure` и `no_verified_failure_reducer` — разные остановки;
ни одна не является успешным исправлением. Façade-модули сохраняют старые imports.

Привязка assertion к локальному API реализована в
`runtime/project_native_failure_target_binding.py`. Source resolver поддерживает
один переход через абсолютный/относительный реэкспорт из `__init__.py`.
`runtime/project_native_failure_unittest_assertions.py` выделяет аргументы
стандартных сравнений прямого наследника `unittest.TestCase`; подготовка теста
и сообщение assertion не назначаются production-целью. Переопределённые методы,
непрозрачные наблюдатели и неоднозначные цели не получают такой привязки.
Это статическая связь наблюдаемого результата с API, а не доказанный диагноз
внутреннего дефекта. Проверка: `tests/runtime/test_native_unittest_binding.py`.

Потреблённый случай vblf проходит отдельный учебный путь: новый диагностический
тест связывает потерю хвоста с `BlfWriter._flush_container`, а
`runtime/programmer_buffer_tail_patch.py` предлагает удалить терминальный clear
после комплементарного split. AST-условия ограничивают форму правки; её корректность
подтверждают targeted replay и полная native suite. Оператор зарегистрирован как
`training_only`, требует `explicit_training_replay` и меняет только sandbox.
Привязка к прежнему месту проявления (`CanFdMessage64.unpack`) не расширяется
автоматически. Проверки: `tests/runtime/test_programmer_buffer_tail_patch.py`.

Порядок артефактов: Project Analyzer -> Architect -> SpecWriter -> Implementer Planner -> Tester (TestPlan) -> Sandbox Programmer (PatchPackage/TestResult) -> Reviewer.
Контролируемое восстановление: Reviewer -> Researcher -> Architect -> Developer -> Tester -> Architect.
`ProjectDevelopmentDiagnosis` и `ProjectDevelopmentOutcomeContract` связывают
диагноз с проверяемым результатом. При отсутствии допустимого исполнения итог —
`needs_replanning`; наличие плана само по себе не означает выполненное изменение.

Зависимости: Inspect через fact plugins, Evidence, Execution; KB/policy/config
нужны для интерпретации. Фактический граф шире этих точек входа. Native-failure
intake связан циклом с project_development; не переносить его целиком в Replay.

Проверки: role_project_analysis и тесты соответствующего изменяемого артефакта;
сквозные qualification/holdout нужны для утверждений об улучшении качества.
Успешное создание схемы или текста не заменяет независимый исправленный дефект.

Генератор `runtime/llm_sandbox_implementation.py` создаёт устанавливаемый CLI и
корневой `main.py`. Для преобразования текстовых файлов ввод читается как UTF-8
без нормализации переводов строк; одинаковые файлы/алиасы отклоняются. Результат
записывается через временный файл и замену, после успешного преобразования.
Ошибки чтения и кодировки сохраняют существующий output. Внешний контракт task15
проверяет `evaluation/acceptance/check_uppercase_cli.py`; это отдельная проверка
от тестов, создаваемых тем же генератором. Первый пакет со статусом `ok` не прошёл
этот контракт, исправленный прошёл 6/6; это инженерное исправление ассистентом,
а не самостоятельный ремонт свежего дефекта ролевой цепочкой.
Проверка синтаксиса сгенерированных Python-файлов компилирует их в памяти:
так вложенная Windows-копия не требует ещё более длинных путей к bytecode cache.
Исполнение pytest сохраняется; случай длинного пути входит в регрессионные тесты.

Завершение структурных изменений: `runtime/stage_finalization.py`, CLI
`tools/finalize_stage.py`. Контракт, ограничения и порядок применения описаны в
[finalization.md](../../architecture/finalization.md). Модель группирует функции, оператор переносит
их, прежние тесты подтверждают выбранный regression scope. Это отдельный контур
поддержки разработки, не автоматическое повышение оценок ролей.
Незавершённые случаи CLI передаёт в `DEVELOPMENT_TASKS.json` через
`runtime/development_handoff.py`; генератор контекста показывает задачи выбранной
подсистемы. Порядок ручного продолжения и закрытия — в `DEVELOPMENT_TASKS.md`.
Единый вход и завершение этапа, общая очередь, память решений и резервирование
LLM описаны в [development_workflow.md](../../architecture/development_workflow.md).

Текущие оценки читать в DEVELOPMENT_STATUS, подробные таблицы — в датированном
ROLE_PROJECT_SCORE_REPORT. Обучающие replay и свежие holdout имеют разную область
действия. Новое структурное разделение не повышает баллы ролей автоматически.

Greenfield-доставка поддержанного uppercase CLI реализована отдельным режимом
`run_role_pipeline(mode="greenfield")`: `runtime/greenfield_delivery.py` и
`runtime/greenfield_delivery_contracts.py` связывают ProductTechnicalSpec с native
sandbox generator, внешним TestResult и GreenfieldDeliveryReview. Обычный режим
остаётся `existing_project`. CLI: `tools/greenfield_role_run.py --output-dir PATH --write`.
Исполнение допускается только в пустой output под artifacts и с внешним verifier.
Контракты, проверенный scope и ограничения: [greenfield_delivery_20260912](../../architecture/greenfield_delivery_20260912.md).
