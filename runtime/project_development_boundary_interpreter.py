"""Interpret staged project-development boundary knowledge without executing KB code."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILES = ROOT / "knowledge" / "role_knowledge" / "project_development_boundary_profiles.json"
DEFAULT_CONTRASTS = ROOT / "knowledge" / "role_knowledge" / "project_development_source_contrasts.json"
DEFAULT_EXCEPTION_PICKLE_PATTERNS = (
    ROOT / "knowledge" / "role_knowledge" / "exception_pickle_reconstruction_patterns.json"
)
ALLOWED_OPERATORS = {"eq", "gt", "suffix"}


class ProjectDevelopmentBoundaryKnowledgeError(RuntimeError):
    """Raised when boundary knowledge cannot be interpreted safely."""


@lru_cache(maxsize=4)
def load_boundary_profiles(path: str | None = None) -> dict[str, Any]:
    payload = json.loads(Path(path or DEFAULT_PROFILES).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "project_development_boundary_profiles.v1":
        raise ProjectDevelopmentBoundaryKnowledgeError("boundary profile schema mismatch")
    profiles = payload.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        raise ProjectDevelopmentBoundaryKnowledgeError("boundary profiles must be non-empty")
    ids: set[str] = set()
    fallbacks = 0
    for raw in profiles:
        profile = dict(raw or {})
        profile_id = str(profile.get("id") or "")
        if not profile_id or profile_id in ids:
            raise ProjectDevelopmentBoundaryKnowledgeError(f"invalid boundary profile id: {profile_id}")
        ids.add(profile_id)
        if profile.get("status") not in {"staged", "active"}:
            raise ProjectDevelopmentBoundaryKnowledgeError(f"invalid boundary profile status: {profile_id}")
        if profile.get("fallback") is True:
            fallbacks += 1
        else:
            _validate_expression(dict(profile.get("match") or {}), profile_id)
        hypothesis = dict(profile.get("hypothesis") or {})
        for field in ("status", "confidence", "experiment_kind", "strategy"):
            if field not in hypothesis:
                raise ProjectDevelopmentBoundaryKnowledgeError(f"profile {profile_id} lacks hypothesis.{field}")
        confidence = float(hypothesis.get("confidence") or 0.0)
        if not 0.0 <= confidence <= 1.0:
            raise ProjectDevelopmentBoundaryKnowledgeError(f"invalid confidence: {profile_id}")
        if not isinstance(profile.get("required_evidence"), list):
            raise ProjectDevelopmentBoundaryKnowledgeError(f"profile {profile_id} lacks required_evidence")
        for rule in dict(profile.get("requirement_rules") or {}).values():
            row = dict(rule or {})
            for key in ("primary_match", "contrast_match"):
                if key in row:
                    _validate_expression(dict(row[key]), profile_id)
    if fallbacks != 1:
        raise ProjectDevelopmentBoundaryKnowledgeError("boundary knowledge requires exactly one fallback")
    return payload


@lru_cache(maxsize=4)
def load_source_contrasts(path: str | None = None) -> dict[str, Any]:
    payload = json.loads(Path(path or DEFAULT_CONTRASTS).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "project_development_source_contrasts.v1":
        raise ProjectDevelopmentBoundaryKnowledgeError("source contrast schema mismatch")
    rows = payload.get("contrasts")
    if not isinstance(rows, list) or not rows:
        raise ProjectDevelopmentBoundaryKnowledgeError("source contrasts must be non-empty")
    ids: set[str] = set()
    for raw in rows:
        row = dict(raw or {})
        contrast_id = str(row.get("contrast_id") or "")
        if not contrast_id or contrast_id in ids:
            raise ProjectDevelopmentBoundaryKnowledgeError(f"invalid source contrast id: {contrast_id}")
        ids.add(contrast_id)
        for field in ("hypothesis_kind", "project_path", "target", "validation_report", "expected_facts"):
            if not row.get(field):
                raise ProjectDevelopmentBoundaryKnowledgeError(f"contrast {contrast_id} lacks {field}")
        digest = str(row.get("sha256") or "")
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest.lower()):
            raise ProjectDevelopmentBoundaryKnowledgeError(f"invalid source contrast digest: {contrast_id}")
        if dict(row.get("provenance") or {}).get("kb_promotion_evidence") is not False:
            raise ProjectDevelopmentBoundaryKnowledgeError(f"contrast may not promote KB: {contrast_id}")
    return payload


@lru_cache(maxsize=4)
def load_exception_pickle_patterns(path: str | None = None) -> dict[str, Any]:
    source = Path(path or DEFAULT_EXCEPTION_PICKLE_PATTERNS)
    if not source.exists():
        return {"schema_version": "exception_pickle_reconstruction_patterns.v1", "status": "absent"}
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "exception_pickle_reconstruction_patterns.v1":
        raise ProjectDevelopmentBoundaryKnowledgeError("exception pickle pattern schema mismatch")
    if payload.get("status") not in {"active", "absent"}:
        raise ProjectDevelopmentBoundaryKnowledgeError("invalid exception pickle pattern lifecycle")
    operator = dict(payload.get("operator") or {})
    if payload.get("status") == "active":
        required = {
            "id": "preserve_exception_constructor_reconstruction",
            "status": "validated_active",
            "hypothesis_kind": "exception_pickle_reconstruction_boundary",
            "reconstruction_method": "__reduce__",
            "state_strategy": "reuse_direct_assignments",
        }
        for field, expected in required.items():
            if operator.get(field) != expected:
                raise ProjectDevelopmentBoundaryKnowledgeError(
                    f"invalid exception pickle operator.{field}"
                )
        safety = dict(payload.get("safety") or {})
        if safety.get("source_apply_allowed") is not False or safety.get(
            "automatic_runtime_mutation_allowed"
        ) is not False:
            raise ProjectDevelopmentBoundaryKnowledgeError("unsafe exception pickle pattern policy")
    return payload


def interpret_boundary(
    context: dict[str, Any],
    *,
    profiles: dict[str, Any] | None = None,
    active_patterns: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = profiles or load_boundary_profiles()
    active = active_patterns if active_patterns is not None else load_exception_pickle_patterns()
    rows = sorted(
        (dict(row) for row in payload["profiles"]),
        key=lambda row: int(row.get("priority") or 0),
        reverse=True,
    )
    matched = next(
        (row for row in rows if row.get("fallback") is not True and evaluate_expression(row["match"], context)),
        None,
    )
    profile = matched or next(row for row in rows if row.get("fallback") is True)
    return _apply_active_pattern_overlay(dict(profile), active)


def profile_for_hypothesis(kind: str, *, profiles: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = profiles or load_boundary_profiles()
    for raw in payload["profiles"]:
        profile = dict(raw)
        if str(profile.get("hypothesis_kind") or profile.get("id")) == kind and profile.get("fallback") is not True:
            return profile
    return {}


def contrast_for_hypothesis(kind: str, *, contrasts: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = contrasts or load_source_contrasts()
    matches = [dict(row) for row in payload["contrasts"] if row.get("hypothesis_kind") == kind]
    return matches[0] if len(matches) == 1 else {}


def _apply_active_pattern_overlay(profile: dict[str, Any], active: dict[str, Any]) -> dict[str, Any]:
    if profile.get("id") != "exception_pickle_reconstruction_boundary":
        return profile
    operator = dict(active.get("operator") or {})
    if (
        active.get("status") != "active"
        or operator.get("status") != "validated_active"
        or operator.get("hypothesis_kind") != profile.get("id")
    ):
        return profile
    profile["status"] = "active"
    profile["active_kb_operator"] = operator
    evidence = dict(profile.get("evidence_state") or {})
    evidence.update({
        "promotion_ready": True,
        "promotion_authority": active.get("promotion_authority"),
        "active_catalog": "exception_pickle_reconstruction_patterns",
    })
    profile["evidence_state"] = evidence
    hypothesis = dict(profile.get("hypothesis") or {})
    hypothesis["status"] = "proposed"
    hypothesis["confidence"] = max(float(hypothesis.get("confidence") or 0.0), 0.97)
    profile["hypothesis"] = hypothesis
    return profile


def evaluate_requirement(
    name: str,
    *,
    profile: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    rule = dict(dict(profile.get("requirement_rules") or {}).get(name) or {})
    kind = str(rule.get("kind") or "")
    authority = str(rule.get("authority") or "unknown_requirement")
    if kind == "source_backed":
        return {"satisfied": dict(context.get("primary_facts") or {}).get("source_backed") is True, "authority": authority}
    if kind == "target_identity":
        satisfied = bool(context.get("target")) and context.get("target") == context.get("origin_target")
        return {"satisfied": satisfied, "authority": authority}
    if kind == "paired_shape":
        primary = evaluate_expression(dict(rule.get("primary_match") or {}), context)
        contrast = evaluate_expression(dict(rule.get("contrast_match") or {}), context)
        satisfied = primary and contrast
        return {
            "satisfied": satisfied,
            "authority": authority,
            "source_backed_negative": primary,
            "source_backed_positive": contrast,
            "bounded_implementation_evidence": satisfied and rule.get("bounded_implementation_evidence") is True,
            "kb_promotion_evidence": False,
        }
    return {"satisfied": False, "authority": authority}


def evaluate_expression(expression: dict[str, Any], context: dict[str, Any]) -> bool:
    if "all" in expression:
        values = expression.get("all")
        return isinstance(values, list) and bool(values) and all(evaluate_expression(dict(row), context) for row in values)
    if "any" in expression:
        values = expression.get("any")
        return isinstance(values, list) and bool(values) and any(evaluate_expression(dict(row), context) for row in values)
    source = context.get(str(expression.get("source") or ""))
    candidates = source if isinstance(source, list) else [source]
    where = expression.get("where")
    if where:
        candidates = [value for value in candidates if _evaluate_predicate(dict(where), value)]
    return any(_evaluate_predicate(expression, value) for value in candidates)


def _evaluate_predicate(predicate: dict[str, Any], value: Any) -> bool:
    actual = _resolve_path(value, str(predicate.get("path") or ""))
    expected = predicate.get("value")
    operator = str(predicate.get("operator") or "")
    if operator == "eq":
        return actual == expected
    if operator == "gt":
        try:
            return float(actual) > float(expected)
        except (TypeError, ValueError):
            return False
    if operator == "suffix":
        return str(actual or "").endswith(str(expected or ""))
    return False


def _resolve_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split(".") if path else []:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _validate_expression(expression: dict[str, Any], profile_id: str) -> None:
    logical = [key for key in ("all", "any") if key in expression]
    if logical:
        if len(logical) != 1 or not isinstance(expression[logical[0]], list) or not expression[logical[0]]:
            raise ProjectDevelopmentBoundaryKnowledgeError(f"invalid logical expression: {profile_id}")
        for row in expression[logical[0]]:
            if not isinstance(row, dict):
                raise ProjectDevelopmentBoundaryKnowledgeError(f"invalid predicate: {profile_id}")
            _validate_expression(row, profile_id)
        return
    if expression.get("operator") not in ALLOWED_OPERATORS or not expression.get("source") or not expression.get("path"):
        raise ProjectDevelopmentBoundaryKnowledgeError(f"invalid predicate: {profile_id}")
    where = expression.get("where")
    if where is not None:
        if not isinstance(where, dict) or where.get("operator") not in ALLOWED_OPERATORS or not where.get("path"):
            raise ProjectDevelopmentBoundaryKnowledgeError(f"invalid selector: {profile_id}")
