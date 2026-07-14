"""Evidence hardening for human-facing Level 4 project interpretations."""

from __future__ import annotations

import re
from typing import Any


def harden_deliberation(result: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    hardened = dict(result)
    warnings = []
    if _is_weak_summary(hardened.get("executive_summary")):
        hardened["executive_summary"] = _grounded_summary(facts)
        warnings.append("summary_replaced_from_facts")
    capabilities = _grounded_list(hardened.get("capability_decomposition"), facts, kind="capability")
    if capabilities != hardened.get("capability_decomposition"):
        warnings.append("capabilities_grounded")
    hardened["capability_decomposition"] = capabilities
    refactor_plan = _grounded_list(hardened.get("refactor_plan"), facts, kind="refactor")
    if refactor_plan != hardened.get("refactor_plan"):
        warnings.append("refactor_plan_grounded")
    hardened["refactor_plan"] = refactor_plan
    original_questions = [str(item) for item in hardened.get("open_questions", [])]
    open_questions = [item for item in original_questions if _safe_open_question(item, facts)]
    if not open_questions:
        hardened["open_questions"] = _grounded_open_questions(facts)
        warnings.append("open_questions_added")
    else:
        hardened["open_questions"] = open_questions[:3]
        if open_questions != original_questions[:3]:
            warnings.append("open_questions_grounded")
    if not str(hardened.get("cognitive_loop") or "").strip():
        hardened["cognitive_loop"] = _grounded_loop(facts)
        warnings.append("cognitive_loop_added")
    if _facts_are_sparse(facts) and hardened.get("confidence") == "high":
        hardened["confidence"] = "medium"
        warnings.append("confidence_reduced_for_sparse_facts")
    structural_hardening = {"capabilities_grounded", "refactor_plan_grounded"} & set(warnings)
    if structural_hardening and "summary_replaced_from_facts" not in warnings:
        hardened["executive_summary"] = _grounded_summary(facts)
        warnings.append("summary_replaced_due_to_structural_hardening")
    if structural_hardening:
        grounded_questions = _grounded_open_questions(facts)
        if hardened.get("open_questions") != grounded_questions:
            hardened["open_questions"] = grounded_questions
            warnings.append("open_questions_replaced_due_to_structural_hardening")
        grounded_loop = _grounded_loop(facts)
        if hardened.get("cognitive_loop") != grounded_loop:
            hardened["cognitive_loop"] = grounded_loop
            warnings.append("cognitive_loop_replaced_due_to_structural_hardening")
    if warnings:
        hardened["quality_warnings"] = warnings
    return hardened


def _is_weak_summary(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if not text or text in {".", "...", "n/a", "unknown"}:
        return True
    generic = (
        "target software project",
        "unspecified functionality",
        "automation/tooling solution",
        "deterministic facts",
        "level 4",
        "cognitive os",
        "insert concise description",
        "insert brief description",
    )
    dependency_markers = (">=", "<=", "pytest", "uvicorn", "pydantic", "pyyaml")
    product_markers = ("service", "application", "library", "tool", "processes", "provides", "routes")
    dependency_inventory = sum(marker in text for marker in dependency_markers) >= 2 and not any(marker in text for marker in product_markers)
    return any(marker in text for marker in generic) or dependency_inventory or _template_placeholder(text)


def _grounded_summary(facts: dict[str, Any]) -> str:
    task = str(facts.get("task") or "").strip()
    if task:
        return _clean_task(task)
    frameworks = ", ".join(str(item) for item in facts.get("frameworks", [])[:2])
    root = str(facts.get("root") or "project").replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    if frameworks:
        return f"{root} is analyzed as a {frameworks} project."
    return f"{root} has insufficient product-level evidence; review README, entrypoints, and core modules."


def _clean_task(task: str) -> str:
    text = task
    prefix = "Inferred from docs: "
    if text.startswith(prefix):
        text = text[len(prefix) :]
    for suffix in (" (Python project).", " (Python automation/tooling project).", " (FastAPI API service).", " (Flask web application)."):
        text = text.replace(suffix, ".")
    return text.strip()


def _grounded_list(value: Any, facts: dict[str, Any], *, kind: str) -> list[str]:
    rows = [str(item) for item in value if _is_grounded_item(str(item), facts, kind=kind)] if isinstance(value, list) else []
    if rows:
        return rows[:3]
    fallback = _capability_fallback(facts) if kind == "capability" else _refactor_fallback(facts)
    return (rows + [item for item in fallback if item not in rows])[:3]


def _is_grounded_item(text: str, facts: dict[str, Any], *, kind: str) -> bool:
    lowered = text.lower()
    bad = ("optimize", "human-readable", "integration with other libraries", "pipeline", "clarity", "future")
    if any(marker in lowered for marker in bad) or _template_placeholder(text):
        return False
    if kind == "refactor" and any(marker in lowered for marker in ("extract logic", "separate modules", "improve modularity", "enhance modularity")):
        return False
    if kind == "capability" and _mentions_context_path(lowered):
        return False
    evidence = _evidence_terms(facts)
    return any(term and term in lowered for term in evidence) and _has_evidence_anchor(text, facts)


def _mentions_context_path(lowered: str) -> bool:
    context = ("bench/", "benchmark", "test/", "tests/", "testing/", "test_", "testing.py", "integration/", "docs/", "ci/")
    return any(marker in lowered for marker in context)


def _evidence_terms(facts: dict[str, Any]) -> set[str]:
    terms = set()
    for key in ("task", "inputs", "outputs", "entrypoints", "capabilities", "schemas", "weak_contracts", "errors", "risks", "loop"):
        terms.update(_terms_from_value(facts.get(key)))
    for key in ("central", "broad", "hotspots"):
        terms.update(_terms_from_value(facts.get(key)))
    return {term for term in terms if len(term) >= 4}


def _terms_from_value(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set().union(*(_terms_from_value(item) for item in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(_terms_from_value(item) for item in value)) if value else set()
    text = str(value or "").replace("_", " ").replace("/", " ").replace(":", " ").replace(".", " ")
    return {part.lower() for part in text.split() if part.isalnum()}


def _capability_fallback(facts: dict[str, Any]) -> list[str]:
    rows = [str(item) for item in facts.get("capabilities", [])[:3]]
    if rows:
        return rows
    task = _clean_task(str(facts.get("task") or ""))
    entries = [str(item) for item in facts.get("entrypoints", [])[:2]]
    if "json" in task.lower():
        return ["JSON serialization/deserialization behavior evidenced by project docs"]
    if "http" in task.lower():
        return ["HTTP protocol/request handling evidenced by project docs"]
    if "ini" in task.lower():
        return ["INI configuration parsing evidenced by project docs"]
    if entries:
        return [f"Entrypoint workflow: {entry}" for entry in entries]
    return ["No safe reusable Python capability identified from current facts"]


def _refactor_fallback(facts: dict[str, Any]) -> list[str]:
    rows = []
    rows.extend(f"Review hotspot {item.get('target')}" for item in facts.get("hotspots", [])[:2] if isinstance(item, dict) and item.get("target"))
    rows.extend(f"Harden weak contract {item}" for item in facts.get("weak_contracts", [])[:2])
    if rows:
        return list(dict.fromkeys(rows))[:3]
    if not facts.get("entrypoints"):
        return ["Add or identify a product-level entrypoint before extraction"]
    return ["Map core boundaries before extracting runtime capabilities"]


def _grounded_open_questions(facts: dict[str, Any]) -> list[str]:
    questions = []
    if not facts.get("entrypoints"):
        questions.append("Which product-level entrypoint should be treated as runtime boundary?")
    if not facts.get("capabilities"):
        questions.append("Which core function is safe to extract as the first capability?")
    if facts.get("risks"):
        questions.append("Which listed risks must block automated extraction?")
    return questions[:3] or ["Which scenario should be validated first by a human reviewer?"]


def _template_placeholder(text: str) -> bool:
    lowered = text.lower()
    bracket_placeholder = re.search(r"\[(?:specific|feature|core|component|key)\b[^\]]*\]", text, flags=re.IGNORECASE)
    identifier = re.search(r"\b(?:class|schema|function|module)\s+[a-z]\b", text, flags=re.IGNORECASE)
    return bool(bracket_placeholder or identifier) or any(
        marker in lowered for marker in ("provide summary of the target project", "specific feature or functionality", "example:")
    )


def _has_evidence_anchor(text: str, facts: dict[str, Any]) -> bool:
    values = []
    for key in ("entrypoints", "capabilities", "schemas", "weak_contracts", "central", "broad", "hotspots", "boundaries"):
        values.extend(_flatten_strings(facts.get(key)))
    ignored = {"main", "config", "index", "server", "handler", "project"}
    lowered = text.lower()
    for value in values:
        normalized = value.lower().split("(", 1)[0]
        path, _, symbol = normalized.partition(":")
        candidates = [normalized] if "/" in normalized or ":" in normalized else []
        if "/" in path:
            candidates.append(path)
        if len(symbol) >= 5 and symbol not in ignored:
            candidates.append(symbol)
        if any(candidate and candidate in lowered for candidate in candidates):
            return True
    return False


def _flatten_strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [item for nested in value.values() for item in _flatten_strings(nested)]
    if isinstance(value, list):
        return [item for nested in value for item in _flatten_strings(nested)]
    return [str(value)] if value else []


def _safe_open_question(text: str, facts: dict[str, Any]) -> bool:
    if _template_placeholder(text):
        return False
    paths = re.findall(r"[a-zA-Z0-9_./-]+\.(?:py|go|js|ts|java|cs|rs|cpp|c|h)", text)
    return not paths or all(_has_evidence_anchor(path, facts) for path in paths)


def _grounded_loop(facts: dict[str, Any]) -> str:
    loop = [str(item) for item in facts.get("loop", []) if item]
    if loop:
        return "; ".join(loop[:4])
    if facts.get("entrypoints"):
        return "run entrypoint; capture input/output; inject controlled failure; report result"
    return "identify product boundary; capture representative input; test controlled failure; report extraction decision"


def _facts_are_sparse(facts: dict[str, Any]) -> bool:
    return not facts.get("entrypoints") or not facts.get("capabilities")
