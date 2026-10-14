"""Pre-repair proposals retain provenance and must reproduce native outcomes."""
from copy import deepcopy

import pytest

from runtime.upstream_acceptance_proposals import propose_acceptance, materialize_acceptance
from runtime.stage_finalization_workspace import inventory


@pytest.fixture
def case(tmp_path):
    project = tmp_path / 'source'
    project.mkdir()
    (project / 'core.py').write_text('def double(x):\n    return x\n')
    (project / 'test_core.py').write_text('from core import double\ndef test_double():\n    assert double(2) == 4\n')
    contract = {'schema_version':'upstream_task_contract.v1','origin':'assistant_supplied',
        'change_kind':'defect','requirements':[{'id':'R','statement':'Double the input.',
        'targets':['core.py:double'],'acceptance_examples':[{'kind':'native_test',
        'nodeid':'test_core.py::test_double','expectation':'passes','baseline_expectation':'fails'}]}]}
    response = {'tests':[{'requirement_id':'R','baseline_expectation':'fails',
        'reason':'Negative values distinguish doubling from absolute-value repairs.',
        'source':'def test_negative():\n    from core import double\n    assert double(-2) == -4\n'}]}
    return project, contract, response


def proposal(case, response=None):
    project, contract, expected = case
    return propose_acceptance(project, contract, config=None, chat=lambda messages, **kw: response or expected)


def test_native_pre_repair_check_retains_source_tests_and_mixed_provenance(case, tmp_path):
    project, contract, _ = case
    before = inventory(project)
    value = proposal(case)
    result = materialize_acceptance(project, value, tmp_path/'run', authorized=True)
    assert result['status'] == 'baseline_verified'
    assert inventory(project) == before
    assert result['task_contract']['origin'] == contract['origin']
    examples = result['task_contract']['requirements'][0]['acceptance_examples']
    assert examples[0] == contract['requirements'][0]['acceptance_examples'][0]
    assert examples[1]['origin'] == 'model_proposal'
    assert result['semantic_adequacy'] == 'not_independently_verified'
    assert result['source_apply'] is False


def test_wrong_baseline_prediction_is_not_accepted(case, tmp_path):
    response = deepcopy(case[2])
    response['tests'][0]['baseline_expectation'] = 'passes'
    value = proposal(case, response)
    result = materialize_acceptance(case[0], value, tmp_path/'run', authorized=True)
    assert result['status'] == 'not_verified'


def test_missing_import_is_not_a_valid_baseline_counterexample(case, tmp_path):
    response = deepcopy(case[2])
    response['tests'][0]['source'] = 'def test_negative():\n    assert missing(-2) == -4\n'
    value = proposal(case, response)
    result = materialize_acceptance(case[0], value, tmp_path/'run', authorized=True)
    assert result['status'] == 'not_verified'


@pytest.mark.parametrize('change', ['stale', 'tampered', 'unauthorized'])
def test_rejects_before_writing_or_executing(case, tmp_path, change):
    value = proposal(case)
    if change == 'stale':
        (case[0]/'core.py').write_text('def double(x):\n    return x * 2\n')
    if change == 'tampered':
        value['response']['tests'][0]['source'] += '# altered\n'
    with pytest.raises(ValueError):
        materialize_acceptance(case[0], value, tmp_path/'run', authorized=change != 'unauthorized')
    assert not (tmp_path/'run').exists()


@pytest.mark.parametrize('source', [
    'import os\ndef test_x():\n    assert True',
    'def test_x(value):\n    assert value',
    'async def test_x():\n    assert True',
    'def test_x():\n    pass',
    '@decorator\ndef test_x():\n    assert True',
])
def test_unsupported_shapes_rejected(case, source):
    response = deepcopy(case[2])
    response['tests'][0]['source'] = source
    with pytest.raises(ValueError, match='ordinary_asserting'):
        proposal(case, response)


def test_changed_source_during_model_call_rejected(case):
    def chat(messages, **kw):
        assert 'BEFORE' in messages[0]['content']
        (case[0]/'core.py').write_text('def double(x):\n    return x * 2\n')
        return case[2]
    with pytest.raises(ValueError, match='sources_changed'):
        propose_acceptance(case[0], case[1], config=None, chat=chat)


@pytest.mark.parametrize('key', ['requirement_id', 'baseline_expectation'])
def test_unhashable_response_values_are_validation_errors(case, key):
    response = deepcopy(case[2])
    response['tests'][0][key] = []
    with pytest.raises(ValueError, match='invalid_acceptance'):
        proposal(case, response)
