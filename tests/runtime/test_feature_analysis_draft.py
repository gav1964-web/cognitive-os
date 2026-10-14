"""Unaccepted analysis context cannot become a decision or cross source/role boundaries."""
import json
from pathlib import Path

import pytest

from runtime.feature_analysis_draft import load_analysis_draft
from runtime.feature_workspace import inventory, read_sources, catalog
from tests.runtime.test_feature_development import project, fake_chat, run


def checkpoint(project, tmp_path):
    prior = tmp_path / 'prior/run'; prior.mkdir(parents=True)
    goal = 'Improve negative display labels'
    expected = inventory(project)
    sources = read_sources(project, expected, [{'path': 'engine.py', 'start': 1, 'end': 2}])
    draft = {'status': 'ready', 'analysis': 'old unaccepted draft', 'scope': ['engine.py'],
             'evidence': [{'path': 'engine.py', 'start': 1, 'end': 2, 'finding': 'plain output'}],
             'unknowns': [], 'user_outcome': 'negative labels'}
    call = {'status': 'failed', 'usage_known': True,
            'telemetry': [{'provider_label': 'feature:analyzer'}],
            'messages': [{}, {'content': json.dumps({'goal': goal, 'sources': sources})}],
            'response_evidence': [{'content': json.dumps({'status': 'read', 'reads': []}) + '\n' + json.dumps(draft)}]}
    for name, value in [('source-inventory.json', expected),
            ('report.json', {'goal': goal, 'project': str(project)}),
            ('source-context.json', {'goal': goal, 'sources': sources, 'catalog': catalog(project, expected)})]:
        (prior / name).write_text(json.dumps(value))
    (prior.parent / 'transcript.json').write_text(json.dumps([call]))
    return prior, goal, expected, call


@pytest.mark.parametrize('changed', [None, 'source', 'goal', 'role', 'usage', 'citation'])
def test_only_bound_observed_analysis_can_be_reconsidered(project, tmp_path, changed):
    prior, goal, expected, call = checkpoint(project, tmp_path)
    if changed == 'source': (project / 'engine.py').write_text('# replaced\n')
    if changed == 'goal': goal = 'different task'
    if changed == 'role': call['telemetry'][0]['provider_label'] = 'feature:reviewer'
    if changed == 'usage': call['usage_known'] = False
    if changed == 'citation': call['messages'][1]['content'] = json.dumps({'goal': goal, 'sources': []})
    (prior.parent / 'transcript.json').write_text(json.dumps([call]))
    if changed:
        with pytest.raises(ValueError): load_analysis_draft(prior, project, expected, goal)
    else:
        value = load_analysis_draft(prior, project, expected, goal)
        assert value['accepted'] is False and len(value['sources']) == 1
        assert 'fresh complete Analyzer' in value['instruction']


def test_fresh_model_decision_is_required_after_draft(project, tmp_path):
    prior, _, _, _ = checkpoint(project, tmp_path)
    delegate = fake_chat(project)
    def chat(messages, *, config):
        if config.provider_label == 'feature:analyzer':
            payload = json.loads(messages[1]['content'])
            assert payload['unaccepted_analysis_draft']['accepted'] is False
            assert 'analyzer' not in payload['artifacts']
            return {'status': 'blocked', 'reason': 'fresh decision rejects prior draft'}
        return delegate(messages, config=config)
    result = run(project, tmp_path, chat=chat, resume_context=prior, resume_analysis_draft=True)
    assert result['status'] == 'blocked'
    assert 'fresh decision rejects' in result['reason']
    assert 'analyzer' not in result['artifacts']
