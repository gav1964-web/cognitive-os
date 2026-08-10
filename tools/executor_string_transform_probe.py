"""Probe contract-derived string transform Executor recipe on downloaded sources."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.programmer_executor import run_programmer_executor


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--projects-dir", required=True)
    parser.add_argument("--label", default="executor_string_transform_probe")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--max-per-project", type=int, default=4)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    projects_dir = Path(args.projects_dir)
    if not projects_dir.is_absolute():
        projects_dir = root / projects_dir
    report = run_transform_probe(
        root=root,
        projects_dir=projects_dir.resolve(),
        limit=args.limit,
        label=args.label,
        max_per_project=args.max_per_project,
    )
    if args.write:
        report.update(write_report(root, report, args.label))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def run_transform_probe(
    *,
    root: Path,
    projects_dir: Path,
    limit: int = 20,
    label: str = "executor_string_transform_probe",
    max_per_project: int = 4,
) -> dict[str, Any]:
    work_root = root / "artifacts" / "executor_string_transform_probe" / _stamp()
    rows = _discover_identity_targets(projects_dir, limit, max_per_project)
    cases = [_run_case_safe(root, work_root, row) for row in rows]
    summary = _summary(cases)
    return {
        "artifact_type": "ExecutorStringTransformProbe",
        "status": "ok" if cases and summary["accepted"] == len(cases) else "needs_review",
        "milestone": label,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(cases),
        "summary": summary,
        "cases": cases,
        "invariants": {"source_projects_modified": summary["source_code_changes"], "mode": "derived", "apply_source": False},
    }


def _run_case(root: Path, work_root: Path, row: dict[str, Any]) -> dict[str, Any]:
    project_dir = _case_project(work_root, row)
    target = f"main.py:{row['symbol']}"
    result = run_programmer_executor(
        root=root,
        project_dir=project_dir,
        technical_spec={"artifact_type": "TechnicalSpec", "source_origin": row},
        implementation_plan=_plan(target),
        test_plan=_test_plan(target, row),
        run_verification=True,
    )
    patch = _read_json(result.get("patch_package_path"))
    synthesis = dict(patch.get("patch_synthesis") or {})
    strategy = dict(patch.get("patch_strategy") or {})
    quality = dict(strategy.get("patch_quality") or {})
    return {
        "project": row["project"],
        "source_target": row["source_target"],
        "transform": row["transform"],
        "status": "ok"
        if result.get("status") == "ok" and synthesis.get("reason") == "contract_transform_identity_return_synthesized"
        else "needs_review",
        "executor_status": result.get("status"),
        "patch_reason": synthesis.get("reason"),
        "patch_quality_level": quality.get("level"),
        "solution_pattern_ids": [str(item.get("id") or "") for item in list(strategy.get("solution_patterns") or [])],
        "source_code_changes": bool(result.get("source_code_changes")),
    }


def _run_case_safe(root: Path, work_root: Path, row: dict[str, Any]) -> dict[str, Any]:
    try:
        return _run_case(root, work_root, row)
    except BaseException as exc:  # noqa: BLE001 - probe must preserve per-case failures.
        return {
            "project": row.get("project"),
            "source_target": row.get("source_target"),
            "transform": row.get("transform"),
            "status": "needs_review",
            "executor_status": "failed",
            "patch_reason": "probe_exception",
            "patch_quality_level": "probe_exception",
            "error": f"{type(exc).__name__}: {str(exc)[:240]}",
            "source_code_changes": False,
        }


def _case_project(work_root: Path, row: dict[str, Any]) -> Path:
    project = work_root / f"{row['project']}_{row['symbol']}_{row['line']}"
    project.mkdir(parents=True, exist_ok=True)
    (project / "main.py").write_text(str(row["source"]) + "\n", encoding="utf-8")
    return project


def _plan(target: str) -> dict[str, Any]:
    return {
        "implementation_target": {"candidate": target},
        "patch_intent": {"target_symbol": target},
        "writable_scope": [target],
        "expected_files": ["main.py"],
        "verification_commands": ["python -m compileall ."],
    }


def _test_plan(target: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "executable_acceptance": {
            "obligations": [
                {
                    "id": "OBL-001",
                    "acceptance_id": "AC-001",
                    "target": target,
                    "kind": "positive_contract_case",
                    "given": {row["arg"]: row["input"]},
                    "expect": {"return_value": row["expected"]},
                    "oracle": "output_schema_and_acceptance_criterion",
                },
                {
                    "id": "OBL-002",
                    "acceptance_id": "side_effect_boundary",
                    "target": target,
                    "kind": "side_effect_scope_case",
                    "given": {"declared_scope": "writable_scope_only"},
                    "expect": {"no_writes_outside_declared_scope": True},
                    "oracle": "changed_file_list_is_subset_of_writable_scope",
                },
            ]
        }
    }


def _discover_identity_targets(projects_dir: Path, limit: int, max_per_project: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    per_project: dict[str, int] = {}
    for path in sorted(projects_dir.rglob("*.py")):
        if len(rows) >= limit * 6:
            break
        rel = path.relative_to(projects_dir).as_posix()
        if _excluded(rel, path.name):
            continue
        for row in _identity_rows(projects_dir, path, limit - len(rows)):
            project = str(row["project"])
            if per_project.get(project, 0) >= max_per_project * 3:
                continue
            rows.append(row)
            per_project[project] = per_project.get(project, 0) + 1
            if len(rows) >= limit * 6:
                break
    return _diverse_rows(rows, limit, max_per_project)


def _diverse_rows(rows: list[dict[str, Any]], limit: int, max_per_project: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    per_project: dict[str, int] = {}
    for transform in ("comma_split_strip_nonempty", "strip_lower", "strip_upper", "lower", "upper", "strip"):
        for row in rows:
            project = str(row["project"])
            if row["transform"] != transform or per_project.get(project, 0) >= max_per_project:
                continue
            selected.append(row)
            per_project[project] = per_project.get(project, 0) + 1
            if len(selected) >= limit:
                return selected
    return selected


def _identity_rows(projects_dir: Path, path: Path, limit: int) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    rel = path.relative_to(projects_dir).as_posix()
    rows = []
    for node in tree.body:
        row = _identity_row(node, rel)
        if row:
            rows.append(row)
        if len(rows) >= limit:
            return rows
    return rows


def _identity_row(node: ast.AST, rel: str) -> dict[str, Any] | None:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.decorator_list:
        return None
    body = [item for item in node.body if not _doc_expr(item)]
    if len(body) != 1 or not isinstance(body[0], ast.Return) or not isinstance(body[0].value, ast.Name):
        return None
    arg = body[0].value.id
    if not _single_required_arg(node, arg):
        return None
    transform, sample, expected = _transform_for_name(node.name)
    clone = ast.fix_missing_locations(_clean_function(node))
    project = rel.split("/", 1)[0]
    return {
        "project": project,
        "source_target": f"{rel}:{node.name}",
        "symbol": node.name,
        "line": node.lineno,
        "arg": arg,
        "input": sample,
        "expected": expected,
        "transform": transform,
        "source": ast.unparse(clone),
    }


def _transform_for_name(name: str) -> tuple[str, str, object]:
    low = name.lower()
    if any(token in low for token in ("items", "list", "split", "csv")):
        sample = "one, two,,three"
        return "comma_split_strip_nonempty", sample, ["one", "two", "three"]
    sample = " Sample "
    if "upper" in low:
        return "strip_upper", sample, sample.strip().upper()
    if "lower" in low or "normalize" in low or "clean" in low or "canonical" in low:
        return "strip_lower", sample, sample.strip().lower()
    return "strip", sample, sample.strip()


def _single_required_arg(node: ast.FunctionDef | ast.AsyncFunctionDef, arg: str) -> bool:
    args = node.args
    if args.vararg or args.kwarg or args.kwonlyargs or args.posonlyargs:
        return False
    return len(args.args) == 1 and args.args[0].arg == arg and not args.defaults


def _clean_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.FunctionDef | ast.AsyncFunctionDef:
    clone = ast.parse(ast.unparse(node)).body[0]
    assert isinstance(clone, (ast.FunctionDef, ast.AsyncFunctionDef))
    clone.decorator_list = []
    clone.returns = None
    clone.args.args[0].annotation = None
    return clone


def _doc_expr(node: ast.AST) -> bool:
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def _excluded(rel: str, name: str) -> bool:
    low = "/" + rel.lower()
    tokens = ("/tests/", "/test/", "/testing/", "/scripts/", "/examples/", "/migrations/", "/docs/")
    return name.startswith("test_") or name.endswith("_test.py") or any(token in low for token in tokens)


def _summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "accepted": sum(case["status"] == "ok" for case in cases),
        "needs_review": sum(case["status"] == "needs_review" for case in cases),
        "patch_reasons": _counts(case.get("patch_reason") for case in cases),
        "patch_quality_levels": _counts(case.get("patch_quality_level") for case in cases),
        "solution_patterns": _counts(pattern for case in cases for pattern in list(case.get("solution_pattern_ids") or [])),
        "transforms": _counts(case.get("transform") for case in cases),
        "source_code_changes": sum(bool(case.get("source_code_changes")) for case in cases),
    }


def write_report(root: Path, report: dict[str, Any], label: str) -> dict[str, str]:
    out_dir = root / "artifacts" / "field_trials"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{label}_{_stamp()}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"report_path": path.as_posix()}


def _read_json(path: Any) -> dict[str, Any]:
    if not path:
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        if value:
            counts[str(value)] = counts.get(str(value), 0) + 1
    return dict(sorted(counts.items()))


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


if __name__ == "__main__":
    raise SystemExit(main())
