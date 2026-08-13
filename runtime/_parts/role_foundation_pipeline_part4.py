from __future__ import annotations

from pathlib import Path
from typing import Any


def _named_package_over_tests_scope(project_dir: Path, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    aliases = _project_aliases(project_dir)
    has_tests = any(str(row.get("path") or "").split("/", 1)[0].lower() in DISFAVORED_SCOPE_ROOTS for row in candidates)
    if not has_tests:
        return None
    for row in candidates:
        path = str(row.get("path") or "").replace("\\", "/").strip("/")
        first = path.split("/", 1)[0].lower().replace("-", "_")
        compact = first.replace("_", "")
        if first not in aliases and compact not in aliases:
            continue
        if int(row.get("python_files") or 0) < scope_policy_int("named_package_min_python_files", 3):
            continue
        if not (project_dir / path / "__init__.py").exists():
            continue
        return dict(row)
    return None


def _auto_active_root_decision(project_dir: Path, scope_report: dict[str, Any]) -> dict[str, Any]:
    candidates = list(scope_report.get("candidate_roots") or [])
    if not candidates:
        return _active_root_decision(project_dir, None)
    if _current_root_is_python_product(project_dir):
        decision = _active_root_decision(project_dir, project_dir)
        decision["source"] = "auto_current_python_product_root"
        decision["selection_confidence"] = "high"
        return decision
    best = dict(candidates[0])
    second = dict(candidates[1]) if len(candidates) > 1 else {}
    best_score = int(best.get("score") or 0)
    second_score = int(second.get("score") or 0)
    path = str(best.get("path") or "")
    if _flat_script_collection_candidate(best):
        return _active_root_decision(project_dir, None)
    native_package = _native_python_package_scope(project_dir)
    if native_package:
        return _active_root_decision(project_dir, native_package)
    frontend_python_package = _frontend_python_package_scope(project_dir, candidates)
    if frontend_python_package:
        return _selected_scope_decision(
            project_dir,
            frontend_python_package,
            "auto_python_facing_scope_selector",
        )
    if package_scope := _named_package_over_tests_scope(project_dir, candidates):
        return _selected_scope_decision(project_dir, package_scope, "auto_named_package_over_tests_scope_selector")
    application_package = _application_python_package_scope(project_dir, candidates)
    if application_package:
        return _selected_scope_decision(project_dir, application_package, "auto_application_package_scope_selector")
    for scoped, source in (
        (_monorepo_python_modules_scope(project_dir, candidates), "auto_monorepo_python_modules_scope_selector"),
        (_aliased_core_package_scope(project_dir, candidates), "auto_aliased_core_scope_selector"),
        (_library_module_scope(project_dir, candidates), "auto_library_module_scope_selector"),
    ):
        if scoped:
            return _selected_scope_decision(project_dir, scoped, source)
    if project_dir.name.lower().replace("-", "_") == project_dir.parent.name.lower().replace("-", "_"):
        return _active_root_decision(project_dir, None)
    clear_named_package = _clear_named_package_candidate(project_dir, path, best_score, second_score)
    high_score = scope_policy_int("safe_selector_named_package_high_score", 90)
    medium_score = scope_policy_int("safe_selector_named_package_medium_score", 70)
    required_gap = (
        scope_policy_int("safe_selector_named_package_high_gap", 0)
        if clear_named_package and best_score >= high_score
        else scope_policy_int("safe_selector_named_package_medium_gap", 6)
        if clear_named_package and best_score >= medium_score
        else scope_policy_int("safe_selector_default_gap", 12)
    )
    confidence = (
        "high"
        if (
            (best_score >= scope_policy_int("safe_selector_high_score", 75) or clear_named_package)
            and best_score - second_score >= required_gap
            and not _disfavored_scope_root(path)
        )
        else "low"
    )
    if confidence != "high":
        return _active_root_decision(project_dir, None)
    decision = _active_root_decision(project_dir, path)
    decision.update(
        {
            "source": "auto_safe_scope_selector",
            "selection_confidence": confidence,
            "selected_candidate_score": best_score,
            "score_gap_to_next": best_score - second_score,
            "evidence": {"candidate": best, "runner": "role_foundation_pipeline.auto_active_root"},
        }
    )
    return decision


def _flat_script_collection_candidate(candidate: dict[str, Any]) -> bool:
    path = str(candidate.get("path") or "").replace("\\", "/").strip("/").lower()
    return bool(
        path in PREFERRED_SCOPE_ROOTS
        and int(candidate.get("max_depth") or 0) == 0
        and not candidate.get("manifest_samples")
        and int(candidate.get("python_files") or 0) <= scope_policy_int("flat_script_collection_max_files", 20)
    )


def _current_root_is_python_product(project_dir: Path) -> bool:
    root_modules = list(project_dir.glob("*.py"))
    if (project_dir / "__init__.py").exists() and len(root_modules) >= 5:
        return True
    manifests = set(scope_policy_list("python_product_manifest_names"))
    if not any((project_dir / name).is_file() for name in manifests):
        return False
    entrypoints = set(scope_policy_list("python_product_entrypoints"))
    package_dirs = [
        child for child in project_dir.iterdir()
        if child.is_dir()
        and (child / "__init__.py").exists()
        and not _disfavored_scope_root(child.name)
    ]
    has_entrypoint = any(path.name.lower() in entrypoints for path in root_modules)
    root_package_app = (project_dir / "__init__.py").exists() and bool(package_dirs)
    return has_entrypoint or root_package_app


def _selected_scope_decision(project_dir: Path, candidate: dict[str, Any], source: str) -> dict[str, Any]:
    decision = _active_root_decision(project_dir, candidate["path"])
    decision.update(
        {
            "source": source,
            "selection_confidence": "high",
            "selected_candidate_score": int(candidate.get("score") or 0),
            "evidence": {"candidate": candidate, "runner": "role_foundation_pipeline.auto_active_root"},
        }
    )
    return decision
