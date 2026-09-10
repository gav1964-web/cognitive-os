# Evidence: контракты и доказательства

Назначение: связывать артефакт с содержимым, проверять schema и отделять
измеренные результаты от утверждений.

Начинать с `runtime/evidence_ledger.py`, `runtime/schema.py`, `runtime/models.py`.
JSON контракты лежат в `registry/interface_contracts.json` и plugin schemas.
JSON Schema использует jsonschema; ограниченный fallback должен отказывать на
неподдерживаемых конструкциях, а не пропускать их.

Зависимости: эта область не должна получать ответственность за роли или mining.
У пакета Replay есть собственные маленькие helpers canonical digest/path; они
не импортируют evidence ledger и не образуют универсального пакета «core».

Проверки: evidence_ledger, schema и соответствующие consumer contract tests.
Разные строки producer/evaluator fingerprint сами по себе не аутентифицируют
участников и не доказывают независимость оценки. Digest показывает целостность
содержимого; качество решения требует подходящей независимой проверки.
