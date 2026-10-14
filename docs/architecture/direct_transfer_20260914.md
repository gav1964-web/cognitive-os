# Перенос прямого ремонта: Humanize и vblf

Дата: 14 сентября 2026. Выполнен пункт 4 принятого плана: два других
development-проекта. Оба ремонта доставлены через COS до полного native regression
и final Reviewer `approve`. Humanize — первая попытка; vblf — после исправления
настройки baseline-протокола. Независимое достижение 9.7+ не подтверждено.

## Наблюдаемый результат

| Проект | До ремонта | После ремонта | Запросы ремонта | Вмешательство этого этапа |
|---|---|---|---:|---|
| Humanize | 715 passed / 5 failed / 74 skipped | 720 passed / 0 failed / 74 skipped | 1 | Нет правки исходников, тестов или ответа модели |
| vblf | 39 passed / 5 failed | 44 passed / 0 failed | 2 | Повторная фиксация baseline с обычным assertion rewriting |

Все десять исходных падений устранены; ранее проходившие тесты сохранены.
Дополнительный аудит сравнил точные collected nodeid и skipped nodeid, а не только
счётчики. У Humanize те же 74 пропуска, они не засчитываются как проверенные тесты.
У vblf нет пропусков. Оригинальные проекты и COS во время каждого запуска неизменны;
патчи применены только к проверочным копиям. Runtime, prompts, evaluator и пороги
в этом этапе не менялись. Default маршрута остаётся `hypothesis`, direct — opt-in.

Это consumed development: Humanize уже использовался в модельных попытках,
vblf имеет ранее созданный ассистентом диагностический тест и учебный оператор.
Этот оператор в direct-маршруте не вызывался. Upstream production fix в этом этапе
не читался и не передавался модели. Новый blind holdout и CLI здесь не измерены.
Предыдущий markdownify 81/0 — третий успешный проект в совокупной истории direct,
но не новая попытка этого этапа и не третий независимый пример.

## Уровни ролей по неизменённой рубрике

Одинаковые результаты для обоих принятых запусков:

| Роль | Calibration | С существующими ограничениями training replay | Независимые 9.7+ |
|---|---:|---:|---|
| Project Analyzer | 8.0 | 8.0 | Нет |
| Architect | 5.0 | 5.0 | Нет |
| SpecWriter | 6.0 | 6.0 | Нет |
| Implementer | 10.0 | 9.0 | Нет |
| Tester | 10.0 | 8.8 | Нет |
| Reviewer | 10.0 | 8.8 | Нет |

Calibration был заявлен до запросов. Дополнительно опубликован существующий
`training_replay` режим, поскольку случаи уже использованы и запуск разрешён
через development/training authority. Ни один режим не является новым holdout.
Десятки последних ролей означают выполнение пяти бинарных условий каждого
измерителя на этих доставках; это не оценка универсальной зрелости 10/10.
Researcher сопоставимо не измерен.

Analyzer не предъявляет отдельный причинный диагноз. Architect не предъявляет
concrete repair design и требуемый evaluator implementation path; его foundation
quality также ниже порога. SpecWriter не предъявляет ожидаемый concrete repair
action / implementation delta. Direct хранит проверенный кандидат и native evidence
в другом контракте, поэтому часть пробела относится к представлению артефактов.
Успех ремонта сам по себе не доказывает независимое качество этих трёх ролей.
Их численные уровни не выросли; это следующий предмет работы, а не повод добавить
обязательные неподтверждённые модельные объяснения или ослабить рубрику.

Общий evaluator возвращает `evidence_required`: нет CLI-покрытия, необходимых
lineages по каждому stratum и всех ролей >=9.7. Первая остановленная попытка vblf
сохранена и оценена отдельно; итоговые успешные запуски не заменяют историю попыток.

## Ошибки и расходы этапа

Бюджет до вызовов: максимум четыре transport attempts на проект, включая все
локальные callers и fallback, максимум два запроса ремонта, 3500 output tokens
на попытку; format retry выключен. Второй запрос допускался в пределах бюджета.

Всего **7 transport attempts**, из них **3 DeepSeek repair requests** и четыре
неуспешных `local` обращения. DeepSeek сообщил **5796 tokens**:
2859 Humanize + 1463 vblf v1 + 1474 vblf v2. Usage локальных ошибок неизвестен,
billing не установлен, fallback не наблюдался. На повторном vblf остаток общего
бюджета закончился после patch request; последующий необязательный local caller
был остановлен счётчиком до HTTP. Повторной номинации и hypothesis-запросов нет.

Vblf preflight сначала обнаружил недоступный внешний pytest tmp и четыре
дополнительных исходных падения. Tmp перенесён настройкой в workspace, полный
baseline зафиксирован до первого model call. Первая доставка затем корректно
отказала: `recorded_baseline_not_reproduced`. Старый intake использовал
`--assert=plain`; native acceptance — assertion rewriting, отчего отличался
failure signature. Повторный intake получил текущую подпись без изменения теста
или production-кода. V2 заново объявлен, использовал оставшийся бюджет и принят.
Это ручное исправление протокола, не полностью автономный успех первой попытки.

Первый audit точных nodeid обнаружил разный workspace-префикс копий vblf.
При пересчёте удалён только известный путь соответствующей копии, проверена
уникальность nodeid; исходные pytest reports и неуспешный audit сохранены.

## Evidence и следующий этап

Основной каталог: `artifacts/causal_trials/direct_transfer_20260914/`.
`transfer_audit.json` содержит проверки, результаты и SHA256 исходных receipts.
Для humanize, vblf, vblf_protocol_v2 сохранены declarations, transcripts, transport
attempts, telemetry, result и source checks; первая попытка vblf не удалена.
`role_scores_calibration.json`, `role_scores_training_replay.json`,
`vblf_first_attempt_scores.json` — численные измерения.
`*_normalized_identity.json` — полные идентичности проверок.

Handoff: `artifacts/verification/development_stage_direct_transfer_20260914.json`;
финальная проверка: `artifacts/verification/direct_transfer_final_audit_20260914.json`.

Далее: до следующего оплачиваемого запроса согласовать native assertion mode
intake/acceptance и обнаруживать несовместимость локальным preflight; привести
первые три ролевых артефакта к проверяемому контракту реально доставляемого direct
patch без выдуманных causal claims. Затем зафиксировать новый CLI/library набор
и неизменённые критерии независимой оценки. Map по-прежнему отложен.
