"""Acceptance follows the configured TestPlan handoff, preserving required evidence."""
from tools.mvp_acceptance_role_checks import tester_role_skill_ok as check_handoff


def test_tester_acceptance_requires_task_tree_builder_handoff():
    payload = {
        'artifact_type': 'TestPlan', 'role': 'tester', 'status': 'ok',
        'acceptance_tests': ['positive'], 'negative_tests': ['negative'],
        'smoke_checklist': ['smoke'], 'regression_risks': ['risk'],
        'reproducibility': {'command': 'pytest'}, 'forbidden_actions_observed': [],
        'artifact_path': 'artifacts/test-plan.json',
        'next_artifact': {'recommended_role': 'task_tree_builder'},
    }
    context = {'returncode': 0, 'payload': payload}
    assert check_handoff(context)[0]
    payload['next_artifact']['recommended_role'] = 'reviewer'
    assert not check_handoff(context)[0]
    payload['next_artifact']['recommended_role'] = 'task_tree_builder'
    payload['acceptance_tests'] = []
    assert not check_handoff(context)[0]
