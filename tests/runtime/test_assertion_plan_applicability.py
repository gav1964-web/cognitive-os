import json
import pytest

from runtime.local_inference import LocalInferenceConfig
from runtime.upstream_llm_trials import validate_llm_diagnosis_proposals
from tests.runtime.test_native_failure_acceptance import replay_case
from tests.runtime.test_upstream_llm_trials import _inputs, _hypothesis, _response


@pytest.mark.parametrize('mode,error,invoked', [
 ('when_supported',None,True),
 ('when_supported','only_direct_test_assertions_supported',True),
 (True,'only_direct_test_assertions_supported',False),
 ('when_supported','complete_source_bound_assertions_required',False),
])
def test_applicability_preserves_native_verification_and_rejects_corrupt_evidence(
        tmp_path,replay_case,monkeypatch,mode,error,invoked):
    project,issue=_inputs(replay_case)
    if error:
        def unsupported(packet):raise ValueError(error)
        monkeypatch.setattr('runtime.repair_assertion_contract.build_assertion_contract',unsupported)
    calls=[]
    def chat(messages,*,config):
        calls.append(messages)
        envelope=json.loads(messages[1]['content'])
        if len(calls)==1:
            payload=_hypothesis(issue)
            if envelope.get('assertion_contract'):
                payload['assertion_plan']=[{'assertion_id':r['id'],
                    'behavior':'Preserve caller-visible list identity while clearing pending items.'}
                    for r in envelope['assertion_contract']['assertions']]
            return payload
        return _response()
    result=validate_llm_diagnosis_proposals({'issues':[issue]},project=project,root=tmp_path,
        config=LocalInferenceConfig(base_url='http://example.invalid',model='scripted'),authorized=True,
        require_assertion_plan=mode,chat=chat)['issues'][0]
    assert bool(calls)==invoked
    trial=result['llm_candidate_trial']
    if invoked:
        assert trial['comparison']['status']=='selected_for_regression'
        assert trial['assertion_planning']['status']==('unsupported' if error else 'required')
        assert ('assertion_contract' in result)==(error is None)
    else:
        assert trial['reason']==error
