# Inspect: факты о репозитории

Назначение: дерево файлов, признаки стека, ограниченный Python AST и объявленные
команды. API и установка: [package README](../../packages/cognitive-inspect/README.md).

`cognitive_inspect.ast_navigation` владеет общими `parent_map` и
`find_top_level_function`, а также `call_name` (синтаксическое имя Name/Attribute,
без разрешения binding): без мутации/IO. Их используют
append-mapping plugin и JSON/text reducers; предметные patch-правила в Inspect
не перенесены. [Проверка разделения](append_mapping_extractor_20260915.md).

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


С17 сентября2026 пакет предоставляет `python -m cognitive_inspect PATH` для JSON
дерева файлов с прежними ограничениями области и бюджета. Публичные Python API
сохранены. [Ролевой handoff и CLI-проверка](description_campaign_20260917.md).
