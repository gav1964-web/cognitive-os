"""Probe literal-stub Executor recipe on real-source-derived GitHub stubs."""

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
    parser.add_argument("--label", default="executor_stub_recipe_probe")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--max-per-project", type=int, default=4)
    parser.add_argument("--mode", choices=["derived", "full-repo"], default="derived")
    parser.add_argument("--placeholder-kind", choices=["stub", "notimplemented"], default="stub")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    projects_dir = Path(args.projects_dir)
    if not projects_dir.is_absolute():
        projects_dir = root / projects_dir
    report = run_stub_probe(
        root=root,
        projects_dir=projects_dir.resolve(),
        limit=args.limit,
        label=args.label,
        max_per_project=args.max_per_project,
        mode=args.mode,
        placeholder_kind=args.placeholder_kind,
    )
    if args.write:
        report.update(write_report(root, report, args.label))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def run_stub_probe(
    *,
    root: Path,
    projects_dir: Path,
    limit: int = 20,
    label: str = "executor_stub_recipe_probe",
    max_per_project: int = 4,
    mode: str = "derived",
    placeholder_kind: str = "stub",
) -> dict[str, Any]:
    work_root = root / "artifacts" / "executor_stub_recipe_probe" / _stamp()
    rows = _discover_stub_targets(projects_dir, limit, max_per_project, placeholder_kind, mode=mode)
    cases = [_run_case_safe(root, work_root, row, mode=mode) for row in rows]
    summary = _summary(cases)
    return {
        "artifact_type": "ExecutorStubRecipeProbe",
        "status": "ok" if summary["accepted"] == len(cases) and cases else "needs_review",
        "milestone": label,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(cases),
        "summary": summary,
        "cases": cases,
        "invariants": {
            "source_projects_modified": summary["source_code_changes"],
            "mode": mode,
            "placeholder_kind": placeholder_kind,
            "apply_source": False,
        },
    }


def _run_case(root: Path, work_root: Path, row: dict[str, Any], *, mode: str) -> dict[str, Any]:
    project_dir, target = _case_project(work_root, row, mode)
    expected = f"stub-ready:{row['project']}:{row['symbol']}"
    result = run_programmer_executor(
        root=root,
        project_dir=project_dir,
        technical_spec={"artifact_type": "TechnicalSpec", "source_origin": row},
        implementation_plan=_plan(target),
        test_plan=_test_plan(target, expected),
        run_verification=True,
    )
    patch = _read_json(result.get("patch_package_path"))
    synthesis = dict(patch.get("patch_synthesis") or {})
    strategy = dict(patch.get("patch_strategy") or {})
    quality = dict(strategy.get("patch_quality") or {})
    accepted_reasons = {"return_literal_stub_synthesized", "return_literal_notimplemented_synthesized"}
    return {
        "project": row["project"],
        "source_target": row["source_target"],
        "execution_input_project": project_dir.as_posix(),
        "mode": mode,
        "status": "ok" if result.get("status") == "ok" and synthesis.get("reason") in accepted_reasons else "needs_review",
        "executor_status": result.get("status"),
        "patch_synthesis": synthesis.get("status"),
        "patch_reason": synthesis.get("reason"),
        "patch_quality_level": quality.get("level"),
        "solution_pattern_ids": [str(item.get("id") or "") for item in list(strategy.get("solution_patterns") or [])],
        "source_code_changes": bool(result.get("source_code_changes")),
    }


def _run_case_safe(root: Path, work_root: Path, row: dict[str, Any], *, mode: str) -> dict[str, Any]:
    try:
        return _run_case(root, work_root, row, mode=mode)
    except BaseException as exc:  # noqa: BLE001 - field probe must preserve per-case failures.
        return {
            "project": row.get("project"),
            "source_target": row.get("source_target"),
            "mode": mode,
            "status": "needs_review",
            "executor_status": "failed",
            "patch_synthesis": None,
            "patch_reason": f"{type(exc).__name__}: {str(exc)[:200]}",
            "patch_quality_level": "probe_exception",
            "solution_pattern_ids": [],
            "source_code_changes": False,
        }


def _case_project(work_root: Path, row: dict[str, Any], mode: str) -> tuple[Path, str]:
    if mode == "full-repo":
        return Path(str(row["project_dir"])), f"{row['project_rel_path']}:{row['symbol']}"
    case_dir = work_root / _slug(f"{row['project']} {row['symbol']} {row['line']}")
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "main.py").write_text(str(row["source"]) + "\n", encoding="utf-8")
    return case_dir, "main.py:" + str(row["symbol"])


def _plan(target: str) -> dict[str, Any]:
    path_text = target.split(":", 1)[0]
    return {
        "implementation_target": {"candidate": target},
        "patch_intent": {"target_symbol": target},
        "writable_scope": [target],
        "expected_files": [path_text],
        "verification_commands": ["python -m compileall ."],
    }


