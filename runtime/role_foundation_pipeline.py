"""Focused foundation pipeline: ProjectMapReport -> ADR -> TechnicalSpec."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .architecture_analysis_document import write_architecture_analysis_document
from .local_inference import LocalInferenceConfig
from .project_benchmark import analyze_project
from .role_skill_common import load_skill_registry, write_role_artifact
from .role_skills import run_architect_skill, run_spec_writer_skill


def run_role_foundation_pipeline(
    *,
    root: Path,
    project_dir: Path,
    goal: str,
    write: bool = False,
    architect_advisory_config: LocalInferenceConfig | None = None,
) -> dict[str, Any]:
    load_skill_registry(root)
    with _pushd(root):
        project_map_report = analyze_project(project_dir)["project_map_report"]
    project_artifact = _project_map_artifact(project_dir, goal, project_map_report)
    adr = run_architect_skill(
        goal=goal,
        project_report=project_map_report,
        advisory_config=architect_advisory_config,
    )
    spec = run_spec_writer_skill(architecture_decision=adr)
    artifacts = {
        "project_map_report": project_artifact,
        "architecture_decision": adr,
        "technical_spec": spec,
    }
    paths = _write_artifacts(root, artifacts) if write else {}
    human_documents = _write_human_documents(root, artifacts) if write else {}
    score = score_role_foundation(artifacts, paths if write else None)
    selected_candidate = _selected_extraction_candidate(spec)
    result = {
        "status": "ok" if score["passed"] else "failed",
        "kind": "role_foundation_pipeline",
        "milestone": "ProjectMapReport -> ArchitectureDecisionRecord -> TechnicalSpec",
        "created_at": _now(),
        "project": project_dir.as_posix(),
        "goal": goal,
        "score": score,
        "architect_advisory": adr.get("architect_advisory", {}),
        "selected_extraction_candidate": selected_candidate,
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
        "expected_best_extraction_candidate": expected_candidate,
    }


def score_role_foundation(artifacts: dict[str, dict[str, Any]], paths: dict[str, str] | None = None) -> dict[str, Any]:
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
        "spec_contract_candidate_ranked_first": _contract_candidate_ranked_first(spec),
        "spec_contract_has_selection_reason": _contract_has_selection_reason(spec),
        "spec_acceptance_is_source_linked": _acceptance_is_source_linked(spec),
    }
    if paths is not None:
        checks["paths_written"] = all(paths.get(key) for key in artifacts)
    warnings = [name for name, ok in checks.items() if not ok]
    return {
        "passed": not warnings,
        "artifact_score": _ratio(sum(1 for ok in checks.values() if ok), len(checks)),
        "checks": checks,
        "warnings": warnings,
    }


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
        "role": "project_analyzer",
        "status": "ok",
        "created_at": _now(),
        "goal": goal,
        "project": project_dir.as_posix(),
        "content": project_map_report,
        "forbidden_actions_observed": [],
        "forbidden_actions_enforced": ["write_code", "edit_registry", "execute_pipeline", "promote_candidate"],
    }


def _write_artifacts(root: Path, artifacts: dict[str, dict[str, Any]]) -> dict[str, str]:
    roles = {
        "project_map_report": "project_analyzer",
        "architecture_decision": "architect",
        "technical_spec": "spec_writer",
    }
    paths = {}
    for key, artifact in artifacts.items():
        path = write_role_artifact(root, roles[key], artifact)
        artifact["artifact_path"] = path.as_posix()
        paths[key] = path.as_posix()
    return paths


def _write_human_documents(root: Path, artifacts: dict[str, dict[str, Any]]) -> dict[str, str]:
    path = write_architecture_analysis_document(
        root=root,
        project_report=artifacts["project_map_report"],
        architecture_decision=artifacts["architecture_decision"],
        technical_spec=artifacts["technical_spec"],
        output_group="foundations",
    )
    return {"architecture_analysis": path.as_posix()}


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


@contextmanager
def _pushd(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)
