"""Semantic admission for framework/plugin role-chain evidence."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .foundation_semantic_quality import evaluate_foundation_semantic_quality


_GENERIC_ADR_PREFIX = "treat "
_GENERIC_OPTION_IDS = {
    "minimal_safe_extraction",
    "contract_hardening_first",
    "full_subsystem_split",
}
_GENERIC_VERIFICATION = {
    "pytest or explicit review checklist",
    "contract test or explicit review checklist tied to the selected source target",
}


def evaluate_framework_plugin_role_semantics(
    *,
    project_report: dict[str, Any],
    architecture_decision: dict[str, Any],
    technical_spec: dict[str, Any],
    classification: dict[str, Any],
    goal: str,
    executor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score meaning and consistency, not merely artifact field presence."""
    artifacts = {
        "project_map_report": project_report,
        "architecture_decision": architecture_decision,
        "technical_spec": technical_spec,
    }
    foundation = evaluate_foundation_semantic_quality({"artifacts": artifacts})
    entrypoints = _plugin_entrypoints(project_report)
    target = str(
        dict(technical_spec.get("extraction_contract") or {}).get("candidate") or ""
    )
    target_relevant = _target_matches_entrypoint(target, entrypoints)
    content = dict(project_report.get("content") or project_report)
    scope = dict(dict(content.get("answers") or {}).get("1_scope") or {})
    purpose_text = _flatten({
        "main_task": scope.get("main_task"),
        "scenarios": scope.get("supported_scenarios"),
        "profile": scope.get("domain_profile"),
    }).lower()
    analyzer_checks = [
        _check(
            "framework_identity_is_source_backed",
            classification.get("effective_project_identity") == "framework_plugin_build"
            and bool(entrypoints),
        ),
        _check("purpose_mentions_plugin_contract", _purpose_matches_entrypoints(purpose_text, entrypoints)),
        _check(
            "identity_and_domain_are_separated",
            classification.get("project_archetype_scope") in {"project_identity", "domain"}
            or classification.get("project_archetype") == "framework_plugin_build",
        ),
        _check("evaluation_goal_is_project_specific", not _generic_probe_goal(goal)),
        _check(
            "foundation_analyzer_quality_passed",
            float(dict(foundation.get("role_scores") or {}).get("project_analyzer") or 0.0)
            >= 9.7,
        ),
    ]
    first_slice = dict(architecture_decision.get("first_slice_contract") or {})
    decision = str(architecture_decision.get("decision_summary") or "")
    options = list(architecture_decision.get("architecture_options") or [])
    architect_checks = [
        _check("selected_target_is_plugin_contract_relevant", target_relevant),
        _check("decision_summary_is_not_generic_extraction_template", _specific_decision(decision)),
        _check(
            "architecture_options_are_project_specific",
            bool(options)
            and not {str(row.get("id")) for row in options if isinstance(row, dict)}.issubset(
                _GENERIC_OPTION_IDS
            ),
        ),
        _check(
            "first_slice_is_focused",
            0 < len({str(value) for value in first_slice.get("targets") or [] if value}) <= 5,
        ),
        _check(
            "foundation_architect_quality_passed",
            float(dict(foundation.get("role_scores") or {}).get("architect") or 0.0) >= 9.7,
        ),
    ]
    spec_checks = [
        _check("selected_target_is_plugin_contract_relevant", target_relevant),
        _check("requirements_have_consistent_targets", _requirements_consistent(technical_spec, target)),
        _check("acceptance_scope_is_bounded", _acceptance_is_bounded(technical_spec, target)),
        _check("acceptance_criteria_are_not_duplicated", _acceptance_is_distinct(technical_spec)),
        _check("verification_is_executable_not_placeholder", _verification_is_concrete(technical_spec)),
        _check(
            "foundation_spec_writer_quality_passed",
            float(dict(foundation.get("role_scores") or {}).get("spec_writer") or 0.0) >= 9.7,
        ),
    ]
    role_checks = {
        "project_analyzer": analyzer_checks,
        "architect": architect_checks,
        "spec_writer": spec_checks,
    }
    role_scores = {
        role: _score(rows, ceiling=float(dict(foundation.get("role_scores") or {}).get(role) or 0.0))
        for role, rows in role_checks.items()
    }
    execution = dict(executor or {})
    development_change = (
        execution.get("patch_synthesis_status") not in {None, "verification_only"}
        and int(execution.get("patch_count") or 0) > 0
    )
    body = {
        "artifact_type": "FrameworkPluginRoleSemanticAdmission",
        "schema_version": "framework_plugin_role_semantic_admission.v1",
        "status": "passed" if min(role_scores.values(), default=0.0) >= 9.7 else "needs_work",
        "role_scores": role_scores,
        "checks": role_checks,
        "failed_checks": {
            role: [row["code"] for row in rows if not row["passed"]]
            for role, rows in role_checks.items()
            if any(not row["passed"] for row in rows)
        },
        "plugin_entrypoints": entrypoints,
        "selected_target": target,
        "development_change_evaluated": development_change,
        "foundation_semantic_quality": foundation,
    }
    return {**body, "admission_digest": _digest(body)}


