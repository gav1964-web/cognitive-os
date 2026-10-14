from __future__ import annotations

from tests.runtime.project_development_helpers import *

def test_generated_function_stub_makes_green_experiment_fail():
    experiment = _experiment_artifact(
        {"status": "ok", "source_code_changes": False},
        {
            "artifact_type": "PatchPackage",
            "status": "prepared",
            "patch_synthesis": {"status": "prepared"},
            "patches": [{"file": "pkg/service.py", "kind": "generated_change"}],
        },
        {
            "status": "ok",
            "executable_acceptance_result": {"status": "passed"},
        },
        {"artifact_type": "ProjectNativeVerificationResult", "status": "not_requested"},
        {
            "artifact_type": "GeneratedFunctionStubAdmission",
            "status": "blocked",
            "violations": [{"file": "pkg/service.py", "qualified_name": "pending", "marker": "pass"}],
        },
        {"status": "admitted"},
        "same-digest",
        "same-digest",
        {"selected_issue": {"issue_id": "ISSUE-001", "evidence": ["pkg/service.py:run"]}},
        load_project_development_policy(),
    )

    assert experiment["status"] == "failed"
    assert experiment["checks"]["no_generated_function_stubs"] is False
    assert experiment["generated_function_stub_admission"]["violations"][0]["qualified_name"] == "pending"


def test_reassessment_validates_only_measurable_issue_reduction():
    decision = {
        "selected_issue": {
            "issue_id": "ISSUE-001",
            "rule_id": "weak_contracts",
            "evidence": ["pkg/service.py:run"],
        },
        "selected_option": {"strategy": "contract_characterization"},
    }
    outcome = {"baseline_evidence": ["pkg/service.py:run"]}
    experiment = {
        "status": "verified",
        "patch_kinds": ["insert_required_input_guard"],
        "source_invariant": {"unchanged": True},
        "checks": {"patch_scope_within_issue_evidence": True},
        "patch_package_path": "patch.json",
        "test_result_path": "test.json",
    }
    test_result = {
        "status": "ok",
        "summary": {"failed": 0, "passed": 2},
        "executable_acceptance_result": {"status": "passed"},
    }
    reassessment = _reassessment(
        "evaluated", decision, outcome, {"issues": []}, experiment, test_result,
        verified_patch_reducers=["insert_required_input_guard"],
    )
    memory = _validated_memory(
        decision, experiment, reassessment, load_project_development_policy(),
    )

    assert reassessment["status"] == "validated"
    assert reassessment["issue_disposition"] == "resolved"
    assert memory["status"] == "validated"
    assert memory["authority"] == "verified_sandbox_outcome"


def test_unchanged_issue_cannot_enter_validated_memory():
    decision = {
        "selected_issue": {
            "issue_id": "ISSUE-001",
            "rule_id": "weak_contracts",
            "evidence": ["pkg/service.py:run"],
        },
        "selected_option": {"strategy": "contract_characterization"},
    }
    experiment = {
        "status": "verified",
        "patch_kinds": [],
        "source_invariant": {"unchanged": True},
        "checks": {"patch_scope_within_issue_evidence": True},
    }
    reassessment = _reassessment(
        "evaluated",
        decision,
        {"baseline_evidence": ["pkg/service.py:run"]},
        {"issues": [{"rule_id": "weak_contracts", "evidence": ["pkg/service.py:run"]}]},
        experiment,
        {"status": "ok", "summary": {"failed": 0}, "executable_acceptance_result": {"status": "passed"}},
    )
    memory = _validated_memory(
        decision, experiment, reassessment, load_project_development_policy(),
    )

    assert reassessment["status"] == "not_validated"
    assert "selected_issue_resolved_or_reduced" in reassessment["failed_checks"]
    assert memory["status"] == "not_promoted"
    assert memory["authority"] == "none"


def test_allowlisted_reducer_can_make_semantic_delta_ready():
    policy = load_project_development_policy()
    decision = {
        "selected_issue": {"rule_id": "weak_contracts"},
        "selected_option": {"option_id": "OPT-001"},
    }
    plan = {
        "artifact_type": "ImplementationPlan",
        "implementation_delta": {"status": "semantic_synthesis_required"},
        "patch_intent": {"status": "blocked"},
    }

    transformed = development_delta_transform(decision, policy)(plan)

    assert transformed["implementation_delta"]["status"] == "ready"
    assert transformed["implementation_delta"]["intent"]["operator_id"] == "insert_required_input_guard"
    assert plan["implementation_delta"]["status"] == "semantic_synthesis_required"


