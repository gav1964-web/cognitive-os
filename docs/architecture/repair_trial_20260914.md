# Проверка ремонта внутреннего метода

14 сентября 2026, следующий этап после repair nomination. Инженерный переход
реализован и проверен до завершающего Reviewer на scripted-сценарии. Реальные
попытки markdownify остались неуспешными; независимые баллы ролей не повышены.

## Контракт и границы

`run_project_development(..., repair_nomination=bundle)` принимает nomination,
две трассы и их контекст только в явно разрешённом модельном trial.
`runtime/repair_trial_binding.py` строит отдельный `ProjectRepairTrialPacket`
(`repair_trial_packet.v1`). Он содержит неизменённый `observation_packet`,
исходный `observed_target`, прежнюю failure signature, test sources и nodeids.
Поле `target` нового пакета обозначает выбранный внутренний метод. Исходные
failure rows, packet list и исторические repetitions не переписываются.

Новый пакет не выдаётся за повторное наблюдение native failure. На границах
генерации, comparison, native acceptance и материализации заново проверяются
nomination/context/trace, исходники и их hashes. Native baseline обязан дважды
воспроизвести старую signature. Патч ограничен точными байтами одного метода;
изменение соседнего метода в том же файле также отклоняется. Существующие
точные model bytes, полная native regression и финальный Reviewer сохранены.
Training/KB routes не принимают nomination как разрешение исполнять свой reducer.

Гипотеза получает код вызывающих методов из проверенной трассы: раньше этот
контекст сохранялся в nomination, но терялся при переходе к гипотезе. Бюджет
такого prompt envelope — 24 000 символов, без скрытого обрезания. Превышение
останавливает запрос. Existing requested-change contract по-прежнему требует
точного target; автоматическое переназначение произвольных требований с API на
внутренний метод не добавлялось.

## Реальные попытки и собственные ошибки

Артефакты: `artifacts/causal_trials/markdownify_repair_trial_20260914/`.
Все попытки относятся к прежнему frozen consumed assisted markdownify case02.
Ассистент уже видел manual reference; его patch в запросы не передавался.
Upstream production oracle не читался; исходный проект неизменен.

| Попытка | Маршрут | Результат | Reported tokens |
|---|---|---|---:|
| 01 | DeepSeek | Гипотеза принята, кандидат сначала остановлен моей проверкой scope; сохранённый кандидат затем не прошёл native test | 4889 |
| 02 | GigaChat Pro, явный маршрут | Модель исказила failure signature; гипотеза отклонена до запроса патча | неизвестно, reported 0 |
| 03 | DeepSeek, с caller context | Кандидат не прошёл исходный native test | 9025 |

Всего **5 logical / 5 transport calls, 13 914 reported DeepSeek tokens**.
GigaChat usage неизвестен; reported 0 не означает бесплатный запрос. Format
retries не использовались; GigaChat запускался явно, не по исчерпанию квоты.
`accounting.json`, все transcripts, telemetry и source checks сохранены.

Моя первоначальная проверка scope некорректно повторно добавляла отступы при
CRLF, пустых строках и допустимом нестандартном отступе тела. Исправлено,
проверено для LF/CRLF. `saved_candidate_replay.json` повторно проверяет точные
байты attempt01 с нулём новых model calls; старый inconclusive receipt сохранён.

Оба DeepSeek-кандидата оставили ранний `return ""` для `_inline` и добавили
обработку заголовка после него. Они не исправили исходный assertion. Более
широкий source context не обеспечил правильного анализа ветвей. Это не доказывает
неспособность модели вообще и не устанавливает влияние gateway/cache; модельное
происхождение не имеет независимой provider attestation.

## Проверки и дальнейшая работа

`tests/runtime/test_repair_trial_binding.py`: неизменность observation, новый
scope, старые nodeids/signature, stale и подменённые bundles, нулевые LLM-вызовы
на неверном evidence, обход через training route, LF/CRLF, native replay и delivery.
`tests/runtime/test_repair_trial_role_chain.py`: scripted модельный ответ проходит
реальные роли, executor, native regression и финальный Reviewer `approve`.
Это тест инфраструктуры, не успешный самостоятельный ремонт markdownify.

Focused receipt: `artifacts/verification/repair_trial_final_focused_20260914.xml`.
Финализация 400 строк и regression на снимке:
`artifacts/verification/development_stage_repair_trial_20260914.json`.

Следующий приоритет Analyzer → Architect → SpecWriter: доказательства реально
достигнутой ветви/early return, проверка согласованности repair mechanism с ней
и ограниченная передача native-контрпримеров обратно в диагноз. Не повторять
те же LLM-запросы без нового evidence. Затем повторить точный модельный patch,
всю native suite и Reviewer на этом же consumed случае. Model quality/gateway
evidence остаются отдельными вопросами; map и независимый holdout отложены.
