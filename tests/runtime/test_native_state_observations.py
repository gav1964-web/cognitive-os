"""Actual AST shape, yielded callback and preserved-case state reach model input."""
import ast
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from runtime.native_failure_acceptance import _probe
from runtime.native_observation_values import state_value
from runtime.native_repair_observations import collect_native_repair_observations
from runtime.narrow_type_evidence_binding import content_digest
from runtime.project_failure_evidence_packet import build_failure_evidence_packet
from runtime.project_native_failure_binding import _interpret_pytest_result
from runtime.repair_diagnostic_context import diagnostic_context
from runtime.repair_observations import validate_repair_observations, observation_context
from runtime.repair_preservation import collect_preservation_evidence


@pytest.fixture(scope='module')
def state_case(tmp_path_factory):
    root = tmp_path_factory.mktemp('native-state')
    project = root/'project'
    project.mkdir()
    (project/'pytest.ini').write_text('[pytest]\n')
    (project/'api.py').write_text('import ast\nfrom callbacks import visit\n'
        'def render(value):\n    callbacks = list(visit(ast.parse(value).body[0].value))\n'
        '    return callbacks[0]()\n')
    (project/'callbacks.py').write_text('from functools import partial\nfrom helpers import convert\n'
        'def register(fn):\n    return fn\n@register\n'
        'def visit(node):\n    one = len(node.elts) == 1\n'
        '    callback = partial(convert, one=one)\n    yield callback\n')
    (project/'helpers.py').write_text("def convert(one):\n    return 'one' if one else 'broken'\n"
        "def unused():\n    return 'unused'\n")
    (project/'test_case.py').write_text('from api import render\n'
        "def test_failure():\n    assert render('(1,2)') == 'two'\n"
        "def test_preserved():\n    assert render('(1,)') == 'one'\n")
    nodes = ['test_case.py::test_failure']
    records = []
    for i in range(2):
        probe = _probe(project, root/f'intake-{i}', nodes, [], 60, Path(sys.executable))
        output = Path(probe['output']).read_text(encoding='utf-8')
        records.append({**_interpret_pytest_result(project, probe['returncode'], output, {}), 'output': output})
    packet = build_failure_evidence_packet(project_dir=project, failure={
        'target':'api.py:render', 'failure_signature':records[0]['failure_signature'],
        'failing_nodeids':nodes, 'detail':records[0]['output'], 'failure_kind':'test_failed'},
        chain_case={'repetitions':records})
    assert packet['status']=='complete'
    preservation = collect_preservation_evidence(project=project, packet=packet,
        nodeids=['test_case.py::test_preserved'], work_dir=root/'preserved', authorized=True)
    evidence = collect_native_repair_observations(project,packet,root/'state',authorized=True,
        source_files=['api.py','callbacks.py','helpers.py'], preservation=preservation,
        method_fields={'callbacks.py:visit':['node','one','callback'], 'helpers.py:convert':['one'], 'helpers.py:unused':[]})
    return project,packet,evidence


def test_native_state_distinguishes_failure_from_preserved_case(state_case):
    project,packet,evidence=state_case
    validate_repair_observations(project,packet,evidence)
    rows=observation_context(evidence)['rows']
    assert [r['test_outcome'] for r in rows]==['failed','passed']
    for row,arity,one in zip(rows,[2,1],[False,True]):
        visits=[c for c in row['calls'] if c['target']=='callbacks.py:visit']
        assert len(visits)==1  # A resumed generator is the same invocation.
        call=visits[0]
        assert call['events'][0]['locals']['node']['fields']['elts']['length']==arity
        yields=[e for e in call['events'] if e['event']=='yield']
        assert len(yields)==1
        assert yields[0]['yielded']['function']['target']=='helpers.py:convert'
        assert yields[0]['yielded']['keywords']['one']['value'] is one
        assert call['events'][-1]['event']=='return'
        assert call['return']['value'] is None
        helper=next(c for c in row['calls'] if c['target']=='helpers.py:convert')
        assert helper['events'][0]['locals']['one']['value'] is one
    compact=observation_context(evidence,compact=True)
    assert all(v==['helpers.py:unused'] for v in compact['not_observed_targets_by_test'].values())
    rebuilt=deepcopy(compact['rows'])
    for row in rebuilt:
        for call in row['calls']:
            fields={}
            for event in call['events']:
                fields.update(event['locals']);event['locals']=deepcopy(fields)
    assert rebuilt==rows
    context=diagnostic_context({'failure_evidence_packet':packet,'repair_observations':evidence},project)
    assert context['native_test_observations']['rows']==compact['rows']


@pytest.mark.parametrize('mutation',['values','source','scope','probe','preservation'])
def test_changed_state_cannot_be_rehashed_into_valid_evidence(state_case,mutation):
    project,packet,evidence=state_case
    changed=deepcopy(evidence)
    if mutation=='values':
        for r in changed['repeats']:
            r['observation']['rows'][0]['calls'][0]['events'][0]['locals']['node']={'type':'invented'}
    elif mutation=='source':changed['project_inventory_digest']='sha256:changed'
    elif mutation=='scope':changed['state_scope']['source_files']=['api.py']
    elif mutation=='probe':changed['probe_hashes']['native_observation_values.py']='0'*64
    else:changed['state_scope']['preservation']['nodeids']=[]
    changed['observations_digest']=content_digest({k:v for k,v in changed.items() if k!='observations_digest'})
    with pytest.raises(ValueError):validate_repair_observations(project,packet,changed)


@pytest.mark.parametrize('sources',[[],['../outside.py'],['test_case.py']])
def test_state_scope_rejected_before_execution(state_case,tmp_path,sources):
    project,packet,_=state_case
    with pytest.raises(ValueError):
        collect_native_repair_observations(project,packet,tmp_path/'never',authorized=True,
            method_fields={'api.py:render':['value']},source_files=sources)
    assert not (tmp_path/'never').exists()


def test_opaque_objects_and_ast_subclasses_do_not_execute_hooks():
    class Hostile(ast.Tuple):
        def __getattribute__(self,name):pytest.fail('user attribute access')
        def __repr__(self):pytest.fail('user repr')
    assert state_value(Hostile(),{})=={'type':'opaque','value_omitted':True}
    value=state_value(ast.parse('(1,2,3,4,5)').body[0].value,{})
    assert value['fields']['elts']['length']==5
    assert value['fields']['elts']['omitted_items']==2
    assert len(value['fields']['elts']['items'])==3
