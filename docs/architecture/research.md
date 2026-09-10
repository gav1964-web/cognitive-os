# Research: корпус, обучение и оценка

Назначение: находить пригодные задачи, учитывать exposure, получать обучающие
данные и независимо измерять способности/продуктовый эффект.

Начинать с `runtime/local_historical_defect_mining.py`,
`runtime/historical_defect_qualification.py`, `runtime/three_route_evaluation.py`.
Политики: `config/local_historical_defect_mining.json`,
`evaluation/protocol_v2_manifest.json`; протокол — `evaluation/PROTOCOL_V2.md`.

`HypothesisValidationPlan` связывает post-training admission с проверкой
как минимум одного newly discovered match; large blind corpora remain release/calibration.
Полный действующий протокол: [SELF_IMPROVEMENT.md](../../SELF_IMPROVEMENT.md).
`SelfDevelopmentChangeProposal` учитывает границы L0-L4; unknown target kind
не получает автоматического допуска. Проспективный сбор остаётся в
`waiting_for_evidence`, пока требуемое независимое доказательство не получено.

Зависимости: Replay для исполнения одного известного дефекта, Roles для решения
задач, Evidence для связывания inputs/results. Наличие корпуса не означает его
семантическую пригодность. Текущий keyword-based library admission требует
улучшения по package/API/test evidence.

Проверки: mining, qualification и three_route_evaluation. Не передавать sealed
oracle решающей роли до завершения её независимой попытки. Не возвращать
потреблённый обучающий случай в fresh holdout. Receipt связывать с исходным
manifest, окружением и точным результатом проверки.

Артефакты читать по ссылке из текущего статуса. Не включать весь corpus или
sealed receipts в обычный context bundle. Fresh holdout и same-task three-route
сравнение остаются отдельными обязательствами при соответствующих утверждениях.
