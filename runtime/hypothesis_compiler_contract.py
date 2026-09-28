"""Strict contracts for evidence-bound self-improvement hypotheses."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def build_candidate(
    *, candidate_type: str, failure_class: str, portable_signature: str,
    semantic_context: list[str], evidence_refs: list[str], counterexample_refs: list[str],
    invariant: str, desired_effect: str, capability: str, gates: list[str],
    confidence: float = 0.5, model_abstraction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    identity = json.dumps(
        [candidate_type, failure_class, portable_signature, sorted(semantic_context)],
        ensure_ascii=True, separators=(",", ":"),
    )
    candidate = {
        "artifact_type": "HypothesisCandidate",
        "hypothesis_id": f"hc_{hashlib.sha256(identity.encode()).hexdigest()[:12]}",
        "candidate_type": candidate_type,
        "failure_class": failure_class,
        "portable_signature": portable_signature,
        "semantic_context": sorted(set(semantic_context)),
        "abstraction": {
            "invariant": invariant[:800],
            "desired_effect": desired_effect[:800],
            **_model_abstraction(model_abstraction or {}),
        },
        "evidence_refs": sorted(set(evidence_refs)),
        "counterexample_refs": sorted(set(counterexample_refs)),
        "required_plugin_contract": {
            "capability": capability,
            "input": "FailureDiagnosisEnvelope plus compact positive and counterexample evidence",
            "output": "bounded shadow-trial candidate with measurable role effect",
        },
        "validation_plan": {
            "corpus_policy": "existing_frozen_corpus_only",
            "positive_case_count": len(set(evidence_refs)),
            "counterexample_case_count": len(set(counterexample_refs)),
            "gates": list(gates),
        },
        "confidence": round(max(0.0, min(1.0, float(confidence))), 3),
        "authority": "hypothesis_only",
    }
    return candidate


def validate_candidate(
    candidate: dict[str, Any], *, allowed_types: set[str], allowed_capabilities: set[str],
    forbidden_fields: set[str], evidence_refs: set[str], counterexample_refs: set[str],
) -> tuple[dict[str, Any], list[str]]:
    errors = []
    if candidate.get("artifact_type") != "HypothesisCandidate":
        errors.append("artifact_type_invalid")
    if str(candidate.get("candidate_type") or "") not in allowed_types:
        errors.append("candidate_type_not_allowed")
    contract = dict(candidate.get("required_plugin_contract") or {})
    if str(contract.get("capability") or "") not in allowed_capabilities:
        errors.append("capability_not_allowed")
    if not str(dict(candidate.get("abstraction") or {}).get("invariant") or "").strip():
        errors.append("invariant_required")
    supplied = {str(value) for value in candidate.get("evidence_refs") or []}
    controls = {str(value) for value in candidate.get("counterexample_refs") or []}
    if not supplied or not supplied.issubset(evidence_refs):
        errors.append("evidence_refs_unbound")
    if not controls.issubset(counterexample_refs):
        errors.append("counterexample_refs_unbound")
    forbidden = _forbidden_keys(candidate, forbidden_fields)
    if forbidden:
        errors.append("forbidden_fields:" + ",".join(sorted(forbidden)))
    if candidate.get("authority") != "hypothesis_only":
        errors.append("authority_must_be_hypothesis_only")
    return (candidate if not errors else {}), errors


def capability_request(candidate: dict[str, Any]) -> dict[str, Any]:
    """Translate one validated hypothesis into the existing plugin-foundry contract."""
    contract = dict(candidate.get("required_plugin_contract") or {})
    return {
        "artifact_type": "CapabilityDevelopmentRequest",
        "request_id": f"cdr_{str(candidate.get('hypothesis_id') or 'unknown')[3:]}",
        "status": "trial_required",
        "hypothesis_id": candidate.get("hypothesis_id"),
        "gap_id": (
            f"compiled:{candidate.get('failure_class')}:{candidate.get('portable_signature')}"
        ),
        "label": dict(candidate.get("abstraction") or {}).get("invariant"),
        "observed_projects": list(candidate.get("evidence_refs") or []),
        "counterexample_projects": list(candidate.get("counterexample_refs") or []),
        "missing_capability": contract.get("capability"),
        "required_plugin_contract": contract,
        "validation_plan": dict(candidate.get("validation_plan") or {}),
        "intervention_scope": "implement_or_trial_bounded_improvement_plugin_only",
        "forbidden": [
            "manual_project_repair",
            "evaluation_threshold_change",
            "unverified_kb_promotion",
        ],
    }


def _model_abstraction(value: dict[str, Any]) -> dict[str, str]:
    allowed = ("problem_pattern", "applicability", "counterexample_risk")
    return {
        key: str(value[key])[:800]
        for key in allowed if str(value.get(key) or "").strip()
    }


def _forbidden_keys(value: Any, forbidden: set[str]) -> set[str]:
    if isinstance(value, dict):
        return {
            *({str(key) for key in value if str(key) in forbidden}),
            *(key for child in value.values() for key in _forbidden_keys(child, forbidden)),
        }
    if isinstance(value, list):
        return {key for child in value for key in _forbidden_keys(child, forbidden)}
    return set()
