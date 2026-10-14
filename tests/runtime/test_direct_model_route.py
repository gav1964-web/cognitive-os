"""Direct route preserves native authority and makes no invented hypothesis claim."""
import json
from copy import deepcopy

import pytest

from runtime.local_inference import LocalInferenceConfig
from runtime.upstream_llm_trials import validate_llm_diagnosis_proposals
from runtime.repair_trial_binding import bind_repair_diagnosis
from runtime.upstream_model_requirements import model_issue_intent
from runtime.upstream_model_delivery import validate_delivery_source, selected_model_candidate
from runtime.narrow_type_evidence_binding import content_digest
from tests.runtime.test_repair_target_nomination import evidence
from tests.runtime.test_repair_trial_binding import repair_case, issue_for


def trial(repair_case, tmp_path, **kwargs):
    project, observation, bundle, _ = repair_case
    diagnosis = bind_repair_diagnosis({'issues':[issue_for(observation)]}, project=project, bundle=bundle)
    return validate_llm_diagnosis_proposals(diagnosis, project=project, root=tmp_path,
        config=LocalInferenceConfig(base_url='http://example.invalid', model='scripted'),
        authorized=True, delivery_authorized=True, proposal_route='direct',
        require_assertion_plan=True, **kwargs)['issues'][0]


def candidate(value):
    return {'candidates':[{'id':'repair', 'reason':'Satisfy the original supplied native assertions.',
        'replacement_source':f'def convert_bad(self):\n    return {value!r}\n'}]}


def test_direct_native_retry_preserves_obligations_and_delivery_provenance(repair_case,tmp_path,monkeypatch):
    calls=[]
    def respond(messages, *, config):
        envelope=json.loads(messages[1]['content'])
        assert 'design' not in envelope and 'hypothesis' not in envelope
        assert len(envelope['assertion_contract']['assertions'])==2
        if calls:
            assert envelope['native_counterexamples']['examples']
        calls.append(messages)
        return candidate('wrong' if len(calls)==1 else 'fixed')
    monkeypatch.setattr('runtime.upstream_llm_trials.call_json_chat',respond)
    monkeypatch.setattr('runtime.project_development_llm_hypothesis.call_json_chat',
        lambda *a,**kw: pytest.fail('direct route invoked a hypothesis'))
    issue=trial(repair_case,tmp_path,semantic_retries=1)
    assert len(calls)==2
    assert issue['llm_candidate_trial']['total_logical_model_calls']==2
    assert issue['llm_candidate_trial']['status']=='model_candidate_replay_ready'
    assert 'llm_hypothesis_advisory' not in issue and 'causal_hypothesis' not in issue
    validate_delivery_source(repair_case[0],model_issue_intent(issue))
    comparison=deepcopy(issue['causal_comparison'])
    proof=comparison['attempts'][0]['provenance']
    proof.pop('request_context_digest')
    proof['provenance_digest']=content_digest({k:v for k,v in proof.items() if k!='provenance_digest'})
    comparison['comparison_digest']=content_digest({k:v for k,v in comparison.items() if k!='comparison_digest'})
    with pytest.raises(ValueError,match='selected_evidence_invalid'):
        selected_model_candidate(comparison,issue['failure_evidence_packet'])


@pytest.mark.parametrize('payload',[[], {'candidates':[]}, {'candidates':None},
    {**candidate('fixed'), 'candidate_id':'repair'},
    {'candidates':[{'id':'bad','reason':'Bad scope must not execute.',
        'replacement_source':"def convert_bad(self):\n    return 'fixed'\n\ndef other(): pass\n"}]}])
def test_direct_bad_response_is_controlled_without_delivery(repair_case,tmp_path,monkeypatch,payload):
    calls=[]
    def respond(*args,**kwargs):
        calls.append(1)
        return payload
    monkeypatch.setattr('runtime.upstream_llm_trials.call_json_chat',respond)
    result=trial(repair_case,tmp_path)
    assert calls==[1]
    assert result['llm_candidate_trial']['status']=='not_compared'
    assert 'model_delivery' not in result


def test_route_selection_cannot_bypass_authorization(tmp_path):
    config=LocalInferenceConfig(base_url='http://example.invalid',model='scripted')
    with pytest.raises(ValueError,match='explicit_training_trial_authorization'):
        validate_llm_diagnosis_proposals({},project=tmp_path,root=tmp_path,config=config,proposal_route='direct')
    with pytest.raises(ValueError,match='invalid_model_proposal_route'):
        validate_llm_diagnosis_proposals({},project=tmp_path,root=tmp_path,config=config,authorized=True,proposal_route='typo')


def test_direct_requested_behavior_reaches_final_review(tmp_path):
    from tests.runtime.test_model_candidate_delivery import _run_case
    from tests.runtime.test_model_requested_delivery import _contract, SOURCE
    _,result=_run_case(tmp_path,source=SOURCE,task_contract=_contract(),expected_calls=1,proposal_route='direct')
    assert result['status']=='experiment_validated',result['requested_change']
    issue=result['decision']['selected_issue']
    assert issue['requested_change']['status']=='verified_for_regression'
    assert issue['model_delivery']['task_contract_digest']==issue['requested_change']['contract']['contract_digest']
    assert result['experiment']['final_review']['recommendation']=='approve'
