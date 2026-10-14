from copy import deepcopy
import pytest
from plugins.development_quality.src.main import run


def proposal():
    return {'status': 'ready', 'regression_tests': [],
            'tests': [{'path': 'tests/test_x.py', 'content': 'assert f(1) == 2\n'}],
            'case_plan': [{'kind': 'preservation', 'node': 'test_x'}]}


@pytest.mark.parametrize('prediction,allowed', [('feature_control', True), ('preservation', False)])
def test_qualified_label_contract_requires_same_baseline_meaning(prediction, allowed):
    old = {'node': 'tests/test_x.py::test_x', 'kind': 'feature_control', 'behavior': 'feature control'}
    new = {**old, 'kind': 'boundary'}
    result = run({'action': 'allow_qualified_label_correction', 'previous': old, 'current': new,
                  'artifact': {'baseline_expectations': [{'node': old['node'], 'classification': prediction}]}})
    assert result == {'contract': 'development_quality.v1', 'allowed': allowed, 'grants_approval': False}


def repair(value, paths):
    return run({'action': 'repair_metadata', 'artifact': value, 'source_paths': paths})


def test_only_derived_label_changes_without_mutating_input():
    raw = proposal()
    before = deepcopy(raw)
    result = repair(raw, ['engine.py'])
    assert raw == before
    assert result['artifact'] == {**before, 'regression_policy': 'new_preservation_only'}
    assert result['changes'] and result['grants_approval'] is False
    assert not repair(result['artifact'], ['engine.py'])['changes']


@pytest.mark.parametrize('paths', [None, [], ['test_old.py'], ['tests/test_old.py'],
                                  ['engine_test.py'], ['test.py']])
def test_missing_inventory_or_existing_suite_never_authorizes_label(paths):
    raw = proposal()
    assert repair(raw, paths)['artifact'] == raw


@pytest.mark.parametrize('change', [{'regression_policy': None}, {'regression_policy': 'skip'},
    {'regression_tests': ['test_old.py']}, {'regression_tests': None},
    {'case_plan': []}, {'case_plan': None}, {'status': 'read'}])
def test_explicit_conflict_or_missing_preservation_is_not_repaired(change):
    raw = {**proposal(), **change}
    assert repair(raw, ['engine.py'])['artifact'] == raw
