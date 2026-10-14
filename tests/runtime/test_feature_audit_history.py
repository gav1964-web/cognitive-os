"""Policy changes retire audit authority, preserve evidence and require fresh gates."""
import json
from copy import deepcopy

import pytest

from runtime.feature_acceptance import save
from runtime.feature_audit_history import history_path, load_history, save_history
from runtime.feature_quality_chat import QualityChat
from runtime.feature_quality_draft import audit_policy_matches, correction_feedback, draft_binding
from runtime.feature_quality_resume import restore_spec_draft
from runtime.local_inference import LocalInferenceConfig
from runtime.narrow_type_evidence_binding import content_digest
from tests.runtime.test_feature_development import spec
from tests.runtime.test_feature_quality import augment
from tests.runtime.test_feature_quality_resume import receipt


def changed_receipt(tmp_path, *, changed=True):
    project, expected, checkpoint, rows = receipt(tmp_path)
    roles = json.loads((checkpoint / 'report.json').read_text())['artifacts']
    payload = {'goal': 'goal', 'artifacts': roles, 'sources': [],
               'source_inventory_digest': content_digest(expected)}
    proposal = augment('spec_writer', spec())
    rows[0]['raw_response'] = proposal
    rows[0]['messages'][1]['content'] = json.dumps(payload)
    audit_payload = json.loads(rows[1]['messages'][1]['content'])
    audit_payload['specification'] = proposal
    audit_payload['prior_audit_issues'] = [{'reason': 'positive input boundary'}]
    rows[1]['messages'][1]['content'] = json.dumps(audit_payload)
    if changed:
        rows[1]['messages'][0]['content'] = 'Return one JSON object only.\nOld policy'
    rows[1]['raw_response']['issues'] = [
        {'reason': 'obsolete formatting demand'}, {'reason': 'missing negative boundary'}]
    for row in rows:
        row['request_digest'] = content_digest(row['messages'])
    save(checkpoint.parent.parent / 'transcript.json', rows)
    return project, expected, checkpoint, rows, payload


@pytest.mark.parametrize('split', [False, True])
def test_changed_policy_rechecks_all_old_concerns_but_routes_only_current_rejection(tmp_path, split):
    project, expected, checkpoint, rows, payload = changed_receipt(tmp_path)
    calls, current_issue = [], {'reason': 'missing negative boundary'}
    counterexample = {'survivors': [{'input': -2, 'expected': '(2)'}]}

    def transport(messages, *, config):
        data = json.loads(messages[1]['content'])
        role = config.provider_label
        calls.append(role)
        if role == 'quality:spec_auditor':
            assert data['historical_audits'][0]['audit'] == rows[1]['raw_response']
            assert data['historical_audits'][0]['prior_audit_issues'] == [{'reason': 'positive input boundary'}]
            assert 'historical_audits' not in data['previous_unaccepted_draft']
            assert data['review_counterexample_context'] == counterexample
            assert data['accepted_test_paths'] == [spec()['tests'][0]['path']]
            return {'decision': 'reject', 'issues': [current_issue]} if len(calls) == 1 else {'decision': 'approve'}
        feedback = data['quality_contract_feedback']
        assert feedback['issues'] == [{'acceptance_audit': {'decision': 'reject', 'issues': [current_issue]}}]
        assert feedback['prior_audit_issues'] == [current_issue]
        assert 'obsolete formatting demand' not in messages[1]['content']
        assert data['immutable_previous_tests'] == spec()['tests']
        return augment('spec_writer', spec())

    q = QualityChat(transport, tmp_path / 'new', audit_mode='on_feedback')
    kwargs = {}
    if split:
        save(tmp_path / 'writer.json', rows[:1])
        save(tmp_path / 'audit.json', rows[1:])
        kwargs = {'writer_transcript': tmp_path / 'writer.json', 'audit_transcript': tmp_path / 'audit.json'}
    restore_spec_draft(q, checkpoint, project, expected, 'goal', **kwargs)
    q.feedback, q.frozen = counterexample, spec()['tests']
    messages = [{'role': 'system', 'content': 'write tests'}, {'role': 'user', 'content': json.dumps(payload)}]
    result = q(messages, config=LocalInferenceConfig('http://unused', 'fake', provider_label='feature:spec_writer'))
    assert result == augment('spec_writer', spec())
    assert calls == ['quality:spec_auditor', 'feature:spec_writer', 'quality:spec_auditor']
    assert not q.pending and not q.retained  # Native qualification remains the caller's next gate.
    assert q.frozen == spec()['tests'] and q.feedback == counterexample


def test_same_policy_preserves_active_obligations_and_prior_issues(tmp_path):
    project, expected, checkpoint, rows, _ = changed_receipt(tmp_path, changed=False)
    q = QualityChat(None, tmp_path / 'new')
    restore_spec_draft(q, checkpoint, project, expected, 'goal')
    feedback = q.pending['spec_writer']['feedback']
    assert feedback['issues'] == [{'acceptance_audit': rows[1]['raw_response']}]
    assert feedback['prior_audit_issues'] == [{'reason': 'positive input boundary'}]
    assert 'historical_audits' not in feedback and not q.unaccepted


@pytest.mark.parametrize('instruction,expected', [
    ('Return one JSON object only.\ncurrent', True),
    ('Return one JSON object only.\ncurrent\nInput tests with content_reference exact code', True),
    ('Return one JSON object only.\nold current', False),
    ('Return one JSON object only.\ncurrent but different', False),
    ('legacy unknown', False),
])
def test_policy_comparison_does_not_accept_a_substring_match(instruction, expected):
    assert audit_policy_matches(instruction, 'current') is expected


