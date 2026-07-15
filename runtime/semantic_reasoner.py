"""Bounded L4.5 semantic hypothesis contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from .local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat


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
            "required_step": "emit_l4_semantic_validation_result_then_rerun_deterministic_gate",
        },
        "principle": "L4.5 may propose bounded hypotheses; L4.0 gates decide whether anything can proceed",
    }


def run_semantic_reasoner(
    *,
    request: dict[str, Any],
    proposal_provider: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    config: LocalInferenceConfig | None = None,
    use_model: bool = False,
) -> dict[str, Any]:
    raw_proposal: dict[str, Any]
    model_error: str | None = None
    model_used = False
    if proposal_provider is not None:
        raw_proposal = proposal_provider(request)
    elif use_model:
        try:
            raw_proposal = _model_proposal(request, config=config)
            model_used = True
        except LocalInferenceError as exc:
            raw_proposal = _deterministic_proposal(request)
            model_error = str(exc)
    else:
        raw_proposal = _deterministic_proposal(request)
    proposal = _harden_proposal(request, raw_proposal)
    proposal["hardening"]["raw_model_output_used"] = model_used
    if model_error is not None:
        proposal["hardening"]["model_error"] = model_error
        proposal["hardening"]["fallback"] = "deterministic_proposal"
    validation = validate_semantic_hypothesis_proposal(request=request, proposal=proposal)
    if validation["status"] != "ok":
        return {
            "artifact_type": "SemanticHypothesisProposal",
            "layer": "L4.5",
            "status": "blocked",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "hypothesis_type": "invalid_proposal",
            "proposal": {},
            "confidence": 0.0,
            "evidence_refs": [],
            "risks": validation["violations"],
            "return_to_gate": False,
            "validation": validation,
        }
    proposal["validation"] = validation
    return proposal


def build_stage2_template_backlog_item(proposal: dict[str, Any]) -> dict[str, Any] | None:
    if proposal.get("status") != "ok" or proposal.get("hypothesis_type") != "new_template_candidate":
        return None
    data = dict(proposal.get("proposal", {}))
    return {
        "artifact_type": "Stage2TemplateBacklogItem",
        "status": "candidate",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "template_id": data.get("template_id") or "unclassified_template_candidate",
        "system_type": data.get("system_type"),
        "purpose": data.get("purpose"),
        "acceptance_focus": list(data.get("acceptance_focus") or []),
        "source": "L4.5 SemanticHypothesisProposal",
        "requires_human_review": True,
        "forbidden_auto_actions": ["build_package", "edit_runtime_templates", "mutate_registry"],
        "next_step": "human_or_engineer_reviews_candidate_before_adding_deterministic_template",
    }


def validate_semantic_hypothesis_proposal(*, request: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    required = list(dict(request.get("output_contract", {})).get("required_fields") or [])
    missing = [field for field in required if field not in proposal]
    allowed = set(str(item) for item in request.get("allowed_hypothesis_types", []))
    violations: list[str] = []
    if missing:
        violations.append(f"missing_fields:{','.join(missing)}")
    if proposal.get("hypothesis_type") not in allowed:
        violations.append(f"hypothesis_type_not_allowed:{proposal.get('hypothesis_type')}")
    if not isinstance(proposal.get("proposal"), dict):
        violations.append("proposal_must_be_object")
    if not isinstance(proposal.get("evidence_refs"), list):
        violations.append("evidence_refs_must_be_list")
    if not isinstance(proposal.get("risks"), list):
        violations.append("risks_must_be_list")
    if not isinstance(proposal.get("return_to_gate"), bool):
        violations.append("return_to_gate_must_be_bool")
    try:
        confidence = float(proposal.get("confidence"))
    except (TypeError, ValueError):
        confidence = -1.0
    if confidence < 0.0 or confidence > 1.0:
        violations.append("confidence_out_of_range")
    forbidden = set(str(item) for item in request.get("forbidden_actions", []))
    proposed_actions = set(str(item) for item in dict(proposal.get("proposal", {})).get("actions", []))
    forbidden_used = sorted(forbidden & proposed_actions)
    if forbidden_used:
        violations.append(f"forbidden_actions_requested:{','.join(forbidden_used)}")
    return {
        "status": "blocked" if violations else "ok",
        "violations": violations,
        "required_fields": required,
        "allowed_hypothesis_types": sorted(allowed),
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


def _deterministic_proposal(request: dict[str, Any]) -> dict[str, Any]:
    reasons = [str(item) for item in request.get("trigger_reasons", [])]
    mode = str(dict(request.get("source_decision", {})).get("mode") or "")
    context = dict(request.get("evidence_context", {}))
    prompt = str(context.get("prompt") or "")
    if mode == "prompt_to_product" and "no_supported_package_template" in reasons:
        return _new_template_candidate(prompt)
    if "unsupported_system_type_requires_semantic_classification" in reasons:
        return _unsupported_reason(prompt)
    if "semantic_rework_after_contracts_passed" in reasons:
        return _rework_target(request)
    return _knowledge_gap(request)


def _model_proposal(request: dict[str, Any], *, config: LocalInferenceConfig | None) -> dict[str, Any]:
    result = call_json_chat(_messages(request), config=config)
    if not isinstance(result, dict):
        raise LocalInferenceError("L4.5 model proposal must be a JSON object")
    return result


def _messages(request: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Cognitive OS L4.5 Semantic Reasoner. Return only JSON that matches "
                "the requested SemanticHypothesisProposal contract. You may propose hypotheses, "
                "but you must not execute, build packages, edit source, mutate registries, promote "
                "capabilities, or bypass gates."
            ),
        },
        {
            "role": "user",
            "content": (
                "Build a bounded semantic hypothesis proposal for this request. "
                "Use only allowed_hypothesis_types and respect forbidden_actions.\n"
                f"{request}"
            ),
        },
    ]


def _harden_proposal(request: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    proposal = {
        "artifact_type": "SemanticHypothesisProposal",
        "layer": "L4.5",
        "status": "ok",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_request": {
            "trigger_reasons": list(request.get("trigger_reasons", [])),
            "source_decision": dict(request.get("source_decision", {})),
        },
        "hypothesis_type": raw.get("hypothesis_type"),
        "proposal": dict(raw.get("proposal", {})) if isinstance(raw.get("proposal"), dict) else {},
        "confidence": _bounded_float(raw.get("confidence"), default=0.5),
        "evidence_refs": list(raw.get("evidence_refs", [])) if isinstance(raw.get("evidence_refs"), list) else [],
        "risks": list(raw.get("risks", [])) if isinstance(raw.get("risks"), list) else [],
        "return_to_gate": bool(raw.get("return_to_gate", True)),
        "hardening": {
            "raw_model_output_used": False,
            "forbidden_actions_stripped": False,
            "schema_normalized": True,
        },
    }
    if proposal["hypothesis_type"] == "clarification_question" and not proposal["proposal"]:
        proposal["proposal"] = {
            "question": request.get("question"),
            "actions": ["ask_clarification"],
        }
    elif proposal["hypothesis_type"] == "unsupported_reason" and not proposal["proposal"]:
        proposal["proposal"] = {
            "reason": "L4.5 could not map the request into a supported bounded route.",
            "actions": ["stop_unsupported"],
        }
    forbidden = set(str(item) for item in request.get("forbidden_actions", []))
    actions = list(proposal["proposal"].get("actions", []))
    safe_actions = [str(item) for item in actions if str(item) not in forbidden]
    if len(safe_actions) != len(actions):
        proposal["proposal"]["actions"] = safe_actions
        proposal["hardening"]["forbidden_actions_stripped"] = True
    return proposal


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
