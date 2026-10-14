# Prompt

## Original Prompt

Проанализировать проект `artifacts/evaluation_inputs/20260912/map` и дать предложения по архитектурным улучшениям.

## Constraints

- Use Python 3.10+; generation and verification run in a fresh output directory, with no changes to frozen inputs.
- No network from produced programs or tests. Model inference may use the configured local gateway only; record every model attempt.
- No package installation during a route. Use the frozen available dependencies; report missing optional adapters explicitly.
- Per route budget: 20 model calls, 120000 reported total tokens, 900 seconds; record unknown usage as unknown, never invent zero cost.
- All routes receive these same constraints and input bytes. Log every clarification, manual edit and retry; none are supplied silently.
- Only the frozen selected source tree is in scope; omissions and unavailable live behavior must be stated.


- Allowed tools: read-only project analysis, local runtime tools, non-mutating tests.
- Allowed network access: none required.
- Allowed dependencies: existing repository dependencies only.
- Source mutation policy: source project must remain unchanged.

## Expected Inputs

- Project directory: `artifacts/evaluation_inputs/20260912/map`.
- User goal: architecture and improvement analysis.

## Expected Outputs

- Project purpose and supported scenarios.
- Entrypoints and main execution path.
- Core logic vs interface/adapters/tests/noise.
- Capability extraction candidates.
- Risks around provider integration, state, idempotency and replay.
- Improvement plan with evidence.

## Success Criteria

- Identifies real entrypoints and provider-boundary risks.
- Avoids treating generated/scratch artifacts as core logic.
- Proposes bounded improvements rather than broad rewrites.
- Keeps source project read-only.

## Known Ambiguities

- Some provider behavior may require secrets or network and should be marked as unverified if not executed.


## Frozen Input Location

artifacts/evaluation_inputs/20260912/map
