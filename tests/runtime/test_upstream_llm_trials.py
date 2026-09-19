"""Scripted model responses with real native replay; not model-quality evidence."""
import json
from copy import deepcopy

import pytest

from runtime.local_inference import LocalInferenceConfig, LocalInferenceError
from runtime.stage_finalization_workspace import inventory
from runtime.upstream_causal_review import causal_comparison_checks
from runtime.upstream_llm_trials import validate_llm_diagnosis_proposals
from runtime.upstream_llm_candidates import build_model_candidates, validate_model_candidate
from tests.runtime.test_native_failure_acceptance import replay_case, TARGET, NODE


def _inputs(replay_case):
    project, spec = replay_case
    packet = spec['implementation_delta']['intent']['failure_evidence_packet']
    issue = {'failure_specific_reducer_required': True, 'affected_targets': [TARGET],
        'failure_evidence': [{'target': TARGET, 'failure_signature': packet['failure_signature'],
                             'failing_nodeids': [NODE]}], 'failure_evidence_packet': packet,
        'allowed_operator_ids': ['old'], 'training_replay_authority': {'status': 'explicitly_authorized'},
        'llm_training_replay': {'authorized': True}}
    return project, issue


def _hypothesis(issue):
    return {'target': TARGET, 'failure_signature': issue['failure_evidence'][0]['failure_signature'],
        'mechanism': 'Closing the channel leaves the caller-owned pending list unchanged.',
        'repair_mechanism': 'Mutate the shared pending list to preserve caller-visible ownership.',
        'mutation_contract': {'precondition': 'The channel retains the caller-owned list.',
            'change': 'Settle the pending items in place during channel close.',
            'preserved_behavior': 'The original list object remains visible to its owner.'},
        'residual_risks': ['Other close behaviors require complete native regression.'], 'confidence': 0.8}


def _response():
    return {'candidates': [
        {'id': 'rebind', 'replacement_source': 'def close(self):\n    self.pending = []\n',
         'reason': 'Test whether replacing the channel attribute clears caller observations.'},
        {'id': 'mutate', 'replacement_source': 'def close(self):\n    self.pending[:] = []\n',
         'reason': 'Test whether mutation of the existing list clears caller observations.'}]}


def _provider(monkeypatch, issue, payload=None):
    calls = []
    def hypothesis(messages, config=None):
        calls.append(('hypothesis', config))
        return _hypothesis(issue)
    def candidates(messages, config=None):
        calls.append(('candidates', config))
        return _response() if payload is None else payload
    monkeypatch.setattr('runtime.project_development_llm_hypothesis.call_json_chat', hypothesis)
    monkeypatch.setattr('runtime.upstream_llm_trials.call_json_chat', candidates)
    return calls


def _run(tmp_path, project, issue):
    return validate_llm_diagnosis_proposals({'issues': [issue]}, project=project,
        root=tmp_path, config=LocalInferenceConfig(base_url='http://example.test/v1', model='scripted'),
        authorized=True)['issues'][0]


def test_model_candidates_use_real_native_evidence_without_delivery(tmp_path, replay_case, monkeypatch):
    project, issue = _inputs(replay_case)
    before = inventory(project)
    calls = _provider(monkeypatch, issue)
    result = _run(tmp_path, project, issue)
    trial = result['llm_candidate_trial']
    assert trial['status'] == 'supported_hypothesis_review_required', trial
    comparison = trial['comparison']
    assert [r['outcome'] for r in comparison['attempts']] == [
        'contradicted_by_targeted_tests', 'supported_by_targeted_tests']
    assert comparison['selected_candidate_id'] == 'mutate'
    assert comparison['candidate_origin'] == 'llm_structured_proposal'
    assert len(calls) == trial['logical_model_calls'] == 2
    assert calls[0][1] is calls[1][1]
    assert result['allowed_operator_ids'] == []
    assert 'training_replay_authority' not in result and 'llm_training_replay' not in result
    assert result['repair_design']['execution_authority'] is False
    assert inventory(project) == before
    from pathlib import Path
    assert json.loads(Path(trial['receipt_path']).read_text(encoding='utf-8')) == trial
    # A supported model proposal cannot masquerade as an executable training recipe.
    selected = comparison['attempts'][1]
    spec = {'implementation_delta': {'intent': {'causal_comparison': comparison,
        'failure_evidence_packet': issue['failure_evidence_packet']}}}
    assert not all(r['passed'] for r in causal_comparison_checks(spec, selected['evidence']))
    assert issue['allowed_operator_ids'] == ['old']


@pytest.mark.parametrize('corruption', ['stale_packet', 'wrong_failure', 'wrong_target'])
def test_preflight_rejects_before_spending_or_writing(tmp_path, replay_case, monkeypatch, corruption):
    project, original = _inputs(replay_case)
    issue = deepcopy(original)
    calls = _provider(monkeypatch, issue)
    if corruption == 'stale_packet':
        issue['failure_evidence_packet']['project_inventory_digest'] = 'stale'
    elif corruption == 'wrong_failure':
        issue['failure_evidence'][0]['failure_signature'] = 'another-failure'
    else:
        issue['affected_targets'] = ['channel.py:Other.close']
    result = _run(tmp_path, project, issue)
    assert result['llm_candidate_trial']['status'] == 'not_compared'
    assert calls == [] and not (tmp_path / 'artifacts').exists()
    assert result['allowed_operator_ids'] == []


