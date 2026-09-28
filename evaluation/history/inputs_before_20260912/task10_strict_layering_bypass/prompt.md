# Prompt

## Original Prompt

Compare strict layered routing against an explicitly declared bypass route for a simple supported task.

## Constraints

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

