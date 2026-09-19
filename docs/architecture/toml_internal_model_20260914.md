# Toml-sort: модельный ремонт с внутренним контекстом

14 сентября 2026. Выполнен следующий пункт после локальной диагностики:
одна модельная nomination и один direct candidate, без format/native retries.
Это тот же consumed assisted случай. Ассистент знает прежний ручной reference,
но patch и объяснение reference в запросы не передавались. Upstream fix не читался.

**Результат: 0 принятых ремонтов.** Исходная ошибка осталась; точный кандидат
DeepSeek дал 6 новых регрессий. Native gate отклонил его до доставки и финального
Reviewer. Исходный проект и версия COS во время запуска не менялись.

| Проверка | Результат |
|---|---|
| Свежая трасса исходного теста | Два одинаковых replay, 5 внутренних кандидатов |
| Выбор модели | `TomlSort.write_header_comment`, advisory nomination валидна |
| Native preflight перед кандидатом | Пройден, исходная signature сохранена |
| Полная baseline suite | 33 passed / 1 failed / 2 xfail |
| Полная suite точного кандидата | 27 passed / 7 failed / 2 xfail |
| Исправлено / новых регрессий | 0 / 6 |
| Финальный Reviewer | Не запускался: кандидат отклонён ранее |

Полные коллекции и прежние skipped/xfail identities сохранены. В derived packet
сохранены исходные observed API, failure signature, assertions и test sources.
Патч ограничен одним nominated method, exact response и replacement scope проверены.
Default маршрута, пороги качества и исходные результаты fresh серии не менялись.

## Что выяснилось

Nomination увидела 13 468 символов контекста и выбрала метод записи header.
Объяснение связывало название метода с симптомом, но не доказывало его причину.
Кандидат получил 14 341 символ контекста: тела **всех шести** traced методов,
включая `sorted`, `toml_doc_sorted`, `body_to_tomlsortitems` и `write_header_comment`;
параметризованный тест и observed failure также присутствовали. Контекст не
потерялся между nomination и direct proposal.

Модель переместила запись newline из ветки non-comment в конец цикла. Её
объяснение «newline после каждого комментария вызывает дублирование» не соответствует
показанному исходнику. Native test это опроверг; дополнительные тесты выявили
потерю ожидаемых пустых строк в других документах. Принадлежность метода к
трассе устанавливает допустимое место исследования, но не истинность диагноза.

Ожидание «достаточно передать внутренние определения» **не подтвердилось на этой
попытке**. Это не эксперимент, отделяющий влияние модели, nomination и prompt:
по одному исходу нельзя делать вывод о всех задачах или моделях. Нового production
кода на основании неуспеха не добавлено; существующие проверки отклонили патч.

## Расход и оценки

Заранее объявлено: максимум 1 nomination + 1 repair, 5 transports со служебным
L3.5 и failover; output limits 1200/3500. Фактически 2 task requests / 3 transports:

| Обращение | Prompt / completion / total tokens |
|---|---:|
| DeepSeek nomination | 3898 / 207 / 4105 |
| Служебный local L3.5 | Ошибка, usage неизвестен |
| DeepSeek candidate | 4100 / 269 / 4369 |

Всего **8474 reported tokens**, billing неизвестен. Резервная модель не
использовалась. Повторных запросов после неуспеха нет. Контрольные full-suite
прогоны выполнены без LLM. Результат неизменённой calibration-рубрики:
Analyzer **8**, Architect **5**, SpecWriter **6**, Implementer **4**, Tester **0**,
Reviewer **2**. Это прежние ограничения оценки, не независимая сертификация.
9.7+ не достигнут.

## Evidence и передача следующего этапа

`artifacts/causal_trials/toml_internal_model_20260914/`:
`declaration.json`, `cos_frozen.json`, `trace/result.json`, `nomination_bundle.json`,
`derived_packet.json`, `transcript.json`, `telemetry.json`, `transports.json`,
`result.json`, `source_check.json`, `full_comparison.json`, точные XML в
`full_comparison/`, `role_scores.json`, `audit.json` с проверками и hashes receipts.

Проверки этапа: `artifacts/verification/development_stage_toml_internal_model_20260914.json`.
Архитектурный checkpoint без полного environment-dependent suite:
`artifacts/verification/toml_internal_model_architecture_20260914.json`.

Следующее действие — локально проверить, как дать существующему diagnostic input
различающие наблюдения двух записей одного комментария и сохранённых режимов
header/footer. Сначала проверить совместимость существующих collectors с
параметризованным тестом/fixtures; не объявлять неподдержанный сбор рабочим и
не добавлять обязательное модельное объяснение или новые баллы за заполнение полей.
Новый запрос оправдан только новым проверенным evidence и отдельным бюджетом;
повторение прежнего контекста уже проверено. Pyupgrade function/plugin trace,
полные группы Wcmatch и Pathspec сохраняются в очереди, Map отложен.
