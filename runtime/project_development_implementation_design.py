"""Admission boundary for Architect design after a human-approved candidate."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def build_implementation_design_request(
    *,
    candidate: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    design_policy = _design_policy(policy)
    target = str(candidate.get("target") or "")
    candidate_id = str(candidate.get("candidate_id") or "")
    active_operator = dict(candidate.get("active_kb_operator") or {})
    return {
        "artifact_type": "ProjectDevelopmentImplementationDesignRequest",
        "status": "requested",
        "request_id": f"design:{candidate_id}",
        "candidate_id": candidate_id,
        "proposal_id": candidate.get("proposal_id"),
        "evidence_digest": candidate.get("evidence_digest"),
        "target": target,
        "design_scope": {
            "targets": [target] if target else [],
            "maximum_targets": int(design_policy.get("maximum_targets") or 0),
            "purpose": "produce a bounded implementation design without executable artifacts",
        },
        "required_outputs": list(design_policy.get("required_outputs") or []),
        "forbidden_outputs": list(design_policy.get("forbidden_outputs") or []),
        "suggested_implementation_recipe": _recipe_from_operator(active_operator),
        "constraints": _design_constraints(),
    }


def admit_implementation_design(
    *,
    request: dict[str, Any],
    candidate: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    design_policy = _design_policy(policy)
    scope = dict(request.get("design_scope") or {})
    candidate_constraints = dict(candidate.get("constraints") or {})
    request_constraints = dict(request.get("constraints") or {})
    active_operator = dict(candidate.get("active_kb_operator") or {})
    checks = {
        "design_gate_is_enabled": design_policy.get("enabled") is True,
        "candidate_status_is_allowed": candidate.get("status")
        in set(design_policy.get("allowed_candidate_statuses") or []),
        "candidate_identity_matches": request.get("candidate_id") == candidate.get("candidate_id"),
        "proposal_identity_matches": request.get("proposal_id") == candidate.get("proposal_id"),
        "evidence_digest_matches": request.get("evidence_digest") == candidate.get("evidence_digest"),
        "target_identity_matches": request.get("target") == candidate.get("target"),
        "single_target_scope": (
            scope.get("targets") == [candidate.get("target")]
            and int(scope.get("maximum_targets") or 0) == 1
            and design_policy.get("maximum_targets") == 1
        ),
        "required_outputs_are_closed": request.get("required_outputs")
        == design_policy.get("required_outputs"),
        "forbidden_outputs_are_closed": request.get("forbidden_outputs")
        == design_policy.get("forbidden_outputs"),
        "suggested_recipe_matches_active_operator": request.get("suggested_implementation_recipe")
        == _recipe_from_operator(active_operator),
        "automatic_role_invocation_is_forbidden": (
            design_policy.get("automatic_role_invocation") is False
            and request_constraints.get("automatic_role_invocation") is False
        ),
        "execution_is_forbidden": (
            design_policy.get("execution_authorized") is False
            and request_constraints.get("execution_authorized") is False
            and candidate_constraints.get("execution_authorized") is False
        ),
        "developer_handoff_is_forbidden": (
            request_constraints.get("developer_handoff_allowed") is False
            and candidate_constraints.get("developer_handoff_allowed") is False
        ),
        "executor_rerun_is_forbidden": request_constraints.get("executor_rerun_allowed") is False,
        "source_changes_are_forbidden": request_constraints.get("source_changes_allowed") is False,
    }
    ready = all(checks.values())
    return {
        "artifact_type": "ProjectDevelopmentImplementationDesignAdmission",
        "status": "ready_for_architect_design" if ready else "blocked",
        "checks": checks,
        "blocking_reasons": [name for name, passed in checks.items() if not passed],
        "request_id": request.get("request_id"),
        "candidate_id": candidate.get("candidate_id"),
        "next_role": "architect" if ready else "human",
        "automatic_role_invocation": False,
        "execution_authorized": False,
    }


def validate_implementation_design(
    *,
    design: dict[str, Any] | None,
    request: dict[str, Any],
    admission: dict[str, Any],
    candidate: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any] | None:
    """Validate an explicitly supplied Architect design without authorizing execution."""
    if design is None:
        return None
    design_policy = _design_policy(policy)
    snapshot = dict(dict(candidate.get("evidence_summary") or {}).get("source_snapshot") or {})
    primary = dict(snapshot.get("primary") or {})
    required_outputs = list(design_policy.get("required_outputs") or [])
    forbidden_outputs = set(design_policy.get("forbidden_outputs") or [])
    constraints = dict(design.get("constraints") or {})
    active_operator = dict(candidate.get("active_kb_operator") or {})
    expected_recipe = _recipe_from_operator(active_operator)
    checks = {
        "design_gate_is_ready": admission.get("status") == "ready_for_architect_design",
        "artifact_type_is_valid": (
            design.get("artifact_type") == "ProjectDevelopmentImplementationDesign"
        ),
        "status_is_non_executable": design.get("status")
        in set(design_policy.get("design_statuses") or []),
        "authority_is_architect": design.get("authority")
        in set(design_policy.get("allowed_authorities") or []),
        "request_identity_matches": design.get("request_id") == request.get("request_id"),
        "candidate_identity_matches": design.get("candidate_id") == candidate.get("candidate_id"),
        "proposal_identity_matches": design.get("proposal_id") == candidate.get("proposal_id"),
        "evidence_digest_matches": design.get("evidence_digest") == candidate.get("evidence_digest"),
        "target_identity_matches": design.get("target") == candidate.get("target"),
        "source_digest_matches": bool(primary.get("after"))
        and design.get("source_sha256") == primary.get("after"),
        "required_outputs_are_present": all(bool(design.get(name)) for name in required_outputs),
        "active_recipe_is_preserved": (
            not expected_recipe or design.get("implementation_recipe") == expected_recipe
        ),
        "forbidden_outputs_are_absent": not _contains_forbidden_key(design, forbidden_outputs),
        "execution_is_forbidden": constraints.get("execution_authorized") is False,
        "developer_handoff_is_forbidden": constraints.get("developer_handoff_allowed") is False,
        "executor_rerun_is_forbidden": constraints.get("executor_rerun_allowed") is False,
        "source_changes_are_forbidden": constraints.get("source_changes_allowed") is False,
        "memory_promotion_is_forbidden": constraints.get("memory_promotion_allowed") is False,
    }
    accepted = all(checks.values())
    return {
        "artifact_type": "ProjectDevelopmentImplementationDesignValidation",
        "status": (
            str(list(design_policy.get("validation_statuses") or ["accepted_not_executable"])[0])
            if accepted
            else "blocked"
        ),
        "checks": checks,
        "blocking_reasons": [name for name, passed in checks.items() if not passed],
        "request_id": request.get("request_id"),
        "candidate_id": candidate.get("candidate_id"),
        "design_digest": _artifact_digest(design),
        "design_accepted": accepted,
        "next_gate": design_policy.get("next_gate") if accepted else "human",
        "execution_authorized": False,
    }


def _contains_forbidden_key(value: Any, forbidden: set[str]) -> bool:
    if isinstance(value, dict):
        if any(str(key) in forbidden for key in value):
            return True
        return any(_contains_forbidden_key(item, forbidden) for item in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_key(item, forbidden) for item in value)
    return False


def _artifact_digest(artifact: dict[str, Any]) -> str:
    encoded = json.dumps(
        artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _design_constraints() -> dict[str, Any]:
    return {
        "automatic_role_invocation": False,
        "execution_authorized": False,
        "developer_handoff_allowed": False,
        "executor_rerun_allowed": False,
        "source_changes_allowed": False,
        "implementation_plan_allowed": False,
        "source_patch_allowed": False,
    }


def _recipe_from_operator(operator: dict[str, Any]) -> dict[str, Any] | None:
    if not operator:
        return None
    applicability = dict(operator.get("applicability") or {})
    return {
        "operator_id": operator.get("id"),
        "reconstruction_method": operator.get("reconstruction_method"),
        "state_strategy": operator.get("state_strategy"),
        "maximum_required_constructor_inputs": applicability.get("maximum_required_constructor_inputs"),
        "required_constructor_inputs_source": "target_constructor",
        "source": "active_kb_operator",
    }


def _design_policy(policy: dict[str, Any]) -> dict[str, Any]:
    revision = dict(dict(policy.get("feedback_policy") or {}).get("replan_revision") or {})
    experiment = dict(revision.get("bounded_experiment") or {})
    approval = dict(experiment.get("human_approval") or {})
    return dict(approval.get("implementation_design") or {})
