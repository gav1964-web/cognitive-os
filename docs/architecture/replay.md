# Replay: воспроизведение одного дефекта

Назначение: из заданных baseline/fix и regression tests получить два одинаковых
baseline failure, результат исправления и сведения о сохранности исходника.
API, входные поля и установка: [package README](../../packages/cognitive-replay/README.md).

Реализация: `packages/cognitive-replay/src/cognitive_replay/`. `sandbox.py`
связывает Git worktree, `environment.py`, `pytest_report.py` и process helpers.
Отчётный pytest plugin включён в пакет и копируется в тестовое окружение.
Windows subprocess runner используется также старым native-failure intake.
Roles использует `cognitive_replay.process` для source-bound paired native acceptance
через `runtime/native_failure_acceptance.py`. Ролевой контракт и решение о допуске
остаются в COS; публичный API пакета Replay не изменён.
`git.py` декодирует Git-вывод явно как UTF-8. Невалидные байты patch закрывают
чтение с ошибкой, чтобы не подменять содержимое при вычислении digest.

Зависимости: packaging, tomli для Python 3.10, внешний Git. Пакет не импортирует
COS. Manifest admission и требование двух случаев на тип остаются в
`runtime/historical_defect_qualification.py`, mining — в Research.

Контракты: environment v1 и pytest result v1 внутри пакета, qualification receipt
v2 в COS. Версии и canonical digests при переносе сохранены. Проверять status,
source HEAD/worktree/registry invariants и cleanup вместе. Изоляция worktree/venv
не является защитой ОС от недоверенного кода.
Пользовательский сценарий Inspect → проверка заданного Git fix доступен через
`tools/review_project_fix.py`; параметры и область результата — в
[development_workflow.md](development_workflow.md).

Тесты: пакетный replay настоящего временного Git-репозитория, frozen environment,
pytest protocol и Windows process lifecycle; в COS — весь qualification/mining
контур. Независимый тест пакета не использует corpus/role policy.
