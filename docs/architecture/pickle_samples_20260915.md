# Pickle: подбор образцов в компетенции, 15 сентября 2026

Продолжение функционального разделения. Плагин `exception_pickle` версии 0.2.0
владеет правилами выбора базовых образцов и анализом исходника конструктора.
Общий provider, boundary interpreter, генератор патча и активная KB не изменены.
Правила из `constructor_samples.py` перенесены без изменения текста, с обычной
нормализацией переводов строк. Алгоритм object-contract classifier сохранён.

## Граница контракта

| Операция | Вход | Выход |
|---|---|---|
| `sample_values` | Упорядоченные `names`, optional `object_contracts`; optional текст `source` с `class_name` | `status: ok`, список `samples` той же длины; `null` означает неизвестную форму |
| `constructor_call` | Текст `source`, `class_name`, `required`, `samples` | `status: ok`, позиционные `args` и именованные `kwargs` по прежним правилам |

Образцы — прежние JSON-совместимые значения и дескрипторы `__sample__`.
`ok` означает, что операция подбора выполнена; это не подтверждение корректности
конструктора, native replay или допуска знания. Сохраняются неизвестные формы,
приоритет source observations / explicit contracts / базовых правил и fallback
аргументов при неподдержанной сигнатуре. Пустой batch допустим.

Плагин получает текст; пути проекта ему не передаются. Он не импортирует и
не исполняет анализируемый исходник. `runtime/exception_pickle_sample_contract.py`
читает файл один раз, сохраняет UTF-8 replacement и fallback отсутствующего файла,
затем вызывает registry. Общий протокол продолжает проверять manifest/schema,
активность и целостность. Ошибки admission не превращаются в неизвестный образец
и не обходятся приватным вызовом. Batch API позволяет проверить несколько имён
за один вызов; существующий одиночный API сохранён для совместимости.

## Потребители и дальнейшая миграция

Девять runtime-модулей используют новый клиент: active application, selection,
replay policy, autonomous shadow, blocker intelligence, failed probe analyzer,
materializer audit, object-contract classifier и semantic replay.
Sample-функции больше не импортируются через autonomous shadow.

`exception_pickle_constructor_samples.py` и `exception_pickle_source_samples.py`
остались адаптерами старых используемых импортов. Их можно удалить после
перехода downstream; рабочих runtime-потребителей этих модулей больше нет.
AST helpers бывшего source-модуля — внутренние функции владельца, не публичный
runtime API. Классификация/оценка объектных контрактов пока остаётся в Research,
но её обратная зависимость от shadow-исполнения устранена.

Создание настоящих объектов, запуск дочернего процесса и semantic replay
остаются в Research / Replay. Независимая оценка, authorization, source apply
и promotion не перенесены в callable plugin и не получили новых полномочий.
Следующий этап — разнести контракт проверки явного исследовательского каталога
и чтение зарегистрированной активной KB у application, blocker intelligence
и config doctor. Promotion требует отдельного write-contract с прежними guards.

## Доказательства

До переноса сохранены исходники/hashes:
`artifacts/verification/pickle_samples_before_20260915.json`.
Frozen development fixture `tests/fixtures/exception_pickle_samples_legacy.json`
содержит фактические результаты прежней реализации: 228 имён, 12 форм исходника,
8 объектных контрактов и 3 формы вызова. Это регрессия, не независимый holdout.

- Фокус: `artifacts/verification/pickle_samples_focused_20260915.xml` — 32 passed.
- Первый полный профиль: `artifacts/verification/pickle_samples_regression_20260915.xml`
  — 260 passed, одна ошибка size gate: active application вырос до 401 строки.
  Убраны две лишние пустые строки в конце файла; логика не менялась, итог 399.
- Повтор фокуса и config doctor: `artifacts/verification/pickle_samples_focused_v2_20260915.xml`.
- Финальный снимок / size gate:
  `artifacts/verification/development_stage_pickle_samples_20260915.json`.
- Границы: `artifacts/verification/pickle_samples_architecture_20260915.json`.
- Пакеты: `artifacts/verification/pickle_samples_packages_20260915.log`.
- Актуальность, hashes и дополнительные локальные проверки:
  `artifacts/verification/pickle_samples_final_audit_20260915.json`.

Перенос не повышает ролевые оценки. LLM-вызовов нет. Стоимость registry теперь
относится и к sample-вызовам; ускорение не заявляется, глобальный кеш не добавлен.
