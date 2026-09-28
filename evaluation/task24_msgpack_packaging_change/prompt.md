# task24_msgpack_packaging_change

## Prompt

В отдельной копии модернизируй packaging-конфигурацию проекта, сохранив публичное поведение, и докажи сборку и установку локальными проверками.

## Constraints

- Use Python 3.10+; generation and verification run in a fresh output directory, with no changes to frozen inputs.
- No network from produced programs or tests. Model inference may use the configured local gateway only; record every model attempt.
- No package installation during a route. Use the frozen available dependencies; report missing optional adapters explicitly.
- Per route budget: 20 model calls, 120000 reported total tokens, 900 seconds; record unknown usage as unknown, never invent zero cost.
- All routes receive these same constraints and input bytes. Log every clarification, manual edit and retry; none are supplied silently.


- No network
- Never mutate the frozen input
- Use only locally available build tools
- A controlled block is preferable to fabricated success

## Expected Inputs

- Frozen Python project tree

## Success Criteria

- Change is limited to a sandbox copy
- Build metadata is internally consistent
- Wheel or sdist build is verified
- Existing public imports remain usable
- No placeholder implementation is introduced
