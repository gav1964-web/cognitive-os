from __future__ import annotations

from tests.runtime.project_development_feedback_helpers import *

def test_nested_mapping_feedback_produces_bounded_architect_replan(tmp_path: Path):
    source = (
        "def normalize_batches(batches):\n"
        "    normalized = []\n"
        "    for batch in batches:\n"
        "        for row in batch:\n"
        "            normalized.append({'name': row.strip()})\n"
        "    return normalized\n"
    )
    (tmp_path / "normalizer.py").write_text(source, encoding="utf-8")

    baseline_decision, baseline_outcome = _baselines("normalizer.py:normalize_batches")
    continuation = run_project_development_feedback_continuation(
        project_dir=tmp_path,
        feedback=_feedback("normalizer.py:normalize_batches"),
        policy=load_project_development_policy(),
        baseline_decision=baseline_decision,
        baseline_outcome_contract=baseline_outcome,
    )

    hypothesis = continuation["research_hypothesis"]
    decision = continuation["architect_decision"]
    assert continuation["status"] == "awaiting_human_approval"
    assert hypothesis["status"] == "proposed"
    assert hypothesis["hypothesis_kind"] == "nested_loop_mapping_boundary"
    assert hypothesis["evidence"]["knowledge_profile"] == "nested_loop_mapping_boundary"
    assert hypothesis["evidence"]["knowledge_status"] == "staged"
    assert hypothesis["evidence"]["source_facts"]["maximum_loop_depth"] == 2
    assert hypothesis["constraints"]["allowed_targets"] == ["normalizer.py:normalize_batches"]
    assert decision["decision"] == "replan"
    assert decision["allowed_targets"] == ["normalizer.py:normalize_batches"]
    assert decision["executor_rerun_allowed"] is False
    revision = continuation["replan_revision"]
    assert revision["status"] == "planning_only"
    assert revision["revision"] == 2
    assert revision["revised_decision"]["status"] == "replanned"
    assert revision["revised_decision"]["planning_adjustment"]["target"] == (
        "normalizer.py:normalize_batches"
    )
    assert revision["revised_decision"]["selected_option"] == baseline_decision["selected_option"]
    assert revision["revised_outcome_contract"]["status"] == "revised_planning_only"
    assert revision["revised_outcome_contract"]["required_checks"] == (
        baseline_outcome["required_checks"]
    )
    assert revision["constraints"] == {
        "allowed_targets": ["normalizer.py:normalize_batches"],
        "planning_only": True,
        "developer_handoff_allowed": False,
        "executor_rerun_allowed": False,
        "source_changes_allowed": False,
    }
    proposal = continuation["bounded_experiment_proposal"]
    admission = continuation["planning_admission"]
    assert proposal["status"] == "proposed"
    assert proposal["target"] == "normalizer.py:normalize_batches"
    assert proposal["budget"]["maximum_targets"] == 1
    assert proposal["budget"]["maximum_source_files"] == 2
    assert proposal["budget"]["maximum_contrast_sources"] == 1
    assert proposal["budget"]["execution_runs"] == 0
    assert proposal["contrast_source"]["contrast_id"] == "simple_loop_mapping_validated_o"
    assert proposal["constraints"]["execution_authorized"] is False
    assert admission["status"] == "admitted_for_planning"
    assert admission["next_role"] == "researcher"
    assert admission["execution_authorized"] is False
    evidence = continuation["bounded_experiment_evidence"]
    closure = continuation["architect_evidence_decision"]
    assert evidence["status"] == "collected"
    assert evidence["collector"] == "embedded_read_only_researcher"
    assert evidence["source_snapshot"]["unchanged"] is True
    assert len(evidence["observations"]) == 3
    contrast = evidence["requirement_results"]["positive_and_negative_shape_contrast"]
    assert contrast["satisfied"] is True
    assert contrast["source_backed_negative"] is True
    assert contrast["source_backed_positive"] is True
    assert contrast["bounded_implementation_evidence"] is True
    assert contrast["kb_promotion_evidence"] is False
    assert contrast["authority"] == "paired_source_ast"
    assert evidence["constraints"]["network_used"] is False
    assert evidence["constraints"]["subprocess_used"] is False
    assert closure["decision"] == "evidence_accepted"
    assert closure["next_step"] == "human_review_bounded_implementation_candidate"
    assert closure["checks"]["paired_source_contrast_supports_bounded_implementation"] is True
    assert closure["checks"]["kb_promotion_remains_forbidden"] is True
    assert closure["execution_authorized"] is False
    approval_request = continuation["implementation_approval_request"]
    approval_validation = continuation["implementation_approval_validation"]
    assert approval_request["status"] == "awaiting_human_approval"
    assert approval_request["proposal_id"] == proposal["proposal_id"]
    assert len(approval_request["evidence_digest"]) == 64
    assert approval_validation["status"] == "pending"
    assert approval_validation["candidate_allowed"] is False
    assert continuation["human_approval_decision"] is None
    assert continuation["bounded_implementation_candidate"] is None
    assert continuation["implementation_design_request"] is None
    assert continuation["implementation_design_admission"] is None
    assert continuation["implementation_design"] is None
    assert continuation["implementation_design_validation"] is None
    registry = ContractRegistry({})
    registry.validate_artifact(hypothesis)
    registry.validate_artifact(decision)
    registry.validate_artifact(revision)
    registry.validate_artifact(revision["revised_decision"])
    registry.validate_artifact(revision["revised_outcome_contract"])
    registry.validate_artifact(proposal)
    registry.validate_artifact(admission)
    registry.validate_artifact(evidence)
    registry.validate_artifact(closure)
    registry.validate_artifact(approval_request)
    registry.validate_artifact(approval_validation)
    registry.validate_artifact(continuation)

    drifted = deepcopy(proposal)
    drifted["target"] = "normalizer.py:other"
    blocked = admit_bounded_experiment_proposal(
        proposal=drifted,
        revision=revision,
        hypothesis=hypothesis,
        policy=load_project_development_policy(),
    )
    assert blocked["status"] == "blocked"
    assert "target_matches_hypothesis" in blocked["blocking_reasons"]
    assert "target_is_revision_allowlisted" in blocked["blocking_reasons"]

    unsafe = deepcopy(proposal)
    unsafe["allowed_actions"].append("invoke_executor")
    blocked = admit_bounded_experiment_proposal(
        proposal=unsafe,
        revision=revision,
        hypothesis=hypothesis,
        policy=load_project_development_policy(),
    )
    assert blocked["status"] == "blocked"
    assert "actions_are_allowlisted" in blocked["blocking_reasons"]

    incomplete = deepcopy(evidence)
    incomplete["status"] = "incomplete"
    incomplete["failed_requirements"] = ["positive_and_negative_shape_contrast"]
    closure = decide_bounded_experiment_evidence(
        evidence=incomplete,
        proposal=proposal,
        policy=load_project_development_policy(),
    )
    assert closure["decision"] == "research_more"
    assert closure["execution_authorized"] is False

    blocked_evidence = collect_bounded_experiment_evidence(
        project_dir=tmp_path,
        workspace_root=Path(__file__).resolve().parents[2],
        proposal=proposal,
        admission={"status": "blocked", "execution_authorized": False},
        hypothesis=hypothesis,
        policy=load_project_development_policy(),
    )
    assert blocked_evidence["status"] == "blocked"
    assert blocked_evidence["collector"] == "not_started"
    assert blocked_evidence["source_snapshot"]["primary"]["before"] is None

    drifted_contrast = deepcopy(proposal)
    drifted_contrast["contrast_source"]["sha256"] = "0" * 64
    incomplete = collect_bounded_experiment_evidence(
        project_dir=tmp_path,
        workspace_root=Path(__file__).resolve().parents[2],
        proposal=drifted_contrast,
        admission=admission,
        hypothesis=hypothesis,
        policy=load_project_development_policy(),
    )
    assert incomplete["status"] == "incomplete"
    assert incomplete["checks"]["contrast_digest_is_allowlisted"] is False
    assert "positive_and_negative_shape_contrast" in incomplete["failed_requirements"]

    human_approval = {
        "artifact_type": "ProjectDevelopmentHumanApprovalDecision",
        "status": "decided",
        "decision": "approve",
        "request_id": approval_request["request_id"],
        "proposal_id": approval_request["proposal_id"],
        "evidence_digest": approval_request["evidence_digest"],
        "authority": "human",
        "reason": "Approve candidate materialization for bounded design review only",
    }
    approved = run_project_development_feedback_continuation(
        project_dir=tmp_path,
        feedback=_feedback("normalizer.py:normalize_batches"),
        policy=load_project_development_policy(),
        baseline_decision=baseline_decision,
        baseline_outcome_contract=baseline_outcome,
        human_approval=human_approval,
    )
    assert approved["status"] == "implementation_design_ready"
    assert approved["implementation_approval_validation"]["status"] == "approved"
    candidate = approved["bounded_implementation_candidate"]
    assert candidate["status"] == "approved_not_executable"
    assert candidate["target"] == "normalizer.py:normalize_batches"
    assert candidate["evidence_digest"] == approval_request["evidence_digest"]
    assert candidate["constraints"]["execution_authorized"] is False
    assert candidate["constraints"]["developer_handoff_allowed"] is False
    design_request = approved["implementation_design_request"]
    design_admission = approved["implementation_design_admission"]
    assert design_request["status"] == "requested"
    assert design_request["candidate_id"] == candidate["candidate_id"]
    assert design_request["design_scope"]["targets"] == ["normalizer.py:normalize_batches"]
    assert "source_patch" in design_request["forbidden_outputs"]
    assert design_request["constraints"]["automatic_role_invocation"] is False
    assert design_admission["status"] == "ready_for_architect_design"
    assert design_admission["next_role"] == "architect"
    assert design_admission["automatic_role_invocation"] is False
    assert design_admission["execution_authorized"] is False
    registry.validate_artifact(approved["human_approval_decision"])
    registry.validate_artifact(approved["implementation_approval_validation"])
    registry.validate_artifact(candidate)
    registry.validate_artifact(design_request)
    registry.validate_artifact(design_admission)

    architect_design = {
        "artifact_type": "ProjectDevelopmentImplementationDesign",
        "status": "designed_not_executable",
        "authority": "architect",
        "request_id": design_request["request_id"],
        "candidate_id": candidate["candidate_id"],
        "proposal_id": candidate["proposal_id"],
        "evidence_digest": candidate["evidence_digest"],
        "hypothesis_kind": candidate["hypothesis_kind"],
        "target": candidate["target"],
        "source_sha256": candidate["evidence_summary"]["source_snapshot"]["primary"]["after"],
        "interface_boundary": {"preserve": ["public signature"]},
        "transformation_steps": ["Preserve inputs needed for reconstruction"],
        "acceptance_mapping": [{"requirement": "round_trip", "check": "targeted test"}],
        "rollback_strategy": {"scope": [candidate["target"]]},
        "constraints": {
            "execution_authorized": False,
            "developer_handoff_allowed": False,
            "executor_rerun_allowed": False,
            "source_changes_allowed": False,
            "memory_promotion_allowed": False,
        },
    }
    designed = run_project_development_feedback_continuation(
        project_dir=tmp_path,
        feedback=_feedback("normalizer.py:normalize_batches"),
        policy=load_project_development_policy(),
        baseline_decision=baseline_decision,
        baseline_outcome_contract=baseline_outcome,
        human_approval=human_approval,
        architect_design=architect_design,
    )
    assert designed["status"] == "implementation_designed"
    assert designed["implementation_design"] == architect_design
    validation = designed["implementation_design_validation"]
    assert validation["status"] == "accepted_not_executable"
    assert validation["design_accepted"] is True
    assert validation["next_gate"] == "separate_implementation_authorization"
    assert validation["execution_authorized"] is False
    registry.validate_artifact(designed["implementation_design"])
    registry.validate_artifact(validation)

    forbidden_design = deepcopy(architect_design)
    forbidden_design["source_patch"] = "not allowed"
    blocked_design_submission = run_project_development_feedback_continuation(
        project_dir=tmp_path,
        feedback=_feedback("normalizer.py:normalize_batches"),
        policy=load_project_development_policy(),
        baseline_decision=baseline_decision,
        baseline_outcome_contract=baseline_outcome,
        human_approval=human_approval,
        architect_design=forbidden_design,
    )
    assert blocked_design_submission["status"] == "controlled_stop"
    assert blocked_design_submission["implementation_design_validation"]["status"] == "blocked"
    assert "forbidden_outputs_are_absent" in blocked_design_submission[
        "implementation_design_validation"
    ]["blocking_reasons"]

    drifted_design = deepcopy(design_request)
    drifted_design["evidence_digest"] = "0" * 64
    blocked_design = admit_implementation_design(
        request=drifted_design,
        candidate=candidate,
        policy=load_project_development_policy(),
    )
    assert blocked_design["status"] == "blocked"
    assert "evidence_digest_matches" in blocked_design["blocking_reasons"]
    assert blocked_design["automatic_role_invocation"] is False
    assert blocked_design["execution_authorized"] is False

    replayed = deepcopy(human_approval)
    replayed["evidence_digest"] = "0" * 64
    blocked = run_project_development_feedback_continuation(
        project_dir=tmp_path,
        feedback=_feedback("normalizer.py:normalize_batches"),
        policy=load_project_development_policy(),
        baseline_decision=baseline_decision,
        baseline_outcome_contract=baseline_outcome,
        human_approval=replayed,
    )
    assert blocked["status"] == "controlled_stop"
    assert blocked["implementation_approval_validation"]["status"] == "blocked"
    assert "evidence_digest_matches" in blocked["implementation_approval_validation"][
        "blocking_reasons"
    ]
    assert blocked["bounded_implementation_candidate"] is None
    assert blocked["implementation_design_request"] is None
    assert blocked["implementation_design_admission"] is None
    assert blocked["implementation_design"] is None
    assert blocked["implementation_design_validation"] is None


