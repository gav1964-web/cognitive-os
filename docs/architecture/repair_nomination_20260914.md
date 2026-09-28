# Предложение внутреннего места ремонта

14 сентября 2026. Этап реализует advisory nomination; переход к patch/replay
остаётся отдельным следующим этапом. Независимые оценки ролей не изменились.

`runtime/repair_target_nomination.py` сохраняет исходные observed target,
evidence packet и failure signature. `repair_target` — отдельное предложение,
без patch authority и без утверждения о доказанной причине дефекта.
`runtime/repair_target_trace_probe.py` дважды запускает исходный падающий тест
в отдельных копиях через `-I`. Поддержаны обычные синхронные методы одного
класса и одного экземпляра. Выбирается единственный вызов observed API на строке
падающего `assert`; предыдущие успешные assertions исключаются.

Исполняемый код сверяется со структурой скомпилированного исходника, включая
вложенные helpers/lambda. Кандидаты — только методы класса. Рёбра соединяют
ближайшие методы того же экземпляра в стеке и могут проходить через helpers:
это execution ancestry, не доказанный data flow. Аргументы и locals не
сериализуются. Trusted-code subprocess copies — не hostile-code attestation.
Несколько вызовов, нестабильная трасса, неподдержанные подмены и stale source/probe
hashes закрывают допуск. Бюджеты: 1 MB module, 64 метода, 32 000 символов контекста;
превышение отклоняется, без скрытого обрезания.

CLI `tools/nominate_repair_target.py` по умолчанию строит контекст; явный
`--request-model` делает один logical call без format retry, максимум 1200 output
tokens на transport attempt. Существующий transport failover сохранён.
Declaration, сообщения, response, telemetry, трассы и ошибки сохраняются.

## Markdownify: наблюдение, расходы, ограничения

Артефакты: `artifacts/causal_trials/markdownify_nomination_20260914/`.
Использован тот же frozen consumed assisted case02. Ассистент уже видел прежний
manual reference; reference patch в новый модельный запрос не передавался.
Sealed upstream oracle не читался. Это не независимый holdout.

`trace_attempt_01` и `02` остановились без LLM: первоначальная проверка отвергала
вложенный код и зависела от marshal interning. `trace_attempt_03` проверил
исправление. `model_attempt_01` заново получил две одинаковые трассы исходного
падения: 12 методов, 11 внутренних кандидатов, 17 343 символа контекста со всеми
assertions. DeepSeek выбрал `MarkdownConverter.convert_br`, сохранив observed API
`MarkdownConverter.convert`: **1 logical/transport call, 5177 input + 233 output
= 5410 reported tokens, 10.845 s, без failover**.

Выбор совпал с местом предыдущего manual reference, но объяснение неполное:
модель не разобрала существующую ветку `_inline`. Validator проверяет место и
provenance, а не истинность свободного объяснения. Новых модельных patch, native
repair success или final Reviewer нет. `model_source_check.json` подтверждает
неизменность COS и исходного проекта на момент модельного запуска.

## Проверки и продолжение

25 runtime tests и 6 CLI tests: настоящие subprocess-трассы, assertion scope,
dynamic helpers, чужие/неисполненные методы, неоднозначность, stale hashes,
unsupported classes, отсутствие patch authority, один model call, provider
errors и сохранность receipts. Связанный focused scope: 74 passed до последних
контролей. Итог выбранного regression scope и обязательной 400-line finalization:
`artifacts/verification/development_stage_repair_nomination_20260914.json`.

Следом explicit observation → repair trial binding: native acceptance сохраняет
исходную observed signature, replacement scope и model provenance привязываются
к nominated method. Старые packets/nodeids/repetitions не переписываются.
Нужны negatives для подмены nomination, stale trace, выхода patch за метод и
потери assertions; затем exact model patch → targeted comparison → full native
regression → Reviewer. До этой границы новые запросы патча не делать.
Map отложен, 9.7+ независимым измерением не подтверждён.
