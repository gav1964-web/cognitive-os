"""Focused foundation pipeline: ProjectMapReport -> ADR -> TechnicalSpec."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .architecture_analysis_document import write_architecture_analysis_document
from .architect_red_team import red_team_architecture_decision
from .configured_role_pipeline import artifact_by_type, producer_for_artifact_type, run_configured_role_prefix
from .contract_registry import load_artifact_contracts
from .human_document_quality import evaluate_human_role_documents
from .local_inference import LocalInferenceConfig
from .project_benchmark import analyze_project
from .project_interpreter import interpret_project_report
from .role_artifact_quality import evaluate_role_artifacts
from .role_skill_common import load_skill_registry, write_role_artifact
from .scope_selection_document import write_scope_selection_document
from .spec_writer_red_team import red_team_technical_spec
from .technical_spec_document import write_technical_spec_document


def run_role_foundation_pipeline(
    *,
    root: Path,
    project_dir: Path,
    goal: str,
    write: bool = False,
    active_root: str | Path | None = None,
    architect_advisory_config: LocalInferenceConfig | None = None,
) -> dict[str, Any]:
    load_skill_registry(root)
    active_root_decision = _active_root_decision(project_dir, active_root)
    analysis_project_dir = Path(str(active_root_decision.get("selected_root") or project_dir)).resolve()
    with _pushd(_analysis_cwd(root, analysis_project_dir)):
        analyzer_outputs = analyze_project(analysis_project_dir)
        project_map_report = analyzer_outputs["project_map_report"]
        project_map_report = _attach_interpretation(
            root=root,
            goal=goal,
            project_map_report=project_map_report,
            analyzer_outputs=analyzer_outputs,
        )
    project_artifact = _project_map_artifact(analysis_project_dir, goal, project_map_report)
    scope_report = _scope_selection_report(analysis_project_dir, project_map_report, analyzer_outputs)
    if _requires_scope_selection(project_map_report):
        scope_artifact = _scope_selection_artifact(analysis_project_dir, goal, scope_report)
        artifacts = {
            "project_map_report": project_artifact,
            "scope_selection_report": scope_artifact,
        }
        if active_root_decision["status"] == "selected":
            artifacts["active_root_decision"] = _active_root_decision_artifact(project_dir, goal, active_root_decision)
        paths = _write_artifacts(root, artifacts) if write else {}
        human_documents = _write_scope_human_documents(root, scope_report) if write else {}
        result = {
            "status": "blocked",
            "kind": "role_foundation_pipeline",
            "milestone": "ProjectMapReport -> ScopeSelectionReport",
            "created_at": _now(),
            "project": analysis_project_dir.as_posix(),
            "portfolio_root": project_dir.as_posix(),
            "goal": goal,
            "blocker": "scope_selection_required",
            "scope_selection_report": scope_report,
            "score": _blocked_scope_score(project_artifact, scope_artifact),
            "artifacts": _artifact_summary(artifacts, paths),
            "human_documents": human_documents,
            "safety": {
                "source_code_changes": False,
                "registry_changes": False,
                "foundry_invoked": False,
                "llm_invoked": False,
            },
        }
        if write:
            result["report_path"] = write_role_foundation_report(root, result).as_posix()
        return result
    built_artifacts = run_configured_role_prefix(
        goal=goal,
        project_report=project_map_report,
        architect_advisory_config=architect_advisory_config,
        until_artifact_type="TechnicalSpec",
    )
    artifacts = {
        "project_map_report": project_artifact,
        **built_artifacts,
    }
    if active_root_decision["status"] == "selected":
        artifacts["active_root_decision"] = _active_root_decision_artifact(project_dir, goal, active_root_decision)
    adr = artifact_by_type(artifacts, "ArchitectureDecisionRecord")
    spec = artifact_by_type(artifacts, "TechnicalSpec")
    paths = _write_artifacts(root, artifacts) if write else {}
    human_documents = _write_human_documents(root, artifacts) if write else {}
    score = score_role_foundation(artifacts, paths if write else None, human_documents=human_documents if write else None)
    architect_red_team = red_team_architecture_decision(adr, project_artifact)
    spec_red_team = red_team_technical_spec(spec, adr)
    selected_candidate = _selected_extraction_candidate(spec)
    selected_candidate_quality = dict(dict(spec.get("extraction_contract", {})).get("semantic_quality", {}))
    result = {
        "status": "ok" if score["passed"] else "failed",
        "kind": "role_foundation_pipeline",
        "milestone": "ProjectMapReport -> ArchitectureDecisionRecord -> TechnicalSpec",
        "created_at": _now(),
        "project": analysis_project_dir.as_posix(),
        "portfolio_root": project_dir.as_posix(),
        "active_root_decision": active_root_decision if active_root_decision["status"] == "selected" else None,
        "goal": goal,
        "score": score,
        "architect_red_team": architect_red_team,
        "spec_writer_red_team": spec_red_team,
        "architect_advisory": adr.get("architect_advisory", {}),
        "selected_extraction_candidate": selected_candidate,
        "selected_candidate_quality": selected_candidate_quality,
        "artifacts": _artifact_summary(artifacts, paths),
        "human_documents": human_documents,
        "safety": {
            "source_code_changes": False,
            "registry_changes": False,
            "foundry_invoked": False,
            "llm_invoked": bool(dict(adr.get("architect_advisory", {})).get("llm_invoked")),
        },
    }
    if write:
        result["report_path"] = write_role_foundation_report(root, result).as_posix()
    return result


def _attach_interpretation(
    *,
    root: Path,
    goal: str,
    project_map_report: dict[str, Any],
    analyzer_outputs: dict[str, Any],
) -> dict[str, Any]:
    """Attach L3.5/L4/synthesis artifacts as evidence, not as source-truth replacement."""

    goal_report = {
        "goal_id": f"role_foundation_{Path(str(project_map_report.get('root') or '')).name or 'project'}",
        "goal": goal,
        "execution": {
            "status": "ok",
            "completed_nodes": list(analyzer_outputs),
            "outputs": analyzer_outputs,
        },
    }
    interpretation = interpret_project_report(goal_report, root=root.as_posix())
    return {
        **project_map_report,
        "level35_project_signals": interpretation.get("level35_project_signals", {}),
        "level4_project_interpretation": interpretation.get("level4_project_interpretation", {}),
        "analysis_tasks": interpretation.get("analysis_tasks", {}),
        "architecture_synthesis": interpretation.get("architecture_synthesis", {}),
        "knowledge_gap": interpretation.get("knowledge_gap"),
        "research_plan": interpretation.get("research_plan"),
    }


def run_role_foundation_benchmark(
    root: Path,
    *,
    benchmarks_dir: Path,
    project: str | None = None,
    write: bool = False,
    architect_advisory_config: LocalInferenceConfig | None = None,
) -> dict[str, Any]:
    projects_dir = benchmarks_dir / "projects"
    project_dirs = _selected_projects(projects_dir, project)
    cases = [
        run_role_foundation_case(
            root=root,
            project_dir=project_dir,
            write=write,
            architect_advisory_config=architect_advisory_config,
        )
        for project_dir in project_dirs
    ]
    report = _benchmark_report(cases)
    if write:
        out_dir = root / "artifacts" / "field_trials"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = out_dir / f"role_foundation_field_trial_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    return report


def run_role_foundation_case(
    *,
    root: Path,
    project_dir: Path,
    write: bool = False,
    architect_advisory_config: LocalInferenceConfig | None = None,
) -> dict[str, Any]:
    expected_candidate = _expected_best_extraction_candidate(project_dir)
    result = run_role_foundation_pipeline(
        root=root,
        project_dir=project_dir,
        goal=f"Produce ADR and TechnicalSpec for first safe transformation in {project_dir.name}",
        write=write,
        architect_advisory_config=architect_advisory_config,
    )
    score = _score_expected_candidate(
        result["score"],
        result.get("selected_extraction_candidate"),
        expected_candidate,
    )
    return {
        "project": project_dir.name,
        "status": "ok" if score["passed"] else "failed",
        "score": score,
        "safety": result["safety"],
        "architect_advisory": result.get("architect_advisory", {}),
        "human_documents": result.get("human_documents", {}),
        "selected_extraction_candidate": result.get("selected_extraction_candidate"),
        "selected_candidate_quality": result.get("selected_candidate_quality", {}),
        "expected_best_extraction_candidate": expected_candidate,
    }


def score_role_foundation(
    artifacts: dict[str, dict[str, Any]],
    paths: dict[str, str] | None = None,
    *,
    human_documents: dict[str, str] | None = None,
) -> dict[str, Any]:
    project = dict(artifacts.get("project_map_report", {}))
    adr = dict(artifacts.get("architecture_decision", {}))
    spec = dict(artifacts.get("technical_spec", {}))
    checks = {
        "project_map_report_present": project.get("artifact_type") == "ProjectMapReport",
        "project_report_has_answers": bool(dict(project.get("content", {})).get("answers")),
        "adr_present": adr.get("artifact_type") == "ArchitectureDecisionRecord",
        "adr_has_chosen_option": bool(dict(adr.get("chosen_option", {})).get("id")),
        "adr_has_traceability": bool(adr.get("traceability")),
        "spec_present": spec.get("artifact_type") == "TechnicalSpec",
        "spec_has_requirements": bool(spec.get("requirements")),
        "spec_has_acceptance": bool(spec.get("acceptance_criteria")),
        "spec_has_traceability": bool(spec.get("traceability_table")),
        "spec_has_source_evidence": bool(spec.get("source_evidence")),
        "spec_has_extraction_contract": bool(dict(spec.get("extraction_contract", {})).get("candidate")),
        "spec_has_work_plan_contract": bool(dict(spec.get("work_plan_contract", {})).get("obligations")),
        "spec_contract_candidate_ranked_first": _contract_candidate_ranked_first(spec),
        "spec_contract_has_selection_reason": _contract_has_selection_reason(spec),
        "spec_acceptance_is_source_linked": _acceptance_is_source_linked(spec),
    }
    quality = evaluate_role_artifacts(artifacts)
    architect_red_team = red_team_architecture_decision(adr, project)
    spec_red_team = red_team_technical_spec(spec, adr)
    human_document_quality = None
    for name, result in dict(quality.get("results", {})).items():
        checks[f"{name}_quality_passed"] = dict(result).get("passed") is True
    checks["architect_red_team_passed"] = architect_red_team.get("status") == "pass"
    checks["spec_writer_red_team_passed"] = spec_red_team.get("status") == "pass"
    if paths is not None:
        checks["paths_written"] = all(paths.get(key) for key in artifacts)
    if human_documents is not None:
        human_document_quality = evaluate_human_role_documents(
            architecture_document=human_documents.get("architecture_analysis"),
            technical_spec_document=human_documents.get("technical_spec"),
        )
        checks["human_documents_quality_passed"] = human_document_quality.get("status") == "pass"
    warnings = [name for name, ok in checks.items() if not ok]
    payload = {
        "passed": not warnings,
        "artifact_score": _ratio(sum(1 for ok in checks.values() if ok), len(checks)),
        "quality": quality,
        "architect_red_team": architect_red_team,
        "spec_writer_red_team": spec_red_team,
        "checks": checks,
        "warnings": warnings,
    }
    if human_document_quality is not None:
        payload["human_document_quality"] = human_document_quality
    return payload


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


def _requires_scope_selection(project_map_report: dict[str, Any]) -> bool:
    source_health = dict(project_map_report.get("source_health") or {})
    shape = str(source_health.get("project_shape") or "")
    status = str(source_health.get("status") or "")
    if shape == "dirty_portfolio":
        return True
    if int(source_health.get("packaged_copy_signal_count") or 0) > 0:
        return True
    if status == "damaged":
        return True
    return False


def _scope_selection_report(
    project_dir: Path,
    project_map_report: dict[str, Any],
    analyzer_outputs: dict[str, Any],
) -> dict[str, Any]:
    source_health = dict(project_map_report.get("source_health") or {})
    candidates = _scope_candidates(project_dir)
    recommendation = "choose_active_root_before_role_pipeline"
    preferred = candidates[0]["path"] if len(candidates) == 1 else None
    confidence = "single_candidate" if len(candidates) == 1 else "ambiguous"
    return {
        "artifact_type": "ScopeSelectionReport",
        "status": "blocked_until_scope_selected" if _requires_scope_selection(project_map_report) else "not_required",
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
    for child in children:
        if child.name in {".git", ".hg", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}:
            continue
        rows.append(_scope_candidate(project_dir, child))
    return sorted(rows, key=lambda row: (row["score"], row["last_write"] or ""), reverse=True)[:12]


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
        if item.name.lower() in {"pyproject.toml", "requirements.txt", "setup.py", "package.json", "readme.md"}:
            manifest_hits.append(rel)
        if _candidate_noise_path(rel):
            noise_hits.append(rel)
    largest_py = sorted(largest_py, key=lambda row: int(row["size_bytes"]), reverse=True)[:5]
    score = _scope_candidate_score(file_count, py_count, js_ts_count, manifest_hits, noise_hits)
    rel_path = path.relative_to(root).as_posix()
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
    excluded = {".git", ".hg", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "site-packages"}
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


def _scope_candidate_score(file_count: int, py_count: int, js_ts_count: int, manifest_hits: list[str], noise_hits: list[str]) -> int:
    score = 0
    if file_count:
        score += min(20, file_count // 5)
    if py_count:
        score += min(45, py_count * 2)
    if js_ts_count:
        score += min(25, js_ts_count)
    score += min(20, len(manifest_hits) * 5)
    score -= min(35, len(noise_hits) * 4)
    return max(0, min(100, score))


def _candidate_noise_path(path: str) -> bool:
    lowered = path.replace("\\", "/").lower()
    parts = [part for part in lowered.split("/") if part]
    if any(part in {"test_workspace", "source_project", "archives", "runs", "generated", "scratch", "tmp"} for part in parts):
        return True
    return lowered.endswith((".zip", ".log", ".jsonl", ".sqlite", ".db", ".pkl", ".pickle", ".bin"))


def _scope_candidate_kind(py_count: int, js_ts_count: int, manifest_hits: list[str]) -> str:
    has_package = any(path.endswith("package.json") for path in manifest_hits)
    has_python = py_count > 0
    if has_python and has_package:
        return "mixed_python_frontend_candidate"
    if has_python:
        return "python_project_candidate"
    if js_ts_count or has_package:
        return "frontend_or_extension_candidate"
    return "artifact_or_unknown_candidate"


def _blocked_scope_score(project_artifact: dict[str, Any], scope_artifact: dict[str, Any]) -> dict[str, Any]:
    project = dict(project_artifact.get("content", {}))
    scope = dict(scope_artifact.get("content", {}))
    source_health = dict(scope.get("source_health") or project.get("source_health") or {})
    damaged_without_candidate = (
        source_health.get("status") == "damaged"
        and int(source_health.get("syntax_error_count") or 0) > 0
        and not scope.get("candidate_roots")
    )
    checks = {
        "project_map_report_present": project_artifact.get("artifact_type") == "ProjectMapReport",
        "scope_selection_report_present": scope_artifact.get("artifact_type") == "ScopeSelectionReport",
        "scope_selection_blocks_downstream": scope.get("status") == "blocked_until_scope_selected",
        "scope_selection_has_candidates_or_damaged_stop": bool(scope.get("candidate_roots")) or damaged_without_candidate,
        "adr_not_built": True,
        "technical_spec_not_built": True,
    }
    warnings = [name for name, ok in checks.items() if not ok]
    return {
        "passed": False,
        "blocked": True,
        "blocker": "scope_selection_required",
        "artifact_score": _ratio(sum(1 for ok in checks.values() if ok), len(checks)),
        "checks": checks,
        "warnings": warnings,
        "project_shape": dict(project.get("source_health") or {}).get("project_shape"),
    }


def _write_artifacts(root: Path, artifacts: dict[str, dict[str, Any]]) -> dict[str, str]:
    paths = {}
    contracts = load_artifact_contracts()
    for key, artifact in artifacts.items():
        artifact_type = str(artifact.get("artifact_type") or "")
        role = str(dict(contracts.get(artifact_type, {})).get("producer") or artifact.get("role") or "unknown")
        path = write_role_artifact(root, role, artifact)
        artifact["artifact_path"] = path.as_posix()
        paths[key] = path.as_posix()
    return paths


def _write_human_documents(root: Path, artifacts: dict[str, dict[str, Any]]) -> dict[str, str]:
    architecture_path = write_architecture_analysis_document(
        root=root,
        project_report=artifacts["project_map_report"],
        architecture_decision=artifacts["architecture_decision"],
        technical_spec=artifacts["technical_spec"],
        output_group="foundations",
    )
    spec_path = write_technical_spec_document(
        root=root,
        project_report=artifacts["project_map_report"],
        architecture_decision=artifacts["architecture_decision"],
        technical_spec=artifacts["technical_spec"],
        output_group="foundations",
    )
    return {"architecture_analysis": architecture_path.as_posix(), "technical_spec": spec_path.as_posix()}


def _write_scope_human_documents(root: Path, scope_report: dict[str, Any]) -> dict[str, str]:
    path = write_scope_selection_document(root=root, scope_report=scope_report, output_group="foundations")
    return {"scope_selection": path.as_posix()}


def _artifact_summary(artifacts: dict[str, dict[str, Any]], paths: dict[str, str]) -> dict[str, dict[str, Any]]:
    return {
        key: {
            "artifact_type": artifact.get("artifact_type"),
            "role": artifact.get("role"),
            "status": artifact.get("status"),
            "path": paths.get(key),
        }
        for key, artifact in artifacts.items()
    }


def _selected_projects(projects_dir: Path, project: str | None) -> list[Path]:
    if project:
        path = projects_dir / project
        if not path.is_dir():
            raise FileNotFoundError(f"benchmark project not found: {path}")
        return [path]
    return sorted(path for path in projects_dir.iterdir() if path.is_dir())


def _benchmark_report(cases: list[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(1 for case in cases if case["status"] == "ok")
    return {
        "status": "ok" if passed == len(cases) else "failed",
        "milestone": "Role Foundation Field Trial v0.1",
        "generated_at": _now(),
        "project_count": len(cases),
        "passed": passed,
        "summary": {
            "artifact_score": _ratio(sum(case["score"]["artifact_score"] for case in cases), len(cases)),
            "candidate_match_score": _ratio(
                sum(
                    1
                    for case in cases
                    if case["score"]["checks"].get("spec_contract_matches_expected_candidate") is True
                ),
                sum(1 for case in cases if case.get("expected_best_extraction_candidate")),
            ),
            "warnings": sum(len(case["score"]["warnings"]) for case in cases),
            "llm_invoked": sum(1 for case in cases if case["safety"].get("llm_invoked") is True),
        },
        "cases": cases,
    }


def _ratio(numerator: float, denominator: float) -> float:
    return 1.0 if denominator == 0 else round(numerator / denominator, 4)


def _acceptance_is_source_linked(spec: dict[str, Any]) -> bool:
    criteria = spec.get("acceptance_criteria", [])
    return any(
        isinstance(row, dict)
        and row.get("source")
        and ":" in str(row.get("source"))
        and str(row.get("source")) in str(row.get("criterion"))
        for row in criteria
    )


def _contract_candidate_ranked_first(spec: dict[str, Any]) -> bool:
    contract = dict(spec.get("extraction_contract", {}))
    candidate = str(contract.get("candidate") or "")
    ranked = contract.get("ranked_candidates", [])
    return bool(candidate and isinstance(ranked, list) and ranked and dict(ranked[0]).get("source") == candidate)


def _contract_has_selection_reason(spec: dict[str, Any]) -> bool:
    contract = dict(spec.get("extraction_contract", {}))
    return bool(str(contract.get("selection_reason") or "").strip())


def _selected_extraction_candidate(spec: dict[str, Any]) -> str | None:
    candidate = dict(spec.get("extraction_contract", {})).get("candidate")
    return str(candidate) if candidate else None


def _expected_best_extraction_candidate(project_dir: Path) -> str | None:
    path = project_dir / "expected_analysis.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = payload.get("expected_best_extraction_candidate")
    return str(expected) if expected else None


def _score_expected_candidate(score: dict[str, Any], selected: object, expected: str | None) -> dict[str, Any]:
    if not expected:
        return score
    checks = dict(score.get("checks", {}))
    checks["spec_contract_matches_expected_candidate"] = str(selected or "") == expected
    warnings = [name for name, ok in checks.items() if not ok]
    return {
        **score,
        "passed": not warnings,
        "artifact_score": _ratio(sum(1 for ok in checks.values() if ok), len(checks)),
        "checks": checks,
        "warnings": warnings,
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _analysis_cwd(root: Path, project_dir: Path) -> Path:
    root = root.resolve()
    project_dir = project_dir.resolve()
    if _is_relative_to(project_dir, root) or _is_relative_to(project_dir, root.parent):
        return root
    return project_dir.parent


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


@contextmanager
def _pushd(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)