@pytest.mark.parametrize('bad', [
    {'id': 'extra', 'replacement_source': 'def close(self):\n    pass\n', 'reason': 'x', 'commands': []},
    {'id': 'extra', 'replacement_source': 'def close(self, other):\n    return other\n', 'reason': 'x'},
    {'id': 'extra', 'replacement_source': 'def close(self) -> bool:\n    return True\n', 'reason': 'x'},
    {'id': 'extra', 'replacement_source': 'def close(self):\n    return\nprint(1)', 'reason': 'x'},
])
def test_all_candidates_validated_before_any_execution(tmp_path, replay_case, monkeypatch, bad):
    project, issue = _inputs(replay_case)
    payload = {'candidates': [_response()['candidates'][1], bad]}
    calls = _provider(monkeypatch, issue, payload)
    monkeypatch.setattr('runtime.upstream_llm_trials.compare_causal_candidates',
        lambda **kw: pytest.fail('invalid candidate set executed'))
    result = _run(tmp_path, project, issue)
    assert result['llm_candidate_trial']['status'] == 'not_compared'
    assert result['llm_candidate_trial']['candidate_response'] == payload
    assert len(calls) == 2


def test_provider_failure_has_receipt_and_no_retry(tmp_path, replay_case, monkeypatch):
    project, issue = _inputs(replay_case)
    calls = _provider(monkeypatch, issue)
    def unavailable(*args, **kwargs):
        raise LocalInferenceError('provider unavailable')
    monkeypatch.setattr('runtime.upstream_llm_trials.call_json_chat', unavailable)
    result = _run(tmp_path, project, issue)
    assert result['llm_candidate_trial']['reason'] == 'provider unavailable'
    assert len(calls) == 1
    assert result['llm_candidate_trial']['automatic_retry'] is False
    assert result['causal_feedback']['reason'] == 'provider unavailable'


def test_disproved_candidate_routes_to_design_reconciliation(tmp_path, replay_case, monkeypatch):
    project, issue = _inputs(replay_case)
    _provider(monkeypatch, issue, {'candidates': [_response()['candidates'][0]]})
    result = _run(tmp_path, project, issue)
    assert result['causal_comparison']['status'] == 'no_supported_candidate'
    assert result['causal_feedback']['role'] == 'architect'
    assert result['causal_feedback']['next_action'] == 'reconcile_design_and_candidate_with_native_counterexample'
    assert result['repair_design']['execution_authority'] is False


def test_model_provenance_and_patch_cannot_be_substituted(replay_case):
    project, issue = _inputs(replay_case)
    packet = issue['failure_evidence_packet']
    source = (project / 'channel.py').read_bytes().decode('utf-8')
    advisory = {'model_response_digest': 'response-fixture'}
    candidate = build_model_candidates(_response(), packet=packet, advisory=advisory, source=source)[1]
    validate_model_candidate(candidate, packet, source)
    candidate['replacement_source'] += '\nprint(1)\n'
    with pytest.raises(ValueError, match='replacement_mismatch'):
        validate_model_candidate(candidate, packet, source)
    candidate['provenance']['packet_digest'] = 'another-packet'
    with pytest.raises(ValueError, match='provenance_mismatch'):
        validate_model_candidate(candidate, packet, source)


def test_trial_requires_explicit_authority(tmp_path):
    with pytest.raises(ValueError, match='authorization'):
        validate_llm_diagnosis_proposals({}, project=tmp_path, root=tmp_path, config=None)


def test_two_supported_model_interventions_return_to_analyzer(tmp_path, replay_case, monkeypatch):
    project, issue = _inputs(replay_case)
    response = _response()
    response['candidates'][0]['replacement_source'] = 'def close(self):\n    self.pending.clear()\n'
    _provider(monkeypatch, issue, response)
    result = _run(tmp_path, project, issue)
    assert result['llm_candidate_trial']['status'] == 'ambiguous'
    assert result['causal_comparison']['selected_candidate_id'] is None
    assert result['causal_feedback']['role'] == 'analyzer'
    assert result['repair_design']['execution_authority'] is False


