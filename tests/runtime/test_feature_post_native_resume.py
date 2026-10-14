"""A later audited correction cannot be replaced by an older rejected native draft."""
import json
import pytest
from runtime.feature_acceptance import save
from runtime.feature_quality_chat import QualityChat
from runtime.feature_quality_resume import restore_native_rejected_spec
from runtime.narrow_type_evidence_binding import content_digest
from tests.runtime.test_feature_quality_resume import receipt


@pytest.mark.parametrize('change', ['none', 'unrelated_native', 'tampered_audit', 'tampered_goal'])
def test_native_resume_retains_bound_later_audit_without_approval(tmp_path, change):
    project, expected, prior, rows = receipt(tmp_path)
    old = {'status': 'ready', 'tests': [{'path': 'tests/test_old.py', 'content': 'wrong native expectation'}]}
    report = json.loads((prior/'report.json').read_text())
    report['spec_attempts'] = [{'status': 'rejected', 'feedback': {'rejected_spec': old}}]
    save(prior/'report.json', report); save(prior/'spec-proposal-1.json', old)
    payload = {'goal': 'other' if change == 'tampered_goal' else 'goal',
        'artifacts': report['artifacts'], 'source_inventory_digest': content_digest(expected),
        'feedback': {'rejected_spec': {} if change == 'unrelated_native' else old}}
    rows[0]['messages'][1]['content'] = json.dumps(payload)
    rows[0]['request_digest'] = content_digest(rows[0]['messages'])
    if change == 'tampered_audit': rows[-1]['request_digest'] = 'bad digest'
    save(prior.parent.parent/'transcript.json', rows)
    q = QualityChat(None, tmp_path/'new')
    if change.startswith('tampered'):
        with pytest.raises(ValueError, match='quality_resume'):
            restore_native_rejected_spec(q, prior, project, expected, 'goal')
    else:
        restore_native_rejected_spec(q, prior, project, expected, 'goal')
        if change == 'none':
            assert q.pending['spec_writer']['feedback']['rejected'] == rows[0]['raw_response']
            assert q.events[-1]['event'] == 'post_native_audit_restored'
        else:
            assert not q.pending
    assert not q.frozen and not q.retained
