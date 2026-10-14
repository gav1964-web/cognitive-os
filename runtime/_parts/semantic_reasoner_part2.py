from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable
from runtime.local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat
from runtime.semantic_resolution_artifacts import (
    build_developer_improvement_request,
    build_successful_resolution_candidate,
    developer_improvement_request,
    resolve_with_existing_means_or_developer_request,
)

def _is_prompt_to_product_existing_route_request(request: dict[str, Any]) -> bool:
    mode = str(dict(request.get("source_decision", {})).get("mode") or "")
    allowed = set(str(item) for item in request.get("allowed_hypothesis_types", []))
    reasons = set(str(item) for item in request.get("trigger_reasons", []))
    return (
        mode == "prompt_to_product"
        and "successful_existing_resolution" in allowed
        and bool({"no_supported_package_template", "prompt_intake_uncertainty"} & reasons)
    )

def _default_risks(hypothesis_type: str) -> list[str]:
    return {
        "new_template_candidate": [
            "model omitted explicit risks",
            "human review required before template admission",
        ],
        "successful_existing_resolution": [
            "model omitted explicit risks",
            "resolution must pass verification and repeated-success admission before KB promotion",
        ],
        "developer_improvement_request": [
            "model omitted explicit risks",
            "developer request may be incomplete without human review",
        ],
        "template_mapping_candidate": ["model omitted explicit risks", "mapping must be rerun through deterministic gate"],
        "clarification_question": ["model omitted explicit risks", "clarification may still be incomplete"],
        "unsupported_reason": ["model omitted explicit risks", "unsupported classification may need human review"],
    }.get(hypothesis_type, ["model omitted explicit risks", "L4.0 validation required"])

def _new_template_candidate(prompt: str) -> dict[str, Any]:
    lower = prompt.lower()
    if "csv" in lower and ("sort" in lower or "сорт" in lower):
        template_id = "csv_sort_cli"
        purpose = "CLI utility that reads a CSV file, sorts rows by a named column, and writes a CSV file."
        acceptance = ["reads CSV input", "sorts by configured column", "writes CSV output", "has README and tests"]
    elif "url" in lower and ("status" in lower or "статус" in lower):
        template_id = "url_status_checker_cli"
        purpose = "CLI utility that reads URLs, checks HTTP statuses, and writes a JSON report."
        acceptance = ["reads URL list", "handles network failures", "writes JSON report", "has README and tests"]
    else:
        template_id = "new_stage2_cli_template"
        purpose = "New bounded Stage 2 CLI template candidate inferred from an adequate prompt without a supported template."
        acceptance = ["bounded CLI scope", "declared inputs", "declared outputs", "README and tests"]
    return {
        "hypothesis_type": "new_template_candidate",
        "proposal": {
            "template_id": template_id,
            "system_type": "cli",
            "purpose": purpose,
            "acceptance_focus": acceptance,
            "actions": ["record_backlog_item"],
        },
        "confidence": 0.74,
        "evidence_refs": ["PromptAdequacyGate.status=ready", "prompt_product_gate.supported_template=null"],
        "risks": ["template does not exist yet", "human review required before deterministic generation"],
        "return_to_gate": True,
    }

def _unsupported_reason(prompt: str) -> dict[str, Any]:
    return {
        "hypothesis_type": "unsupported_reason",
        "proposal": {
            "reason": "Prompt could not be classified into the supported Stage 2 bounded system types.",
            "prompt_excerpt": prompt[:200],
            "actions": ["ask_clarification"],
        },
        "confidence": 0.6,
        "evidence_refs": ["PromptAdequacyGate.system_type=null"],
        "risks": ["classification may be incomplete without human clarification"],
        "return_to_gate": True,
    }

def _rework_target(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "hypothesis_type": "rework_target",
        "proposal": {
            "target": "role_artifact_semantics",
            "reason": "Review requested semantic rework after contract checks passed.",
            "actions": ["return_to_role_pipeline_rework"],
        },
        "confidence": 0.65,
        "evidence_refs": list(request.get("trigger_reasons", [])),
        "risks": ["requires human or model-backed review of semantics"],
        "return_to_gate": True,
    }

def _knowledge_gap(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "hypothesis_type": "knowledge_gap",
        "proposal": {
            "question": request.get("question"),
            "needed_for": "resolve_semantic_escalation",
            "actions": ["record_knowledge_gap"],
        },
        "confidence": 0.55,
        "evidence_refs": list(request.get("trigger_reasons", [])),
        "risks": ["insufficient deterministic context"],
        "return_to_gate": True,
    }

def _bounded_float(value: Any, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, parsed))
