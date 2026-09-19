# task16_project7_analysis

## Prompt

Проанализируй Python-проект 7 и дай предложения по развитию.

## Success Criteria

- Entrypoints detected
- Evidence refs exist
- Recommendations are project-specific

## Constraints

- Use Python 3.10+; generation and verification run in a fresh output directory, with no changes to frozen inputs.
- No network from produced programs or tests. Model inference may use the configured local gateway only; record every model attempt.
- No package installation during a route. Use the frozen available dependencies; report missing optional adapters explicitly.
- Per route budget: 20 model calls, 120000 reported total tokens, 900 seconds; record unknown usage as unknown, never invent zero cost.
- All routes receive these same constraints and input bytes. Log every clarification, manual edit and retry; none are supplied silently.
- Analyze only the provided project7 source snapshot; omitted machine data and live behavior remain unverified. Cite paths and separate facts from recommendations.

## Frozen Input Location

artifacts/evaluation_inputs/20260912/project7
