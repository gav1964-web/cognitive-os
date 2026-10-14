"""Explicit semantic failover preserves reason, model origin and bounded attempts."""
import io
import json
from dataclasses import replace
from pathlib import Path
from urllib.error import HTTPError

import pytest

from runtime import llm_failover
from runtime.local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat
from runtime.role_inference import role_model_config


def experimental_role_config(role):
    """Exercise optional provider failover without restoring it in live defaults."""
    backup = replace(role_model_config(role), provider_label='deepseek_role_backup')
    return replace(backup, model='geminivm/pro', provider_label='experimental',
                   fallbacks=(backup,), fallback_on_codes=('refusal', 'suspected_stub', 'busy'))


@pytest.fixture(autouse=True)
def circuits():
    llm_failover._COOLDOWNS.clear()
    yield
    llm_failover._COOLDOWNS.clear()


def rejected(code='refusal', status=422):
    payload = {'error': {'code': code}, 'provider_diagnostics': {
        'response_status': code, 'run_id': 'saved-run', 'requested_model': 'pro', 'resolved_model': 'pro'}}
    return HTTPError('http://gateway', status, 'error', {}, io.BytesIO(json.dumps(payload).encode()))


def reply(value):
    return io.BytesIO(json.dumps({'model': 'deepseek-real-model', 'choices': [
        {'finish_reason': 'stop', 'message': {'content': json.dumps(value)}}],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 20, 'total_tokens': 30}}).encode())


@pytest.mark.parametrize('status,code', [(422, 'refusal'), (422, 'suspected_stub'),
                                       (409, 'busy'), (504, 'request_timeout')])
def test_role_fallback_declared_outcome_then_one_backup(monkeypatch, status, code):
    cfg = experimental_role_config('analyzer')
    calls, events = [], []
    def send(request, timeout):
        calls.append(json.loads(request.data))
        if len(calls) == 1:
            raise rejected(code, status)
        assert timeout == 180
        return reply({'answer': 42})
    monkeypatch.setattr('runtime.local_inference.request.urlopen', send)
    assert call_json_chat([{'role': 'user', 'content': 'task'}], config=replace(cfg, telemetry_sink=events.append)) == {'answer': 42}
    assert [r['model'] for r in calls] == ['geminivm/pro', 'deepseek/deepseek-chat']
    assert calls[0]['messages'] == calls[1]['messages']
    assert calls[1]['max_tokens'] == 32768
    failed = next(r for r in events if r.get('event') == 'attempt_failed')
    assert failed['reason_code'] == code and failed['attempt_index'] == 0
    assert events[-1]['model'] == 'deepseek-real-model' and events[-1]['fallback_used']
    if code != 'request_timeout':
        assert not llm_failover._COOLDOWNS  # Semantic failure cannot poison other tasks.


@pytest.mark.parametrize('status,code', [(422, 'validation_error'), (422, 'content_filter'),
                                       (422, 'invalid_response_format'),
                                       (403, 'refusal'), (400, 'refusal')])
def test_other_422_and_policy_or_auth_errors_do_not_switch(monkeypatch, status, code):
    calls = []
    def send(*args, **kwargs):
        calls.append(1)
        raise rejected(code, status)
    monkeypatch.setattr('runtime.local_inference.request.urlopen', send)
    with pytest.raises(LocalInferenceError):
        call_json_chat([], config=experimental_role_config('architect'))
    assert len(calls) == 1


def test_refusal_fallback_requires_explicit_opt_in(monkeypatch):
    cfg = replace(experimental_role_config('analyzer'), fallback_on_codes=())
    calls = []
    def send(*args, **kwargs):
        calls.append(1)
        raise rejected()
    monkeypatch.setattr('runtime.local_inference.request.urlopen', send)
    with pytest.raises(LocalInferenceError):
        call_json_chat([], config=cfg)
    assert len(calls) == 1


def test_both_routes_refuse_without_loop_or_global_cooldown(monkeypatch):
    calls = []
    def send(request, timeout):
        calls.append(json.loads(request.data)['model'])
        raise rejected()
    monkeypatch.setattr('runtime.local_inference.request.urlopen', send)
    with pytest.raises(LocalInferenceError):
        call_json_chat([], config=experimental_role_config('spec_writer'))
    assert calls == ['geminivm/pro', 'deepseek/deepseek-chat']
    assert not llm_failover._COOLDOWNS


@pytest.mark.parametrize('codes', ['refusal', [None], ['unknown'], ['refusal', 'refusal']])
def test_invalid_semantic_policy_rejected(tmp_path, codes):
    from runtime.local_inference import load_llm_profiles, LlmProfileError
    path = tmp_path/'profiles.json'
    path.write_text(json.dumps({'schema_version': 'llm_profiles.v1', 'profiles': {
        'p': {'base_url': 'http://gateway/v1', 'model': 'm', 'provider_label': 'p', 'fallback_on_codes': codes}}}))
    with pytest.raises(LlmProfileError):
        load_llm_profiles(str(path))


@pytest.mark.parametrize('role', ['analyzer', 'architect', 'spec_writer'])
def test_role_artifact_reports_answering_model(monkeypatch, role):
    from runtime.role_architect_llm import apply_architect_advisory
    from runtime.spec_writer_candidate_arbiter import arbitrate_candidates
    from runtime.project_deliberation import deliberate_project_report
    calls = []
    values = {'analyzer': {'executive_summary': 'CLI tool', 'capability_decomposition': [],
                          'refactor_plan': [], 'cognitive_loop': {}, 'open_questions': [], 'confidence': 'low'},
              'architect': {'chosen_option_id': '', 'reason': '', 'additional_risks': [], 'summary': 'Bounded'},
              'spec_writer': {'selected_source': 'a.py:a', 'reason': 'Existing target'}}
    def send(request, timeout):
        calls.append(json.loads(request.data)['model'])
        if len(calls) == 1:
            raise rejected()
        return reply(values[role])
    monkeypatch.setattr('runtime.local_inference.request.urlopen', send)
    cfg = experimental_role_config(role)
    if role == 'analyzer':
        result = deliberate_project_report({}, config=replace(cfg, provider_label='external_l4'))
    elif role == 'architect':
        result = apply_architect_advisory({}, config=cfg)['architect_advisory']
    else:
        _, result = arbitrate_candidates([{'source': 'a.py:a', 'score': 80},
                                         {'source': 'b.py:b', 'score': 79}], config=cfg)
    assert result['model'] == 'deepseek-real-model'
    assert result['requested_model'] == 'geminivm/pro'
    assert result['resolved_provider'] == 'deepseek_role_backup'
    assert result['fallback_used'] and result['model_reported']
    assert result['route_failures'] == [{'requested_model': 'geminivm/pro',
                                       'http_status': 422, 'reason_code': 'refusal'}]
