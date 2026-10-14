"""Audit partition and native controls keep masked expectations unaccepted."""
import json
import sys
from pathlib import Path

import pytest

from runtime.feature_acceptance import prepare
from runtime.feature_workspace import inventory
from runtime.feature_quality_chat import QualityChat
from runtime.local_inference import LocalInferenceConfig


def specification():
    body = ('from engine import copy_values\n'
        'def test_new():\n    source = [1]\n    result = copy_values(source)\n'
        '    assert result is not source\n    assert result == []\n'
        'def test_control():\n    assert copy_values([1]) == [1]\n'
        'def test_empty():\n    assert copy_values([]) == []\n')
    rows = [('test_new', 'feature', 'feature_gap'),
            ('test_control', 'preservation', 'preservation'),
            ('test_empty', 'boundary', 'preservation')]
    return {'status': 'ready', 'tests': [{'path': 'tests/test_copy.py', 'content': body}],
        'regression_tests': [], 'regression_policy': 'new_preservation_only',
        'acceptance': ['fresh copy with same contents'], 'limitations': ['unit boundary'],
        'case_plan': [{'node': 'tests/test_copy.py::' + n, 'kind': k, 'behavior': n} for n,k,_ in rows],
        'baseline_expectations': [{'node': 'tests/test_copy.py::' + n, 'classification': k,
            'reason': n, 'goal_quote': 'fresh copy',
            'source_evidence': [{'path': 'engine.py', 'quote': 'return source'}]} for n,_,k in rows]}


def test_separating_old_assertion_exposes_its_error_on_baseline(tmp_path):
    project = tmp_path / 'source'; project.mkdir()
    (project / 'engine.py').write_text('def copy_values(source):\n    return source\n')
    spec = specification(); expected = inventory(project)
    # Existing per-test prediction alone cannot detect the hidden wrong assertion.
    _, result = prepare(project, tmp_path / 'mixed', expected, spec, Path(sys.executable))
    assert result['baseline_expectations']['status'] == 'matched'
    spec['tests'][0]['content'] += '\ndef test_old_independent():\n    assert copy_values([1]) == []\n'
    spec['baseline_expectations'].append({'node': 'tests/test_copy.py::test_old_independent',
                                        'classification': 'preservation'})
    with pytest.raises(ValueError, match='feature_baseline_expectations_not_qualified'):
        prepare(project, tmp_path / 'split', expected, spec, Path(sys.executable))
    assert inventory(project) == expected


def test_audit_approval_without_partition_cannot_promote_strict_draft(tmp_path):
    seen = []
    def chat(messages, *, config):
        payload = json.loads(messages[1]['content'])
        if config.provider_label == 'quality:spec_auditor':
            cat = payload['baseline_assertion_inventory']
            assert len(cat['feature_gap_assertions'][0]['assertions']) == 2
            seen.append(cat['digest'])
            return {'decision': 'approve'}  # Incomplete audit must not approve.
        return specification()
    q = QualityChat(chat, tmp_path / 'quality', require_baseline_expectations=True)
    with pytest.raises(ValueError, match='quality_audit_response_invalid'):
        q([{'role': 'system', 'content': 'spec'}, {'role': 'user', 'content': json.dumps({
            'goal': 'fresh copy', 'sources': [{'path': 'engine.py', 'content': 'return source'}],
            'artifacts': {}})}], config=LocalInferenceConfig('http://unused', 'fake', provider_label='feature:spec_writer'))
    assert len(seen) == 3
    assert not q.pending


def test_malformed_auditor_mapping_is_repaired_by_auditor_not_writer(tmp_path):
    from plugins.development_quality.src.assertion_obligations import inventory
    spec = specification()
    cat = inventory(spec)
    row = cat['feature_gap_assertions'][0]
    calls = []
    def chat(messages, *, config):
        calls.append(config.provider_label)
        payload = json.loads(messages[1]['content'])
        if len(calls) == 1:
            return {'decision': 'approve'}
        assert payload['audit_response_feedback']['issues']
        assert payload['specification'] == spec
        return {'decision': 'reject', 'issues': ['Independent control has different expected contents']}
    q = QualityChat(chat, tmp_path / 'audit')
    result = q.audit_specification({'specification': spec, 'baseline_assertion_inventory': cat,
        'accepted_test_paths': []}, LocalInferenceConfig('http://unused', 'fake', provider_label='quality:spec_auditor'))
    assert result['decision'] == 'reject' and calls == ['quality:spec_auditor'] * 2
