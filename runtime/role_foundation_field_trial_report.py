"""Report and calibration helpers for role foundation field trials."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .foundation_semantic_quality_policy import load_foundation_semantic_quality_policy


def build_field_trial_report(cases: list[dict[str, Any]], *, target_score: float) -> dict[str, Any]:
    published_caps = dict(load_foundation_semantic_quality_policy().get("role_score_caps") or {})
    scored_cases = [case for case in cases if case.get("status") != "out_of_scope"]
    role_mins = {
        role: min_available([dict(case.get("role_scores") or {}).get(role) for case in scored_cases])
        for role in ("project_analyzer", "architect", "spec_writer")
    }
    local_role_mins = {
        role: min_available([
            dict(case.get("local_role_scores") or case.get("role_scores") or {}).get(role)
            for case in scored_cases
        ])
        for role in ("project_analyzer", "architect", "spec_writer")
    }
    project_mins = [float(case.get("project_min_score") or 0.0) for case in scored_cases]
    readiness_scores = [case_readiness_score(case) for case in scored_cases]
    below_target = [
        {
            "project": case["project"],
            "project_min_score": case["project_min_score"],
            "readiness_score": case_readiness_score(case),
            "role_scores": case["role_scores"],
            "local_role_scores": case.get("local_role_scores", case["role_scores"]),
            "status": case["status"],
            "warnings": case["warnings"][:8],
        }
        for case in scored_cases
        if case_readiness_score(case) < target_score or case["status"] != "ok"
    ]
    readiness_min = round(min(readiness_scores), 2) if readiness_scores else 0.0
    calibration = readiness_calibration(
        scored_cases=scored_cases,
        role_mins=role_mins,
        readiness_min=readiness_min,
        target_score=target_score,
    )
    calibrated_min = float(calibration["calibrated_readiness_min_score"])
    corpus_passed = not below_target and readiness_min >= target_score and all(score >= target_score for score in role_mins.values())
    return {
        "artifact_type": "RoleFoundationFieldTrialReport",
        "status": "ok" if corpus_passed else "needs_work",
        "promotion_status": "ready_for_9_7" if corpus_passed and calibrated_min >= target_score else "needs_more_evidence",
        "milestone": "Project Analyzer -> Architect -> SpecWriter minimum field trial",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_score": target_score,
        "project_count": len(cases),
        "summary": field_trial_summary(cases, scored_cases, project_mins, readiness_scores, role_mins, local_role_mins, below_target),
        "calibration": calibration,
        "below_target": below_target,
        "invariants": {
            "score_policy": "raw minimums diagnose a corpus; calibrated readiness gates promotion claims",
            "feedback_policy": "published role scores include downstream evidence caps; local scores remain diagnostic",
            "published_role_score_caps": published_caps,
            "controlled_block_readiness_score": 7.0,
            "out_of_scope_projects_are_reported_but_not_scored_for_python_roles": True,
            "blocked_scope_selection_is_valid_project_analyzer_output": True,
            "downstream_roles_not_scored_when_scope_selection_blocks_pipeline": True,
            "source_projects_modified": any(dict(case.get("safety") or {}).get("source_code_changes") for case in cases),
        },
        "cases": cases,
    }


def field_trial_summary(
    cases: list[dict[str, Any]],
    scored_cases: list[dict[str, Any]],
    project_mins: list[float],
    readiness_scores: list[float],
    role_mins: dict[str, float],
    local_role_mins: dict[str, float],
    below_target: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "project_min_score": round(min(project_mins), 2) if project_mins else 0.0,
        "readiness_min_score": round(min(readiness_scores), 2) if readiness_scores else 0.0,
        "readiness_avg_score": round(sum(readiness_scores) / len(readiness_scores), 2) if readiness_scores else 0.0,
        "role_min_scores": role_mins,
        "local_role_min_scores": local_role_mins,
        "ok": sum(1 for case in cases if case["status"] == "ok"),
        "blocked_ok": sum(1 for case in cases if case["status"] == "blocked_ok"),
        "needs_review": sum(1 for case in cases if case["status"] == "needs_review"),
        "out_of_scope": sum(1 for case in cases if case["status"] == "out_of_scope"),
        "scored_project_count": len(scored_cases),
        "usable_handoff_rate": ratio(sum(1 for case in scored_cases if case["status"] == "ok"), len(scored_cases)),
        "controlled_block_rate": ratio(sum(1 for case in scored_cases if case["status"] == "blocked_ok"), len(scored_cases)),
        "out_of_scope_rate": ratio(sum(1 for case in cases if case["status"] == "out_of_scope"), len(cases)),
        "below_target_count": len(below_target),
        "executable_callable": sum(1 for case in scored_cases if case.get("acceptance_signal") == "executable_callable"),
        "acceptance_meta_only": sum(1 for case in scored_cases if case.get("acceptance_signal") == "meta_only"),
        "acceptance_failed": sum(1 for case in scored_cases if dict(case.get("downstream_evidence") or {}).get("status") == "failed"),
        "acceptance_not_measured": sum(
            1 for case in scored_cases
            if case.get("acceptance_signal") == "not_measured"
            and dict(case.get("downstream_evidence") or {}).get("status") != "failed"
        ),
        "llm_invoked": sum(1 for case in cases if dict(case.get("safety") or {}).get("llm_invoked") is True),
        "source_code_changes": sum(1 for case in cases if dict(case.get("safety") or {}).get("source_code_changes") is True),
    }


def readiness_calibration(
    *,
    scored_cases: list[dict[str, Any]],
    role_mins: dict[str, float],
    readiness_min: float,
    target_score: float,
) -> dict[str, Any]:
    raw_floor = round(min([readiness_min, *role_mins.values()] or [0.0]), 2)
    scored_count = len(scored_cases)
    evidence_cap = evidence_cap_for_count(scored_count)
    issue_penalty = calibration_issue_penalty(scored_cases)
    calibrated = round(max(0.0, min(raw_floor, evidence_cap) - issue_penalty), 2)
    return {
        "artifact_type": "FieldTrialReadinessCalibration",
        "raw_readiness_floor": raw_floor,
        "evidence_cap": evidence_cap,
        "issue_penalty": issue_penalty,
        "calibrated_readiness_min_score": calibrated,
        "target_met": calibrated >= target_score,
        "evidence_tier": evidence_tier(scored_count),
        "rationale": "A single clean corpus is diagnostic evidence, not proof of stable 9.7+ readiness.",
    }


def evidence_cap_for_count(scored_count: int) -> float:
    if scored_count >= 320:
        return 9.7
    if scored_count >= 160:
        return 9.5
    if scored_count >= 80:
        return 9.35
    if scored_count >= 40:
        return 9.2
    return 9.0


def evidence_tier(scored_count: int) -> str:
    if scored_count >= 320:
        return "promotion_candidate"
    if scored_count >= 160:
        return "broad_regression"
    if scored_count >= 80:
        return "multi_corpus_probe"
    if scored_count >= 40:
        return "single_corpus_probe"
    return "thin_probe"


def calibration_issue_penalty(scored_cases: list[dict[str, Any]]) -> float:
    if not scored_cases:
        return 0.0
    non_ok = sum(1 for case in scored_cases if case.get("status") != "ok")
    weak = sum(1 for case in scored_cases if float(case.get("project_min_score") or 0.0) < 9.7)
    return round(min(1.2, non_ok * 0.25 + weak * 0.1), 2)


def case_readiness_score(case: dict[str, Any]) -> float:
    if case.get("status") == "ok":
        return round(float(case.get("project_min_score") or 0.0), 2)
    if case.get("status") == "blocked_ok":
        return 7.0
    return round(min(5.0, float(case.get("project_min_score") or 0.0)), 2)


def min_available(values: list[float | None]) -> float:
    available = [float(value) for value in values if value is not None]
    return round(min(available), 2) if available else 0.0


def ratio(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 3) if denominator else 0.0


def write_field_trial_report(root: Path, report: dict[str, Any]) -> Path:
    out_dir = root / "artifacts" / "field_trials"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"role_foundation_min_field_trial_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
