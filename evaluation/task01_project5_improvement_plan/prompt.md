# Prompt

## Original Prompt

Проанализировать проект `artifacts/evaluation_inputs/20260912/project5` и дать предложения по улучшению.

## Constraints

- Use Python 3.10+; generation and verification run in a fresh output directory, with no changes to frozen inputs.
- No network from produced programs or tests. Model inference may use the configured local gateway only; record every model attempt.
- No package installation during a route. Use the frozen available dependencies; report missing optional adapters explicitly.
- Per route budget: 20 model calls, 120000 reported total tokens, 900 seconds; record unknown usage as unknown, never invent zero cost.
- All routes receive these same constraints and input bytes. Log every clarification, manual edit and retry; none are supplied silently.
- Only the frozen selected source tree is in scope; omissions and unavailable live behavior must be stated.


- Allowed tools: read-only project analysis, local runtime tools, tests that do not mutate the source project.
- Allowed network access: none required.
- Allowed dependencies: existing repository dependencies only.
- Source mutation policy: source project must remain unchanged.

## Expected Inputs

- Project directory: `artifacts/evaluation_inputs/20260912/project5`.
- User goal: improvement-oriented architectural analysis.

## Expected Outputs

- Project purpose and boundaries.
- Entrypoints and execution path.
- Core logic vs adapters/tests/legacy/noise.
- Capability candidates and broad-function candidates.
- Contract/data observations.
- Error/state/reproducibility risks.
- Prioritized improvement plan.

## Success Criteria

- Finds concrete source-backed improvement themes.
- Separates facts from architectural judgments.
- Does not propose automatic source edits.
- Records evidence links or file references.
- Produces comparable direct-agent and Cognitive OS artifacts.

## Known Ambiguities

- The exact quality threshold for "good proposals" is judgment-based and must be scored by rubric.


## Frozen Input Location

artifacts/evaluation_inputs/20260912/project5
