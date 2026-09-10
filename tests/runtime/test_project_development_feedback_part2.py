from __future__ import annotations

from tests.runtime.project_development_feedback_helpers import *

def test_active_exception_pickle_operator_reaches_design_request(tmp_path: Path):
    target = "errors.py:PayloadError.__init__"
    (tmp_path / "errors.py").write_text(
        "class PayloadError(Exception):\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "        super().__init__(f'value={value}')\n",
        encoding="utf-8",
    )
    baseline_decision, baseline_outcome = _baselines(target)
    first = run_project_development_feedback_continuation(
        project_dir=tmp_path,
        workspace_root=Path(__file__).resolve().parents[2],
        feedback=_feedback(target, reason="no_verified_failure_reducer"),
        policy=load_project_development_policy(),
        baseline_decision=baseline_decision,
        baseline_outcome_contract=baseline_outcome,
    )

    hypothesis = first["research_hypothesis"]
    assert hypothesis["evidence"]["knowledge_status"] == "active"
    assert hypothesis["evidence"]["active_kb_operator"]["status"] == "validated_active"
    proposal = first["bounded_experiment_proposal"]
    assert proposal["active_kb_operator"]["id"] == "preserve_exception_constructor_reconstruction"
    request = first["implementation_approval_request"]
    human_approval = {
        "artifact_type": "ProjectDevelopmentHumanApprovalDecision",
        "status": "decided",
        "decision": "approve",
        "request_id": request["request_id"],
        "proposal_id": request["proposal_id"],
        "evidence_digest": request["evidence_digest"],
        "authority": "human",
        "reason": "Approve active exception pickle pattern for design only",
    }

    approved = run_project_development_feedback_continuation(
        project_dir=tmp_path,
        workspace_root=Path(__file__).resolve().parents[2],
        feedback=_feedback(target, reason="no_verified_failure_reducer"),
        policy=load_project_development_policy(),
        baseline_decision=baseline_decision,
        baseline_outcome_contract=baseline_outcome,
        human_approval=human_approval,
    )

    candidate = approved["bounded_implementation_candidate"]
    design_request = approved["implementation_design_request"]
    recipe = design_request["suggested_implementation_recipe"]
    assert candidate["active_kb_operator"]["status"] == "validated_active"
    assert recipe == {
        "operator_id": "preserve_exception_constructor_reconstruction",
        "reconstruction_method": "__reduce__",
        "state_strategy": "reuse_direct_assignments",
        "maximum_required_constructor_inputs": 4,
        "required_constructor_inputs_source": "target_constructor",
        "source": "active_kb_operator",
    }

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
        "interface_boundary": {"preserve": ["PayloadError(value)"]},
        "transformation_steps": ["Reuse stored constructor input for reconstruction"],
        "acceptance_mapping": [{"requirement": "round_trip", "check": "pickle replay"}],
        "rollback_strategy": {"scope": [candidate["target"]]},
        "implementation_recipe": recipe,
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
        workspace_root=Path(__file__).resolve().parents[2],
        feedback=_feedback(target, reason="no_verified_failure_reducer"),
        policy=load_project_development_policy(),
        baseline_decision=baseline_decision,
        baseline_outcome_contract=baseline_outcome,
        human_approval=human_approval,
        architect_design=architect_design,
    )
    assert designed["status"] == "implementation_designed"
    assert designed["implementation_design_validation"]["checks"]["active_recipe_is_preserved"] is True

    drifted = deepcopy(architect_design)
    drifted["implementation_recipe"]["state_strategy"] = "insert_private_exact"
    blocked = run_project_development_feedback_continuation(
        project_dir=tmp_path,
        workspace_root=Path(__file__).resolve().parents[2],
        feedback=_feedback(target, reason="no_verified_failure_reducer"),
        policy=load_project_development_policy(),
        baseline_decision=baseline_decision,
        baseline_outcome_contract=baseline_outcome,
        human_approval=human_approval,
        architect_design=drifted,
    )
    assert blocked["status"] == "controlled_stop"
    assert "active_recipe_is_preserved" in blocked["implementation_design_validation"]["blocking_reasons"]


def test_unclassified_source_shape_returns_to_researcher(tmp_path: Path):
    (tmp_path / "normalizer.py").write_text(
        "def normalize_rows(rows):\n"
        "    normalized = []\n"
        "    for row in rows:\n"
        "        normalized.append({'name': row.strip()})\n"
        "    return normalized\n",
        encoding="utf-8",
    )

    continuation = run_project_development_feedback_continuation(
        project_dir=tmp_path,
        feedback=_feedback("normalizer.py:normalize_rows"),
        policy=load_project_development_policy(),
    )

    assert continuation["status"] == "research_required"
    assert continuation["research_hypothesis"]["status"] == "research_more"
    assert continuation["architect_decision"]["decision"] == "research_more"
    assert continuation["architect_decision"]["next_role"] == "researcher"
    assert continuation["replan_revision"] is None
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


def test_missing_feedback_target_keeps_controlled_stop(tmp_path: Path):
    continuation = run_project_development_feedback_continuation(
        project_dir=tmp_path,
        feedback=_feedback(""),
        policy=load_project_development_policy(),
    )

    assert continuation["status"] == "controlled_stop"
    assert continuation["research_hypothesis"]["status"] == "knowledge_gap"
    assert continuation["architect_decision"]["decision"] == "controlled_stop"
    assert continuation["architect_decision"]["next_role"] == "human"
    assert continuation["replan_revision"] is None
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


def test_completed_feedback_does_not_start_continuation(tmp_path: Path):
    feedback = _feedback("normalizer.py:normalize_rows")
    feedback.update({"status": "not_required", "decision": "completed", "reason": "experiment_validated"})

    continuation = run_project_development_feedback_continuation(
        project_dir=tmp_path,
        feedback=feedback,
        policy=load_project_development_policy(),
    )

    assert continuation == {
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
