# JSON serialization: три шага, 16 сентября 2026

## 1. Владение и исходные результаты

Механизм — извлечение одной inline `json.dumps(value)` из аргумента `write_text`.
Это не общий JSON codec. В shared boundary profile/source-contrast KB нет
отдельной записи для него; создавать искусственный профиль не требуется.
Предметный источник — существующий recipe и алгоритм с ограничениями.

| Область | Владелец после этапа |
|---|---|
| Recipe, extractor, metadata, refusal | `plugins/json_serialization` 0.1.0 |
| Parent map, top-level lookup, call-name spelling, parser | Inspect, нейтральные AST-функции |
| Legacy API | Alias зарегистрированного клиента, без второй реализации |
| Recovery, candidate selection, ambiguity, source scope/write | Прежний runtime coordinator |
| Differential verifier, Config Doctor | Прежние проверки, recipe через составной каталог |
| Role/research recognition | `no_safe_candidate_recovery`, `recovery_pattern_ast/clusters`, без изменения |

JSON loads, splitlines, semantic JOSE profile не объединяются с serialization.
Не заявляется завершённая миграция всех правил распознавания из planning слоя.
Сохранены 12 pre-change результатов, включая CRLF/no-EOF, kwargs, async,
несколько переменных, нулевой лимит, неоднозначность и повреждённый исходник.
Legacy algorithm даёт 5 proposals; это регрессионные случаи, не сертификация.

## 2. Плагин и нейтральная зависимость

`_extract_json_dumps_helper` перенесён с идентичным AST. Общий `_call_name`
используется оставшимися reducers и перенесён в `cognitive_inspect.ast_navigation`
как `call_name` с тем же телом/рекурсией. Это синтаксическое имя, не разрешение
импорта или binding; Inspect не получает правил ремонта.
18 проверок прямого контракта и AST API прошли до подключения рабочих вызовов.

Плагин предоставляет `patch_recipes`, `propose_patch`, `propose_helper`.
Recipe сохраняет все значения; предложение использует общий `helper_proposal.v1`.
Плагин активен для read-only вызовов; это не promotion и не source authority.
Inspect implementation hash входит в identity. Обновлены identity четырёх
Inspect plugins и append_mapping, добавлен новый plugin; остальные не менялись.

## 3. Рабочее подключение и проверка

JSON recipe удалён из общей конфигурации, runtime recipe helper читает
составной зарегистрированный каталог. Полный legacy каталог равен по значениям;
test raw-document expectation обновлён для двух извлечённых владельцев.
Dispatcher вызывает registered `propose_helper`, legacy alias — `propose_patch`.
Прежняя metadata/refusal ветка удалена из runtime; приватного fallback нет.
Общий interpreter, competency dispatcher, recovery и differential source не менялись.
Recipe admission проверяется заново; цена дополнительных registry/hash вызовов
не измерялась, ускорение не заявляется. 83 focused проверки прошли.

Доказательства:

- `artifacts/verification/json_serialization_begin_20260916.json`
- `artifacts/verification/json_serialization_before_20260916.json`
- `tests/fixtures/json_serialization_legacy.json`
- `artifacts/verification/json_serialization_step2_20260916.xml`
- `artifacts/verification/json_serialization_focused_20260916.xml`
- `artifacts/verification/json_serialization_preservation_20260916.json`
- `artifacts/verification/json_serialization_architecture_20260916.json`
- `artifacts/verification/json_serialization_packages_20260916.log`
- `artifacts/verification/development_stage_json_serialization_20260916.json`
- `artifacts/verification/json_serialization_final_audit_20260916.json`

Три шага завершаются финальной проверкой; следующий отдельный этап — карта
владельца JSON parsing с тем же контрактом, сохранением read_text boundary и
отказов на несколько чтений. Распознавание planning/research остаётся видимым
долгом миграции. Map отложен, новые модельные вызовы не разрешались этим этапом.
Оценки ролей и результаты автономного ремонта не повышаются от переноса файлов.
