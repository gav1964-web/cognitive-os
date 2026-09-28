# Prompt

## Original Prompt

Compare strict layered routing against an explicitly declared bypass route for a simple supported task.

## Constraints

- Use Python 3.10+; generation and verification run in a fresh output directory, with no changes to frozen inputs.
- No network from produced programs or tests. Model inference may use the configured local gateway only; record every model attempt.
- No package installation during a route. Use the frozen available dependencies; report missing optional adapters explicitly.
- Per route budget: 20 model calls, 120000 reported total tokens, 900 seconds; record unknown usage as unknown, never invent zero cost.
- All routes receive these same constraints and input bytes. Log every clarification, manual edit and retry; none are supplied silently.
- Use task15_uppercase_cli; bypass is a declared direct generation/verification path. Compare it with strict routing; record which orchestration steps were skipped. Default COS policy stays unchanged.


- Allowed tools: local runtime tools, evaluation reports.
- Allowed network access: none required.
- Allowed dependencies: existing repository dependencies only.
- Source mutation policy: generated package or sandbox only.

## Expected Inputs

- One simple supported task prompt.
- Route A: explicit bypass route that skips at least one orchestration layer.
- Route B: strict Cognitive OS layered route.

## Expected Outputs

- Quality, speed, source-safety and traceability comparison.
- Decision on whether bypass should remain experimental, be promoted for this task class, or be rejected.

## Success Criteria

- Bypass is declared and logged, not implicit.
- Both routes use the same original prompt and constraints.
- Source safety and artifact traceability are measured.
- Result does not weaken default safety policy without evidence.

## Known Ambiguities

- A bypass may be better for trivial tasks but unsafe for project-change tasks.


## Frozen Input Location

artifacts/evaluation_inputs/20260912/workloads/task10_strict_layering_bypass
