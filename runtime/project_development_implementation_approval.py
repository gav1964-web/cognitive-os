"""Digest-bound human approval for a non-executable implementation candidate."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def build_implementation_approval_request(
    *,
    evidence: dict[str, Any],
    architect_decision: dict[str, Any],
    proposal: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    approval_policy = _approval_policy(policy)
    digest = _artifact_digest(evidence)
    proposal_id = str(proposal.get("proposal_id") or "")
    request_id = f"approval:{proposal_id}:{digest[:16]}"
    return {
        "artifact_type": "ProjectDevelopmentImplementationApprovalRequest",
        "status": "awaiting_human_approval",
        "request_id": request_id,
        "proposal_id": proposal_id,
        "evidence_digest": digest,
        "target": proposal.get("target"),
        "requested_decisions": list(approval_policy.get("allowed_decisions") or []),
        "risk_summary": {
            "architect_decision": architect_decision.get("decision"),
            "bounded_implementation_evidence": True,
            "kb_promotion_evidence": False,
            "execution_reviewed": False,
            "implementation_reviewed": False,
        },
        "constraints": _candidate_constraints(),
    }


def validate_implementation_approval(
    *,
    request: dict[str, Any],
    human_decision: dict[str, Any] | None,
    policy: dict[str, Any],
) -> dict[str, Any]:
    approval_policy = _approval_policy(policy)
    if human_decision is None:
        return {
            "artifact_type": "ProjectDevelopmentImplementationApprovalValidation",
            "status": "pending",
            "checks": {"human_decision_is_present": False},
            "blocking_reasons": ["human_decision_is_present"],
            "request_id": request.get("request_id"),
            "decision": None,
            "candidate_allowed": False,
            "execution_authorized": False,
        }
    checks = {
        "artifact_type_is_valid": (
            human_decision.get("artifact_type") == "ProjectDevelopmentHumanApprovalDecision"
        ),
        "decision_is_final": human_decision.get("status") == "decided",
        "decision_is_allowed": human_decision.get("decision")
        in set(approval_policy.get("allowed_decisions") or []),
        "authority_is_allowed": human_decision.get("authority")
        in set(approval_policy.get("allowed_authorities") or []),
        "request_identity_matches": human_decision.get("request_id") == request.get("request_id"),
        "proposal_identity_matches": human_decision.get("proposal_id") == request.get("proposal_id"),
        "evidence_digest_matches": human_decision.get("evidence_digest")
        == request.get("evidence_digest"),
        "human_reason_is_present": bool(human_decision.get("reason")),
        "execution_remains_forbidden": approval_policy.get("execution_authorized") is False,
    }
    valid = all(checks.values())
    decision = str(human_decision.get("decision") or "")
    status = "approved" if valid and decision == "approve" else "rejected" if valid else "blocked"
    return {
        "artifact_type": "ProjectDevelopmentImplementationApprovalValidation",
        "status": status,
        "checks": checks,
        "blocking_reasons": [name for name, passed in checks.items() if not passed],
        "request_id": request.get("request_id"),
        "decision": decision or None,
        "candidate_allowed": status == "approved",
        "execution_authorized": False,
    }


def build_bounded_implementation_candidate(
    *,
    request: dict[str, Any],
    validation: dict[str, Any],
    human_decision: dict[str, Any] | None,
    evidence: dict[str, Any],
    proposal: dict[str, Any],
) -> dict[str, Any] | None:
    if validation.get("status") != "approved" or validation.get("candidate_allowed") is not True:
        return None
    target = str(proposal.get("target") or "")
    hypothesis_kind = str(proposal.get("hypothesis_kind") or "")
    active_operator = dict(proposal.get("active_kb_operator") or {})
    return {
        "artifact_type": "ProjectDevelopmentBoundedImplementationCandidate",
        "status": "approved_not_executable",
        "candidate_id": f"candidate:{proposal.get('proposal_id')}:{request['evidence_digest'][:16]}",
        "proposal_id": proposal.get("proposal_id"),
        "target": target,
        "hypothesis_kind": hypothesis_kind,
        "active_kb_operator": active_operator or None,
        "implementation_intent": {
            "strategy": proposal.get("strategy"),
            "scope": [target] if target else [],
            "purpose": f"Prepare a bounded implementation design for {hypothesis_kind}",
        },
        "evidence_digest": request.get("evidence_digest"),
        "approval_binding": {
            "request_id": request.get("request_id"),
            "authority": dict(human_decision or {}).get("authority"),
            "decision": dict(human_decision or {}).get("decision"),
            "reason": dict(human_decision or {}).get("reason"),
        },
        "acceptance_requirements": list(proposal.get("evidence_requirements") or []),
        "evidence_summary": {
            "collector": evidence.get("collector"),
            "source_snapshot": evidence.get("source_snapshot"),
            "kb_promotion_evidence": False,
        },
        "constraints": _candidate_constraints(),
    }


def _artifact_digest(artifact: dict[str, Any]) -> str:
    encoded = json.dumps(
        artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _candidate_constraints() -> dict[str, Any]:
    return {
        "execution_authorized": False,
        "developer_handoff_allowed": False,
        "executor_rerun_allowed": False,
        "source_changes_allowed": False,
        "memory_promotion_allowed": False,
        "next_gate": "separate_implementation_design_admission",
    }


def _approval_policy(policy: dict[str, Any]) -> dict[str, Any]:
    revision = dict(dict(policy.get("feedback_policy") or {}).get("replan_revision") or {})
    experiment = dict(revision.get("bounded_experiment") or {})
    return dict(experiment.get("human_approval") or {})
