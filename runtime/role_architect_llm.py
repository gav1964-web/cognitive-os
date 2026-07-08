"""Optional LLM advisory backend for ArchitectSkill."""

from __future__ import annotations

import json
import re
from typing import Any

from .local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat


def apply_architect_advisory(
    artifact: dict[str, Any],
    *,
    config: LocalInferenceConfig | None,
) -> dict[str, Any]:
    if config is None:
        artifact["architect_advisory"] = {"source": "deterministic", "llm_invoked": False}
        return artifact
    try:
        response = call_json_chat(_messages(artifact), config=config)
    except LocalInferenceError as exc:
        artifact["architect_advisory"] = {
            "source": "deterministic_fallback",
            "llm_invoked": False,
            "error": str(exc),
        }
        return artifact
    normalized = _normalize_advisory(response, artifact)
    accepted = normalized["advisory_delta_score"] > 0
    artifact["architect_advisory"] = {
        "source": config.provider_label,
        "model": config.model,
        "llm_invoked": True,
        "accepted": accepted,
        "advisory_delta_score": normalized["advisory_delta_score"],
        "applied_changes": normalized["applied_changes"] if accepted else [],
        "accepted_risks": normalized["additional_risks"] if accepted else [],
        "quality_tags": normalized["quality_tags"] if accepted else [],
        "rejected_items": normalized["rejected_items"],
        "summary": normalized.get("summary"),
    }
    if accepted and normalized.get("chosen_option"):
        artifact["chosen_option"] = normalized["chosen_option"]
    if accepted and normalized.get("additional_risks"):
        artifact["risks"] = [*artifact.get("risks", []), *normalized["additional_risks"][:3]]
    return artifact


def _messages(artifact: dict[str, Any]) -> list[dict[str, str]]:
    evidence_sources = sorted(_risk_evidence_terms(artifact))
    compact = {
        "goal": artifact.get("goal"),
        "project": artifact.get("project"),
        "options": artifact.get("architecture_options"),
        "capabilities": artifact.get("capability_model"),
        "risks": artifact.get("risks"),
        "non_goals": artifact.get("non_goals"),
        "evidence_sources": evidence_sources,
        "source_context": _select_source_context(artifact, evidence_sources),
        "current_choice": dict(artifact.get("chosen_option", {})).get("id"),
    }
    return [
        {
            "role": "system",
            "content": (
                "You are ArchitectSkill advisory backend. Return only JSON. "
                "Do not propose code execution, registry mutation, pipeline execution, or promotion. "
                "Choose one existing architecture option by id only if it improves the deterministic choice. "
                "If the deterministic current_choice is already best, repeat it and keep reason short. "
                "Additional risks must be concrete, non-generic, and cite one exact evidence_source. "
                "Look for source-level extraction risks: I/O boundary, hidden orchestration, shared state, "
                "contract ambiguity, retry/idempotency risk, dependency/runtime boundary. "
                "Use source_context snippets, callers, callees, dataflow_steps, and central_flow_node facts. "
                "Prefer risks about extraction boundaries between caller and callee over generic code quality notes. "
                "If a source_context item contains idempotency_risk, process_boundary_reasons, side_effects, "
                "or mixed_responsibilities, turn that fact into a specific extraction risk unless it merely "
                "duplicates an existing risk. "
                "Keep summaries short; put useful architectural value into additional_risks, not prose summary. "
                "A good risk names one evidence_source and explains the specific extraction hazard. "
                "Do not invent evidence sources. If no source-backed risk exists, return an empty additional_risks list. "
                "Return keys: chosen_option_id, reason, tradeoffs, prerequisites, additional_risks, summary. "
                "Each additional_risk must be an object with description and evidence_source."
            ),
        },
        {"role": "user", "content": json.dumps(compact, ensure_ascii=False, separators=(",", ":"))},
    ]


