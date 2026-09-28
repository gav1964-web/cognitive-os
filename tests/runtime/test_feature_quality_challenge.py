import json
from pathlib import Path
import sys
import pytest

from runtime.feature_quality import run_quality_development
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_feature_development import project, fake_chat
from tests.runtime.test_feature_quality import augment


def test_invalid_fault_is_repaired_automatically_and_candidate_is_unchanged(project, tmp_path):
    delegate = fake_chat(project)
    calls = []

    def chat(messages, *, config):
        role = config.provider_label.partition(':')[2]
        if role == 'design_auditor':
            return {'decision': 'approve'}
        if role != 'challenger':
            return augment(role, delegate(messages, config=config))
        payload = json.loads(messages[1]['content'])
        calls.append(payload)
        if len(calls) == 1:
            return {'challenges': []}
        source = payload['candidate_sources'][0]
        return {'challenges': [{'id': 'sign', 'reason': 'negative labels lost',
            'edits': [{'path': 'engine.py', 'source_sha256': source['sha256'],
                       'replacements': [{'old': 'return f"({-value})" if value < 0 else str(value)',
                                         'new': 'return str(value)'}]}],
            'oracle_tests': [{'path': 'tests/test_witness.py', 'content':
                'from engine import display\ndef test_witness():\n    assert display(-2) == "(2)"\n'}]}]}

    cfg = LocalInferenceConfig('http://unused', 'fake')
    result = run_quality_development(project=project, work=tmp_path / 'quality',
        goal='negative labels', python=Path(sys.executable), chat=chat,
        configs={r: cfg for r in ('analyzer', 'architect', 'spec_writer')})
    assert result['status'] == 'verified', result
    assert len(calls) == 2 and calls[-1]['native_feedback']
    assert calls[0]['boundary_probes']
    assert all(p['source_sha256'] == calls[0]['candidate_sources'][0]['sha256']
               for p in calls[0]['boundary_probes'])
    assert result['source_unchanged'] and result['autonomy']['automatic_routes'] == 1


def test_exhausted_invalid_fault_never_becomes_success(project, tmp_path):
    delegate = fake_chat(project)

    def chat(messages, *, config):
        role = config.provider_label.partition(':')[2]
        if role == 'design_auditor':
            return {'decision': 'approve'}
        if role == 'challenger':
            return {'challenges': []}
        return augment(role, delegate(messages, config=config))

    cfg = LocalInferenceConfig('http://unused', 'fake')
    result = run_quality_development(project=project, work=tmp_path / 'quality',
        goal='negative labels', python=Path(sys.executable), chat=chat,
        configs={r: cfg for r in ('analyzer', 'architect', 'spec_writer')})
    assert result['status'] == 'blocked' and result['reason'] == 'quality_challenge_inconclusive'
    assert result['autonomy']['automatic_routes'] == 1


@pytest.mark.parametrize('admission_failures', [0, 3])
def test_surviving_fault_returns_to_specwriter_and_retains_frozen_tests(project, tmp_path, admission_failures):
    delegate = fake_chat(project)
    specs = []
    roles = []

    def chat(messages, *, config):
        role = config.provider_label.partition(':')[2]
        roles.append(role)
        payload = json.loads(messages[1]['content'])
        if role == 'design_auditor':
            return {'decision': 'approve'}
        if role == 'challenger':
            source = payload['candidate_sources'][0]
            return {'challenges': [{'id': 'another-negative', 'reason': 'all negative numbers need labels',
                'edits': [{'path': 'engine.py', 'source_sha256': source['sha256'],
                    'replacements': [{'old': 'if value < 0 else', 'new': 'if value == -2 else'}]}],
                'oracle_tests': [{'path': 'tests/test_witness.py', 'content':
                    'from engine import display\ndef test_witness():\n    assert display(-3) == "(3)"\n'}]}]}
        value = augment(role, delegate(messages, config=config))
        if role == 'spec_writer':
            specs.append(value)
            if len(specs) > 1:
                assert payload['quality_feedback']['survivors']
                value['tests'].append({'path': 'tests/test_witness.py', 'content':
                    'from engine import display\ndef test_witness():\n    assert display(-3) == "(3)"\n'})
                if len(specs) <= 1 + admission_failures:
                    value['case_plan'][0]['node'] = 'missing_test'
        return value

    cfg = LocalInferenceConfig('http://unused', 'fake')
    result = run_quality_development(project=project, work=tmp_path / 'quality',
        goal='negative labels', python=Path(sys.executable), chat=chat,
        configs={r: cfg for r in ('analyzer', 'architect', 'spec_writer')})
    assert result['status'] == 'verified', result
    assert len(specs) == 2 + admission_failures
    assert len(result['cycles']) == (3 if admission_failures else 2)
    assert specs[0]['tests'][0] == specs[1]['tests'][0]
    assert result['cycles'][0]['challenges']['status'] == 'needs_specification'
    assert result['cycles'][-1]['challenges']['status'] == 'passed'
    assert result['autonomy']['human_interventions'] == 0
    assert roles.count('challenger') == roles.count('programmer') == 1
