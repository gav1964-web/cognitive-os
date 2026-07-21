"""Run Project Analyzer + ArchitectSkill over cloned GitHub projects."""

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
from runtime.role_skills import run_role_skill


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
    parser.add_argument("--label", default="github_architect_probe")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    projects_dir = Path(args.projects_dir)
    if not projects_dir.is_absolute():
        projects_dir = root / projects_dir
    report = run_probe(root=root, projects_dir=projects_dir.resolve(), label=args.label, limit=args.limit)
    if args.write:
        paths = write_report(root, report, args.label)
        report.update(paths)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def run_probe(*, root: Path, projects_dir: Path, label: str, limit: int = 0) -> dict[str, Any]:
    projects = sorted(path for path in projects_dir.iterdir() if path.is_dir() and (path / ".git").exists())
    if limit > 0:
        projects = projects[:limit]
    cases = [_run_case(root, project_dir) for project_dir in projects]
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
        },
        "cases": cases,
    }


def _run_case(root: Path, project_dir: Path) -> dict[str, Any]:
    outputs = analyze_project(project_dir)
    project_report = outputs["project_map_report"]
    adr = run_role_skill(
        "architect",
        goal=f"GitHub Architect probe for {project_dir.name}",
        project_report=project_report,
        constraints=[
            "External source project is read-only evidence.",
            "Do not treat teacher/reference output as ground truth.",
        ],
    )
    capability_sources = _capability_sources(adr)
    forbidden_sources = [source for source in capability_sources if _is_forbidden_source(source)]
    blocked_reason = _blocked_reason(project_report)
    source_context = dict(adr.get("source_context", {}))
    report_summary = dict(project_report.get("summary", {}))
    entrypoints = [str(item) for item in report_summary.get("entrypoints", [])]
    quality = _quality_score(entrypoints, capability_sources, source_context, forbidden_sources)
    status = "ok" if quality >= 0.75 and not forbidden_sources else "needs_review"
    if blocked_reason == "no_safe_python_candidate" and not capability_sources and not forbidden_sources:
        status = "blocked_ok"
        quality = 1.0
    return {
        "project": project_dir.name,
        "project_dir": project_dir.as_posix(),
        "status": status,
        "quality_score": quality,
        "blocked_reason": blocked_reason,
        "summary": {
            "entrypoints": entrypoints,
            "frameworks": report_summary.get("frameworks", []),
            "languages": report_summary.get("languages", []),
            "risks": project_report.get("risks", []),
        },
        "source_strata_sample": _source_strata_sample(adr),
        "capability_sources": capability_sources,
        "forbidden_capability_sources": forbidden_sources,
        "chosen_option": dict(adr.get("chosen_option", {})).get("id"),
        "risk_count": len(adr.get("risks", [])),
        "source_context_sources": sorted(source_context)[:12],
        "llm_invoked": bool(dict(adr.get("architect_advisory", {})).get("llm_invoked")),
        "source_code_changes": _git_dirty(project_dir),
        "report_excerpt": _report_excerpt(project_report),
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
        "entrypoints_present": sum(1 for case in cases if case["summary"]["entrypoints"]),
        "capability_model_present": sum(1 for case in cases if case["capability_sources"]),
        "forbidden_capability_sources": sum(len(case["forbidden_capability_sources"]) for case in cases),
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
    entrypoints: list[str],
    capability_sources: list[str],
    source_context: dict[str, Any],
    forbidden_sources: list[str],
) -> float:
    score = 0.0
    if entrypoints:
        score += 0.25
    if capability_sources:
        score += 0.25
    if source_context:
        score += 0.25
    if not forbidden_sources:
        score += 0.25
    return round(score, 3)


def _capability_sources(adr: dict[str, Any]) -> list[str]:
    sources = []
    for row in adr.get("capability_model", []):
        if isinstance(row, dict) and row.get("source"):
            sources.append(str(row["source"]))
    return sources


def _source_strata_sample(adr: dict[str, Any]) -> dict[str, list[str]]:
    strata = dict(adr.get("source_strata", {}))
    result = {}
    for name in ("active_core", "context_only", "legacy_noise", "packaged_copy"):
        result[name] = [str(row.get("path")) for row in strata.get(name, [])[:8] if isinstance(row, dict)]
    return result


def _report_excerpt(project_report: dict[str, Any]) -> dict[str, Any]:
    answers = dict(project_report.get("answers", {}))
    scope = dict(answers.get("1_scope", {}))
    execution = dict(answers.get("2_execution", {}))
    return {
        "main_task": scope.get("main_task"),
        "supported_scenarios": scope.get("supported_scenarios", []),
        "primary_execution_path": execution.get("primary_execution_path", []),
    }


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
                f"- entrypoints: `{', '.join(case['summary']['entrypoints']) or 'none'}`",
                f"- first capabilities: `{', '.join(case['capability_sources'][:5]) or 'none'}`",
                f"- forbidden capability sources: `{', '.join(case['forbidden_capability_sources']) or 'none'}`",
                f"- source modified: `{case['source_code_changes']}`",
                "",
            ]
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
