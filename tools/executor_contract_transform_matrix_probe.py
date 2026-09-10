"""Probe all contract-transform operators through Programmer Executor."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.contract_transform_operators import load_contract_transform_operators
from runtime.programmer_executor import run_programmer_executor


CASES = {
    "strip": ("value", " Sample ", "Sample"),
    "lower": ("value", "Sample", "sample"),
    "upper": ("value", "Sample", "SAMPLE"),
    "strip_lower": ("value", " Sample ", "sample"),
    "strip_upper": ("value", " Sample ", "SAMPLE"),
    "comma_split_strip_nonempty": ("value", "one, two,,three", ["one", "two", "three"]),
    "sum_numbers": ("values", [1, 2, 3], 6),
    "len_sequence": ("values", ["a", "b"], 2),
    "first_item": ("values", ["a", "b"], "a"),
    "last_item": ("values", ["a", "b"], "b"),
    "sorted_list": ("values", [3, 1, 2], [1, 2, 3]),
    "unique_preserve_order": ("values", ["a", "b", "a"], ["a", "b"]),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--projects-dir", required=True)
    parser.add_argument("--label", default="executor_contract_transform_matrix")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    projects_dir = Path(args.projects_dir)
    if not projects_dir.is_absolute():
        projects_dir = root / projects_dir
    report = run_matrix_probe(root=root, projects_dir=projects_dir.resolve(), label=args.label)
    if args.write:
        report.update(write_report(root, report, args.label))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def run_matrix_probe(*, root: Path, projects_dir: Path, label: str = "executor_contract_transform_matrix") -> dict[str, Any]:
    operators = [str(row.get("id") or "") for row in load_contract_transform_operators().get("operators", [])]
    projects = _project_names(projects_dir)
    work_root = root / "artifacts" / "executor_contract_transform_matrix" / _stamp()
    rows = [_row(operator_id, projects[index % len(projects)]) for index, operator_id in enumerate(operators) if operator_id in CASES]
    cases = [_run_case_safe(root, work_root, row) for row in rows]
    summary = _summary(cases)
    return {
        "artifact_type": "ExecutorContractTransformMatrixProbe",
        "status": "ok" if cases and summary["accepted"] == len(cases) else "needs_review",
        "milestone": label,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(cases),
        "summary": summary,
        "cases": cases,
        "invariants": {"source_projects_modified": summary["source_code_changes"], "mode": "operator_matrix", "apply_source": False},
    }


def _row(operator_id: str, project: str) -> dict[str, Any]:
    arg, sample, expected = CASES[operator_id]
    symbol = f"transform_{operator_id}"
    return {"project": project, "symbol": symbol, "arg": arg, "input": sample, "expected": expected, "transform": operator_id}


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
    transform = str((list(patch.get("patches") or [{}])[0] or {}).get("transform") or "")
    return {
        "project": row["project"],
        "transform": row["transform"],
        "status": "ok" if result.get("status") == "ok" and transform == row["transform"] else "needs_review",
        "executor_status": result.get("status"),
        "patch_reason": synthesis.get("reason"),
        "patch_transform": transform,
        "source_code_changes": bool(result.get("source_code_changes")),
    }


def _run_case_safe(root: Path, work_root: Path, row: dict[str, Any]) -> dict[str, Any]:
    try:
        return _run_case(root, work_root, row)
    except BaseException as exc:  # noqa: BLE001 - matrix probe preserves failures.
        return {
            "project": row.get("project"),
            "transform": row.get("transform"),
            "status": "needs_review",
            "executor_status": "failed",
            "patch_reason": "probe_exception",
            "error": f"{type(exc).__name__}: {str(exc)[:240]}",
            "source_code_changes": False,
        }


def _case_project(work_root: Path, row: dict[str, Any]) -> Path:
    project = work_root / f"{row['project']}_{row['symbol']}"
    project.mkdir(parents=True, exist_ok=True)
    (project / "main.py").write_text(f"def {row['symbol']}({row['arg']}):\n    pass\n", encoding="utf-8")
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
                    "given": {},
                    "expect": {"no_writes_outside_declared_scope": True},
                    "oracle": "changed_file_list_is_subset_of_writable_scope",
                },
            ]
        }
    }


def _project_names(projects_dir: Path) -> list[str]:
    names = [path.name for path in sorted(projects_dir.iterdir()) if path.is_dir()]
    return names or ["derived_project"]


def _summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "accepted": sum(case["status"] == "ok" for case in cases),
        "needs_review": sum(case["status"] == "needs_review" for case in cases),
        "transforms": _counts(case.get("transform") for case in cases),
        "patch_reasons": _counts(case.get("patch_reason") for case in cases),
        "source_code_changes": sum(bool(case.get("source_code_changes")) for case in cases),
    }


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
