from __future__ import annotations

from runtime.programmer_executor_playbooks import load_programmer_executor_playbooks, select_executor_playbooks


def test_executor_playbooks_load_active_policy():
    policy = load_programmer_executor_playbooks()

    assert policy["status"] == "active"
    assert policy["admission_policy"]["automatic_source_mutation_allowed"] is False
    assert any(row["id"] == "executor_playbook_fixture_profile_gap" for row in policy["playbooks"])


def test_executor_playbooks_match_acceptance_boundaries():
    matches = select_executor_playbooks(
        {"signal_strength": "meta_only", "skipped_reason_counts": {"positive_sample_execution_failed": 2}}
    )

    assert [row["id"] for row in matches] == ["executor_playbook_fixture_profile_gap"]
    assert matches[0]["authority"] == "advisory_playbook_only"
    assert "regression_test_added" in matches[0]["required_gates"]


def test_executor_playbooks_rebind_nested_closure():
    matches = select_executor_playbooks(
        {"signal_strength": "meta_only", "skipped_reason_counts": {"nested_function_requires_closure": 1}}
    )

    assert [row["id"] for row in matches] == ["executor_playbook_nested_closure_rebind"]
    assert matches[0]["action"] == "request_implementation_plan_contract_rebind"