def test_replan_materialization_blocks_without_authority_baselines(tmp_path: Path):
    (tmp_path / "normalizer.py").write_text(
        "def normalize_batches(batches):\n"
        "    output = []\n"
        "    for batch in batches:\n"
        "        for row in batch:\n"
        "            output.append({'name': row})\n"
        "    return output\n",
        encoding="utf-8",
    )

    continuation = run_project_development_feedback_continuation(
        project_dir=tmp_path,
        feedback=_feedback("normalizer.py:normalize_batches"),
        policy=load_project_development_policy(),
    )

    assert continuation["status"] == "controlled_stop"
    assert continuation["architect_decision"]["decision"] == "replan"
    assert continuation["replan_revision"]["status"] == "blocked"
    assert continuation["replan_revision"]["revised_decision"] is None
    assert "baseline_decision_is_valid" in continuation["replan_revision"]["failed_checks"]
    assert continuation["bounded_experiment_proposal"] is None
    assert continuation["planning_admission"] is None
    assert continuation["bounded_experiment_evidence"] is None
    assert continuation["architect_evidence_decision"] is None
    assert continuation["implementation_approval_request"] is None
    assert continuation["human_approval_decision"] is None
    assert continuation["implementation_approval_validation"] is None
    assert continuation["bounded_implementation_candidate"] is None
    assert continuation["implementation_design_request"] is None
    assert continuation["implementation_design_admission"] is None
    assert continuation["implementation_design"] is None
    assert continuation["implementation_design_validation"] is None
