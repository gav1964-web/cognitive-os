"""Unambiguous negative review spelling can route repair, never grant approval."""
import pytest

from tests.runtime.test_feature_development import project, fake_chat, run


@pytest.mark.parametrize('status,decision', [('reject', 'reject'), ('approve', 'approve'), ('reject', 'approve')])
def test_only_explicit_consistent_rejection_is_normalized(project, tmp_path, status, decision):
    delegate = fake_chat(project)
    original = []

    def chat(messages, *, config):
        value = delegate(messages, config=config)
        if config.provider_label == 'feature:reviewer':
            value.update(status=status, decision=decision, reason='review observation')
            original.append(value)
        return value

    result = run(project, tmp_path, chat=chat)
    assert result['status'] == 'blocked' and not result['source_apply']
    assert original[0]['status'] == status
    if status == decision == 'reject':
        assert result['reason'] == 'feature_review_rejected:review observation'
        assert result['artifacts']['reviewer']['original_model_status'] == 'reject'
        assert result['artifacts']['reviewer']['decision'] == 'reject'
    else:
        assert result['reason'].startswith('feature_role_blocked:')
        assert 'reviewer' not in result['artifacts']
