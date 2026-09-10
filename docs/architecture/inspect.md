# Inspect: факты о репозитории

Назначение: дерево файлов, признаки стека, ограниченный Python AST и объявленные
команды. API и установка: [package README](../../packages/cognitive-inspect/README.md).

Точки входа: `cognitive_inspect.scan_project_tree`, `detect_project_stack`,
`extract_python_structure`, `extract_runtime_commands`. Реализация:
`packages/cognitive-inspect/src/cognitive_inspect/`; старые plugin `run` сохранены.
Payload и result описаны input/output JSON схемами соответствующих plugins.

Зависимости: стандартная библиотека. Runtime, роли, база архитектурных знаний,
project_map_report и правила исправлений сюда не входят. COS использует факты
через плагины; наличие route/policy candidate не доказывает понимание архитектуры.

Проверки: собственные тесты пакета, четыре plugin contract suite и потребители
Python parser/source helpers. Установка wheel проверяется отдельно от checkout.
При добавлении поля результата менять соответствующую схему и consumer tests.
Сохранять ограничения обхода и явные сведения о пропусках/неподдерживаемом синтаксисе.

Четыре plugin manifests объявляют `implementation_packages: ["cognitive_inspect"]`.
Hash и plugin lint учитывают исходники установленного пакета без их исполнения,
поэтому изменение реализации остаётся видимым registry doctor после переноса.
