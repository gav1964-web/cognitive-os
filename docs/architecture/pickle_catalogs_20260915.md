# Pickle: исследовательский документ и установленная KB, 15 сентября 2026

Плагин `exception_pickle` версии 0.3.0 разделяет чтение своей установленной KB
и проверку переданного исследовательского документа. Оба пути используют один
валидатор владельца с прежними schema/operator/safety правилами.

## Владение и контракты

| Потребитель / API | Откуда берутся данные | Что проверяется |
|---|---|---|
| `read_installed_patterns(competency_root=...)` | Локальная KB зарегистрированной установки | Registry identity, lifecycle, input/output schema и содержимое каталога |
| `validate_research_patterns(document, competency_root=...)` | Переданный объект; `None` означает отсутствие | Допуск установленного валидатора и прежние правила документа |
| `read_research_patterns(path, competency_root=...)` | Только явный путь потребителя, свежая загрузка | JSON parsing, затем `validate_patterns` через registry |
| Active application / blocker intelligence | Прежний каталог относительно research root | Проверка переданного документа; прежние outer gates |
| Config doctor | KB проверяемой установки через `patterns` | Никакой прямой загрузки внутреннего файла владельца |

Клиент — `runtime/exception_pickle_catalog_contract.py`. Операция плагина
`validate_patterns` принимает `document: object | null`, возвращает
`{status: ok, catalog: ...}`. Путь файла через эту операцию передать нельзя.
Чтение файла остаётся у runtime; валидатор получает deepcopy данных и не читает
установленный каталог. Общий dispatcher всё ещё вычисляет hash всей установки,
включая KB, для допуска кода; это не подстановка её содержимого в документ.

`ok` подтверждает структурную проверку документа. Поле `status: active` внутри
документа не является новым независимым доказательством или разрешением promotion.
Исследовательские consumers сохраняют свои прежние требования к применению,
native replay, source mutation и evidence. Проверка provenance не была частью
старого loader и не добавлена скрыто в ходе разделения.

## Сохранённое поведение

Отсутствующий исследовательский файл остаётся `absent`, даже если live KB активна.
Повреждённый JSON, неверные schema/lifecycle/operator и небезопасные flags
отклоняются. Неизвестные дополнительные поля разрешены как прежде; validation
не переписывает evidence и не повышает lifecycle. Повторный вызов читает изменённый
файл; возвращённые объекты не разделяют изменяемое состояние с входом.
Ошибки admission/контракта не обходятся прямым вызовом владельца.

`RESEARCH_CATALOG_PATH` фиксирует совместимое расположение существующих
исследовательских входов, не второй редактируемый источник live-знаний.
Корень этих входов и `competency_root` могут различаться. Внутренний owner-loader
с optional path сохранён для совместимости, но рабочих runtime-потребителей
его приватного API больше нет.

Генератор патча, sample algorithms, общий provider/interpreter и активная KB
не изменены. В двух исследовательских runners изменён только маршрут загрузки
каталога. Существующие validation statements совпадают по AST. Promotion
transaction сохранена побайтно; никакой рабочий каталог не продвигался.

## Проверки и следующий этап

- `artifacts/verification/pickle_catalogs_focused_20260915.xml`: 47 passed,
  включая разделение источников, freshness, негативные проверки, application,
  blocker intelligence и config doctor.
- Полный профиль и финальный size gate на снимке:
  `artifacts/verification/development_stage_pickle_catalogs_20260915.json`.
- Архитектура: `artifacts/verification/pickle_catalogs_architecture_20260915.json`.
- Пакеты: `artifacts/verification/pickle_catalogs_packages_20260915.log`.
- Hash/AST evidence: `artifacts/verification/pickle_catalogs_preservation_20260915.json`.
- Актуальность снимка и проверки локального корпуса:
  `artifacts/verification/pickle_catalogs_final_audit_20260915.json`.

Далее — карта подготовки promotion-документа и его разрешённой записи:
предметная сборка/валидация принадлежит компетенции, независимая оценка,
явное разрешение и транзакция записи остаются у governance. Сначала определить
этот контракт и проверить отказы; фактический promotion не является частью
структурной миграции. Обновление registry не должно происходить автоматически.
Ролевые оценки и качество ремонта этим этапом не повышаются; LLM-вызовов нет.
