import json
from copy import deepcopy

import pytest

from runtime.local_inference import LocalInferenceConfig
from runtime.project_development_llm_hypothesis import _validate_payload, _messages
from runtime.repair_trial_binding import bind_repair_diagnosis
from runtime.upstream_llm_trials import validate_llm_diagnosis_proposals
from tests.runtime.test_repair_trial_binding import repair_case, evidence, issue_for


def hypothesis(packet):
    return {'target': packet['target'], 'failure_signature': packet['failure_signature'],
        'mechanism': 'The observed internal method returns a broken value on the reached branch.',
        'repair_mechanism': 'Correct the reached return while preserving the successful alternative branch.',
        'mutation_contract': {'precondition': 'The failing call reaches the internal bad converter.',
            'change': 'Change the reached R1 return to the required fixed result.',
            'preserved_behavior': 'Preserve the existing successful dispatch branch.'},
        'residual_risks': ['Other callers require native regression.'], 'confidence': 0.8}


@pytest.mark.parametrize('kind', ['correct', 'wrong_id', 'unaddressed'])
def test_diagnosis_requires_grounded_return_references(repair_case, kind):
    _, _, _, packet = repair_case
    payload = {**hypothesis(packet), 'reached_return_ids': ['R1']}
    envelope = {'target': packet['target'], 'failure_signature': packet['failure_signature'],
                'reached_returns': [{'id':'R1','source':"return 'broken'"}]}
    if kind == 'wrong_id':payload['reached_return_ids']=['R2']
    if kind == 'unaddressed':payload.pop('reached_return_ids')
    _, errors = _validate_payload(payload, envelope)
    assert bool(errors) == (kind != 'correct')
    schema = _messages(envelope)[0]['content']
    assert 'reached_return_ids' in schema


@pytest.mark.parametrize('second_fixed', [True, False])
@pytest.mark.parametrize('format_first', [True, False])
def test_native_counterexample_retry_is_bounded_and_preserves_both_trials(repair_case, tmp_path, monkeypatch, second_fixed, format_first):
    project, observation, bundle, packet = repair_case
    diagnosis = bind_repair_diagnosis({'issues':[issue_for(observation)]},project=project,bundle=bundle)
    calls=[]
    def propose(messages,config):
        envelope=json.loads(messages[1]['content'])
        if calls:
            assert envelope['native_counterexamples']['examples'][0]['native_output']
        calls.append('hypothesis')
        return {**hypothesis(packet), 'assertion_plan': [
            {'assertion_id': r['id'], 'behavior': 'Preserve the assertion result after the internal correction.'}
            for r in envelope['assertion_contract']['assertions']]}
    def patch(messages,config):
        if format_first and calls==['hypothesis']:
            calls.append('format_error')
            return {'candidates':[{'id':'bad','replacement_source':'import os\ndef convert_bad(self):\n    return 1\n','reason':'Invalid shape before native comparison.'}]}
        fixed=second_fixed and calls.count('hypothesis')>1
        calls.append('patch')
        value='fixed' if fixed else 'still broken'
        return {'candidates':[{'id':'candidate','replacement_source':f"def convert_bad(self):\n    return {value!r}\n",
                               'reason':'Test the proposed internal result against unchanged native assertions.'}]}
    monkeypatch.setattr('runtime.project_development_llm_hypothesis.call_json_chat',propose)
    monkeypatch.setattr('runtime.upstream_llm_trials.call_json_chat',patch)
    result=validate_llm_diagnosis_proposals(diagnosis,project=project,root=tmp_path,
        config=LocalInferenceConfig(base_url='http://example.invalid',model='scripted'),authorized=True,semantic_retries=1,format_retries=int(format_first),
        require_assertion_plan=True)
    issue=result['issues'][0]
    assert calls==(['hypothesis','format_error','patch','hypothesis','patch'] if format_first else ['hypothesis','patch','hypothesis','patch'])
    assert issue['llm_candidate_trial']['total_logical_model_calls']==len(calls)
    assert len(issue['prior_llm_trials'])==1
    assert issue['prior_llm_trials'][0]['status']=='no_supported_candidate'
    assert issue['llm_candidate_trial']['status']==('supported_hypothesis_review_required' if second_fixed else 'no_supported_candidate')
    from runtime.repair_counterexamples import native_counterexamples
    comparison=deepcopy(issue['prior_native_comparison']);comparison['packet_digest']='changed'
    with pytest.raises(ValueError):native_counterexamples(project,packet,comparison)
    from runtime.repair_counterexamples import bind_saved_counterexample
    saved = bind_saved_counterexample(diagnosis, project, issue['prior_native_comparison'])
    assert saved['issues'][0]['native_counterexamples'] == issue['native_counterexamples']
    assert saved['issues'][0]['saved_counterexample_origin']['comparison_digest'] == issue['prior_native_comparison']['comparison_digest']
    from runtime.narrow_type_evidence_binding import content_digest
    forged = deepcopy(issue['prior_native_comparison'])
    forged['attempts'][0]['provenance']['replacement_function'] = 'def convert_bad(self):\n    return 99\n'
    forged['comparison_digest'] = content_digest({k:v for k,v in forged.items() if k!='comparison_digest'})
    with pytest.raises(ValueError): bind_saved_counterexample(diagnosis, project, forged)
    from runtime.repair_diagnostic_context import bind_diagnostic_context, diagnostic_context
    comparison = issue['prior_native_comparison']
    retained = bind_diagnostic_context(diagnosis, project, history=[comparison])
    context = diagnostic_context(retained['issues'][0], project)
    assert context['counterexample_history'][0]['comparison_digest'] == comparison['comparison_digest']
    assert context['counterexample_history'][0]['replacement_function'] == comparison['attempts'][0]['provenance']['replacement_function']
    with pytest.raises(ValueError, match='duplicate'):
        bind_diagnostic_context(diagnosis, project, history=[comparison, comparison])


@pytest.mark.parametrize('budget', [True, -1, 2, '1'])
def test_unbounded_native_retry_budgets_rejected(tmp_path, budget):
    with pytest.raises(ValueError,match='native_retry'):
        validate_llm_diagnosis_proposals({},project=tmp_path,root=tmp_path,authorized=True,
            config=LocalInferenceConfig(base_url='http://example.invalid',model='scripted'),semantic_retries=budget,format_retries=1)
