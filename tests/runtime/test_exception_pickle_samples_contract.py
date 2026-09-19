"""Frozen pre-extraction descriptors and the source-only competency boundary."""
import ast
import json
from copy import deepcopy
from pathlib import Path

import pytest

from runtime.competency_knowledge import invoke_knowledge
from runtime import exception_pickle_sample_contract as client

ROOT = Path(__file__).resolve().parents[2]
FROZEN = json.loads((ROOT / 'tests/fixtures/exception_pickle_samples_legacy.json').read_text(encoding='utf-8'))


def test_all_frozen_name_rules_match_through_one_registered_batch():
    rows = FROZEN['base']
    assert client.sample_constructor_values([r['name'] for r in rows]) == [r['sample'] for r in rows]


@pytest.mark.parametrize('row', FROZEN['source'])
def test_source_rules_preserve_frozen_descriptors_without_executing_source(row, tmp_path):
    sentinel = tmp_path / 'must_not_exist'
    source = f'raise RuntimeError({str(sentinel)!r})\n' + row['source']
    assert client.sample_constructor_values([row['name']], source=source, class_name='Broken') == [row['sample']]
    assert not sentinel.exists()


@pytest.mark.parametrize('row', FROZEN['contracts'])
def test_explicit_contract_rules_preserve_descriptors_and_input(row):
    contracts = deepcopy(row['contracts'])
    assert client.sample_constructor_values(['mystery_parameter'], object_contracts=contracts) == [row['sample']]
    assert contracts == row['contracts']


@pytest.mark.parametrize('row', FROZEN['calls'])
def test_positional_and_keyword_call_shape_matches_legacy(row, tmp_path):
    source_file = tmp_path / 'source.py'
    source_file.write_text(row['source'], encoding='utf-8')
    assert client.constructor_sample_call(source_file=source_file, class_name='Broken',
        required=row['required'], samples=row['samples']) == (row['args'], row['kwargs'])


def test_missing_invalid_and_non_utf8_source_keep_legacy_fallbacks(tmp_path):
    source_file = tmp_path / 'source.py'
    assert client.sample_constructor_value_for_source_file('count', source_file=source_file, class_name='Broken') == 7
    assert client.constructor_sample_call(source_file=source_file, class_name='Broken', required=['value'], samples=[7]) == ([7], {})
    source_file.write_text('invalid syntax !', encoding='utf-8')
    assert client.sample_constructor_value_for_source_file('count', source_file=source_file, class_name='Broken') == 7
    source_file.write_bytes(b'# \xff\nclass Broken(Exception):\n    def __init__(self, mystery_parameter):\n        self.code = mystery_parameter.code\n')
    assert client.sample_constructor_value_for_source_file('mystery_parameter', source_file=source_file,
        class_name='Broken') == {'__sample__': 'named_object', 'code': 7, 'name': 'sample-mystery_parameter'}


@pytest.mark.parametrize('payload', [
    {'operation': 'sample_values'},
    {'operation': 'sample_values', 'names': ['x'], 'source': ''},
    {'operation': 'sample_values', 'names': [7]},
    {'operation': 'sample_values', 'names': ['x'], 'source_file': '/some/file'},
    {'operation': 'constructor_call', 'source': '', 'class_name': 'Broken'},
])
def test_operation_inputs_are_checked_by_registry(payload):
    with pytest.raises(Exception, match='exception_pickle.input'):
        invoke_knowledge('exception_pickle', payload)


def test_bad_response_or_admission_failure_does_not_become_unknown_sample(monkeypatch):
    monkeypatch.setattr(client, 'invoke_knowledge', lambda *a, **k: {'status': 'ok', 'samples': []})
    with pytest.raises(ValueError, match='invalid_exception_pickle_sample_response'):
        client.sample_constructor_value('count')

    def denied(*args, **kwargs):
        raise ValueError('knowledge_provider_identity_mismatch')

    monkeypatch.setattr(client, 'invoke_knowledge', denied)
    with pytest.raises(ValueError, match='knowledge_provider_identity_mismatch'):
        client.sample_constructor_value('count')


def test_sample_owner_does_not_import_runtime_or_read_project_files():
    for name in ['constructor_samples.py', 'source_samples.py']:
        tree = ast.parse((ROOT / 'plugins/exception_pickle/src' / name).read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or '').startswith('runtime')
            if isinstance(node, ast.Call):
                assert not (isinstance(node.func, ast.Attribute) and node.func.attr in {'read_text', 'read_bytes'})
