from runtime.role_chain_interaction import (
    build_role_chain_trace,
    build_unknown_role_chain_trace,
    summarize_role_chain_traces,
)


ROLES = ("project_analyzer", "architect", "spec_writer", "implementer", "tester", "reviewer")


def test_known_role_chain_measures_target_and_gate_continuity() -> None:
    result = _known_result()

    trace = build_role_chain_trace(project="known", result=result)

    assert trace["status"] == "ok"
    assert trace["interaction_score"] == 1.0
    assert trace["first_pass_acceptance"] is True
    assert trace["handoff_loss_count"] == 0
    assert trace["required_human_decisions"] == ["material_risk_review"]


def test_known_role_chain_exposes_target_drift() -> None:
    result = _known_result()
    result["role_quality"]["test_targets_implementation_target"] = False

    trace = build_role_chain_trace(project="drift", result=result)

    assert trace["status"] == "needs_work"
    assert trace["handoff_loss"] == ["implementer_to_tester_target_preserved"]
    assert trace["first_pass_acceptance"] is False


def test_known_chain_treats_consistent_no_safe_candidate_as_controlled_stop() -> None:
    result = _known_result()
    result["role_quality"].update({
        "implementation_targets_extraction_candidate": False,
        "implementation_blocked_no_safe_candidate": True,
        "test_blocked_no_safe_candidate": True,
        "review_target": "blocked_no_safe_candidate",
    })
    result["next_action"] = "rework_role_artifacts"
    result["chain_telemetry"]["build_reselection_history"] = [{"resolution_status": "exhausted"}]

    trace = build_role_chain_trace(project="legacy", result=result)

    assert trace["status"] == "controlled_stop"
    assert trace["handoff_loss_count"] == 0
    assert trace["first_pass_acceptance"] is False
    assert trace["terminal_reason"] == "no_safe_candidate_after_bounded_reselection"


def test_unknown_chain_treats_quarantine_as_controlled_stop() -> None:
    intake = {
        "project": "novel",
        "knowledge_gap": {"gap_id": "kgp_test"},
        "research_plan": {"steps": [{"source_type": "official_docs_fetch"}], "policy": {"llm_may_not_browse_freely": True}},
        "routing": {"current_stratum": "unknown_new_archetype", "downstream_roles_blocked": True},
    }
    candidate = {"status": "needs_teacher_approval", "promotion_gate": {"automatic_promotion": False}}

    trace = build_unknown_role_chain_trace(intake=intake, candidate=candidate)

    assert trace["status"] == "controlled_stop"
    assert trace["interaction_score"] == 1.0
    assert trace["blocked_route"][0] == "architect"
    assert trace["required_human_decision_count"] == 1


def test_role_chain_summary_separates_first_pass_from_controlled_unknown() -> None:
    known = build_role_chain_trace(project="known", result=_known_result())
    unknown = build_unknown_role_chain_trace(
        intake={
            "project": "novel",
            "knowledge_gap": {"gap_id": "kgp_test"},
            "research_plan": {"steps": [{}], "policy": {"llm_may_not_browse_freely": True}},
            "routing": {"current_stratum": "unknown_new_archetype", "downstream_roles_blocked": True},
        }
    )

    summary = summarize_role_chain_traces([known, unknown])

    assert summary["known_trace_count"] == 1
    assert summary["first_pass_acceptance_count"] == 1
    assert summary["controlled_unknown_stop_count"] == 1


def test_known_chain_records_researcher_architect_recovery_loop() -> None:
    result = _known_result()
    result["role_quality"].update({
        "implementation_targets_extraction_candidate": False,
        "implementation_blocked_no_safe_candidate": True,
        "test_blocked_no_safe_candidate": True,
        "review_target": "blocked_no_safe_candidate",
    })
    result["next_action"] = "rework_role_artifacts"
    result["chain_telemetry"].update({
        "build_reselection_history": [{"resolution_status": "exhausted"}],
        "no_safe_candidate_recovery": {
            "status": "bounded_rework_ready",
            "candidate_status": "verified_for_bounded_implementation",
        },
    })

    trace = build_role_chain_trace(project="legacy", result=result)
    summary = summarize_role_chain_traces([trace])

    assert trace["route"][-2:] == ["researcher", "architect"]
    assert trace["conditional_roles"]["developer"] == "bounded_decomposition_required"
    assert trace["recovery_candidate_status"] == "verified_for_bounded_implementation"
    assert summary["bounded_recovery_ready_count"] == 1


def _known_result() -> dict:
    return {
        "role_gates": {"cases": [{"role_id": role, "status": "ok"} for role in ROLES]},
        "role_quality": {
            "implementation_targets_extraction_candidate": True,
            "test_targets_implementation_target": True,
            "review_targets_implementation_target": True,
            "review_confirms_target_coverage": True,
            "selected_extraction_candidate": "pkg/core.py:normalize",
            "review_target": "pkg/core.py:normalize",
        },
        "cognitive_control_plane": {
            "artifact_promotion_gate": {"status": "passed"},
            "semantic_escalation": {"l4_5_required": False},
        },
        "chain_telemetry": {"build_reselection_history": [], "execution_reselection_history": []},
        "next_action": "review_risks_then_run_project_transform",
    }
