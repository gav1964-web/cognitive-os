import io
import json
from dataclasses import replace
from urllib.error import HTTPError, URLError
from unittest.mock import patch

import pytest

from runtime import llm_failover
from runtime.local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat


@pytest.fixture(autouse=True)
def clear_circuits():
    llm_failover._COOLDOWNS.clear()
    yield
    llm_failover._COOLDOWNS.clear()


def config(records):
    backup = LocalInferenceConfig('http://gateway/v1', 'GigaChat-Pro', api_key='backup-secret', response_format=False)
    return LocalInferenceConfig('http://gateway/v1', 'DeepSeek', api_key='primary-secret',
                                fallbacks=(backup,), telemetry_sink=records.append, max_output_tokens=2400)


def response(content='{"ok":true}'):
    return io.BytesIO(json.dumps({'model': 'GigaChat-Pro', 'choices': [
        {'message': {'content': content}}], 'usage': {'total_tokens': 12}}).encode())


def failure(code):
    return HTTPError('http://gateway', code, 'failure', {'Retry-After': '30'}, io.BytesIO(b'echoed secret'))


@pytest.mark.parametrize('code', [402, 408, 429, 500, 502, 503, 504])
def test_transient_or_quota_failure_switches_with_separate_credentials_and_telemetry(code):
    records = []
    cfg = config(records)
    with patch('runtime.local_inference.request.urlopen', side_effect=[failure(code), response()]) as transport:
        assert call_json_chat([{'role': 'user', 'content': 'private input'}], config=cfg) == {'ok': True}
    first, second = [row.args[0] for row in transport.call_args_list]
    assert first.headers['Authorization'] == 'Bearer primary-secret'
    assert second.headers['Authorization'] == 'Bearer backup-secret'
    payload = json.loads(second.data)
    assert payload['model'] == 'GigaChat-Pro' and payload['max_tokens'] == 2400
    assert 'response_format' not in payload
    assert records[0]['http_status'] == code
    assert records[-1]['model'] == 'GigaChat-Pro' and records[-1]['fallback_used'] is True
    assert all(secret not in str(records) for secret in ('private input', 'primary-secret', 'backup-secret', 'echoed secret'))


@pytest.mark.parametrize('code', [400, 401, 403, 404, 422])
def test_configuration_and_auth_errors_do_not_switch(code):
    records = []
    with patch('runtime.local_inference.request.urlopen', side_effect=failure(code)) as transport:
        with pytest.raises(LocalInferenceError) as raised:
            call_json_chat([], config=config(records))
    assert transport.call_count == 1
    assert 'echoed secret' not in str(raised.value)


def test_network_failure_switches_but_invalid_json_does_not():
    with patch('runtime.local_inference.request.urlopen', side_effect=[URLError('secret host'), response()]):
        assert call_json_chat([], config=config([])) == {'ok': True}
    llm_failover._COOLDOWNS.clear()
    with patch('runtime.local_inference.request.urlopen', return_value=response('bad content')) as transport:
        with pytest.raises(LocalInferenceError):
            call_json_chat([], config=config([]))
        assert transport.call_count == 1


def test_cooldown_skips_primary_then_restores_it_without_sleeping():
    cfg = config([])
    with patch('runtime.llm_failover.time.monotonic', return_value=100):
        with patch('runtime.local_inference.request.urlopen', side_effect=[failure(429), response()]):
            call_json_chat([], config=cfg)
    with patch('runtime.llm_failover.time.monotonic', return_value=120):
        with patch('runtime.local_inference.request.urlopen', return_value=response()) as transport:
            call_json_chat([], config=cfg)
            assert json.loads(transport.call_args.args[0].data)['model'] == 'GigaChat-Pro'
    with patch('runtime.llm_failover.time.monotonic', return_value=161):
        with patch('runtime.local_inference.request.urlopen', return_value=response()) as transport:
            call_json_chat([], config=cfg)
            assert json.loads(transport.call_args.args[0].data)['model'] == 'DeepSeek'


def test_all_routes_fail_once_and_do_not_loop_or_retry_during_cooldown():
    cfg = config([])
    with patch('runtime.local_inference.request.urlopen', side_effect=[failure(402), failure(429)]) as transport:
        with pytest.raises(LocalInferenceError):
            call_json_chat([], config=cfg)
        with pytest.raises(LocalInferenceError, match='cooling down'):
            call_json_chat([], config=cfg)
        assert transport.call_count == 2


def test_explicit_single_route_never_uses_default_fallback():
    with patch('runtime.local_inference.request.urlopen', side_effect=failure(429)) as transport:
        with pytest.raises(LocalInferenceError):
            call_json_chat([], config=replace(config([]), fallbacks=()))
        assert transport.call_count == 1


def test_profile_configures_discovered_gateway_model():
    cfg = LocalInferenceConfig.from_l45_env()
    assert [route.model for route in cfg.fallbacks] == ['GigaChat-Pro']
    assert cfg.fallbacks[0].response_format is False


@pytest.mark.parametrize('value,expected', [('15', 15), ('-5', 0), ('NaN', 0), ('bad', 0), ('999999', 86400)])
def test_retry_after_is_bounded(value, expected):
    assert llm_failover.retry_after(value) == expected


@pytest.mark.parametrize('names', [['missing'], ['primary'], ['backup', 'backup'], [123]])
def test_invalid_fallback_graph_fails_during_profile_loading(tmp_path, names):
    from runtime.local_inference import load_llm_profiles, LlmProfileError
    path = tmp_path / 'profiles.json'
    profile = {'base_url': 'http://gateway/v1', 'model': 'test', 'provider_label': 'test'}
    path.write_text(json.dumps({'schema_version': 'llm_profiles.v1', 'profiles': {
        'primary': {**profile, 'fallback_profiles': names}, 'backup': profile}}))
    with pytest.raises(LlmProfileError):
        load_llm_profiles(str(path))
