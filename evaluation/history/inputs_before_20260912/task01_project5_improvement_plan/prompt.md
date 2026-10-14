# Prompt

## Original Prompt

Проанализировать проект `F:\ubuntu\test\5` и дать предложения по улучшению.

## Constraints

- Allowed tools: read-only project analysis, local runtime tools, tests that do not mutate the source project.
- Allowed network access: none required.
- Allowed dependencies: existing repository dependencies only.
- Source mutation policy: source project must remain unchanged.

## Expected Inputs

- Project directory: `F:\ubuntu\test\5`.
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

