# Чтение helper recipes — 16 сентября 2026

После выделения четырёх владельцев каждый отдельный getter собирал весь каталог.
Recovery и differential verifier вызывали четыре getter подряд. Теперь
`runtime.patch_synthesis_policy.helper_extraction_recipes` получает один живой
составной каталог и возвращает прежний упорядоченный набор доступных рецептов.
Его используют development lookup, recovery selection и differential verification.

| Граница | Чтений всего каталога до | После |
|---|---:|---:|
| Поиск development recipe | 4 | 1 |
| Выбор recovery recipe | 4 | 1 |
| Выбор differential recipe | 4 | 1 |

В development остаются два отдельных чтения на рассматриваемый кандидат:
поиск рецепта и admission recovery. Следующий кандидат читает каталог заново;
verifier также выполняет собственное чтение. Результат не кешируется между
вызовами и не передаётся как обход admission. Каждый вклад по-прежнему проходит
registered identity/lifecycle/schema/code checks; исполнение proposal отдельно
проверяет его владельца. Это не атомарный снимок всех файлов при конкурентном
изменении установки — такой гарантии прежний загрузчик также не давал.

Сохранены порядок append/dumps/loads/splitlines, disabled/missing semantics,
отказы при дубликатах, выбор единственного кандидата, sandbox, compile, metadata,
digest и полномочия применения. Плагины, KB, registry и алгоритмы не менялись.
Число обходов уменьшилось на 75%; это не измерение ускорения всего pipeline,
качества ремонта или экономии модельных токенов.

Профильные проверки: **63 passed**, включая полное сравнение 18 frozen recovery
packages и 12 новых проверок чтений, порядка, KB refresh и отказов при изменении
регистрации/KB между кандидатами и перед verification.

Доказательства:

- `artifacts/verification/helper_recipe_reads_begin_20260916.json`
- `artifacts/verification/helper_recipe_reads_20260916/before.json`
- `artifacts/verification/helper_recipe_reads_20260916/after.json`
- `artifacts/verification/helper_recipe_reads_focused_20260916.xml`
- `artifacts/verification/helper_recipe_reads_architecture_20260916.json`
- `artifacts/verification/helper_recipe_reads_packages_20260916.log`
- `artifacts/verification/development_stage_helper_recipe_reads_20260916.json`
- `artifacts/verification/helper_recipe_reads_final_audit_20260916.json`

В измерении числа чтений использован frozen extractor fixture: differential
runner отклонял его и до, и после изменения. Это не успешная native-проверка;
положительные differential scenarios покрывает профильная регрессия этапа.

Далее: составить карту владельцев planning/research recognition и выбрать один
ограниченный перенос с проверкой сохранения результатов. Вопрос о разработке
`F:/ubuntu/test/map` оценён по [сохранённому прогону](map_assessment_20260913.md):
0 patches, ошибочная identity/scope, пропущенные NaN/Infinity. Самостоятельное
развитие map не подтверждено; первый кандидат — явный finite-bbox контракт,
внешние тесты map/events/export и ограниченный ремонт в копии. Исходники map и
модельные бюджеты этот этап не затрагивает. Оценки ролей не повышаются.
