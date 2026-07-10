# Prompt

## Original Prompt

Compare full Cognitive OS role separation against a merged-role baseline for a bounded software task.

## Constraints

- Allowed tools: local role pipeline, local deterministic baselines, evaluation reports.
- Allowed network access: none required.
- Allowed dependencies: existing repository dependencies only.
- Source mutation policy: no source edits from this evaluation.

## Expected Inputs

- One existing evaluation task selected as the workload.
- Route A: merged-role or reduced-role baseline.
- Route B: full role pipeline.

## Expected Outputs

- Metrics for artifact completeness, missed requirements, review blockers, repair cycles and runtime overhead.
- Decision on whether full role separation adds measurable value for the workload.

## Success Criteria

- Uses the same original task prompt for both routes.
- Records which roles were merged or skipped.
- Does not score conversation quality as artifact quality.
- Produces a clear keep/simplify recommendation.

## Known Ambiguities

- Some roles may be useful only for specific task classes, so results must not be overgeneralized.

