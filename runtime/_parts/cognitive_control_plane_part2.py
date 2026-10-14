from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from runtime.l4_decision_table import (
    match_prompt_product_rule,
    match_prompt_product_transition_rule,
    prompt_product_escalation_reason,
    terminal_secret_risk_markers,
    terminal_unsupported_markers,
)


def _is_bounded_behavior_question(prompt: str, prompt_adequacy: dict[str, Any]) -> bool:
    if prompt_adequacy.get("status") != "needs_clarification":
        return False
    boundary = dict(prompt_adequacy.get("boundary_classification", {}))
    if boundary.get("risk_markers") or boundary.get("unsupported_markers"):
        return False
    lower = prompt.lower()
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
    has_supported_domain_signal = any(
        marker in lower
        for marker in (
            "изображ",
            "картин",
            "фото",
            "image",
            "picture",
            "ocr",
            "excel",
            "xlsx",
            "таблиц",
            "csv",
            "json",
            "файл",
        )
    )
    return (
        prompt_adequacy.get("system_type") in {"cli", "file_processing_utility", "small_local_service", "fastapi_service"}
        and boundary.get("boundary") in {"incomplete_bounded_prompt", "bounded_supported_class"}
        and has_question_shape
        and has_supported_domain_signal
    )

def _prompt_product_crystallization_backlog(
    transition: dict[str, Any],
    gate: dict[str, Any],
    escalation: dict[str, Any],
) -> list[dict[str, Any]]:
    if escalation.get("l4_5_required"):
        return []
    if gate.get("status") != "passed":
        return []
    return [
        {
            "candidate": "prompt_product_transition_rule",
            "pattern": transition.get("reason_code"),
            "target": "runtime/cognitive_control_plane.py",
            "action": "keep prompt-to-product routing deterministic and covered by tests",
        },
        {
            "candidate": "supported_package_template",
            "pattern": gate.get("supported_template"),
            "target": "curricula/programmer_prompt_stage2",
            "action": "promote stable generated-package case coverage into the curriculum catalog",
        },
    ]

def _blocked_no_safe_candidate(artifacts: dict[str, dict[str, Any]]) -> bool:
    for artifact in artifacts.values():
        if _has_blocked_candidate_signal(artifact):
            return True
    return False

def _has_blocked_candidate_signal(value: Any) -> bool:
    if isinstance(value, dict):
        status = value.get("status")
        reason = value.get("reason")
        code = value.get("code")
        if status == "blocked_no_safe_candidate" or reason == "no_safe_source_specific_candidate" or code == "no_safe_source_specific_candidate":
            return True
        return any(_has_blocked_candidate_signal(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_blocked_candidate_signal(item) for item in value if isinstance(item, (dict, list)))
    return value in {"blocked_no_safe_candidate", "no_safe_source_specific_candidate"}

def _has_architect_fallback(artifacts: dict[str, dict[str, Any]]) -> bool:
    adr = dict(artifacts.get("architecture_decision", {}))
    advisory = dict(adr.get("architect_advisory", {}))
    return advisory.get("source") == "deterministic_fallback"