def _test_plan(target: str, expected: str) -> dict[str, Any]:
    return {
        "executable_acceptance": {
            "obligations": [
                {
                    "id": "OBL-001",
                    "acceptance_id": "AC-001",
                    "target": target,
                    "kind": "positive_contract_case",
                    "given": {},
                    "expect": {"return_value": expected},
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


def _discover_stub_targets(
    projects_dir: Path,
    limit: int,
    max_per_project: int,
    placeholder_kind: str,
    *,
    mode: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    per_project: dict[str, int] = {}
    for path in sorted(projects_dir.rglob("*.py")):
        if len(rows) >= limit:
            break
        rel = path.relative_to(projects_dir).as_posix()
        if _excluded(rel, path.name):
            continue
        for row in _stub_rows(projects_dir, path, limit - len(rows), placeholder_kind, mode=mode):
            project = str(row["project"])
            if per_project.get(project, 0) >= max_per_project:
                continue
            rows.append(row)
            per_project[project] = per_project.get(project, 0) + 1
            if len(rows) >= limit:
                break
    return rows[:limit]


def _stub_rows(projects_dir: Path, path: Path, limit: int, placeholder_kind: str, *, mode: str) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    rel = path.relative_to(projects_dir).as_posix()
    rows = []
    for node in tree.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and _no_required_args(node)
            and _matches_placeholder(node, placeholder_kind)
            and not _risky_full_repo_target(node, rel, mode)
        ):
            clone = ast.fix_missing_locations(_clean_function(node))
            project = rel.split("/", 1)[0]
            rows.append(
                {
                    "project": project,
                    "project_dir": (projects_dir / project).as_posix(),
                    "project_rel_path": rel.split("/", 1)[1] if "/" in rel else rel,
                    "source_target": f"{rel}:{node.name}",
                    "symbol": node.name,
                    "line": node.lineno,
                    "source": ast.unparse(clone),
                }
            )
        if len(rows) >= limit:
            return rows
    return rows


def _clean_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.FunctionDef | ast.AsyncFunctionDef:
    clone = ast.parse(ast.unparse(node)).body[0]
    assert isinstance(clone, (ast.FunctionDef, ast.AsyncFunctionDef))
    clone.decorator_list = []
    clone.returns = None
    for arg in clone.args.posonlyargs + clone.args.args + clone.args.kwonlyargs:
        arg.annotation = None
    return clone


def _no_required_args(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    args = node.args
    positional = len(args.posonlyargs + args.args) - len(args.defaults)
    keyword_only = sum(1 for default in args.kw_defaults if default is None)
    return positional + keyword_only == 0


def _is_stub(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    body = [item for item in node.body if not (isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant) and isinstance(item.value.value, str))]
    if len(body) != 1:
        return False
    item = body[0]
    return isinstance(item, ast.Pass) or (isinstance(item, ast.Return) and (item.value is None or _is_none_constant(item.value)))


def _matches_placeholder(node: ast.FunctionDef | ast.AsyncFunctionDef, placeholder_kind: str) -> bool:
    if placeholder_kind == "notimplemented":
        return _is_notimplemented(node)
    return _is_stub(node)


def _risky_full_repo_target(node: ast.FunctionDef | ast.AsyncFunctionDef, rel: str, mode: str) -> bool:
    if mode != "full-repo":
        return False
    if node.decorator_list:
        return True
    low = "/" + rel.lower()
    path_tokens = ("/cli", "/commands/", "/command/", "/scaffold", "/schema/", "/automation/", "/migrations/")
    risky_names = {
        "cli",
        "main",
        "check",
        "watch",
        "show",
        "config",
        "dep",
        "env",
        "project",
        "python",
        "self_command",
        "scaffold",
        "monorepo_sync",
        "query",
    }
    return node.name.lower() in risky_names or any(token in low for token in path_tokens)


def _is_notimplemented(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    body = [item for item in node.body if not (isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant) and isinstance(item.value.value, str))]
    if len(body) != 1 or not isinstance(body[0], ast.Raise):
        return False
    exc = body[0].exc
    if isinstance(exc, ast.Name):
        return exc.id == "NotImplementedError"
    return isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name) and exc.func.id == "NotImplementedError"


def _is_none_constant(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _excluded(rel: str, name: str) -> bool:
    low = "/" + rel.lower()
    tokens = ("/tests/", "/test/", "/typing_tests/", "/scripts/", "/examples/", "/.test-infra/", "/integration_tests/")
    return name.startswith("test_") or name.endswith("_test.py") or any(token in low for token in tokens)


def _summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "accepted": sum(case["status"] == "ok" for case in cases),
        "needs_review": sum(case["status"] == "needs_review" for case in cases),
        "patch_reasons": _counts(case.get("patch_reason") for case in cases),
        "patch_quality_levels": _counts(case.get("patch_quality_level") for case in cases),
        "solution_patterns": _counts(pattern for case in cases for pattern in list(case.get("solution_pattern_ids") or [])),
        "source_code_changes": sum(bool(case.get("source_code_changes")) for case in cases),
    }


def write_report(root: Path, report: dict[str, Any], label: str) -> dict[str, str]:
    out_dir = root / "artifacts" / "field_trials"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{label}_{_stamp()}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"report_path": path.as_posix()}


def _read_json(path: object) -> dict[str, Any]:
    source = Path(str(path)) if path else Path()
    return json.loads(source.read_text(encoding="utf-8")) if source.is_file() else {}


def _counts(values: Any) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        if value:
            result[str(value)] = result.get(str(value), 0) + 1
    return dict(sorted(result.items()))


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value.lower()).strip("_")[:120]


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


if __name__ == "__main__":
    raise SystemExit(main())
