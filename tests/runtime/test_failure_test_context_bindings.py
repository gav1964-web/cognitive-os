"""Binding evidence must distinguish assigning a name from mutating its value."""
import ast

import pytest

from runtime.failure_test_context import test_support_context


def test_function_metadata_does_not_hide_helper():
    source = ('def helper(): return 7\n'
              'helper.__test__ = False\n'
              'def test_case(): assert helper() == 7\n')
    tree = ast.parse(source)
    result = test_support_context(source, tree, tree.body[-1])
    assert result['ambiguous_names'] == []
    assert any('def helper()' in row['excerpt'] for row in result['sources'])
    assert result['authority'] == 'diagnostic_only'
    assert result['pytest_fixture_resolution_complete'] is False


@pytest.mark.parametrize('mutation', [
    'helper.flag = False', 'helper.flag: bool = False',
    'helper["flag"] = False', 'helper[index] = False',
    'helper.flag, other = False, 1',
    'helper[index], other = False, 1',
])
def test_mutation_targets_do_not_rebind_loaded_base_or_index(mutation):
    source = ('index = "flag"\ndef helper(): return index\n' + mutation
              + '\ndef test_case(): assert helper()\n')
    tree = ast.parse(source)
    result = test_support_context(source, tree, tree.body[-1])
    assert result['ambiguous_names'] == []
    assert any('def helper()' in row['excerpt'] for row in result['sources'])
    assert any('index = "flag"' in row['excerpt'] for row in result['sources'])


@pytest.mark.parametrize('binding', [
    'helper = None', 'helper: object = None',
    'helper, other = None, 1', '[other, *helper] = [1, 2]',
    'other = helper = None',
])
def test_actual_rebindings_stay_ambiguous(binding):
    source = 'def helper(): return 7\n' + binding + '\ndef test_case(): assert helper()\n'
    tree = ast.parse(source)
    result = test_support_context(source, tree, tree.body[-1])
    assert result['ambiguous_names'] == ['helper']
    assert result['sources'] == []


def test_destructuring_binds_each_stored_name():
    source = 'left, [right, *rest] = 1, [2, 3]\ndef test_case(): assert left and right and rest\n'
    tree = ast.parse(source)
    result = test_support_context(source, tree, tree.body[-1])
    assert result['ambiguous_names'] == []
    assert len(result['sources']) == 1
    assert result['sources'][0]['excerpt'] == source.splitlines()[0]
