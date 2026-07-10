# Evaluation Corpus

This directory stores direct-agent vs Cognitive OS comparison tasks.

The purpose is to prove or falsify value, not to showcase architecture.

Each task compares two routes under the same prompt and constraints:

```text
Route A: direct agent / executor
Route B: Cognitive OS mediated route
```

## Directory Layout

```text
evaluation/
  task01_example/
    prompt.md
    direct_agent/
      README.md
    cognitive_os/
      README.md
    metrics.json
    verdict.md
```

Use `task_template/` as the starting shape for new tasks.

Initial seed tasks:

- `task01_project5_improvement_plan` - project analysis and improvement planning.
- `task02_map_project_analysis` - project analysis with provider-boundary risks.
- `task03_markdown_to_rtf_cli` - CLI utility generation.
- `task04_xlsx_csv_converter` - CLI utility with dependency/format ambiguity.
- `task05_fastapi_csv_aggregator` - small local service generation.
- `task06_ambiguous_project_request` - negative prompt adequacy case.
- `task07_role_pipeline_ablation` - full role chain vs reduced-role baseline.
- `task08_registry_artifact_audit` - registry separation and artifact redundancy audit.
- `task09_stage3_value_ablation` - Stage 2 package vs Stage 3 product slice.
- `task10_strict_layering_bypass` - strict layered route vs controlled bypass.

## Required Files

- `prompt.md` - original user task, constraints, allowed tools and success criteria.
- `direct_agent/README.md` - what the direct route did, with links to artifacts.
- `cognitive_os/README.md` - what the Cognitive OS route did, with links to artifacts.
- `metrics.json` - comparable numeric and categorical results.
- `verdict.md` - human-readable conclusion, including where Cognitive OS won, lost or made no difference.

## Metrics Contract

`metrics.json` is the task-level API for evaluation. It is not a narrative report.

Required top-level fields:

```text
task_id
task_class
prompt_hash
routes
comparison
invariants
verdict
```

`routes.direct_agent` and `routes.cognitive_os` should use the same metric names whenever possible:

- `executor`
- `model`
- `status`
- `requirement_coverage`
- `missed_requirements`
- `invented_requirements`
- `tests_passed`
- `tests_total`
- `verification_status`
- `repair_cycles`
- `runtime_seconds`
- `estimated_cost`
- `artifact_completeness`
- `source_safety_violations`
- `review_blockers`
- `human_correction_minutes`

## Rules

- Same original prompt for both routes.
- Same model/executor family where possible.
- Manual corrections must be recorded.
- Teacher references are review targets, not ground truth.
- Source mutation must be explicit and detectable.
- A controlled `blocked`, `needs_clarification` or `needs_rework` can be a valid result.
- Do not average unrelated task classes into one global score.

## Validation

Run:

```bash
python tools/evaluation_check.py --root .
```

The checker validates required files and required `metrics.json` fields for every `evaluation/task*` directory except `task_template`.

To print a compact corpus table:

```bash
python tools/evaluation_summary.py --root .
```
