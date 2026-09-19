# task21_fastapi_durable_jobs

## Prompt

Создай локальную FastAPI-службу постановки фоновых заданий: идемпотентная постановка, получение статуса, отмена и восстановление очереди после перезапуска.

## Constraints

- Use Python 3.10+; generation and verification run in a fresh output directory, with no changes to frozen inputs.
- No network from produced programs or tests. Model inference may use the configured local gateway only; record every model attempt.
- No package installation during a route. Use the frozen available dependencies; report missing optional adapters explicitly.
- Per route budget: 20 model calls, 120000 reported total tokens, 900 seconds; record unknown usage as unknown, never invent zero cost.
- All routes receive these same constraints and input bytes. Log every clarification, manual edit and retry; none are supplied silently.


- No network services
- SQLite or filesystem persistence only
- Generated package or sandbox only
- No placeholder functions

## Expected Inputs

- An empty writable workspace

## Success Criteria

- API contract covers create, status and cancel
- Idempotency is tested
- Restart recovery is demonstrated
- Invalid transitions fail explicitly
- README contains exact run and test commands