def artifact_digest(value: dict[str, Any]) -> str:
    return _digest(value)


def _plugin_entrypoints(report: dict[str, Any]) -> list[str]:
    content = dict(report.get("content") or report)
    summary = dict(content.get("summary") or {})
    return sorted({
        str(value)
        for value in summary.get("entrypoints") or []
        if "[plugin:" in str(value).lower() or "entry-points" in str(value).lower()
    })


def _target_matches_entrypoint(target: str, entrypoints: list[str]) -> bool:
    target_module = _source_module(target)
    modules = [_entrypoint_module(value) for value in entrypoints]
    return bool(target_module) and any(
        module and (target_module == module or target_module.startswith(module + "."))
        for module in modules
    )


def _purpose_matches_entrypoints(text: str, entrypoints: list[str]) -> bool:
    tokens = {
        token
        for value in entrypoints
        for token in re.findall(r"[a-z][a-z0-9_-]{2,}", value.lower())
        if token not in {"plugin", "project", "pyproject", "entry", "points"}
    }
    return "plugin" in text and bool(tokens.intersection(re.findall(r"[a-z][a-z0-9_-]{2,}", text)))


def _entrypoint_module(value: str) -> str:
    target = value.split("=", 1)[-1].strip().split(":", 1)[0]
    return target.replace("/", ".").strip(". ")


def _source_module(value: str) -> str:
    path = value.split(":", 1)[0].replace("\\", "/")
    if path.startswith("src/"):
        path = path[4:]
    if path.endswith("/__init__.py"):
        path = path[: -len("/__init__.py")]
    elif path.endswith(".py"):
        path = path[:-3]
    return path.replace("/", ".").strip(".")


def _generic_probe_goal(goal: str) -> bool:
    lowered = goal.strip().lower()
    return not lowered or lowered.startswith("github full-chain probe")


def _specific_decision(value: str) -> bool:
    lowered = value.strip().lower()
    return bool(value.strip()) and not (
        lowered.startswith(_GENERIC_ADR_PREFIX) and "candidate for bounded capability extraction" in lowered
    )


def _requirements_consistent(spec: dict[str, Any], selected: str) -> bool:
    rows = [row for row in spec.get("requirements") or [] if isinstance(row, dict)]
    explicit = {str(row.get("target")) for row in rows if row.get("target")}
    mismatched_text = any(
        row.get("target") and _source_refs(str(row.get("statement") or ""))
        and str(row.get("target")) not in _source_refs(str(row.get("statement") or ""))
        for row in rows
    )
    return bool(rows) and not mismatched_text and (not explicit or explicit == {selected})


def _acceptance_is_bounded(spec: dict[str, Any], selected: str) -> bool:
    rows = [row for row in spec.get("acceptance_criteria") or [] if isinstance(row, dict)]
    sources = {
        str(row.get("source")) for row in rows
        if str(row.get("source") or "").endswith(".py") or ".py:" in str(row.get("source") or "")
    }
    return 1 <= len(rows) <= 20 and (not sources or sources == {selected})


def _acceptance_is_distinct(spec: dict[str, Any]) -> bool:
    rows = [row for row in spec.get("acceptance_criteria") or [] if isinstance(row, dict)]
    normalized = [re.sub(r"`[^`]+`", "<target>", str(row.get("criterion") or "").lower()) for row in rows]
    return bool(normalized) and len(set(normalized)) == len(normalized)


def _verification_is_concrete(spec: dict[str, Any]) -> bool:
    rows = [row for row in spec.get("acceptance_criteria") or [] if isinstance(row, dict)]
    values = [str(row.get("verification") or "").strip().lower() for row in rows]
    return bool(values) and all(value and value not in _GENERIC_VERIFICATION for value in values)


def _source_refs(value: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9_./\\-]+\.py(?::[A-Za-z0-9_.]+)?", value))


def _check(code: str, passed: bool) -> dict[str, Any]:
    return {"code": code, "passed": bool(passed)}


def _score(rows: list[dict[str, Any]], *, ceiling: float) -> float:
    score = 10.0 * sum(row["passed"] for row in rows) / max(1, len(rows))
    return round(min(score, ceiling), 2)


def _flatten(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten(item) for item in value)
    return str(value or "")


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
