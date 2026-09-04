"""Build the authoritative early project recognition and routing decision."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from .pilot_profile import load_pilot_profile
from .role_project_type_evaluation import classify_project_case


CONFIDENCE_BY_SOURCE = {
    "explicit": 0.98,
    "contract_family_precedence": 0.96,
    "entrypoint_identity_precedence": 0.92,
    "evidence_match": 0.88,
    "identity_override": 0.78,
    "fallback_authoritative_unmatched": 0.35,
    "fallback": 0.2,
}
MIN_ANALYZER_CONFIDENCE = 0.7


def recognize_project(
    *,
    project: str,
    project_report: dict[str, Any],
    classification: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    project_dir: Path | None = None,
    change_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one fail-closed recognition decision before downstream roles run."""
    classified = classification or classify_project_case({
        "project": project,
        "artifacts": {"project_map_report": project_report},
    })
    source = str(classified.get("classification_source") or "fallback")
    stratum = str(classified.get("project_stratum") or "unknown_new_archetype")
    risks = sorted({str(value) for value in classified.get("risk_profiles") or []})
    analyzer_profile = _analyzer_domain_profile(project_report)
    analyzer_confidence = _optional_confidence(analyzer_profile.get("confidence"))
    reasons: list[str] = []
    if stratum == "unknown_new_archetype":
        status = "unknown"
        reasons.append("no_configured_project_stratum_matched")
    elif classified.get("classification_conflict"):
        status = "ambiguous"
        reasons.append("authoritative_evidence_conflicts_with_project_identity")
    elif not risks or risks == ["unspecified"]:
        status = "ambiguous"
        reasons.append("risk_profile_not_resolved")
    elif (
        source == "evidence_match"
        and analyzer_confidence is not None
        and analyzer_confidence < MIN_ANALYZER_CONFIDENCE
    ):
        status = "ambiguous"
        reasons.append("project_analyzer_confidence_below_threshold")
    else:
        status = "recognized"

    confidence = CONFIDENCE_BY_SOURCE.get(source, 0.5)
    if source == "evidence_match" and analyzer_confidence is not None:
        confidence = min(confidence, analyzer_confidence)
    if status == "ambiguous":
        confidence = min(confidence, 0.65)
    elif status == "unknown":
        confidence = min(confidence, 0.35)

    route = _role_route(status)
    pilot = _pilot_route(
        classified,
        status=status,
        profile=profile,
        project_dir=project_dir,
        change_request=change_request,
    )
    return {
        "artifact_type": "ProjectRecognitionDecision",
        "schema_version": "project_recognition.v1",
        "status": status,
        "project": project,
        "confidence": confidence,
        "classification": classified,
        "evidence": {
            "classification_source": source,
            "matched_markers": list(classified.get("matched_markers") or []),
            "project_archetype": classified.get("project_archetype"),
            "project_archetype_scope": classified.get("project_archetype_scope"),
            "effective_project_identity": classified.get("effective_project_identity"),
            "project_analyzer_confidence": analyzer_confidence,
            "project_analyzer_evidence": list(analyzer_profile.get("evidence") or []),
            "contract_family": classified.get("contract_family"),
            "project_shape": classified.get("project_shape"),
        },
        "ambiguity_reasons": reasons,
        "role_route": route,
        "pilot_route": pilot,
        "authority": "project_analyzer_recognition_gate",
    }


def _analyzer_domain_profile(project_report: dict[str, Any]) -> dict[str, Any]:
    answers = dict(project_report.get("answers") or {})
    scope = dict(answers.get("1_scope") or answers.get("scope") or {})
    return dict(scope.get("domain_profile") or project_report.get("domain_profile") or {})


def _optional_confidence(value: Any) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    return max(0.0, min(1.0, float(value)))


def attach_project_recognition(
    project_report: dict[str, Any], recognition: dict[str, Any]
) -> dict[str, Any]:
    """Expose recognition as immutable input context for every later role."""
    return {
        **project_report,
        "project_recognition": recognition,
        "project_classification": dict(recognition.get("classification") or {}),
    }


def _role_route(status: str) -> dict[str, Any]:
    if status == "recognized":
        return {"status": "configured_role_chain", "roles": [
            "architect", "spec_writer", "implementer", "tester", "reviewer",
        ]}
    if status == "unknown":
        return {"status": "unknown_project_lifecycle", "roles": [
            "project_analyzer", "researcher",
        ]}
    return {"status": "recognition_review", "roles": [
        "project_analyzer", "architect", "researcher",
    ]}


