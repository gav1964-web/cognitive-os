# Roles: анализ и планирование

Текущие результаты и ограничения: [статус](../../DEVELOPMENT_STATUS.md),
[активный план](../../DEVELOPMENT_PLAN_97.md), [сравнение моделей](model_comparison_20260918.md).
Исторические измерения: [прежний brief](../history/model_comparison_20260918/roles.md).

Последний [внешний цикл](external_cycle_20260918.md): python-slugify проходит
81 native tests и final approve после одной повторной модели с regression feedback.
Переход между попытками выполнил ассистент; патч оставлен точным модельным.
`runtime/upstream_acceptance_proposals.py` принимает предложения тестов до ремонта,
сохраняет provenance и проверяет два baseline повтора в разрешённых копиях.
Ошибка импорта не проходит как assertion counterexample; смысл теста не сертифицируется.
Проверки: `test_upstream_acceptance_proposals`, `test_native_export_binding`.

`project_description` 0.17.0 владеет `behavior_checks`: явно выбранные свойства
конкретного вызова передаются в обе стадии полного описания. Смысловые ошибки
в paired controls сохранились; opt-in не продвигается в default и не объявляется
доказательством качества. Контракт: [README](../../plugins/project_description/README.md).
Проверка: `tests/runtime/test_description_behavior_context.py`.

`BudgetedChat` связывает слот, проверку шлюза, реальный ответ и ledger.
Usage0 для непустого запроса остаётся unknown. Новый явный параметр
`allow_unknown_reservations=False` позволяет вызывающему коду реализовать отдельно
разрешённую политику продолжения: unknown остаётся unknown с полным резервом.
Сумма max(reserve, reported) строго меньше1млн; started и повторные слоты блокируются.
Кампания966292 получила явное разрешение владельца и завершена:21вызов,
4unknown сохранены. [Полные результаты](model_comparison_followup_20260918.md).

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

Автоматический bounded retry: `runtime/development_regression_cycle.py` использует
`development_regression_feedback.py`, повторно проверяя фактическое падение полной
регрессии. Свежий model trial имеет отдельный authorization от training replay.
`native_replay_settings.py` сохраняет pytest plugins и timeout в evidence packet;
`native_regression_scope.py` проверяет сохранность тестов и doctests. Ролевая
рубрика v3 требует этот receipt для validated-change credit. Область и реальные
неудачи: [кампания 19 сентября](role9_campaign_20260919.md).

`model_require_assertion_plan: when_supported` включает явный план для каждого
прямого assertion в поддержанных test excerpts. Неподдержанная форма сохраняет
исходный native oracle и явное ограничение; повреждённые source hashes не дают
fallback. Форматный и native-feedback retry могут сочетаться в пределах пяти
логических вызовов, а injected budgeted chat независимо ограничивает токены.

`upstream_owned_acceptance.prepare_owned_acceptance` связывает выбранную
компетенцию, исходный seed, требование, копию и два baseline-прогона. Плагин
`python_transform_contracts` владеет проверками выходного Python и сохранения AST
для форматирования, включая варианты пробелов и комментариев с тем же входным
AST. Выбор применимости явный; это ограниченное свойство, не полнота acceptance.
`python_overload_resolution` допускает последовательные декларации стандартного
typing.overload и одну реализацию; сохраняет stubs, блокирует неоднозначные и
исполняемые дубликаты. Evidence, prompts и structured editor используют одну
привязку. Проверки: `test_owned_acceptance_properties`,
`test_overload_implementation_binding`.

Opt-in `model_include_dependency_context` передаёт исходные объявления прямых
помощников и потребителей состояния класса с hashes и явными пропусками. Это
статический контекст, не доказательство causal call graph. Вместе с ним
`model_same_class_repairs` разрешает модели объявить до двух дополнительных
существующих методов того же класса; сигнатуры, decorators, doctests и остальные
части файла сохраняются. Набор edits должен точно совпасть с планом Architect.
Валидатор повторно проверяет всю согласованную правку перед delivery. No-op или
несоответствие плану может вызвать один design retry в том же лимите вызовов;
это отдельно отмечено от feedback по реально выполненным native tests.
Код: `model_edit_scope`, `candidate_rejection_feedback`,
`upstream_dependency_context`; проверка `test_same_class_model_edits` включает
сквозное исполнение пары методов и автоматический повтор без сетевых вызовов.

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
[finalization.md](finalization.md). Модель группирует функции, оператор переносит
их, прежние тесты подтверждают выбранный regression scope. Это отдельный контур
поддержки разработки, не автоматическое повышение оценок ролей.
Незавершённые случаи CLI передаёт в `DEVELOPMENT_TASKS.json` через
`runtime/development_handoff.py`; генератор контекста показывает задачи выбранной
подсистемы. Порядок ручного продолжения и закрытия — в `DEVELOPMENT_TASKS.md`.
Единый вход и завершение этапа, общая очередь, память решений и резервирование
LLM описаны в [development_workflow.md](development_workflow.md).

Текущие оценки читать в DEVELOPMENT_STATUS, подробные таблицы — в датированном
ROLE_PROJECT_SCORE_REPORT. Обучающие replay и свежие holdout имеют разную область
действия. Новое структурное разделение не повышает баллы ролей автоматически.

Greenfield-доставка поддержанного uppercase CLI реализована отдельным режимом
`run_role_pipeline(mode="greenfield")`: `runtime/greenfield_delivery.py` и
`runtime/greenfield_delivery_contracts.py` связывают ProductTechnicalSpec с native
sandbox generator, внешним TestResult и GreenfieldDeliveryReview. Обычный режим
остаётся `existing_project`. CLI: `tools/greenfield_role_run.py --output-dir PATH --write`.
Исполнение допускается только в пустой output под artifacts и с внешним verifier.
Контракты, проверенный scope и ограничения: [greenfield_delivery_20260912](greenfield_delivery_20260912.md).
