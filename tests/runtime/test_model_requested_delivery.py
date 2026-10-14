"""Explicit repair and preservation contracts through scripted model delivery."""
from copy import deepcopy
from pathlib import Path

import pytest

from runtime.narrow_type_evidence_binding import content_digest
from runtime.upstream_requested_review import requested_change_checks
from runtime.upstream_causal_review import causal_comparison_checks
from runtime.programmer_model_delivery import model_delivery_precheck
from tests.runtime.test_model_candidate_delivery import _run_case, TARGET, NODE

SOURCE = 'def invert(value: bool) -> bool:\n    return bool(value) and False\n'
KEEP = 'tests/test_logic.py::test_true'


def test_explicit_plugin_survives_model_request_and_execution(tmp_path):
    _, result = _run_case(tmp_path, source=SOURCE, task_contract=_contract(), native_plugin=True)
    assert result['status'] == 'experiment_validated', result['requested_change'].get('reason')
    proof = result['requested_change']['acceptance']
    assert proof['native_replay_settings']['pytest_plugins'] == ['env_plugin']


def _contract():
    return {'schema_version': 'upstream_task_contract.v1', 'change_kind': 'defect',
        'origin': 'assistant_authored_development_fixture', 'requirements': [
            {'id': ident, 'statement': statement, 'targets': [TARGET], 'acceptance_examples': [
                {'kind': 'native_test', 'nodeid': node, 'expectation': 'passes', 'baseline_expectation': baseline}]}
            for ident, statement, node, baseline in [
                ('REPAIR', 'Invert False to True.', NODE, 'fails'),
                ('PRESERVE', 'Keep True mapped to False.', KEEP, 'passes')]]}


@pytest.fixture(scope='module')
def requested(tmp_path_factory):
    project, result = _run_case(tmp_path_factory.mktemp('model-requested'), source=SOURCE, task_contract=_contract())
    assert result['status'] == 'experiment_validated', {
        'request': result['requested_change'], 'experiment': result['experiment'],
        'handoff': result['role_chain_handoff']}
    return project, result


def test_requirements_reach_prompts_ticket_native_suite_and_reviewer(requested):
    project, result = requested
    issue = result['decision']['selected_issue']
    request = issue['requested_change']
    proof = request['acceptance']
    ticket = issue['model_delivery']
    assert request['status'] == 'verified_for_regression'
    assert [r['baseline_expectation'] for r in proof['bindings']] == ['fails', 'passes']
    assert proof['probes'][0]['passing'] == 1 and proof['probes'][1]['passing'] == 2
    assert ticket['task_contract_digest'] == request['contract']['contract_digest']
    assert ticket['requested_acceptance_digest'] == proof['receipt_digest']
    assert ticket['requested_change_digest'] == request['request_digest']
    artifacts = result['role_artifacts']
    spec = artifacts['technical_spec']
    assert {r['id'] for r in spec['requirements']} >= {'REPAIR', 'PRESERVE'}
    assert all(r['target']==TARGET for r in spec['requirements'])
    from runtime.narrow_type_role_semantics import _requirements_target_bound, _concrete_spec_action
    assert _requirements_target_bound(spec,TARGET)
    assert _concrete_spec_action(spec,TARGET)
    assert artifacts['implementation_plan']['implementation_delta']['intent']['model_delivery'] == ticket
    assert all(r['passed'] for r in requested_change_checks(spec, {}))
    assert all(r['passed'] for r in causal_comparison_checks(spec, {}))
    assert result['experiment']['final_review']['recommendation'] == 'approve'
    assert (project / 'logic.py').read_text(encoding='utf-8') == SOURCE


@pytest.mark.parametrize('bad', ['preservation', 'baseline'])
def test_unmet_declared_observation_revokes_model_delivery(tmp_path, bad):
    contract = _contract()
    replacement = 'return bool(value) or True' if bad == 'preservation' else 'return not bool(value)'
    if bad == 'baseline':
        contract['requirements'][1]['acceptance_examples'][0]['baseline_expectation'] = 'fails'
    _, result = _run_case(tmp_path, source=SOURCE, replacement=replacement, task_contract=contract)
    issue = result['decision']['selected_issue']
    assert issue['causal_comparison']['status'] == 'selected_for_regression'
    assert issue['requested_change']['status'] == 'needs_clarification'
    assert issue['requested_change']['execution_authorized'] is False
    assert 'model_delivery' not in issue and issue['allowed_operator_ids'] == []
    assert result['status'] != 'experiment_validated'
    assert not (tmp_path / 'exec').exists()


