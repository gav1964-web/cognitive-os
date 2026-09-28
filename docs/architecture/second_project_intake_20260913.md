# Второй development-проект: отбор и остановка native intake

13 сентября 2026. Второй проект — **python-markdownify**. Исторический дефект
воспроизведён, но ремонт ещё не выполнен: COS останавливается до модели на
`reproducible_unbound_failure`. Это development evidence, не новый результат
ролей 9.7+ и не независимый holdout. Map остаётся отложенным.

## Что проверено

| Кандидат | Наблюдение | Receipt в `artifacts/causal_trials/` |
|---|---|---|
| python-slugify | В первых 120, затем 160 немержевых коммитах не выбрана пара production + native test delta | `second_project_20260913/selection_before_test_path_fix.json`, `selection.json`, `mining_diagnostics.json` |
| tomli | Статический admission не установил связь тестов с owned API; допуск не подменён ручным утверждением | `second_project_tomli_20260913/admission.json` |
| markdownify, case 01 | Наложены только исторические тесты; дважды 50 passed, дефект не воспроизведён | `second_project_markdownify_20260913/attempt_01_intake.json` |
| markdownify, case 02 | Дважды 48 passed / 1 failed в целевом модуле; после исправления диагностики дважды 80 passed / 1 failed во всей native suite | `second_project_markdownify_case02_20260913/attempt_01_intake.json`, `full_native_intake_after_import_fix.json` |

Новый поиск ограничен тремя Git-историями. Изначальный metadata-index проверен
на совпадения имён; Click, more-itertools и python-dotenv исключены как ранее
экспонированные. Отсутствие имени в этом index не доказывает глобальную
независимость или отсутствие знания проекта в обучении модели. Индексу не
приписывается `local_corpus_sufficient` с фиктивным fingerprint. Snapshot
fingerprint основан на реальном Git tree, вход исполнения — на хешах файлов.

В case 02 используется baseline `5122c973c1a0d4351e64f02e2782912afbada9ef`,
case ID `7bf52af60fe4e98d0bef`. Источник:
`https://github.com/matthewwithanm/python-markdownify.git`.
Заморожен Git archive родительской версии с test-only overlay
`tests/test_conversions.py`; production-исправление upstream осталось в sealed
oracle и не передавалось ассистенту или модели. Snapshot классифицирован как
library candidate; наличие CLI в историческом baseline не превращает этот
прогон в проверку CLI-поведения.

`freeze.json` в каталоге case 02 хранит baseline/overlay inventories и source
digest `sha256:93346db55f53ec66747c6fedb3ca2bdd30fa26a86e582fcb03fbd363d965086d`.
`attempt_01_cos_inventory.json` фиксирует COS перед первым intake;
`verified_intake_cos_inventory.json` — версию после изменения диагностики.
`full_native_source_check.json` подтверждает неизменность исходной копии и COS
во время финального native intake. Source-файлы markdownify не исправлялись.

## Изменения COS

1. Mining распознаёт `test.py` и относит `*_test.py` к тестам, включая корневые
   файлы. Изменение только теста не считается production-исправлением.
   Native regression поддерживает одиночный корневой `test.py`, как ранее
   `tests.py`, когда стандартных тестовых модулей нет. Этот общий пробел найден
   при отборе slugify; его устранение **не** обеспечило пригодного случая slugify.
2. Относительные импорты тестов разрешаются от пакета теста, включая `src/`,
   импорт модуля через `from . import ...` и переход к родительскому пакету.
   Выход выше пакета и отсутствие package-контекста не дают привязки.
   Совпадающее имя корневого модуля не перехватывает относительный импорт.
3. Для непрозрачного локального помощника сохраняется ограниченный source
   excerpt, импорты, границы строк и SHA256 файла. Поле `test_support_sources`
   имеет authority `diagnostic_only_not_a_production_target`. Код помощника
   не импортируется и не исполняется при статическом анализе; усечение явно
   отмечается. Цель ремонта по этому свидетельству не назначается.

В текущем случае тест вызывает `tests/utils.py:md`, который создаёт
`MarkdownConverter` и вызывает `.convert`. До изменения `md` ошибочно отмечался
как `external_dependency_call`, теперь — `test_support_call` с исходником.
Падение остаётся тем же: `tests/test_conversions.py::test_br` и signature
`be5c1284be460ea7e354ff428f2ed2d4eea9624fbc014d4b0ac6f2a8b25098b1`.
Это исправление происхождения вызова, **не** доказательство конкретной причины
дефекта внутри конвертера.

## Роли, вмешательства и расходы

| Роль / участок | Evidence этого этапа | Что не подтверждено |
|---|---|---|
| Analyzer / native intake | Реальный повторяемый сбой, правильное происхождение helper и связанные хеши | Выбор внутреннего production-метода через wrapper/instance dispatch |
| Architect | Диагностический контракт сохраняет границу между тестовым помощником и целью ремонта | Новый модельный дизайн ремонта не запускался |
| SpecWriter | Исходные native assertions сохранены | Новый исполняемый контракт ремонта не сформирован |
| Implementer / Tester / Reviewer | Проверены изменения COS и исходный дефект markdownify | Патч markdownify, успешная native suite и final Reviewer отсутствуют |

**0 вызовов моделей через Cognitive OS.** Файлы с префиксом `attempt_01` здесь
фиксируют попытки intake: assertions остановили runners до declaration/LLM IO.
Нельзя выдавать их за модельные попытки. Расходы этого Codex-диалога не измерены
этим счётчиком. Assistant выбрал проекты по метаданным, расширил поиск с 120
до 160 коммитов, заменил невоспроизводимый случай следующим, исправил COS и
прочитал тестовый helper. Механизм production-ремонта не задавался. Случаи уже
экспонированы для development; использовать их как untouched holdout нельзя.

## Проверки и следующий шаг

Focused regression: **96 passed**,
`artifacts/verification/second_project_final_focused_20260913.xml`.
Проверки охватывают отделение test-only изменений, относительные импорты,
совпадающие имена модулей, parent/src packages, хеши и усечение helper evidence,
существующие native assertions и unittest binding.

Финальный stage receipt:
`artifacts/verification/development_stage_second_project_20260913.json`.
Он фиксирует фактический итог расширенных регрессий и 400-line finalization;
до его успешного завершения этап не считается закрытым.

Следующая задача — на **этом же замороженном case 02** спроектировать ограниченную
проверяемую связь helper → созданный объект → owned method. Сначала нужны
негативные случаи неоднозначности, изменения входов/результата помощником и
переопределения метода; не назначать entrypoint местом дефекта автоматически.
После допуска сохранить первую фактическую модельную попытку и пройти точный
patch → полный native regression → final Reviewer. Повторный поиск проекта
или просмотр upstream production oracle сейчас не нужен. Пилот 6 CLI + 6 library
и независимая оценка остаются последующими задачами.
