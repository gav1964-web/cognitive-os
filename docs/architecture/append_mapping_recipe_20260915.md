# Append mapping: рецепт у владельца, 15 сентября 2026

Плагин `append_mapping` 0.3.0 владеет KB границы, алгоритмом и extraction recipe.
Рецепт из общей `config/patch_synthesis_policy.json` перенесён без изменения
значений в `plugins/append_mapping/knowledge/patch_recipes.json`.
Frozen legacy fixture служит только тестовым эталоном, runtime её не читает.

## Контракты и потребители

| Потребитель | Источник и сохранённая ответственность |
|---|---|
| `append_mapping.patch_recipes` | `ok` + records `{id, recipe}`, версия локального документа проверяется |
| `load_installed_patch_synthesis_policy(root)` | Общий каталог плюс зарегистрированные владельцы; конфликт ID отклоняется |
| `load_patch_synthesis_policy()` | Прежний составной результат для рабочих читателей |
| `load_patch_synthesis_policy(path)` | Только переданный JSON; без подмешивания установленной KB |
| Recovery/development | Прежние функции выбора кандидата, неоднозначности, sandbox и применения |
| Differential verification | Прежние profile, inputs, timeout, observations из контракта recipe |
| Recovery pattern clusters | Прежний набор реализованных target clusters через составной каталог |
| Config doctor | Составной каталог указанного installation root; прежние проверки обязательных полей |
| Config mutation sandbox | Валидация переданного документа; не чтение или изменение KB плагина |
| Upstream causal selection | Переданный training policy; append recipe не имеет training authority |

Нейтральный `catalog_records('patch_recipes')` использует существующий протокол;
общий dispatcher и boundary interpreter не изменены. Новая компетенция может
предоставить recipe без новой предметной ветки композиции. Нет тихого замещения
локального рецепта либо другого владельца. Обычные local recipe helpers сохраняют
прежний кеш, зарегистрированные recipe и generic framework lookup читаются заново.
Это добавляет проверку registry, ускорение и изоляция отказов framework lookup
на этом этапе не заявляются. Отказ допуска не превращается в fallback.

Порядок выбора четырёх extraction reducers и их функции не менялись. Полный
составной документ равен legacy по значениям; позиция перенесённого ключа JSON
в словаре не используется этими потребителями для выбора кандидата.
Плагин активен для чтения, boundary KB остаётся staged. Allowed operators,
разрешение на source apply и условия verification не расширены.

## Проверка этапа

- Legacy catalog: `tests/fixtures/append_mapping_policy_legacy.json`.
- Исходники до переноса: `artifacts/verification/append_recipe_before_20260915.json`.
- Фокус: `artifacts/verification/append_recipe_focused_20260915.xml`.
- Сохранение алгоритмов и guards: `artifacts/verification/append_recipe_preservation_20260915.json`.
- Архитектура: `artifacts/verification/append_recipe_architecture_20260915.json`.
- Финальная регрессия и 400-line gate: `artifacts/verification/development_stage_append_recipe_20260915.json`.
- Итоговая актуальность: `artifacts/verification/append_recipe_final_audit_20260915.json`.

Проверяются полный legacy каталог, реальные чтения Config Doctor, disabled recipe,
duplicate/malformed records, неизвестный временный plugin, mutation isolation и
смена KB hash с отказом до регистрации. Existing helper/recovery/differential и
pickle suites проверяют последствия переноса. Это инженерная регрессия,
не независимая оценка качества. Новых LLM-вызовов нет.

Следующий этап — карта предметных веток recovery dispatch: отделить описание
результата append-mapping от общей координации кандидатов и проверок. Перед
переносом определить общий контракт результата для остальных reducers;
сохранить байты patch package, причины отказов и единственный prepared candidate.
Не переносить sandbox/authorization в компетенцию и не объединять этот механизм
с mapping-path-descent. Остальные KB-владельцы мигрируют отдельными этапами.
