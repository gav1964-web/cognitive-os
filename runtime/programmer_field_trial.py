"""Field trial scoring for the programmer role on real projects."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .role_pipeline import run_role_pipeline


def run_programmer_field_trial(*, root: Path, projects: list[Path], write: bool = False) -> dict[str, Any]:
    cases = [_run_case(root, project) for project in projects]
    report = {
        "status": "ok",
        "kind": "programmer_field_trial",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_count": len(cases),
        "summary": _summary(cases),
        "cases": cases,
    }
    if write:
        report["report_path"] = _write_report(root, report).as_posix()
    return report


def _run_case(root: Path, project: Path) -> dict[str, Any]:
    result = run_role_pipeline(
        root=root,
        project_dir=project,
        goal=f"Analyze {project.name}, prepare an implementation plan, and execute programmer verification safely.",
        write=True,
        run_executor=True,
    )
    executor = dict(result.get("executor") or {})
    test_result = dict(executor.get("test_result") or {})
    patch_package = _read_json(executor.get("patch_package_path"))
    score = _score(result, executor, test_result, patch_package)
    return {
        "project": project.as_posix(),
        "status": _verdict(score),
        "score": score,
        "recommendation": result.get("recommendation"),
        "next_action": result.get("next_action"),
        "role_quality": result.get("role_quality", {}),
        "executor": {
            "status": executor.get("status"),
            "execution_dir": executor.get("execution_dir"),
            "patch_package_path": executor.get("patch_package_path"),
            "test_result_path": executor.get("test_result_path"),
            "source_code_changes": executor.get("source_code_changes"),
        },
        "programmer_evidence": _programmer_evidence(patch_package, test_result),
        "pipeline_report": result.get("report_path"),
    }


def _score(result: dict[str, Any], executor: dict[str, Any], test_result: dict[str, Any], patch_package: dict[str, Any]) -> dict[str, Any]:
    role_quality = dict(result.get("role_quality") or {})
    commands = dict(test_result.get("summary") or {})
    command_rows = list(test_result.get("commands") or [])
    patches = list(patch_package.get("patches") or [])
    snapshot = list(patch_package.get("snapshot") or [])
    checks = {
        "implementation_plan_bound": role_quality.get("implementation_targets_extraction_candidate") is True,
        "contracts_bound": role_quality.get("implementation_has_input_contract") is True
        and role_quality.get("implementation_has_output_contract") is True,
        "patch_package_created": bool(executor.get("patch_package_path")) and patch_package.get("artifact_type") == "PatchPackage",
        "snapshot_attempted": bool(snapshot),
        "verification_executed": int(commands.get("executed") or 0) > 0,
        "verification_passed": int(commands.get("failed") or 0) == 0 and int(commands.get("executed") or 0) > 0,
        "verification_project_scoped": _verification_project_scoped(command_rows, patch_package),
        "patches_proposed": bool(patches),
        "source_unchanged": executor.get("source_code_changes") is False,
    }
    planning = _ratio([checks["implementation_plan_bound"], checks["contracts_bound"]])
    execution = _ratio(
        [
            checks["patch_package_created"],
            checks["snapshot_attempted"],
            checks["verification_executed"],
            checks["verification_passed"],
            checks["verification_project_scoped"],
        ]
    )
    coding = _ratio([checks["patches_proposed"]])
    safety = _ratio([checks["source_unchanged"]])
    return {
        "planning_score": planning,
        "execution_score": execution,
        "coding_score": coding,
        "safety_score": safety,
        "maturity_score": round((planning + execution + coding + safety) / 4, 3),
        "checks": checks,
    }


def _verdict(score: dict[str, Any]) -> str:
    coding = float(score.get("coding_score") or 0)
    execution = float(score.get("execution_score") or 0)
    if coding >= 0.8 and execution >= 0.8:
        return "programmer_active"
    if execution >= 0.5:
        return "executor_only"
    return "planner_only"


def _programmer_evidence(patch_package: dict[str, Any], test_result: dict[str, Any]) -> dict[str, Any]:
    synthesis = dict(patch_package.get("patch_synthesis") or {})
    return {
        "patch_count": len(patch_package.get("patches") or []),
        "patch_synthesis_status": synthesis.get("status"),
        "patch_synthesis_reason": synthesis.get("reason"),
        "patch_sandbox_project": synthesis.get("sandbox_project"),
        "snapshot_count": len(patch_package.get("snapshot") or []),
        "command_summary": test_result.get("summary", {}),
        "commands": [
            {"command": row.get("command"), "status": row.get("status"), "reason": row.get("reason")}
            for row in test_result.get("commands", [])
        ],
        "implementation_target": patch_package.get("implementation_target", {}),
        "mode": patch_package.get("mode"),
    }


def _verification_project_scoped(command_rows: list[dict[str, Any]], patch_package: dict[str, Any]) -> bool:
    expected = [str(item).replace("\\", "/").split(":", 1)[0] for item in patch_package.get("expected_files", [])]
    target = str(dict(patch_package.get("implementation_target") or {}).get("candidate") or "").replace("\\", "/")
    needles = [item for item in expected if item]
    if target:
        needles.append(target.split(":", 1)[0])
    if not needles:
        return False
    for row in command_rows:
        command = str(row.get("command") or "").replace("\\", "/")
        if row.get("status") in {"passed", "failed"} and any(needle in command for needle in needles):
            return True
    return False


def _summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    verdicts: dict[str, int] = {}
    for case in cases:
        verdicts[case["status"]] = verdicts.get(case["status"], 0) + 1
    keys = ["planning_score", "execution_score", "coding_score", "safety_score", "maturity_score"]
    return {
        "verdicts": verdicts,
        "average_scores": {
            key: round(sum(float(dict(case["score"]).get(key) or 0) for case in cases) / len(cases), 3) if cases else 0
            for key in keys
        },
    }


def _ratio(values: list[bool]) -> float:
    return round(sum(1 for value in values if value) / len(values), 3) if values else 0.0


def _read_json(path: object) -> dict[str, Any]:
    if not path:
        return {}
    target = Path(str(path))
    if not target.exists():
        return {}
    return json.loads(target.read_text(encoding="utf-8"))


def _write_report(root: Path, report: dict[str, Any]) -> Path:
    out_dir = root / "artifacts" / "field_trials"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"programmer_field_trial_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