def test_experiment_admission_blocks_unknown_issue_reducer():
    policy = load_project_development_policy()
    plan = {
        "artifact_type": "ImplementationPlan",
        "implementation_delta": {"status": "semantic_synthesis_required"},
    }
    artifacts = {
        "spec": {"artifact_type": "TechnicalSpec"},
        "plan": development_delta_transform(
            {"selected_issue": {"rule_id": "unknown_issue"}}, policy,
        )(plan),
        "tests": {"artifact_type": "TestPlan"},
        "tree": {"artifact_type": "ProgrammerTaskTree"},
    }

    admission = _admission(
        {"status": "completed_aligned", "review_recommendation": "approve"},
        artifacts,
        policy,
        {"pilot_route": {"status": "eligible_for_full_chain"}},
    )

    assert admission["status"] == "blocked"
    assert "implementation_delta_ready" in admission["blocking_reasons"]


def test_experiment_admission_honors_analysis_only_pilot_stop():
    policy = load_project_development_policy()
    artifacts = {
        "spec": {"artifact_type": "TechnicalSpec"},
        "plan": {
            "artifact_type": "ImplementationPlan",
            "implementation_delta": {"status": "ready"},
        },
        "tests": {"artifact_type": "TestPlan"},
        "tree": {"artifact_type": "ProgrammerTaskTree"},
    }

    admission = _admission(
        {"status": "completed_aligned", "review_recommendation": "approve"},
        artifacts,
        policy,
        {"pilot_route": {"status": "analysis_only_stop"}},
    )

    assert admission["status"] == "blocked"
    assert "recognition_pilot_route_allows_experiment" in admission["blocking_reasons"]


def test_execution_feedback_routes_unproven_pattern_to_research():
    feedback = build_project_development_execution_feedback(
        handoff={"status": "completed_aligned"},
        experiment={
            "status": "failed",
            "selected_target": "pkg/service.py:run",
            "patch_count": 0,
            "patch_synthesis_status": "skipped",
            "patch_reason": "no_unique_development_helper_extraction",
            "reducer_selection": {"attempts": [{"operation_kind": "extract_splitlines_helper", "status": "skipped"}]},
        },
        reassessment={"status": "not_validated", "failed_checks": ["selected_issue_resolved_or_reduced"]},
        policy=load_project_development_policy(),
    )

    assert feedback["status"] == "action_required"
    assert feedback["decision"] == "research"
    assert feedback["next_roles"] == ["researcher", "architect"]
    assert feedback["evidence"]["reducer_attempts"][0]["status"] == "skipped"
    assert feedback["constraints"]["automatic_retry"] is False
    assert feedback["constraints"]["allowed_targets_preserved"] is True
    ContractRegistry({}).validate_artifact(feedback)


def test_execution_feedback_returns_failed_prepared_patch_to_architect():
    feedback = build_project_development_execution_feedback(
        handoff={"status": "completed_aligned"},
        experiment={"status": "failed", "patch_count": 1, "patch_reason": ""},
        reassessment={"status": "not_validated", "failed_checks": ["regression_suite_passed"]},
        policy=load_project_development_policy(),
    )

    assert feedback["decision"] == "needs_replanning"
    assert feedback["reason"] == "prepared_patch_verification_failed"
    assert feedback["next_roles"] == ["architect"]


def test_execution_feedback_unknown_failure_stops_without_retry():
    feedback = build_project_development_execution_feedback(
        handoff={"status": "completed_aligned"},
        experiment={"status": "blocked", "patch_count": 0},
        reassessment={"status": "not_validated", "reason": "experiment_admission_blocked"},
        policy=load_project_development_policy(),
    )

    assert feedback["decision"] == "controlled_stop"
    assert feedback["reason"] == "experiment_admission_blocked"
    assert feedback["next_roles"] == ["human"]
    assert feedback["constraints"]["scope_expansion_allowed"] is False


def test_execution_feedback_routes_missing_failure_reducer_to_research():
    feedback = build_project_development_execution_feedback(
        handoff={
            "status": "completed_aligned",
            "selected_target": "src/plugin.py:seed_fixture",
        },
        experiment={
            "status": "blocked",
            "patch_count": 0,
            "admission": {
                "blocking_reasons": [
                    "implementation_delta_ready",
                    "recognition_pilot_route_allows_experiment",
                ],
                "contract_mode": "failure_repair",
                "allowed_operator_ids": [],
                "implementation_delta_status": "semantic_synthesis_required",
            },
        },
        reassessment={"status": "not_validated", "reason": "experiment_admission_blocked"},
        policy=load_project_development_policy(),
    )

    assert feedback["decision"] == "research"
    assert feedback["reason"] == "no_verified_failure_reducer"
    assert feedback["evidence"]["selected_target"] == "src/plugin.py:seed_fixture"
    assert feedback["next_roles"] == ["researcher", "architect"]


def test_execution_feedback_closes_validated_experiment():
    feedback = build_project_development_execution_feedback(
        handoff={"status": "completed_aligned"},
        experiment={"status": "verified", "patch_count": 1},
        reassessment={"status": "validated", "failed_checks": []},
        policy=load_project_development_policy(),
    )

    assert feedback["status"] == "not_required"
    assert feedback["decision"] == "completed"
    assert feedback["reason"] == "experiment_validated"
    assert feedback["next_roles"] == []
