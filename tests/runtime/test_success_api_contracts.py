from copy import deepcopy
import hashlib
import json

import pytest

from plugins.project_description.src.api_inputs import analyze_inputs
from plugins.project_description.src.api_contracts import build
from runtime.competency_knowledge import invoke_knowledge, ROOT
from runtime.single_claim_review import prepare_claim_review, run_claim_review, checked_job
from runtime.claim_review_proposals import checked_proposal
from runtime.narrow_type_evidence_binding import content_digest
from tests.runtime.test_lean_claim_review import saved_report
from tests.runtime.test_return_property_review import response


SOURCE = '''def execute(profile=None):
    if profile is None:
        return {'status': 'blocked'}
    return {'status': 'ok'}
'''


@pytest.mark.parametrize('inputs,expected', [({},False),({'profile':None},False),({'profile':True},True),({'profile':False},True)])
def test_success_is_distinct_from_normal_return(inputs, expected):
    normal = analyze_inputs(SOURCE, 'execute', inputs)
    success = analyze_inputs(SOURCE, 'execute', inputs, success={'field':'status','expected':'ok'})
    functions = {}
    exec(SOURCE, functions)  # Author-controlled fixture, never inspected source.
    actual = functions['execute'](**inputs)
    assert normal['status'] == 'holds_in_model'
    assert success['field_matches'] == (actual['status'] == 'ok') == expected
    assert success['status'] == ('holds_in_model' if expected else 'counterexample_in_model')


@pytest.mark.parametrize('code,status', [
    ('def execute():\n    return backend()\n', 'unknown'),
    ('def execute():\n    return {"other":"ok"}\n', 'counterexample_in_model'),
    ('def execute():\n    return None\n', 'counterexample_in_model'),
    ('def execute():\n    return helper()\ndef helper():\n    return {"status":"ok"}\n', 'holds_in_model'),
])
def test_success_field_handles_missing_values_and_unknown_calls(code, status):
    assert analyze_inputs(code, 'execute', {}, success={'field':'status','expected':'ok'})['status'] == status


def job(tmp_path, code=SOURCE):
    text='The omitted profile still yields status ok.'
    report=saved_report(tmp_path,code,text)
    return prepare_claim_review(report,'purpose',claim_namespace='final',return_property={
        'path':'example.py','symbol':'execute','kind':'return_field_equals_for_inputs',
        'inputs':{},'field':'status','expected':'ok','claim_start':0,'claim_end':len(text)})


def test_error_status_cannot_be_relabelled_as_successful_normal_return(tmp_path):
    selected=job(tmp_path)
    raw=response(selected)
    raw['parts'][0]['reason']='Returning a dictionary means success.'
    report=run_claim_review(selected,chat=lambda *a,**k:deepcopy(raw))
    assert report['result']['verdict']=='uncertain'
    assert report['raw_response']==raw
    checked_proposal(report)


def test_changed_success_expectation_invalidates_saved_analysis(tmp_path):
    selected=job(tmp_path)
    selected['return_property']['expected']='blocked'
    selected.pop('digest')
    selected['digest']=content_digest(selected)
    with pytest.raises(ValueError,match='return_property_evidence_or_instruction_changed'):
        checked_job(selected)


def packet(folder, files):
    sources=[]
    for i,(name,text) in enumerate(files.items()):
        path=folder/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')
        sources.append({'id':f's{i}','path':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'excerpt':text})
    return {'root':str(folder),'sources':sources}


def facts(folder, evidence, symbol='execute'):
    source=evidence['sources'][0]
    return invoke_knowledge('project_description',{'action':'api_contracts','project_root':str(folder),
        'evidence':evidence,'requests':[{'path':source['path'],'sha256':source['sha256'],'symbol':symbol}]})['api_contract_facts']


def test_cross_module_alias_preserves_validator_and_error_handler(tmp_path):
    evidence=packet(tmp_path,{
        'pkg/api.py':'from .checks import require as verify\ndef execute(profile=None):\n    try:\n        verify(profile)\n        return {"status":"ok"}\n    except ValueError:\n        return {"status":"blocked"}\n',
        'pkg/checks.py':'def require(profile):\n    if profile is None:\n        raise ValueError("required")\n    return profile\n'})
    result=facts(tmp_path,evidence)
    assert any(e['target']=='pkg/checks.py:require' for e in result['calls'])
    by_symbol={f['symbol']:f for f in result['functions']}
    assert by_symbol['execute']['defaults'][0]['quote']=='None'
    assert by_symbol['execute']['handler_excerpts'] and by_symbol['require']['guard_excerpts']
    assert not result['semantic_verified'] and not result['source_executed']


@pytest.mark.parametrize('body', [
    '    verify = external\n    return verify(profile)\n',
    '    def verify(value):\n        return True\n    return verify(profile)\n',
    '    from opaque import verify\n    return verify(profile)\n',
])
def test_shadowed_import_is_not_linked_to_original_validator(tmp_path, body):
    evidence=packet(tmp_path,{'api.py':'from check import verify\ndef execute(profile=None):\n'+body,
        'check.py':'def verify(profile):\n    return True\n'})
    result=facts(tmp_path,evidence)
    assert not any(e['target']=='check.py:verify' for e in result['calls'])


def test_unknown_dependency_stays_unresolved(tmp_path):
    evidence=packet(tmp_path,{'api.py':'from opaque import verify\ndef execute(profile=None):\n    return verify(profile)\n'})
    result=facts(tmp_path,evidence)
    assert result['calls'][0]['status']=='unresolved'


def test_stale_graph_source_cannot_be_used(tmp_path):
    evidence=packet(tmp_path,{'api.py':SOURCE})
    (tmp_path/'api.py').write_text(SOURCE+'\n# changed',encoding='utf-8')
    with pytest.raises(ValueError,match='source_changed'):
        facts(tmp_path,evidence)


def test_private_file_rejected_even_with_matching_hash(tmp_path):
    evidence=packet(tmp_path,{'credentials.py':SOURCE})
    with pytest.raises(ValueError,match='source_path'):
        facts(tmp_path,evidence)


def test_star_import_disables_ambiguous_entry_binding(tmp_path):
    evidence=packet(tmp_path,{'api.py':'from external import *\n'+SOURCE})
    with pytest.raises(ValueError,match='ambiguous'):
        facts(tmp_path,evidence)


def test_limited_graph_does_not_silently_claim_completeness(tmp_path):
    calls='\n'.join('    remote'+str(i)+'()' for i in range(7))
    evidence=packet(tmp_path,{'api.py':'def execute():\n'+calls+'\n    return True\n'})
    result=facts(tmp_path,evidence)
    assert result['limited'] and len(result['calls'])==3
