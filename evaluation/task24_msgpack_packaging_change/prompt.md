# task24_msgpack_packaging_change

## Prompt

В отдельной копии модернизируй packaging-конфигурацию проекта, сохранив публичное поведение, и докажи сборку и установку локальными проверками.

## Constraints

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
