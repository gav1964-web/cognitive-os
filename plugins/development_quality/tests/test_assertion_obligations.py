from copy import deepcopy
import json
from pathlib import Path

import jsonschema
import pytest

from plugins.development_quality.src.assertion_obligations import inventory, validate_review
from plugins.development_quality.src.main import run


def specimen():
    return {'tests': [{'path': 'tests/test_values.py', 'content':
        'def test_new():\n    value = compute()\n    assert value is not source\n    assert value == []\n'
        'def test_old():\n    assert compute() == [first]\n'}],
        'baseline_expectations': [
            {'node': 'tests/test_values.py::test_new', 'classification': 'feature_gap'},
            {'node': 'tests/test_values.py::test_old', 'classification': 'preservation'}]}


def approval(spec):
    items = inventory(spec)
    row = items['feature_gap_assertions'][0]
    return {'decision': 'approve', 'baseline_assertion_review': {'digest': items['digest'],
        'tests': [{'node': row['node'], 'changed': [row['assertions'][0]['id']],
                   'preserved': [{'id': row['assertions'][1]['id'],
                                  'control': spec['baseline_expectations'][1]['node']}]}]}}


def test_inventory_exposes_wrong_assert_after_a_feature_failure_without_rewriting():
    spec = specimen(); before = deepcopy(spec)
    row = inventory(spec)['feature_gap_assertions'][0]
    assert [x['code'] for x in row['assertions']] == ['assert value is not source', 'assert value == []']
    assert spec == before
    assert validate_review(spec, {'decision': 'approve'})
    # Only the semantic auditor can establish if the referenced control is equivalent.
    assert validate_review(spec, approval(spec)) == []


@pytest.mark.parametrize('defect', ['missing', 'duplicate', 'stale', 'feature_control', 'same_node', 'wrong_id'])
def test_approval_cannot_omit_or_misbind_preservation(defect):
    spec = specimen(); audit = approval(spec)
    row = audit['baseline_assertion_review']['tests'][0]
    if defect == 'missing': row['preserved'] = []
    elif defect == 'duplicate': row['changed'].append(row['preserved'][0]['id'])
    elif defect == 'stale': spec['tests'][0]['content'] += '\n# modified\n'
    elif defect == 'feature_control': spec['baseline_expectations'][1]['classification'] = 'feature_control'
    elif defect == 'same_node': row['preserved'][0]['control'] = row['node']
    else: row['preserved'][0]['id'] = '999:4'
    assert validate_review(spec, audit)


def test_parameter_cases_classes_frozen_and_unsupported_remain_explicit():
    spec = specimen()
    spec['tests'][0]['content'] = 'class TestValues:\n    def test_new(self, x):\n        assert x == 2\n'
    spec['baseline_expectations'][0]['node'] = 'tests/test_values.py::TestValues::test_new[negative]'
    assert inventory(spec)['feature_gap_assertions'][0]['assertions'][0]['code'] == 'assert x == 2'
    assert not inventory(spec, ['tests/test_values.py'])['feature_gap_assertions']
    spec['tests'][0]['content'] = 'def test_helper():\n    verify_condition()\n'
    spec['baseline_expectations'][0]['node'] = 'tests/test_values.py::test_helper'
    assert inventory(spec)['limitations'] and not inventory(spec)['feature_gap_assertions']
    assert validate_review(spec, {'decision': 'reject'}) == []


def test_new_actions_follow_versioned_schema_and_do_not_grant_approval():
    root = Path(__file__).resolve().parents[1]
    for request in [{'action': 'assertion_inventory', 'artifact': specimen()},
                    {'action': 'validate_assertion_review', 'artifact': specimen(), 'audit': approval(specimen())}]:
        jsonschema.validate(request, json.loads((root / 'schemas/input.json').read_text()))
        response = run(request)
        jsonschema.validate(response, json.loads((root / 'schemas/output.json').read_text()))
        assert response['grants_approval'] is False
