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
        instruction = ('Return one JSON object only.\n' + QualityChat(None, tmp_path).policy['spec_auditor']
                       if role == 'quality:spec_auditor' else role)
        messages = [{'role': 'system', 'content': instruction}, {'role': 'user', 'content': json.dumps(payload)}]
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


def test_paid_unreviewed_draft_can_resume_without_inventing_prior_approval(tmp_path):
    project, expected, prior, rows = receipt(tmp_path)
    roles = json.loads((prior / 'report.json').read_text())['artifacts']
    row = rows[0]
    row['messages'][1]['content'] = json.dumps({'goal': 'goal', 'artifacts': roles,
        'source_inventory_digest': content_digest(expected)})
    row['request_digest'] = content_digest(row['messages'])
    save(prior.parent.parent / 'transcript.json', [row])
    q = QualityChat(None, tmp_path / 'new')
    restore_spec_draft(q, prior, project, expected, 'goal')
    assert q.unaccepted['spec_writer']['proposal'] == row['raw_response']
    assert not q.retained and not q.pending and not q.frozen
    assert q.events[-1]['event'] == 'unreviewed_draft_restored'


@pytest.mark.parametrize('tamper', [False, True])
def test_new_paid_draft_after_older_approval_is_reaudited(tmp_path, tamper):
    from copy import deepcopy
    project, expected, prior, rows = receipt(tmp_path)
    roles = json.loads((prior / 'report.json').read_text())['artifacts']
    rows[1]['raw_response'] = {'decision': 'approve'}
    newer = deepcopy(rows[0])
    newer['raw_response']['tests'][0]['content'] = 'new paid draft, not approved'
    newer['messages'][1]['content'] = json.dumps({'goal': 'other' if tamper else 'goal',
        'artifacts': roles, 'source_inventory_digest': content_digest(expected)})
    newer['request_digest'] = content_digest(newer['messages'])
    save(prior.parent.parent / 'transcript.json', [*rows, newer])
    q = QualityChat(None, tmp_path / 'new')
    if tamper:
        with pytest.raises(ValueError, match='proposal_identity'):
            restore_spec_draft(q, prior, project, expected, 'goal')
        assert not q.unaccepted
    else:
        restore_spec_draft(q, prior, project, expected, 'goal')
        assert q.unaccepted['spec_writer']['proposal'] == newer['raw_response']
    assert not q.retained and not q.pending and not q.frozen


def test_changed_auditor_policy_reaudits_same_bound_draft_without_accepting_it(tmp_path):
    project, expected, prior, rows = receipt(tmp_path)
    roles = json.loads((prior / 'report.json').read_text())['artifacts']
    rows[0]['messages'][1]['content'] = json.dumps({'goal': 'goal', 'artifacts': roles,
        'source_inventory_digest': content_digest(expected)})
    rows[0]['request_digest'] = content_digest(rows[0]['messages'])
    rows[1]['messages'][0]['content'] = 'Return one JSON object only.\nOld auditor rules'
    rows[1]['request_digest'] = content_digest(rows[1]['messages'])
    save(prior.parent.parent / 'transcript.json', rows)
    q = QualityChat(None, tmp_path / 'new')
    restore_spec_draft(q, prior, project, expected, 'goal')
    assert q.unaccepted['spec_writer']['proposal'] == rows[0]['raw_response']
    assert 'different auditor policy' in q.pending['spec_writer']['feedback']['instruction']
    assert q.pending['spec_writer']['feedback']['issues'] == []
    assert q.pending['spec_writer']['feedback']['historical_audits'][0]['audit'] == rows[1]['raw_response']
    assert not q.retained and not q.frozen
    assert any(e['event'] == 'unaccepted_draft_policy_reaudit' for e in q.events)


