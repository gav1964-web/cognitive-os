"""Minimum-based field trial for Project Analyzer -> Architect -> SpecWriter."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .foundation_semantic_quality import evaluate_foundation_semantic_quality
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
    )
    semantic_quality = evaluate_foundation_semantic_quality(_result_with_loaded_artifacts(result))
    result["foundation_semantic_quality"] = semantic_quality
    role_scores = _role_scores(result)
    available_scores = [score for score in role_scores.values() if score is not None]
    return {
        "project": project_dir.name,
        "project_dir": project_dir.as_posix(),
        "status": _case_status(result),
        "pipeline_status": result.get("status"),
        "blocker": result.get("blocker"),
        "role_scores": role_scores,
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
    foundation_semantic = dict(result.get("foundation_semantic_quality") or {})
    semantic_role_scores = dict(foundation_semantic.get("role_scores") or {})
    project_semantic = _number_or_none(semantic_role_scores.get("project_analyzer"))
    architect_semantic = _number_or_none(semantic_role_scores.get("architect"))
    spec_semantic = _number_or_none(semantic_role_scores.get("spec_writer"))
    spec_scores = [value for value in (spec_quality, spec_red, semantic) if value is not None]
    if _spec_writer_blocked_no_safe_candidate(result):
        spec_scores = [10.0]

    architect_all_scores = [*architect_scores, architect_semantic]
    spec_all_scores = [*spec_scores, spec_semantic]
    return {
        "project_analyzer": _min_optional(project_score, project_semantic),
        "architect": _min_optional(*architect_all_scores),
        "spec_writer": _min_optional(*spec_all_scores),
    }


def _result_with_loaded_artifacts(result: dict[str, Any]) -> dict[str, Any]:
    loaded = {}
    for key, value in dict(result.get("artifacts") or {}).items():
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
    scored_cases = [case for case in cases if case.get("status") != "out_of_scope"]
    role_mins = {
        role: _min_available([dict(case.get("role_scores") or {}).get(role) for case in scored_cases])
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
            "status": case["status"],
            "warnings": case["warnings"][:8],
        }
        for case in scored_cases
        if _case_readiness_score(case) < target_score or case["status"] != "ok"
    ]
    readiness_min = round(min(readiness_scores), 2) if readiness_scores else 0.0
    return {
        "artifact_type": "RoleFoundationFieldTrialReport",
        "status": "ok" if not below_target and readiness_min >= target_score and all(score >= target_score for score in role_mins.values()) else "needs_work",
        "milestone": "Project Analyzer -> Architect -> SpecWriter minimum field trial",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_score": target_score,
        "project_count": len(cases),
        "summary": {
            "project_min_score": round(min(project_mins), 2) if project_mins else 0.0,
            "readiness_min_score": readiness_min,
            "readiness_avg_score": round(sum(readiness_scores) / len(readiness_scores), 2) if readiness_scores else 0.0,
            "role_min_scores": role_mins,
            "ok": sum(1 for case in cases if case["status"] == "ok"),
            "blocked_ok": sum(1 for case in cases if case["status"] == "blocked_ok"),
            "needs_review": sum(1 for case in cases if case["status"] == "needs_review"),
            "out_of_scope": sum(1 for case in cases if case["status"] == "out_of_scope"),
            "scored_project_count": len(scored_cases),
            "usable_handoff_rate": _ratio(sum(1 for case in scored_cases if case["status"] == "ok"), len(scored_cases)),
            "controlled_block_rate": _ratio(sum(1 for case in scored_cases if case["status"] == "blocked_ok"), len(scored_cases)),
            "out_of_scope_rate": _ratio(sum(1 for case in cases if case["status"] == "out_of_scope"), len(cases)),
            "below_target_count": len(below_target),
            "llm_invoked": sum(1 for case in cases if dict(case.get("safety") or {}).get("llm_invoked") is True),
            "source_code_changes": sum(1 for case in cases if dict(case.get("safety") or {}).get("source_code_changes") is True),
        },
        "below_target": below_target,
        "invariants": {
            "score_policy": "minimum per project and per role; controlled blocks are safe outcomes but not full readiness",
            "controlled_block_readiness_score": 7.0,
            "out_of_scope_projects_are_reported_but_not_scored_for_python_roles": True,
            "blocked_scope_selection_is_valid_project_analyzer_output": True,
            "downstream_roles_not_scored_when_scope_selection_blocks_pipeline": True,
            "source_projects_modified": any(dict(case.get("safety") or {}).get("source_code_changes") for case in cases),
        },
        "cases": cases,
    }


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


def _number_or_none(value: object) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _min_optional(*values: float | None) -> float | None:
    available = [float(value) for value in values if value is not None]
    return round(min(available), 2) if available else None


def _ten_point(value: object) -> float | None:
    if value is None:
        return None
    return round(max(0.0, min(10.0, float(value) * 10.0)), 2)


def _min_available(values: list[float | None]) -> float:
    available = [float(value) for value in values if value is not None]
    return round(min(available), 2) if available else 0.0


def _ratio(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 3) if denominator else 0.0


def _primary_language_scope(path: Path) -> dict[str, Any]:
    top_files = {child.name.lower() for child in path.iterdir() if child.is_file()}
    top_dirs = {child.name.lower() for child in path.iterdir() if child.is_dir()}
    py_files = list(path.rglob("*.py"))
    rust_files = list(path.rglob("*.rs"))
    python_source_files = [file for file in py_files if _python_role_source_file(file.relative_to(path))]
    root_package = _root_python_package(path)
    has_root_python_source = bool(root_package or (path / "src").is_dir() or (path / "app").is_dir())
    rust_workspace = "cargo.toml" in top_files and ("crates" in top_dirs or len(rust_files) >= max(20, len(py_files) * 2))
    rust_dominates = len(rust_files) >= max(50, len(py_files) * 5)
    python_is_embedded = not has_root_python_source and (
        len(python_source_files) < max(8, len(py_files) // 2)
        or rust_dominates
    )
    if rust_workspace and python_is_embedded:
        return {
            "status": "out_of_scope",
            "reason_code": "unsupported_primary_language_for_python_foundation",
            "primary_language": "Rust",
            "python_files": len(py_files),
            "python_source_files": len(python_source_files),
            "rust_files": len(rust_files),
            "evidence": {
                "top_level_cargo": "cargo.toml" in top_files,
                "crates_dir": "crates" in top_dirs,
                "root_python_package": root_package,
            },
        }
    return {
        "status": "in_scope",
        "primary_language": "Python",
        "python_files": len(py_files),
        "python_source_files": len(python_source_files),
        "rust_files": len(rust_files),
        "evidence": {"root_python_package": root_package},
    }


def _python_role_source_file(path: Path) -> bool:
    normalized = path.as_posix().lower()
    parts = normalized.split("/")
    if any(part in {"tests", "test", "docs", "examples", "example", "scripts", ".github", "ci", "templates"} for part in parts):
        return False
    if "test" in path.name.lower() or path.name.lower().endswith("_template.py"):
        return False
    return True


def _root_python_package(path: Path) -> str | None:
    for child in sorted(path.iterdir(), key=lambda item: item.name.lower()):
        if not child.is_dir() or child.name.startswith(".") or child.name.lower() in {"tests", "docs", "examples", "scripts", "crates"}:
            continue
        if (child / "__init__.py").exists():
            return child.name
    return None


def _is_python_project(path: Path) -> bool:
    if not path.is_dir():
        return False
    if _has_project_manifest(path):
        return True
    if any(path.glob("*.py")):
        return True
    children = [child for child in path.iterdir() if child.is_dir()]
    if any(child.name in {"src", "app", "tests"} and any(child.rglob("*.py")) for child in children):
        return True
    py_files = list(path.rglob("*.py"))
    if len(py_files) >= 20 and any(_python_source_like(rel.relative_to(path)) for rel in py_files[:200]):
        return True
    return False


def _child_python_projects(path: Path) -> list[Path]:
    return [child.resolve() for child in sorted(path.iterdir()) if child.is_dir() and _is_python_project(child)]


def _has_project_manifest(path: Path) -> bool:
    return any((path / marker).exists() for marker in ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"))


def _python_source_like(path: Path) -> bool:
    normalized = path.as_posix().lower()
    if any(token in normalized for token in ("/.git/", "/docs/", "/assets/", "/ci/", "/scripts/")):
        return False
    return "__init__.py" in normalized or "/src/" in normalized or normalized.count("/") >= 1


def _write_report(root: Path, report: dict[str, Any]) -> Path:
    out_dir = root / "artifacts" / "field_trials"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"role_foundation_min_field_trial_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
