# task25_amazon_tool_test_change

## Prompt

В отдельной копии найди один подтверждаемый тестами дефект на границе ввода или конфигурации, исправь его минимально и предоставь regression evidence.

## Constraints

- Use Python 3.10+; generation and verification run in a fresh output directory, with no changes to frozen inputs.
- No network from produced programs or tests. Model inference may use the configured local gateway only; record every model attempt.
- No package installation during a route. Use the frozen available dependencies; report missing optional adapters explicitly.
- Per route budget: 20 model calls, 120000 reported total tokens, 900 seconds; record unknown usage as unknown, never invent zero cost.
- All routes receive these same constraints and input bytes. Log every clarification, manual edit and retry; none are supplied silently.


- No network
- Never mutate the frozen input
- Do not invent a defect
- Block with evidence if no bounded defect can be established

## Expected Inputs

- Frozen Python project tree

## Success Criteria

- Defect is tied to concrete source evidence
- A failing regression test precedes or demonstrates the fix
- Patch is minimal and preserves unrelated behavior
- Relevant tests pass
- Frozen input remains unchanged
