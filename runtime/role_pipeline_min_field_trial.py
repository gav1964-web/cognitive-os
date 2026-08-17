"""Minimum-based field trial for downstream implementation roles."""

from __future__ import annotations

import contextlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .role_pipeline import run_role_pipeline


ROLE_IDS = ("implementer", "task_tree_builder", "programmer_executor", "tester", "reviewer")


def run_role_pipeline_min_field_trial(
    *,
    root: Path,
    projects_dir: Path,
    eligible_projects: set[str] | None = None,
    limit: int = 0,
    target_score: float = 9.7,
    write: bool = False,
) -> dict[str, Any]:
    projects = sorted(path for path in projects_dir.iterdir() if path.is_dir())
    if eligible_projects is not None:
        projects = [path for path in projects if path.name in eligible_projects]
    if limit:
        projects = projects[:limit]
    cases = [_run_case(root, project) for project in projects]
    report = _report(cases, target_score)
    if write:
        out_dir = root / "artifacts" / "field_trials"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = out_dir / f"role_pipeline_min_field_trial_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    return report


def eligible_projects_from_foundation_report(path: Path) -> set[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(case["project"])
        for case in payload.get("cases", [])
        if case.get("status") not in {"out_of_scope", "failed"}
    }


def _run_case(root: Path, project_dir: Path) -> dict[str, Any]:
    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(captured_stderr):
            result = run_role_pipeline(
                root=root,
                project_dir=project_dir,
                goal=f"Assess and prepare first safe transformation for {project_dir.name}",
                run_executor=True,
            )
    except (Exception, SystemExit) as exc:
        return {
            "project": project_dir.name,
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "role_scores": {role_id: 0.0 for role_id in ROLE_IDS},
            "runtime_output": _captured_output(captured_stdout, captured_stderr),
        }
    gate_cases = {
        str(case.get("role_id")): case
        for case in result.get("role_gates", {}).get("cases", [])
        if isinstance(case, dict)
    }
    role_scores = {
        "implementer": _gate_score(gate_cases.get("implementer", {})),
        "task_tree_builder": _gate_score(gate_cases.get("task_tree_builder", {})),
        "programmer_executor": _programmer_score(result),
        "tester": _gate_score(gate_cases.get("tester", {})),
        "reviewer": _gate_score(gate_cases.get("reviewer", {})),
    }
    return {
        "project": project_dir.name,
        "status": "ok" if min(role_scores.values()) >= 9.7 else "needs_work",
        "role_scores": role_scores,
        "project_min_score": min(role_scores.values()),
        "role_gate_statuses": {
            role_id: gate_cases.get(role_id, {}).get("status")
            for role_id in ("implementer", "task_tree_builder", "tester", "reviewer")
        },
        "programmer_evidence": _programmer_evidence(result),
        "recommendation": result.get("recommendation"),
        "next_action": result.get("next_action"),
        "safety": result.get("safety", {}),
        "runtime_output": _captured_output(captured_stdout, captured_stderr),
    }


def _captured_output(stdout: io.StringIO, stderr: io.StringIO) -> dict[str, str]:
    return {"stdout_tail": stdout.getvalue()[-1000:], "stderr_tail": stderr.getvalue()[-1000:]}


def _gate_score(case: dict[str, Any]) -> float:
    checks = [*case.get("gates", []), *case.get("quality_criteria", [])]
    evaluated = [check for check in checks if check.get("status") in {"passed", "failed"}]
    if not evaluated:
        return 0.0
    passed = sum(check.get("status") == "passed" for check in evaluated)
    return round(10.0 * passed / len(evaluated), 2)


def _programmer_score(result: dict[str, Any]) -> float:
    evidence = _programmer_evidence(result)
    checks = dict(evidence["checks"])
    return round(10.0 * sum(checks.values()) / len(checks), 2)


def _programmer_evidence(result: dict[str, Any]) -> dict[str, Any]:
    executor = dict(result.get("executor", {}))
    test_result = dict(executor.get("test_result", {}))
    acceptance = dict(test_result.get("executable_acceptance_result", {}))
    summary = dict(acceptance.get("summary", {}))
    strategy = dict(test_result.get("executor_strategy", {}))
    deterministic = dict(strategy.get("deterministic_strategy", {}))
    alignment = dict(strategy.get("contract_alignment", {}))
    candidate = dict(strategy.get("sandbox_patch_candidate", {}))
    task_tree = dict(test_result.get("programmer_task_tree", {}))
    coverage = dict(task_tree.get("coverage", {}))
    commands = [row for row in test_result.get("commands", []) if isinstance(row, dict)]
    skipped_targets = list(summary.get("skipped_targets", []))
    checks = {
        "executor_completed": executor.get("status") == "ok",
        "source_unchanged": executor.get("source_code_changes") is False,
        "patch_package_recorded": bool(executor.get("patch_package_path") or executor.get("no_patch_package_path")),
        "executable_acceptance_passed": acceptance.get("status") == "passed",
        "executable_callable_evidence": summary.get("signal_strength") == "executable_callable",
        "no_skipped_acceptance_targets": not skipped_targets,
        "task_tree_fully_traced": coverage.get("all_changes_traced") is True,
        "task_tree_acceptance_mapped": not coverage.get("unmapped_acceptance_ids"),
        "contract_alignment": alignment.get("status") == "aligned",
        "strategy_is_actionable": deterministic.get("action") not in {None, "", "unknown"},
        "sandbox_candidate_available": candidate.get("status") not in {None, "not_available", "none"},
        "verifier_commands_have_no_failure": not any(row.get("status") == "failed" for row in commands),
    }
    return {
        "executor_status": executor.get("status"),
        "signal_strength": summary.get("signal_strength"),
        "skipped_target_count": len(skipped_targets),
        "strategy_action": deterministic.get("action"),
        "sandbox_candidate_status": candidate.get("status"),
        "checks": checks,
    }


def _report(cases: list[dict[str, Any]], target_score: float) -> dict[str, Any]:
    minima = {
        role_id: min((case["role_scores"][role_id] for case in cases), default=0.0)
        for role_id in ROLE_IDS
    }
    below_target = [
        {"project": case["project"], "project_min_score": case.get("project_min_score", 0.0), "role_scores": case["role_scores"]}
        for case in cases
        if min(case["role_scores"].values()) < target_score
    ]
    return {
        "artifact_type": "RolePipelineMinimumFieldTrialReport",
        "status": "ok" if not below_target else "needs_work",
        "milestone": "Implementer -> TaskTree -> Programmer -> Tester -> Reviewer minimum field trial",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_count": len(cases),
        "target_score": target_score,
        "summary": {
            "role_min_scores": minima,
            "project_min_score": min(minima.values(), default=0.0),
            "below_target_count": len(below_target),
            "source_code_changes": sum(case.get("safety", {}).get("source_code_changes") is True for case in cases),
            "score_policy": "minimum per role across eligible Python-owned projects",
        },
        "below_target": below_target,
        "cases": cases,
    }
