"""LLM-backed diagnosis for a failed Cognitive OS project trial."""

from __future__ import annotations

import json
from typing import Any

from .local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat
from .executable_acceptance_policy import structural_sample_policy
from .project_evolution_policy import load_project_evolution_policy
from .self_improvement_evidence_proposals import attach_evidence_proposal


def diagnose_training_failure(
    failure_packet: dict[str, Any],
    *,
    local_config: LocalInferenceConfig,
    teacher_config: LocalInferenceConfig | None = None,
) -> dict[str, Any]:
    policy = dict(load_project_evolution_policy().get("self_improvement") or {})
    local = _attempt(failure_packet, config=local_config, tier="local_l35")
    threshold = float(policy.get("teacher_confidence_threshold") or 0.78)
    actionable = bool(local.get("recommended_source") or local.get("proposed_knowledge"))
    needs_teacher = (
        local.get("status") != "ok"
        or float(local.get("confidence") or 0.0) < threshold
        or not actionable
    )
    if not needs_teacher or teacher_config is None:
        return local
    teacher_packet = {
        **failure_packet,
        "local_diagnosis": {
            "status": local.get("status"),
            "failure_class": local.get("failure_class"),
            "confidence": local.get("confidence"),
            "error": local.get("error"),
        },
    }
    teacher = _attempt(teacher_packet, config=teacher_config, tier="external_teacher")
    if teacher.get("status") == "ok":
        teacher["escalated_from"] = local.get("model_trace")
        return teacher
    return {**local, "teacher_attempt": teacher, "status": local.get("status", "failed")}


def _attempt(packet: dict[str, Any], *, config: LocalInferenceConfig, tier: str) -> dict[str, Any]:
    try:
        response = call_json_chat(_messages(packet), config=config)
    except LocalInferenceError as exc:
        evidence_class = _evidence_failure_class(packet)
        return {
            "status": "failed", "confidence": 0.0, "error": str(exc),
            "failure_class": evidence_class or "unknown",
            "classification_source": "executable_evidence" if evidence_class else "unavailable",
            "model_trace": _trace(config, tier),
        }
    normalized = _normalize(response)
    normalized = attach_evidence_proposal(packet, normalized)
    evidence_class = _evidence_failure_class(packet)
    if evidence_class:
        normalized["llm_failure_class"] = normalized["failure_class"]
        normalized["failure_class"] = evidence_class
    current = str(packet.get("selected_candidate") or "")
    if current and normalized.get("recommended_source") == current:
        normalized["recommended_source"] = ""
        normalized.setdefault("policy_violations", []).append("same_as_failed_target")
        normalized["status"] = "failed"
    normalized["model_trace"] = _trace(config, tier)
    return normalized


def _evidence_failure_class(packet: dict[str, Any]) -> str:
    policy = dict(load_project_evolution_policy().get("self_improvement") or {})
    taxonomy = dict(policy.get("failure_classification") or {})
    downstream = dict(packet.get("downstream_evidence") or {})
    reason = str(downstream.get("reason") or "")
    reason_map = dict(taxonomy.get("downstream_reason_map") or {})
    if reason in reason_map:
        return str(reason_map[reason])
    evidence = dict(packet.get("artifact_evidence") or {})
    reselection = dict(dict(evidence.get("technical_spec") or {}).get("reselection") or {})
    trigger_map = dict(taxonomy.get("reselection_trigger_map") or {})
    trigger = str(reselection.get("trigger") or "")
    if trigger in trigger_map:
        return str(trigger_map[trigger])
    skipped = dict(dict(downstream.get("summary") or {}).get("skipped_reason_counts") or {})
    skipped_map = dict(taxonomy.get("skipped_reason_map") or {})
    return next((str(skipped_map[key]) for key in sorted(skipped) if key in skipped_map), "")


def _normalize(response: dict[str, Any]) -> dict[str, Any]:
    roles = [str(item) for item in list(response.get("target_roles") or [])]
    allowed_roles = {"project_analyzer", "architect", "spec_writer"}
    roles = [role for role in roles if role in allowed_roles]
    changes = [str(item) for item in list(response.get("parameter_changes") or [])]
    allowed_changes = set(
        dict(load_project_evolution_policy().get("self_improvement") or {}).get("allowed_parameter_changes") or []
    )
    changes = [item for item in changes if item in allowed_changes]
    confidence = max(0.0, min(1.0, float(response.get("confidence") or 0.0)))
    diagnosis = str(response.get("diagnosis") or "")[:1200]
    hypothesis = str(response.get("hypothesis") or "")[:1200]
    proposed_value = response.get("proposed_knowledge")
    proposed = dict(proposed_value) if isinstance(proposed_value, dict) else {}
    proposed, proposal_rejections = _sanitize_proposals(proposed)
    recommended_source = str(response.get("recommended_source") or "")
    generic_knowledge = {
        key: value for key, value in proposed.items()
        if key not in {"config_mutation_proposal", "capability_adapter_proposal"}
    }
    policy_violations = _policy_violations(
        f"{diagnosis} {hypothesis} {json.dumps(generic_knowledge, ensure_ascii=False)}"
    )
    if "config_mutation_proposal" not in proposed:
        changes = [item for item in changes if item != "config_mutation_proposal"]
    status = "ok" if diagnosis and hypothesis and roles and not policy_violations else "failed"
    return {
        "status": status,
        "failure_class": str(response.get("failure_class") or "unknown")[:80],
        "diagnosis": diagnosis,
        "hypothesis": hypothesis,
        "confidence": confidence,
        "target_roles": roles,
        "parameter_changes": changes,
        "proposed_knowledge": proposed,
        "recommended_source": recommended_source,
        "policy_violations": policy_violations,
        "proposal_rejections": proposal_rejections,
    }


