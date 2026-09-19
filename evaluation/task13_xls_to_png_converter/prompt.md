# task13_xls_to_png_converter

## Prompt

Напиши конвертер .xls в .png.

## Success Criteria

- Adapter boundary exists
- Missing dependencies are controlled
- Tests run without external files

## Constraints

- Use Python 3.10+; generation and verification run in a fresh output directory, with no changes to frozen inputs.
- No network from produced programs or tests. Model inference may use the configured local gateway only; record every model attempt.
- No package installation during a route. Use the frozen available dependencies; report missing optional adapters explicitly.
- Per route budget: 20 model calls, 120000 reported total tokens, 900 seconds; record unknown usage as unknown, never invent zero cost.
- All routes receive these same constraints and input bytes. Log every clarification, manual edit and retry; none are supplied silently.
- table.xls is a real BIFF8 workbook with Data/name/value. Produce PNG through an explicit XLS reader adapter; reject corrupt and missing inputs.
- A missing optional XLS reader must yield a documented controlled block, not a successful conversion claim. Positive conversion requires a real installed reader.

## Frozen Input Location

artifacts/evaluation_inputs/20260912/fixtures
