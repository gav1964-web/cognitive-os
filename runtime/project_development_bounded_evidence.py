"""Execute admitted read-only research and return bounded evidence to Architect."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .project_development_boundary_interpreter import (
    evaluate_requirement,
    profile_for_hypothesis,
)
from .project_development_source_evidence import (
    collect_python_target_facts,
    target_source_digest,
)


def collect_bounded_experiment_evidence(
    *,
    project_dir: Path,
    workspace_root: Path,
    proposal: dict[str, Any],
    admission: dict[str, Any],
    hypothesis: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    experiment_policy = _experiment_policy(policy)
    target = str(proposal.get("target") or "")
    contrast_source = dict(proposal.get("contrast_source") or {})
    constraints = {
        "read_only": True,
        "network_used": False,
        "subprocess_used": False,
        "source_changes": False,
        "developer_handoff": False,
        "executor_rerun": False,
        "memory_promotion": False,
    }
    admission_ok = (
        admission.get("status") == "admitted_for_planning"
        and admission.get("execution_authorized") is False
    )
    if not admission_ok:
        return _blocked_evidence(proposal, target, constraints, "planning_admission_not_granted")
    before = target_source_digest(project_dir, target)
    facts = collect_python_target_facts(project_dir, target)
    resolved_workspace = workspace_root.resolve()
    contrast_project = (
        resolved_workspace / str(contrast_source.get("project_path") or "")
    ).resolve()
    try:
        contrast_project.relative_to(resolved_workspace)
        contrast_scope_ok = True
    except ValueError:
        contrast_scope_ok = False
    contrast_target = str(contrast_source.get("target") or "")
    contrast_before = (
        target_source_digest(contrast_project, contrast_target) if contrast_scope_ok else None
    )
    contrast_facts = (
        collect_python_target_facts(contrast_project, contrast_target)
        if contrast_scope_ok else {"source_backed": False, "reason": "contrast_outside_workspace"}
    )
    contrast_after = (
        target_source_digest(contrast_project, contrast_target) if contrast_scope_ok else None
    )
    expected_facts = dict(contrast_source.get("expected_facts") or {})
    contrast_facts_match = bool(expected_facts) and all(
        contrast_facts.get(name) == value for name, value in expected_facts.items()
    )
    validation_report = (
        resolved_workspace
        / "artifacts"
        / "project_development"
        / str(contrast_source.get("validation_report") or "")
    ).resolve()
    validation_report_ok = (
        validation_report.parent == (resolved_workspace / "artifacts" / "project_development").resolve()
        and validation_report.is_file()
    )
    contrast_identity_ok = (
        contrast_scope_ok
        and bool(contrast_before)
        and contrast_before == contrast_after
        and contrast_before == str(contrast_source.get("sha256") or "").lower()
        and contrast_facts_match
        and validation_report_ok
    )
    requirement_results = _requirement_results(
        proposal, hypothesis, facts, contrast_facts, contrast_identity_ok
    )
    observations = _observations(
        hypothesis, facts, contrast_source, contrast_facts, requirement_results
    )
    after = target_source_digest(project_dir, target)
    checks = {
        "read_only_research_is_enabled": experiment_policy.get("read_only_research_enabled") is True,
        "target_is_source_backed": facts.get("source_backed") is True,
        "target_matches_hypothesis": target == hypothesis.get("origin_target"),
        "observation_budget_is_preserved": (
            len(observations) <= int(experiment_policy.get("maximum_observations") or 0)
        ),
        "source_digest_is_unchanged": bool(before) and before == after,
        "contrast_is_source_backed": contrast_facts.get("source_backed") is True,
        "contrast_is_inside_workspace": contrast_scope_ok,
        "contrast_facts_match_policy": contrast_facts_match,
        "contrast_validation_report_exists": validation_report_ok,
        "contrast_digest_is_allowlisted": contrast_identity_ok,
        "network_is_forbidden": experiment_policy.get("network_allowed") is False,
        "subprocess_is_forbidden": experiment_policy.get("subprocess_allowed") is False,
        "execution_remains_forbidden": admission.get("execution_authorized") is False,
    }
    failed_requirements = [
        name for name, result in requirement_results.items() if result.get("satisfied") is not True
    ]
    status = "collected" if all(checks.values()) and not failed_requirements else "incomplete"
    return {
        "artifact_type": "ProjectDevelopmentBoundedExperimentEvidence",
        "status": status,
        "proposal_id": proposal.get("proposal_id"),
        "target": target,
        "collector": "embedded_read_only_researcher",
        "source_snapshot": {
            "primary": {"before": before, "after": after, "unchanged": before == after},
            "contrast": {
                "before": contrast_before,
                "after": contrast_after,
                "unchanged": contrast_before == contrast_after,
            },
            "unchanged": before == after and contrast_before == contrast_after,
        },
        "observations": observations,
        "requirement_results": requirement_results,
        "failed_requirements": failed_requirements,
        "checks": checks,
        "blocking_reasons": [name for name, passed in checks.items() if not passed],
        "constraints": constraints,
    }


def decide_bounded_experiment_evidence(
    *,
    evidence: dict[str, Any],
    proposal: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    experiment_policy = _experiment_policy(policy)
    constraints = dict(evidence.get("constraints") or {})
    snapshot = dict(evidence.get("source_snapshot") or {})
    bounded_results = [
        dict(result)
        for result in dict(evidence.get("requirement_results") or {}).values()
        if dict(result or {}).get("bounded_implementation_evidence") is True
    ]
    contrast = bounded_results[0] if len(bounded_results) == 1 else {}
    checks = {
        "evidence_is_collected": evidence.get("status") == "collected",
        "proposal_identity_matches": evidence.get("proposal_id") == proposal.get("proposal_id"),
        "target_identity_matches": evidence.get("target") == proposal.get("target"),
        "all_requirements_are_satisfied": not evidence.get("failed_requirements"),
        "paired_source_contrast_supports_bounded_implementation": (
            contrast.get("authority") == "paired_source_ast"
            and contrast.get("bounded_implementation_evidence") is True
        ),
        "kb_promotion_remains_forbidden": contrast.get("kb_promotion_evidence") is False,
        "source_digest_is_unchanged": snapshot.get("unchanged") is True,
        "research_was_read_only": constraints.get("read_only") is True,
        "network_was_not_used": constraints.get("network_used") is False,
        "subprocess_was_not_used": constraints.get("subprocess_used") is False,
        "execution_remains_forbidden": experiment_policy.get("execution_authorized") is False,
        "memory_promotion_is_forbidden": constraints.get("memory_promotion") is False,
    }
    if all(checks.values()):
        decision = "evidence_accepted"
        next_step = "human_review_bounded_implementation_candidate"
    elif checks["proposal_identity_matches"] and checks["target_identity_matches"]:
        decision = "research_more"
        next_step = "collect_missing_bounded_evidence"
    else:
        decision = "controlled_stop"
        next_step = "human_review_scope_or_identity_failure"
    allowed = set(experiment_policy.get("architect_evidence_decisions") or [])
    if decision not in allowed:
        decision = "controlled_stop"
        next_step = "human_review_policy_failure"
    return {
        "artifact_type": "ProjectDevelopmentArchitectEvidenceDecision",
        "status": "decided",
        "decision": decision,
        "authority": "architect",
        "checks": checks,
        "blocking_reasons": [name for name, passed in checks.items() if not passed],
        "proposal_id": proposal.get("proposal_id"),
        "next_step": next_step,
        "execution_authorized": False,
    }


def _requirement_results(
    proposal: dict[str, Any],
    hypothesis: dict[str, Any],
    facts: dict[str, Any],
    contrast_facts: dict[str, Any],
    contrast_identity_ok: bool,
) -> dict[str, dict[str, Any]]:
    target = str(proposal.get("target") or "")
    profile = profile_for_hypothesis(str(hypothesis.get("hypothesis_kind") or ""))
    context = {
        "target": target,
        "origin_target": hypothesis.get("origin_target"),
        "primary_facts": facts,
        "contrast_facts": contrast_facts,
        "contrast_identity": {"verified": contrast_identity_ok},
    }
    return {
        name: evaluate_requirement(name, profile=profile, context=context)
        for name in proposal.get("evidence_requirements") or []
    }


def _observations(
    hypothesis: dict[str, Any],
    facts: dict[str, Any],
    contrast_source: dict[str, Any],
    contrast_facts: dict[str, Any],
    requirement_results: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    bounded = next(
        (
            dict(result)
            for result in requirement_results.values()
            if dict(result or {}).get("bounded_implementation_evidence") is True
        ),
        {},
    )
    return [
        {"kind": "target_source_facts", "authority": "source_ast", "facts": facts},
        {
            "kind": "negative_shape",
            "authority": "source_ast",
            "maximum_loop_depth": facts.get("maximum_loop_depth"),
            "dict_append_sites": facts.get("dict_append_sites"),
        },
        {
            "kind": "positive_boundary",
            "authority": "source_ast",
            "hypothesis_kind": hypothesis.get("hypothesis_kind"),
            "contrast_id": contrast_source.get("contrast_id"),
            "validation_report": contrast_source.get("validation_report"),
            "facts": contrast_facts,
            "bounded_implementation_evidence": bounded.get("bounded_implementation_evidence") is True,
            "kb_promotion_evidence": False,
        },
    ]


def _blocked_evidence(
    proposal: dict[str, Any],
    target: str,
    constraints: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    return {
        "artifact_type": "ProjectDevelopmentBoundedExperimentEvidence",
        "status": "blocked",
        "proposal_id": proposal.get("proposal_id"),
        "target": target,
        "collector": "not_started",
        "source_snapshot": {
            "primary": {"before": None, "after": None, "unchanged": False},
            "contrast": {"before": None, "after": None, "unchanged": False},
            "unchanged": False,
        },
        "observations": [],
        "requirement_results": {},
        "failed_requirements": list(proposal.get("evidence_requirements") or []),
        "checks": {"planning_admission_is_granted": False},
        "blocking_reasons": [reason],
        "constraints": constraints,
    }


def _experiment_policy(policy: dict[str, Any]) -> dict[str, Any]:
    revision = dict(dict(policy.get("feedback_policy") or {}).get("replan_revision") or {})
    return dict(revision.get("bounded_experiment") or {})