def _messages(packet: dict[str, Any]) -> list[dict[str, str]]:
    mutable_keys = ", ".join(sorted(structural_sample_policy()))
    system = (
        "You diagnose a failed Cognitive OS role trial and propose a reusable improvement. Return JSON only. "
        "Do not change evaluation thresholds, score caps, source projects, or active KB. "
        "Diagnose role quality and target selection; transport/context errors are escalation metadata, not the project failure. "
        "When downstream_evidence contains an execution error, explain that concrete contract mismatch and make the "
        "smallest reusable proposal that can change its measured outcome. "
        "Use only supplied evidence. Prefer general KB/config learning over project-specific rules. "
        "Return failure_class, diagnosis, hypothesis, confidence (0..1), target_roles, parameter_changes, "
        "recommended_source, and proposed_knowledge. recommended_source must exactly match one supplied ranked source "
        "and must differ from selected_candidate; use empty when no stronger source exists. Compare candidate reasons, "
        "domain relevance, side effects, and contract shape. target_roles: project_analyzer, architect, spec_writer. "
        "parameter_changes: architect_advisory, spec_writer_advisory, model_tier, staged_kb_candidate, "
        "config_mutation_proposal. A config proposal is optional and must be nested under proposed_knowledge as "
        "config_mutation_proposal with artifact_type ConfigMutationProposal, target "
        "config/executable_acceptance_policy.json, operation merge_object, path /structural_sample_policy, and "
        "a small reusable content object. Omit config_mutation_proposal unless every required field and content key "
        "matches this contract exactly; rejected proposals are discarded and do not improve the diagnosis. "
        "When the evidence proves an undeclared external module is the only blocker, "
        "proposed_knowledge may instead include capability_adapter_proposal with artifact_type "
        "ExecutableCapabilityAdapterProposal, kind generated_module_profile, a Python module name, and profile.attrs. "
        "Each callable attr must use one of: callable_identity, callable_noop, callable_true, callable_empty_list, "
        "callable_empty_string, callable_transport_result, stub_class, safe_method_attribute, "
        "safe_symbolic_attribute, module_getattr_stub. Never include source, code, diff, entrypoint, paths, score, "
        "evaluator, network behavior, or project-specific changes."
        f" Mutable content top-level keys are limited to: {mutable_keys}."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(packet, ensure_ascii=False, separators=(",", ":"))},
    ]


def _trace(config: LocalInferenceConfig, tier: str) -> dict[str, Any]:
    return {"tier": tier, "provider": config.provider_label, "model": config.model}


def _policy_violations(text: str) -> list[str]:
    lowered = text.lower()
    forbidden = {
        "score_manipulation": ("score boost", "boost score", "recalibrat", "lower the threshold", "raise score"),
        "evaluation_change": ("change evaluation", "modify evaluator", "weaken gate"),
    }
    return [code for code, tokens in forbidden.items() if any(token in lowered for token in tokens)]


def _proposal_violations(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, dict):
        return ["config_proposal_must_be_object"]
    expected = {
        "artifact_type": "ConfigMutationProposal",
        "target": "config/executable_acceptance_policy.json",
        "operation": "merge_object",
        "path": "/structural_sample_policy",
    }
    errors = [f"config_proposal_invalid_{key}" for key, expected_value in expected.items()
              if value.get(key) != expected_value]
    content = value.get("content")
    if not isinstance(content, dict) or not content:
        return [*errors, "config_proposal_content_required"]
    allowed = set(structural_sample_policy())
    if set(content) - allowed:
        errors.append("config_proposal_unknown_or_project_specific_keys")
    return errors


def _adapter_proposal_violations(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, dict):
        return ["capability_adapter_proposal_must_be_object"]
    try:
        from .improvement_plugins.executable_adapter_admission import _adapter_from_proposal

        adapter = _adapter_from_proposal(value)
    except (TypeError, ValueError):
        adapter = {}
    return [] if adapter else ["capability_adapter_proposal_invalid_or_unsafe"]


def _sanitize_proposals(proposed: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    result = dict(proposed)
    rejections: list[dict[str, Any]] = []
    validators = {
        "config_mutation_proposal": _proposal_violations,
        "capability_adapter_proposal": _adapter_proposal_violations,
    }
    for key, validator in validators.items():
        if key not in result:
            continue
        value = result[key]
        if value is None:
            violations = [f"{key}_must_be_object"]
        else:
            violations = validator(value)
        violations.extend(
            f"proposal_{code}" for code in _policy_violations(json.dumps(value, ensure_ascii=False))
        )
        if violations:
            result.pop(key, None)
            rejections.append({"proposal": key, "violations": list(dict.fromkeys(violations))})
    return result, rejections
