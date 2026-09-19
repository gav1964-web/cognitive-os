# Markdownify: наблюдаемый API и место ремонта

13 сентября 2026. Связь тестового helper с owned method реализована. Четыре
реальные модельные попытки **не дали принятого ремонта**. После их фиксации
отдельная ручная reference-правка другого метода прошла всю native suite:
**81 passed**. Это assisted development; независимые 9.7+ не подтверждены.

Вход прежний: `second_project_markdownify_case02_20260913`, case
`7bf52af60fe4e98d0bef`, baseline `5122c973c1a0d4351e64f02e2782912afbada9ef`.
Замороженный исходник и исторические тесты не изменены. Upstream production fix
не читался. Map отложен; новый поиск корпуса не проводился.

## Что изменено

`runtime/project_native_failure_helper_binding.py` связывает узкую форму
помощника с наблюдаемым API: прямой return метода нового объекта, неизменённые
позиционные входы, optional constructor kwargs с literal defaults перед
переданными options. Класс должен быть локальным, без неподдержанного наследования,
декораторов, metaclass и динамической подмены метода. Преобразования входа/выхода,
неоднозначность, fixtures/декораторы вызывающего теста, видимые monkeypatch и
изменения `__dict__` закрывают этот путь. Это ограниченный статический анализ;
произвольное динамическое поведение и скрытые runtime mutations не доказаны.

Привязка хранит helper/production SHA256 и authority
`observed_api_only_not_root_cause`. Evidence packet заново проверяет binding
и исходные хеши перед передачей helper в модельный контекст. Сохранённые
диагностические excerpts не превращаются в разрешение изменять тесты.
Старые прямые native/unittest bindings сохранены.

В этом случае связаны `tests/utils.py:md` и
`markdownify/__init__.py:MarkdownConverter.convert`. Новая intake signature
`27cb5602d46343d393f7a8ac57fb05f7d0f2c98dee7114e1660f3ef012d53d95`
отличается от прежней unbound signature, потому что в неё входит target.
Это изменение протокольной идентичности; прежние receipts не переписаны.

Исправлена и классификация: явно объявленный CLI может предоставлять capability
`library_pure_transform` без конфликта типов. Plugin/packaging conflicts остаются
отдельными; stateful execution risk не отменён. Нормализация текста перенесена
в `project_type_token_matcher.py`, совместимый `_normalized_text` import сохранён:
classification module снова укладывается в 400 строк.

## Модельные попытки

Все материалы — `artifacts/causal_trials/markdownify_helper_20260913/`.
Каждый `attempt_0N` содержит declaration, COS inventory, intake, полный transcript,
telemetry, result и проверку неизменности source/COS во время попытки.
Во всех попытках заранее разрешён максимум один повтор исправления формата.

| Попытка | Модель | Результат | Сообщённые токены |
|---|---|---|---:|
| 01 | DeepSeek | Гипотеза + кандидат + format correction. Replay сначала не нашёл bs4; после подготовки interpreter точный сохранённый patch прошёл assertion для heading, но упал на следующем assertion для table cell | 7 880 |
| 02 | DeepSeek | После уточнения инструкции учитывать все assertions предложено добавлять пробел после каждого br; нарушен обычный перенос строки. Native candidate rejected | 8 048 |
| 03 | DeepSeek | Переданы сохранённые native counterexamples двух предыдущих кандидатов. После format correction остался лишний schema_version; строгая схема отклонила ответ | 10 171 |
| 04 | GigaChat Pro | Отдельно выбран резервный provider для development-сравнения. Кандидат снова нарушил обычный перенос; native candidate rejected | 0 reported, usage не установлено |

Всего **12 логических model calls / 12 transport events**, **26 099 reported
tokens** от DeepSeek. Три GigaChat ответа имеют нулевое usage при ненулевой
задержке; это не доказательство нулевой стоимости. Billing и токены Codex-диалога
этими числами не измерены. Receipt: `stage_accounting.json`.
Attempt 04 — явный выбор резервного провайдера в эксперименте, не автоматический
переход по исчерпанию квоты. Этот этап не проверяет quota failover.

Полный `test_br` с четырьмя assertions присутствовал в hypothesis/candidate
контексте всех попыток. Проблема не объясняется потерей последних assertions
при обрезке prompt. Три DeepSeek гипотезы сообщали confidence 0.85; native checks
не позволили превратить уверенность модели в ошибочное принятие патча.
Код ответов вручную не исправлялся. Невалидный ответ attempt 03 не исполнялся.

## Окружение replay

Первичный intake использовал существующий dependency overlay. Изолированный
replay (`-I`) не видел его bs4. Для повторной проверки создан task-local
`artifacts/tooling/markdownify-native`: в него скопированы ровно четыре уже
использованные локальные зависимости, с file hashes и версиями в
`native_environment.json`. Скачиваний и изменения исходного проекта не было.
`saved_candidates_protocol_replay.json` подтверждает проверку точных байтов
первого кандидата в новом окружении, с **0 новых model calls**.
Общий автоматический перенос dependency environment между intake и replay
остаётся дальнейшей инженерной задачей; task-local подготовка его не заменяет.

## Ручной контроль после модельных попыток

Просмотр текущего production-кода показал, что `convert` только разбирает HTML
и делегирует обработку. В `convert_br` ветка inline-контекста возвращала пустую
строку. После фиксации всех четырёх модельных ответов ассистент заменил этот
return на один пробел в отдельной копии, сохранив обе обычные newline-ветки.
Полная native suite: **81 passed**. Changed set — только
`markdownify/__init__.py`; исходная frozen copy неизменна.

Receipts: `reference_intervention/declaration.json`, `full_native.json`,
`checks.json`; исправленная копия — `reference_intervention/project`.
Это **assistant_manual_reference**, не модельный patch, не финальный ролевой
Reviewer и не доказательство единственности причины. Для дальнейших опытов
этот метод и случай уже экспонированы; их нельзя назвать fresh holdout.

| Роль / участок | Что подтвердилось | Что осталось |
|---|---|---|
| Analyzer | Source-bound helper → observed method; native failure допускается к реальной модели | Выбор внутреннего repair target независимо от места наблюдения |
| Architect | Ограниченный контракт observed API, hashes, сохранённые риски и неоднозначность | Проектирование перехода observed API → проверяемая номинация внутреннего метода |
| SpecWriter | Сохранены все native assertions и исходные интерфейсы | Дизайн должен учитывать все требования, а не только первый упавший assertion |
| Implementer / Tester / Reviewer | Неверные кандидаты отклонены; исходник сохранён | Нет принятого model delivery и final Reviewer для markdownify |

## Проверки и следующий шаг

Focused regression: **112 passed**,
`artifacts/verification/markdownify_helper_final_focused_20260913.xml`.
Сохранены и ранние неудачные проверки новых fixtures. Финальный обязательный
stage receipt: `artifacts/verification/development_stage_markdownify_helper_20260913.json`;
он определяет фактический итог расширенной regression и 400-line gate.

Следующий этап — разделить observed API и candidate repair target. Номинация
модели должна опираться на ограниченный source/call context, проверяться на
принадлежность проекту и связь с native failure; при динамической диспетчеризации
может понадобиться runtime evidence. Номинация не авторизует patch. Требуются
negative controls для несвязанного метода, stale hashes, ложного call path и
неоднозначности, затем точная модельная правка, полный native regression и
final Reviewer. Не добавлять специальный оператор для markdownify и не повторять
дорогие запросы к тому же слишком узкому target без изменения архитектуры.
