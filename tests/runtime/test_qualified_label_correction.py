"""Legacy descriptive labels may be corrected by COS without changing evidence."""
from copy import deepcopy
import pytest

from runtime.feature_accepted_metadata import capture, restore


@pytest.mark.parametrize('old_kind', ['feature_gap', 'feature_control'])
@pytest.mark.parametrize('new_kind', ['feature', 'boundary'])
def test_model_label_correction_preserves_forecasts_test_bytes_and_behavior(old_kind, new_kind):
    node = 'tests/test_old.py::test_old'
    original = {'tests': [{'path': 'tests/test_old.py', 'content': 'def test_old():\n assert f() == 1\n'}],
        'baseline_expectations': [{'node': node, 'classification': old_kind, 'reason': 'goal'}],
        'case_plan': [{'node': node, 'kind': old_kind, 'behavior': 'goal boundary'}]}
    accepted = capture(original, goal='goal', design={}, source_hashes={})
    draft = deepcopy(original); draft['case_plan'][0]['kind'] = new_kind
    assert restore(draft, accepted, accepted['binding'])[0] == original  # Historical transcript default.
    result, changes = restore(draft, accepted, accepted['binding'], allow_label_correction=True)
    assert result == draft and changes[0]['model_correction'] == draft['case_plan'][0]
    assert result['tests'] == original['tests']
    assert result['baseline_expectations'] == original['baseline_expectations']
    assert accepted['case_plan'] == original['case_plan'] and not changes[0]['grants_approval']


@pytest.mark.parametrize('change', ['behavior', 'valid_old_kind', 'preservation', 'forecast', 'bytes', 'binding'])
def test_label_exception_never_waives_other_evidence(change):
    node = 'tests/test_old.py::test_old'
    original = {'tests': [{'path': 'tests/test_old.py', 'content': 'def test_old():\n assert f() == 1\n'}],
        'baseline_expectations': [{'node': node, 'classification': 'feature_control'}],
        'case_plan': [{'node': node, 'kind': 'feature_control', 'behavior': 'same'}]}
    if change == 'valid_old_kind': original['case_plan'][0]['kind'] = 'feature'
    if change == 'forecast': original['baseline_expectations'][0]['classification'] = 'preservation'
    accepted = capture(original, goal='goal', design={}, source_hashes={})
    draft = deepcopy(original); draft['case_plan'][0]['kind'] = 'boundary'
    binding = accepted['binding']
    if change == 'behavior': draft['case_plan'][0]['behavior'] = 'different'
    if change == 'preservation': draft['case_plan'][0]['kind'] = 'preservation'
    if change == 'bytes': draft['tests'][0]['content'] += '# changed'
    if change == 'binding': binding += 'changed'
    result, changes = restore(draft, accepted, binding, allow_label_correction=True)
    assert not any('model_correction' in c for c in changes)
    if change not in ('bytes', 'binding'): assert result['case_plan'] == original['case_plan']
