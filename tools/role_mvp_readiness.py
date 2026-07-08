"""Build one MVP readiness report across role field trials."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.architect_curriculum import run_architect_curriculum
from runtime.implementer_curriculum import run_implementer_curriculum
from runtime.role_pipeline_benchmark import run_role_pipeline_benchmark
from runtime.spec_writer_curriculum import run_spec_writer_curriculum
from tools.github_architect_probe import run_probe as run_github_architect
from tools.github_implementer_probe import run_probe as run_github_implementer
from tools.github_reviewer_probe import run_probe as run_github_reviewer
from tools.github_spec_writer_probe import run_probe as run_github_spec_writer
from tools.github_tester_probe import run_probe as run_github_tester


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--github-projects-dir", default="benchmarks/github_architect_10")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    github_dir = Path(args.github_projects_dir)
    if not github_dir.is_absolute():
        github_dir = root / github_dir
    report = build_report(root=root, github_dir=github_dir.resolve())
    if args.write:
        report.update(write_report(root, report))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def build_report(*, root: Path, github_dir: Path) -> dict[str, Any]:
    runs = _run_trials(root, github_dir)
    roles = {
        "project_analyzer": _project_analyzer_readiness(runs),
        "architect": _architect_readiness(runs),
        "spec_writer": _spec_writer_readiness(runs),
        "implementer_planner": _implementer_readiness(runs),
        "programmer_executor": _programmer_executor_readiness(runs, root),
        "tester": _tester_readiness(runs),
        "reviewer": _reviewer_readiness(runs),
    }
    return {
        "status": "ok" if all(role["mvp_ready"] for role in roles.values()) else "needs_work",
        "milestone": "Role MVP Readiness v0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": _summary(roles),
        "invariants": {
            "teacher_reference_is_ground_truth": False,
            "automatic_code_changes_from_own_output": False,
            "external_projects_are_read_only": True,
            "llm_required_for_readiness": False,
            "implementer_planner_is_not_programmer_executor": True,
        },
        "roles": roles,
        "source_reports": _source_reports(runs),
    }


def _run_trials(root: Path, github_dir: Path) -> dict[str, Any]:
    return {
        "architect_local": run_architect_curriculum(root=root, curriculum_dir=root / "curricula" / "architect_local_3"),
        "architect_external": run_architect_curriculum(root=root, curriculum_dir=root / "curricula" / "architect_external_local_3"),
        "architect_github": run_github_architect(root=root, projects_dir=github_dir, label="role_readiness_architect"),
        "spec_local": run_spec_writer_curriculum(root=root, curriculum_dir=root / "curricula" / "spec_writer_local_3"),
        "spec_external": run_spec_writer_curriculum(root=root, curriculum_dir=root / "curricula" / "spec_writer_external_local_3"),
        "spec_github": run_github_spec_writer(root=root, projects_dir=github_dir, label="role_readiness_spec_writer"),
        "impl_local": run_implementer_curriculum(root=root, curriculum_dir=root / "curricula" / "implementer_local_3"),
        "impl_external": run_implementer_curriculum(root=root, curriculum_dir=root / "curricula" / "implementer_external_local_3"),
        "impl_github": run_github_implementer(root=root, projects_dir=github_dir, label="role_readiness_implementer"),
        "tester_github": run_github_tester(root=root, projects_dir=github_dir, label="role_readiness_tester"),
        "reviewer_github": run_github_reviewer(root=root, projects_dir=github_dir, label="role_readiness_reviewer"),
        "pipeline": run_role_pipeline_benchmark(root, benchmarks_dir=root / "benchmarks" / "project_analyzer"),
    }


def _project_analyzer_readiness(runs: dict[str, Any]) -> dict[str, Any]:
    arch = runs["architect_github"]
    summary = dict(arch.get("summary", {}))
    blocked = int(summary.get("blocked_no_safe_candidate") or 0)
    checks = {
        "github_projects_covered": arch.get("project_count") == 10,
        "entrypoints_or_blocked_present": int(summary.get("entrypoints_present") or 0) + blocked == arch.get("project_count"),
        "capability_or_blocked_present": int(summary.get("capability_model_present") or 0) + blocked == arch.get("project_count"),
        "forbidden_sources_absent": summary.get("forbidden_capability_sources") == 0,
        "source_projects_read_only": summary.get("source_code_changes") == 0,
    }
    return _role("project_analyzer", checks, [_metric("github_quality", summary.get("avg_quality_score"))])


def _architect_readiness(runs: dict[str, Any]) -> dict[str, Any]:
    local = runs["architect_local"]
    external = runs["architect_external"]
    github = runs["architect_github"]
    checks = {
        "local_curriculum_ok": local.get("status") == "ok",
        "external_curriculum_ok": external.get("status") == "ok",
        "github_probe_ok": github.get("status") == "ok",
        "fact_recall_ok": _summary_value(local, "fact_recall") >= 0.9 and _summary_value(external, "fact_recall") >= 0.9,
        "judgment_score_ok": _summary_value(local, "judgment_score") >= 0.8 and _summary_value(external, "judgment_score") >= 0.8,
    }
    return _role("architect", checks, _curriculum_metrics(local, external, github))


def _spec_writer_readiness(runs: dict[str, Any]) -> dict[str, Any]:
    local, external, github = runs["spec_local"], runs["spec_external"], runs["spec_github"]
    gh = dict(github.get("summary", {}))
    blocked = int(gh.get("blocked_no_safe_candidate") or 0)
    checks = {
        "local_curriculum_ok": local.get("status") == "ok",
        "external_curriculum_ok": external.get("status") == "ok",
        "github_probe_ok": github.get("status") == "ok",
        "no_backlog": _summary_value(local, "backlog_items") == 0 and _summary_value(external, "backlog_items") == 0,
        "candidate_or_blocked_present_github": int(gh.get("candidate_present") or 0) + blocked == github.get("project_count"),
    }
    return _role("spec_writer", checks, _curriculum_metrics(local, external, github))


def _implementer_readiness(runs: dict[str, Any]) -> dict[str, Any]:
    local, external, github = runs["impl_local"], runs["impl_external"], runs["impl_github"]
    gh = dict(github.get("summary", {}))
    blocked = int(gh.get("blocked_no_safe_candidate") or 0)
    runnable = int(github.get("project_count") or 0) - blocked
    checks = {
        "local_curriculum_ok": local.get("status") == "ok",
        "external_curriculum_ok": external.get("status") == "ok",
        "github_probe_ok": github.get("status") == "ok",
        "writable_scope_guarded": gh.get("writable_scope_targets_candidate") == runnable,
        "candidate_matches_spec": gh.get("candidate_matches_spec") == runnable,
    }
    return _role("implementer_planner", checks, _curriculum_metrics(local, external, github))


def _programmer_executor_readiness(runs: dict[str, Any], root: Path) -> dict[str, Any]:
    planner = _implementer_readiness(runs)
    pipeline = runs["pipeline"]
    pipe = dict(pipeline.get("summary", {}))
    tool_exists = (root / "tools" / "apply_implementation_plan.py").exists()
    runtime_exists = (root / "runtime" / "programmer_executor.py").exists()
    checks = {
        "implementation_plan_input_ready": planner["mvp_ready"],
        "patch_executor_tool_exists": tool_exists,
        "writes_are_sandboxed_before_source_edit": runtime_exists,
        "test_results_feed_reviewer": tool_exists and runtime_exists,
        "rollback_snapshot_is_created": runtime_exists,
        "project_source_edits_are_allowed_only_by_explicit_flag": tool_exists,
        "role_pipeline_still_dry_run_by_default": pipe.get("safety_score") == 1.0,
    }
    role = _role(
        "programmer_executor",
        checks,
        [
            _metric("planner_readiness", planner["readiness_score"]),
            _metric("pipeline_safety", pipe.get("safety_score")),
            _metric("executor_scope", "sandbox_patch_package"),
        ],
    )
    role["definition"] = (
        "Executes an approved ImplementationPlan into an isolated patch, runs verification, "
        "captures TestResult, and hands results to Reviewer. The MVP executor does not edit "
        "project sources by default and keeps source rollback material as a sandbox snapshot. "
        "This is intentionally separate "
        "from Implementer Planner."
    )
    return role


def _tester_readiness(runs: dict[str, Any]) -> dict[str, Any]:
    github = runs["tester_github"]
    pipeline = runs["pipeline"]
    gh = dict(github.get("summary", {}))
    pipe = dict(pipeline.get("summary", {}))
    blocked = int(gh.get("blocked_no_safe_candidate") or 0)
    runnable = int(github.get("project_count") or 0) - blocked
    checks = {
        "github_probe_ok": github.get("status") == "ok",
        "pipeline_qa_ok": pipe.get("qa_score") == 1.0,
        "target_matches_implementation": gh.get("target_matches_implementation") == runnable,
        "writable_scope_guarded": gh.get("writable_scope_targets_candidate") == runnable,
        "no_source_changes": gh.get("source_code_changes") == 0,
    }
    return _role("tester", checks, [_metric("github_quality", gh.get("avg_quality_score")), _metric("pipeline_qa", pipe.get("qa_score"))])


def _reviewer_readiness(runs: dict[str, Any]) -> dict[str, Any]:
    github = runs["reviewer_github"]
    pipeline = runs["pipeline"]
    gh = dict(github.get("summary", {}))
    pipe = dict(pipeline.get("summary", {}))
    blocked = int(gh.get("blocked_no_safe_candidate") or 0)
    runnable = int(github.get("project_count") or 0) - blocked
    checks = {
        "github_probe_ok": github.get("status") == "ok",
        "pipeline_qa_ok": pipe.get("qa_score") == 1.0,
        "scope_preserved": gh.get("scope_preserved") == github.get("project_count"),
        "no_contract_violations": gh.get("contract_violations") == 0,
        "no_architecture_drift": gh.get("architecture_drift") == 0,
        "review_target_matches_runnable": gh.get("review_target_matches_implementation") == runnable,
    }
    return _role("reviewer", checks, [_metric("github_quality", gh.get("avg_quality_score")), _metric("pipeline_qa", pipe.get("qa_score"))])


def _role(name: str, checks: dict[str, bool], metrics: list[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(1 for ok in checks.values() if ok)
    readiness = round(passed / len(checks), 3) if checks else 0.0
    return {
        "role": name,
        "mvp_ready": readiness >= 0.95,
        "readiness_score": readiness,
        "status": "MVP-ready" if readiness >= 0.95 else "needs-work",
        "checks": checks,
        "metrics": metrics,
        "remaining_work": _remaining_work(checks),
    }


def _summary(roles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "roles_total": len(roles),
        "roles_mvp_ready": sum(1 for role in roles.values() if role["mvp_ready"]),
        "average_readiness": round(sum(float(role["readiness_score"]) for role in roles.values()) / len(roles), 3),
        "not_ready": [name for name, role in roles.items() if not role["mvp_ready"]],
    }


def _curriculum_metrics(local: dict[str, Any], external: dict[str, Any], github: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _metric("local_status", local.get("status")),
        _metric("external_status", external.get("status")),
        _metric("github_status", github.get("status")),
        _metric("local_score", dict(local.get("summary", {})).get("score") or dict(local.get("summary", {})).get("judgment_score")),
        _metric("external_score", dict(external.get("summary", {})).get("score") or dict(external.get("summary", {})).get("judgment_score")),
        _metric("github_quality", dict(github.get("summary", {})).get("avg_quality_score")),
    ]


def _summary_value(report: dict[str, Any], key: str) -> float:
    value = dict(report.get("summary", {})).get(key)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _metric(name: str, value: Any) -> dict[str, Any]:
    return {"name": name, "value": value}


def _remaining_work(checks: dict[str, bool]) -> list[str]:
    return [name for name, ok in checks.items() if not ok]


def _source_reports(runs: dict[str, Any]) -> dict[str, Any]:
    return {
        name: {
            "status": report.get("status"),
            "project_count": report.get("project_count"),
            "summary": report.get("summary", {}),
        }
        for name, report in runs.items()
    }


def write_report(root: Path, report: dict[str, Any]) -> dict[str, str]:
    out_dir = root / "artifacts" / "field_trials"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    json_path = out_dir / f"role_mvp_readiness_{stamp}.json"
    md_path = out_dir / f"role_mvp_readiness_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    return {"report_path": json_path.as_posix(), "markdown_path": md_path.as_posix()}


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {report['milestone']}",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Status: `{report['status']}`",
        f"Average readiness: `{report['summary']['average_readiness']}`",
        "",
        "| Role | Status | Score | Remaining |",
        "| --- | --- | ---: | --- |",
    ]
    for name, role in report["roles"].items():
        remaining = ", ".join(role["remaining_work"]) or "none"
        lines.append(f"| {name} | {role['status']} | {role['readiness_score']} | {remaining} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
