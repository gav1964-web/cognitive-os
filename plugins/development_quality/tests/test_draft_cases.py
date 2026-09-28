"""Case continuity is structural evidence, never semantic approval."""
from plugins.development_quality.src.main import run
import json
from pathlib import Path
import jsonschema


def artifact(body, path='tests/test_feature.py', **extra):
    return {'tests': [{'path': path, 'content': body}], **extra}


def compare(old, new):
    return run({'action': 'compare_draft', 'previous': old, 'current': new})


def test_same_file_cannot_silently_drop_prior_case():
    old = artifact('def test_keep():\n    assert result == 1\ndef test_boundary():\n    assert result == 0\n')
    new = artifact('def test_keep():\n    assert result == 1\n')
    result = compare(old, new)
    assert result['unexplained'] == ['tests/test_feature.py::test_boundary']
    root = Path(__file__).resolve().parents[1]
    jsonschema.validate({'action': 'compare_draft', 'previous': old, 'current': new},
                        json.loads((root / 'schemas/input.json').read_text()))
    jsonschema.validate(result, json.loads((root / 'schemas/output.json').read_text()))


def test_moves_and_body_repairs_do_not_freeze_unaccepted_tests():
    old = artifact('def test_boundary():\n    assert broken_fixture == 0\n')
    new = artifact('def test_boundary():\n    assert actual() == 0\n', path='tests/test_moved.py')
    assert compare(old, new)['missing'] == []


def test_declared_consolidation_needs_existing_targets_and_reason():
    old = artifact('def test_old():\n    assert actual() == 0\n')
    new = artifact('def test_new():\n    assert actual() == 0\n')
    mapping = {'previous': 'tests/test_feature.py::test_old',
               'replacements': ['tests/test_feature.py::test_new'], 'reason': 'same assertion'}
    assert compare(old, new)['unexplained']
    new['case_replacements'] = [mapping]
    assert compare(old, new)['missing'] and not compare(old, new)['unexplained']
    mapping['replacements'] = ['tests/test_feature.py::nonexistent']
    assert compare(old, new)['unexplained']
    mapping['replacements'] = []
    assert compare(old, new)['unexplained']


def test_methods_are_qualified_and_nested_helpers_are_not_cases():
    old = artifact('class TestA:\n    def test_edge(self):\n        assert actual()\nclass TestB:\n    def test_edge(self):\n        assert other()\ndef helper():\n    def test_fake():\n        pass\n')
    new = artifact('class TestA:\n    def test_edge(self):\n        assert actual()\n')
    assert compare(old, new)['unexplained'] == ['tests/test_feature.py::TestB::test_edge']
