"""Conditional counterexamples, bounded models and explicit unsupported cases."""
import hashlib
from pathlib import Path

import pytest

from plugins.project_description.src.return_flags import analyze_function
from plugins.project_description.src.scalar_boundary import examples
from runtime.competency_knowledge import invoke_knowledge


def program(guard=''):
    return ('def run(old, new):\n    result = {}\n'
            '    result["same"] = old == new\n' + guard + '    return result\n')


def test_reported_false_is_allowed_but_raise_blocks_normal_false_return():
    reported = analyze_function(program(), 'run')
    guarded = analyze_function(program('    if not result["same"]:\n        raise ValueError()\n'), 'run')
    witness = reported['model']['fields'][0]['false_return_witness']
    assert witness['outcome'] == 'returned' and witness['flags']['same'] is False
    assert guarded['model']['fields'][0]['false_return_witness'] is None
    assert guarded['model']['fields'][0]['all_normal_returns_true_in_model']
    assert not guarded['full_function_reachability_proven']
    assert not reported['source_executed'] and not reported['semantic_verified']


def test_prefix_and_impossible_predicates_never_become_executed_counterexamples():
    text = program().replace('old == new', '1 == 1')
    result = analyze_function(text, 'run')
    assert result['model']['fields'][0]['false_return_witness']
    assert not result['full_function_reachability_proven']
    assert 'not an executed project counterexample' in result['conclusion_limit']
    assert any('not be jointly feasible' in a for a in result['assumptions'])


def test_no_normal_returns_does_not_vacuously_certify_true():
    result = analyze_function(program('    if not result["same"]:\n        raise ValueError()\n'
                                     '    if result["same"]:\n        raise ValueError()\n'), 'run')
    assert result['model']['normal_returns'] == 0
    assert not result['model']['fields'][0]['all_normal_returns_true_in_model']


@pytest.mark.parametrize('body', [
    '    result["same"] = opaque()\n    return result\n',
    '    result["same"] = old == new\n    result.update(other)\n    return result\n',
    '    result["same"] = old == new\n    result["same"] = old != new\n    return result\n',
    '    if not result["same"]:\n        raise ValueError()\n    return result\n',
    '    return {"same": True}\n',
])
def test_opaque_mutating_reassigned_or_unmodeled_suffix_is_unsupported(body):
    result = analyze_function('def run(old, new):\n    result = {}\n' + body, 'run')
    assert result['status'] == 'unsupported' and 'model' not in result


def test_decorators_and_extra_module_statements_are_not_executed():
    assert analyze_function('@dangerous()\n'+program(), 'run')['status'] == 'unsupported'
    assert analyze_function('raise RuntimeError()\n'+program(), 'run')['status'] == 'unsupported'


@pytest.mark.parametrize('operator,expected', [('>=', True), ('>', False), ('<=', True), ('<', False)])
def test_integer_equality_boundary_is_computed_without_running_source(operator, expected):
    text = 'def run(amount):\n    result = {}\n    result["accepted"] = amount '+operator+' 0\n    return result\n'
    row = analyze_function(text, 'run')['integer_boundaries']['p0']
    assert row['cases'][1] == {'value': 0, 'predicate_result': expected}
    assert not row['full_function_reachability_proven']


def test_number_of_predicates_is_bounded():
    text = 'def run(x):\n    result = {}\n'
    text += ''.join(f'    result["flag{i}"] = x == {i}\n' for i in range(7))
    assert analyze_function(text+'    return result\n', 'run')['status'] == 'unsupported'


def test_registered_analysis_checks_source_hash_and_never_executes_module(tmp_path):
    file = tmp_path / 'app.py'
    file.write_text('raise RuntimeError("DO_NOT_EXECUTE")\n'+program(), encoding='utf-8')
    request = {'path': 'app.py', 'symbol': 'run', 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}
    result = invoke_knowledge('project_description', {'project_root': str(tmp_path),
        'action': 'return_flags', 'requests': [request]})['return_flag_analysis']
    assert result['functions'][0]['status'] == 'modeled'
    assert result['source_executed'] is False
    file.write_text(program('    if not result["same"]:\n        raise ValueError()\n'), encoding='utf-8')
    with pytest.raises(ValueError, match='source_changed'):
        invoke_knowledge('project_description', {'project_root': str(tmp_path),
            'action': 'return_flags', 'requests': [request]})
