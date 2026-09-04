"""Minimum-based field trial for downstream implementation roles."""

from __future__ import annotations

import contextlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .project_execution_isolation import isolated_project_execution
from .role_pipeline import run_role_pipeline
from .role_project_type_evaluation import classify_project_case
from .role_chain_interaction import build_role_chain_trace, summarize_role_chain_traces


ROLE_IDS = ("implementer", "task_tree_builder", "programmer_executor", "tester", "reviewer")


def run_role_pipeline_min_field_trial(
    *,
    root: Path,
    projects_dir: Path,
    eligible_projects: set[str] | None = None,
    project_classifications: dict[str, dict[str, Any]] | None = None,
    limit: int = 0,
    target_score: float = 9.7,
    write: bool = False,
) -> dict[str, Any]:
    projects = sorted(path for path in projects_dir.iterdir() if path.is_dir())
    if eligible_projects is not None:
        projects = [path for path in projects if path.name in eligible_projects]
    if limit:
        projects = projects[:limit]
    cases = [_run_case(root, project, (project_classifications or {}).get(project.name)) for project in projects]
    report = _report(cases, target_score, source_lineage=projects_dir.resolve().as_posix())
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


def project_classifications_from_foundation_reports(paths: list[Path]) -> dict[str, dict[str, Any]]:
    classifications: dict[str, dict[str, Any]] = {}
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for case in payload.get("cases", []):
            if not isinstance(case, dict) or case.get("status") in {"out_of_scope", "failed"}:
                continue
            classifications[str(case.get("project") or "")] = classify_project_case(case)
    return classifications


def _run_case(root: Path, project_dir: Path, inherited_classification: dict[str, Any] | None = None) -> dict[str, Any]:
    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    try:
        with isolated_project_execution(), contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(captured_stderr):
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
    project_classification = inherited_classification or classify_project_case({
        "project": project_dir.name,
        "artifacts": result.get("artifacts", {}),
        "role_quality": result.get("role_quality", {}),
        "programmer_evidence": _programmer_evidence(result),
    })
    chain_trace = build_role_chain_trace(project=project_dir.name, result=result)
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
        "project_classification": project_classification,
        "role_chain_interaction": chain_trace,
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
    patch_package = _read_json(executor.get("patch_package_path"))
    test_result = dict(executor.get("test_result", {}))
    acceptance = dict(test_result.get("executable_acceptance_result", {}))
    summary = dict(acceptance.get("summary", {}))
    strategy = dict(test_result.get("executor_strategy", {}))
    deterministic = dict(strategy.get("deterministic_strategy", {}))
    alignment = dict(strategy.get("contract_alignment", {}))
    candidate = dict(strategy.get("sandbox_patch_candidate", {}))
    synthesis = dict(patch_package.get("patch_synthesis", {}))
    delta = dict(patch_package.get("implementation_delta") or {})
    if not delta:
        delta = dict(patch_package.get("patch_intent", {}).get("implementation_delta") or {})
    verification_only = delta.get("status") == "verification_only" or synthesis.get("status") == "verification_only"
    deterministic_candidate = synthesis.get("status") == "prepared" and bool(patch_package.get("patches"))
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
        "requested_route_satisfied": verification_only or deterministic_candidate
        or candidate.get("status") not in {None, "not_available", "none"},
        "verifier_commands_have_no_failure": not any(row.get("status") == "failed" for row in commands),
    }
    return {
        "executor_status": executor.get("status"),
        "signal_strength": summary.get("signal_strength"),
        "skipped_target_count": len(skipped_targets),
        "strategy_action": deterministic.get("action"),
        "sandbox_candidate_status": candidate.get("status"),
        "deterministic_patch_count": len(patch_package.get("patches", [])),
        "patch_synthesis_status": synthesis.get("status"),
        "implementation_delta_status": delta.get("status"),
        "transformation_evaluated": not verification_only,
        "checks": checks,
    }


def _read_json(path: object) -> dict[str, Any]:
    if not path:
        return {}
    target = Path(str(path))
    if not target.is_file():
        return {}
    return json.loads(target.read_text(encoding="utf-8"))


def _report(
    cases: list[dict[str, Any]], target_score: float, *, source_lineage: str | None = None
) -> dict[str, Any]:
    minima = {
        role_id: min((case["role_scores"][role_id] for case in cases), default=0.0)
        for role_id in ROLE_IDS
    }
    below_target = [
        {"project": case["project"], "project_min_score": case.get("project_min_score", 0.0), "role_scores": case["role_scores"]}
        for case in cases
        if min(case["role_scores"].values()) < target_score
    ]
    transformation_cases = [
        case for case in cases
        if dict(case.get("programmer_evidence") or {}).get("transformation_evaluated") is True
    ]
    chain_summary = summarize_role_chain_traces([
        dict(case.get("role_chain_interaction") or {})
        for case in cases
        if case.get("role_chain_interaction")
    ])
    return {
        "artifact_type": "RolePipelineMinimumFieldTrialReport",
        "status": "ok" if not below_target else "needs_work",
        "milestone": "Implementer -> TaskTree -> Programmer -> Tester -> Reviewer minimum field trial",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_lineage": source_lineage,
        "project_count": len(cases),
        "target_score": target_score,
        "summary": {
            "role_min_scores": minima,
            "project_min_score": min(minima.values(), default=0.0),
            "below_target_count": len(below_target),
            "source_code_changes": sum(case.get("safety", {}).get("source_code_changes") is True for case in cases),
            "score_policy": "minimum per role across eligible Python-owned projects",
            "programmer_transformation_case_count": len(transformation_cases),
            "programmer_verification_only_count": len(cases) - len(transformation_cases),
            "programmer_transformation_min_score": min(
                (case["role_scores"]["programmer_executor"] for case in transformation_cases),
                default=None,
            ),
            "role_chain": chain_summary,
        },
        "below_target": below_target,
        "cases": cases,
    }
