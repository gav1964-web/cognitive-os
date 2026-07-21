"""Deterministic quality scoring for Level 4 project interpretations."""

from __future__ import annotations

import re
from typing import Any


CONTEXT_MARKERS = ("bench/", "benchmark", "test/", "tests/", "testing/", "test_", "integration/", "docs/", "ci/")
GENERIC_MARKERS = ("optimize", "improve", "future", "clarity", "pipeline", "tooling/automation solution")


def score_l4_interpretation(interpretation: dict[str, Any]) -> dict[str, Any]:
    facts = dict(interpretation.get("fact_summary", {}))
    scores = {
        "summary_grounding": _summary_grounding(interpretation, facts),
        "capability_grounding": _capability_grounding(interpretation, facts),
        "actionability": _actionability(interpretation, facts),
        "uncertainty_honesty": _uncertainty_honesty(interpretation, facts),
    }
    warnings = _warnings(interpretation, scores)
    return {
        "quality_score": round(sum(scores.values()) / len(scores), 3),
        "scores": scores,
        "warnings": warnings,
        "passed": not warnings and min(scores.values()) >= 0.75,
    }


def _summary_grounding(interpretation: dict[str, Any], facts: dict[str, Any]) -> float:
    summary = str(interpretation.get("executive_summary") or "")
    if _placeholder(summary) or _template_placeholder(summary) or _self_referential(summary) or _dependency_inventory(summary):
        return 0.0
    if _overlaps(summary, _evidence_terms(facts, include_paths=False)):
        return 1.0
    return 0.5 if len(summary.split()) >= 6 else 0.25


def _capability_grounding(interpretation: dict[str, Any], facts: dict[str, Any]) -> float:
    rows = [str(item) for item in interpretation.get("capability_decomposition", []) if str(item).strip()]
    if not rows:
        return 0.0
    evidence = _evidence_terms(facts, include_paths=True)
    anchors = _evidence_anchors(facts)
    good = 0
    for row in rows:
        lowered = row.lower()
        if any(marker in lowered for marker in CONTEXT_MARKERS) or _template_placeholder(row):
            continue
        if _overlaps(row, evidence) and _has_anchor(row, anchors):
            good += 1
    return round(good / len(rows), 3)


def _actionability(interpretation: dict[str, Any], facts: dict[str, Any]) -> float:
    rows = [str(item) for item in interpretation.get("refactor_plan", []) if str(item).strip()]
    if not rows:
        return 0.0
    evidence = _evidence_terms(facts, include_paths=True)
    anchors = _evidence_anchors(facts)
    good = 0
    for row in rows:
        lowered = row.lower()
        if _vague_action(row) or _template_placeholder(row):
            continue
        if any(marker in lowered for marker in GENERIC_MARKERS) and not _overlaps(row, evidence):
            continue
        if _has_action_verb(row) and ((_overlaps(row, evidence) and _has_anchor(row, anchors)) or _mentions_risk(row, facts)):
            good += 1
    return round(good / len(rows), 3)


def _uncertainty_honesty(interpretation: dict[str, Any], facts: dict[str, Any]) -> float:
    confidence = str(interpretation.get("confidence") or "").lower()
    sparse = _facts_are_sparse(facts)
    questions = [str(item) for item in interpretation.get("open_questions", []) if str(item).strip()]
    if sparse:
        score = 0.5 if confidence in {"medium", "low"} else 0.0
        return min(1.0, score + (0.5 if questions else 0.0))
    if confidence in {"high", "medium", "low"}:
        return 1.0
    return 0.5


def _warnings(interpretation: dict[str, Any], scores: dict[str, float]) -> list[str]:
    warnings = [name for name, value in scores.items() if value < 0.75]
    text_fields = [
        interpretation.get("executive_summary"),
        interpretation.get("cognitive_loop"),
        interpretation.get("capability_decomposition"),
        interpretation.get("refactor_plan"),
        interpretation.get("open_questions"),
    ]
    if any(_template_placeholder(str(item)) for field in text_fields for item in (field if isinstance(field, list) else [field])):
        warnings.append("template_placeholder")
    facts = dict(interpretation.get("fact_summary", {}))
    if any(_ungrounded_path_reference(str(item), facts) for item in interpretation.get("open_questions", [])):
        warnings.append("ungrounded_open_question")
    if interpretation.get("fallback_reason"):
        warnings.append("fallback_used")
    if interpretation.get("source") != "external_l4":
        warnings.append("external_l4_not_used")
    return warnings


