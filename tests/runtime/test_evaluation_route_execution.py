import json
from pathlib import Path

import pytest

from evaluation.executors.workspace_agent import run_agent, owned
from runtime.evaluation_route_execution import MeteredChat, RouteBudgetExceeded, verify_task15
from runtime.local_inference import LocalInferenceConfig


def chat_sequence(items, captured=None):
    values = iter(items)
    def chat(messages):
        if captured is not None:
            captured.append(json.loads(json.dumps(messages)))
        return next(values)
    return chat


def test_agent_writes_verifies_and_finishes_without_cos_context(tmp_path):
    captured = []
    result = run_agent(tmp_path, 'Build a CLI.', chat=chat_sequence([
        {'action': 'write', 'files': [{'path': 'main.py', 'content': 'print(42)\n'}]},
        {'action': 'verify'}, {'action': 'finish', 'summary': 'Done.'}], captured),
        verify=lambda p: {'status': 'passed'})
    assert result['status'] == 'completed'
    assert (tmp_path / 'main.py').read_text() == 'print(42)\n'
    assert len(captured[0]) == 2
    assert 'Planning context' not in json.dumps(captured)


def test_write_invalidates_prior_verification(tmp_path):
    result = run_agent(tmp_path, 'Task', chat=chat_sequence([
        {'action': 'verify'}, {'action': 'write', 'files': [{'path': 'main.py', 'content': 'broken'}]},
        {'action': 'finish'}]), verify=lambda p: {'status': 'passed'}, max_turns=3)
    assert result['status'] == 'blocked'
    assert result['events'][-1]['observation']['error'] == 'passing_verification_required'


@pytest.mark.parametrize('name', ['../a', '/a', 'C:/a', 'x:stream', '.env', 'inputs/data.txt'])
def test_agent_cannot_write_private_external_or_input_paths(tmp_path, name):
    with pytest.raises(ValueError):
        owned(tmp_path, name, write=True)


def test_read_only_inputs_rejection_is_visible_to_agent(tmp_path):
    result = run_agent(tmp_path, 'Task', chat=chat_sequence([{'action': 'write',
        'files': [{'path': 'inputs/source.txt', 'content': 'replacement'}]}]),
        verify=lambda p: {}, max_turns=1)
    assert result['events'][0]['observation']['reason'] == 'read_only_inputs'


def test_budget_stops_before_provider_and_usage_is_not_invented(monkeypatch):
    calls = []
    monkeypatch.setattr('runtime.evaluation_route_execution.call_json_chat', lambda *a, **k: calls.append(1) or {})
    chat = MeteredChat(LocalInferenceConfig('http://gateway/v1', 'test'), max_calls=1)
    chat([])
    with pytest.raises(RouteBudgetExceeded):
        chat([])
    assert len(calls) == 1
    assert chat.usage()['status'] == 'unknown' and chat.usage()['input'] is None
    assert chat.usage()['estimated_cost'] is None


def test_reported_zero_tokens_are_not_a_measured_free_run():
    chat = MeteredChat(LocalInferenceConfig('http://gateway/v1', 'test'))
    chat.records.append({'usage_reported': True, 'prompt_tokens': 0, 'completion_tokens': 0})
    assert chat.usage()['status'] == 'unknown'


def test_verification_requires_real_product_and_nonempty_tests(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    result = verify_task15(project, tmp_path / 'checks')
    assert result['status'] == 'failed'
    assert result['pytest']['passing'] == 0
    assert result['acceptance']['status'] == 'failed'


def test_inputs_are_visible_but_outside_native_project_scope(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    inputs = tmp_path / 'inputs'
    inputs.mkdir()
    (inputs / 'fixture.py').write_text('value = 42')
    assert owned(project, 'inputs/fixture.py').read_text() == 'value = 42'
    assert list(project.rglob('*.py')) == []


def test_provider_stop_preserves_prior_actions(tmp_path):
    calls = []
    def chat(messages):
        if calls:
            raise RouteBudgetExceeded('stop')
        calls.append(1)
        return {'action': 'list'}
    result = run_agent(tmp_path, 'Task', chat=chat, verify=lambda p: {})
    assert result['reason'] == 'RouteBudgetExceeded'
    assert result['events'][0]['action'] == 'list'


def test_real_reported_tokens_replace_reserved_estimate(monkeypatch):
    def provider(messages, config):
        config.telemetry_sink({'total_tokens': 10})
        return {}
    monkeypatch.setattr('runtime.evaluation_route_execution.call_json_chat', provider)
    chat = MeteredChat(LocalInferenceConfig('http://gateway/v1', 'test'), max_tokens=3500)
    chat([])
    chat([])
    assert chat.accounted_tokens == 20


def test_root_level_pytest_files_are_collected(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'test_main.py').write_text('def test_real_discovery(): assert 2 + 2 == 4\n')
    result = verify_task15(project, tmp_path / 'checks')
    assert result['pytest']['passing'] == 1
    assert result['status'] == 'failed'  # No actual CLI yet; tests alone cannot certify it.


def test_src_layout_is_importable_without_install_or_project_pytest_options(tmp_path):
    project = tmp_path / 'project'
    (project / 'src' / 'example').mkdir(parents=True)
    (project / 'src/example/__init__.py').write_text('value = 42\n')
    (project / 'test_example.py').write_text('from example import value\ndef test_value(): assert value == 42\n')
    result = verify_task15(project, tmp_path / 'checks')
    assert result['pytest']['passing'] == 1
    assert result['status'] == 'failed'  # Test discovery is not acceptance.


def test_fixed_backup_trial_does_not_change_default_failover():
    from tools.run_evaluation_routes import select_model_config
    backup = LocalInferenceConfig('http://gateway/v1', 'backup', api_key='backup-test')
    primary = LocalInferenceConfig('http://gateway/v1', 'primary', fallbacks=(backup,))
    fixed = select_model_config(primary, 'backup')
    assert fixed.model == 'backup' and fixed.fallbacks == ()
    assert fixed.api_key == 'backup-test'
    assert select_model_config(primary, 'failover') is primary
    assert primary.fallbacks == (backup,)


@pytest.mark.parametrize('response_observed', [False, True])
def test_single_model_failure_is_recorded_without_exception_secrets(monkeypatch, response_observed):
    from runtime.local_inference import LocalInferenceError
    def provider(messages, config):
        if response_observed:
            config.telemetry_sink({'model': 'test', 'model_reported': True})
        failure = LocalInferenceError('private gateway response must not be stored')
        failure.http_status = 503 if not response_observed else None
        raise failure
    monkeypatch.setattr('runtime.evaluation_route_execution.call_json_chat', provider)
    chat = MeteredChat(LocalInferenceConfig('http://gateway/v1', 'test'))
    with pytest.raises(LocalInferenceError):
        chat([])
    assert chat.records[-1]['event'] == 'attempt_failed'
    assert chat.records[-1]['response_observed'] is response_observed
    assert 'private gateway' not in json.dumps(chat.records)
    assert chat.usage()['status'] == 'unknown'
