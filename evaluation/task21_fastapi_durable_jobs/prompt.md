# task21_fastapi_durable_jobs

## Prompt

Создай локальную FastAPI-службу постановки фоновых заданий: идемпотентная постановка, получение статуса, отмена и восстановление очереди после перезапуска.

## Constraints

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
