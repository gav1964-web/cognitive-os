"""Source-bound invocation facts reach both writers without certifying prose."""
import hashlib
import json

import pytest

from runtime.competency_knowledge import invoke_knowledge
from runtime.project_description import describe_project
from runtime.project_failure_evidence_packet import _test_source


def setup(tmp_path, default='None', body=None):
    text = body or ('def check(profile):\n    if profile is None:\n        raise ValueError("missing")\n    return True\n'
        f'def execute(profile={default}, unchanged=False):\n    try:\n        check(profile)\n'
        '        return {"status":"ready", "unchanged":unchanged}\n'
        '    except ValueError:\n        return {"status":"blocked", "unchanged":unchanged}\n')
    (tmp_path/'core.py').write_text(text,encoding='utf-8')
    digest = hashlib.sha256((tmp_path/'core.py').read_bytes()).hexdigest()
    return {'path':'core.py','sha256':digest,'symbol':'execute','inputs':{},'field':'status','expected':'ready'}


@pytest.mark.parametrize('default,status', [('None','counterexample_in_model'),('True','holds_in_model')])
def test_opposite_defaults_have_distinct_facts_in_both_prompts(tmp_path, default, status):
    check = setup(tmp_path,default)
    seen = []
    def chat(messages, **kw):
        request = json.loads(messages[1]['content'])
        seen.append(request)
        facts = request['behavior_facts']
        assert facts['checks'][0]['analysis']['status'] == status
        assert facts['claim_binding'] == 'not_established'
        claim = {'text':'Reports readiness.', 'evidence_ids':[facts['checks'][0]['evidence_id']]}
        answer = {'purpose':claim,'scenarios':[dict(claim)],'data_flow':[dict(claim)],'unknowns':[],'confidence':'medium'}
        if 'draft_claims' in request:
            return {'description':answer,'corrections':[],'claim_reviews':[
                {'claim_id':r['id'],'action':'retained','reason':'Fixture response.',
                 'evidence_ids':r['evidence_ids']} for r in request['draft_claims']]}
        return answer
    report = describe_project(tmp_path,behavior_checks=[check],chat=chat)
    assert report['status'] == 'described'
    assert len(seen) == 2
    assert not report['behavior_facts']['semantic_verified']
    assert report['verification']['semantic_review_required']


def test_stale_selector_rejected_before_inference(tmp_path):
    check = setup(tmp_path)
    check['sha256'] = '0'*64
    with pytest.raises(ValueError,match='source_bound'):
        describe_project(tmp_path,behavior_checks=[check],chat=lambda *a,**k:pytest.fail('must not infer'))


def test_unknown_dependency_not_promoted_to_behavior_proof(tmp_path):
    check = setup(tmp_path,body='def execute():\n    return external()\n')
    evidence = invoke_knowledge('project_description',{'project_root':str(tmp_path)})['evidence']
    facts = invoke_knowledge('project_description',{'project_root':str(tmp_path),'action':'behavior_checks',
        'evidence':evidence,'behavior_checks':[check]})['behavior_facts']
    assert facts['checks'][0]['analysis']['status'] == 'unknown'


def test_test_source_uses_class_selector_before_repeated_leaf_name(tmp_path):
    (tmp_path/'test_case.py').write_text('class TestA:\n    def test_same(self):\n        assert 1 == 2\n'
        'class TestB:\n    def test_same(self):\n        assert 3 == 3\n')
    excerpt = _test_source(tmp_path,'test_case.py::TestA::test_same')['excerpt']
    assert 'assert 1 == 2' in excerpt and 'assert 3 == 3' not in excerpt
