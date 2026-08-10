from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from runtime.architecture_analysis_document import write_architecture_analysis_document
from runtime.architect_red_team import red_team_architecture_decision
from runtime.configured_role_pipeline import artifact_by_type, producer_for_artifact_type, run_configured_role_prefix
from runtime.contract_registry import load_artifact_contracts
from runtime.foundation_semantic_quality import evaluate_foundation_semantic_quality
from runtime.human_document_quality import evaluate_human_role_documents
from runtime.local_inference import LocalInferenceConfig
from runtime.project_benchmark import analyze_project
from runtime.project_interpreter import interpret_project_report
from runtime.role_artifact_quality import evaluate_role_artifacts
from runtime.role_skill_common import load_skill_registry, write_role_artifact
from runtime.scope_selection_document import write_scope_selection_document
from runtime.spec_writer_red_team import red_team_technical_spec
from runtime.technical_spec_document import write_technical_spec_document

def write_role_foundation_report(root: Path, payload: dict[str, Any]) -> Path:
    out_dir = root / "artifacts" / "roles" / "foundations"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"role_foundation_{stamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path

def _project_map_artifact(project_dir: Path, goal: str, project_map_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": "ProjectMapReport",
        "role": producer_for_artifact_type("ProjectMapReport"),
        "status": "ok",
        "created_at": _now(),
        "goal": goal,
        "project": project_dir.as_posix(),
        "content": project_map_report,
        "forbidden_actions_observed": [],
        "forbidden_actions_enforced": ["write_code", "edit_registry", "execute_pipeline", "promote_candidate"],
    }

def _active_root_decision_artifact(project_dir: Path, goal: str, decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": "ActiveRootDecision",
        "role": "human",
        "status": decision["status"],
        "created_at": _now(),
        "goal": goal,
        "project": project_dir.as_posix(),
        "content": decision,
        "forbidden_actions_observed": [],
        "forbidden_actions_enforced": ["write_code", "edit_registry", "execute_pipeline"],
    }

def _active_root_decision(project_dir: Path, active_root: str | Path | None) -> dict[str, Any]:
    if active_root is None:
        return {
            "artifact_type": "ActiveRootDecision",
            "status": "not_selected",
            "portfolio_root": project_dir.as_posix(),
            "selected_root": None,
            "selected_relative_path": None,
            "source": "not_provided",
        }
    selected = Path(active_root)
    if not selected.is_absolute():
        selected = project_dir / selected
    selected = selected.resolve()
    portfolio = project_dir.resolve()
    if not _is_relative_to(selected, portfolio):
        raise ValueError("active_root must be inside project_dir")
    if not selected.exists() or not selected.is_dir():
        raise ValueError("active_root must point to an existing directory")
    return {
        "artifact_type": "ActiveRootDecision",
        "status": "selected",
        "portfolio_root": portfolio.as_posix(),
        "selected_root": selected.as_posix(),
        "selected_relative_path": selected.relative_to(portfolio).as_posix(),
        "source": "explicit_user_or_cli",
        "decision_policy": "downstream roles may run only on selected_root",
    }

def _native_python_package_scope(project_dir: Path) -> str | None:
    native_named = any(token in project_dir.name.lower() for token in ("rust", "pyo3", "native", "extension"))
    if not ((project_dir / "Cargo.toml").exists() or ((project_dir / "pyproject.toml").exists() and native_named)):
        return None
    aliases = _project_aliases(project_dir)
    for child in sorted(project_dir.iterdir(), key=lambda item: item.name.lower()):
        if not child.is_dir() or not (child / "__init__.py").exists():
            continue
        normalized = child.name.lower().replace("-", "_")
        if normalized in aliases:
            return child.name
    return None

def _scope_selection_artifact(project_dir: Path, goal: str, scope_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": "ScopeSelectionReport",
        "role": producer_for_artifact_type("ScopeSelectionReport"),
        "status": scope_report["status"],
        "created_at": _now(),
        "goal": goal,
        "project": project_dir.as_posix(),
        "content": scope_report,
        "forbidden_actions_observed": [],
        "forbidden_actions_enforced": ["build_adr", "build_technical_spec", "write_code", "execute_pipeline"],
    }

def _requires_scope_selection(project_map_report: dict[str, Any], *, active_root_selected: bool = False) -> bool:
    source_health = dict(project_map_report.get("source_health") or {})
    shape = str(source_health.get("project_shape") or "")
    status = str(source_health.get("status") or "")
    if active_root_selected:
        if int(source_health.get("packaged_copy_signal_count") or 0) > 0:
            return True
        if status == "damaged" and int(source_health.get("inaccessible_count") or 0) > 0:
            return True
        return False
    if shape == "dirty_portfolio":
        return True
    if int(source_health.get("packaged_copy_signal_count") or 0) > 0:
        return True
    if _syntax_damage_is_fixture_only(source_health):
        return False
    if status == "damaged":
        return True
    return False

