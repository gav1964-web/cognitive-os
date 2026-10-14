# task11_image_contents_cli

## Prompt

Напиши CLI .py, которая перечислит содержимое картинки.

## Success Criteria

- CLI accepts image path
- Output is structured text
- No source tree mutation

## Constraints

- Use Python 3.10+; generation and verification run in a fresh output directory, with no changes to frozen inputs.
- No network from produced programs or tests. Model inference may use the configured local gateway only; record every model attempt.
- No package installation during a route. Use the frozen available dependencies; report missing optional adapters explicitly.
- Per route budget: 20 model calls, 120000 reported total tokens, 900 seconds; record unknown usage as unknown, never invent zero cost.
- All routes receive these same constraints and input bytes. Log every clarification, manual edit and retry; none are supplied silently.
- Return JSON with width, height, image format and declared backend status. Semantic object recognition requires a real optional backend; metadata alone must be labelled metadata-only.
- Check table.png, invalid.png and a missing path; never fabricate recognized objects.

## Frozen Input Location

artifacts/evaluation_inputs/20260912/fixtures
