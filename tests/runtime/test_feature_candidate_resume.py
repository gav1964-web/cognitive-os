"""A review transport/format failure must not force code regeneration."""
import json
import sys
from pathlib import Path

import pytest

from runtime.feature_development import run_feature_development
from runtime.local_inference import LocalInferenceConfig, LocalInferenceError
from tests.runtime.test_feature_development import project, fake_chat, run


@pytest.mark.parametrize('tamper', [False, True])
def test_resume_rechecks_exact_candidate_and_only_calls_reviewer(project, tmp_path, tamper):
    delegate = fake_chat(project)
    def fail_review(messages, *, config):
        if config.provider_label == 'feature:reviewer':
            raise LocalInferenceError('structured response is not a complete JSON object')
        return delegate(messages, config=config)
    result = run(project, tmp_path, chat=fail_review)
    assert result['status'] == 'blocked' and result['attempts'][-1]['passed']
    if tamper:
        proposal = tmp_path / 'run/proposal-1.json'
        value = json.loads(proposal.read_text())
        value['edits'][0]['replacements'][0]['new'] += '  # changed bytes'
        proposal.write_text(json.dumps(value))
    calls = []
    def review(messages, *, config):
        calls.append(config.provider_label)
        assert config.provider_label == 'feature:reviewer'
        payload = json.loads(messages[1]['content'])
        assert 'JSON' in payload['previous_review_error']
        assert payload['verification']['passed']
        return delegate(messages, config=config)
    resumed = run_feature_development(project=project, work=tmp_path / 'resumed',
        goal=result['goal'], python=Path(sys.executable), chat=review,
        configs={'spec_writer': LocalInferenceConfig('http://unused', 'fake')},
        resume_roles=tmp_path / 'run', resume_candidate=True)
    if tamper:
        assert resumed['reason'] == 'feature_resumed_candidate_changed_or_failed'
        assert calls == []
    else:
        assert resumed['status'] == 'verified', resumed
        assert calls == ['feature:reviewer']
        assert resumed['frozen_test_hashes'] == result['frozen_test_hashes']
    assert not resumed['source_apply']


def test_interrupted_review_retains_reads_and_full_acceptance(project, tmp_path):
    delegate = fake_chat(project)
    calls = []
    def interrupted(messages, *, config):
        if config.provider_label == 'feature:reviewer':
            calls.append(config.provider_label)
            if len(calls) == 1:
                return {'status': 'read', 'reads': [{'path': 'engine.py', 'start': 1, 'end': 2}]}
            raise LocalInferenceError('interrupted review')
        return delegate(messages, config=config)
    result = run(project, tmp_path, chat=interrupted)
    assert result['status'] == 'blocked' and result['attempts'][-1]['passed']
    calls.clear()
    def review(messages, *, config):
        calls.append(config.provider_label)
        payload = json.loads(messages[1]['content'])
        assert payload['sources'][0]['content'] == (project / 'engine.py').read_text()
        architect = result['artifacts']['architect']
        assert payload['artifacts']['architect'] == {k: architect[k] for k in
            ('scope', 'preserve', 'risks', 'acceptance')}
        assert payload['artifacts']['spec_writer']['tests'] == result['artifacts']['spec_writer']['tests']
        assert payload['verification']['tests'] == result['attempts'][-1]['tests']
        assert payload['proposal'] == json.loads((tmp_path / 'run/proposal-1.json').read_text())
        return delegate(messages, config=config)
    resumed = run_feature_development(project=project, work=tmp_path / 'resumed',
        goal=result['goal'], python=Path(sys.executable), chat=review,
        configs={'spec_writer': LocalInferenceConfig('http://unused', 'fake')},
        resume_roles=tmp_path / 'run', resume_candidate=True)
    assert resumed['status'] == 'verified', resumed
    assert calls == ['feature:reviewer']
    assert json.loads((tmp_path / 'resumed/reviewer-source-ranges.json').read_text()) == [
        {'path': 'engine.py', 'start': 1, 'end': 2}]


def test_programmer_retains_requested_test_source_after_interruption(project, tmp_path):
    delegate = fake_chat(project)
    calls = []
    def interrupted(messages, *, config):
        if config.provider_label == 'feature:programmer':
            calls.append(1)
            if len(calls) == 1:
                return {'status': 'read', 'reads': [{'path': 'tests/test_existing.py', 'start': 1, 'end': 100}]}
            raise LocalInferenceError('interrupted')
        return delegate(messages, config=config)
    first = run(project, tmp_path, chat=interrupted)
    assert first['status'] == 'blocked'
    called = []
    def resumed_chat(messages, *, config):
        called.append(config.provider_label)
        if config.provider_label == 'feature:programmer':
            payload = json.loads(messages[1]['content'])
            assert any(s['path'] == 'tests/test_existing.py' for s in payload['sources'])
        return delegate(messages, config=config)
    result = run_feature_development(project=project, work=tmp_path / 'resumed',
        goal=first['goal'], python=Path(sys.executable), chat=resumed_chat,
        configs={'spec_writer': LocalInferenceConfig('http://unused', 'fake')}, resume_roles=tmp_path / 'run')
    assert result['status'] == 'verified', result
    assert called == ['feature:programmer', 'feature:reviewer']


def test_rejected_candidate_reproduces_feedback_before_model_correction(project, tmp_path):
    first = run(project, tmp_path, chat=fake_chat(project, bad=True))
    assert first['reason'] == 'feature_acceptance_failed'
    delegate = fake_chat(project)
    called = []
    def correct(messages, *, config):
        called.append(config.provider_label)
        if config.provider_label == 'feature:programmer':
            feedback = json.loads(messages[1]['content'])['feedback']
            assert feedback['verification']['failures']
            assert 'output_tail' not in feedback['verification']
            assert feedback['rejected_proposal']['edits']
        return delegate(messages, config=config)
    result = run_feature_development(project=project, work=tmp_path / 'resumed',
        goal=first['goal'], python=Path(sys.executable), chat=correct,
        configs={'spec_writer': LocalInferenceConfig('http://unused', 'fake')}, resume_roles=tmp_path / 'run')
    assert result['status'] == 'verified', result
    assert [r['passed'] for r in result['attempts']] == [False, True]
    assert called == ['feature:programmer', 'feature:reviewer']
