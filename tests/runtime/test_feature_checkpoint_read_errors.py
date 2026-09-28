"""Resuming a missing-file request must preserve valid reads and source authority."""
import json
from pathlib import Path
import sys

import pytest

from runtime.feature_checkpoint import recover_pending_read, review_reads
from runtime.feature_workspace import inventory
from runtime.feature_development import run_feature_development
from runtime.local_inference import LocalInferenceConfig
from tests.runtime.test_feature_development import project, fake_chat, run


def checkpoint(tmp_path, requests):
    prior = tmp_path / 'prior/run'
    prior.mkdir(parents=True)
    calls = [{'status': 'returned', 'telemetry': [{'provider_label': 'feature:programmer'}],
              'raw_response': {'status': 'read', 'reads': requests}}]
    (prior.parent / 'transcript.json').write_text(json.dumps(calls))
    return prior


@pytest.mark.parametrize('loader', [review_reads, recover_pending_read])
def test_missing_draft_does_not_discard_existing_requested_source(project, tmp_path, loader):
    prior = checkpoint(tmp_path, [{'path': 'new_module.py'}, {'path': 'engine.py', 'start': 1, 'end': 2}])
    errors = []
    rows = loader(prior, project, inventory(project), 'programmer', errors=errors)
    assert len(rows) == 1 and rows[0]['path'] == 'engine.py'
    assert (rows[0]['start'], rows[0]['end']) == (1, 2)
    assert 'def display' in rows[0]['content']
    assert errors[0]['path'] == 'new_module.py'
    assert errors[0]['error'] == 'not_in_source_inventory'


@pytest.mark.parametrize('loader', [review_reads, recover_pending_read])
@pytest.mark.parametrize('unsafe', ['../escape.py', '.env', 'untracked.py'])
def test_restored_request_cannot_admit_forbidden_or_uninventoried_files(project, tmp_path, loader, unsafe):
    expected = inventory(project)
    (project / 'untracked.py').write_text('value = 1')
    prior = checkpoint(tmp_path, [{'path': unsafe}, {'path': 'engine.py'}])
    with pytest.raises(ValueError):
        loader(prior, project, expected, 'programmer', errors=[])


@pytest.mark.parametrize('loader', [review_reads, recover_pending_read])
def test_restored_missing_name_does_not_hide_changed_source(project, tmp_path, loader):
    expected = inventory(project)
    prior = checkpoint(tmp_path, [{'path': 'new_module.py'}, {'path': 'engine.py'}])
    (project / 'engine.py').write_text('changed = 1')
    with pytest.raises(ValueError, match='feature_source_changed'):
        loader(prior, project, expected, 'programmer', errors=[])


def test_resumed_programmer_receives_missing_path_feedback_and_keeps_qualified_spec(project, tmp_path):
    first = run(project, tmp_path, chat=fake_chat(project, review='reject'))
    assert first['status'] == 'blocked'
    prior = tmp_path / 'run'
    calls = [{'status': 'returned', 'telemetry': [{'provider_label': 'feature:programmer'}],
              'raw_response': {'status': 'read', 'reads': [{'path': 'new_module.py'}, {'path': 'engine.py'}]}}]
    (prior.parent / 'transcript.json').write_text(json.dumps(calls))
    delegate, invoked = fake_chat(project), []

    def chat(messages, *, config):
        invoked.append(config.provider_label)
        if config.provider_label == 'feature:programmer':
            payload = json.loads(messages[1]['content'])
            assert any(e['path'] == 'new_module.py' for e in payload['read_tool_result']['errors'])
            assert any(r['path'] == 'engine.py' and 'def display' in r['content'] for r in payload['sources'])
            assert payload['artifacts']['spec_writer'] == first['artifacts']['spec_writer']
        return delegate(messages, config=config)

    result = run_feature_development(project=project, work=tmp_path / 'resumed',
        goal=first['goal'], python=Path(sys.executable), chat=chat,
        configs={'spec_writer': LocalInferenceConfig('http://unused', 'fake')}, resume_roles=prior)
    assert result['status'] == 'verified', result.get('reason')
    assert invoked == ['feature:programmer', 'feature:reviewer']
    assert result['frozen_test_hashes'] == first['frozen_test_hashes']
