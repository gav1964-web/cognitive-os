"""Run role-produced Executor probes for profile-safe identity transforms."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.architecture_decision_policy import load_architecture_decision_policy
from runtime.contract_transform_contract_profiles import contract_profile_for_operator, contract_profile_hint
from runtime.contract_transform_mutation import identity_mutation_source, observed_operator
from runtime.implementation_plan_builder import build_implementation_plan
from runtime.programmer_executor import run_programmer_executor
from runtime.programmer_transformation_trial_quality import evaluate_transformation_case, transformation_summary
from runtime.project_benchmark import analyze_project
from runtime.technical_spec_builder import build_technical_spec
from runtime.test_plan_builder import build_test_plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--projects-dir", required=True)
    parser.add_argument("--label", default="executor_profile_safe_role_probe")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--max-per-project", type=int, default=3)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    projects_dir = Path(args.projects_dir)
    if not projects_dir.is_absolute():
        projects_dir = root / projects_dir
    report = run_profile_safe_role_probe(
        root=root,
        projects_dir=projects_dir.resolve(),
        label=args.label,
        limit=args.limit,
        max_per_project=args.max_per_project,
    )
    if args.write:
        report.update(write_report(root, report, args.label))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def run_profile_safe_role_probe(
    *,
    root: Path,
    projects_dir: Path,
    label: str,
    limit: int = 20,
    max_per_project: int = 3,
) -> dict[str, Any]:
    rows = _discover_rows(projects_dir, limit=limit, max_per_project=max_per_project)
    work_root = root / "artifacts" / "executor_profile_safe_role_probe" / _stamp()
    cases = [_run_case_safe(root, work_root, row) for row in rows]
    summary = transformation_summary(cases)
    return {
        "artifact_type": "ExecutorProfileSafeRoleProbe",
        "status": "ok" if cases and summary["accepted"] == len(cases) else "needs_review",
        "milestone": label,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(cases),
        "summary": summary,
        "invariants": {"source_projects_modified": summary["source_code_changes"], "mode": "derived_role_chain"},
        "cases": cases,
    }


def _run_case(root: Path, work_root: Path, row: dict[str, Any]) -> dict[str, Any]:
    project_dir = _case_project(work_root, row)
    source_path = project_dir / "main.py"
    source_before = source_path.read_text(encoding="utf-8")
    target = f"main.py:{row['symbol']}"
    spec = build_technical_spec(architecture_decision=_adr(target, row))
    plan = build_implementation_plan(technical_spec=spec)
    test_plan = build_test_plan(technical_spec=spec, implementation_plan=plan)
    result = run_programmer_executor(
        root=root,
        project_dir=project_dir,
        technical_spec=spec,
        implementation_plan=plan,
        test_plan=test_plan,
        run_verification=True,
    )
    patch = _read_json(result.get("patch_package_path"))
    test_result = _read_json(result.get("test_result_path"))
    quality = evaluate_transformation_case(
        expected_profile=str(row["profile_id"]),
        expected_operator=str(row["operator_id"]),
        source_before=source_before,
        source_after=source_path.read_text(encoding="utf-8"),
        technical_spec=spec,
        result=result,
        patch_package=patch,
        test_result=test_result,
    )
    return {
        "project": row["project"],
        "source_target": row["source_target"],
        **quality,
        "executor_status": result.get("status"),
        "source_code_changes": bool(result.get("source_code_changes")),
    }


def _run_case_safe(root: Path, work_root: Path, row: dict[str, Any]) -> dict[str, Any]:
    try:
        return _run_case(root, work_root, row)
    except BaseException as exc:  # noqa: BLE001 - field probe preserves failures.
        return {
            "project": row.get("project"),
            "source_target": row.get("source_target"),
            "status": "needs_review",
            "executor_status": "failed",
            "profile_id": row.get("profile_id"),
            "operator_id": row.get("operator_id"),
            "score": 0.0,
            "patch_reason": "probe_exception",
            "error": f"{type(exc).__name__}: {str(exc)[:240]}",
            "source_code_changes": False,
        }


def _discover_rows(projects_dir: Path, *, limit: int, max_per_project: int) -> list[dict[str, Any]]:
    allowed = _pathless_allowed_profiles()
    mapped = _discover_project_map_rows(projects_dir, allowed=allowed, limit=limit, max_per_project=max_per_project)
    rows: list[dict[str, Any]] = list(mapped)
    seen = {str(row.get("source_target")) for row in rows}
    per_project: dict[str, int] = {}
    for row in rows:
        project = str(row.get("project") or "")
        per_project[project] = per_project.get(project, 0) + 1
    for path in sorted(projects_dir.rglob("*.py")):
        if len(rows) >= limit:
            break
        rel = path.relative_to(projects_dir).as_posix()
        if _excluded(rel, path.name):
            continue
        for row in _path_rows(projects_dir, path, allowed):
            project = str(row["project"])
            if row["source_target"] in seen or per_project.get(project, 0) >= max_per_project:
                continue
            rows.append(row)
            seen.add(str(row["source_target"]))
            per_project[project] = per_project.get(project, 0) + 1
            if len(rows) >= limit:
                break
    return rows


def _discover_project_map_rows(
    projects_dir: Path,
    *,
    allowed: set[str],
    limit: int,
    max_per_project: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    per_project: dict[str, int] = {}
    for project_dir in sorted(path for path in projects_dir.iterdir() if path.is_dir()):
        if len(rows) >= limit:
            break
        try:
            report = analyze_project(project_dir)["project_map_report"]
        except Exception:
            continue
        capabilities = dict(dict(report.get("answers") or {}).get("3_capabilities") or {})
        for item in list(capabilities.get("pure_transforms") or [])[:120]:
            if not isinstance(item, dict):
                continue
            row = _project_map_row(project_dir.name, item, allowed)
            if not row or per_project.get(project_dir.name, 0) >= max_per_project:
                continue
            rows.append(row)
            per_project[project_dir.name] = per_project.get(project_dir.name, 0) + 1
            if len(rows) >= limit:
                break
    return rows


def _project_map_row(project: str, item: dict[str, Any], allowed: set[str]) -> dict[str, Any] | None:
    args = [dict(arg) for arg in list(item.get("args") or []) if isinstance(arg, dict)]
    if len(args) != 1:
        return None
    arg = str(args[0].get("name") or "")
    symbol = str(item.get("name") or "")
    path = str(item.get("path") or "")
    if not arg or not symbol or not path:
        return None
    target = f"{path}:{symbol}"
    arg_type = str(args[0].get("annotation") or "InferredInput")
    return_type = str(item.get("returns") or "InferredOutput")
    hint = contract_profile_hint(target=target, input_contract={arg: arg_type}, output_contract={"result": return_type})
    profile = dict((hint or {}).get("contract_profile") or {})
    if str(profile.get("id") or "") not in allowed:
        return None
    return {
        "project": project,
        "source_target": target,
        "symbol": symbol,
        "arg": arg,
        "arg_type": arg_type,
        "return_type": return_type,
        "source": f"def {symbol}({arg}):\n    return {arg}",
        "profile_id": str(profile.get("id") or ""),
        "operator_id": str(profile.get("operator_id") or ""),
    }


def _path_rows(projects_dir: Path, path: Path, allowed: set[str]) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    rel = path.relative_to(projects_dir).as_posix()
    return [row for node in ast.walk(tree) if (row := _node_row(node, rel, allowed))]


def _node_row(node: ast.AST, rel: str, allowed: set[str]) -> dict[str, Any] | None:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.decorator_list:
        return None
    body = [item for item in node.body if not _doc_expr(item)]
    if len(body) != 1 or not isinstance(body[0], ast.Return):
        return None
    arg = node.args.args[0].arg if len(node.args.args) == 1 else ""
    if not _single_arg_shape(node, arg):
        return None
    project, _, project_rel = rel.partition("/")
    current_operator = observed_operator(node, arg)
    identity = isinstance(body[0].value, ast.Name) and body[0].value.id == arg
    if identity and not _single_required_arg(node, arg):
        return None
    symbol = node.name
    arg_type = _annotation(node)
    return_type = _returns(node)
    if identity:
        target = f"{project_rel or rel}:{symbol}"
        hint = contract_profile_hint(
            target=target, input_contract={arg: arg_type}, output_contract={"result": return_type}
        )
        profile = dict((hint or {}).get("contract_profile") or {})
    else:
        profile_record = dict(contract_profile_for_operator(str(current_operator or "")) or {})
        symbol = str(profile_record.get("trial_symbol") or "")
        input_types = [str(item) for item in list(profile_record.get("input_types") or []) if item]
        output_types = [str(item) for item in list(profile_record.get("output_types") or []) if item]
        arg_type = input_types[0] if input_types else "InferredInput"
        return_type = output_types[0] if output_types else "InferredOutput"
        profile = {
            "id": profile_record.get("id"),
            "operator_id": profile_record.get("operator_id"),
        }
        target = f"{project_rel or rel}:{symbol}"
    profile_id = str(profile.get("id") or "")
    if not symbol or not profile_id:
        return None
    if identity and profile_id not in allowed:
        return None
    if not identity and current_operator != str(profile.get("operator_id") or ""):
        return None
    source = (
        ast.unparse(ast.fix_missing_locations(_clean_function(node)))
        if identity else identity_mutation_source(node, arg, function_name=symbol)
    )
    return {
        "project": project,
        "source_target": target,
        "symbol": symbol,
        "arg": arg,
        "arg_type": arg_type,
        "return_type": return_type,
        "source": source,
        "profile_id": profile_id,
        "operator_id": str(profile.get("operator_id") or ""),
        "mutation_source": "existing_identity" if identity else "real_operator_replaced_with_identity",
        "oracle_operator_id": current_operator,
    }


def _case_project(work_root: Path, row: dict[str, Any]) -> Path:
    project = work_root / f"{row['project']}_{row['symbol']}"
    project.mkdir(parents=True, exist_ok=True)
    (project / "main.py").write_text(str(row["source"]) + "\n", encoding="utf-8")
    return project


def _adr(target: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": f"Implement verified {row['operator_id']} transform in the profile-safe role chain",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare profile-safe transform."],
            "files_or_symbols": [target],
            "requested_contract_profile": {
                "id": row["profile_id"],
                "operator_id": row["operator_id"],
                "evidence": row["source_target"],
            },
        },
        "traceability": [{"source": target, "requirement": "Capability candidate requires TechnicalSpec."}],
        "source_context": {
            target: {
                "kind": "pure_transform",
                "signature": {"args": [{"name": row["arg"], "annotation": row["arg_type"]}], "returns": row["return_type"]},
                "snippet": {"text": row["source"]},
            }
        },
    }


def _pathless_allowed_profiles() -> set[str]:
    policy = dict(load_architecture_decision_policy().get("source_selection") or {})
    fallback = dict(policy.get("callable_transform_fallback") or {})
    return {str(item) for item in list(fallback.get("pathless_allowed_contract_profiles") or [])}


def _single_required_arg(node: ast.FunctionDef | ast.AsyncFunctionDef, arg: str) -> bool:
    args = node.args
    if args.vararg or args.kwarg or args.kwonlyargs or args.posonlyargs:
        return False
    return len(args.args) == 1 and args.args[0].arg == arg and not args.defaults


def _single_arg_shape(node: ast.FunctionDef | ast.AsyncFunctionDef, arg: str) -> bool:
    args = node.args
    return bool(
        arg and not args.vararg and not args.kwarg and not args.kwonlyargs
        and not args.posonlyargs and len(args.args) == 1 and args.args[0].arg == arg
    )


def _clean_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.FunctionDef | ast.AsyncFunctionDef:
    clone = ast.parse(ast.unparse(node)).body[0]
    assert isinstance(clone, (ast.FunctionDef, ast.AsyncFunctionDef))
    clone.decorator_list = []
    clone.returns = None
    clone.args.args[0].annotation = None
    return clone


def _annotation(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    annotation = node.args.args[0].annotation if node.args.args else None
    return ast.unparse(annotation) if annotation is not None else "InferredInput"


def _returns(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    return ast.unparse(node.returns) if node.returns is not None else "InferredOutput"


def _doc_expr(node: ast.AST) -> bool:
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def _excluded(rel: str, name: str) -> bool:
    low = "/" + rel.lower()
    tokens = ("/tests/", "/test/", "/testing/", "/scripts/", "/examples/", "/migrations/", "/docs/")
    return name.startswith("test_") or name.endswith("_test.py") or any(token in low for token in tokens)


def write_report(root: Path, report: dict[str, Any], label: str) -> dict[str, str]:
    out_dir = root / "artifacts" / "field_trials"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{label}_{_stamp()}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"report_path": path.as_posix()}


def _read_json(path: Any) -> dict[str, Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")) if path else {}
    except Exception:
        return {}


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


if __name__ == "__main__":
    raise SystemExit(main())
