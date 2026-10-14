# JSON parsing: три шага, 16 сентября 2026

## 1. Карта владельца и baseline

Владелец bounded-механизма — `json_parsing`: одна inline `json.loads` вокруг
синтаксического вызова с именем, заканчивающимся на `read_text`. Алгоритм не
разрешает binding и не доказывает реальный filesystem effect. Его ограничения
сохранены, улучшение качества этим переносом не заявляется.
Отдельного boundary profile/source contrast в shared KB нет; новый не создаётся.

Recipe, extractor, metadata/refusal относятся к плагину. Общие AST/parser API
уже находятся в Inspect и не меняются. Recovery сохраняет выбор, неоднозначность,
admission, sandbox/compile/write. Differential verifier и Config Doctor читают
прежние поля через составной каталог. Recognition в `no_safe_candidate_recovery`
и `recovery_pattern_ast/clusters` остаётся внешним planning/research слоем.
Network parsing boundary не переносится; serialization/splitlines не объединяются.

До изменений сохранены 12 результатов (5 proposals, 7 refusals): inline,
CRLF/no-final-newline, read kwargs, запрещённые loads kwargs, несколько чтений,
existing helper, invalid syntax, alias, async, non-read_text. Это regression
fixture, не независимые доказательства качества.

## 2. Плагин

`plugins/json_parsing` 0.1.0 владеет точным прежним AST extractor и recipe.
Контракты: `patch_recipes`, `propose_patch`, `propose_helper`; последний возвращает
общий `helper_proposal.v1`, без нового протокола. Плагин не импортирует runtime,
не исполняет входной source и не пишет его. Version hash включает Inspect
implementation. В registry добавлен только новый владелец; старые не изменены.
Прямой контракт прошёл 15 проверок до рабочего подключения.

## 3. Подключение

`runtime/json_parsing_contract.py` проверяет зарегистрированный ответ; прежний
extractor импорт — alias этого клиента. Dispatcher использует общий proposal,
собственная metadata/refusal ветка удалена. Recipe удалён из общей конфигурации,
`json_loads_helper_recipe` читает установленный составной каталог без кеша KB.
Полный legacy каталог сохранился; raw-document test теперь учитывает трёх
извлечённых владельцев. Приватного fallback нет. 100 focused checks passed.

Recovery, verifier, core interpreter/dispatcher, Inspect и соседние алгоритмы
не менялись. Плагин active только для зарегистрированных read-only calls;
это не promotion или право source application. Повторное чтение составного
каталога добавляет registry/hash проверки; ускорение не заявляется.

Доказательства:

- `artifacts/verification/json_parsing_begin_20260916.json`
- `artifacts/verification/json_parsing_before_20260916.json`
- `tests/fixtures/json_parsing_legacy.json`
- `artifacts/verification/json_parsing_step2_20260916.xml`
- `artifacts/verification/json_parsing_focused_20260916.xml`
- `artifacts/verification/json_parsing_preservation_20260916.json`
- `artifacts/verification/json_parsing_architecture_20260916.json`
- `artifacts/verification/json_parsing_packages_20260916.log`
- `artifacts/verification/development_stage_json_parsing_20260916.json`
- `artifacts/verification/json_parsing_final_audit_20260916.json`

После трёх шагов — остановка. Следующий владелец: text splitting, с проверкой
своего recipe, реальной KB и границ splitlines. Затем отдельно рассмотреть
повторные чтения составного каталога в одной recovery-транзакции, сохраняя
проверку identity/freshness и отсутствие скрытого fallback. Planning recognition
остаётся видимым долгом миграции. Map и модельные эксперименты не возобновлялись.
