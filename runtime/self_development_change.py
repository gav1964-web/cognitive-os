"""Typed, fail-closed protocol for bounded Cognitive OS self-development."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "self_development_change_policy.json"
PROPOSAL_SCHEMA = "self_development_change_proposal.v1"


class SelfDevelopmentChangeError(ValueError):
    """Raised when the change policy or a proposal violates its contract."""


@lru_cache(maxsize=1)
def load_self_development_change_policy(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else POLICY_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "self_development_change_policy.v1":
        raise SelfDevelopmentChangeError("self-development policy schema mismatch")
    if payload.get("status") != "active":
        raise SelfDevelopmentChangeError("self-development policy must be active")
    classes = payload.get("classes")
    if not isinstance(classes, dict) or set(classes) != {"L0", "L1", "L2", "L3", "L4"}:
        raise SelfDevelopmentChangeError("self-development policy must define L0 through L4")
    actions = payload.get("actions")
    if actions != ["propose", "sandbox", "promote", "apply"]:
        raise SelfDevelopmentChangeError("self-development policy actions are invalid")
    if payload.get("default_unknown_class") != "L4":
        raise SelfDevelopmentChangeError("unknown changes must default to L4")
    if payload.get("class_precedence") != ["L4", "L3", "L2", "L1", "L0"]:
        raise SelfDevelopmentChangeError("self-development class precedence is invalid")
    known_kinds: set[str] = set()
    for class_id, profile_value in classes.items():
        profile = dict(profile_value or {})
        kinds = profile.get("target_kinds")
        authority = profile.get("authority")
        if not isinstance(kinds, list) or not kinds or not all(isinstance(item, str) and item for item in kinds):
            raise SelfDevelopmentChangeError(f"{class_id} requires target kinds")
        overlap = known_kinds.intersection(kinds)
        if overlap:
            raise SelfDevelopmentChangeError(f"target kinds belong to multiple classes: {sorted(overlap)}")
        known_kinds.update(kinds)
        if not isinstance(authority, dict) or set(authority) != set(actions):
            raise SelfDevelopmentChangeError(f"{class_id} authority matrix is incomplete")
    invariants = dict(payload.get("invariants") or {})
    if not all(invariants.get(name) is True for name in (
        "proposal_is_not_execution_authority",
        "unknown_target_kind_fails_closed",
        "same_change_cannot_replace_its_success_evaluator",
        "source_apply_requires_separate_authority",
    )) or invariants.get("runtime_patch_auto_promotion") is not False:
        raise SelfDevelopmentChangeError("self-development safety invariants are invalid")
    return payload


def classify_self_development_change(
    change: dict[str, Any],
    impact_map: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rules = policy or load_self_development_change_policy()
    target_kind = str(change.get("target_kind") or "")
    matched = [
        class_id
        for class_id, profile in dict(rules["classes"]).items()
        if target_kind in set(dict(profile).get("target_kinds") or [])
    ]
    known = len(matched) == 1
    class_id = matched[0] if known else str(rules.get("default_unknown_class") or "L4")
    impact = dict(impact_map or {})
    if impact.get("changes_evaluator_architecture") is True:
        class_id = "L4"
        known = target_kind == "evaluator_architecture"
    profile = dict(rules["classes"][class_id])
    sensitive = class_id == "L1" and (
        target_kind in set(profile.get("sensitive_target_kinds") or [])
        or impact.get("changes_admission_or_promotion") is True
        or impact.get("changes_success_measure") is True
    )
    return {
        "class": class_id,
        "variant": "L1-sensitive" if sensitive else class_id,
        "known_target_kind": known,
        "target_kind": target_kind or None,
        "basis": (
            "evaluator_architecture_impact"
            if impact.get("changes_evaluator_architecture") is True
            else "declared_target_kind" if known else "unknown_target_kind_defaulted_to_L4"
        ),
        "classification_review_required": not known or class_id == "L4",
    }


def build_self_development_change_proposal(
    *,
    problem: dict[str, Any],
    hypothesis: dict[str, Any],
    change: dict[str, Any],
    evidence: list[dict[str, Any]],
    impact_map: dict[str, Any],
    verification: dict[str, Any],
    rollback_plan: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rules = policy or load_self_development_change_policy()
    _require_mapping_fields(problem, "problem", ("summary", "failure_signature"))
    _require_mapping_fields(hypothesis, "hypothesis", ("summary", "expected_effect"))
    _require_mapping_fields(change, "change", ("target", "target_kind", "operation"))
    if not evidence or not all(
        isinstance(item, dict) and item.get("artifact_type") for item in evidence
    ):
        raise SelfDevelopmentChangeError("evidence must contain typed evidence records")
    if not isinstance(impact_map, dict) or not isinstance(verification, dict):
        raise SelfDevelopmentChangeError("impact_map and verification must be objects")
    if not isinstance(rollback_plan, dict) or not rollback_plan.get("strategy"):
        raise SelfDevelopmentChangeError("rollback_plan.strategy is required")
    classification = classify_self_development_change(change, impact_map, policy=rules)
    body = {
        "schema_version": PROPOSAL_SCHEMA,
        "problem": dict(problem),
        "hypothesis": dict(hypothesis),
        "change": dict(change),
        "classification": classification,
        "evidence": [dict(item) for item in evidence],
        "impact_map": _normalized_impact_map(impact_map),
        "verification": dict(verification),
        "rollback_plan": dict(rollback_plan),
    }
    proposal_id = f"sdcp_{_digest(body)[:20]}"
    return {
        "artifact_type": "SelfDevelopmentChangeProposal",
        "proposal_id": proposal_id,
        "status": "shadow_candidate",
        **body,
        "constraints": {
            "execution_authorized": False,
            "source_changes_allowed": False,
            "promotion_applied": False,
            "proposal_is_not_authority": True,
        },
    }


def interpret_self_development_change(
    proposal: dict[str, Any],
    *,
    action: str,
    authority: str | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rules = policy or load_self_development_change_policy()
    integrity_errors = _proposal_integrity_errors(proposal, rules)
    if action not in rules["actions"]:
        integrity_errors.append("unknown_action")
    classification = dict(proposal.get("classification") or {})
    class_id = str(classification.get("class") or rules["default_unknown_class"])
    if class_id not in rules["classes"]:
        class_id = str(rules["default_unknown_class"])
        integrity_errors.append("unknown_change_class")
    profile = dict(rules["classes"][class_id])
    authority_map = dict(
        profile.get("sensitive_authority")
        if classification.get("variant") == "L1-sensitive"
        else profile.get("authority")
    )
    required_authority = authority_map.get(action) if action in rules["actions"] else None
    required_gates = list(dict(profile.get("required_gates") or {}).get(action) or [])
    if not classification.get("known_target_kind") and action != "propose":
        if "classification_review" not in required_gates:
            required_gates.insert(0, "classification_review")
        required_authority = "external_architect"
    gate_results = {gate: _gate_passed(gate, proposal, authority) for gate in required_gates}
    failed_gates = [name for name, passed in gate_results.items() if not passed]
    authority_present = authority == required_authority
    external_authorities = {"external_architect", "human_merge_authority", "architecture_board"}
    if integrity_errors:
        status = "blocked"
    elif authority is not None and not authority_present:
        status = "blocked"
    elif required_authority in external_authorities and not authority_present:
        status = "external_review_required"
    elif required_authority != "cognitive_os" and not authority_present:
        status = "blocked"
    elif failed_gates:
        status = "blocked"
    else:
        status = "allowed"
    return {
        "artifact_type": "SelfDevelopmentChangeAdmission",
        "proposal_id": proposal.get("proposal_id"),
        "action": action,
        "status": status,
        "change_class": class_id,
        "change_variant": classification.get("variant") or class_id,
        "required_authority": required_authority,
        "provided_authority": authority,
        "authority_present": authority_present,
        "required_gates": required_gates,
        "gate_results": gate_results,
        "blocking_reasons": [*integrity_errors, *failed_gates],
        "execution_authorized": False,
        "source_changes_allowed": False,
        "promotion_applied": False,
    }


def build_shadow_change_dossier(
    proposal: dict[str, Any], *, policy: dict[str, Any] | None = None
) -> dict[str, Any]:
    rules = policy or load_self_development_change_policy()
    admissions = {
        action: interpret_self_development_change(proposal, action=action, policy=rules)
        for action in rules["actions"]
    }
    impact = dict(proposal.get("impact_map") or {})
    return {
        "artifact_type": "SelfDevelopmentShadowDossier",
        "status": "shadow_only",
        "proposal": proposal,
        "architectural_delta": {
            "change_class": dict(proposal.get("classification") or {}).get("class"),
            "target": dict(proposal.get("change") or {}).get("target"),
            "components": list(impact.get("components") or []),
            "roles": list(impact.get("roles") or []),
            "project_types": list(impact.get("project_types") or []),
            "contracts": list(impact.get("contracts") or []),
        },
        "admissions": admissions,
        "constraints": {
            "apply_source": False,
            "promotion_applied": False,
            "external_decision_not_inferred": True,
        },
    }


def build_capability_change_dossier(
    request: dict[str, Any], *, evaluator_fingerprint: str
) -> dict[str, Any]:
    projects = [str(item) for item in list(request.get("observed_projects") or []) if item]
    proposal = build_self_development_change_proposal(
        problem={
            "summary": str(request.get("label") or request.get("missing_capability") or "capability gap"),
            "failure_signature": str(request.get("gap_id") or request.get("request_id") or "unknown_gap"),
        },
        hypothesis={
            "summary": f"Add or repair {request.get('missing_capability') or 'bounded capability'}",
            "expected_effect": "reduce the repeated capability gap without role or project regression",
        },
        change={
            "target": str(request.get("missing_capability") or "unresolved_improvement_capability"),
            "target_kind": "runtime_component",
            "operation": "add_or_repair_bounded_improvement_capability",
            "patch_digest": None,
        },
        evidence=[
            {"artifact_type": "ObservedProjectEvidence", "project": project}
            for project in projects
        ] or [{"artifact_type": "CapabilityGapEvidence", "request_id": request.get("request_id")}],
        impact_map={
            "components": ["self_improvement_runtime"],
            "roles": list(request.get("role_scope") or []),
            "project_types": [],
            "contracts": ["bounded shadow-trial candidate"],
            "changes_evaluator_architecture": False,
            "changes_admission_or_promotion": False,
            "changes_success_measure": False,
        },
        verification={
            "regression_passed": False,
            "independent_holdout_passed": False,
            "independent_evaluator": False,
            "evaluator_fingerprint": evaluator_fingerprint,
            "generated_stub_gate_passed": False,
        },
        rollback_plan={"strategy": "discard sandbox branch and restore promotion snapshot"},
    )
    return build_shadow_change_dossier(proposal)


def _proposal_integrity_errors(proposal: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if proposal.get("artifact_type") != "SelfDevelopmentChangeProposal":
        errors.append("artifact_type_mismatch")
    if proposal.get("schema_version") != PROPOSAL_SCHEMA:
        errors.append("proposal_schema_mismatch")
    classification = classify_self_development_change(
        dict(proposal.get("change") or {}), dict(proposal.get("impact_map") or {}), policy=policy
    )
    if proposal.get("classification") != classification:
        errors.append("classification_mismatch")
    body = {
        key: proposal.get(key)
        for key in (
            "schema_version", "problem", "hypothesis", "change", "classification",
            "evidence", "impact_map", "verification", "rollback_plan",
        )
    }
    if proposal.get("proposal_id") != f"sdcp_{_digest(body)[:20]}":
        errors.append("proposal_digest_mismatch")
    constraints = dict(proposal.get("constraints") or {})
    if constraints.get("execution_authorized") is not False or constraints.get("promotion_applied") is not False:
        errors.append("unsafe_proposal_constraints")
    return errors


def _gate_passed(gate: str, proposal: dict[str, Any], authority: str | None) -> bool:
    change = dict(proposal.get("change") or {})
    verification = dict(proposal.get("verification") or {})
    checks = {
        "classification_review": authority in {"external_architect", "architecture_board"},
        "patch_digest": bool(change.get("patch_digest")),
        "regression": verification.get("regression_passed") is True,
        "independent_holdout": verification.get("independent_holdout_passed") is True,
        "independent_evaluator": verification.get("independent_evaluator") is True,
        "evaluator_fingerprint": bool(verification.get("evaluator_fingerprint")),
        "generated_stub_gate": verification.get("generated_stub_gate_passed") is True,
        "rollback_plan": bool(dict(proposal.get("rollback_plan") or {}).get("strategy")),
    }
    return checks.get(gate, False)


def _normalized_impact_map(impact_map: dict[str, Any]) -> dict[str, Any]:
    return {
        "components": sorted({str(item) for item in list(impact_map.get("components") or []) if item}),
        "roles": sorted({str(item) for item in list(impact_map.get("roles") or []) if item}),
        "project_types": sorted({str(item) for item in list(impact_map.get("project_types") or []) if item}),
        "contracts": sorted({str(item) for item in list(impact_map.get("contracts") or []) if item}),
        "changes_evaluator_architecture": impact_map.get("changes_evaluator_architecture") is True,
        "changes_admission_or_promotion": impact_map.get("changes_admission_or_promotion") is True,
        "changes_success_measure": impact_map.get("changes_success_measure") is True,
    }


def _require_mapping_fields(value: dict[str, Any], label: str, fields: tuple[str, ...]) -> None:
    if not isinstance(value, dict):
        raise SelfDevelopmentChangeError(f"{label} must be an object")
    missing = [field for field in fields if not str(value.get(field) or "").strip()]
    if missing:
        raise SelfDevelopmentChangeError(f"{label} requires fields: {', '.join(missing)}")


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