def _pilot_route(
    classification: dict[str, Any],
    *,
    status: str,
    profile: dict[str, Any] | None,
    project_dir: Path | None = None,
    change_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = profile or load_pilot_profile()
    stratum = str(classification.get("project_stratum") or "unknown_new_archetype")
    risks = {str(value) for value in classification.get("risk_profiles") or []}
    prohibited = risks & {str(value) for value in policy.get("prohibited_risk_profiles") or []}
    reasons = []
    if status != "recognized":
        reasons.append(f"recognition_status:{status}")
    if stratum not in {str(value) for value in policy.get("allowed_project_strata") or []}:
        reasons.append("project_stratum_allowed")
    if prohibited:
        reasons.append("risk_profile_allowed")
    scoped = _target_scoped_admission(
        project_dir=project_dir,
        change_request=change_request or {},
        prohibited=prohibited,
        policy=policy,
    )
    if reasons == ["risk_profile_allowed"] and scoped.get("status") == "admitted":
        return {
            "profile_id": policy.get("profile_id"),
            "status": "eligible_for_full_chain",
            "blocking_reasons": [],
            "prohibited_risks": sorted(prohibited),
            "scope": "authoritative_failure_target",
            "target_scope_admission": scoped,
        }
    return {
        "profile_id": policy.get("profile_id"),
        "status": "eligible_for_full_chain" if not reasons else "analysis_only_stop",
        "blocking_reasons": reasons,
        "prohibited_risks": sorted(prohibited),
        "target_scope_admission": scoped,
    }


def _target_scoped_admission(
    *,
    project_dir: Path | None,
    change_request: dict[str, Any],
    prohibited: set[str],
    policy: dict[str, Any],
) -> dict[str, Any]:
    scoped_policy = dict(policy.get("target_scoped_admission") or {})
    if not scoped_policy.get("enabled"):
        return {"status": "not_admitted", "reason": "target_scoped_admission_disabled"}
    allowed_risks = {str(value) for value in scoped_policy.get("waivable_project_risks") or []}
    if not prohibited or not prohibited.issubset(allowed_risks):
        return {"status": "not_admitted", "reason": "project_risk_not_waivable"}
    if project_dir is None or change_request.get("authority") != "failing_contract_test":
        return {"status": "not_admitted", "reason": "authoritative_target_missing"}
    if int(change_request.get("repeat_count") or 0) < int(scoped_policy.get("minimum_repeat_count") or 2):
        return {"status": "not_admitted", "reason": "failure_not_repeated"}
    target = str(change_request.get("target") or "")
    path_text, separator, symbol = target.partition(":")
    if not separator or not path_text.endswith(".py") or not symbol:
        return {"status": "not_admitted", "reason": "target_invalid"}
    root = project_dir.resolve()
    source = (root / path_text).resolve()
    try:
        source.relative_to(root)
    except ValueError:
        return {"status": "not_admitted", "reason": "target_outside_project"}
    function = _target_function(source, symbol)
    if function is None:
        return {"status": "not_admitted", "reason": "target_function_unresolved"}
    forbidden_calls = {str(value) for value in scoped_policy.get("forbidden_call_names") or []}
    observed = sorted({
        name
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        for name in [_call_name(node.func)]
        if name and _is_forbidden_target_call(node, name, forbidden_calls)
    })
    if observed:
        return {
            "status": "not_admitted",
            "reason": "target_has_prohibited_direct_effects",
            "observed_forbidden_calls": observed,
        }
    if any(isinstance(node, (ast.Global, ast.Nonlocal)) for node in ast.walk(function)):
        return {"status": "not_admitted", "reason": "target_mutates_nonlocal_state"}
    return {
        "status": "admitted",
        "authority": "repeated_failure_target_ast_scope",
        "target": target,
        "waived_project_risks": sorted(prohibited),
        "source_apply_allowed": False,
        "direct_forbidden_effect_count": 0,
    }


def _is_forbidden_target_call(
    node: ast.Call, name: str, forbidden_calls: set[str]
) -> bool:
    leaf = name.rsplit(".", 1)[-1]
    if name not in forbidden_calls and leaf not in forbidden_calls:
        return False
    if leaf != "open":
        return True
    mode: ast.expr | None = node.args[1] if len(node.args) > 1 else None
    if mode is None:
        mode = next(
            (keyword.value for keyword in node.keywords if keyword.arg == "mode"),
            None,
        )
    if mode is None:
        return True
    return not (
        isinstance(mode, ast.Constant)
        and isinstance(mode.value, str)
        and mode.value in {"r", "rt", "rb"}
    )


def _target_function(source: Path, symbol: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    try:
        tree = ast.parse(source.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return None
    current: list[ast.stmt] = list(tree.body)
    found: ast.AST | None = None
    for part in symbol.split("."):
        found = next(
            (
                node for node in current
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == part
            ),
            None,
        )
        if found is None:
            return None
        current = list(found.body) if hasattr(found, "body") else []
    return found if isinstance(found, (ast.FunctionDef, ast.AsyncFunctionDef)) else None


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""
