# Verdict

## Summary

Evaluation completed on 2026-07-11 and rerun on 2026-07-13 after source-strata filtering, purpose extraction, recommendation and target-sketch fixes.

Final verdict: no clear winner. Direct inspection is still more concise and explains the GigaChat/import boundary more naturally, but Cognitive OS now gives comparable coverage with stronger artifacts, safety trace, source-strata filtering and a target architecture sketch.

Cognitive OS produced stronger typed artifacts, preserved source safety and selected a good first capability target (`app.py:parse_bbox`). After the fixes, it no longer polluted active execution evidence with `map_install_package/*`, it inferred the project as `Offline Kursk Map Package`, added improvement recommendations, restored code-area breakdown and added `Target Architecture Sketch`.

## Where Cognitive OS Helped

- Preserved source immutability and registry safety.
- Produced ADR, TechnicalSpec, ImplementationPlan, TestPlan and ReviewFindings.
- Selected `app.py:parse_bbox` as a safe bounded extraction target and kept it consistent through implementation/test/review.
- Surfaced risks around large artifacts, risky imports and unpinned dependencies.
- Excluded packaged-copy runtime commands and central nodes from active execution evidence after rerun.
- Added structured recommendations for hidden orchestrators, process boundaries, idempotency/replay and quarantine policy.
- Added target architecture sketch: thin entrypoints, API/web boundary, application services, explicit data lifecycle, adapters and state checkpoints.

## Where Direct Agent Helped

- Better identified real product purpose: offline Kursk Flask/Leaflet map with vector roads, incidents, branches/ATMs and search.
- Better identified operational entrypoints: `RUN_MAP.bat`, `app.py`, `REBUILD_INCIDENTS.bat`, `REBUILD_BRANCHES_ATMS.bat`, `import_indoc.py`.
- Better described the `import_indoc.py` pipeline and direct GigaChat provider boundary.
- Produced more compact human prose around the import/GigaChat boundary.

## No Clear Difference

- Both routes preserved source immutability.
- Both recognized `app.py:parse_bbox` as a useful first extraction target.
- Neither route executed live GigaChat/Nominatim calls or ran the map server.

## Open Risks

- This is one map-like project and should not be generalized to all project-analysis tasks.
- Direct route is still produced in the same Codex session, not by an independent human reviewer.
- Cognitive OS still needs a clearer target-module proposal section, not just evidence-driven recommendations.
- Provider-boundary behavior was only statically analyzed; no live GigaChat/Nominatim call was executed.

## Decision

`no_clear_difference`
