"""Knowledge-backed domain profile matching."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def infer_knowledge_profile(
    searchable: str,
    source_searchable: str,
    authoritative_searchable: str,
    root_docs_searchable: str,
    summary: dict[str, Any],
) -> dict[str, Any] | None:
    best: tuple[int, dict[str, Any], list[str]] | None = None
    for rule in _load_project_archetypes().get("records", []):
        if not isinstance(rule, dict):
            continue
        score, evidence = _score_rule(
            rule, searchable, source_searchable,
            authoritative_searchable, root_docs_searchable, summary,
        )
        minimum = int(dict(rule.get("match") or {}).get("min_score") or 1)
        if score < minimum:
            continue
        rank = _identity_rank(evidence) * 10000 + score + int(rule.get("priority") or 0)
        if best is None or rank > best[0]:
            best = (rank, rule, evidence)
    if best is None:
        return None
    _, rule, evidence = best
    strong = ("matched root purpose markers:", "matched source contract markers:")
    evidence_units = sum(2 if item.startswith(strong) else 1 for item in evidence)
    return {
        "kind": str(rule.get("archetype") or rule.get("rule_id") or "generic"),
        "confidence": round(min(0.98, 0.55 + min(evidence_units, 5) * 0.08), 2),
        "evidence": evidence,
        "evidence_scope": "project_identity" if _identity_rank(evidence) else "internal_capability",
        "transport": _transport(summary),
        "knowledge_rule": rule.get("rule_id"),
        "label": rule.get("label"),
        "purpose_summary": rule.get("purpose_summary"),
        "scenario_summary": _strings(rule.get("scenario_summary"))[:6],
        "input_summary": _strings(rule.get("input_summary"))[:8],
        "output_summary": _strings(rule.get("output_summary"))[:8],
        "target_markers": _strings(dict(rule.get("first_slice") or {}).get("targets_prefer"))[:12],
    }


def _identity_rank(evidence: list[str]) -> int:
    if any(item.startswith(("matched project name:", "matched source contract markers:")) for item in evidence):
        return 2
    if any(item.startswith("matched root purpose markers:") for item in evidence):
        return 1
    return 0


def _score_rule(
    rule: dict[str, Any], searchable: str, source_searchable: str,
    authoritative_searchable: str, root_docs_searchable: str,
    summary: dict[str, Any],
) -> tuple[int, list[str]]:
    match = dict(rule.get("match") or {})
    root = str(summary.get("root") or "").replace("\\", "/").rstrip("/").lower()
    project_name = root.rsplit("/", 1)[-1] if root else ""
    name_hits = [item for item in _strings(match.get("project_name_contains_any")) if _contains(item, project_name)]
    purpose_hits = [item for item in _strings(match.get("purpose_contains_any")) if _contains(item, root_docs_searchable)]
    negative = _strings(match.get("negative_contains_any"))
    if negative and any(_contains(item, searchable) for item in negative):
        if not (match.get("project_name_overrides_negative") and name_hits):
            return 0, []
    required = _strings(match.get("required_contains_any"))
    if required and not (purpose_hits or any(_contains(item, authoritative_searchable) for item in required)):
        return 0, []
    required_all = _strings(match.get("required_contains_all"))
    if required_all and not all(_contains(item, searchable) for item in required_all):
        return 0, []
    required_source = _strings(match.get("required_source_contains_any"))
    source_hits = [item for item in required_source if _contains(item, source_searchable)]
    if required_source and not source_hits:
        return 0, []
    source_all = _strings(match.get("required_source_contains_all"))
    if source_all and not all(_contains(item, source_searchable) for item in source_all):
        return 0, []
    if match.get("require_project_name_match") and not name_hits:
        return 0, []
    if match.get("require_project_name_or_purpose_match") and not (name_hits or purpose_hits):
        return 0, []

    score, evidence = 0, []
    score, evidence = _add_hits(score, evidence, name_hits, 60, 10, "matched project name: ")
    score, evidence = _add_hits(score, evidence, purpose_hits, 100, 5, "matched root purpose markers: ")
    text_hits = [item for item in _strings(match.get("text_contains_any")) if _contains(item, searchable)]
    score, evidence = _add_hits(score, evidence, text_hits, 30, 3, "matched text markers: ")
    score, evidence = _add_hits(score, evidence, source_hits, 30, 2, "matched source markers: ")
    score, evidence = _add_hits(score, evidence, source_all, 80, 5, "matched source contract markers: ")
    frameworks = {str(item).lower() for item in summary.get("frameworks", [])}
    framework_hits = [item for item in _strings(match.get("framework_contains_any")) if item.lower() in frameworks]
    score, evidence = _add_hits(score, evidence, framework_hits, 40, 5, "matched frameworks: ")
    routes_min = match.get("routes_min")
    if routes_min is not None and int(summary.get("routes") or 0) >= int(routes_min):
        score += 25
        evidence.append(f"matched routes >= {routes_min}")
    return score, evidence


def _add_hits(
    score: int, evidence: list[str], hits: list[str], base: int, weight: int, prefix: str,
) -> tuple[int, list[str]]:
    if hits:
        score += base + len(hits) * weight
        evidence.append(prefix + ", ".join(hits[:5]))
    return score, evidence


def _load_project_archetypes() -> dict[str, Any]:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        candidate = parent / "knowledge" / "architecture_patterns" / "project_archetypes.json"
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
    return {"records": []}


def _contains(marker: str, text: str) -> bool:
    needle = marker.strip().lower()
    if not needle:
        return False
    if re.fullmatch(r"\.[a-z0-9]+", needle):
        return re.search(re.escape(needle) + r"(?![a-z0-9])", text.lower()) is not None
    if any(character in needle for character in "/\\.:"):
        return needle in text.lower()
    tokens = [re.escape(token) for token in re.split(r"[\s_-]+", needle) if token]
    return re.search(r"(?<![a-z0-9])" + r"[\s_-]+".join(tokens) + r"(?![a-z0-9])", text.lower()) is not None


def _transport(summary: dict[str, Any]) -> str:
    frameworks = {str(item).lower() for item in summary.get("frameworks", [])}
    if "fastapi" in frameworks:
        return "FastAPI"
    return "CLI/script" if summary.get("entrypoints") else "unknown"


def _strings(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)] if value else []
