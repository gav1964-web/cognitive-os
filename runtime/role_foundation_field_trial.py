"""Minimum-based field trial for Project Analyzer -> Architect -> SpecWriter."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .foundation_semantic_quality import evaluate_foundation_semantic_quality
from .foundation_semantic_quality_policy import load_foundation_semantic_quality_policy
from .foundation_executable_evidence import collect_foundation_executable_evidence
from ._parts.role_foundation_field_trial_scope import _child_python_projects, _has_project_manifest, _is_python_project, _primary_language_scope
from .role_foundation_pipeline import run_role_foundation_pipeline
from .role_foundation_feedback_scores import (
    apply_role_score_caps as _apply_role_score_caps,
    role_score_evaluation,
    role_scores as _role_scores,
)
from .role_foundation_trial_status import (
    case_status as _case_status,
)
from .python_module_transaction import python_module_transaction


DEFAULT_GOAL = "Produce ADR and TechnicalSpec for first safe transformation"


def run_role_foundation_field_trial(
    *,
    root: Path,
    project_roots: list[Path],
    limit: int = 0,
    write: bool = False,
    target_score: float = 9.2,
    executable_acceptance: bool = False,
) -> dict[str, Any]:
    projects = discover_python_projects(project_roots)
    if limit > 0:
        projects = projects[:limit]
    cases = [
        _run_isolated_case(
            root=root, project_dir=project, write=write,
            executable_acceptance=executable_acceptance,
        )
        for project in projects
    ]
    report = _report(cases, target_score=target_score)
    if write:
        report["report_path"] = _write_report(root, report).as_posix()
    return report


def _run_isolated_case(
    *, root: Path, project_dir: Path, write: bool, executable_acceptance: bool
) -> dict[str, Any]:
    with python_module_transaction():
        return _run_case(
            root=root,
            project_dir=project_dir,
            write=write,
            executable_acceptance=executable_acceptance,
        )


def discover_python_projects(roots: list[Path]) -> list[Path]:
    projects: list[Path] = []
    for root in roots:
        base = root.resolve()
        if (base / "projects").is_dir():
            projects.extend(_child_python_projects(base / "projects"))
            continue
        if (base / ".git").exists():
            projects.append(base)
            continue
        if _has_project_manifest(base):
            projects.append(base)
            continue
        git_children = [path for path in base.iterdir() if path.is_dir() and (path / ".git").exists()]
        if git_children:
            projects.extend(git_children)
            projects.extend(
                path for path in _child_python_projects(base)
                if path not in git_children
            )
            continue
        child_projects = _child_python_projects(base)
        if child_projects:
            projects.extend(child_projects)
            continue
        if _is_python_project(base):
            projects.append(base)
            continue
    return sorted(dict.fromkeys(projects), key=lambda path: path.as_posix().lower())


def _run_case(
    *, root: Path, project_dir: Path, write: bool, executable_acceptance: bool = False
) -> dict[str, Any]:
    primary_scope = _primary_language_scope(project_dir)
    if primary_scope["status"] == "out_of_scope":
        return {
            "project": project_dir.name,
            "project_dir": project_dir.as_posix(),
            "status": "out_of_scope",
            "pipeline_status": "not_run",
            "blocker": primary_scope["reason_code"],
            "role_scores": {"project_analyzer": None, "architect": None, "spec_writer": None},
            "project_min_score": 0.0,
            "selected_extraction_candidate": None,
            "selected_candidate_quality": {},
            "architect_first_slice": None,
            "warnings": [primary_scope["reason_code"]],
            "safety": {"source_code_changes": False, "llm_invoked": False},
            "artifacts": {},
            "human_documents": {},
            "scope_classification": primary_scope,
        }
    result = run_role_foundation_pipeline(
        root=root,
        project_dir=project_dir,
        goal=f"{DEFAULT_GOAL} in {project_dir.name}",
        write=write,
        include_artifact_contents=True,
    )
    loaded_result = _result_with_loaded_artifacts(result)
    downstream_evidence = {}
    if executable_acceptance and result.get("status") == "ok":
        downstream_evidence = collect_foundation_executable_evidence(
            root=root,
            project_dir=project_dir,
            technical_spec=dict(loaded_result["artifacts"].get("technical_spec") or {}),
            process_isolated=True,
        )
        result["downstream_evidence"] = downstream_evidence
    semantic_quality = dict(dict(result.get("score") or {}).get("foundation_semantic_quality") or {})
    if not semantic_quality:
        semantic_quality = evaluate_foundation_semantic_quality(loaded_result)
    result["foundation_semantic_quality"] = semantic_quality
    scored_result = {**result, "artifacts": loaded_result["artifacts"]}
    score_evaluation = role_score_evaluation(scored_result)
    role_scores = dict(score_evaluation["role_scores"])
    available_scores = [score for score in role_scores.values() if score is not None]
    return {
        "project": project_dir.name,
        "project_dir": project_dir.as_posix(),
        "status": _case_status(scored_result),
        "pipeline_status": result.get("status"),
        "blocker": result.get("blocker"),
        "role_scores": role_scores,
        "local_role_scores": score_evaluation["local_role_scores"],
        "score_adjustments": score_evaluation["adjustments"],
        "acceptance_signal": score_evaluation["acceptance_signal"],
        "downstream_evidence": downstream_evidence,
        "semantic_quality": semantic_quality,
        "project_min_score": round(min(available_scores), 2) if available_scores else 0.0,
        "selected_extraction_candidate": result.get("selected_extraction_candidate"),
        "selected_candidate_quality": result.get("selected_candidate_quality", {}),
        "architect_first_slice": dict(result.get("architect_red_team") or {}).get("checked_first_slice"),
        "warnings": _warnings(result),
        "safety": result.get("safety", {}),
        "artifacts": result.get("artifacts", {}),
        "human_documents": result.get("human_documents", {}),
    }


def _result_with_loaded_artifacts(result: dict[str, Any]) -> dict[str, Any]:
    in_memory = dict(result.get("artifact_contents") or {})
    loaded = {}
    for key, value in dict(result.get("artifacts") or {}).items():
        if key in in_memory:
            loaded[key] = in_memory[key]
            continue
        row = dict(value or {})
        path = row.get("path")
        if path:
            try:
                loaded[key] = json.loads(Path(str(path)).read_text(encoding="utf-8"))
                continue
            except (OSError, json.JSONDecodeError):
                pass
        loaded[key] = value
    return {**result, "artifacts": loaded}


def _report(cases: list[dict[str, Any]], *, target_score: float) -> dict[str, Any]:
    published_caps = dict(load_foundation_semantic_quality_policy().get("role_score_caps") or {})
    scored_cases = [case for case in cases if case.get("status") != "out_of_scope"]
    role_mins = {
        role: _min_available([dict(case.get("role_scores") or {}).get(role) for case in scored_cases])
        for role in ("project_analyzer", "architect", "spec_writer")
    }
    local_role_mins = {
        role: _min_available([
            dict(case.get("local_role_scores") or case.get("role_scores") or {}).get(role)
            for case in scored_cases
        ])
        for role in ("project_analyzer", "architect", "spec_writer")
    }
    project_mins = [float(case.get("project_min_score") or 0.0) for case in scored_cases]
    readiness_scores = [_case_readiness_score(case) for case in scored_cases]
    below_target = [
        {
            "project": case["project"],
            "project_min_score": case["project_min_score"],
            "readiness_score": _case_readiness_score(case),
            "role_scores": case["role_scores"],
            "local_role_scores": case.get("local_role_scores", case["role_scores"]),
            "status": case["status"],
            "warnings": case["warnings"][:8],
        }
        for case in scored_cases
        if _case_readiness_score(case) < target_score or case["status"] != "ok"
    ]
    readiness_min = round(min(readiness_scores), 2) if readiness_scores else 0.0
    calibration = _readiness_calibration(
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
        "summary": {
            "project_min_score": round(min(project_mins), 2) if project_mins else 0.0,
            "readiness_min_score": readiness_min,
            "readiness_avg_score": round(sum(readiness_scores) / len(readiness_scores), 2) if readiness_scores else 0.0,
            "role_min_scores": role_mins,
            "local_role_min_scores": local_role_mins,
            "ok": sum(1 for case in cases if case["status"] == "ok"),
            "blocked_ok": sum(1 for case in cases if case["status"] == "blocked_ok"),
            "needs_review": sum(1 for case in cases if case["status"] == "needs_review"),
            "out_of_scope": sum(1 for case in cases if case["status"] == "out_of_scope"),
            "scored_project_count": len(scored_cases),
            "usable_handoff_rate": _ratio(sum(1 for case in scored_cases if case["status"] == "ok"), len(scored_cases)),
            "controlled_block_rate": _ratio(sum(1 for case in scored_cases if case["status"] == "blocked_ok"), len(scored_cases)),
            "out_of_scope_rate": _ratio(sum(1 for case in cases if case["status"] == "out_of_scope"), len(cases)),
            "below_target_count": len(below_target),
            "executable_callable": sum(
                1 for case in scored_cases if case.get("acceptance_signal") == "executable_callable"
            ),
            "acceptance_meta_only": sum(
                1 for case in scored_cases if case.get("acceptance_signal") == "meta_only"
            ),
            "acceptance_failed": sum(
                1 for case in scored_cases
                if dict(case.get("downstream_evidence") or {}).get("status") == "failed"
            ),
            "acceptance_not_measured": sum(
                1 for case in scored_cases
                if case.get("acceptance_signal") == "not_measured"
                and dict(case.get("downstream_evidence") or {}).get("status") != "failed"
            ),
            "llm_invoked": sum(1 for case in cases if dict(case.get("safety") or {}).get("llm_invoked") is True),
            "source_code_changes": sum(1 for case in cases if dict(case.get("safety") or {}).get("source_code_changes") is True),
        },
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


def _readiness_calibration(
    *,
    scored_cases: list[dict[str, Any]],
    role_mins: dict[str, float],
    readiness_min: float,
    target_score: float,
) -> dict[str, Any]:
    raw_floor = round(min([readiness_min, *role_mins.values()] or [0.0]), 2)
    scored_count = len(scored_cases)
    evidence_cap = _evidence_cap(scored_count)
    issue_penalty = _calibration_issue_penalty(scored_cases)
    calibrated = round(max(0.0, min(raw_floor, evidence_cap) - issue_penalty), 2)
    return {
        "artifact_type": "FieldTrialReadinessCalibration",
        "raw_readiness_floor": raw_floor,
        "evidence_cap": evidence_cap,
        "issue_penalty": issue_penalty,
        "calibrated_readiness_min_score": calibrated,
        "target_met": calibrated >= target_score,
        "evidence_tier": _evidence_tier(scored_count),
        "rationale": "A single clean corpus is diagnostic evidence, not proof of stable 9.7+ readiness.",
    }


def _evidence_cap(scored_count: int) -> float:
    if scored_count >= 320:
        return 9.7
    if scored_count >= 160:
        return 9.5
    if scored_count >= 80:
        return 9.35
    if scored_count >= 40:
        return 9.2
    return 9.0


def _evidence_tier(scored_count: int) -> str:
    if scored_count >= 320:
        return "promotion_candidate"
    if scored_count >= 160:
        return "broad_regression"
    if scored_count >= 80:
        return "multi_corpus_probe"
    if scored_count >= 40:
        return "single_corpus_probe"
    return "thin_probe"


def _calibration_issue_penalty(scored_cases: list[dict[str, Any]]) -> float:
    if not scored_cases:
        return 0.0
    non_ok = sum(1 for case in scored_cases if case.get("status") != "ok")
    weak = sum(1 for case in scored_cases if float(case.get("project_min_score") or 0.0) < 9.7)
    return round(min(1.2, non_ok * 0.25 + weak * 0.1), 2)


def _case_readiness_score(case: dict[str, Any]) -> float:
    """Score usable role readiness, not just safety.

    A controlled block is a correct safety behavior, but it is not equivalent to
    producing an Architect/SpecWriter handoff that an Implementer can use.
    """

    if case.get("status") == "ok":
        return round(float(case.get("project_min_score") or 0.0), 2)
    if case.get("status") == "blocked_ok":
        return 7.0
    return round(min(5.0, float(case.get("project_min_score") or 0.0)), 2)


def _warnings(result: dict[str, Any]) -> list[str]:
    score = dict(result.get("score") or {})
    warnings = [str(item) for item in score.get("warnings", [])]
    for key in ("architect_red_team", "spec_writer_red_team"):
        payload = dict(result.get(key) or {})
        warnings.extend(str(row.get("code") or row) for row in payload.get("blocking_findings", []) if row)
        warnings.extend(str(row.get("code") or row) for row in payload.get("warnings", []) if row)
    return sorted(dict.fromkeys(warnings))


def _min_available(values: list[float | None]) -> float:
    available = [float(value) for value in values if value is not None]
    return round(min(available), 2) if available else 0.0

def _ratio(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 3) if denominator else 0.0

def _write_report(root: Path, report: dict[str, Any]) -> Path:
    out_dir = root / "artifacts" / "field_trials"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"role_foundation_min_field_trial_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
