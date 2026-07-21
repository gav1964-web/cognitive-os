"""Run Project Analyzer -> Architect -> SpecWriter -> Implementer over GitHub projects."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.project_benchmark import analyze_project
from runtime.configured_role_pipeline import artifact_by_type, producer_for_artifact_type, run_configured_role_prefix


FORBIDDEN_SOURCE_TOKENS = (
    "/benchmarks/",
    "/bench/",
    "/ci_tools/",
    "/docs/",
    "/downstream/",
    "/examples/",
    "/failures-to-investigate/",
    "/packaging/pep517_backend/",
    "/scripts/",
    "/tasks/",
    "/test/",
    "/tests/",
    "/tools/",
    "benchmark.py",
    "bench.py",
    "_bench.py",
    "_benchmark.py",
    "noxfile.py",
    "testclient.py",
    "testing.py",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--projects-dir", required=True)
    parser.add_argument("--label", default="github_implementer_probe")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    projects_dir = Path(args.projects_dir)
    if not projects_dir.is_absolute():
        projects_dir = root / projects_dir
    report = run_probe(root=root, projects_dir=projects_dir.resolve(), label=args.label)
    if args.write:
        report.update(write_report(root, report, args.label))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def run_probe(*, root: Path, projects_dir: Path, label: str) -> dict[str, Any]:
    cases = [_run_case(project_dir) for project_dir in sorted(projects_dir.iterdir()) if (project_dir / ".git").exists()]
    return {
        "status": "ok" if all(case["status"] in {"ok", "blocked_ok"} for case in cases) else "needs_review",
        "milestone": label,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_count": len(cases),
        "summary": _summary(cases),
        "invariants": {
            "llm_invoked": False,
            "source_projects_modified": any(case["source_code_changes"] for case in cases),
            "registry_changes": False,
            "teacher_reference_is_ground_truth": False,
            "automatic_code_changes_from_own_output": False,
            "downstream_roles_not_in_scope": True,
            "foundry_or_promote_not_in_scope": True,
        },
        "cases": cases,
    }


def _run_case(project_dir: Path) -> dict[str, Any]:
    project_report = analyze_project(project_dir)["project_map_report"]
    artifacts = run_configured_role_prefix(
        goal=f"GitHub Implementer probe for {project_dir.name}",
        project_report=project_report,
        until_artifact_type="ImplementationPlan",
    )
    spec = artifact_by_type(artifacts, "TechnicalSpec")
    plan = artifact_by_type(artifacts, "ImplementationPlan")
    contract = dict(spec.get("extraction_contract", {}))
    target = dict(plan.get("implementation_target", {}))
    binding = dict(plan.get("contract_binding", {}))
    candidate = str(target.get("candidate") or "")
    expected_files = [str(item) for item in plan.get("expected_files", []) if item]
    patch_scope = [str(item) for item in plan.get("patch_scope", []) if item]
    writable_scope = [str(item) for item in plan.get("writable_scope", []) if item]
    forbidden = [value for value in [candidate, *expected_files, *patch_scope, *writable_scope] if _is_forbidden_source(value)]
    blocked_reason = _blocked_reason(project_report)
    quality = _quality_score(spec, plan, candidate, binding, forbidden, writable_scope)
    status = "ok" if quality >= 0.9 and not forbidden else "needs_review"
    if blocked_reason == "no_safe_python_candidate" and not candidate and not writable_scope and not forbidden:
        status = "blocked_ok"
        quality = 1.0
    return {
        "project": project_dir.name,
        "project_dir": project_dir.as_posix(),
        "status": status,
        "quality_score": quality,
        "blocked_reason": blocked_reason,
        "candidate": candidate,
        "spec_candidate": contract.get("candidate"),
        "binding_status": binding.get("binding_status"),
        "has_input_contract": bool(binding.get("input_contract")),
        "has_output_contract": bool(binding.get("output_contract")),
        "patch_scope": patch_scope[:8],
        "writable_scope": writable_scope[:8],
        "expected_files": expected_files[:8],
        "verification_commands": plan.get("verification_commands", []),
        "forbidden_sources": sorted(set(forbidden)),
        "llm_invoked": False,
        "source_code_changes": _git_dirty(project_dir),
    }


def write_report(root: Path, report: dict[str, Any], label: str) -> dict[str, str]:
    report_dir = root / "artifacts" / "field_trials"
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    json_path = report_dir / f"{label}_{stamp}.json"
    md_path = report_dir / f"{label}_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    return {"report_path": json_path.as_posix(), "markdown_path": md_path.as_posix()}


def _summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(cases)
    ok = sum(1 for case in cases if case["status"] == "ok")
    blocked = sum(1 for case in cases if case["status"] == "blocked_ok")
    return {
        "ok": ok,
        "blocked_no_safe_candidate": blocked,
        "accepted": ok + blocked,
        "needs_review": count - ok - blocked,
        "avg_quality_score": round(sum(float(case["quality_score"]) for case in cases) / count, 3) if count else 0.0,
        "candidate_matches_spec": sum(1 for case in cases if case["candidate"] == case["spec_candidate"] and case["candidate"]),
        "bound_to_extraction_contract": sum(1 for case in cases if case["binding_status"] == "bound_to_extraction_contract"),
        "writable_scope_targets_candidate": sum(1 for case in cases if case["writable_scope"] == [case["candidate"]] and case["candidate"]),
        "forbidden_sources": sum(len(case["forbidden_sources"]) for case in cases),
        "source_code_changes": sum(1 for case in cases if case["source_code_changes"]),
        "llm_invoked": sum(1 for case in cases if case["llm_invoked"]),
}


def _blocked_reason(project_report: dict[str, Any]) -> str:
    answers = dict(project_report.get("answers", {}))
    readiness = dict(answers.get("6_runtime_extraction_readiness", {}))
    plan = dict(readiness.get("minimal_extraction_plan", {}))
    blocked = [str(item) for item in plan.get("blocked_by", [])]
    return "no_safe_python_candidate" if "no_safe_python_candidate" in blocked else ""


def _quality_score(
    spec: dict[str, Any],
    plan: dict[str, Any],
    candidate: str,
    binding: dict[str, Any],
    forbidden: list[str],
    writable_scope: list[str],
) -> float:
    score = 0.0
    if plan.get("artifact_type") == "ImplementationPlan" and plan.get("role") == producer_for_artifact_type("ImplementationPlan"):
        score += 0.15
    if candidate and candidate == dict(spec.get("extraction_contract", {})).get("candidate"):
        score += 0.2
    if binding.get("binding_status") == "bound_to_extraction_contract":
        score += 0.15
    if binding.get("input_contract") and binding.get("output_contract"):
        score += 0.15
    if plan.get("patch_scope") and plan.get("expected_files"):
        score += 0.1
    if writable_scope == [candidate]:
        score += 0.1
    if plan.get("rollback_plan", {}).get("registry_policy"):
        score += 0.05
    if plan.get("verification_commands"):
        score += 0.05
    if not forbidden and not plan.get("forbidden_actions_observed"):
        score += 0.05
    return round(score, 3)


def _is_forbidden_source(value: str) -> bool:
    normalized = "/" + value.replace("\\", "/").lower()
    return any(token in normalized for token in FORBIDDEN_SOURCE_TOKENS)


def _git_dirty(project_dir: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_dir), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return True
    return bool(result.stdout.strip())


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {report['milestone']}",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Projects: `{report['project_count']}`",
        f"Average quality: `{report['summary']['avg_quality_score']}`",
        f"Needs review: `{report['summary']['needs_review']}`",
        "",
        "## Cases",
    ]
    for case in report["cases"]:
        lines.extend(
            [
                f"### {case['project']}",
                f"- status: `{case['status']}`",
                f"- quality: `{case['quality_score']}`",
                f"- candidate: `{case['candidate'] or 'none'}`",
                f"- binding: `{case['binding_status']}`",
                f"- forbidden sources: `{', '.join(case['forbidden_sources']) or 'none'}`",
                "",
            ]
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
