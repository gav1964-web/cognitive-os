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
from runtime.role_project_analysis import enrich_weak_contract_readiness as _enrich_weak_contract_readiness
from runtime.role_project_analysis import prepare_role_project_report
from runtime.role_artifact_quality import evaluate_role_artifacts
from runtime.role_skill_common import load_skill_registry, write_role_artifact
from runtime.scope_selection_document import write_scope_selection_document
from runtime.spec_writer_red_team import red_team_technical_spec
from runtime.target_quality import semantic_target_quality_report
from runtime.technical_spec_document import write_technical_spec_document

def run_role_foundation_pipeline(
    *,
    root: Path,
    project_dir: Path,
    goal: str,
    write: bool = False,
    active_root: str | Path | None = None,
    architect_advisory_config: LocalInferenceConfig | None = None,
    spec_writer_advisory_config: LocalInferenceConfig | None = None,
    _auto_scope_depth: int = 0,
    _active_root_is_auto: bool = False,
    _auto_scope_current_root_confirmed: bool = False,
) -> dict[str, Any]:
    load_skill_registry(root)
    active_root_decision = _active_root_decision(project_dir, active_root)
    if active_root_decision["status"] == "selected" and _active_root_is_auto:
        active_root_decision["source"] = "auto_safe_scope_selector"
    analysis_project_dir = Path(str(active_root_decision.get("selected_root") or project_dir)).resolve()
    with _pushd(_analysis_cwd(root, analysis_project_dir)):
        analyzer_outputs = analyze_project(analysis_project_dir)
        project_map_report = prepare_role_project_report(
            root=root,
            goal=goal,
            analyzer_outputs=analyzer_outputs,
        )
    if active_root_decision["status"] == "selected":
        project_map_report = _attach_active_root_evidence(project_map_report, active_root_decision)
    project_artifact = _project_map_artifact(analysis_project_dir, goal, project_map_report)
    active_root_selected = active_root_decision["status"] == "selected"
    current_root_confirmed = _auto_scope_current_root_confirmed
    scope_report = _scope_selection_report(
        analysis_project_dir,
        project_map_report,
        analyzer_outputs,
        active_root_selected=active_root_selected,
        current_root_confirmed=current_root_confirmed,
    )
    scope_required = _requires_scope_selection(
        project_map_report,
        active_root_selected=active_root_selected,
        current_root_confirmed=current_root_confirmed,
    )
    auto_scope_useful = scope_required or _syntax_damage_is_test_support_only(dict(project_map_report.get("source_health") or {}))
    if (not active_root_selected or _active_root_is_auto) and _auto_scope_depth < 2 and auto_scope_useful:
        auto_decision = _auto_active_root_decision(analysis_project_dir, scope_report)
        if auto_decision["status"] == "selected":
            selected_root = Path(str(auto_decision["selected_root"])).resolve()
            return run_role_foundation_pipeline(
                root=root,
                project_dir=project_dir,
                goal=goal,
                write=write,
                active_root=selected_root,
                architect_advisory_config=architect_advisory_config,
                spec_writer_advisory_config=spec_writer_advisory_config,
                _auto_scope_depth=_auto_scope_depth + 1,
                _active_root_is_auto=True,
                _auto_scope_current_root_confirmed=selected_root == analysis_project_dir,
            )
    if scope_required:
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
        spec_writer_advisory_config=spec_writer_advisory_config,
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
    selected_candidate_quality = _selected_candidate_quality(spec, analysis_project_dir)
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
            "llm_invoked": bool(
                dict(adr.get("architect_advisory", {})).get("llm_invoked")
                or dict(spec.get("spec_writer_advisory", {})).get("llm_invoked")
            ),
        },
    }
    if write:
        result["report_path"] = write_role_foundation_report(root, result).as_posix()
    return result

def _selected_candidate_quality(spec: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    contract = dict(spec.get("extraction_contract", {}) or {})
    quality = dict(contract.get("semantic_quality", {}) or {})
    target = str(contract.get("candidate") or quality.get("target") or "")
    if not target:
        return quality
    ranked = [str(row.get("source")) for row in list(contract.get("ranked_candidates") or []) if isinstance(row, dict)]
    evidence = [str(row.get("source")) for row in list(spec.get("source_evidence") or []) if isinstance(row, dict)]
    return semantic_target_quality_report(
        target,
        ranked_candidates=ranked,
        source_evidence=evidence,
        context_evidence=[project_dir.name],
        selection_reason=str(contract.get("selection_reason") or ""),
        structural_evidence=dict(contract.get("structural_evidence") or {}),
        input_contract=dict(contract.get("input_contract") or {}),
        output_contract=dict(contract.get("output_contract") or {}),
        side_effect_contract=dict(contract.get("side_effects") or {}),
    )

def _attach_active_root_evidence(project_map_report: dict[str, Any], active_root_decision: dict[str, Any]) -> dict[str, Any]:
    source_health = dict(project_map_report.get("source_health") or {})
    source_health["active_root_decision"] = {
        "status": active_root_decision.get("status"),
        "selected_relative_path": active_root_decision.get("selected_relative_path"),
        "source": active_root_decision.get("source"),
        "decision_policy": active_root_decision.get("decision_policy"),
    }
    source_health["noise_exclusion_decision"] = {
        "status": "active_root_selected",
        "policy": "downstream roles may use selected_root as active source and treat generated/test/docs noise as context-only evidence",
        "source": active_root_decision.get("source"),
    }
    answers = dict(project_map_report.get("answers") or {})
    answers["0_source_health"] = source_health
    return {
        **project_map_report,
        "source_health": source_health,
        "answers": answers,
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
    semantic_quality = evaluate_foundation_semantic_quality({"artifacts": artifacts})
    architect_red_team = red_team_architecture_decision(adr, project)
    spec_red_team = red_team_technical_spec(spec, adr)
    human_document_quality = None
    for name, result in dict(quality.get("results", {})).items():
        checks[f"{name}_quality_passed"] = dict(result).get("passed") is True
    checks["foundation_semantic_quality_passed"] = semantic_quality.get("status") == "ok"
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
    artifact_score = _ratio(sum(1 for ok in checks.values() if ok), len(checks))
    semantic_score = _ratio(float(semantic_quality.get("min_score") or 0.0), 10.0)
    overall_score = min(artifact_score, semantic_score)
    payload = {
        "passed": not warnings,
        "artifact_score": artifact_score,
        "semantic_score": semantic_score,
        "overall_score": overall_score,
        "role_scores_10pt": dict(semantic_quality.get("role_scores") or {}),
        "min_role_score_10pt": semantic_quality.get("min_score"),
        "quality": quality,
        "foundation_semantic_quality": semantic_quality,
        "architect_red_team": architect_red_team,
        "spec_writer_red_team": spec_red_team,
        "checks": checks,
        "warnings": warnings,
    }
    if human_document_quality is not None:
        payload["human_document_quality"] = human_document_quality
    return payload
