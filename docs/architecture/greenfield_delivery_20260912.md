# Доставка greenfield CLI: 12 сентября 2026

Поддержанный uppercase CLI теперь проходит собственный greenfield-контур до
готовых файлов. Это расширение существующего bounded generator; универсальная
LLM-реализация новых проектов этим этапом не добавлена.

## Контракт и исполнение

`run_role_pipeline(..., mode="greenfield")` вызывает `runtime/greenfield_delivery.py`.
Режим по умолчанию `existing_project` сохраняет прежний configured workflow.
Greenfield не получает фиктивный ProjectMapReport и не ищет extraction candidate
в пустом каталоге. Его порядок:

1. Настоящие Architect/SpecWriter создают ProductArchitectureRecord и ProductTechnicalSpec.
2. `GreenfieldImplementationHandoff` связывает спецификацию с существующим
   SandboxImplementationPlan: interface, transform, expression и SHA-256.
3. `GreenfieldTestPlan` фиксирует требуемые файлы и полный набор внешних проверок.
4. Существующий sandbox programmer создаёт пакет и запускает compile/pytest.
5. Внешний verifier повторяет pytest и шесть CLI-проверок; GreenfieldDeliveryReview
   проверяет полноту, хеши и неизменность кода при тестировании.

В `config/greenfield_architecture_patterns.json` добавлен конкретный pattern
`uppercase_file_cli`. Он содержит исполнимый `delivery_recipe` главного контракта
и `acceptance_check_ids`. Generic architecture, другой интерфейс и несовпадение
операции блокируют реализацию. Расширять этот маршрут следует через явные
совместимые контракты и соответствующие проверки.

Это новые native greenfield handoff/review artifacts. Они не подменяют прежние
extraction-first ImplementationPlan/TestPlan/ReviewFindings и не притворяются
универсальным результатом той старой цепочки. Контрактная проверка не является
независимой оценкой всех требований произвольного prompt.

Реализация требует `write=True`, `run_executor=True` и внешнего verifier.
Выходной каталог должен быть новым или пустым, находиться под `root/artifacts`
и не проходить через ссылки/junctions. Существующие файлы не перезаписываются.
Отрицательные результаты сохраняются для review; они не становятся готовой доставкой.
Никакого продвижения в source/KB/registry нет. Подпроцессы работают с правами
текущего процесса; отдельный OS sandbox не появился.

CLI:

```powershell
python tools/greenfield_role_run.py --prompt "Напиши CLI .py, которая переводит текстовый файл в верхний регистр." --output-dir artifacts/greenfield_delivery/new_cli --write
```

CLI пока использует verifier поддержанного uppercase-контракта. Он отклоняет
совмещение доставки с generic-pattern/LLM-planning флагами, чтобы не расширять
допуск неявно. Планирование без `--output-dir` сохраняет прежнее поведение.

## Проверенные результаты и ошибки ассистента

- Первая интеграционная проверка: **21 passed, 1 failed**. Внешний CLI прошёл
  6/6, но общий pytest wrapper отключал project config и терял импорт из `src/`.
  Receipt сохранён: `artifacts/verification/greenfield_delivery_initial_20260912.xml`.
  Verifier теперь добавляет только корень output project и его `src/` в import
  path; установка пакета и произвольные project pytest options не требуются.
- После исправления прошли **44** фокусные проверки. После проверки совместимости
  CLI/document writer и прежнего pipeline — **61 passed**:
  `artifacts/verification/greenfield_delivery_tests_20260912.xml`.
- При подготовке pattern я сначала использовала строки в data_lifecycle вместо
  ожидаемых renderer записей. Формат исправлен и покрыт тестом реального writer.
  Избыточные metadata, которые builder не читает, удалены.
- Реальный route runner: `artifacts/evaluation_v2/routes_20260912T083955Z/summary.json`.
  **full_chain completed, собственный pytest 3, внешние проверки 6/6**.
  Native review approved, maintained sources не изменились. Более ранняя успешная
  проверка до уточнения metadata сохранена в `routes_20260912T083744Z`.
- Настоящий CLI entrypoint тоже доставил пакет:
  `artifacts/verification/greenfield_cli_delivery_20260912.json`;
  результат — `artifacts/greenfield_delivery/uppercase_cli_20260912/main.py`.

Маршрут имеет отдельное имя `native_greenfield_bounded_delivery.v1` и **0 вызовов LLM**.
Он не заменён коротким workspace agent. Изменение маршрута относительно предыдущего
этапа явно зафиксировано; старые неудачные попытки не переписаны. Checker и manifest
остались прежними. Это инженерная доставка известного сценария после доработки
ассистентом, а не свежий holdout и не доказательство преимущества COS.

Протокол v2 по-прежнему отклоняет draft: у символического пути нет истории вызовов
модели, а финансовые поля неизвестны. Даже после получения расходов у пользователя
нельзя автоматически объявить эту попытку сравнением на одной модели или вызвать
модель только ради заполнения журнала. Нужна задача с реальным участием модели либо
отдельно объявленный протокол для сравнения символических и LLM-маршрутов.

Точная версия исходников, финализация и выбранные регрессии:
`artifacts/verification/development_stage_greenfield_20260912.json`.
Linux: **43 passed**, receipt: `artifacts/verification/linux_greenfield_delivery_20260912.xml`.
Полный canonical suite не повторяется; выполняются preflight и связанные тесты.

Первый финальный regression snapshot прошёл 122 теста, но был отклонён по
`source_changed_during_verification`: старый test_role_pipeline_can_run_transform
перезаписывал maintained `generated/specs/simple_cli_tool_normalize_text.json`.
Сам spec writer сохранён; тест направляет его вывод во временный каталог и проверяет
байтовую неизменность maintained spec. Неуспешный receipt сохранён в
`artifacts/development/stage-d0edfb9688/report.json`; gate не ослаблен.
