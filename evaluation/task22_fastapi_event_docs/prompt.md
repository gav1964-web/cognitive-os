# task22_fastapi_event_docs

## Prompt

Проведи evidence-based аудит документации проекта и подготовь улучшенный README для нового разработчика без изменения исходного кода.

## Constraints

- Use Python 3.10+; generation and verification run in a fresh output directory, with no changes to frozen inputs.
- No network from produced programs or tests. Model inference may use the configured local gateway only; record every model attempt.
- No package installation during a route. Use the frozen available dependencies; report missing optional adapters explicitly.
- Per route budget: 20 model calls, 120000 reported total tokens, 900 seconds; record unknown usage as unknown, never invent zero cost.
- All routes receive these same constraints and input bytes. Log every clarification, manual edit and retry; none are supplied silently.


- No network
- Treat the input tree as read-only
- Cite source paths for non-obvious claims

## Expected Inputs

- Frozen Python project tree

## Success Criteria

- Commands and entrypoints are verified against source
- Configuration and dependencies are documented
- At least one minimal working example is included
- Unknown behavior is not invented
- Only documentation artifacts are produced
