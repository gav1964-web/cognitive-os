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
from runtime.python_source_files import is_python_source_ref
from runtime.project_interpreter import interpret_project_report
from runtime.role_artifact_quality import evaluate_role_artifacts
from runtime.role_skill_common import load_skill_registry, write_role_artifact
from runtime.scope_selection_document import write_scope_selection_document
from runtime.scope_selection_policy import (
    ALIASED_CORE_SUFFIXES,
    DISFAVORED_SCOPE_ROOTS,
    MONOREPO_PYTHON_ROOTS,
    PREFERRED_SCOPE_ROOTS,
    SOFT_DISFAVORED_SCOPE_ROOTS,
    candidate_noise_path as _candidate_noise_path,
    disfavored_scope_root as _disfavored_scope_root,
    scope_candidate_kind as _scope_candidate_kind,
    scope_candidate_priority as _scope_candidate_priority,
    scope_path_score as _scope_path_score,
    scope_policy_int,
    scope_policy_list,
    syntax_error_fixture_path as _syntax_error_fixture_path,
)
from runtime.spec_writer_red_team import red_team_technical_spec
from runtime.technical_spec_document import write_technical_spec_document

def _syntax_damage_is_fixture_only(source_health: dict[str, Any]) -> bool:
    return _syntax_damage_is_test_support_only(source_health)

def _syntax_damage_is_test_support_only(source_health: dict[str, Any]) -> bool:
    if source_health.get("status") != "damaged":
        return False
    if int(source_health.get("inaccessible_count") or 0) > 0:
        return False
    count = int(source_health.get("syntax_error_count") or 0)
    samples = [dict(row) for row in list(source_health.get("syntax_error_samples") or []) if isinstance(row, dict)]
    if not count or count > len(samples):
        return False
    return all(_syntax_error_fixture_path(str(row.get("path") or "")) for row in samples)

def _clear_named_package_candidate(project_dir: Path, rel_path: str, best_score: int, second_score: int) -> bool:
    normalized_project = project_dir.name.lower().replace("-", "_")
    normalized_candidate = rel_path.replace("\\", "/").strip("/").split("/", 1)[0].lower().replace("-", "_")
    project_aliases = {normalized_project}
    if "__" in normalized_project:
        owner, repo = normalized_project.rsplit("__", 1)
        project_aliases.add(repo)
        if owner == repo:
            project_aliases.add(owner)
    if "_" in normalized_project:
        project_aliases.add(normalized_project.rsplit("_", 1)[-1])
    return bool(
        normalized_project
        and normalized_candidate in project_aliases
        and best_score >= scope_policy_int("named_package_min_score", 35)
    )

def _project_aliases(project_dir: Path) -> set[str]:
    normalized = project_dir.name.lower().replace("-", "_")
    aliases = {normalized}
    if "__" in normalized:
        owner, repo = normalized.rsplit("__", 1)
        aliases.add(owner)
        aliases.add(repo)
    if "_" in normalized:
        aliases.add(normalized.rsplit("_", 1)[-1])
        parts = [part for part in normalized.split("_") if part]
        aliases.update("_".join(parts[index:]) for index in range(1, len(parts)))
    if normalized.endswith("_python"):
        aliases.add(normalized.removesuffix("_python") + "py")
    aliases.update(alias.replace("_", "") for alias in list(aliases))
    return aliases

def _frontend_python_package_scope(project_dir: Path, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not any(str(row.get("path") or "").split("/", 1)[0].lower() == "packages" for row in candidates):
        return None
    aliases = _project_aliases(project_dir)
    for row in candidates:
        path = str(row.get("path") or "").replace("\\", "/").strip("/")
        first = path.split("/", 1)[0].lower().replace("-", "_")
        if (
            first in aliases
            and int(row.get("python_files") or 0) >= scope_policy_int("frontend_package_min_python_files", 8)
            and int(row.get("score") or 0) >= scope_policy_int("frontend_package_min_score", 70)
        ):
            if (project_dir / path).is_dir():
                return dict(row)
    return None

def _application_python_package_scope(project_dir: Path, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    aliases = _project_aliases(project_dir)
    tooling = {"pylint", *DISFAVORED_SCOPE_ROOTS, *SOFT_DISFAVORED_SCOPE_ROOTS}
    has_tooling = any(str(row.get("path") or "").split("/", 1)[0].lower() in tooling for row in candidates)
    if not has_tooling:
        return None
    for row in candidates:
        path = str(row.get("path") or "").replace("\\", "/").strip("/")
        first = path.split("/", 1)[0].lower().replace("-", "_")
        if (
            first in aliases
            and int(row.get("python_files") or 0) >= scope_policy_int("application_package_min_python_files", 40)
            and int(row.get("score") or 0) >= scope_policy_int("application_package_min_score", 45)
        ):
            if (project_dir / path).is_dir():
                return dict(row)
    return None

def _monorepo_python_modules_scope(project_dir: Path, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in candidates:
        path = str(row.get("path") or "").replace("\\", "/").strip("/")
        if path.lower() not in MONOREPO_PYTHON_ROOTS:
            continue
        if (
            int(row.get("score") or 0) >= scope_policy_int("monorepo_min_score", 80)
            and int(row.get("python_files") or 0) >= scope_policy_int("monorepo_min_python_files", 40)
        ):
            if (project_dir / path).is_dir():
                return dict(row)
    return None

def _aliased_core_package_scope(project_dir: Path, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    aliases = _project_aliases(project_dir)
    for index, row in enumerate(candidates[: scope_policy_int("aliased_core_top_n", 5)]):
        path = str(row.get("path") or "").replace("\\", "/").strip("/")
        first = path.split("/", 1)[0].lower().replace("-", "_")
        has_alias = any(first == f"{alias}{suffix}" for alias in aliases for suffix in ALIASED_CORE_SUFFIXES)
        if not has_alias:
            continue
        if (
            int(row.get("score") or 0) < scope_policy_int("aliased_core_min_score", 35)
            or int(row.get("python_files") or 0) < scope_policy_int("aliased_core_min_python_files", 40)
        ):
            continue
        if index > 0 and int(candidates[0].get("score") or 0) - int(row.get("score") or 0) > scope_policy_int("aliased_core_max_gap", 8):
            continue
        if _disfavored_scope_root(path) or not (project_dir / path).is_dir():
            continue
        return dict(row)
    return None

def _library_module_scope(project_dir: Path, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if len(candidates) < 2:
        return None
    best = candidates[0]
    second = candidates[1]
    path = str(best.get("path") or "").replace("\\", "/").strip("/")
    if str(best.get("kind") or "") != "python_project_candidate":
        return None
    min_score = (
        scope_policy_int("library_root_min_score", 40)
        if path.lower() in PREFERRED_SCOPE_ROOTS
        else scope_policy_int("library_module_min_score", 80)
    )
    min_files = (
        scope_policy_int("library_root_min_python_files", 5)
        if path.lower() in PREFERRED_SCOPE_ROOTS
        else scope_policy_int("library_module_min_python_files", 20)
    )
    if int(best.get("score") or 0) < min_score or int(best.get("python_files") or 0) < min_files:
        return None
    if int(best.get("score") or 0) - int(second.get("score") or 0) < scope_policy_int("library_module_min_gap", 8):
        return None
    if _disfavored_scope_root(path) or not (project_dir / path).is_dir():
        return None
    if any(int(row.get("js_ts_files") or 0) > 0 for row in candidates[:4]):
        return None
    return dict(best)

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
        and is_python_source_ref(str(row.get("source")))
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
