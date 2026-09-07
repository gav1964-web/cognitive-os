"""Top-level orchestration for project development."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .classification_consistency import evaluate_classification_consistency
from .project_development_diagnosis import build_development_diagnosis
from .project_development_experiment import (
    build_project_development_execution_feedback,
    run_project_development_experiment,
)
from .project_failure_causal_diagnosis import enrich_failure_diagnosis
from .project_development_feedback import run_project_development_feedback_continuation
from .project_development_handoff import _role_chain_handoff
from .project_development_memory import _memory_context, _now
from .project_development_policy import load_project_development_policy
from .project_development_selection import (
    build_development_options,
    build_outcome_contract,
    select_development_option,
)
from .project_development_source_evidence import collect_source_incompleteness_evidence
from .project_recognition import recognize_project
from .role_project_analysis import analyze_role_project
from .role_pipeline_stages import artifact_by_type
from .role_project_type_evaluation import classify_project_case


def run_project_development(
    *,
    root: Path,
    project_dir: Path,
    goal: str,
    run_role_chain: bool = False,
    run_sandbox_experiment: bool = False,
    prior_runs: list[dict[str, Any]] | None = None,
    chain_case: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
    human_approval: dict[str, Any] | None = None,
    architect_design: dict[str, Any] | None = None,
    authorize_training_replay: bool = False,
) -> dict[str, Any]:
    """Diagnose one project and select a bounded, measurable next experiment."""
    policy = policy or load_project_development_policy()
    report = analyze_role_project(root=root, project_dir=project_dir, goal=goal)["project_map_report"]
    classification = None
    intake_stratum = str((chain_case or {}).get("project_stratum") or "")
    if intake_stratum:
        classification = classify_project_case({
            "project": project_dir.name,
            "project_stratum": intake_stratum,
            "artifacts": {"project_map_report": report},
        })
    recognition = recognize_project(
        project=project_dir.name,
        project_report=report,
        classification=classification,
        project_dir=project_dir,
        change_request=chain_case,
    )
    classification_consistency = evaluate_classification_consistency(
        project_dir=project_dir,
        recognition=recognition,
    )
    source_incompleteness = collect_source_incompleteness_evidence(
        project_dir,
        corroborating_failures=list((chain_case or {}).get("contract_failure_evidence") or []),
    )
    diagnosis = build_development_diagnosis(
        project=project_dir.name,
        project_report=report,
        recognition=recognition,
        chain_case=chain_case,
        source_incompleteness=source_incompleteness,
        classification_consistency=classification_consistency,
        policy=policy,
    )
    diagnosis = enrich_failure_diagnosis(
        diagnosis, project_dir=project_dir, workspace_root=root,
        authorize_training_replay=authorize_training_replay,
    )
    portfolio = build_development_options(diagnosis, policy=policy)
    decision = select_development_option(diagnosis, portfolio, policy=policy)
    outcome = build_outcome_contract(decision, policy=policy)
    memory = _memory_context(project_dir, prior_runs or [])
    handoff = _role_chain_handoff(
        project_report=report,
        recognition=recognition,
        decision=decision,
        goal=goal,
        run_role_chain=run_role_chain or run_sandbox_experiment,
        policy=policy,
    )
    role_artifacts = handoff.pop("_artifacts", {})
    experiment, reassessment, validated_memory = run_project_development_experiment(
        root=root,
        project_dir=project_dir,
        goal=goal,
        decision=decision,
        outcome_contract=outcome,
        handoff=handoff,
        artifacts=role_artifacts,
        requested=run_sandbox_experiment,
        policy=policy,
        recognition=recognition,
    )
    execution_feedback = build_project_development_execution_feedback(
        handoff=handoff,
        experiment=experiment,
        reassessment=reassessment,
        policy=policy,
    )
    feedback_continuation = run_project_development_feedback_continuation(
        project_dir=project_dir,
        feedback=execution_feedback,
        policy=policy,
        baseline_decision=decision,
        baseline_outcome_contract=outcome,
        workspace_root=root,
        human_approval=human_approval,
        architect_design=architect_design,
    )
    status = "ready_for_experiment" if decision.get("status") == "selected" else "controlled_stop"
    if handoff.get("status") == "needs_replanning":
        status = "needs_replanning"
    if run_sandbox_experiment:
        status = {
            "completed": "experiment_validated",
            "research": "research_required",
            "needs_replanning": "needs_replanning",
            "controlled_stop": "controlled_stop",
        }.get(str(execution_feedback.get("decision")), "controlled_stop")
        if execution_feedback.get("decision") == "research":
            status = {
                "awaiting_human_approval": "awaiting_human_approval",
                "implementation_candidate_approved": "implementation_candidate_ready",
                "implementation_design_ready": "implementation_design_ready",
                "implementation_designed": "implementation_designed",
                "human_rejected": "controlled_stop",
                "research_required": "research_required",
                "controlled_stop": "controlled_stop",
            }.get(str(feedback_continuation.get("status")), "controlled_stop")
    result = {
        "artifact_type": "ProjectDevelopmentRun",
        "schema_version": "project_development_run.v1",
        "status": status,
        "generated_at": _now(),
        "project": project_dir.name,
        "project_root": project_dir.resolve().as_posix(),
        "goal": goal,
        "recognition": recognition,
        "classification_consistency": classification_consistency,
        "diagnosis": diagnosis,
        "option_portfolio": portfolio,
        "decision": decision,
        "outcome_contract": outcome,
        "memory_context": memory,
        "role_chain_handoff": handoff,
        "experiment": experiment,
        "outcome_reassessment": reassessment,
        "execution_feedback": execution_feedback,
        "feedback_continuation": feedback_continuation,
        "validated_memory": validated_memory,
        "safety": {
            "source_changes": False,
            "automatic_patch_apply": False,
            "automatic_kb_promotion": False,
            "unknown_or_ambiguous_routes_to_research": True,
            "automatic_feedback_retry": False,
            "feedback_executor_rerun": False,
            "feedback_developer_handoff": False,
            "replan_execution_authorized": False,
            "training_replay_authorized": authorize_training_replay,
            "training_replay_scope": "consumed_case_sandbox_only" if authorize_training_replay else None,
        },
    }
    if role_artifacts:
        result["role_artifacts"] = {
            "project_map_report": report,
            "architecture_decision": artifact_by_type(
                role_artifacts, "ArchitectureDecisionRecord"
            ),
            "technical_spec": artifact_by_type(role_artifacts, "TechnicalSpec"),
        }
    return result
