"""Digest-bound authorization for a single non-applying sandbox implementation run."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def build_implementation_authorization_request(
    *, design: dict[str, Any], design_validation: dict[str, Any], policy: dict[str, Any]
) -> dict[str, Any]:
    authorization = _authorization_policy(policy)
    design_digest = _artifact_digest(design)
    execution_policy_digest = _execution_policy_digest(policy)
    candidate_id = str(design.get("candidate_id") or "")
    return {
        "artifact_type": "ProjectDevelopmentImplementationAuthorizationRequest",
        "status": "awaiting_human_approval",
        "request_id": (
            f"implementation:{candidate_id}:{design_digest[:16]}:{execution_policy_digest[:16]}"
        ),
        "candidate_id": candidate_id,
        "proposal_id": design.get("proposal_id"),
        "design_digest": design_digest,
        "execution_policy_digest": execution_policy_digest,
        "evidence_digest": design.get("evidence_digest"),
        "target": design.get("target"),
        "source_sha256": design.get("source_sha256"),
        "requested_decisions": list(authorization.get("allowed_decisions") or []),
        "prerequisites": {
            "design_status": design.get("status"),
            "design_validation_status": design_validation.get("status"),
        },
        "constraints": _authorization_constraints(),
    }


def validate_implementation_authorization(
    *,
    request: dict[str, Any],
    human_decision: dict[str, Any] | None,
    design: dict[str, Any],
    design_validation: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    authorization = _authorization_policy(policy)
    if human_decision is None:
        return {
            "artifact_type": "ProjectDevelopmentImplementationAuthorizationValidation",
            "status": "pending",
            "checks": {"human_decision_is_present": False},
            "blocking_reasons": ["human_decision_is_present"],
            "request_id": request.get("request_id"),
            "decision": None,
            "sandbox_implementation_authorized": False,
            "source_apply_authorized": False,
        }
    checks = {
        "authorization_is_enabled": authorization.get("enabled") is True,
        "artifact_type_is_valid": human_decision.get("artifact_type")
        == "ProjectDevelopmentImplementationAuthorizationDecision",
        "decision_is_final": human_decision.get("status") == "decided",
        "decision_is_allowed": human_decision.get("decision")
        in set(authorization.get("allowed_decisions") or []),
        "authority_is_allowed": human_decision.get("authority")
        in set(authorization.get("allowed_authorities") or []),
        "request_identity_matches": human_decision.get("request_id") == request.get("request_id"),
        "candidate_identity_matches": human_decision.get("candidate_id")
        == request.get("candidate_id"),
        "design_digest_matches": human_decision.get("design_digest")
        == request.get("design_digest") == _artifact_digest(design),
        "execution_policy_digest_matches": human_decision.get("execution_policy_digest")
        == request.get("execution_policy_digest") == _execution_policy_digest(policy),
        "evidence_digest_matches": human_decision.get("evidence_digest")
        == request.get("evidence_digest") == design.get("evidence_digest"),
        "target_identity_matches": human_decision.get("target")
        == request.get("target") == design.get("target"),
        "source_digest_matches": request.get("source_sha256") == design.get("source_sha256"),
        "design_is_accepted": design_validation.get("status") == "accepted_not_executable"
        and design_validation.get("design_accepted") is True
        and design_validation.get("design_digest") == _artifact_digest(design),
        "reason_is_present": bool(human_decision.get("reason")),
        "source_apply_remains_forbidden": authorization.get("source_apply_allowed") is False,
        "memory_promotion_remains_forbidden": authorization.get("memory_promotion_allowed") is False,
    }
    valid = all(checks.values())
    decision = str(human_decision.get("decision") or "")
    status = "approved" if valid and decision == "approve" else "rejected" if valid else "blocked"
    return {
        "artifact_type": "ProjectDevelopmentImplementationAuthorizationValidation",
        "status": status,
        "checks": checks,
        "blocking_reasons": [name for name, passed in checks.items() if not passed],
        "request_id": request.get("request_id"),
        "decision": decision or None,
        "sandbox_implementation_authorized": status == "approved",
        "source_apply_authorized": False,
    }


def _artifact_digest(artifact: dict[str, Any]) -> str:
    encoded = json.dumps(
        artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _execution_policy_digest(policy: dict[str, Any]) -> str:
    return _artifact_digest({
        "implementation_authorization": _authorization_policy(policy),
        "native_failure_intake": dict(policy.get("native_failure_intake") or {}),
    })


def _authorization_constraints() -> dict[str, Any]:
    return {
        "maximum_targets": 1,
        "sandbox_only": True,
        "targeted_verification_required": True,
        "regression_verification_required": True,
        "generated_function_stubs_allowed": False,
        "source_apply_allowed": False,
        "memory_promotion_allowed": False,
    }


def _authorization_policy(policy: dict[str, Any]) -> dict[str, Any]:
    revision = dict(dict(policy.get("feedback_policy") or {}).get("replan_revision") or {})
    experiment = dict(revision.get("bounded_experiment") or {})
    approval = dict(experiment.get("human_approval") or {})
    design = dict(approval.get("implementation_design") or {})
    return dict(design.get("implementation_authorization") or {})
