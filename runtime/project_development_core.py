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
from .project_failure_evidence_packet import attach_failure_evidence_packets
from .project_development_llm_hypothesis import enrich_with_llm_failure_hypothesis
from .local_inference import LocalInferenceConfig
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
    authorize_model_trial: bool = False,
    llm_hypothesis_config: LocalInferenceConfig | None = None,
    validate_causal_proposals: bool = False,
    task_contract: dict | None = None,
    repair_nomination: dict | None = None,
    repair_branch_evidence: dict | None = None,
    repair_counterexample_comparison: dict | None = None,
    repair_observations: dict | None = None,
    repair_counterexample_history: list[dict] | None = None,
    model_chat=None,
    repair_preservation: dict | None = None,
) -> dict[str, Any]:
    """Diagnose one project and select a bounded, measurable next experiment."""
    if type(authorize_model_trial) is not bool or (authorize_model_trial and (
            not validate_causal_proposals or llm_hypothesis_config is None)):
        raise ValueError('model_trial_authorization_requires_configured_causal_trial')
    if validate_causal_proposals and not (authorize_training_replay or authorize_model_trial):
        raise ValueError('causal_comparison_requires_explicit_training_authorization')
    if model_chat is not None and (not validate_causal_proposals or llm_hypothesis_config is None):
        raise ValueError('model_chat_requires_configured_causal_trial')
    if repair_preservation is not None and (not validate_causal_proposals or llm_hypothesis_config is None):
        raise ValueError('preservation_requires_authorized_model_trial')
    if task_contract is not None and not validate_causal_proposals:
        raise ValueError('requested_native_repair_requires_causal_comparison')
    if repair_nomination is not None and (not validate_causal_proposals or llm_hypothesis_config is None):
        raise ValueError('repair_nomination_requires_authorized_model_trial')
    if repair_branch_evidence is not None and repair_nomination is None:
        raise ValueError('branch_evidence_requires_repair_nomination')
    if repair_counterexample_comparison is not None and (not validate_causal_proposals or llm_hypothesis_config is None):
        raise ValueError('counterexample_requires_authorized_model_trial')
    if (repair_observations is not None or repair_counterexample_history is not None) and (
            not validate_causal_proposals or llm_hypothesis_config is None):
        raise ValueError('diagnostics_require_authorized_model_trial')
    policy = policy or load_project_development_policy()
    report = analyze_role_project(root=root, project_dir=project_dir, goal=goal,
        **({'task_contract': task_contract} if task_contract is not None else {}))["project_map_report"]
    request = None
    if task_contract is not None:
        from .upstream_requested_change import prepare_requested_change
        request = prepare_requested_change(report, project_dir)
        report['requested_change'] = request
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
    from .native_replay_settings import policy_replay_settings
    replay_settings = policy_replay_settings(policy)
    diagnosis = attach_failure_evidence_packets(
        diagnosis, project_dir=project_dir, chain_case=chain_case,
        native_replay_settings=replay_settings if replay_settings != {'pytest_plugins': [], 'timeout_seconds': 20} else None,
    )
    model_trial = validate_causal_proposals and llm_hypothesis_config is not None
    if repair_nomination is not None:
        from .repair_trial_binding import bind_repair_diagnosis
        diagnosis = bind_repair_diagnosis(diagnosis, project=project_dir, bundle=repair_nomination)
        if repair_branch_evidence is not None:
            from .repair_branch_evidence import validate_branch_evidence
            issue = next(i for i in diagnosis['issues'] if i.get('repair_trial_packet_digest'))
            validate_branch_evidence(project_dir, issue['failure_evidence_packet'], repair_branch_evidence)
            from copy import deepcopy
            issue['repair_branch_evidence'] = deepcopy(repair_branch_evidence)
    if model_trial:
        if repair_preservation is not None:
            from .repair_preservation import bind_preservation
            diagnosis = bind_preservation(diagnosis, project_dir, repair_preservation)
        if repair_observations is not None or repair_counterexample_history is not None:
            from .repair_diagnostic_context import bind_diagnostic_context
            diagnosis = bind_diagnostic_context(diagnosis, project_dir,
                observations=repair_observations, history=repair_counterexample_history)
        if repair_counterexample_comparison is not None:
            from .repair_counterexamples import bind_saved_counterexample
            diagnosis = bind_saved_counterexample(diagnosis, project_dir, repair_counterexample_comparison)
        from .upstream_llm_trials import validate_llm_diagnosis_proposals
        diagnosis = validate_llm_diagnosis_proposals(diagnosis, project=project_dir, root=root,
            config=llm_hypothesis_config, authorized=True, delivery_authorized=run_sandbox_experiment,
            request=request, format_retries=policy.get('model_candidate_format_retries', 0),
            semantic_retries=policy.get('model_native_counterexample_retries', 0),
            require_assertion_plan=policy.get('model_require_assertion_plan', False),
            proposal_route=policy.get('model_proposal_route', 'hypothesis'), chat=model_chat,
            include_dependency_context=policy.get('model_include_dependency_context', False),
            same_class_repairs=policy.get('model_same_class_repairs', False))
    else:
        diagnosis = enrich_failure_diagnosis(
            diagnosis, project_dir=project_dir, workspace_root=root,
            authorize_training_replay=authorize_training_replay,
        )
        diagnosis = enrich_with_llm_failure_hypothesis(
            diagnosis, project_dir=project_dir, config=llm_hypothesis_config,
            training_replay_authorized=authorize_training_replay,
        )
    if validate_causal_proposals and not model_trial and (request is None or request['status'] == 'ready_for_candidate_check'):
        from .upstream_causal_selection import validate_diagnosis_proposals
        diagnosis = validate_diagnosis_proposals(diagnosis, project=project_dir, root=root, authorized=True)
    if request is not None:
        from .upstream_requested_change import bind_requested_change
        diagnosis = bind_requested_change(diagnosis, request, project=project_dir, root=root)
    llm_advisories = [
        dict(issue.get("llm_hypothesis_advisory") or {})
        for issue in diagnosis.get("issues") or [] if isinstance(issue, dict)
        and issue.get("llm_hypothesis_advisory")
    ]
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
    role_project_report = handoff.pop("_project_report", report)
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
        use_l45_llm=bool(llm_hypothesis_config and authorize_training_replay and not model_trial),
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
    if handoff.get("status") in {"needs_replanning", "research_required", "controlled_stop"}:
        status = handoff['status']
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
        "llm_hypothesis_summary": {
            "requested": llm_hypothesis_config is not None,
            "advisory_count": len(llm_advisories),
            "statuses": sorted({str(row.get("status") or "unknown") for row in llm_advisories}),
            "accepted_count": sum(
                row.get("status") == "accepted_hypothesis_only" for row in llm_advisories
            ),
            "execution_authorized": False,
        },
        "causal_comparison_requested": validate_causal_proposals,
        "requested_change": dict(decision.get('selected_issue') or {}).get('requested_change', request),
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
            "model_trial_authorized": authorize_model_trial,
            "model_trial_scope": "source_bound_candidate_sandbox_only" if authorize_model_trial else None,
            "training_replay_scope": "consumed_case_sandbox_only" if authorize_training_replay else None,
            "llm_hypothesis_enabled": llm_hypothesis_config is not None,
            "llm_hypothesis_authority": "hypothesis_only" if llm_hypothesis_config is not None else None,
        },
    }
    if role_artifacts:
        result["role_artifacts"] = {
            "project_map_report": role_project_report,
            "architecture_decision": artifact_by_type(
                role_artifacts, "ArchitectureDecisionRecord"
            ),
            "technical_spec": artifact_by_type(role_artifacts, "TechnicalSpec"),
            "implementation_plan": artifact_by_type(role_artifacts, "ImplementationPlan"),
            "test_plan": artifact_by_type(role_artifacts, "TestPlan"),
            "programmer_task_tree": artifact_by_type(role_artifacts, "ProgrammerTaskTree"),
            "review_findings": artifact_by_type(role_artifacts, "ReviewFindings"),
        }
    return result
