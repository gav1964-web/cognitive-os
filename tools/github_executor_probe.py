"""Run Executor over role-produced TestPlans for cloned GitHub projects."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.configured_role_pipeline import artifact_by_type, run_configured_role_prefix
from runtime.executor_solution_patterns import select_solution_patterns
from runtime.programmer_executor import run_programmer_executor
from runtime.project_benchmark import analyze_project


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--projects-dir", required=True)
    parser.add_argument("--label", default="github_executor_probe")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--run-verification", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    projects_dir = Path(args.projects_dir)
    if not projects_dir.is_absolute():
        projects_dir = root / projects_dir
    report = run_probe(
        root=root,
        projects_dir=projects_dir.resolve(),
        label=args.label,
        run_verification=args.run_verification,
    )
    if args.write:
        report.update(write_report(root, report, args.label))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def run_probe(*, root: Path, projects_dir: Path, label: str, run_verification: bool = False) -> dict[str, Any]:
    cases = [
        _run_case(root=root, project_dir=project_dir, run_verification=run_verification)
        for project_dir in sorted(projects_dir.iterdir())
        if (project_dir / ".git").exists()
    ]
    summary = _summary(cases)
    return {
        "artifact_type": "GitHubExecutorProbe",
        "status": "ok" if summary["accepted"] == len(cases) else "needs_review",
        "milestone": label,
        "generated_at": _now(),
        "project_count": len(cases),
        "summary": summary,
        "invariants": {
            "apply_source": False,
            "run_verification": run_verification,
            "source_projects_modified": summary["source_code_changes"],
            "llm_invoked": False,
        },
        "cases": cases,
    }


def _run_case(*, root: Path, project_dir: Path, run_verification: bool) -> dict[str, Any]:
    try:
        project_dir = project_dir.resolve()
        before = _git_porcelain(project_dir)
        project_report = analyze_project(project_dir)["project_map_report"]
        artifacts = run_configured_role_prefix(
            goal=f"GitHub Executor probe for {project_dir.name}",
            project_report=project_report,
            until_artifact_type="TestPlan",
        )
        spec = artifact_by_type(artifacts, "TechnicalSpec")
        plan = artifact_by_type(artifacts, "ImplementationPlan")
        test_plan = artifact_by_type(artifacts, "TestPlan")
        profile = _contract_profile_fields(spec, plan, test_plan)
        result = run_programmer_executor(
            root=root,
            project_dir=project_dir,
            technical_spec=spec,
            implementation_plan=plan,
            test_plan=test_plan,
            run_verification=run_verification,
            apply_source=False,
        )
        task_tree = _read_json(result.get("task_tree_path"))
        tree = _task_tree_fields(task_tree)
        if result.get("status") == "blocked":
            after = _git_porcelain(project_dir)
            reason = str(result.get("reason") or "")
            no_patch = _read_json(result.get("no_patch_package_path"))
            ok = reason in {"blocked_no_safe_candidate", "context_only_implementation_target"} and before == after
            return {
                "project": project_dir.name,
                "project_dir": project_dir.as_posix(),
                "status": "blocked_ok" if ok else "needs_review",
                "executor_status": result.get("status"),
                "blocked_reason": reason,
                "no_patch_package": no_patch.get("artifact_type"),
                "test_result_status": None,
                "executable_acceptance": None,
                "callable_harness_count": 0,
                "acceptance_signal": "blocked",
                "acceptance_skipped_reasons": {},
                "acceptance_skipped_targets": [],
                "effect_module_stub_targets": {},
                "boundary_track": "blocked_handoff",
                **profile,
                **tree,
                "patch_synthesis": "blocked",
                "patch_reason": reason,
                "patch_quality_level": "blocked_handoff",
                "patch_quality_review_required": False,
                "solution_pattern_ids": _solution_pattern_ids(
                    {
                        "acceptance_signal": "blocked",
                        "patch_synthesis": "blocked",
                        "patch_reason": reason,
                        "patch_quality_level": "blocked_handoff",
                        "patch_quality_review_required": False,
                    }
                ),
                "target": str(dict(plan.get("implementation_target", {})).get("candidate") or ""),
                "source_code_changes": before != after,
            }
        test_result = _read_json(result.get("test_result_path"))
        executable = dict(test_result.get("executable_acceptance_result") or {})
        acceptance = dict(executable.get("summary") or {})
        patch = _read_json(result.get("patch_package_path"))
        patch_synthesis = dict(patch.get("patch_synthesis") or {})
        patch_quality = dict(dict(patch.get("patch_strategy") or {}).get("patch_quality") or {})
        strategy = _strategy_fields(dict(test_result.get("executor_strategy") or patch.get("patch_strategy") or {}))
        candidate_attempt = _candidate_attempt_fields(dict(test_result.get("sandbox_candidate_attempt") or {}))
        repair_attempt = _repair_attempt_fields(dict(test_result.get("sandbox_candidate_repair_attempt") or {}))
        after = _git_porcelain(project_dir)
        ok = result.get("status") == "ok" and executable.get("status") == "passed" and before == after
        boundary_track = _boundary_track(acceptance)
        return {
            "project": project_dir.name,
            "project_dir": project_dir.as_posix(),
            "status": "ok" if ok else "needs_review",
            "executor_status": result.get("status"),
            "test_result_status": test_result.get("status"),
            "executable_acceptance": executable.get("status"),
            "callable_harness_count": acceptance.get("callable_harness_count"),
            "acceptance_signal": acceptance.get("signal_strength"),
            "acceptance_skipped_reasons": acceptance.get("skipped_reason_counts"),
            "acceptance_skipped_targets": acceptance.get("skipped_targets"),
            "effect_module_stub_targets": acceptance.get("effect_module_stub_targets", {}),
            "boundary_track": boundary_track,
            **profile,
            **tree,
            "patch_synthesis": patch_synthesis.get("status"),
            "patch_reason": patch_synthesis.get("reason"),
            "patch_quality_level": str(patch_quality.get("level") or ""),
            "patch_quality_review_required": bool(patch_quality.get("review_required")),
            **strategy,
            **candidate_attempt,
            **repair_attempt,
            "target": str(dict(plan.get("implementation_target", {})).get("candidate") or ""),
            "source_code_changes": before != after,
        }
    except (Exception, SystemExit) as exc:  # field-trial isolation includes argparse exits from foreign projects.
        return {"project": project_dir.name, "project_dir": project_dir.as_posix(), "status": "failed", "error": f"{type(exc).__name__}: {exc}"}


def write_report(root: Path, report: dict[str, Any], label: str) -> dict[str, str]:
    report_dir = root / "artifacts" / "field_trials"
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = report_dir / f"{label}_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"report_path": path.as_posix()}


def _summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    ok = sum(case["status"] == "ok" for case in cases)
    blocked = sum(case["status"] == "blocked_ok" for case in cases)
    return {
        "ok": ok,
        "blocked_no_safe_candidate": blocked,
        "accepted": ok + blocked,
        "needs_review": sum(case["status"] == "needs_review" for case in cases),
        "failed": sum(case["status"] == "failed" for case in cases),
        "executor_ok": sum(case.get("executor_status") == "ok" for case in cases),
        "executor_blocked": sum(case.get("executor_status") == "blocked" for case in cases),
        "executable_acceptance_passed": sum(case.get("executable_acceptance") == "passed" for case in cases),
        "patch_prepared": sum(case.get("patch_synthesis") == "prepared" for case in cases),
        "patch_blocked": sum(case.get("patch_synthesis") == "blocked" for case in cases),
        "patch_skipped": sum(case.get("patch_synthesis") == "skipped" for case in cases),
        "patch_quality_levels": _counts(_patch_quality_level(case) for case in cases),
        "patch_quality_review_required": sum(bool(case.get("patch_quality_review_required")) for case in cases),
        "acceptance_callable": sum(case.get("acceptance_signal") == "executable_callable" for case in cases),
        "acceptance_meta_only": sum(case.get("acceptance_signal") == "meta_only" for case in cases),
        "acceptance_effect_stubbed": sum(bool(case.get("effect_module_stub_targets")) for case in cases),
        "effect_stub_modules": _counts(
            module
            for case in cases
            for modules in dict(case.get("effect_module_stub_targets") or {}).values()
            for module in list(modules or [])
        ),
        "boundary_tracks": _counts(str(case.get("boundary_track") or "unknown") for case in cases),
        "contract_profiles": _counts(str(case.get("contract_profile_id") or "none") for case in cases),
        "contract_profile_operators": _counts(str(case.get("contract_profile_operator_id") or "none") for case in cases),
        "dependency_readiness_statuses": _counts(str(case.get("dependency_readiness_status") or "unknown") for case in cases),
        "dependency_missing_modules": _counts(
            module for case in cases for module in list(case.get("dependency_missing_modules") or [])
        ),
        "task_tree_statuses": _counts(str(case.get("task_tree_status") or "unknown") for case in cases),
        "task_tree_boundaries": _counts(str(case.get("task_tree_boundary") or "unknown") for case in cases),
        "task_tree_dependency_edges_total": sum(int(case.get("task_tree_dependency_edge_count") or 0) for case in cases),
        "task_tree_unmapped_acceptance_total": sum(int(case.get("task_tree_unmapped_acceptance_count") or 0) for case in cases),
        "task_tree_changes_traced": sum(case.get("task_tree_all_changes_traced") is True for case in cases),
        "strategy_actions": _counts(str(case.get("strategy_action") or "unknown") for case in cases),
        "contract_rebind_requested": sum(bool(case.get("contract_rebind_requested")) for case in cases),
        "contract_rebind_reasons": _counts(
            str(case.get("contract_rebind_reason"))
            for case in cases
            if case.get("contract_rebind_requested")
        ),
        "executor_playbooks": _counts(playbook for case in cases for playbook in list(case.get("executor_playbook_ids") or [])),
        "solution_patterns": _counts(pattern for case in cases for pattern in list(case.get("solution_pattern_ids") or [])),
        "llm_strategy_statuses": _counts(str(case.get("llm_strategy_status") or "none") for case in cases),
        "sandbox_candidate_statuses": _counts(str(case.get("sandbox_candidate_status") or "none") for case in cases),
        "sandbox_candidate_attempt_statuses": _counts(
            str(case.get("sandbox_candidate_attempt_status") or "none") for case in cases
        ),
        "sandbox_candidate_repair_statuses": _counts(
            str(case.get("sandbox_candidate_repair_status") or "none") for case in cases
        ),
        "source_code_changes": sum(bool(case.get("source_code_changes")) for case in cases),
    }


def _contract_profile_fields(spec: dict[str, Any], plan: dict[str, Any], test_plan: dict[str, Any]) -> dict[str, Any]:
    extraction = dict(spec.get("extraction_contract") or {})
    readiness = dict(extraction.get("dependency_readiness") or {})
    spec_profile = dict(dict(spec.get("extraction_contract") or {}).get("contract_profile") or {})
    plan_profile = dict(dict(plan.get("contract_binding") or {}).get("contract_profile") or {})
    test_profile = _first_test_plan_profile(test_plan)
    profile = test_profile or plan_profile or spec_profile
    return {
        "contract_profile_id": str(profile.get("id") or ""),
        "contract_profile_operator_id": str(profile.get("operator_id") or ""),
        "contract_profile_source": str(profile.get("source") or ("test_plan" if test_profile else "")),
        "dependency_readiness_status": str(readiness.get("status") or "unknown"),
        "dependency_missing_modules": [str(item) for item in list(readiness.get("missing_external_modules") or [])],
    }


def _first_test_plan_profile(test_plan: dict[str, Any]) -> dict[str, Any]:
    for obligation in list(dict(test_plan.get("executable_acceptance") or {}).get("obligations") or []):
        if not isinstance(obligation, dict):
            continue
        profile = dict(obligation.get("contract_profile") or {})
        if profile:
            return profile
    return {}


def _strategy_fields(strategy: dict[str, Any]) -> dict[str, Any]:
    deterministic = dict(strategy.get("deterministic_strategy") or {})
    llm = dict(strategy.get("llm_strategy") or {})
    candidate = dict(strategy.get("sandbox_patch_candidate") or {})
    playbooks = [str(row.get("id") or "") for row in list(strategy.get("executor_playbooks") or []) if isinstance(row, dict)]
    patterns = [str(row.get("id") or "") for row in list(strategy.get("solution_patterns") or []) if isinstance(row, dict)]
    rebind = dict(strategy.get("contract_rebind_request") or {})
    return {
        "strategy_action": str(deterministic.get("action") or ""),
        "strategy_reason": str(deterministic.get("reason") or ""),
        "executor_playbook_ids": [item for item in playbooks if item],
        "solution_pattern_ids": [item for item in patterns if item],
        "llm_strategy_status": str(llm.get("status") or "none"),
        "sandbox_candidate_status": str(candidate.get("status") or "none"),
        "contract_rebind_requested": bool(rebind),
        "contract_rebind_reason": str(rebind.get("reason") or ""),
        "contract_rebind_candidates": [
            str(row.get("target") or "")
            for row in list(rebind.get("candidate_targets") or [])
            if isinstance(row, dict) and row.get("target")
        ],
    }


def _solution_pattern_ids(context: dict[str, Any]) -> list[str]:
    return [str(row.get("id") or "") for row in select_solution_patterns(context) if row.get("id")]


def _patch_quality_level(case: dict[str, Any]) -> str:
    if case.get("patch_quality_level"):
        return str(case.get("patch_quality_level"))
    if case.get("patch_synthesis") == "blocked":
        return "blocked_handoff"
    if case.get("patch_synthesis") == "skipped":
        return "verified_no_patch"
    return "none"


def _task_tree_fields(task_tree: dict[str, Any]) -> dict[str, Any]:
    summary = dict(task_tree.get("summary") or {})
    coverage = dict(task_tree.get("coverage") or {})
    return {
        "task_tree_status": str(task_tree.get("status") or ""),
        "task_tree_boundary": str(dict(task_tree.get("boundary") or {}).get("track") or ""),
        "task_tree_node_count": int(summary.get("node_count") or 0),
        "task_tree_change_node_count": int(summary.get("change_node_count") or 0),
        "task_tree_acceptance_node_count": int(summary.get("acceptance_node_count") or 0),
        "task_tree_dependency_edge_count": int(summary.get("dependency_edge_count") or 0),
        "task_tree_unmapped_acceptance_count": len(list(coverage.get("unmapped_acceptance_ids") or [])),
        "task_tree_all_changes_traced": coverage.get("all_changes_traced") is True,
    }


def _candidate_attempt_fields(candidate_attempt: dict[str, Any]) -> dict[str, str]:
    return {
        "sandbox_candidate_attempt_status": str(candidate_attempt.get("status") or ""),
        "sandbox_candidate_attempt_reason": str(candidate_attempt.get("reason") or ""),
    }


def _repair_attempt_fields(repair_attempt: dict[str, Any]) -> dict[str, str]:
    return {
        "sandbox_candidate_repair_status": str(repair_attempt.get("status") or ""),
        "sandbox_candidate_repair_reason": str(repair_attempt.get("reason") or ""),
    }


def _boundary_track(acceptance: dict[str, Any]) -> str:
    if acceptance.get("signal_strength") == "executable_callable":
        return "pure_python_callable"
    reasons = dict(acceptance.get("skipped_reason_counts") or {})
    details = " ".join(
        str(item.get("detail") or item.get("target") or "")
        for item in list(acceptance.get("skipped_targets") or [])
        if isinstance(item, dict)
    ).lower()
    if any(token in details for token in ("_rust", "_imaging", "crypto.low_level", "zmq.backend")):
        return "native_extension_boundary"
    if reasons.get("import_failed_missing_module") or reasons.get("import_failed_import_error"):
        return "optional_dependency_boundary"
    if reasons.get("positive_sample_execution_failed") or reasons.get("method_target_needs_instance_fixture"):
        return "fixture_or_runtime_shape_boundary"
    return "meta_only_boundary" if acceptance.get("signal_strength") == "meta_only" else "unknown"


def _counts(values: Any) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        if not value:
            continue
        result[value] = result.get(value, 0) + 1
    return dict(sorted(result.items()))


def _read_json(path: object) -> dict[str, Any]:
    if not path:
        return {}
    source = Path(str(path))
    if not source.is_file():
        return {}
    return json.loads(source.read_text(encoding="utf-8"))


def _git_porcelain(project_dir: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_dir), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "__git_status_unavailable__"
    return result.stdout.strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
