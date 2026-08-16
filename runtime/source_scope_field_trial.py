"""Measure nested-scope contract inference risk across Python corpora."""

from __future__ import annotations

import ast
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .source_ast_scope import callable_scope_walk


_SKIP_DIRS = {".git", ".venv", "venv", "site-packages", "build", "dist", "node_modules"}
_TEST_PARTS = {"test", "tests", "testing", "__tests__"}


def run_source_scope_field_trial(
    *, corpus_dir: Path, max_samples: int = 40, write_root: Path | None = None,
) -> dict[str, Any]:
    corpus = corpus_dir.resolve()
    counters: defaultdict[str, int] = defaultdict(int)
    projects: defaultdict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    samples: list[dict[str, Any]] = []
    for path in _python_files(corpus, counters):
        counters["files_seen"] += 1
        try:
            if path.stat().st_size > 1_000_000:
                counters["files_oversized"] += 1
                continue
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            counters["files_unparsed"] += 1
            continue
        counters["files_parsed"] += 1
        relative = path.relative_to(corpus)
        project = relative.parts[0] if len(relative.parts) > 1 else corpus.name
        is_test = _is_test_path(relative)
        for function in _functions(tree):
            _measure_function(
                function=function, project=project, relative=relative,
                is_test=is_test, counters=counters, projects=projects,
                samples=samples, max_samples=max_samples,
            )
    samples.sort(key=lambda row: (row["kind"] != "production", row["project"], row["file"]))
    report = _report(corpus, counters, projects, samples[:max_samples])
    if write_root is not None:
        report["report_path"] = _write_report(write_root.resolve(), report).as_posix()
    return report


def _python_files(root: Path, counters: defaultdict[str, int]):
    def onerror(_: OSError) -> None:
        counters["inaccessible_branches"] += 1

    for parent, dirs, names in os.walk(root, onerror=onerror):
        dirs[:] = [name for name in dirs if name not in _SKIP_DIRS]
        for name in names:
            if name.endswith(".py"):
                yield Path(parent) / name


def _functions(tree: ast.AST):
    return (
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )


def _measure_function(
    *, function: ast.FunctionDef | ast.AsyncFunctionDef, project: str, relative: Path,
    is_test: bool, counters: defaultdict[str, int],
    projects: defaultdict[str, defaultdict[str, int]], samples: list[dict[str, Any]],
    max_samples: int,
) -> None:
    counters["functions"] += 1
    calls = [
        ast.unparse(node.func).lower()
        for node in callable_scope_walk(function)
        if isinstance(node, ast.Call)
    ]
    if any("savefig" in call for call in calls):
        kind = "test" if is_test else "production"
        counters["savefig_scopes"] += 1
        counters[f"savefig_{kind}"] += 1
        projects[project]["savefig_scopes"] += 1
    nested = [
        node for node in ast.walk(function)
        if node is not function and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    if not nested:
        return
    counters["functions_with_nested_scopes"] += 1
    all_returns = [node for node in ast.walk(function) if isinstance(node, ast.Return)]
    scoped_returns = [node for node in callable_scope_walk(function) if isinstance(node, ast.Return)]
    all_values = sum(node.value is not None for node in all_returns)
    scoped_values = sum(node.value is not None for node in scoped_returns)
    if len(all_returns) != len(scoped_returns):
        counters["return_path_inflation"] += 1
    if not all_values or scoped_values:
        return
    kind = "test" if is_test else "production"
    counters["false_nonvoid_risk"] += 1
    counters[f"false_nonvoid_{kind}"] += 1
    projects[project]["false_nonvoid_risk"] += 1
    projects[project][f"false_nonvoid_{kind}"] += 1
    if max_samples > 0 and not any(
        row["project"] == project and row["kind"] == kind for row in samples
    ):
        file_name = Path(*relative.parts[1:]).as_posix() if len(relative.parts) > 1 else relative.as_posix()
        samples.append({
            "project": project,
            "file": file_name,
            "function": function.name,
            "line": function.lineno,
            "kind": kind,
            "legacy_value_returns": all_values,
            "scoped_value_returns": scoped_values,
            "nested_scopes": [getattr(node, "name", type(node).__name__) for node in nested[:5]],
        })


def _is_test_path(relative: Path) -> bool:
    parts = {part.lower() for part in relative.parts[:-1]}
    stem = relative.stem.lower()
    return bool(parts & _TEST_PARTS) or stem in {"test", "tests", "conftest"} or stem.startswith(("test_", "tests_"))


def _report(
    corpus: Path, counters: defaultdict[str, int],
    projects: defaultdict[str, defaultdict[str, int]], samples: list[dict[str, Any]],
) -> dict[str, Any]:
    project_rows = [
        {"project": project, **dict(values)}
        for project, values in projects.items()
    ]
    project_rows.sort(key=lambda row: (-int(row.get("false_nonvoid_risk") or 0), str(row["project"])))
    summary = dict(counters)
    summary["affected_projects"] = sum(bool(row.get("false_nonvoid_risk")) for row in project_rows)
    summary["savefig_projects"] = sum(bool(row.get("savefig_scopes")) for row in project_rows)
    return {
        "artifact_type": "SourceScopeFieldTrial",
        "status": "ok" if counters["files_parsed"] else "empty",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "corpus": corpus.as_posix(),
        "summary": summary,
        "project_risks": project_rows,
        "samples": samples,
        "conclusion": (
            "scope_aware_ast_required"
            if counters["false_nonvoid_production"] else "no_production_scope_regression_observed"
        ),
    }


def _write_report(root: Path, report: dict[str, Any]) -> Path:
    output = root / "artifacts" / "field_trials"
    output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = output / f"source_scope_field_trial_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
