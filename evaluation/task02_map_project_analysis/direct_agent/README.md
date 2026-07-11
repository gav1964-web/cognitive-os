# Direct Agent Route

## Executor

- Tool: Codex direct repository/project inspection
- Model: GPT-5 Codex session
- Date: 2026-07-11

## Run Summary

Direct inspection treats `F:\ubuntu\test\map` as an offline Kursk map Flask application with local Leaflet assets, vector/data JSON layers, RTF incident import and optional direct GigaChat extraction.

Main supported scenarios found:

- Run local Flask/Leaflet map through `RUN_MAP.bat` / `app.py`.
- Display vector road/settlement layer from `kursk_vector_map.json`.
- Search settlements and places.
- Filter and export incident events from `incidents.json`.
- Display branches/ATMs from `branches_atms.json`.
- Rebuild incidents from `indoc/*.rtf` through `import_indoc.py`.
- Optionally call direct GigaChat API from `import_indoc.py` for complex incident extraction.
- Rebuild branch/ATM data from Excel files through `geocode_addresses.py`.

Important entrypoints and execution flow:

- `app.py` is the primary runtime entrypoint and Flask app.
- `RUN_MAP.bat` starts the local app.
- `INSTALL.bat`, `REBUILD_INCIDENTS.bat` and `REBUILD_BRANCHES_ATMS.bat` are operational entrypoints.
- Browser route `/` renders a very large inline HTML/JS Leaflet UI through `render_template_string`.
- API routes include `/get_vector_map`, `/incident_meta`, `/import_indoc/start`, `/import_indoc/status`, `/get_incidents`, `/branches_atms`, `/unmatched_incidents`, `/export_incidents` and `/search`.
- `/import_indoc/start` launches `import_indoc.py` in a background thread via `subprocess.run`; `IMPORT_STATUS` is shared process memory.
- `import_indoc.py` parses RTF files, applies rule-based extraction, optionally batches candidate rows through direct GigaChat, writes `incidents.json`, and maintains `indoc_llm_cache.json`.

Core logic vs interfaces/noise:

- Core: bbox parsing/filtering, vector feature filtering, incident filtering/export, RTF-to-text, place matching, event building, GigaChat batch extraction.
- Interface/adapters: Flask routes, inline Leaflet UI, batch scripts, GigaChat HTTP client code in `import_indoc.py`.
- State/side effects: JSON data files, Excel source files, LLM cache, subprocess import job, thread lock/status, network calls to GigaChat/Nominatim, generated map/package artifacts.
- Noise/context-only: `map_install_package`, backup `import_indoc.py.bak.*`, debug PNGs, huge `.osm.pbf`, generated JSON files and package scripts.

Improvement proposals:

1. Split `app.py`. It is a 1600+ line mixed UI/API/data-processing module; `index()` alone embeds a large HTML/JS app and should move to template/static assets.
2. Create a service layer for map data and incident data: `map_service`, `incident_service`, `branch_atm_service`, `search_service`.
3. Isolate import execution: replace global `IMPORT_STATUS` plus background thread/subprocess with a job object, progress file or small durable queue.
4. Make `import_indoc.py` a proper package module with parser, normalizer, LLM client, cache and writer components.
5. Add provider-boundary policy for direct GigaChat calls: credentials, timeout, cache, retry, JSON parsing failures, and offline fallback should be explicit.
6. Add idempotency/replay rules for rebuilding `incidents.json`; preserve raw parsed rows, LLM responses and final normalized events separately.
7. Exclude `map_install_package`, backups, debug images and large generated data from analyzer core scoring.
8. Add tests for `parse_bbox`, `features_for_view`, incident filtering/export, RTF parsing, JSON response parsing and import fallback behavior.
9. Keep `app.py:parse_bbox` as a safe first capability extraction target, but do not mistake it for the main architecture improvement.

## Artifacts

- Output: this README section.
- Tests: not executed for direct route.
- Logs: shell inspection of project files, requirements, README/package docs and key source snippets.

## Notes

The direct route analyzed the project without using Cognitive OS role artifacts and did not modify the source project.