def test_structural_correction_keeps_history_without_reviving_its_authority(tmp_path):
    project, expected, checkpoint, rows, _ = changed_receipt(tmp_path)
    q = QualityChat(None, tmp_path / 'new')
    restore_spec_draft(q, checkpoint, project, expected, 'goal')
    old = q.pending['spec_writer']['feedback']
    feedback = correction_feedback(old['rejected'], ['current structural defect'], old)
    assert feedback['issues'] == ['current structural defect']
    assert not feedback.get('prior_audit_issues')
    assert feedback['historical_audits'][0]['audit'] == rows[1]['raw_response']
    assert load_history(q.work, q.pending['spec_writer']['binding']) == feedback['historical_audits']


@pytest.mark.parametrize('tamper', [None, 'digest', 'binding', 'missing'])
def test_history_survives_resume_before_fresh_audit_and_checks_integrity(tmp_path, tamper):
    project, expected, checkpoint, rows, payload = changed_receipt(tmp_path)
    history = [{'audit': rows[1]['raw_response'], 'authority': 'historical_only_requires_current_audit'}]
    binding = draft_binding(payload, 'spec_writer')
    save_history(checkpoint.parent, binding, history)
    path = history_path(checkpoint.parent, binding)
    payload['quality_contract_feedback'] = {'historical_audits_digest': content_digest(history)}
    rows[0]['messages'][1]['content'] = json.dumps(payload)
    rows[0]['request_digest'] = content_digest(rows[0]['messages'])
    if tamper == 'missing':
        path.unlink()
    elif tamper:
        data = json.loads(path.read_text())
        if tamper == 'digest':
            data['evidence']['historical_audits'] = []
        else:
            data['evidence']['binding'] = 'other goal'
            data['digest'] = content_digest(data['evidence'])
        save(path, data)
    save(checkpoint.parent.parent / 'transcript.json', rows[:1])
    q = QualityChat(None, tmp_path / 'new')
    if tamper:
        with pytest.raises(ValueError, match='audit_history_integrity'):
            restore_spec_draft(q, checkpoint, project, expected, 'goal')
        assert not q.unaccepted
    else:
        restore_spec_draft(q, checkpoint, project, expected, 'goal')
        assert q.pending['spec_writer']['feedback']['historical_audits'] == history
        assert q.pending['spec_writer']['feedback']['issues'] == []
        assert load_history(q.work, binding) == history
        assert q.unaccepted['spec_writer']['proposal'] == rows[0]['raw_response']
    assert not q.retained


def test_second_policy_change_keeps_earlier_history_without_nested_duplication(tmp_path):
    project, expected, checkpoint, rows, payload = changed_receipt(tmp_path)
    history = [{'audit': {'decision': 'reject', 'issues': [{'reason': 'old boundary'}]}}]
    save_history(checkpoint.parent, draft_binding(payload, 'spec_writer'), history)
    audit_payload = json.loads(rows[1]['messages'][1]['content'])
    audit_payload['historical_audits'] = deepcopy(history)
    rows[1]['messages'][1]['content'] = json.dumps(audit_payload)
    rows[1]['request_digest'] = content_digest(rows[1]['messages'])
    save(checkpoint.parent.parent / 'transcript.json', rows)
    q = QualityChat(None, tmp_path / 'new')
    restore_spec_draft(q, checkpoint, project, expected, 'goal')
    restored = q.pending['spec_writer']['feedback']['historical_audits']
    assert len(restored) == 2 and restored[0] == history[0]
    assert restored[1]['audit'] == rows[1]['raw_response']


def test_other_design_history_is_not_reused(tmp_path):
    save_history(tmp_path, 'old design', [{'audit': 'old'}])
    assert load_history(tmp_path, 'new design') == []
    assert load_history(tmp_path, 'old design') == [{'audit': 'old'}]


@pytest.mark.parametrize('missing_hash', [False, True])
def test_history_resume_expands_paid_frozen_refs_before_comparative_audit(tmp_path, missing_hash):
    from runtime.feature_frozen_references import reference_catalog
    from runtime.feature_quality_resume import restore_unaccepted_proposal
    from runtime.feature_test_references import compact_test_references, expand_test_references
    project, expected, checkpoint, rows, payload = changed_receipt(tmp_path)
    frozen = deepcopy(spec()['tests'])
    frozen[0]['content'] += '# long test documentation\n' * 40
    payload['immutable_previous_tests'] = frozen
    rows[0]['raw_response']['tests'] = reference_catalog(frozen)
    if missing_hash:
        rows[0]['raw_response']['tests'][0].pop('content_sha256')
    rows[0]['messages'][1]['content'] = json.dumps(payload)
    rows[0]['request_digest'] = content_digest(rows[0]['messages'])
    path = checkpoint.parent.parent / 'transcript.json'
    save(path, rows[:1])
    save_history(checkpoint.parent, draft_binding(payload, 'spec_writer'), [{'audit': rows[1]['raw_response']}])
    q = QualityChat(None, tmp_path / 'new')
    q.frozen = frozen
    restore_unaccepted_proposal(q, checkpoint, project, expected, 'goal', path)
    feedback = q.pending['spec_writer']['feedback']
    assert feedback['rejected']['tests'] == frozen
    assert q.unaccepted['spec_writer']['proposal'] == rows[0]['raw_response']
    context = {'specification': {'tests': frozen}, 'previous_unaccepted_draft': feedback}
    compacted, count = compact_test_references(context)
    assert count == 1 and expand_test_references(compacted) == context
