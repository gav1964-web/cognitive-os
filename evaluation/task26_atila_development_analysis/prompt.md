# task26_atila_development_analysis

## Prompt

Проанализируй проект как развиваемый Python-продукт: восстанови архитектуру, найди приоритетные недостатки и предложи проверяемую последовательность развития.

## Constraints

- Use Python 3.10+; generation and verification run in a fresh output directory, with no changes to frozen inputs.
- No network from produced programs or tests. Model inference may use the configured local gateway only; record every model attempt.
- No package installation during a route. Use the frozen available dependencies; report missing optional adapters explicitly.
- Per route budget: 20 model calls, 120000 reported total tokens, 900 seconds; record unknown usage as unknown, never invent zero cost.
- All routes receive these same constraints and input bytes. Log every clarification, manual edit and retry; none are supplied silently.


- No network
- Treat the input tree as read-only
- Do not infer maturity from file counts alone

## Expected Inputs

- Frozen Python project tree

## Success Criteria

- Architecture and entrypoints cite source evidence
- Risks distinguish facts from hypotheses
- Recommendations are project-specific and prioritized
- Each top action has an acceptance check
- No source mutation occurs