def _scope_selection_report(
    project_dir: Path,
    project_map_report: dict[str, Any],
    analyzer_outputs: dict[str, Any],
    *,
    active_root_selected: bool = False,
) -> dict[str, Any]:
    source_health = dict(project_map_report.get("source_health") or {})
    candidates = _scope_candidates(project_dir)
    recommendation = "choose_active_root_before_role_pipeline"
    preferred = candidates[0]["path"] if len(candidates) == 1 else None
    confidence = "single_candidate" if len(candidates) == 1 else "ambiguous"
    return {
        "artifact_type": "ScopeSelectionReport",
        "status": "blocked_until_scope_selected" if _requires_scope_selection(project_map_report, active_root_selected=active_root_selected) else "not_required",
        "root": project_dir.as_posix(),
        "reason": _scope_selection_reason(source_health),
        "source_health": source_health,
        "recommended_action": recommendation,
        "preferred_candidate": preferred,
        "selection_confidence": confidence,
        "candidate_roots": candidates,
        "excluded_noise_policy": [
            ".venv",
            "venv",
            "node_modules",
            "__pycache__",
            ".pytest_cache",
            "dist",
            "build",
            "archives",
            "runs",
            "generated",
        ],
        "blocked_downstream_artifacts": ["ArchitectureDecisionRecord", "TechnicalSpec"],
        "evidence": {
            "project_shape": source_health.get("project_shape"),
            "generated_run_samples": source_health.get("generated_run_samples", [])[:8],
            "packaged_copy_samples": source_health.get("packaged_copy_samples", [])[:8],
            "artifact_noise_samples": source_health.get("artifact_noise_samples", [])[:8],
            "tree_counts": dict(dict(analyzer_outputs.get("scan_project_tree", {})).get("counts", {})),
        },
    }

def _scope_selection_reason(source_health: dict[str, Any]) -> str:
    if source_health.get("project_shape") == "dirty_portfolio":
        return "source tree contains multiple project/snapshot candidates"
    if int(source_health.get("packaged_copy_signal_count") or 0) > 0:
        return "source tree contains packaged or snapshot copies"
    if source_health.get("status") == "damaged":
        return "source tree has damaged or inaccessible source evidence"
    return "source tree can be processed as a single active project"

def _scope_candidates(project_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        children = sorted((path for path in project_dir.iterdir() if path.is_dir()), key=lambda path: path.name.lower())
    except OSError:
        return rows
    excluded = set(scope_policy_list("candidate_excluded_dirs"))
    for child in children:
        if child.name in excluded:
            continue
        rows.append(_scope_candidate(project_dir, child))
    return sorted(rows, key=lambda row: (int(row["score"]), _scope_candidate_priority(str(row["path"])), row["last_write"] or ""), reverse=True)[:12]

def _scope_candidate(root: Path, path: Path) -> dict[str, Any]:
    file_count = 0
    py_count = 0
    js_ts_count = 0
    md_count = 0
    manifest_hits: list[str] = []
    noise_hits: list[str] = []
    max_depth = 0
    last_write = ""
    largest_py: list[dict[str, Any]] = []
    for item in _iter_candidate_files(path):
        file_count += 1
        rel = item.relative_to(path).as_posix()
        max_depth = max(max_depth, len(Path(rel).parts) - 1)
        try:
            stat = item.stat()
            stamp = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
            if stamp > last_write:
                last_write = stamp
            size = stat.st_size
        except OSError:
            size = 0
        suffix = item.suffix.lower()
        if suffix == ".py":
            py_count += 1
            largest_py.append({"path": rel, "size_bytes": size})
        elif suffix in {".js", ".ts"}:
            js_ts_count += 1
        elif suffix == ".md":
            md_count += 1
        if item.name.lower() in set(scope_policy_list("manifest_names")):
            manifest_hits.append(rel)
        if _candidate_noise_path(rel):
            noise_hits.append(rel)
    largest_py = sorted(largest_py, key=lambda row: int(row["size_bytes"]), reverse=True)[:5]
    rel_path = path.relative_to(root).as_posix()
    score = _scope_candidate_score(
        file_count,
        py_count,
        js_ts_count,
        manifest_hits,
        noise_hits,
        rel_path=rel_path,
        root_name=root.name,
        parent_name=root.parent.name,
    )
    return {
        "path": rel_path,
        "score": score,
        "kind": _scope_candidate_kind(py_count, js_ts_count, manifest_hits),
        "file_count": file_count,
        "python_files": py_count,
        "js_ts_files": js_ts_count,
        "markdown_files": md_count,
        "max_depth": max_depth,
        "last_write": last_write,
        "manifest_samples": sorted(manifest_hits)[:8],
        "noise_samples": sorted(noise_hits)[:8],
        "largest_python_samples": largest_py,
    }

def _iter_candidate_files(path: Path):
    excluded = set(scope_policy_list("candidate_excluded_dirs"))
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            children = sorted(current.iterdir(), key=lambda item: item.name.lower())
        except OSError:
            continue
        for child in children:
            parts = set(child.relative_to(path).parts)
            if parts & excluded:
                continue
            if child.is_dir():
                stack.append(child)
            elif child.is_file():
                yield child

def _scope_candidate_score(
    file_count: int,
    py_count: int,
    js_ts_count: int,
    manifest_hits: list[str],
    noise_hits: list[str],
    *,
    rel_path: str,
    root_name: str,
    parent_name: str,
) -> int:
    score = 0
    if file_count:
        score += min(20, file_count // 5)
    if py_count:
        score += min(45, py_count * 2)
    if js_ts_count:
        score += min(25, js_ts_count)
    score += min(20, len(manifest_hits) * 5)
    score -= min(35, len(noise_hits) * 4)
    score += _scope_path_score(rel_path, root_name=root_name, parent_name=parent_name)
    return max(0, score)
