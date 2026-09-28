"""Semantic review rejection goes back to the author, without thawing tests."""
import json
import sys
from pathlib import Path

import pytest

from runtime.feature_development import run_feature_development
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_feature_development import project, fake_chat, run


@pytest.mark.parametrize('tamper', [None, 'proposal', 'review'])
def test_rejected_review_rechecks_candidate_before_programmer_feedback(project, tmp_path, tamper):
    first = run(project, tmp_path, chat=fake_chat(project, review='reject'))
    assert first['status'] == 'blocked' and first['attempts'][-1]['passed']
    if tamper:
        file = tmp_path / 'run' / ('proposal-1.json' if tamper == 'proposal' else 'reviewer.json')
        data = json.loads(file.read_text())
        if tamper == 'proposal':
            data['edits'][0]['replacements'][0]['new'] += ' # changed'
        else:
            data['reason'] = 'tampered'
        file.write_text(json.dumps(data))
    delegate = fake_chat(project)
    calls = []

    def chat(messages, *, config):
        calls.append(config.provider_label)
        if config.provider_label == 'feature:programmer':
            payload = json.loads(messages[1]['content'])
            assert payload['feedback']['review'] == first['artifacts']['reviewer']
            assert payload['feedback']['verification']['returncode'] == 0
            assert payload['artifacts']['spec_writer'] == first['artifacts']['spec_writer']
        return delegate(messages, config=config)

    result = run_feature_development(project=project, work=tmp_path / 'resumed',
        goal=first['goal'], python=Path(sys.executable), chat=chat,
        configs={'spec_writer': LocalInferenceConfig('http://unused', 'fake')},
        resume_roles=tmp_path / 'run')
    if tamper:
        assert result['status'] == 'blocked' and calls == []
    else:
        assert result['status'] == 'verified'
        assert calls == ['feature:programmer', 'feature:reviewer']
        assert result['frozen_test_hashes'] == first['frozen_test_hashes']
    assert not result['source_apply']


def test_fresh_spec_can_add_tests_after_rejected_review_without_changing_patch(project, tmp_path):
    first = run(project, tmp_path, chat=fake_chat(project, review='reject'))
    delegate = fake_chat(project)

    def chat(messages, *, config):
        value = delegate(messages, config=config)
        if config.provider_label == 'feature:spec_writer':
            value['tests'].append({'path': 'tests/test_more_negative.py', 'content':
                'from engine import display\ndef test_more_negative():\n    assert display(-3) == "(3)"\n'})
        return value

    result = run_feature_development(project=project, work=tmp_path / 'extended',
        goal=first['goal'], python=Path(sys.executable), chat=chat,
        configs={'spec_writer': LocalInferenceConfig('http://unused', 'fake')},
        resume_roles=tmp_path / 'run', fresh_spec=True)
    assert result['status'] == 'verified', result.get('reason')
    assert result['frozen_test_hashes']['tests/test_labels.py'] == first['frozen_test_hashes']['tests/test_labels.py']
    assert result['attempts'][0]['candidate_hashes']['engine.py'] == first['attempts'][0]['candidate_hashes']['engine.py']
