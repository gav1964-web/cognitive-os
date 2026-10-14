# Prompt

## Original Prompt

Сделай локальную FastAPI-службу, которая принимает CSV, валидирует колонки, считает агрегаты, сохраняет JSON-отчёт и имеет README, тесты и команду запуска.

## Constraints

- Allowed tools: local package generation and local tests.
- Allowed network access: none beyond local test server.
- Allowed dependencies: FastAPI, pytest and ordinary local test dependencies.
- Source mutation policy: generated package or sandbox only.

## Expected Inputs

- HTTP request containing CSV data or uploaded CSV file.
- Required column list declared by the implementation.

## Expected Outputs

- JSON API response with aggregate results.
- Saved JSON report.
- README with run/test commands.
- Automated tests for valid CSV, missing column and malformed CSV.

## Success Criteria

- Exposes a documented FastAPI endpoint.
- Validates required columns.
- Produces deterministic aggregate JSON.
- Saves a report file in a controlled path.
- Includes runnable tests and README.

## Known Ambiguities

- Exact aggregate fields may vary but must be documented and tested.

