# Learned fix templates competency

Owner of fix templates learned without an LLM from real history, anchored to a
detector (ruff). Version 0.1.0 holds two rules whose cross-project evaluation was
usable and for which ruff has no autofix:

| Rule | Meaning | Learned rewrite | Leave-one-project-out |
|---|---|---|---|
| TRY004 | `raise ValueError` after a type check | `raise ValueError(x)` -> `raise TypeError(x)` | 8/9 correct, 19/19 current-code sites detector-verified |
| G002 | `%` formatting inside a logging call | `log.m("..." % y)` -> `log.m("...", y)` (+ 2-tuple form) | 8/16 correct, 5/5 detector-verified |

`knowledge/templates.json` is produced by `tools/fix_template_export.py` from
`artifacts/fix_templates_20261003/detector/anchored.jsonl` (digest recorded) and keeps
only templates supported by at least two projects, with provenance and evaluation.

Operations: `rules` (KB summary) and `task_change` (`task_competency.v1`). The caller
passes the goal, project sources and detector diagnostics; the competency answers only
for rules the goal names (code or a clear description) and only at diagnosed statements,
choosing the most concrete matching template. Owned safety: G002 rewrites must keep
placeholder count equal to positional arguments (mapping placeholders and starred
arguments are refused). TRY004 declares `requires_regression_tests` because the raised
exception type changes. No sources are written here; `runtime/feature_competency.py`
verifies with the detector and existing tests and installs only on `apply_source`.

Limitations: the rewritten statement is re-printed (quotes and inline formatting of
that statement are normalized, comments inside it are lost); semantic correctness is
not proven by the detector. Shared tree/matching code: `runtime/fix_template_tree.py`.
Tests: `plugins/learned_fix_templates/tests`, `tests/runtime/test_feature_competency_detector.py`.
Evidence: `docs/architecture/fix_templates_20261003.md`.
