"""Matching implementation for declarative architecture knowledge."""

from __future__ import annotations

import re
from typing import Any


def match_auxiliary_patterns(
    facts: dict[str, Any],
    records: list[dict[str, Any]],
    *,
    id_field: str,
    fields: tuple[str, ...],
    limit: int,
) -> list[dict[str, Any]]:
    project_text = project_text_from_facts(facts)
    rows = []
    for record in records:
        match = dict(record.get("match") or {})
        needles = strings(match.get("text_contains_any"))
        if not needles:
            continue
        negative = strings(match.get("negative_signals") or match.get("negative_contains_any"))
        blocked = [needle for needle in negative if contains_marker(needle, project_text)]
        if blocked:
            continue
        required = strings(match.get("required_contains_any"))
        if required and not any(contains_marker(needle, project_text) for needle in required):
            continue
        found = [needle for needle in needles if contains_marker(needle, project_text)]
        min_score = int(match.get("min_score") or 1)
        if len(found) < min_score:
            continue
        row = {
            id_field: record.get(id_field),
            "matched_because": found[:5],
            "score": len(found),
        }
        for field in fields:
            row[field] = record.get(field)
        rows.append(row)
    return sorted(rows, key=lambda item: (-int(item["score"]), str(item.get(id_field))))[:limit]


def match_score(facts: dict[str, Any], rule: dict[str, Any]) -> tuple[int, list[str]]:
    match = dict(rule.get("match") or {})
    if not match:
        return 1, ["fallback rule"]
    score = 0
    reasons: list[str] = []
    framework_text = " ".join(str(item) for item in facts.get("frameworks", [])).lower()
    project_text = project_text_from_facts(facts)
    source_text = project_source_text(facts)
    project_name = project_name_from_root(str(facts.get("root") or "")).lower()
    input_text = " ".join(str(item) for item in facts.get("inputs", [])).lower()
    domain_profile = dict(facts.get("domain_profile") or {})
    domain_kind = str(domain_profile.get("kind") or "").lower()
    rule_kind = str(rule.get("archetype") or rule.get("rule_id") or "").lower()
    confident_domain_match = bool(rule_kind == domain_kind and domain_profile.get("evidence")) and float(domain_profile.get("confidence") or 0.0) >= 0.6
    if confident_domain_match:
        score += 160
        reasons.append(f"confident domain profile is {domain_kind}")

    negative_domain_kinds = strings(match.get("negative_domain_profile_kinds"))
    if negative_domain_kinds and domain_kind in {item.lower() for item in negative_domain_kinds}:
        return 0, []

    negative = strings(match.get("negative_contains_any") or match.get("negative_signals"))
    blocked = [needle for needle in negative if contains_marker(needle, project_text)]
    if blocked:
        return 0, []

    required = strings(match.get("required_contains_any"))
    if required:
        found = [needle for needle in required if contains_marker(needle, project_text)]
        if not found:
            return 0, []
        score += 40 + len(found) * 5
        reasons.append("required text contains " + ", ".join(found[:3]))

    required_all = strings(match.get("required_contains_all"))
    if required_all:
        missing = [needle for needle in required_all if not contains_marker(needle, project_text)]
        if missing:
            return 0, []
        score += 20 + len(required_all) * 5
        reasons.append("required text contains all " + ", ".join(required_all[:3]))

    project_names = strings(match.get("project_name_contains_any"))
    project_name_matched = False
    domain_profile_matched = False
    if project_names:
        found = [needle for needle in project_names if contains_marker(needle, project_name)]
        if found:
            project_name_matched = True
            score += 60 + len(found) * 10
            reasons.append("project name contains " + ", ".join(found[:3]))
    if match.get("require_project_name_match") and not project_name_matched:
        return 0, []

    required_sources = strings(match.get("required_source_contains_any"))
    source_evidence_matched = False
    if required_sources:
        found = [needle for needle in required_sources if contains_marker(needle, source_text)]
        if not found and not project_name_matched:
            return 0, []
        if found:
            source_evidence_matched = True
            score += 55 + len(found) * 5
            reasons.append("source targets contain " + ", ".join(found[:3]))

    domain_kinds = strings(match.get("domain_profile_kind") or match.get("domain_profile_kinds"))
    if domain_kinds:
        found = [needle for needle in domain_kinds if needle.lower() == domain_kind]
        if not found and not (project_name_matched or source_evidence_matched):
            return 0, []
        if found:
            domain_profile_matched = True
            score += 180 + len(found) * 10
            reasons.append("domain profile is " + ", ".join(found[:3]))
    anchored = project_name_matched or domain_profile_matched or source_evidence_matched or confident_domain_match

    frameworks = strings(match.get("framework_contains_any"))
    if frameworks:
        found = [needle for needle in frameworks if contains_marker(needle, framework_text)]
        if not found and not anchored:
            return 0, []
        if found:
            score += 40 + len(found) * 5
            reasons.append("framework contains " + ", ".join(found[:3]))

    text_needles = strings(match.get("text_contains_any"))
    if text_needles:
        found = [needle for needle in text_needles if contains_marker(needle, project_text)]
        if not found and not anchored:
            return 0, []
        if found:
            score += 30 + len(found) * 3
            reasons.append("project text contains " + ", ".join(found[:4]))

    input_needles = strings(match.get("input_contains_any"))
    if input_needles:
        found = [needle for needle in input_needles if contains_marker(needle, input_text)]
        if not found and not anchored:
            return 0, []
        if found:
            score += 15 + len(found) * 3
            reasons.append("inputs contain " + ", ".join(found[:3]))

    routes_min = match.get("routes_min")
    if routes_min is not None:
        routes = int(facts.get("routes_count") or 0)
        if routes < int(routes_min):
            return 0, []
        score += 10
        reasons.append(f"routes >= {routes_min}")
    min_score = int(match.get("min_score") or 0)
    if min_score and score < min_score:
        return 0, []
    return score, reasons


