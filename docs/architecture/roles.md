# Roles: анализ и планирование

Назначение: получить связанные артефакты Project Analyzer, Architect, SpecWriter,
Implementer, Tester и Reviewer с ограниченными правами каждой роли.

Начинать с `runtime/configured_role_pipeline.py`,
`runtime/role_artifact_interpreter.py`, `runtime/role_project_analysis.py`.
Pipeline задаётся `config/role_artifact_pipeline.json`; смысловые контракты
связываются с runtime authority и `registry/interface_contracts.json`.

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

Текущие оценки читать в DEVELOPMENT_STATUS, подробные таблицы — в датированном
ROLE_PROJECT_SCORE_REPORT. Обучающие replay и свежие holdout имеют разную область
действия. Новое структурное разделение не повышает баллы ролей автоматически.
