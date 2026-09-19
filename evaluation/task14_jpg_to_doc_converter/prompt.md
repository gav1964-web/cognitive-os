# task14_jpg_to_doc_converter

## Prompt

Напиши CLI для конвертации .jpg в .doc.

## Success Criteria

- Format ambiguity is surfaced
- Fallback path is explicit
- README documents limitations

## Constraints

- Use Python 3.10+; generation and verification run in a fresh output directory, with no changes to frozen inputs.
- No network from produced programs or tests. Model inference may use the configured local gateway only; record every model attempt.
- No package installation during a route. Use the frozen available dependencies; report missing optional adapters explicitly.
- Per route budget: 20 model calls, 120000 reported total tokens, 900 seconds; record unknown usage as unknown, never invent zero cost.
- All routes receive these same constraints and input bytes. Log every clarification, manual edit and retry; none are supplied silently.
- page.jpg is the input. .doc means legacy Word binary format, not .docx and not HTML renamed .doc.
- If no real .doc writer exists, return a controlled block and document an explicit opt-in alternative; never silently change the requested format.

## Frozen Input Location

artifacts/evaluation_inputs/20260912/fixtures
