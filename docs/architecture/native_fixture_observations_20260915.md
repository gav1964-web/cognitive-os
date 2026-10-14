# Наблюдения исходного теста с фикстурами

15 сентября 2026. Локальный этап после неудачного модельного Toml-sort.
Дополнительных модельных вызовов **0**. Исходный проект и прошлые результаты
не изменены; новых автономных ремонтов и независимых оценок 9.7+ нет.

## Проверенное ограничение и реализация

Старый `collect_repair_observations` остановился на реальном тесте с
`fixture_free_source_owned_test_required`. Он отдельно вычисляет expressions
из `assert`, поэтому ему нельзя приписывать исполнение fixtures/sequence.
Legacy-поведение сохранено. Новый opt-in API
`runtime.native_repair_observations.collect_native_repair_observations` запускает
**исходные selected pytest nodeids** с их фикстурами и assertion rewrite дважды
в отдельных копиях. Это диагностический режим, без patch/acceptance authority.

Вызывающая сторона явно задаёт `method_fields` (до 4 методов одного owned класса,
до 8 локальных имён на метод) и `test_local_names` (до 8 имён). Имена сверяются
с исходником; `self` и неизвестные поля запрещены. Сериализатор сохраняет только
ограниченные встроенные значения. Пользовательские объекты остаются opaque:
нет `repr`, обхода атрибутов, автоматического dumps или выполнения expressions.
Снимки locals привязаны к строкам и порядку событий. У assertions фиксируется
**reachability**, а не выдуманный индивидуальный pass. Весь test outcome получен
от pytest. Проверка, не достигнутая после ошибки, не вычисляется повторно.

Обязательны прежняя failure signature, точная коллекция nodeids, повторяемые
observations, исполнение всех явно выбранных методов, source/probe hashes,
неизменность originals/copies и точных request/output receipts. Подмены,
неисполненный метод, неподдержанный тест или превышение бюджета закрывают допуск.
Поддержаны top-level синхронные тесты с прямыми assertions и обычные синхронные
методы; произвольный data flow и hostile-code attestation не заявляются.

Existing `validate_repair_observations` и `observation_context` принимают новый
`native_repair_observations.v1`. В `repair_diagnostic_context` ему соответствует
ключ `native_test_observations`; legacy ключ остаётся
`isolated_assertion_observations`. Оба проходят существующий authorized
`run_project_development(..., repair_observations=...)` и native/Reviewer gates.
Method observations относятся к целому test call, не доказывают причинность
конкретного внутреннего метода или равенство opaque-объектов.

## Реальный Toml-sort

Источник — прежний frozen baseline, packet — сохранённый derived trial после
модельного выбора `write_header_comment`. Модельный патч и ручной reference
не применялись. В `native_verified` два одинаковых native replay показали:

- Вход и ожидаемый результат: один `# This is a single comment\n`.
- `sort_output` и return `sorted()`: два таких комментария с пустой строкой.
- Header-ветка выполняется раньше обработки `items`/footer.
- В `toml_doc_sorted` перед footer-веткой `items == []`, длина `footer_comment == 1`.
- Выполнены строки header-add и footer-add; значения Comment/TOMLDocument opaque.
- Первый assert достигнут, второй assert проверки идемпотентности **не достигнут**.

Это различающие наблюдения, согласующиеся с прежней локальной диагностикой;
они не заменяют её counterfactuals и не доказывают, что модель исправит дефект.
Четыре сочетания header/footer ранее проверены отдельными ручными controls;
новый collector не выдаёт их за часть исходного падающего теста.

Подготовлен direct request через существующий код: **18 218 символов**, содержит
`native_test_observations`, предыдущий отрицательный comparison, исходные assertions
и допустимую source projection. Вариант без history занимал 16 358 символов.
Он **не отправлен**. Объяснение/patch ручного reference в него не добавлены.

## Проверки и handoff

`tests/runtime/test_native_repair_observations.py`: настоящие параметризация,
fixture setup/teardown, недостигнутый вызов, сохранность исходника, explicit scope,
source/probe/request/output tampering и отсутствие execution authority.
`test_repair_trial_role_chain.py` дополнительно проверяет native observations
через direct и hypothesis до полной synthetic regression и final Reviewer.
Scripted role-chain tests проверяют интеграцию, не компетентность реальной модели.

Результаты: `artifacts/causal_trials/toml_fixture_observations_20260915/`:
`legacy_result.json`, `legacy/A001-0/output.txt`, `native_verified/result.json`,
`native_verified_context.json`, `prepared_direct_verified.json`, `audit.json`.
Профильные early checks: `artifacts/verification/fixture_observations_focused_20260915.xml`.
Итоговая regression/400-line finalization:
`artifacts/verification/development_stage_fixture_observations_20260915.json`.
Package verification выполняется offline через `artifacts/tooling/package-wheels`.

Следующий ограниченный эксперимент — один repair request с новым native evidence
и сохранённым отрицательным результатом предыдущего кандидата, после объявления
отдельного бюджета. Evidence пока связано с прежним nominated method; автоматический
перевыбор места ремонта не добавлен. Полная suite, сохранение header/footer modes
и final Reviewer обязательны для утверждения об успехе. Ролевые уровни остаются
**8/5/6/4/0/2** по последней реальной неудачной попытке.
