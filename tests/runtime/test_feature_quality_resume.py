"""Resumption preserves authorship and never admits a rejected specification."""
import json
from pathlib import Path

import pytest

from runtime.feature_acceptance import save
from runtime.feature_quality_chat import QualityChat
from runtime.feature_quality_resume import restore_spec_draft
from runtime.feature_workspace import inventory
from runtime.narrow_type_evidence_binding import content_digest


def receipt(tmp_path):
    project = tmp_path / 'source'
    project.mkdir()
    (project / 'engine.py').write_text('value = 1\n')
    expected = inventory(project)
    prior = tmp_path / 'old/run/cycle-0'
    roles = {'analyzer': {'status': 'ready'}, 'architect': {'status': 'ready', 'design': 'fixed goal'}}
    save(prior / 'report.json', {'project': str(project), 'goal': 'goal', 'artifacts': roles, 'attempts': []})
    save(prior / 'source-inventory.json', expected)
    for name, artifact in roles.items():
        save(prior / (name + '.json'), artifact)
    save(prior.parent / 'report.json', {'goal': 'goal', 'source_hashes': expected})
    draft = {'status': 'ready', 'tests': [{'path': 'tests/test_new.py', 'content': 'unaccepted draft'}]}
    rows = []
    for role, payload, response in [
        ('feature:spec_writer', {'goal': 'goal'}, draft),
        ('quality:spec_auditor', {'goal': 'goal', 'design': roles['architect'], 'specification': draft},
         {'decision': 'reject', 'issues': [{'reason': 'missing boundary'}]})]:
        messages = [{'role': 'system', 'content': role}, {'role': 'user', 'content': json.dumps(payload)}]
        rows.append({'status': 'returned', 'messages': messages, 'request_digest': content_digest(messages),
                     'raw_response': response, 'telemetry': [{'provider_label': role}]})
    save(prior.parent.parent / 'transcript.json', rows)
    return project, expected, prior, rows


def test_restore_only_rejected_draft_with_fresh_gates(tmp_path):
    project, expected, prior, _ = receipt(tmp_path)
    q = QualityChat(None, tmp_path / 'new')
    restore_spec_draft(q, prior, project, expected, 'goal')
    assert q.pending['spec_writer']['feedback']['issues'][0]['acceptance_audit']['decision'] == 'reject'
    assert not q.retained and not q.frozen
    assert q.events[-1]['event'] == 'unaccepted_draft_restored'


@pytest.mark.parametrize('tamper', ['source', 'digest', 'draft', 'design', 'accepted'])
def test_unbound_checkpoint_cannot_restore_pending_spec(tmp_path, tamper):
    project, expected, prior, rows = receipt(tmp_path)
    if tamper == 'source':
        expected = {**expected, 'engine.py': 'changed'}
    elif tamper == 'digest':
        rows[-1]['request_digest'] = 'changed'
    elif tamper == 'draft':
        rows[0]['raw_response']['tests'] = []
    elif tamper == 'design':
        payload = json.loads(rows[-1]['messages'][1]['content'])
        payload['design'] = {'status': 'ready', 'design': 'other'}
        rows[-1]['messages'][1]['content'] = json.dumps(payload)
        rows[-1]['request_digest'] = content_digest(rows[-1]['messages'])
    else:
        path = prior / 'report.json'
        report = json.loads(path.read_text())
        report['artifacts']['spec_writer'] = {'status': 'ready'}
        save(path, report)
    save(prior.parent.parent / 'transcript.json', rows)
    q = QualityChat(None, tmp_path / 'new')
    with pytest.raises(ValueError, match='(quality_resume|feature_checkpoint)'):
        restore_spec_draft(q, prior, project, expected, 'goal')
    assert not q.pending and not q.retained


@pytest.mark.parametrize('tamper', [None, 'writer_goal', 'source_excerpt', 'different_draft'])
def test_split_transcripts_require_exact_writer_audit_and_current_sources(tmp_path, tamper):
    project, expected, prior, rows = receipt(tmp_path)
    roles = json.loads((prior / 'report.json').read_text())['artifacts']
    payload = {'goal': 'goal', 'artifacts': roles}
    if tamper == 'writer_goal':
        payload['goal'] = 'another goal'
    rows[0]['messages'][1]['content'] = json.dumps(payload)
    rows[0]['request_digest'] = content_digest(rows[0]['messages'])
    if tamper == 'different_draft':
        rows[0]['raw_response'] = {**rows[0]['raw_response'], 'tests': []}
    payload = json.loads(rows[1]['messages'][1]['content'])
    payload['sources'] = [{'path': 'engine.py', 'start': 1, 'end': 1,
                          'content': 'value = 99\n' if tamper == 'source_excerpt' else 'value = 1\n'}]
    rows[1]['messages'][1]['content'] = json.dumps(payload)
    rows[1]['request_digest'] = content_digest(rows[1]['messages'])
    writer_path, audit_path = tmp_path / 'writer.json', tmp_path / 'audit.json'
    save(writer_path, [rows[0]])
    save(audit_path, [rows[1]])
    q = QualityChat(None, tmp_path / 'new')
    kwargs = {'writer_transcript': writer_path, 'audit_transcript': audit_path}
    if tamper:
        with pytest.raises(ValueError, match='quality_resume'):
            restore_spec_draft(q, prior, project, expected, 'goal', **kwargs)
        assert not q.pending
    else:
        restore_spec_draft(q, prior, project, expected, 'goal', **kwargs)
        assert q.pending['spec_writer']['feedback']['rejected'] == rows[0]['raw_response']
        assert not q.retained and not q.frozen


@pytest.mark.parametrize('tamper', [None, 'digest', 'goal', 'source'])
def test_unaccepted_proposal_reuse_never_sets_accepted_roles(tmp_path, tamper):
    from runtime.feature_quality_resume import restore_unaccepted_proposal
    project, expected, prior, rows = receipt(tmp_path)
    roles = json.loads((prior / 'report.json').read_text())['artifacts']
    payload = {'goal': 'other' if tamper == 'goal' else 'goal', 'artifacts': roles,
               'source_inventory_digest': 'changed' if tamper == 'source' else content_digest(expected)}
    row = rows[0]
    row['messages'][1]['content'] = json.dumps(payload)
    row['request_digest'] = 'changed' if tamper == 'digest' else content_digest(row['messages'])
    path = tmp_path / 'proposal.json'
    save(path, [row])
    q = QualityChat(None, tmp_path / 'new')
    if tamper:
        with pytest.raises(ValueError, match='quality_resume_proposal'):
            restore_unaccepted_proposal(q, prior, project, expected, 'goal', path)
        assert not q.unaccepted
    else:
        restore_unaccepted_proposal(q, prior, project, expected, 'goal', path)
        assert q.unaccepted['spec_writer']['proposal'] == row['raw_response']
    assert not q.retained and not q.frozen
