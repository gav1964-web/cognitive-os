"""Promote clean executable modules into source-backed process boundaries."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from runtime.python_parser_compatibility import parse_compatible_source
from runtime.python_source_files import is_python_source_ref
from runtime.source_target_policy import is_context_only_implementation_target, load_role_source_policy


def enrich_module_script_readiness(project_report: dict[str, Any]) -> dict[str, Any]:
    policy = _policy()
    if not policy.get("enabled") or not _eligible_report(project_report, policy):
        return project_report
    answers = dict(project_report.get("answers") or {})
    readiness = dict(answers.get("6_runtime_extraction_readiness") or {})
    plan = dict(readiness.get("minimal_extraction_plan") or {})
    if plan.get("capabilities_to_extract") or not _has_required_blocker(plan, policy):
        return project_report
    candidates = _module_candidates(project_report, policy)
    if not candidates:
        return project_report
    plan["capabilities_to_extract"] = candidates
    plan["contracts_to_write"] = [row["first_contract"] for row in candidates]
    plan["blocked_by"] = []
    readiness["minimal_extraction_plan"] = plan
    if len(list(readiness.get("data_lifecycle") or [])) < 3:
        primary = candidates[0]["capability"]
        readiness["data_lifecycle"] = [
            {"stage": "input", "shape": "module inputs and environment", "evidence": primary},
            {"stage": "execution", "shape": "top-level process boundary", "evidence": primary},
            {"stage": "output", "shape": "declared artifacts and side effects", "evidence": primary},
        ]
    boundaries = list(readiness.get("process_boundary_candidates") or [])
    readiness["process_boundary_candidates"] = [
        *[
            {
                "target": row["capability"],
                "reasons": ["top_level_execution", "module_side_effect_boundary"],
                "policy": "extract a testable main/run function while preserving CLI behavior",
            }
            for row in candidates
        ],
        *boundaries,
    ][:12]
    answers["6_runtime_extraction_readiness"] = readiness
    return {**project_report, "answers": answers}


def _policy() -> dict[str, Any]:
    source = load_role_source_policy().get("implementation_target_policy") or {}
    return dict(dict(source).get("module_script_boundary") or {})


def _eligible_report(project_report: dict[str, Any], policy: dict[str, Any]) -> bool:
    health = dict(project_report.get("source_health") or {})
    allowed_health = {str(item) for item in list(policy.get("allowed_source_health") or [])}
    allowed_shapes = {str(item) for item in list(policy.get("allowed_project_shapes") or [])}
    status = str(health.get("status") or "")
    compatibility_only_noise = bool(
        status == "noisy"
        and policy.get("allow_parser_compatibility_noise")
        and int(health.get("parser_incompatibility_count") or 0) > 0
        and int(health.get("syntax_error_count") or 0) == 0
        and int(health.get("artifact_noise_signal_count") or 0) == 0
    )
    return (
        (status in allowed_health or compatibility_only_noise)
        and str(health.get("project_shape") or "") in allowed_shapes
        and int(health.get("inaccessible_count") or 0) == 0
    )


def _has_required_blocker(plan: dict[str, Any], policy: dict[str, Any]) -> bool:
    required = str(policy.get("required_blocker") or "no_safe_python_candidate")
    blocked = plan.get("blocked_by") or []
    blockers = [blocked] if isinstance(blocked, str) else list(blocked)
    return required in {str(item) for item in blockers}


def _module_candidates(project_report: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    summary = dict(project_report.get("summary") or {})
    root = Path(str(summary.get("root") or project_report.get("root") or ""))
    entrypoints = list(dict(project_report.get("answers") or {}).get("2_execution", {}).get("entrypoints") or [])
    entrypoints = entrypoints or list(summary.get("entrypoints") or [])
    entrypoints = entrypoints or _active_core_sources(project_report)
    max_entries = max(1, int(policy.get("max_entrypoint_candidates") or 1))
    if not root.is_dir() or not entrypoints:
        return []
    rows = []
    for source in entrypoints[:max_entries]:
        normalized = str(source or "").replace("\\", "/")
        if not _safe_module_source(root, normalized):
            continue
        rows.append(
            {
                "capability": normalized,
                "reason": str(policy.get("reason") or "executable module boundary"),
                "candidate_kind": str(policy.get("candidate_kind") or "module_script_process_boundary"),
                "first_contract": f"{normalized}: preserve CLI inputs, outputs, failures, and side effects behind main/run",
            }
        )
    limit = max(1, int(policy.get("candidate_limit") or 1))
    return rows[:limit]


def _active_core_sources(project_report: dict[str, Any]) -> list[str]:
    answers = dict(project_report.get("answers") or {})
    readiness = dict(answers.get("6_runtime_extraction_readiness") or {})
    strata = dict(readiness.get("source_strata") or {})
    return [str(row.get("path") or "") for row in list(strata.get("active_core") or []) if isinstance(row, dict)]


def _safe_module_source(root: Path, source: str) -> bool:
    if not is_python_source_ref(source) or ":" in source or is_context_only_implementation_target(source):
        return False
    path = (root / source).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return False
    if not path.is_file() or path.name == "__init__.py":
        return False
    try:
        tree, _ = parse_compatible_source(path.read_text(encoding="utf-8", errors="replace"), path.as_posix())
    except (OSError, SyntaxError):
        return False
    return any(_executable_statement(node) for node in tree.body)


def _executable_statement(node: ast.stmt) -> bool:
    if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Pass)):
        return False
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
        return False
    return any(isinstance(child, ast.Call) for child in ast.walk(node)) or isinstance(
        node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try, ast.Raise, ast.Match)
    )
