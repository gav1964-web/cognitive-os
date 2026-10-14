"""One format correction may recover a response; invalid JSON never authorizes work."""
import json

import pytest

from runtime.local_inference import LocalInferenceError
from tests.runtime.test_feature_development import project, fake_chat, run


@pytest.mark.parametrize('recover', [True, False])
def test_format_retry_is_bounded_and_explicit(project, tmp_path, recover):
    delegate = fake_chat(project)
    calls = []
    def chat(messages, *, config):
        if config.provider_label == 'feature:analyzer':
            calls.append(messages)
            if len(calls) == 1 or not recover:
                raise LocalInferenceError('structured response is not a complete JSON object')
            feedback = json.loads(messages[1]['content'])['read_tool_result']
            assert 'No decision was accepted' in feedback['instruction']
        return delegate(messages, config=config)
    result = run(project, tmp_path, chat=chat)
    assert len(calls) == 2
    assert result['status'] == ('verified' if recover else 'blocked')
    assert not result['source_apply']
    if not recover:
        assert result['artifacts'] == {}


@pytest.mark.parametrize('recover', [True, False])
def test_duplicate_edit_path_gets_bounded_feedback(project, tmp_path, recover):
    delegate = fake_chat(project)
    calls = []

    def chat(messages, *, config):
        response = delegate(messages, config=config)
        if config.provider_label == 'feature:programmer':
            calls.append(messages)
            if len(calls) == 1 or not recover:
                response['edits'] *= 2
            else:
                feedback = json.loads(messages[1]['content'])['read_tool_result']
                assert 'unique edit paths' in feedback['missing_required_fields'][0]
        return response

    result = run(project, tmp_path, chat=chat)
    assert len(calls) == 2
    assert result['status'] == ('verified' if recover else 'blocked')
    assert not result['source_apply']
