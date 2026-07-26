"""Minimum-based field trial for Project Analyzer -> Architect -> SpecWriter."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .role_foundation_pipeline import run_role_foundation_pipeline


DEFAULT_GOAL = "Produce ADR and TechnicalSpec for first safe transformation"


def run_role_foundation_field_trial(
    *,
    root: Path,
    project_roots: list[Path],
    limit: int = 0,
    write: bool = False,
    target_score: float = 9.2,
) -> dict[str, Any]:
    projects = discover_python_projects(project_roots)
    if limit > 0:
        projects = projects[:limit]
    cases = [_run_case(root=root, project_dir=project, write=write) for project in projects]
    report = _report(cases, target_score=target_score)
    if write:
        report["report_path"] = _write_report(root, report).as_posix()
    return report


def discover_python_projects(roots: list[Path]) -> list[Path]:
    projects: list[Path] = []
    for root in roots:
        base = root.resolve()
        if (base / "projects").is_dir():
            projects.extend(_child_python_projects(base / "projects"))
            continue
        if _has_project_manifest(base):
            projects.append(base)
            continue
        child_projects = _child_python_projects(base)
        if child_projects:
            projects.extend(child_projects)
            continue
        if _is_python_project(base):
            projects.append(base)
            continue
    return sorted(dict.fromkeys(projects), key=lambda path: path.as_posix().lower())


def _run_case(*, root: Path, project_dir: Path, write: bool) -> dict[str, Any]:
    result = run_role_foundation_pipeline(
        root=root,
        project_dir=project_dir,
        goal=f"{DEFAULT_GOAL} in {project_dir.name}",
        write=write,
    )
    role_scores = _role_scores(result)
    available_scores = [score for score in role_scores.values() if score is not None]
    return {
        "project": project_dir.name,
        "project_dir": project_dir.as_posix(),
        "status": _case_status(result),
        "pipeline_status": result.get("status"),
        "blocker": result.get("blocker"),
        "role_scores": role_scores,
        "project_min_score": round(min(available_scores), 2) if available_scores else 0.0,
        "selected_extraction_candidate": result.get("selected_extraction_candidate"),
        "selected_candidate_quality": result.get("selected_candidate_quality", {}),
        "architect_first_slice": dict(result.get("architect_red_team") or {}).get("checked_first_slice"),
        "warnings": _warnings(result),
        "safety": result.get("safety", {}),
        "artifacts": result.get("artifacts", {}),
        "human_documents": result.get("human_documents", {}),
    }


def _role_scores(result: dict[str, Any]) -> dict[str, float | None]:
    score = dict(result.get("score") or {})
    quality = dict(score.get("quality") or {})
    quality_results = dict(quality.get("results") or {})
    project_score = _quality_score(quality_results, "project_map_report")
    if project_score is None and result.get("blocker") == "scope_selection_required":
        project_score = _ten_point(score.get("artifact_score"))

    architect_quality = _quality_score(quality_results, "adr")
    architect_red = _ten_point(dict(result.get("architect_red_team") or {}).get("score"))
    architect_scores = [value for value in (architect_quality, architect_red) if value is not None]

    spec_quality = _quality_score(quality_results, "technical_spec")
    spec_red = _ten_point(dict(result.get("spec_writer_red_team") or {}).get("score"))
    semantic = _semantic_score(result.get("selected_candidate_quality"))
    spec_scores = [value for value in (spec_quality, spec_red, semantic) if value is not None]
    if _spec_writer_blocked_no_safe_candidate(result):
        spec_scores = [10.0]

    return {
        "project_analyzer": project_score,
        "architect": round(min(architect_scores), 2) if architect_scores else None,
        "spec_writer": round(min(spec_scores), 2) if spec_scores else None,
    }


def _report(cases: list[dict[str, Any]], *, target_score: float) -> dict[str, Any]:
    role_mins = {
        role: _min_available([dict(case.get("role_scores") or {}).get(role) for case in cases])
        for role in ("project_analyzer", "architect", "spec_writer")
    }
    project_mins = [float(case.get("project_min_score") or 0.0) for case in cases]
    below_target = [
        {
            "project": case["project"],
            "project_min_score": case["project_min_score"],
            "role_scores": case["role_scores"],
            "warnings": case["warnings"][:8],
        }
        for case in cases
        if float(case.get("project_min_score") or 0.0) < target_score or case["status"] not in {"ok", "blocked_ok"}
    ]
    return {
        "artifact_type": "RoleFoundationFieldTrialReport",
        "status": "ok" if not below_target and all(score >= target_score for score in role_mins.values()) else "needs_work",
        "milestone": "Project Analyzer -> Architect -> SpecWriter minimum field trial",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_score": target_score,
        "project_count": len(cases),
        "summary": {
            "project_min_score": round(min(project_mins), 2) if project_mins else 0.0,
            "role_min_scores": role_mins,
            "ok": sum(1 for case in cases if case["status"] == "ok"),
            "blocked_ok": sum(1 for case in cases if case["status"] == "blocked_ok"),
            "needs_review": sum(1 for case in cases if case["status"] == "needs_review"),
            "below_target_count": len(below_target),
            "llm_invoked": sum(1 for case in cases if dict(case.get("safety") or {}).get("llm_invoked") is True),
            "source_code_changes": sum(1 for case in cases if dict(case.get("safety") or {}).get("source_code_changes") is True),
        },
        "below_target": below_target,
        "invariants": {
            "score_policy": "minimum per project and per role, not average",
            "blocked_scope_selection_is_valid_project_analyzer_output": True,
            "downstream_roles_not_scored_when_scope_selection_blocks_pipeline": True,
            "source_projects_modified": any(dict(case.get("safety") or {}).get("source_code_changes") for case in cases),
        },
        "cases": cases,
    }


def _case_status(result: dict[str, Any]) -> str:
    if result.get("status") == "ok":
        return "ok"
    if _spec_writer_blocked_no_safe_candidate(result):
        return "blocked_ok"
    if result.get("status") == "blocked" and result.get("blocker") == "scope_selection_required":
        return "blocked_ok"
    return "needs_review"


def _spec_writer_blocked_no_safe_candidate(result: dict[str, Any]) -> bool:
    return dict(result.get("spec_writer_red_team") or {}).get("handoff_verdict") == "blocked_no_safe_candidate"


def _warnings(result: dict[str, Any]) -> list[str]:
    score = dict(result.get("score") or {})
    warnings = [str(item) for item in score.get("warnings", [])]
    for key in ("architect_red_team", "spec_writer_red_team"):
        payload = dict(result.get(key) or {})
        warnings.extend(str(row.get("code") or row) for row in payload.get("blocking_findings", []) if row)
        warnings.extend(str(row.get("code") or row) for row in payload.get("warnings", []) if row)
    return sorted(dict.fromkeys(warnings))


def _quality_score(quality_results: dict[str, Any], key: str) -> float | None:
    row = quality_results.get(key)
    if not isinstance(row, dict):
        return None
    return _ten_point(row.get("score"))


def _semantic_score(value: object) -> float | None:
    if not isinstance(value, dict):
        return None
    score = value.get("score")
    if score is None:
        return None
    return round(max(0.0, min(10.0, float(score) / 10.0)), 2)


def _ten_point(value: object) -> float | None:
    if value is None:
        return None
    return round(max(0.0, min(10.0, float(value) * 10.0)), 2)


def _min_available(values: list[float | None]) -> float:
    available = [float(value) for value in values if value is not None]
    return round(min(available), 2) if available else 0.0


def _is_python_project(path: Path) -> bool:
    if not path.is_dir():
        return False
    if _has_project_manifest(path):
        return True
    if any(path.glob("*.py")):
        return True
    return any(child.name in {"src", "app", "tests"} and any(child.rglob("*.py")) for child in path.iterdir() if child.is_dir())


def _child_python_projects(path: Path) -> list[Path]:
    return [child.resolve() for child in sorted(path.iterdir()) if child.is_dir() and _is_python_project(child)]


def _has_project_manifest(path: Path) -> bool:
    return any((path / marker).exists() for marker in ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"))


def _write_report(root: Path, report: dict[str, Any]) -> Path:
    out_dir = root / "artifacts" / "field_trials"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"role_foundation_min_field_trial_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
