# task25_amazon_tool_test_change

## Prompt

В отдельной копии найди один подтверждаемый тестами дефект на границе ввода или конфигурации, исправь его минимально и предоставь regression evidence.

## Constraints

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