def test_invalid_request_stops_before_any_model_call(tmp_path):
    contract = _contract()
    contract['constraints'] = [{'key': 'unverified_performance', 'value': 'always under 1ms'}]
    _, result = _run_case(tmp_path, source=SOURCE, task_contract=contract, expected_calls=0)
    assert result['requested_change']['status'] == 'needs_clarification'
    assert result['decision']['selected_issue']['llm_candidate_trial']['logical_model_calls'] == 0
    assert not (tmp_path / 'exec').exists()


@pytest.mark.parametrize('change', ['drop_contract', 'drop_requirement', 'statement', 'proof', 'ticket_contract'])
def test_requirement_or_proof_substitution_cannot_pass_review(requested, change):
    _, result = requested
    artifacts = deepcopy(result['role_artifacts'])
    spec = artifacts['technical_spec']
    if change == 'drop_contract':
        spec.pop('task_contract')
    elif change == 'drop_requirement':
        spec['requirements'] = [r for r in spec['requirements'] if r['id'] != 'PRESERVE']
    elif change == 'statement':
        next(r for r in spec['requirements'] if r['id'] == 'PRESERVE')['statement'] = 'Return any truth value.'
    elif change == 'proof':
        request = spec['requested_change']
        proof = request['acceptance']
        proof['patched_inventory_digest'] = 'another-patch'
        proof['receipt_digest'] = content_digest({k: v for k, v in proof.items() if k != 'receipt_digest'})
        request['request_digest'] = content_digest({k: v for k, v in request.items() if k != 'request_digest'})
    else:
        ticket = spec['implementation_delta']['intent']['model_delivery']
        ticket['task_contract_digest'] = 'another-contract'
        ticket['delivery_digest'] = content_digest({k: v for k, v in ticket.items() if k != 'delivery_digest'})
    assert not all(r['passed'] for r in requested_change_checks(spec, {}))
    assert not all(r['passed'] for r in causal_comparison_checks(spec, {}))
    assert model_delivery_precheck(spec, artifacts['implementation_plan']) is not None


def test_request_cannot_be_added_after_failure_only_proposal(tmp_path):
    from runtime.upstream_requested_change import prepare_requested_change, bind_requested_change
    from runtime.upstream_role_handoff import frame_analysis
    project, result = _run_case(tmp_path, source=SOURCE)
    request = prepare_requested_change(frame_analysis({'root': str(project)}, _contract()), project)
    bound = bind_requested_change(result['diagnosis'], request, project=project, root=tmp_path)
    issue = next(r for r in bound['issues'] if r.get('failure_specific_reducer_required'))
    assert issue['requested_change']['reason'] == 'model_request_was_not_in_proposal'
    assert 'model_delivery' not in issue


def test_all_thirteen_requirements_reach_hypothesis_prompt(tmp_path, monkeypatch):
    import json
    from runtime.project_development_llm_hypothesis import build_llm_failure_hypothesis
    from runtime.upstream_task_contract import normalize_task_contract
    from tests.runtime.test_project_development_llm_hypothesis import _issue, _project, _config, _payload
    issue = _issue()
    contract = normalize_task_contract({'schema_version': 'upstream_task_contract.v1',
        'origin': 'assistant_authored_development_fixture', 'change_kind': 'defect', 'requirements': [
            {'id': f'REQ-{i}', 'statement': f'Preserve observation {i}', 'targets': issue['affected_targets']}
            for i in range(13)]})
    issue['requested_task_contract'] = contract
    observed = []
    def provider(messages, config=None):
        observed.append(json.loads(messages[1]['content'])['task_contract'])
        return _payload()
    monkeypatch.setattr('runtime.project_development_llm_hypothesis.call_json_chat', provider)
    result = build_llm_failure_hypothesis(issue=issue, project_dir=_project(tmp_path), config=_config())
    assert result['status'] == 'accepted_hypothesis_only'
    assert observed == [contract]


def test_oversized_requirement_prompt_is_rejected_without_a_model_call(tmp_path, monkeypatch):
    from runtime.project_development_llm_hypothesis import build_llm_failure_hypothesis
    from runtime.upstream_task_contract import normalize_task_contract
    from tests.runtime.test_project_development_llm_hypothesis import _issue, _project, _config
    issue = _issue()
    issue['requested_task_contract'] = normalize_task_contract({
        'schema_version': 'upstream_task_contract.v1', 'origin': 'assistant_authored_development_fixture',
        'change_kind': 'defect', 'requirements': [{'id': str(i), 'statement': 'large ' * 500} for i in range(9)]})
    monkeypatch.setattr('runtime.project_development_llm_hypothesis.call_json_chat',
        lambda *a, **kw: pytest.fail('oversized prompt invoked model'))
    result = build_llm_failure_hypothesis(issue=issue, project_dir=_project(tmp_path), config=_config())
    assert result['status'] == 'rejected' and result['model_invoked'] is False
    assert result['errors'] == ['requested_hypothesis_prompt_budget_exceeded']