def _normalize_advisory(response: dict[str, Any], artifact: dict[str, Any]) -> dict[str, Any]:
    allowed_ids = {str(item.get("id")) for item in artifact.get("architecture_options", [])}
    chosen_id = str(response.get("chosen_option_id") or "")
    chosen = None
    delta_score = 0
    applied_changes = []
    rejected_items = []
    current_choice = str(dict(artifact.get("chosen_option", {})).get("id") or "")
    reason = _short(response.get("reason"))
    if chosen_id in allowed_ids:
        base = next(item for item in artifact.get("architecture_options", []) if item.get("id") == chosen_id)
        chosen = {
            "id": chosen_id,
            "title": base.get("title"),
            "reason": reason or "LLM advisory selected this existing option.",
            "tradeoffs": _short_list(response.get("tradeoffs")) or base.get("tradeoffs", []),
            "prerequisites": _short_list(response.get("prerequisites")) or base.get("prerequisites", []),
        }
        if chosen_id != current_choice and _has_concrete_reference(reason, artifact):
            delta_score += 2
            applied_changes.append("chosen_option")
        elif chosen_id != current_choice:
            chosen = None
            rejected_items.append({"kind": "chosen_option", "reason": "missing concrete evidence in reason"})
    elif chosen_id:
        rejected_items.append({"kind": "chosen_option", "reason": "unknown option id"})
    risks, rejected_risks = _risk_list(response.get("additional_risks"), artifact)
    if risks:
        delta_score += len(risks)
        applied_changes.append("additional_risks")
    return {
        "chosen_option": chosen,
        "additional_risks": risks,
        "quality_tags": _quality_tags(risks),
        "advisory_delta_score": delta_score,
        "applied_changes": applied_changes,
        "rejected_items": [*rejected_items, *rejected_risks],
        "summary": _short(response.get("summary")),
    }


