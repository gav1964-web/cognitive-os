# task15_uppercase_cli

## Prompt

Напиши CLI .py, которая переводит текстовый файл в верхний регистр.

## Success Criteria

- Input/output paths
- Deterministic transform
- pytest coverage

## Constraints

- Use Python 3.10+; generation and verification run in a fresh output directory, with no changes to frozen inputs.
- No network from produced programs or tests. Model inference may use the configured local gateway only; record every model attempt.
- No package installation during a route. Use the frozen available dependencies; report missing optional adapters explicitly.
- Per route budget: 20 model calls, 120000 reported total tokens, 900 seconds; record unknown usage as unknown, never invent zero cost.
- All routes receive these same constraints and input bytes. Log every clarification, manual edit and retry; none are supplied silently.
- CLI contract: python main.py INPUT OUTPUT; UTF-8, Python str.upper semantics, preserve line endings, standard library only.
- Reject missing input, invalid UTF-8 and identical input/output paths with nonzero exit; do not change input or existing output on rejection.
- Include README and pytest tests. Positive cases include Cyrillic, Straße, empty text and CRLF.

## Frozen Input Location

artifacts/evaluation_inputs/20260912/fixtures
