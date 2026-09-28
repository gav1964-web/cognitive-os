# task23_supervisord_docs

## Prompt

Восстанови фактический пользовательский контракт проекта и подготовь README с установкой, конфигурацией, примером и диагностикой ошибок.

## Constraints

- Use Python 3.10+; generation and verification run in a fresh output directory, with no changes to frozen inputs.
- No network from produced programs or tests. Model inference may use the configured local gateway only; record every model attempt.
- No package installation during a route. Use the frozen available dependencies; report missing optional adapters explicitly.
- Per route budget: 20 model calls, 120000 reported total tokens, 900 seconds; record unknown usage as unknown, never invent zero cost.
- All routes receive these same constraints and input bytes. Log every clarification, manual edit and retry; none are supplied silently.


- No network
- Treat the input tree as read-only
- Do not claim unsupported compatibility

## Expected Inputs

- Frozen Python project tree

## Success Criteria

- Documented behavior matches implementation
- Installation and configuration are reproducible
- Example uses the real public interface
- Failure modes are evidence-backed
- Source tree remains unchanged
