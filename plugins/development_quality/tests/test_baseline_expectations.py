from copy import deepcopy

import pytest

from plugins.development_quality.src.baseline_expectations import validate, compare


def expectation(node='tests/test_contract.py::test_value', kind='preservation'):
    return {'node': node, 'kind': kind, 'reason': 'keep integer coercion',
            'goal_quote': 'Preserve conversion',
            'source_evidence': [{'path': 'engine.py', 'quote': 'return int(value)'}]}


def specification(rows):
    return {'tests': [{'path': 'tests/test_contract.py'}], 'baseline_expectations': rows}


def test_exact_goal_and_source_binding_never_grants_semantic_approval():
    spec = specification([expectation()])
    sources = [{'path': 'engine.py', 'content': 'def convert(value):\n    return int(value)\n'}]
    assert validate(spec, 'Preserve conversion; add aliases', sources, required=True) == []
    assert validate(spec, 'Redesign conversion', sources, required=True)
    assert validate(spec, 'Preserve conversion', [], required=True)
    assert validate({}, '', [], required=True)
    assert validate({}, '', []) == []


def test_missing_overlapping_and_unused_predictions_are_rejected():
    outcomes = {'tests.test_contract::test_value[a]': 'passed', 'tests.test_contract::test_value[b]': 'failed'}
    rows = [expectation()]
    assert compare(specification(rows), outcomes)['status'] == 'rejected'
    rows += [expectation('tests/test_contract.py::test_value[b]', 'feature_gap')]
    assert any('exactly one' in x for x in compare(specification(rows), outcomes)['issues'])
    rows[0]['node'] += '[a]'
    assert compare(specification(rows), outcomes)['status'] == 'matched'
    assert compare(specification(rows[:1]), outcomes)['status'] == 'rejected'
    assert compare(specification(rows), {})['status'] == 'rejected'


def test_classes_and_duplicate_names_are_not_confused():
    rows = [expectation('tests/test_contract.py::TestPositive::test_value'),
            expectation('tests/test_contract.py::TestNegative::test_value', 'feature_gap')]
    result = compare(specification(rows), {'tests.test_contract.TestPositive::test_value': 'passed',
        'tests.test_contract.TestNegative::test_value': 'failed'})
    assert result['status'] == 'matched'


@pytest.mark.parametrize('outcome', ['failed', 'error', 'skipped'])
def test_preservation_must_actually_pass(outcome):
    result = compare(specification([expectation()]), {'tests.test_contract::test_value': outcome})
    assert result['status'] == 'rejected'


def test_feature_gap_cannot_pass_and_preservation_cannot_be_relabeled():
    row = expectation(kind='feature_gap')
    spec = specification([row])
    assert compare(spec, {'tests.test_contract::test_value': 'passed'})['status'] == 'rejected'
    spec['case_plan'] = [{'kind': 'preservation', 'node': row['node']}]
    assert compare(spec, {'tests.test_contract::test_value': 'failed'})['status'] == 'rejected'


def test_malformed_predictions_do_not_crash_or_modify_contract():
    for value in [None, {}, [None], [{'node': 3}], [expectation(), expectation()]]:
        spec = specification(value)
        before = deepcopy(spec)
        assert validate(spec, 'Preserve conversion', [], required=True)
        assert spec == before


def test_versioned_plugin_actions_follow_schemas():
    import json
    from pathlib import Path
    import jsonschema
    from plugins.development_quality.src.main import run
    root = Path(__file__).resolve().parents[1]
    for request in [
        {'action': 'validate_baseline_expectations', 'artifact': {}, 'goal': '', 'sources': [], 'required': True},
        {'action': 'compare_baseline_expectations', 'artifact': specification([expectation()]), 'outcomes': {}}]:
        jsonschema.validate(request, json.loads((root / 'schemas/input.json').read_text()))
        response = run(request)
        jsonschema.validate(response, json.loads((root / 'schemas/output.json').read_text()))
        assert response['grants_approval'] is False


def test_classification_field_is_separate_and_conflicting_legacy_values_fail():
    row = expectation()
    row['classification'] = row.pop('kind')
    spec = specification([row])
    sources = [{'path': 'engine.py', 'content': 'return int(value)'}]
    assert validate(spec, 'Preserve conversion', sources, required=True) == []
    assert compare(spec, {'tests.test_contract::test_value': 'passed'})['status'] == 'matched'
    row['kind'] = 'feature_gap'
    assert validate(spec, 'Preserve conversion', sources, required=True)
    assert compare(spec, {'tests.test_contract::test_value': 'failed'})['status'] == 'rejected'
