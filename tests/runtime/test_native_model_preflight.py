"""Reject incompatible native evidence before a paid candidate request."""
import sys

import pytest

from runtime.local_inference import LocalInferenceConfig
from runtime.project_development_policy import load_project_development_policy
from runtime.project_failure_evidence_packet import build_failure_evidence_packet
from runtime.project_native_failure_intake import run_project_native_failure_intake
from runtime.upstream_llm_trials import validate_llm_diagnosis_proposals


@pytest.mark.parametrize('mode', ['plain', 'rewrite'])
def test_native_protocol_checked_before_model(tmp_path, monkeypatch, mode):
    project = tmp_path / 'project'
    (project / 'tests').mkdir(parents=True)
    (project / 'logic.py').write_text('def zero():\n    return "0/1"\n')
    (project / 'tests/test_logic.py').write_text(
        'from logic import zero\ndef test_zero():\n    assert zero() == "0"\n')
    policy = load_project_development_policy()
    policy['native_failure_intake'].update(local_editable_install=False,
        python_executable=sys.executable, timeout_seconds=15, shard_on_timeout=False,
        pytest_arguments=['-q', '--tb=long', '--color=no', '--assert=' + mode])
    case = run_project_native_failure_intake(root=tmp_path, projects=[project],
        project_stratum='library_pure_transform', test_targets=['tests/test_logic.py'],
        policy=policy)['cases'][0]
    assert case['status'] == 'qualified_failure'
    failure = case['change_request']['contract_failure_evidence'][0]
    packet = build_failure_evidence_packet(project_dir=project, failure=failure, chain_case=case)
    issue = {'failure_specific_reducer_required': True, 'affected_targets': [packet['target']],
        'failure_evidence': [failure], 'failure_evidence_packet': packet}
    calls = []
    def respond(*args, **kwargs):
        calls.append(True)
        return {'candidates': [{'id': 'repair', 'replacement_source': 'def zero():\n    return "0"\n',
            'reason': 'Satisfy the supplied native zero representation contract.'}]}
    monkeypatch.setattr('runtime.upstream_llm_trials.call_json_chat', respond)
    result = validate_llm_diagnosis_proposals({'issues': [issue]}, project=project,
        root=tmp_path, config=LocalInferenceConfig(base_url='http://example.invalid', model='scripted'),
        authorized=True, delivery_authorized=True, proposal_route='direct')['issues'][0]
    trial = result['llm_candidate_trial']
    if mode == 'plain':
        assert calls == []
        assert trial['logical_model_calls'] == 0
        assert trial['native_preflight']['reason'] == 'recorded_baseline_not_reproduced'
        assert 'model_delivery' not in result
    else:
        assert len(calls) == 1
        assert trial['native_preflight']['status'] == 'passed'
        assert trial['status'] == 'model_candidate_replay_ready'
    assert (project / 'logic.py').read_text() == 'def zero():\n    return "0/1"\n'