def test_development_routes_model_trial_through_roles_without_kb_or_delivery(tmp_path, replay_case, monkeypatch):
    import sys
    from pathlib import Path
    from runtime.native_failure_acceptance import _probe
    from runtime.project_development import run_project_development
    from runtime.stage_finalization_workspace import snapshot
    original, issue = _inputs(replay_case)
    # Project metadata is present before intake; rebuild packet inventory for this copy.
    project = tmp_path / 'project'
    snapshot(original, project, inventory(original))
    (project / 'pyproject.toml').write_text("[project]\nname='trial-demo'\nversion='0.1.0'\n")
    code = (project / 'channel.py').read_text()
    (project / 'channel.py').write_text(code.replace('pass', 'self.pending = list(self.pending)'))
    repetitions = []
    for i in range(2):
        probe = _probe(project, tmp_path / f'chain-intake-{i}', [NODE], [], 10, Path(sys.executable))
        assert probe['returncode'] == 1
        repetitions.append({'failure_signature': probe['intake_signature'], 'exit_code': 1,
            'leaf_production_target': TARGET, 'production_targets': [TARGET],
            'output_tail': Path(probe['output']).read_text(encoding='utf-8')})
    failure = {'target': TARGET, 'failure_signature': repetitions[0]['failure_signature'],
        'failing_nodeids': [NODE], 'authority': 'failing_contract_test',
        'detail': repetitions[0]['output_tail']}
    issue['failure_evidence'] = [failure]
    chain = {'project_stratum': 'library_pure_transform', 'contract_failure_evidence': [failure],
        'repetitions': repetitions}
    _provider(monkeypatch, issue)
    monkeypatch.setattr('runtime.project_development_core.enrich_failure_diagnosis',
        lambda *a, **kw: pytest.fail('model trial consulted training KB'))
    monkeypatch.setattr('runtime.project_development_experiment.run_programmer_executor',
        lambda **kw: pytest.fail('trial evidence granted delivery'))
    # Root supplies pipeline contracts; redirect only trial outputs to this test's workspace.
    real_trial = validate_llm_diagnosis_proposals
    monkeypatch.setattr('runtime.upstream_llm_trials.validate_llm_diagnosis_proposals',
        lambda *a, **kw: real_trial(*a, **{**kw, 'root': tmp_path}))
    before = inventory(project)
    result = run_project_development(root=Path(__file__).resolve().parents[2], project_dir=project,
        goal='Close shared pending observations', chain_case=chain, run_role_chain=True,
        run_sandbox_experiment=False, authorize_training_replay=True, validate_causal_proposals=True,
        llm_hypothesis_config=LocalInferenceConfig(base_url='http://example.test/v1', model='scripted'))
    chosen = result['decision']['selected_issue']
    assert chosen['llm_candidate_trial']['status'] == 'supported_hypothesis_review_required', chosen['llm_candidate_trial']
    artifacts = result['role_artifacts']
    assert artifacts['architecture_decision']['causal_comparison'] == chosen['causal_comparison']
    delta = artifacts['technical_spec']['implementation_delta']
    assert delta['intent']['causal_comparison'] == chosen['causal_comparison']
    assert delta['intent']['authority'] == 'none' and delta['status'] != 'ready'
    assert result['status'] != 'experiment_validated'
    assert inventory(project) == before


def test_comparator_rejects_late_invalid_candidate_before_first_probe(tmp_path, replay_case, monkeypatch):
    from runtime.upstream_causal_trials import compare_causal_candidates
    project, issue = _inputs(replay_case)
    packet = issue['failure_evidence_packet']
    source = (project / 'channel.py').read_bytes().decode('utf-8')
    candidates = build_model_candidates(_response(), packet=packet,
        advisory={'model_response_digest': 'scripted'}, source=source)
    candidates[1]['provenance']['target'] = 'channel.py:other'
    monkeypatch.setattr('runtime.upstream_causal_trials.run_native_acceptance',
        lambda **kw: pytest.fail('partial set executed'))
    with pytest.raises(ValueError, match='provenance_mismatch'):
        compare_causal_candidates(project=project, packet=packet, candidates=candidates,
            work_dir=tmp_path / 'runs', authorized=True, candidate_origin='llm_structured_proposal')
    assert not (tmp_path / 'runs').exists()


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
def test_function_candidate_preserves_other_bytes_and_line_endings(replay_case, newline):
    _, issue = _inputs(replay_case)
    source = 'class Channel:\n    # retained comment\n    def close(self):\n        pass\n\n# retained tail\n'
    source = source.replace('\n', newline)
    candidate = build_model_candidates({'candidates': [_response()['candidates'][1]]},
        packet=issue['failure_evidence_packet'], advisory={'model_response_digest': 'scripted'}, source=source)[0]
    expected = source.replace('        pass', '        self.pending[:] = []')
    assert candidate['replacement_source'] == expected


@pytest.mark.parametrize('payload', [[], {'candidates': []}, {'candidates': [None]},
    {'candidates': _response()['candidates'] * 3},
    {'candidates': [_response()['candidates'][0]] * 2}])
def test_malformed_candidate_sets_are_rejected(replay_case, payload):
    project, issue = _inputs(replay_case)
    source = (project / 'channel.py').read_bytes().decode('utf-8')
    with pytest.raises(ValueError):
        build_model_candidates(payload, packet=issue['failure_evidence_packet'],
                               advisory={'model_response_digest': 'scripted'}, source=source)
