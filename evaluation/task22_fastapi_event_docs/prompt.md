# task22_fastapi_event_docs

## Prompt

Проведи evidence-based аудит документации проекта и подготовь улучшенный README для нового разработчика без изменения исходного кода.

## Constraints

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
