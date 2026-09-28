# Prompt

## Original Prompt

Compare full Cognitive OS role separation against a merged-role baseline for a bounded software task.

## Constraints

- Use Python 3.10+; generation and verification run in a fresh output directory, with no changes to frozen inputs.
- No network from produced programs or tests. Model inference may use the configured local gateway only; record every model attempt.
- No package installation during a route. Use the frozen available dependencies; report missing optional adapters explicitly.
- Per route budget: 20 model calls, 120000 reported total tokens, 900 seconds; record unknown usage as unknown, never invent zero cost.
- All routes receive these same constraints and input bytes. Log every clarification, manual edit and retry; none are supplied silently.
- Use task15_uppercase_cli as the workload; compare merged planning/review against the configured full chain. Record skipped roles and actual model usage. No quality scores from the executors.


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


## Frozen Input Location

artifacts/evaluation_inputs/20260912/workloads/task07_role_pipeline_ablation
