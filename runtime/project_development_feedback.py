"""Read-only Researcher -> Architect continuation for failed development experiments."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .project_development_bounded_evidence import (
    collect_bounded_experiment_evidence,
    decide_bounded_experiment_evidence,
)
from .project_development_bounded_experiment import (
    admit_bounded_experiment_proposal,
    build_bounded_experiment_proposal,
)
from .project_development_feedback_replan import (
    _build_architect_decision,
    _build_replan_revision,
    _build_research_hypothesis,
    _revision_origin,
)
from .project_development_implementation_approval import (
    build_bounded_implementation_candidate,
    build_implementation_approval_request,
    validate_implementation_approval,
)
from .project_development_implementation_design import (
    admit_implementation_design,
    build_implementation_design_request,
    validate_implementation_design,
)


def run_project_development_feedback_continuation(
    *,
    project_dir: Path,
    feedback: dict[str, Any],
    policy: dict[str, Any],
    baseline_decision: dict[str, Any] | None = None,
    baseline_outcome_contract: dict[str, Any] | None = None,
    workspace_root: Path | None = None,
    human_approval: dict[str, Any] | None = None,
    architect_design: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if feedback.get("decision") != "research":
        return {
            "artifact_type": "ProjectDevelopmentFeedbackContinuation",
            "status": "not_required",
            "research_hypothesis": None,
            "architect_decision": None,
            "replan_revision": None,
            "bounded_experiment_proposal": None,
            "planning_admission": None,
            "bounded_experiment_evidence": None,
            "architect_evidence_decision": None,
            "implementation_approval_request": None,
            "human_approval_decision": None,
            "implementation_approval_validation": None,
            "bounded_implementation_candidate": None,
            "implementation_design_request": None,
            "implementation_design_admission": None,
            "implementation_design": None,
            "implementation_design_validation": None,
            "source_changes": False,
            "executor_rerun": False,
        }
    hypothesis = _build_research_hypothesis(project_dir, feedback)
    decision = _build_architect_decision(feedback, hypothesis, policy)
    revision = None
    proposal = None
    planning_admission = None
    bounded_evidence = None
    evidence_decision = None
    approval_request = None
    approval_validation = None
    implementation_candidate = None
    design_request = None
    design_admission = None
    design_validation = None
    if decision["decision"] == "replan":
        revision = _build_replan_revision(
            feedback=feedback,
            hypothesis=hypothesis,
            architect_decision=decision,
            baseline_decision=baseline_decision,
            baseline_outcome_contract=baseline_outcome_contract,
            policy=policy,
        )
        if revision["status"] == "planning_only":
            proposal = build_bounded_experiment_proposal(
                revision=revision,
                hypothesis=hypothesis,
                policy=policy,
            )
            planning_admission = admit_bounded_experiment_proposal(
                proposal=proposal,
                revision=revision,
                hypothesis=hypothesis,
                policy=policy,
            )
            if planning_admission["status"] == "admitted_for_planning":
                bounded_evidence = collect_bounded_experiment_evidence(
                    project_dir=project_dir,
                    workspace_root=workspace_root or Path(__file__).resolve().parents[1],
                    proposal=proposal,
                    admission=planning_admission,
                    hypothesis=hypothesis,
                    policy=policy,
                )
                evidence_decision = decide_bounded_experiment_evidence(
                    evidence=bounded_evidence,
                    proposal=proposal,
                    policy=policy,
                )
                if evidence_decision["decision"] == "evidence_accepted":
                    approval_request = build_implementation_approval_request(
                        evidence=bounded_evidence,
                        architect_decision=evidence_decision,
                        proposal=proposal,
                        policy=policy,
                    )
                    approval_validation = validate_implementation_approval(
                        request=approval_request,
                        human_decision=human_approval,
                        policy=policy,
                    )
                    implementation_candidate = build_bounded_implementation_candidate(
                        request=approval_request,
                        validation=approval_validation,
                        human_decision=human_approval,
                        evidence=bounded_evidence,
                        proposal=proposal,
                    )
                    if implementation_candidate is not None:
                        design_request = build_implementation_design_request(
                            candidate=implementation_candidate,
                            policy=policy,
                        )
                        design_admission = admit_implementation_design(
                            request=design_request,
                            candidate=implementation_candidate,
                            policy=policy,
                        )
                        design_validation = validate_implementation_design(
                            design=architect_design,
                            request=design_request,
                            admission=design_admission,
                            candidate=implementation_candidate,
                            policy=policy,
                        )
    status = {
        "replan": "replan_ready",
        "research_more": "research_required",
        "controlled_stop": "controlled_stop",
    }[str(decision["decision"])]
    if revision is not None and revision["status"] != "planning_only":
        status = "controlled_stop"
    elif planning_admission is not None:
        if planning_admission["status"] != "admitted_for_planning":
            status = "controlled_stop"
        elif evidence_decision is not None:
            status = {
                "evidence_accepted": "awaiting_human_approval",
                "research_more": "research_required",
                "controlled_stop": "controlled_stop",
            }[str(evidence_decision["decision"])]
            if approval_validation is not None:
                status = {
                    "pending": "awaiting_human_approval",
                    "approved": "implementation_candidate_approved",
                    "rejected": "human_rejected",
                    "blocked": "controlled_stop",
                }[str(approval_validation["status"])]
                if design_admission is not None:
                    status = (
                        "implementation_design_ready"
                        if design_admission["status"] == "ready_for_architect_design"
                        else "controlled_stop"
                    )
                    if design_validation is not None:
                        status = (
                            "implementation_designed"
                            if design_validation["status"] == "accepted_not_executable"
                            else "controlled_stop"
                        )
    return {
        "artifact_type": "ProjectDevelopmentFeedbackContinuation",
        "status": status,
        "research_hypothesis": hypothesis,
        "architect_decision": decision,
        "replan_revision": revision,
        "bounded_experiment_proposal": proposal,
        "planning_admission": planning_admission,
        "bounded_experiment_evidence": bounded_evidence,
        "architect_evidence_decision": evidence_decision,
        "implementation_approval_request": approval_request,
        "human_approval_decision": human_approval if approval_request is not None else None,
        "implementation_approval_validation": approval_validation,
        "bounded_implementation_candidate": implementation_candidate,
        "implementation_design_request": design_request,
        "implementation_design_admission": design_admission,
        "implementation_design": architect_design if design_request is not None else None,
        "implementation_design_validation": design_validation,
        "source_changes": False,
        "executor_rerun": False,
    }


__all__ = ["run_project_development_feedback_continuation"]
