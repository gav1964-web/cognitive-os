"""A proposed out-of-scope file is rejected, never silently installed or dropped."""
import json

import pytest

from tests.runtime.test_feature_development import project, fake_chat, run


@pytest.mark.parametrize('repeat', [False, True])
def test_programmer_gets_bounded_scope_feedback_before_materialization(project, tmp_path, repeat):
    delegate, attempts = fake_chat(project), []

    def chat(messages, *, config):
        proposal = delegate(messages, config=config)
        if config.provider_label == 'feature:programmer':
            payload = json.loads(messages[1]['content'])
            attempts.append(payload)
            if len(attempts) == 2:
                feedback = payload['read_tool_result']
                assert 'tests/test_extra.py' in str(feedback['missing_required_fields'])
                assert feedback['invalid_response']['edits'][-1]['path'] == 'tests/test_extra.py'
            if len(attempts) == 1 or repeat:
                proposal['edits'].append({'path': 'tests/test_extra.py', 'source_sha256': None,
                                         'content': 'def test_extra():\n    assert True\n'})
        return proposal

    result = run(project, tmp_path, chat=chat)
    assert len(attempts) == 2
    if repeat:
        assert result['status'] == 'blocked'
        assert result['reason'].startswith('feature_role_format_repeated:unauthorized edit paths')
        assert not result['attempts']
    else:
        assert result['status'] == 'verified', result.get('reason')
    assert not (project / 'tests/test_extra.py').exists()
    assert not list((tmp_path / 'run').glob('attempt-*/project/tests/test_extra.py'))