def project_text_from_facts(facts: dict[str, Any]) -> str:
    runtime = dict(facts.get("runtime_extraction", {}))
    parts = (
        [project_name_from_root(str(facts.get("root") or ""))]
        + [str(item) for item in facts.get("frameworks", [])]
        + [str(item) for item in facts.get("inputs", [])]
        + [str(item) for item in facts.get("outputs", [])]
        + facts.get("central", [])
        + facts.get("broad", [])
        + facts.get("capabilities", [])
        + facts.get("domain_anchors", [])
        + [str(item) for item in facts.get("routes", [])]
        + facts.get("entrypoints", [])
        + facts.get("scenarios", [])
        + [str(item) for item in facts.get("schemas", [])]
        + [str(item) for item in facts.get("weak_contracts", [])]
        + [str(item) for item in facts.get("errors", [])]
        + [str(item) for item in facts.get("handlers", [])]
        + [str(item) for item in facts.get("loop", [])]
        + [str(item) for item in facts.get("risks", [])]
        + [str(row) for row in facts.get("subsystems", [])]
        + [str(row) for row in facts.get("hotspots", [])]
        + [str(row) for row in facts.get("boundaries", [])]
        + [target_text(row) for row in runtime.get("process_boundary", [])]
        + [str(row) for row in runtime.get("orchestrators", [])]
        + [str(facts.get("task") or "")]
    )
    return " ".join(str(item) for item in parts).lower()


def contains_marker(marker: str, text: str) -> bool:
    needle = marker.strip().lower()
    if not needle:
        return False
    if any(character in needle for character in "/\\.:"):
        return needle in text.lower()
    tokens = [re.escape(token) for token in re.split(r"[\s_-]+", needle) if token]
    pattern = r"(?<![a-z0-9])" + r"[\s_-]+".join(tokens) + r"(?![a-z0-9])"
    return re.search(pattern, text.lower()) is not None


def project_source_text(facts: dict[str, Any]) -> str:
    runtime = dict(facts.get("runtime_extraction", {}))
    parts = (
        [project_name_from_root(str(facts.get("root") or ""))]
        + list(facts.get("frameworks", []))
        + list(facts.get("central", []))
        + list(facts.get("broad", []))
        + list(facts.get("capabilities", []))
        + list(facts.get("domain_anchors", []))
        + list(facts.get("entrypoints", []))
        + [target_text(row) for row in runtime.get("process_boundary", [])]
        + list(runtime.get("orchestrators", []))
    )
    return " ".join(str(item) for item in parts).lower()


def project_name_from_root(root: str) -> str:
    if not root:
        return ""
    clean = root.replace("\\", "/").rstrip("/")
    return clean.rsplit("/", 1)[-1]


def target_text(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(item.get("target") or item.get("capability") or "")
    return ""


def strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if value in (None, "", []):
        return []
    return [str(value)]
