"""Role-chain handoff construction for project development."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .interpreter_runtime_governance import (
    build_verified_runtime_transition,
    evidence_record,
    project_target_scope,
)
from .project_development_delta import development_delta_transform
from .project_recognition import attach_project_recognition
from .role_pipeline_stages import artifact_by_type, run_configured_role_prefix


def _role_chain_handoff(
    *, project_report: dict[str, Any], recognition: dict[str, Any], decision: dict[str, Any],
    goal: str, run_role_chain: bool, policy: dict[str, Any],
) -> dict[str, Any]:
    option = dict(decision.get("selected_option") or {})
    issue = dict(decision.get("selected_issue") or {})
    target, scope = _handoff_target_scope(project_report, issue)
    route = str(option.get("route") or "")
    next_stage = "architecture" if route == "role_chain" else "research" if route == "research" else "controlled_stop"
    chain_goal = _chain_goal(goal, issue)
    trace = build_verified_runtime_transition(
        stage="project_analysis",
        next_stage=next_stage,
        goal=chain_goal,
        target=target,
        scope=scope,
        evidence=[
            evidence_record("ProjectRecognitionDecision", recognition, kind="recognition"),
            evidence_record("ProjectDevelopmentDecision", decision, kind="development_decision"),
        ],
        rule_id="project_development_role_chain_handoff",
        authority_source="config/project_development.json",
        outcome="controlled_stop" if next_stage == "controlled_stop" else "accepted",
    )
    if trace["status"] != "accepted":
        return {"status": "controlled_stop", "executed": False, "route": route or None, "interpreter_decision_trace": trace}
    if option.get("route") != "role_chain":
        return {"status": "research_required", "executed": False, "route": option.get("route"), "interpreter_decision_trace": trace}
    if not run_role_chain:
        return {"status": "ready", "executed": False, "route": "architect->spec_writer->implementer->tester->reviewer", "interpreter_decision_trace": trace}
    focused = _focused_project_report(project_report, issue, dict(decision.get("selected_option") or {}))
    enriched = attach_project_recognition(focused, recognition)
    artifacts = run_configured_role_prefix(
        goal=chain_goal,
        project_report=enriched,
        until_artifact_type="ReviewFindings",
        artifact_transform=development_delta_transform(decision, policy),
        prior_interpreter_trace=trace,
        interpreter_target=target,
        interpreter_scope=scope,
    )
    spec = artifact_by_type(artifacts, "TechnicalSpec")
    target = str(dict(spec.get("extraction_contract") or {}).get("candidate") or "")
    alignment_targets = list(issue.get("affected_targets") or []) or list(issue.get("evidence") or [])
    aligned = _target_issue_aligned(target, alignment_targets)
    return {
        "status": "completed_aligned" if aligned else "needs_replanning",
        "executed": True,
        "route": "architect->spec_writer->implementer->tester->reviewer",
        "artifacts": {
            artifact: artifact_by_type(artifacts, artifact).get("status")
            for artifact in ("ArchitectureDecisionRecord", "TechnicalSpec", "ImplementationPlan", "TestPlan", "ReviewFindings")
        },
        "selected_target": target,
        "issue_target_aligned": aligned,
        "alignment_policy": "selected target must be the issue evidence target or share its source file",
        "review_recommendation": artifact_by_type(artifacts, "ReviewFindings").get("recommendation"),
        "interpreter_decision_trace": trace,
        "_artifacts": artifacts,
    }


def _chain_goal(goal: str, issue: dict[str, Any]) -> str:
    rule_id = str(issue.get("rule_id") or "").strip()
    evidence = ", ".join(str(value) for value in issue.get("evidence") or [] if value)
    if not rule_id:
        return goal
    return f"{goal}. Fix the selected {rule_id} within ProjectDevelopmentDecision evidence: {evidence}"


def _handoff_target_scope(
    project_report: dict[str, Any], issue: dict[str, Any]
) -> tuple[str, list[str]]:
    values = [str(value) for value in issue.get("affected_targets") or [] if value]
    values.extend(str(value) for value in issue.get("evidence") or [] if ".py" in str(value))
    if values:
        return values[0], sorted(set(values[:8]))
    return project_target_scope(project_report)


def _target_issue_aligned(target: str, evidence: list[str]) -> bool:
    if not target:
        return False
    target_path = target.split(":", 1)[0].replace("\\", "/").lower()
    for value in evidence:
        source = str(value).replace("\\", "/").lower()
        if source == target.lower() or (":" in source and source.split(":", 1)[0] == target_path):
            return True
    return False


def _focused_project_report(
    project_report: dict[str, Any], issue: dict[str, Any], option: dict[str, Any]
) -> dict[str, Any]:
    focused = deepcopy(project_report)
    targets = [str(value) for value in issue.get("affected_targets") or [] if ".py:" in str(value)]
    targets.extend([
        str(value) for value in issue.get("evidence") or []
        if ".py:" in str(value) and not str(value).startswith(("risk:", "failing_", "executable_", "explicit_"))
    ])
    targets = list(dict.fromkeys(targets))[:8]
    focused["project_development_context"] = {
        "artifact_type": "ProjectDevelopmentDecisionContext",
        "issue": issue,
        "option": option,
        "allowed_targets": targets,
        "authority": "ProjectDevelopmentDecision",
    }
    if not targets:
        return focused
    summary = dict(focused.get("summary") or {})
    answers = dict(focused.get("answers") or {})
    profile = dict(dict(answers.get("1_scope") or {}).get("domain_profile") or {})
    focused["architecture_synthesis"] = {
        "artifact_type": "ProjectArchitectureSynthesis",
        "source": "ProjectDevelopmentDecision",
        "synthesis_id": f"development_{issue.get('issue_id')}",
        "confidence": issue.get("confidence"),
        "project_profile": {
            "archetype": profile.get("kind"),
            "entrypoints": list(summary.get("entrypoints") or [])[:6],
            "languages": list(summary.get("languages") or [])[:6],
            "evidence": targets,
            "domain_profile": profile,
        },
        "project_diagnosis": f"Selected {issue.get('rule_id')} as the next evidence-backed development problem.",
        "target_architecture_shape": [
            "Keep the first change inside the selected issue evidence boundary.",
            "Characterize current behavior before changing implementation.",
            "Reassess the original issue after targeted and regression verification.",
        ],
        "recommended_first_slice": {
            "name": f"develop_{issue.get('issue_id')}",
            "goal": f"Resolve or reduce {issue.get('rule_id')}",
            "targets": targets,
            "target_limit": 1,
            "steps": [
                "Reproduce the selected issue from source-backed evidence.",
                "Define the smallest input/output and side-effect contract for one allowed target.",
                "Implement and verify only after the outcome contract is accepted.",
            ],
            "knowledge_rule": "project_development_selected_issue",
        },
    }
    return focused
