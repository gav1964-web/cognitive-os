# Cognitive OS Route

## Executor

- Tool: `python tools\role_pipeline_run.py --root . --project-dir F:\ubuntu\test\map --goal "проанализировать проект F:\ubuntu\test\map и дать предложения по архитектурным улучшениям" --write`
- Model: deterministic role pipeline, LLM not invoked
- Date: 2026-07-11

## Run Summary

Cognitive OS completed the role pipeline with status `ok`.

Key route facts:

- `llm_invoked=false`.
- `source_code_changes=false`.
- `registry_changes=false`.
- `foundry_invoked=false`.
- `executor.status=skipped`.
- recommendation: `approve_with_risks`.
- selected candidate: `app.py:parse_bbox`.
- implementation/test/review target: `app.py:parse_bbox`.
- review contract violations: `0`.

After source-strata and purpose extraction fixes, the human-readable architecture report correctly surfaced:

- `Offline Kursk Map Package` as the project purpose;
- `RUN_MAP.bat` and `app.py` as entrypoints;
- runtime scripts for install/rebuild;
- HTTP request -> router -> handler -> JSON response path;
- risks around large artifacts, risky imports and unpinned dependencies;
- capability candidates including `parse_bbox`, `point_in_bbox`, `batch_key`, `branches_atms` and `create_mbtiles`.
- improvement recommendations for hidden orchestrators, process boundaries, idempotency/replay, quarantine policy and first extraction candidates.

Important weakness:

- The route is still somewhat extraction-oriented and less concise than direct inspection.
- It identifies large control surfaces and process boundaries, but it does not yet explain the desired target module structure as clearly as the direct route.

## Artifact APIs

- `GoalSpec`: implicit role pipeline goal input.
- `ProjectMapReport`: produced internally by `runtime.project_benchmark.analyze_project`.
- `ArchitectureDecisionRecord`: `artifacts/roles/architect/ArchitectureDecisionRecord_20260711T120253058381Z.json`.
- `TechnicalSpec`: `artifacts/roles/spec_writer/TechnicalSpec_20260711T120253059380Z.json`.
- `ImplementationPlan`: `artifacts/roles/implementer/ImplementationPlan_20260711T120253060381Z.json`.
- `TestPlan`: `artifacts/roles/tester/TestPlan_20260711T120253061381Z.json`.
- `ReviewFindings`: `artifacts/roles/reviewer/ReviewFindings_20260711T120253061886Z.json`.

## Artifacts

- Role pipeline report: `artifacts/roles/pipelines/role_pipeline_20260711T120253063900Z.json`.
- Human-readable architecture report: `artifacts/roles/pipelines/architecture_analysis_20260711T120253062892Z.md`.
- Tests: not executed beyond role pipeline artifact checks.
- Logs: role pipeline command output recorded in this evaluation.

## Notes

This route preserved source immutability and separated typed artifacts well. The packaged-copy pollution observed in the first run was fixed before this rerun.
