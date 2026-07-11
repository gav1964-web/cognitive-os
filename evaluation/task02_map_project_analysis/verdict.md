# Verdict

## Summary

Evaluation completed on 2026-07-11. Cognitive OS was rerun after source-strata filtering and purpose/recommendation fixes.

The direct route still wins, but only narrowly after the rerun. It produced a clearer target architecture narrative and better explained the desired module split for the Flask/Leaflet map app, data rebuild scripts and RTF/GigaChat import pipeline.

Cognitive OS produced stronger typed artifacts, preserved source safety and selected a good first capability target (`app.py:parse_bbox`). After the fixes, it no longer polluted active execution evidence with `map_install_package/*`, it inferred the project as `Offline Kursk Map Package`, and it added improvement recommendations. Its remaining weakness is concise architectural synthesis.

## Where Cognitive OS Helped

- Preserved source immutability and registry safety.
- Produced ADR, TechnicalSpec, ImplementationPlan, TestPlan and ReviewFindings.
- Selected `app.py:parse_bbox` as a safe bounded extraction target and kept it consistent through implementation/test/review.
- Surfaced risks around large artifacts, risky imports and unpinned dependencies.
- Excluded packaged-copy runtime commands and central nodes from active execution evidence after rerun.
- Added structured recommendations for hidden orchestrators, process boundaries, idempotency/replay and quarantine policy.

## Where Direct Agent Helped

- Better identified real product purpose: offline Kursk Flask/Leaflet map with vector roads, incidents, branches/ATMs and search.
- Better identified operational entrypoints: `RUN_MAP.bat`, `app.py`, `REBUILD_INCIDENTS.bat`, `REBUILD_BRANCHES_ATMS.bat`, `import_indoc.py`.
- Better described the `import_indoc.py` pipeline and direct GigaChat provider boundary.
- Produced a clearer target architecture narrative around splitting `app.py`, isolating import jobs, packaging importer components, idempotent rebuilds and tests.

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

`direct_agent_wins`
