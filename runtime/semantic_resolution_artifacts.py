"""L4.5 resolution artifacts for prompt-to-product refusals."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


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
    if "csv" in lower and ("sort" in lower or "сорт" in lower) and "csv_sort_cli" in known:
        return {
            "hypothesis_type": "successful_existing_resolution",
            "proposal": {
                "resolution_id": "map_to_existing_csv_sort_cli",
                "means_used": ["known_template:csv_sort_cli", "prompt_to_product_gate"],
                "verification_plan": ["rerun deterministic gate with supported_template=csv_sort_cli", "build package", "run pytest"],
                "kb_candidate": {
                    "pattern": "CSV sort prompts map to csv_sort_cli",
                    "role_scope": "prompt_to_product",
                    "evidence_strength": "weak",
                },
                "actions": ["record_successful_resolution_candidate"],
            },
            "confidence": 0.82,
            "evidence_refs": ["known_templates.csv_sort_cli", "PromptAdequacyGate.status=ready"],
            "risks": ["mapping must be rerun through deterministic gate", "KB promotion requires repeated successes"],
            "return_to_gate": True,
        }
    if _looks_like_image_contents(lower) and "image_contents_cli" in known:
        return {
            "hypothesis_type": "successful_existing_resolution",
            "proposal": {
                "resolution_id": "map_to_existing_image_contents_cli",
                "means_used": ["known_template:image_contents_cli", "prompt_intake_semantic_interpretation"],
                "verification_plan": [
                    "rerun deterministic gate after intake interpretation",
                    "build image_contents_cli package",
                    "run project-scoped pytest",
                ],
                "kb_candidate": {
                    "pattern": "Short image contents CLI prompts map to image_contents_cli",
                    "role_scope": "prompt_to_product",
                    "evidence_strength": "weak",
                },
                "actions": ["record_successful_resolution_candidate"],
            },
            "confidence": 0.78,
            "evidence_refs": ["known_templates.image_contents_cli", "PromptAdequacyGate.status=needs_clarification"],
            "risks": ["short prompt may still need output format clarification", "KB promotion requires repeated successes"],
            "return_to_gate": True,
        }
    return developer_improvement_request(prompt)


def developer_improvement_request(prompt: str) -> dict[str, Any]:
    lower = prompt.lower()
    if _looks_like_image_contents(lower):
        request_id = "add_image_contents_cli_route"
        missing = "image_contents_cli_template_or_vision_analysis_capability"
        acceptance = [
            "image input path accepted by CLI",
            "visible contents returned as JSON items/summary/limitations",
            "vision analyzer is optional/injectable for tests",
            "missing, unsupported, and unavailable-backend errors are controlled",
        ]
    elif "ocr" in lower or "распозна" in lower:
        request_id = "add_ocr_image_cli_route"
        missing = "ocr_image_cli_template_or_image_ocr_capability"
        acceptance = [
            "image input path accepted by CLI",
            "recognized text written to stdout or text file",
            "OCR backend is optional/injectable for tests",
            "missing and unsupported images have controlled errors",
        ]
    else:
        request_id = "add_stage2_template_or_generic_cli_builder"
        missing = "supported_existing_means_for_prompt_to_product"
        acceptance = ["bounded prompt can be built or explicitly rejected", "tests and README are generated"]
    return {
        "hypothesis_type": "developer_improvement_request",
        "proposal": {
            "request_id": request_id,
            "missing_capability": missing,
            "problem": "L4.5 could not solve this adequate prompt with existing templates/capabilities.",
            "prompt_excerpt": prompt[:240],
            "suggested_work": [
                "add or generalize a Stage 2 template only after developer review",
                "add teacher-reference and tests",
                "rerun prompt-to-product and field trial",
            ],
            "acceptance_focus": acceptance,
            "actions": ["record_developer_improvement_request"],
        },
        "confidence": 0.76,
        "evidence_refs": ["PromptAdequacyGate.status=ready", "prompt_product_gate.supported_template=null"],
        "risks": ["existing means may be incomplete", "developer must verify before changing runtime/KB"],
        "return_to_gate": True,
    }


def _looks_like_image_contents(lower: str) -> bool:
    has_image = any(marker in lower for marker in ("image", "picture", "photo", "изображ", "картин", "фото", "png", "jpg", "jpeg", "webp"))
    has_contents = any(marker in lower for marker in ("content", "contents", "list", "objects", "перечисл", "содерж", "объект", "опиши"))
    has_ocr = "ocr" in lower or "распозна" in lower
    return has_image and has_contents and not has_ocr


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
