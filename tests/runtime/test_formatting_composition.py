"""Preservation checks reject rollback and identity-only formatter repairs."""
import hashlib
from pathlib import Path

import pytest

from plugins.python_transform_contracts.src.main import run
from runtime.upstream_owned_acceptance import prepare_owned_acceptance

ROOT = Path(__file__).resolve().parents[2]


def payload():
    return {'operation': 'acceptance_tests', 'contract': 'python_formatting_independent_fragments.v1',
        'module': 'sample', 'function': 'format_source', 'keyword_literals': {},
        'seed': 'stable = (1), 2\n', 'preservation_seed': 'other = [\n  1\n]\n',
        'preservation_expected': 'other = [\n  1,\n]\n'}


@pytest.mark.parametrize('mode,passed', [('correct', 4), ('rollback', 2), ('identity', 1)])
def test_property_detects_loss_of_positive_behavior(monkeypatch, mode, passed):
    import sys
    import types
    data = payload()
    module = types.ModuleType('sample')

    def formatter(source):
        if mode == 'identity' or (mode == 'rollback' and data['seed'] in source):
            return source
        return source.replace(data['preservation_seed'], data['preservation_expected'])

    module.format_source = formatter
    monkeypatch.setitem(sys.modules, 'sample', module)
    result = run(data)
    assert result['source_binding_fields'] == ['seed', 'preservation_seed', 'preservation_expected']
    assert result['tests'][1]['required_baseline_outcome'] == 'passes'
    outcomes = []
    for row in result['tests']:
        namespace = {}
        exec(row['source'], namespace)
        try:
            namespace[row['name']]()
        except AssertionError:
            outcomes.append(False)
        else:
            outcomes.append(True)
    assert sum(outcomes) == passed


def test_ast_changing_expected_value_is_not_applicable():
    data = payload()
    data['preservation_expected'] = 'other = (1,)\n'
    assert run(data)['status'] == 'not_applicable'


def test_positive_control_cannot_be_a_noop():
    data = payload()
    data['preservation_expected'] = data['preservation_seed']
    with pytest.raises(ValueError, match='positive_formatting_change_required'):
        run(data)


def test_unbound_expected_output_rejected_before_native_execution(tmp_path):
    project = tmp_path / 'source'
    project.mkdir()
    data = payload()
    evidence = project / 'test_source.py'
    evidence.write_text('SEED = ' + repr(data['seed']) + '\nCONTROL = ' + repr(data['preservation_seed']))
    plan = {'capability': 'python_transform_contracts', 'requirement_id': 'R', 'payload': data,
            'seed_source': {'path': 'test_source.py', 'sha256': hashlib.sha256(evidence.read_bytes()).hexdigest()}}
    task = {'schema_version': 'upstream_task_contract.v1', 'origin': 'assistant_supplied', 'change_kind': 'defect',
            'requirements': [{'id': 'R', 'statement': 'Preserve formatting.', 'targets': ['sample.py:format_source'],
                              'acceptance_examples': []}]}
    with pytest.raises(ValueError, match='acceptance_example_not_present_in_source'):
        prepare_owned_acceptance(project, task, plan, tmp_path / 'acceptance', authorized=True, root=ROOT)
    assert not (tmp_path / 'acceptance').exists()


def test_source_bound_but_wrong_positive_example_is_not_verified(tmp_path):
    project = tmp_path / 'source'
    project.mkdir()
    data = payload()
    # All strings exist in the bound file, but the transformer never produces
    # the claimed positive output. Merely finding its literal is insufficient.
    (project / 'sample.py').write_text('def format_source(source):\n    return source\n')
    evidence = project / 'test_source.py'
    evidence.write_text('EXAMPLES = ' + repr([data[k] for k in ('seed', 'preservation_seed', 'preservation_expected')]))
    plan = {'capability': 'python_transform_contracts', 'requirement_id': 'R', 'payload': data,
            'seed_source': {'path': 'test_source.py', 'sha256': hashlib.sha256(evidence.read_bytes()).hexdigest()}}
    task = {'schema_version': 'upstream_task_contract.v1', 'origin': 'assistant_supplied', 'change_kind': 'defect',
            'requirements': [{'id': 'R', 'statement': 'Preserve formatting.', 'targets': ['sample.py:format_source'],
                              'acceptance_examples': []}]}
    receipt = prepare_owned_acceptance(project, task, plan, tmp_path / 'acceptance', authorized=True, root=ROOT)
    assert receipt['status'] == 'not_verified'
