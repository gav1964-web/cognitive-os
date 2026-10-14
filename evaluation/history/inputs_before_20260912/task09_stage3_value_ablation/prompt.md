# Prompt

## Original Prompt

Compare Stage 2 Verified System Package against Stage 3 Product Slice for one supported product-generation task. Determine whether Stage 3 reduces review cost or catches issues Stage 2 misses.

## Constraints

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

