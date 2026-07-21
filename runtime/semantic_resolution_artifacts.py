"""L4.5 resolution artifacts for prompt-to-product refusals."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .generic_file_conversion_recipe import build_conversion_recipe, is_file_conversion_prompt
from .semantic_resolution_rules import load_semantic_resolution_rules


def build_successful_resolution_candidate(proposal: dict[str, Any]) -> dict[str, Any] | None:
    if proposal.get("status") != "ok" or proposal.get("hypothesis_type") != "successful_existing_resolution":
        return None
    data = dict(proposal.get("proposal", {}))
    return {
        "artifact_type": "SuccessfulResolutionCandidate",
        "status": "candidate",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "resolution_id": data.get("resolution_id") or "unclassified_existing_resolution",
        "means_used": list(data.get("means_used") or []),
        "verification_plan": list(data.get("verification_plan") or []),
        "kb_candidate": dict(data.get("kb_candidate", {})),
        "requires_repeated_successes": True,
        "requires_human_review": True,
        "forbidden_auto_actions": ["promote_to_kb", "edit_runtime_templates", "mutate_registry"],
        "next_step": "repeat on comparable prompts before KB/template admission",
    }


def build_developer_improvement_request(proposal: dict[str, Any]) -> dict[str, Any] | None:
    if proposal.get("status") != "ok" or proposal.get("hypothesis_type") != "developer_improvement_request":
        return None
    data = dict(proposal.get("proposal", {}))
    return {
        "artifact_type": "DeveloperImprovementRequest",
        "status": "requested",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "request_id": data.get("request_id") or "unclassified_developer_improvement",
        "missing_capability": data.get("missing_capability"),
        "problem": data.get("problem"),
        "evidence_refs": list(data.get("evidence_refs") or proposal.get("evidence_refs") or []),
        "suggested_work": list(data.get("suggested_work") or []),
        "acceptance_focus": list(data.get("acceptance_focus") or []),
        "requires_developer": True,
        "forbidden_auto_actions": ["edit_runtime_templates", "mutate_registry", "promote_to_kb"],
        "next_step": "developer reviews and implements bounded improvement with tests",
    }


def resolve_with_existing_means_or_developer_request(request: dict[str, Any], prompt: str) -> dict[str, Any]:
    known = _known_templates(request)
    lower = prompt.lower()
    for rule in load_semantic_resolution_rules().get("existing_resolution_rules", []):
        if str(rule.get("required_template")) not in known:
            continue
        if not _predicate_matches(str(rule.get("predicate") or ""), prompt, lower):
            continue
        proposal = _existing_resolution_from_rule(dict(rule), prompt)
        if proposal is not None:
            return proposal
    return developer_improvement_request(prompt)


def developer_improvement_request(prompt: str) -> dict[str, Any]:
    lower = prompt.lower()
    selected = None
    for row in load_semantic_resolution_rules().get("developer_request_rules", []):
        if _predicate_matches(str(row.get("predicate") or ""), prompt, lower):
            selected = dict(row)
            break
    if selected is None:
        selected = dict(load_semantic_resolution_rules().get("default_developer_request") or {})
    return {
        "hypothesis_type": "developer_improvement_request",
        "proposal": {
            "request_id": selected.get("request_id"),
            "missing_capability": selected.get("missing_capability"),
            "problem": selected.get("problem"),
            "prompt_excerpt": prompt[:240],
            "suggested_work": [
                "add or generalize a bounded route only after developer review",
                "add teacher-reference and tests",
                "rerun the prompt and field trial",
            ],
            "acceptance_focus": list(selected.get("acceptance_focus") or []),
            "actions": ["record_developer_improvement_request"],
        },
        "confidence": 0.76,
        "evidence_refs": ["PromptAdequacyGate.status=ready", "prompt_product_gate.supported_template=null"],
        "risks": ["existing means may be incomplete", "developer must verify before changing runtime/KB"],
        "return_to_gate": True,
    }


def _existing_resolution_from_rule(rule: dict[str, Any], prompt: str) -> dict[str, Any] | None:
    proposal = {
        "resolution_id": rule.get("resolution_id"),
        "means_used": list(rule.get("means_used") or []),
        "verification_plan": list(rule.get("verification_plan") or []),
        "kb_candidate": dict(rule.get("kb_candidate") or {}),
        "actions": ["record_successful_resolution_candidate"],
    }
    if rule.get("include_conversion_recipe") is True:
        recipe = build_conversion_recipe(prompt)
        if recipe is None:
            return None
        proposal["recipe"] = recipe.to_dict()
    return {
        "hypothesis_type": "successful_existing_resolution",
        "proposal": proposal,
        "confidence": float(rule.get("confidence") or 0.0),
        "evidence_refs": list(rule.get("evidence_refs") or []),
        "risks": list(rule.get("risks") or []),
        "return_to_gate": True,
    }


def _predicate_matches(predicate: str, prompt: str, lower: str) -> bool:
    if predicate == "csv_sort_prompt":
        return "csv" in lower and ("sort" in lower or "сорт" in lower)
    if predicate == "image_contents_prompt":
        return _looks_like_image_contents(lower)
    if predicate == "file_conversion_prompt":
        return is_file_conversion_prompt(prompt)
    if predicate == "behavior_question":
        return _looks_like_behavior_question(lower)
    if predicate == "ocr_prompt":
        return "ocr" in lower or "распозна" in lower
    return False


def _looks_like_image_contents(lower: str) -> bool:
    has_image = any(marker in lower for marker in ("image", "picture", "photo", "изображ", "картин", "фото", "png", "jpg", "jpeg", "webp"))
    has_contents = any(marker in lower for marker in ("content", "contents", "list", "objects", "перечисл", "содерж", "объект", "опиши"))
    has_ocr = "ocr" in lower or "распозна" in lower
    return has_image and has_contents and not has_ocr


def _looks_like_behavior_question(lower: str) -> bool:
    has_question_shape = any(
        marker in lower
        for marker in (
            "что произойдет",
            "что будет",
            "как повед",
            "what happens",
            "what will happen",
            "behavior",
            "behaviour",
        )
    )
    has_condition = any(marker in lower for marker in ("если", "if ", "when ", "при "))
    return has_question_shape and has_condition


def _known_templates(request: dict[str, Any]) -> set[str]:
    context = request.get("evidence_context", {})
    if not isinstance(context, dict):
        return set()
    pack = context.get("evidence_pack", {})
    if not isinstance(pack, dict):
        return set()
    prompt_facts = pack.get("prompt_facts", {})
    if not isinstance(prompt_facts, dict):
        return set()
    return {str(item) for item in prompt_facts.get("known_templates", [])}
