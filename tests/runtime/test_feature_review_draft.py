"""A draft is context, and is bound to the exact proposal and frozen tests."""
import json

import pytest

from runtime.feature_checkpoint import review_draft


@pytest.mark.parametrize('changed', [None, 'proposal', 'tests', 'role'])
def test_draft_is_not_an_approval_and_cannot_cross_candidates(tmp_path, changed):
    prior = tmp_path / 'run'; prior.mkdir()
    proposal = {'edits': ['original']}; spec = {'tests': ['frozen']}
    call = {'status': 'failed', 'usage_known': True,
        'telemetry': [{'provider_label': 'feature:reviewer'}],
        'response_evidence': [{'content': '{"status":"ready","decision":"approve",'}],
        'messages': [{}, {'content': json.dumps({'proposal': proposal,
            'artifacts': {'spec_writer': spec}, 'sources': []})}]}
    if changed == 'role': call['telemetry'][0]['provider_label'] = 'feature:programmer'
    (tmp_path / 'transcript.json').write_text(json.dumps([call]))
    if changed == 'proposal': proposal = {'edits': ['different']}
    if changed == 'tests': spec = {'tests': ['different']}
    if changed:
        with pytest.raises(ValueError, match='review_draft_not_bound'):
            review_draft(prior, proposal, spec)
    else:
        draft = review_draft(prior, proposal, spec)
        assert draft['accepted'] is False and 'decision' not in draft
        assert 'NO approval' in draft['instruction']
