"""A green native example must not hide invalid output on equivalent layout."""
import ast
import hashlib
from copy import deepcopy
from pathlib import Path

import pytest

from plugins.python_transform_contracts.src.main import run, variants
from runtime.native_failure_acceptance import _probe
from runtime.stage_finalization_workspace import inventory
from runtime.upstream_owned_acceptance import prepare_owned_acceptance

ROOT = Path(__file__).resolve().parents[2]
SEED = 'match value:\n    case Box():\n        pass\n'


def payload(seed=SEED):
    return {'operation':'acceptance_tests','contract':'python_text_to_valid_python.v1',
        'module':'core','function':'transform','keyword_literals':{},'seed':seed}


def test_variants_preserve_input_ast_and_cover_empty_multiline_and_comment():
    rows = variants(SEED)
    assert len(rows) == 3
    assert '# acceptance' in rows[2]
    assert all(ast.dump(ast.parse(s)) == ast.dump(ast.parse(SEED)) for s in rows)
    assert 'Box(\n' in rows[1]
    assert all('ast.parse(result)' in t['source'] for t in run(payload())['tests'])


@pytest.mark.parametrize('source', ['x = "(text)"\n', 'x = 5\n'])
def test_strings_and_bracket_free_inputs_only_receive_seed_check(source):
    assert variants(source) == [source]


def test_invalid_grammar_is_not_a_passing_property():
    result = run(payload('match x:\n case (: pass'))
    assert result['status'] == 'not_applicable'
    assert result['tests'] == []


def test_ast_contract_is_explicit_and_stronger_than_syntax():
    data = payload('value = (item), other\n')
    data['contract'] = 'python_text_preserves_ast.v1'
    assert all('ast.dump(ast.parse(result)) == ast.dump(ast.parse(source))' in t['source'] for t in run(data)['tests'])
    assert all('ast.dump' not in t['source'] for t in run(payload())['tests'])


@pytest.mark.parametrize('field,value', [('module','core; import os'), ('function','yield'),
    ('keyword_literals',{'a':'danger()'})])
def test_invocation_is_static_literal_only(field, value):
    data = payload()
    data[field] = value
    with pytest.raises((ValueError,SyntaxError)):
        run(data)


@pytest.fixture
def case(tmp_path):
    project = tmp_path/'source';project.mkdir()
    (project/'core.py').write_text('def transform(source):\n    return source\n')
    test = project/'test_core.py'
    test.write_text('from core import transform\ndef test_example():\n    s = '+repr(SEED)+'\n    assert transform(s) == s\n')
    contract = {'schema_version':'upstream_task_contract.v1','origin':'assistant_supplied',
        'change_kind':'defect','requirements':[{'id':'R','statement':'Preserve valid Python.',
            'targets':['core.py:transform'],'acceptance_examples':[]}]}
    plan = {'capability':'python_transform_contracts','requirement_id':'R','payload':payload(),
        'seed_source':{'path':'test_core.py','sha256':hashlib.sha256(test.read_bytes()).hexdigest()}}
    return project, contract, plan


def test_property_rejects_wrong_repair_that_passes_original_example(case, tmp_path):
    project, contract, plan = case
    before = inventory(project)
    receipt = prepare_owned_acceptance(project,contract,plan,tmp_path/'accept',authorized=True,root=ROOT)
    assert receipt['status'] == 'baseline_verified'
    assert inventory(project) == before
    examples = receipt['task_contract']['requirements'][0]['acceptance_examples']
    assert len(examples) == 3 and all(e['origin']=='competency_property' for e in examples)
    output = Path(receipt['project'])
    # Simulates a formatter inserting a comma into an empty multiline group.
    (output/'core.py').write_text("def transform(source):\n    return source.replace('Box(\\n', 'Box(,\\n')\n")
    import sys
    result = _probe(output,tmp_path/'candidate',['test_core.py','test_cos_owned_acceptance.py'],[],60,Path(sys.executable))
    assert result['returncode'] == 1
    text = Path(result['output']).read_text(encoding='utf-8')
    assert '1 failed, 3 passed' in text


@pytest.mark.parametrize('mode',['stale','missing_seed','unauthorized'])
def test_refuses_unbound_seed_before_execution(case, tmp_path, mode):
    project, contract, plan = case
    plan = deepcopy(plan)
    if mode == 'stale':
        (project/'test_core.py').write_text('# changed')
    if mode == 'missing_seed':
        plan['payload']['seed'] = 'x = []\n'
    with pytest.raises(ValueError):
        prepare_owned_acceptance(project,contract,plan,tmp_path/'accept',authorized=mode!='unauthorized',root=ROOT)
    assert not (tmp_path/'accept').exists()