def test_restored_feedback_expands_output_refs_before_compacting_audit_context(tmp_path):
    from runtime.feature_frozen_references import reference_catalog
    from runtime.feature_test_references import compact_test_references, expand_test_references
    project, expected, prior, rows = receipt(tmp_path)
    body = 'def test_value():\n    assert value == 1\n' + '# documentation\n' * 80
    frozen = [{'path': 'tests/test_new.py', 'content': body}]
    rows[0]['raw_response']['tests'] = reference_catalog(frozen)
    payload = json.loads(rows[0]['messages'][1]['content'])
    payload['immutable_previous_tests'] = frozen
    rows[0]['messages'][1]['content'] = json.dumps(payload)
    rows[0]['request_digest'] = content_digest(rows[0]['messages'])
    audit_payload = json.loads(rows[1]['messages'][1]['content'])
    audit_payload['specification']['tests'] = frozen
    rows[1]['messages'][1]['content'] = json.dumps(audit_payload)
    rows[1]['request_digest'] = content_digest(rows[1]['messages'])
    save(prior.parent.parent / 'transcript.json', rows)
    q = QualityChat(None, tmp_path / 'new')
    restore_spec_draft(q, prior, project, expected, 'goal')
    context = {'specification': audit_payload['specification'],
               'previous_unaccepted_draft': q.pending['spec_writer']['feedback']}
    assert context['previous_unaccepted_draft']['rejected']['tests'] == frozen
    compacted, count = compact_test_references(context)
    assert count == 1 and expand_test_references(compacted) == context


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


@pytest.mark.parametrize('tamper', [False, True])
def test_resume_reuses_paid_unaudited_draft_without_granting_approval(tmp_path, tamper):
    project, expected, prior, rows = receipt(tmp_path)
    roles = json.loads((prior / 'report.json').read_text())['artifacts']
    context = {'survivors': [{'reason': 'missing boundary'}]}
    payload = {'goal':'goal', 'artifacts':roles, 'source_inventory_digest':content_digest(expected),
               'quality_feedback':context}
    if tamper:
        payload['immutable_previous_tests'] = [{'path':'tests/test_fake.py','content':'invented'}]
    messages = [{'role':'system','content':'writer'}, {'role':'user','content':json.dumps(payload)}]
    response = {'status':'ready','tests':[{'path':'tests/test_new.py','content':'paid revision'}]}
    rows.append({'status':'returned','messages':messages,'request_digest':content_digest(messages),
                 'raw_response':response,'telemetry':[{'provider_label':'feature:spec_writer'}]})
    save(prior.parent.parent/'transcript.json',rows)
    q = QualityChat(None,tmp_path/'new')
    if tamper:
        with pytest.raises(ValueError,match='frozen_context_mismatch'):
            restore_spec_draft(q,prior,project,expected,'goal')
        assert not q.unaccepted
    else:
        restore_spec_draft(q,prior,project,expected,'goal')
        assert q.unaccepted['spec_writer']['proposal'] == response
        assert q.feedback == context and not q.retained
        assert q.pending['spec_writer']['feedback']['issues'][0]['acceptance_audit']['decision']=='reject'


@pytest.mark.parametrize('tamper',[False,True])
def test_native_accepted_tests_survive_intervening_rejected_cycle(tmp_path,tamper):
    import sys
    from runtime.feature_development import run_feature_development
    from runtime.feature_quality_resume import restore_prior_frozen
    from runtime.local_inference import LocalInferenceConfig
    from tests.runtime.test_feature_development import fake_chat, spec
    project=tmp_path/'source'
    (project/'tests').mkdir(parents=True)
    (project/'engine.py').write_text('def display(value):\n    return str(value)\n')
    (project/'tests/test_existing.py').write_text('def test_preserve():\n    assert True\n')
    prior=tmp_path/'run/cycle-0'
    cfg=LocalInferenceConfig('http://unused','fake')
    result=run_feature_development(project=project,work=prior,goal='goal',python=Path(sys.executable),
        chat=fake_chat(project),configs={r:cfg for r in ('analyzer','architect','spec_writer')})
    assert result['status']=='verified'
    checkpoint=tmp_path/'run/cycle-1'
    save(prior.parent/'report.json',{'goal':'goal','source_hashes':inventory(project),
        'cycles':[{'checkpoint':str(prior)},{'checkpoint':str(checkpoint)}]})
    if tamper:
        accepted=json.loads((prior/'spec_writer.json').read_text())
        accepted['tests'][0]['content']='changed'
        save(prior/'spec_writer.json',accepted)
    q=QualityChat(None,tmp_path/'new')
    if tamper:
        with pytest.raises(ValueError,match='frozen_spec_mismatch'):
            restore_prior_frozen(q,checkpoint,project,inventory(project),'goal')
        assert not q.frozen
    else:
        restore_prior_frozen(q,checkpoint,project,inventory(project),'goal')
        assert q.frozen == spec()['tests'] and not q.retained
