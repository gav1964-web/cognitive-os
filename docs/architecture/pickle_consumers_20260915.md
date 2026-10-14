# Pickle: потребители контракта, 15 сентября 2026

Продолжение функционального разделения после `pickle_state_20260915.md`.
Четыре рабочих потребителя генератора используют типизированный клиент
`runtime/exception_pickle_contract.py` → зарегистрированный `propose_patch`.
Предметный алгоритм, активная KB и общий интерпретатор не изменены.

## Владение и границы

| Область | Владелец / текущая интеграция | Следующее действие |
|---|---|---|
| Предложение патча | `plugins/exception_pickle/src/patch.py`, manifest 0.1.1; единственная реализация | Алгоритмические улучшения отдельно |
| Разрешённое исполнение дизайна | `project_development_authorized_implementation` → клиент контракта | Сохранить authorization, sandbox и native gates |
| Active application, static risk, autonomous shadow | Три runtime-потребителя → тот же клиент | Корпус и эксперименты остаются ответственностью Research |
| Старый programmer patch API | Совместимый alias зарегистрированного клиента | Удалить после отказа downstream от старого import; рабочих runtime imports уже нет |
| Активная KB, profile, contrast, overlay | Локальная KB плагина, общий provider-протокол | Единственный редактируемый владелец сохраняется |
| Explicit research catalog / диагностика | Active application, blocker intelligence и config doctor ещё используют typed loader владельца с явным путём | Отделить проверку экспериментального документа от чтения установленной активной KB; не подменять одно другим |
| Подбор samples и классификация формы | `exception_pickle_constructor_samples`, `source_samples`, `object_contract_classifier` | Следующий кандидат на выделение: сначала контракт source → sample descriptor и карта импорта; исполнение replay отдельно |
| Semantic replay, аудит и независимая оценка | Research / Replay | Плагин не оценивает сам себя и не получает полномочия из своей регистрации |
| Promotion transaction | Research governance, запись каталога владельца под прежними guards | Отдельный write-contract; без автоматического обновления registry или обхода approvals |

Карта импортов 34 runtime-модулей, включая новый клиент:
`artifacts/verification/pickle_consumers_ownership_20260915.json`.
В частности, classifier сейчас импортирует sample helper через autonomous shadow:
эту обратную зависимость следует убрать при следующем выделении samples.
Все 33 исследовательских модуля целиком в плагин не переносились.

## Контракт и сохранение поведения

Клиент передаёт исходник, имя класса/конструктора и явный рецепт. Возвращает
тот же patch dict; только явный `not_applicable` с `patch: null` означает
нормальную неприменимость. Ошибки identity/lifecycle/schema и неверный ответ
операции распространяются как ошибки, без fallback к приватной функции.
Это дополнительная проверка допуска перед ранее существовавшим алгоритмом.
При исправной регистрации байты предложений и обычные отказы сохранены.

`competency_root` — корень установки COS, по умолчанию корень загруженного runtime.
`root` экспериментальных runners — корень исследовательских входов/проекта;
эти пути могут различаться. Регистрация проверяет установленный механизм,
но не объявляет экспериментальный рецепт активным знанием. Применение в исходный
проект, promotion и native/review условия этим клиентом не разрешаются.
При ошибке admission runner прекращается до записи патча и native replay;
уже созданная исходная копия sandbox может остаться для диагностики.

## Проверка

- `pickle_consumers_focused_20260915.xml`: 23 passed; предложения/отказы,
  старый alias, stale KB hash, карантин и остановка до изменения sandbox.
- `pickle_consumers_regression_20260915.xml`: 229 passed, включая application,
  shadow, evaluation/promotion, boundary feedback и registry.
- Финальный stage: `artifacts/verification/development_stage_pickle_consumers_20260915.json`.
  Он повторяет этот scope на снимке и проверяет обязательный лимит 400 строк.
- Проверка границ: `artifacts/verification/pickle_consumers_architecture_20260915.json`;
  пакеты: `artifacts/verification/pickle_consumers_packages_20260915.log`.
- Итоговые hashes/актуальность снимка:
  `artifacts/verification/pickle_consumers_final_audit_20260915.json`.

Рост качества и ролевых оценок не заявляется. Новых LLM-вызовов нет.
Добавлена стоимость registry-проверки к бывшим прямым вызовам; новые timings
не измерялись. Предыдущие 23–28 мс относятся к прежнему локальному замеру,
а не к гарантии производительности этого этапа.
