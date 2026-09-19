# Append mapping: извлекатель через контракт, 15 сентября 2026

Плагин `append_mapping` версии 0.2.0 владеет исполняющим алгоритмом извлечения
словаря из append-цикла. Результат — предложение исходника, не применение патча.
Staged boundary/contrast KB и прежние полномочия сохранены.

## Владение

| Компонент | Ответственность |
|---|---|
| `cognitive_inspect.ast_navigation` | Общие `parent_map`, `find_top_level_function`; только AST-навигация |
| Inspect compatible parser | Прежняя обработка Python grammar/version; исходник parser не изменён |
| `plugins/append_mapping/src/extractor.py` | Алгоритм и собственные проверки enclosing loop / returns accumulator |
| `runtime/append_mapping_contract.py` | Registered `propose_patch`, proposal/refusal и ошибки допуска |
| Recovery/development consumers | Выбор редьюсера, recipe, sandbox, compile/differential проверки и применение |

JSON-dumps, JSON-loads и splitlines reducers используют те же общие AST-функции
через Inspect; их тела не изменены. Вторых реализаций общих функций нет.
Старый `_extract_append_mapping_helper` — alias зарегистрированного клиента.
Два внутренних owner-specific helper imports из общей facade удалены: других
их потребителей в исходниках не найдено. Это не публичные API плагина.

## Контракт и целостность

Вход `propose_patch`: `source`, `origin_symbol`, `proposed_symbol`,
`maximum_mapping_fields`. Выход: `proposed` + прежний patch dict либо
`not_applicable` + null. Лимит передаётся явно из прежней recipe; плагин не
расширяет его и не получает полномочия из staged boundary evidence.
Ошибки registry/schema не превращаются в обычную неприменимость и не обходятся
приватным вызовом. Прежние route gates работают до обращения к плагину.

Зависимость Inspect объявлена через существующий `implementation_packages`,
поэтому её установленный исходник участвует в hash плагина. Registry identities
обновлены для append_mapping и четырёх существующих Inspect-плагинов, чьи hashes
изменились из-за нового общего модуля. Это обновление identity, не promotion KB.

Общий dispatcher раньше отслеживал ранее импортированный код только в `src`
плагина. Теперь отслеживает также объявленные implementation packages по имени:
после изменения зависимости требуется restart, даже если новый hash зарегистрирован
и вызван другой plugin entrypoint. Проверка не содержит предметных веток.
Тест использует два неизвестных временных плагина и временный пакет; рабочие
пакеты в этом негативном контроле не меняются. Это защита наблюдавшихся импортов,
не OS sandbox и не доказательство происхождения произвольного стороннего кода.

## Доказательства

Исходники/hashes до переноса: `artifacts/verification/append_extractor_before_20260915.json`.
В `tests/fixtures/append_mapping_extractor_legacy.json` сохранены 12 фактических
legacy результатов: inline/assignment, CRLF, no-final-newline, Unicode,
nested/ambiguous/free-variable/limit/invalid-source и прочие отказы.
Новые результаты сравниваются целиком, включая source bytes/metadata; для
положительных случаев сравнивается выполнение на фиксированных входах.
Это development regression, не независимая сертификация алгоритма.

- Фокус: `artifacts/verification/append_extractor_focused_20260915.xml` — 40 passed.
- Финальный snapshot, полный выбранный scope и 400-line gate:
  `artifacts/verification/development_stage_append_extractor_20260915.json`.
- Архитектура: `artifacts/verification/append_extractor_architecture_20260915.json`.
- Установленные пакеты: `artifacts/verification/append_extractor_packages_20260915.log`.
- AST/hash preservation: `artifacts/verification/append_extractor_preservation_20260915.json`.
- Актуальность и local-corpus checks: `artifacts/verification/append_extractor_final_audit_20260915.json`.

Генератор и helpers перенесены с прежними телами. Recovery functions,
JSON/text reducer bodies, parser, mapping-path repair и recipe config сохранены.
Общий boundary interpreter не изменён. Документы знаний не продвигались;
LLM-вызовов нет, оценки качества не повышаются. Добавляется цена registry-вызова;
ускорение не заявляется.

Далее — владение extraction recipe и механизмом выбора среди нескольких
редьюсеров. Предметную recipe следует получать от владельца, а общие правила
сравнения кандидатов/проверки неоднозначности сохранить отдельно. Сначала
проверить всех читателей policy, verification и documentation contracts;
не создавать вторую редактируемую копию recipe и не менять allowed operators
или source-application gates при переносе.
