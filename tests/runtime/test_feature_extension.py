"""Qualified tests survive extension; added checks must prove their own gap."""
import json
import sys
from pathlib import Path

import pytest

from runtime.feature_development import run_feature_development
from runtime.feature_workspace import inventory
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_feature_case_compiler import project, annotate_fixture_api, run, spec


def extend(project, tmp_path, prior, body):
    def chat(messages, *, config):
        assert config.provider_label == 'feature:spec_writer'
        ctx = json.loads(messages[1]['content'])['extension_contract']
        assert ctx['frozen_test_hashes']
        return {'status': 'ready', 'tests': [{'path': 'tests/test_extended.py', 'content': body}],
                'regression_tests': [], 'acceptance': ['additional magnitude'],
                'limitations': ['no GUI'], 'environment': {}}
    return run_feature_development(project=project, work=tmp_path / 'extended',
        goal='Improve labels', python=Path(sys.executable), chat=chat,
        configs={'spec_writer': LocalInferenceConfig('http://unused', 'fake')},
        resume_roles=prior, extend_spec=True, stop_after='spec_writer', max_spec_attempts=1)


def test_native_extension_preserves_frozen_cases_and_resumes_without_regeneration(project, tmp_path):
    base = run(project, tmp_path, spec())
    before = inventory(project)
    body = ('from engine import display\n'
            'def test_gap():\n    assert display(-12) == "(12)"\n'
            'def test_preserved():\n    assert display(12) == "12"\n')
    result = extend(project, tmp_path, tmp_path / 'run', body)
    assert result['status'] == 'spec_qualified', result
    assert all(result['frozen_test_hashes'][n] == h for n, h in base['frozen_test_hashes'].items())
    assert result['baseline']['new_tests']['counts']['failed'] == 2
    def no_chat(*args, **kwargs):
        pytest.fail('Qualified extension must not be regenerated')
    repeated = run_feature_development(project=project, work=tmp_path / 'repeat',
        goal='Improve labels', python=Path(sys.executable), chat=no_chat,
        resume_roles=tmp_path / 'extended', stop_after='spec_writer')
    assert repeated['status'] == 'spec_qualified', repeated
    assert repeated['frozen_test_hashes'] == result['frozen_test_hashes']
    assert inventory(project) == before


def test_all_green_extension_cannot_borrow_inherited_feature_gap(project, tmp_path):
    run(project, tmp_path, spec())
    result = extend(project, tmp_path, tmp_path / 'run',
                    'from engine import display\ndef test_ok():\n    assert display(2) == "2"\n')
    assert result['reason'] == 'feature_extension_requires_own_gap_and_preservation'


def test_extension_rejects_frozen_path_replacement(project, tmp_path):
    from runtime.feature_extension import load_extension, merge_extension
    run(project, tmp_path, spec())
    base = load_extension(tmp_path / 'run')
    with pytest.raises(ValueError, match='cannot_replace'):
        merge_extension(base, {'tests': base['spec']['tests']})


def test_interrupted_extension_keeps_qualified_base_and_requested_source(project, tmp_path):
    run(project, tmp_path, spec())
    calls = []
    def interrupted(messages, *, config):
        calls.append(messages)
        if len(calls) == 1:
            return {'status': 'read', 'reads': [{'path': 'tests/test_existing.py', 'start': 1, 'end': 2}]}
        if len(calls) == 2:
            shown = json.loads(messages[1]['content'])['sources']
            assert any(r['path'] == 'tests/test_existing.py' for r in shown)
            return {'status': 'read', 'reads': [{'path': 'engine.py', 'start': 1, 'end': 2}]}
        raise RuntimeError('budget stopped')
    result = run_feature_development(project=project, work=tmp_path / 'interrupted',
        goal='Improve labels', python=Path(sys.executable), chat=interrupted,
        configs={'spec_writer': LocalInferenceConfig('http://unused', 'fake')},
        resume_roles=tmp_path / 'run', extend_spec=True, stop_after='spec_writer')
    assert result['reason'] == 'budget stopped'
    payload = json.loads(calls[2][1]['content'])
    assert any(r['path'] == 'engine.py' for r in payload['sources'])
    assert any(r['path'] == 'tests/test_existing.py' for r in payload['sources'])
    result = extend(project, tmp_path, tmp_path / 'interrupted',
        'from engine import display\n'
        'def test_gap():\n    assert display(-12) == "(12)"\n'
        'def test_preserve():\n    assert display(12) == "12"\n')
    assert result['status'] == 'spec_qualified', result
