# task12_rotated_image_table

## Prompt

Доработай CLI распознавания табличной картинки: что произойдет, если изображение повернуто на 90 градусов?

## Success Criteria

- Rotation behavior is explicit
- Failure mode is tested
- No fabricated OCR claims

## Constraints

- Use Python 3.10+; generation and verification run in a fresh output directory, with no changes to frozen inputs.
- No network from produced programs or tests. Model inference may use the configured local gateway only; record every model attempt.
- No package installation during a route. Use the frozen available dependencies; report missing optional adapters explicitly.
- Per route budget: 20 model calls, 120000 reported total tokens, 900 seconds; record unknown usage as unknown, never invent zero cost.
- All routes receive these same constraints and input bytes. Log every clarification, manual edit and retry; none are supplied silently.
- The input includes synthetic starter table_reader.py plus table.png and table90.png. Add explicit rotation handling to a copy of this starter.
- Test 0/90-degree behavior with an injectable backend and a controlled missing-OCR result. Do not claim real OCR from a stub.

## Frozen Input Location

artifacts/evaluation_inputs/20260912/fixtures
