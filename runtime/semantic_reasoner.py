"""Bounded L4.5 semantic hypothesis contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_semantic_hypothesis_request(
    *,
    control_plane_decision: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    escalation = dict(control_plane_decision.get("semantic_escalation", {}))
    if not escalation.get("l4_5_required"):
        return None
    reasons = [str(item) for item in escalation.get("reasons", [])]
    mode = str(control_plane_decision.get("mode") or "role_pipeline")
    return {
        "artifact_type": "SemanticHypothesisRequest",
        "layer": "L4.5",
        "status": "requested",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_decision": {
            "artifact_type": control_plane_decision.get("artifact_type"),
            "layer": control_plane_decision.get("layer"),
            "mode": mode,
            "role_transition": dict(control_plane_decision.get("role_transition", {})),
        },
        "trigger_reasons": reasons,
        "question": _question(mode, reasons),
        "evidence_context": dict(context or {}),
        "allowed_hypothesis_types": _allowed_hypothesis_types(mode, reasons),
        "output_contract": {
            "artifact_type": "SemanticHypothesisProposal",
            "required_fields": [
                "hypothesis_type",
                "proposal",
                "confidence",
                "evidence_refs",
                "risks",
                "return_to_gate",
            ],
        },
        "forbidden_actions": [
            "execute_pipeline",
            "edit_user_source_tree",
            "mutate_registry",
            "build_package",
            "promote_capability",
            "bypass_prompt_product_gate",
            "bypass_artifact_promotion_gate",
        ],
        "return_path": {
            "target_layer": "L4.0",
            "required_step": "validate_semantic_hypothesis_then_rerun_deterministic_gate",
        },
        "principle": "L4.5 may propose bounded hypotheses; L4.0 gates decide whether anything can proceed",
    }


def _question(mode: str, reasons: list[str]) -> str:
    if mode == "prompt_to_product" and "no_supported_package_template" in reasons:
        return (
            "Can the bounded prompt be mapped to an existing supported package template, "
            "or should it become a clarification/new-template candidate?"
        )
    if "unsupported_system_type_requires_semantic_classification" in reasons:
        return "Classify the user intent into a supported bounded system type or explain why it is unsupported."
    if "semantic_rework_after_contracts_passed" in reasons:
        return "Explain the semantic mismatch that remains after contract checks passed and propose a bounded rework target."
    return "Resolve the semantic uncertainty without changing execution authority or bypassing runtime contracts."


def _allowed_hypothesis_types(mode: str, reasons: list[str]) -> list[str]:
    if mode == "prompt_to_product":
        allowed = ["template_mapping_candidate", "clarification_question", "unsupported_reason"]
        if "no_supported_package_template" in reasons:
            allowed.append("new_template_candidate")
        return allowed
    return ["risk_interpretation", "architecture_option", "rework_target", "knowledge_gap"]