def _evidence_terms(facts: dict[str, Any], *, include_paths: bool) -> set[str]:
    keys = ("task", "inputs", "outputs", "entrypoints", "capabilities", "schemas", "weak_contracts", "errors", "risks", "loop")
    terms = set().union(*(_terms(facts.get(key), include_paths=include_paths) for key in keys))
    runtime = facts.get("runtime_extraction", {})
    if isinstance(runtime, dict):
        terms.update(_terms(runtime, include_paths=include_paths))
    terms.update(_terms(facts.get("hotspots"), include_paths=include_paths))
    return {term for term in terms if len(term) >= 4}


def _terms(value: Any, *, include_paths: bool) -> set[str]:
    if isinstance(value, dict):
        return set().union(*(_terms(item, include_paths=include_paths) for item in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(_terms(item, include_paths=include_paths) for item in value)) if value else set()
    text = str(value or "").replace("_", " ")
    if include_paths:
        text = text.replace("/", " ").replace(":", " ").replace(".", " ")
    return {part.lower().strip("`'\"(),;") for part in text.split() if part.strip("`'\"(),;").isalnum()}


def _overlaps(text: str, evidence: set[str]) -> bool:
    return bool(_terms(text, include_paths=True) & evidence)


def _placeholder(text: str) -> bool:
    return text.strip().lower() in {"", ".", "...", "unknown", "n/a"}


def _template_placeholder(text: str) -> bool:
    lowered = text.lower()
    bracket_placeholder = re.search(
        r"\[(?:specific|feature|core|component|key)\b[^\]]*\]",
        text,
        flags=re.IGNORECASE,
    )
    return bool(bracket_placeholder or re.search(r"\b(?:class|schema|function|module)\s+[a-z]\b", text, flags=re.IGNORECASE)) or any(
        marker in lowered
        for marker in ("provide summary of the target project", "specific feature or functionality", "example:")
    )


def _dependency_inventory(text: str) -> bool:
    lowered = text.lower()
    dependency_markers = (">=", "<=", "pytest", "uvicorn", "pydantic", "pyyaml")
    product_markers = ("service", "application", "library", "tool", "processes", "provides", "routes")
    return sum(marker in lowered for marker in dependency_markers) >= 2 and not any(marker in lowered for marker in product_markers)


def _vague_action(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in ("extract logic", "separate modules", "improve modularity", "enhance modularity"))


def _evidence_anchors(facts: dict[str, Any]) -> set[str]:
    values = []
    for key in ("entrypoints", "capabilities", "schemas", "weak_contracts", "central", "broad", "hotspots", "boundaries"):
        values.extend(_flatten_strings(facts.get(key)))
    anchors = set()
    ignored = {"main", "config", "index", "server", "handler", "project"}
    for value in values:
        normalized = value.lower().split("(", 1)[0]
        if "/" in normalized or ":" in normalized:
            anchors.add(normalized)
        path, _, symbol = normalized.partition(":")
        if "/" in path:
            anchors.add(path)
        if len(symbol) >= 5 and symbol not in ignored:
            anchors.add(symbol)
    return anchors


def _flatten_strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [item for nested in value.values() for item in _flatten_strings(nested)]
    if isinstance(value, list):
        return [item for nested in value for item in _flatten_strings(nested)]
    return [str(value)] if value else []


def _has_anchor(text: str, anchors: set[str]) -> bool:
    lowered = text.lower()
    return any(anchor in lowered for anchor in anchors)


def _ungrounded_path_reference(text: str, facts: dict[str, Any]) -> bool:
    paths = re.findall(r"[a-zA-Z0-9_./-]+\.(?:py|go|js|ts|java|cs|rs|cpp|c|h)", text)
    if not paths:
        return False
    anchors = _evidence_anchors(facts)
    return any(not _has_anchor(path, anchors) for path in paths)


def _self_referential(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in ("level 4", "cognitive os", "deterministic facts", "this prompt"))


def _has_action_verb(text: str) -> bool:
    lowered = text.lower()
    verbs = (
        "extract",
        "split",
        "separate",
        "harden",
        "define",
        "map",
        "isolate",
        "add",
        "review",
        "clarify",
        "implement",
        "decompose",
        "decomposing",
        "decomposition",
        "decomplexify",
        "enhance",
        "make",
    )
    return any(verb in lowered for verb in verbs)


def _mentions_risk(text: str, facts: dict[str, Any]) -> bool:
    lowered = text.lower()
    risks = [str(item).lower() for item in facts.get("risks", [])]
    return any(risk and risk in lowered for risk in risks) or "risk" in lowered or "dependency" in lowered


def _facts_are_sparse(facts: dict[str, Any]) -> bool:
    return not facts.get("entrypoints") or not facts.get("capabilities")
