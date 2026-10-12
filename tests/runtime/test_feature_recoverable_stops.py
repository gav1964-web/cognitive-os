import json
from pathlib import Path
import sys
import pytest
from runtime.feature_workspace import digest
from runtime.feature_quality import run_quality_development, route_failure
from runtime.feature_development import run_feature_development
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_feature_development import project, fake_chat
from tests.runtime.test_feature_quality import augment


def transport(project, calls, stop):
    delegate=fake_chat(project)
    def chat(messages,*,config):
        role=config.provider_label.partition(':')[2]
        calls.append(role)
        if role=='reviewer':
            payload=json.loads(messages[1]['content'])
            contract=payload['delivery_contract']
            assert contract['already_installed'] is False
            bodies={t['path']:t['content'] for t in payload['artifacts']['spec_writer']['tests']}
            for name,sha in contract['frozen_acceptance_tests'].items():
                assert digest(bodies[name].encode('utf-8'))==sha
            assert contract['frozen_acceptance_tests']
        if role in ('spec_auditor','design_auditor'):return {'decision':'approve'}
        if role=='reviewer' and stop[0] in ('review','stop'):
            raise ValueError('feature_stop_requested' if stop[0]=='stop' else 'feature_call_count_exhausted')
        if role=='programmer' and stop[0]=='before_code':raise ValueError('feature_stop_requested')
        value=augment(role,delegate(messages,config=config))
        if role=='reviewer':value['goal_complete']=stop[0]!='partial'
        if role=='programmer' and stop[0]=='echo':
            value['edits'].append({'path':'tests/test_labels.py','source_sha256':None,'content':'assert True'})
        return value
    return chat


@pytest.mark.parametrize('kind',['review','stop','before_code','echo','completed','partial'])
def test_settled_stop_resumes_without_rewriting_accepted_spec(project,tmp_path,kind):
    calls=[];stop=[kind];chat=transport(project,calls,stop)
    cfg=LocalInferenceConfig('http://unused','fake')
    kwargs=dict(project=project,goal='negative labels',python=Path(sys.executable),chat=chat,
                configs={r:cfg for r in ('analyzer','architect','spec_writer')})
    prior=tmp_path/'old/cycle-0'
    first=run_feature_development(work=prior,**kwargs)
    reason='feature_call_count_exhausted' if kind=='review' else 'feature_frozen_test_echo_changed'
    if kind in ('stop','before_code'):reason='feature_stop_requested'
    if kind in ('completed','partial'):assert first['status']=='verified'
    else:assert first['reason']==reason
    frozen=(prior/'spec_writer.json').read_bytes()
    stop[0]=False;calls.clear()
    result=run_quality_development(work=tmp_path/'new',resume_roles=prior,challenges=False,**kwargs)
    assert result['status']=='verified',result
    assert 'analyzer' not in calls and 'architect' not in calls and 'spec_writer' not in calls
    assert 'reviewer' in calls
    if kind in ('review','stop','completed','partial'):assert 'programmer' not in calls
    assert (prior/'spec_writer.json').read_bytes()==frozen
    assert result['source_unchanged']


def test_only_programmer_echo_error_is_routed():
    assert route_failure({'reason':'feature_frozen_test_echo_changed'})=='programmer'
    assert route_failure({'reason':'feature_frozen_spec_changed'}) is None


@pytest.mark.parametrize('reason',['feature_call_count_exhausted','feature_next_call_budget_exhausted','feature_stop_requested'])
def test_resource_stop_never_reroutes_to_repeat_native_cycles(project,tmp_path,reason):
    delegate=fake_chat(project);calls=[]
    def chat(messages,*,config):
        role=config.provider_label.partition(':')[2];calls.append(role)
        if role=='reviewer':raise ValueError(reason)
        if role in ('spec_auditor','design_auditor'):return {'decision':'approve'}
        return augment(role,delegate(messages,config=config))
    cfg=LocalInferenceConfig('http://unused','fake')
    result=run_quality_development(project=project,work=tmp_path/'stopped',goal='negative labels',
        python=Path(sys.executable),chat=chat,configs={r:cfg for r in ('analyzer','architect','spec_writer')},max_cycles=4)
    assert result['status']=='blocked' and result['reason']==reason
    assert len(result['cycles'])==1 and calls.count('reviewer')==1
    assert route_failure({'reason':reason,'attempts':[{'passed':True}]}) is None
    receipt=json.loads((Path(result['cycles'][0]['checkpoint'])/'report.json').read_text())
    assert receipt['attempts'][0]['passed'] and receipt['frozen_test_hashes']
