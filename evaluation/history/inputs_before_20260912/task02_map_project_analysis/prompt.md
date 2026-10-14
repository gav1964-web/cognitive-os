# Prompt

## Original Prompt

Проанализировать проект `F:\ubuntu\test\map` и дать предложения по архитектурным улучшениям.

## Constraints

- Allowed tools: read-only project analysis, local runtime tools, non-mutating tests.
- Allowed network access: none required.
- Allowed dependencies: existing repository dependencies only.
- Source mutation policy: source project must remain unchanged.

## Expected Inputs

- Project directory: `F:\ubuntu\test\map`.
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