def _risk_list(value: Any, artifact: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    risks = []
    rejected = []
    for item in _risk_items(value):
        description = _short(item.get("description"))
        evidence = _short(item.get("evidence"))
        if _is_generic(description):
            rejected.append({"kind": "additional_risk", "reason": "generic or empty description"})
            continue
        if not _has_risk_evidence(f"{description} {evidence}", artifact):
            rejected.append({"kind": "additional_risk", "reason": "missing concrete source evidence"})
            continue
        if _duplicates_existing_risk(description, artifact):
            rejected.append({"kind": "additional_risk", "reason": "duplicates existing risk"})
            continue
        risk = {
            "source": "architect_llm_advisory",
            "severity": "medium",
            "description": description,
            "evidence": evidence or "description references known project artifact",
        }
        risk["quality_tags"] = _quality_tags_for_risk(risk)
        risks.append(risk)
    return risks[:3], rejected


def _risk_items(value: Any) -> list[dict[str, str]]:
    if isinstance(value, list):
        items = value[:5]
    else:
        items = [value] if value else []
    normalized = []
    for item in items:
        if isinstance(item, dict):
            normalized.append(
                {
                    "description": item.get("description") or item.get("risk") or item.get("text"),
                    "evidence": item.get("evidence_source")
                    or item.get("evidence")
                    or item.get("source")
                    or item.get("reference"),
                }
            )
        else:
            normalized.append({"description": item, "evidence": ""})
    return normalized


def _has_concrete_reference(value: str, artifact: dict[str, Any]) -> bool:
    text = value.lower()
    return any(term in text for term in _evidence_terms(artifact))


def _evidence_terms(artifact: dict[str, Any]) -> set[str]:
    raw_terms = [
        *_collect_terms(artifact.get("project")),
        *_collect_terms(artifact.get("architecture_options")),
        *_collect_terms(artifact.get("capability_model")),
        *_collect_terms(artifact.get("risks")),
    ]
    return {str(term).lower() for term in raw_terms if term and len(str(term)) >= 4}


def _has_risk_evidence(value: str, artifact: dict[str, Any]) -> bool:
    text = value.lower()
    return any(term in text for term in _risk_evidence_terms(artifact))


def _risk_evidence_terms(artifact: dict[str, Any]) -> set[str]:
    terms = []
    for section in ("capability_model", "traceability"):
        for item in artifact.get(section, []):
            if isinstance(item, dict):
                terms.extend(_source_terms(item.get("source")))
    return {term.lower() for term in terms if len(term) >= 4}


def _select_source_context(artifact: dict[str, Any], evidence_sources: list[str]) -> dict[str, Any]:
    context = dict(artifact.get("source_context", {}))
    selected = {}
    for source in evidence_sources[:12]:
        if source in context:
            selected[source] = context[source]
    return selected


def _source_terms(value: Any) -> list[str]:
    if not isinstance(value, str) or not value:
        return []
    parts = [value]
    if ":" in value:
        path, symbol = value.split(":", 1)
        parts.extend([path, symbol])
    return parts


def _collect_terms(value: Any) -> list[str]:
    if isinstance(value, dict):
        terms = [str(key) for key in value.keys()]
        for item in value.values():
            terms.extend(_collect_terms(item))
        return terms
    if isinstance(value, list):
        terms = []
        for item in value:
            terms.extend(_collect_terms(item))
        return terms
    if isinstance(value, str):
        return [value, *re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", value)]
    return []


def _is_generic(value: str) -> bool:
    text = value.strip().lower()
    if len(text) < 12:
        return True
    generic_patterns = [
        r"\bnone identified\b",
        r"\bno additional\b",
        r"\bnot applicable\b",
        r"\bn/?a\b",
        r"\bmay delay future improvements\b",
        r"\bbeyond the tradeoffs\b",
        r"\bincomplete (capability )?extraction\b",
        r"\bnot cover all potential\b",
        r"\bfuture problems\b",
        r"\bfuture bugs\b",
        r"\blimited focus\b",
    ]
    return any(re.search(pattern, text) for pattern in generic_patterns)


def _duplicates_existing_risk(description: str, artifact: dict[str, Any]) -> bool:
    new_tokens = _meaningful_tokens(description)
    if len(new_tokens) < 2:
        return False
    for risk in artifact.get("risks", []):
        if not isinstance(risk, dict):
            continue
        existing_tokens = _meaningful_tokens(str(risk.get("description") or ""))
        if len(existing_tokens) < 2:
            continue
        overlap = len(new_tokens & existing_tokens) / len(new_tokens)
        if overlap >= 0.45:
            return True
    return False


def _quality_tags(risks: list[dict[str, str]]) -> list[str]:
    tags = []
    for risk in risks:
        tags.extend(risk.get("quality_tags", []))
    return sorted(set(tags))


def _quality_tags_for_risk(risk: dict[str, str]) -> list[str]:
    text = f"{risk.get('description', '')} {risk.get('evidence', '')}".lower()
    tags = []
    if _contains_any(text, ("caller", "callee", "boundary", "extraction", "interface")):
        tags.append("boundary_risk")
    if _contains_any(text, ("contract", "schema", "typed", "input", "output", "signature")):
        tags.append("contract_risk")
    if _contains_any(text, ("idempotency", "retry", "replay", "duplicate")):
        tags.append("idempotency_risk")
    if _contains_any(text, ("process", "subprocess", "timeout", "isolation", "network")):
        tags.append("process_boundary_risk")
    if _contains_any(text, ("filesystem", "write", "mutate", "state", "cache", "side effect", "side-effect")):
        tags.append("side_effect_risk")
    if _contains_any(text, ("orchestration", "orchestrator", "control_flow", "mixed responsibilities")):
        tags.append("orchestration_risk")
    return tags or ["source_backed_risk"]


def _contains_any(value: str, needles: tuple[str, ...]) -> bool:
    return any(needle in value for needle in needles)


def _meaningful_tokens(value: str) -> set[str]:
    stopwords = {
        "about",
        "absence",
        "detail",
        "potential",
        "problem",
        "problems",
        "project",
        "related",
        "risk",
        "risks",
        "severity",
        "within",
    }
    normalized = value.lower().replace("_", " ")
    return {_stem(token) for token in re.findall(r"[a-zA-Z][a-zA-Z0-9]{3,}", normalized) if token not in stopwords}


def _stem(token: str) -> str:
    if token.endswith("ies") and len(token) > 5:
        return f"{token[:-3]}y"
    if token.endswith("s") and len(token) > 5:
        return token[:-1]
    return token


def _short_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item)[:240] for item in value[:5] if str(item).strip()]
    if value:
        return [str(value)[:240]]
    return []


def _short(value: Any) -> str:
    return str(value or "")[:500]
