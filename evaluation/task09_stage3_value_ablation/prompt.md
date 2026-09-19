# Prompt

## Original Prompt

Compare Stage 2 Verified System Package against Stage 3 Product Slice for one supported product-generation task. Determine whether Stage 3 reduces review cost or catches issues Stage 2 misses.

## Constraints

- Use Python 3.10+; generation and verification run in a fresh output directory, with no changes to frozen inputs.
- No network from produced programs or tests. Model inference may use the configured local gateway only; record every model attempt.
- No package installation during a route. Use the frozen available dependencies; report missing optional adapters explicitly.
- Per route budget: 20 model calls, 120000 reported total tokens, 900 seconds; record unknown usage as unknown, never invent zero cost.
- All routes receive these same constraints and input bytes. Log every clarification, manual edit and retry; none are supplied silently.
- Use the exact task15_uppercase_cli product and the same generated package for Stage 2 and Stage 3 views. Time review separately; do not infer lower review cost from artifact count.


- Allowed tools: local Stage 2/Stage 3 package generation, tests, review reports.
- Allowed network access: none required.
- Allowed dependencies: existing repository dependencies only.
- Source mutation policy: generated package or sandbox only.

## Expected Inputs

- One supported CLI or FastAPI product prompt.
- Stage 2 package output.
- Stage 3 product-slice output.

## Expected Outputs

- Stage 2 review result.
- Stage 3 review result.
- Comparison of missed scenarios, documentation drift, human review effort and release confidence.

## Success Criteria

- Uses same underlying generated package where possible.
- Measures added value rather than artifact count.
- Records whether Stage 3 found issues Stage 2 missed.
- Produces keep/optional/demote recommendation.

## Known Ambiguities

- Human review effort is approximate unless timed carefully.


## Frozen Input Location

artifacts/evaluation_inputs/20260912/workloads/task09_stage3_value_ablation
