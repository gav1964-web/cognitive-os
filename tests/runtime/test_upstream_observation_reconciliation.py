"""Source observations cannot duplicate or erase native failure identities."""
from copy import deepcopy

from runtime.project_development_diagnosis import build_development_diagnosis


def diagnose(rows, findings=()):
    return build_development_diagnosis(project='example', project_report={},
        recognition={'status': 'recognized'}, chain_case={'contract_failure_evidence': rows},
        source_incompleteness={'actionable_findings': list(findings)})


def native(signature='first'):
    return {'target': 'core.py:read', 'authority': 'failing_contract_test',
        'failure_signature': signature, 'failing_nodeids': ['tests/test_core.py::test_read'],
        'detail': 'AssertionError on a native observation'}


def test_stub_observation_preserves_single_native_packet_input():
    source = {'target': 'core.py:read', 'authority': 'failing_contract_test',
        'detail': 'pass stub corroborated by the failure', 'signal': 'pass'}
    result = diagnose([native()], [source])
    issue = result['issues'][0]
    assert len(issue['failure_evidence']) == 1
    assert issue['failure_evidence'][0]['failure_signature'] == 'first'
    assert result['observations']['corroborating_source_observations'] == [source]


def test_distinct_native_failures_on_same_target_are_not_silently_dropped():
    result = diagnose([native(), native('second')])
    assert [r['failure_signature'] for r in result['issues'][0]['failure_evidence']] == ['first', 'second']


def test_exact_duplicate_is_deduplicated_without_mutating_input():
    row = native()
    original = deepcopy(row)
    result = diagnose([row, deepcopy(row)])
    assert len(result['issues'][0]['failure_evidence']) == 1
    assert row == original


def test_other_target_source_observation_is_retained():
    source = {'target': 'other.py:read', 'authority': 'failing_contract_test', 'detail': 'corroborated stub'}
    result = diagnose([native()], [source])
    assert len(result['issues'][0]['failure_evidence']) == 2
    assert result['observations']['corroborating_source_observations'] == []
