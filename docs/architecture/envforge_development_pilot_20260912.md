# EnvForge: новый development-пилот и полнота native evidence

Дата: 12 сентября 2026. EnvForge выбран из локального корпуса по метаданным;
производственный upstream oracle не раскрывался решающей цепочке или ассистенту.
Результат после помощи ассистента: `experiment_validated`, native acceptance
для пяти падений passed, полная Linux-suite **85 passed**, финальный Reviewer
`approve`. Это учебный ремонт, не независимый holdout и не основание для 9.7+.

## Выбор и сохранённые попытки

Все receipts находятся в `artifacts/causal_trials/development_pilot_20260912/`.

- `selection.json`, `filtered_index.json`, `mining.json`: ограниченная выборка
  по локальной нешаллоу Git-истории, текущему exposure и резервам. Из 24 строк
  после исключений проверены 22; найден один CLI-кандидат, библиотечных — ноль.
  Общий статус mining — shortage. Это не готовый независимый набор.
- Origin: `https://gitlab.com/mimir-tech/envforge.git`; baseline
  `72fd855a9747ea2441a6b6715fb72421356fb6d6`. Fork ancestry независимо не установлена.
  Проект теперь consumed development; возвращать его в fresh holdout нельзя.
- `freeze.json` и `freeze_v2.json`: baseline archive и upstream test-only overlay.
  Первая подготовка ошибочно приняла отсутствие эффекта `git apply` внутри
  вложенного каталога за успех. До запуска ролей тесты восстановлены точными Git
  blobs; проверены четыре изменённых тестовых файла. Первая запись сохранена.
- `intake.json`, `first_attempt.json`: исходный набор — **68 passed / 1 failed**,
  Unix file mode в Windows. Intake `reproducible_unbound_failure`; общая попытка
  остановлена, ремонт не допущен. Исторический upstream fix не квалифицирован.
- Затем ассистент прочитал baseline и обнаружил другой дефект: запрос
  `/app/host/missing` возвращал scalar `/app/host`, хотя API обещает default
  для отсутствующего пути. `path_case_freeze.json` фиксирует авторство нового
  диагностического теста; production-код до первой попытки не исправлялся.
- `path_case_intake.json`, `path_case_first_attempt.json`: падения повторены,
  target `src/envforge/store.py:EnvConfigStore._get_literal`. Цепочка согласовала
  target, но завершилась `research_required/no_verified_failure_reducer`.
- `path_case_trained_attempt.json`: после добавленного ассистентом оператора
  patch подготовлен, но acceptance и полная Windows-suite не прошли. Этот receipt
  сохранён и не переименован в успешный. Полный исходный Windows baseline отдельно
  дал **77 passed / 8 failed**, исправленная копия — **82 passed / 3 failed**:
  оставшиеся три nodeid уже падали до patch (Unix mode и YAML с Windows-путями).
- `linux_intake_v2.json`, `linux_trained_attempt.json`, `linux_execution/`:
  Python **3.13.15**, пять baseline failures, paired acceptance passed,
  полная suite **85 passed**, Reviewer **approve**, source/COS changes во время
  выполнения отсутствуют. Версии зависимостей и source inventory находятся в receipt.

Linux-подготовка потребовала исправить разделители Windows-пути в artifact manifest
и запускать модули из копии COS в той же разрешённой области, что и кандидат.
Первый scoped Inspect отказал корректно. Один запуск не состоялся из-за тайм-аута
автоматической проверки разрешения; разрешённый повтор выполнен. Эти остановки
не считаются падениями продукта. Корпус не изменялся; сетевых вызовов LLM — ноль.
Зависимости скачаны отдельно и установлены в WSL из локальных wheels.

## Что изменено в COS

`programmer_mapping_descent_patch.py` предлагает ограниченный AST-ремонт: проверять
тип текущего узла перед каждым шагом и возвращать значение только после полного
прохода пути. Оператор требует точной поддержанной формы и обычных `dict/isinstance`;
неподдержанные выражения, декораторы и обнаруженное затенение встроенных функций
отклоняются. Включён через существующий `training_only` маршрут. Он не доказывает
универсальную способность диагностировать обходы словаря и не меняет исходный проект.

Перенос выявил ошибку самого COS: `project_native_failure_binding.py` подписывал
полный набор падений, но передавал только четыре nodeid. На пяти параметрах replay
не мог повторить подписанный baseline. Теперь передаются все nodeid в пределах
лимита восемь; превышение числа или длины явно блокирует квалификацию. Packet с
более чем восемью падениями остаётся partial. Регрессия включает настоящий paired
subprocess replay с пятью параметрами, превышение восьми и длинный nodeid.
До исправления четыре проверки падали: `artifacts/verification/failure_set_baseline_20260912.xml`.

## Что показали роли

| Роль | Первая попытка с диагностическим тестом | После вмешательства ассистента |
|---|---|---|
| Analyzer | Получил source-bound failure target | Тот же target и полные пять nodeid |
| Architect | Согласовал ограниченную область | Принял предоставленный training repair design |
| SpecWriter | Сформировал связанный контракт | Сохранил missing-path/default и regression obligations |
| Implementer / Programmer | Ремонт остановлен: нет reducer | Подготовил patch существующим маршрутом с новым оператором |
| Tester | Подготовил план, ремонта ещё нет | Paired native replay и полная Linux regression passed |
| Reviewer | Planning review; успешного ремонта нет | Окончательное approve по результатам и source hashes |

Баллы не присваиваются: тест, причинная гипотеза и оператор разработаны ассистентом.
Этот пример подтверждает работоспособность механизма после обучения и показывает
конкретную границу автономности до обучения. Детерминированный Reviewer не является
независимым судьёй для сравнения маршрутов или сертификации.

## Проверки и следующий шаг

- Профильная регрессия COS: **97 passed**, `artifacts/verification/envforge_focused_20260912.xml`.
- `external_review.json`: отдельные assistant-authored проверки публичного `get`:
  исправление **7/7**, исходник **2/7**; три неверных patch отклонены. Проверяются
  default identity, отсутствие пути ниже scalar/list и сохранение leaf/subtree.
- Финальная регрессия, исходный snapshot, 400-line gate и handoff:
  `artifacts/verification/development_stage_envforge_20260912.json`.
- Архитектурный checkpoint: `artifacts/verification/canonical_envforge_20260912.json`.

Продолжать со второго development-кейса, на котором диагноз и fixture ещё не
подготовлены ассистентом. Сначала зафиксировать попытку текущего COS, затем помощь.
Отдельный независимый CLI/library holdout требует новых manifests и проверки lineage;
EnvForge, RPC и vblf для него уже непригодны. Не добавлять узкие операторы как замену
измерению переноса. Gateway/cost evidence, независимый judge и полный TCP CI остаются
отдельными открытыми требованиями.
