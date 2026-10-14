"""Minimum field trial for bounded Researcher planning contracts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .research_loop import build_knowledge_gap_packet, build_research_plan
from .role_project_type_evaluation import _case_with_loaded_artifacts, classify_project_case


def run_researcher_min_field_trial(
    *, root: Path, foundation_reports: Iterable[Path], write: bool = False
) -> dict[str, Any]:
    projects: dict[str, dict[str, Any]] = {}
    for report_path in foundation_reports:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        for case in payload.get("cases", []):
            if isinstance(case, dict) and case.get("status") not in {"failed", "out_of_scope"}:
                projects[str(case.get("project") or "unknown")] = case
    cases = [_run_case(root, project, case) for project, case in sorted(projects.items())]
    minimum = min((case["role_scores"]["researcher"] for case in cases), default=0.0)
    report = {
        "artifact_type": "ResearcherMinimumFieldTrialReport",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok" if cases and minimum >= 9.7 else "needs_work",
        "evidence_mode": "planning_only",
        "project_count": len(cases),
        "summary": {"role_min_scores": {"researcher": minimum}, "source_code_changes": 0},
        "cases": cases,
    }
    if write:
        out_dir = root / "artifacts" / "field_trials"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = out_dir / f"researcher_min_field_trial_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    return report


def _run_case(root: Path, project: str, foundation_case: dict[str, Any]) -> dict[str, Any]:
    classification = classify_project_case(_case_with_loaded_artifacts(foundation_case, root))
    stratum = str(classification["project_stratum"])
    gap = build_knowledge_gap_packet(
        question=f"Which external facts could change the first-slice decision for {project}?",
        needed_for=f"{stratum} first-slice validation",
        role="researcher",
        reason="separate source-backed facts from local architectural inference",
        acceptable_sources=["official_docs_fetch", "github_repository_search", "user_clarification"],
        decision_if_unresolved="Continue with local evidence and mark external claims unresolved.",
    )
    plan = build_research_plan(gap, query_hint=f"{project} official architecture and API behavior")
    steps = list(plan.get("steps") or [])
    checks = {
        "gap_has_stable_id": str(gap.get("gap_id") or "").startswith("kgp_"),
        "gap_is_decision_bound": bool(gap.get("question") and gap.get("needed_for") and gap.get("reason")),
        "researcher_is_owner": gap.get("role") == "researcher",
        "confidence_is_bounded": 0.0 < float(gap.get("confidence_required") or 0.0) <= 1.0,
        "unresolved_decision_exists": bool(gap.get("decision_if_unresolved")),
        "plan_matches_gap": plan.get("gap_id") == gap.get("gap_id"),
        "plan_has_allowlisted_steps": bool(steps) and all(step.get("source_type") in gap["acceptable_sources"] for step in steps),
        "external_steps_are_opt_in": all(not step.get("execute_by_default") for step in steps if step.get("source_type") != "user_clarification"),
        "source_digest_is_required": dict(plan.get("policy") or {}).get("source_digest_required") is True,
        "free_browsing_is_forbidden": dict(plan.get("policy") or {}).get("llm_may_not_browse_freely") is True,
    }
    score = round(10.0 * sum(checks.values()) / len(checks), 2)
    return {
        "project": project,
        "status": "ok" if score >= 9.7 else "needs_work",
        "project_classification": classification,
        "role_scores": {"researcher": score},
        "evidence_mode": "planning_only",
        "checks": checks,
        "knowledge_gap": gap,
        "research_plan": plan,
        "source_code_changes": False,
    }
