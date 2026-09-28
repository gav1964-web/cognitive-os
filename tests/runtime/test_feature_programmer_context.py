"""Programmer starts from cited writable source and can explicitly read more."""
import json

from runtime.feature_checkpoint import recover_pending_read
from runtime.feature_workspace import inventory

from tests.runtime.test_feature_development import project, fake_chat, run


def test_programmer_reads_missing_context_without_repeating_whole_analysis(project, tmp_path):
    with (project / 'engine.py').open('a') as stream:
        stream.write('\ndef unrelated():\n    return "not initially needed"\n')
    delegate = fake_chat(project)
    rounds = {'analyzer': 0, 'programmer': 0}
    def chat(messages, *, config):
        role = config.provider_label.split(':')[-1]
        payload = json.loads(messages[1]['content'])
        if role == 'analyzer':
            rounds[role] += 1
            if rounds[role] == 1:
                return {'status': 'read', 'reads': [{'path': 'engine.py', 'start': 1, 'end': 5}]}
            value = delegate(messages, config=config)
            value['evidence'] = [{'path': 'engine.py', 'start': 1, 'end': 2, 'finding': 'plain display'}]
            return value
        if role == 'programmer':
            rounds[role] += 1
            source = ''.join(r['content'] for r in payload['sources'])
            if rounds[role] == 1:
                assert 'def display' in source and 'unrelated' not in source
                assert payload['sources'][0]['sha256']
                return {'status': 'read', 'reads': [{'path': 'engine.py', 'start': 3, 'end': 5}]}
            assert 'unrelated' in source
        return delegate(messages, config=config)
    result = run(project, tmp_path, chat=chat)
    assert result['status'] == 'verified'
    assert rounds['programmer'] == 2


def test_pending_read_retains_exact_ranges_and_role(project, tmp_path):
    with (project / 'engine.py').open('a') as stream:
        stream.write('\ndef unrelated():\n    return "extra"\n')
    prior = tmp_path / 'previous/run'; prior.mkdir(parents=True)
    calls = [{'status': 'returned', 'telemetry': [{'provider_label': 'feature:programmer'}],
              'raw_response': {'status': 'read', 'reads': [{'path': 'engine.py', 'start': start, 'end': end}]}}
             for start, end in [(1, 5), (4, 5)]]
    (prior.parent / 'transcript.json').write_text(json.dumps(calls))
    rows = recover_pending_read(prior, project, inventory(project), 'programmer')
    assert [(r['start'], r['end']) for r in rows] == [(4, 5)]
    assert 'def display' not in rows[0]['content']
    assert recover_pending_read(prior, project, inventory(project), 'spec_writer') == []
