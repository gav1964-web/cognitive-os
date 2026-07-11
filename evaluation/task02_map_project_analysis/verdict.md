# Verdict

## Summary

Evaluation completed on 2026-07-11.

The direct route wins with moderate confidence. It produced a fuller architecture analysis of the Flask/Leaflet map app, data rebuild scripts, RTF/GigaChat import pipeline, state/side effects and packaged-copy noise.

Cognitive OS produced stronger typed artifacts, preserved source safety and selected a good first capability target (`app.py:parse_bbox`). However, it polluted active architecture evidence with `map_install_package/*` entries and remained too extraction-oriented for a broad architecture-improvement prompt.

## Where Cognitive OS Helped

- Preserved source immutability and registry safety.
- Produced ADR, TechnicalSpec, ImplementationPlan, TestPlan and ReviewFindings.
- Selected `app.py:parse_bbox` as a safe bounded extraction target and kept it consistent through implementation/test/review.
- Surfaced risks around large artifacts, risky imports and unpinned dependencies.

## Where Direct Agent Helped

- Better identified real product purpose: offline Kursk Flask/Leaflet map with vector roads, incidents, branches/ATMs and search.
- Better identified operational entrypoints: `RUN_MAP.bat`, `app.py`, `REBUILD_INCIDENTS.bat`, `REBUILD_BRANCHES_ATMS.bat`, `import_indoc.py`.
- Better separated active core from generated/package/noise files such as `map_install_package`, backups, debug PNGs and huge `.osm.pbf`.
- Better described the `import_indoc.py` pipeline and direct GigaChat provider boundary.
- Produced broader architectural recommendations around splitting `app.py`, isolating import jobs, packaging importer components, idempotent rebuilds and tests.

## No Clear Difference

- Both routes preserved source immutability.
- Both recognized `app.py:parse_bbox` as a useful first extraction target.
- Neither route executed live GigaChat/Nominatim calls or ran the map server.

## Open Risks

- This is one map-like project and should not be generalized to all project-analysis tasks.
- Direct route is still produced in the same Codex session, not by an independent human reviewer.
- Cognitive OS needs stronger source-strata filtering for packaged copies and generated artifacts.
- Provider-boundary behavior was only statically analyzed; no live GigaChat/Nominatim call was executed.

## Decision

`direct_agent_wins`
