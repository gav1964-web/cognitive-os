from __future__ import annotations

import json
import pytest
from unittest.mock import patch

from runtime.local_inference import LocalInferenceConfig, _loads_json_object, call_json_chat, load_llm_profiles
from runtime.local_inference import LocalInferenceError


class _FakeResponse:
    def __init__(self, payload=None):
        self.payload = payload or {"choices": [{"message": {"content": "{\"action\":\"STOP\"}"}}]}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_output_budget_is_explicit_and_truncated_nested_json_is_rejected():
    response = _FakeResponse({'choices': [{'finish_reason': 'length',
        'message': {'content': '{"groups": [{"module": "partial"}]'}}]})
    with patch('runtime.local_inference.request.urlopen', return_value=response) as mocked:
        with pytest.raises(LocalInferenceError, match='truncated'):
            call_json_chat([], config=LocalInferenceConfig(base_url='http://localhost', model='test',
                                                          max_output_tokens=2400))
    assert json.loads(mocked.call_args.args[0].data)['max_tokens'] == 2400


@pytest.mark.parametrize('content,finish,state,error', [
    ('', 'stop', 'empty', 'empty final content'),
    ('   ', 'length', 'empty', 'truncated'),
    (None, 'stop', 'missing', 'empty final content'),
    ('{"ok":true}', 'length', 'present', 'truncated'),
])
def test_final_content_failure_retains_finish_and_usage(content, finish, state, error):
    records = []
    response = _FakeResponse({'choices': [{'finish_reason': finish, 'message': {
        'content': content, 'reasoning_content': 'private reasoning'}}], 'usage': {'total_tokens': 40}})
    with patch('runtime.local_inference.request.urlopen', return_value=response) as transport:
        with pytest.raises(LocalInferenceError, match=error):
            call_json_chat([], config=LocalInferenceConfig(base_url='http://example.invalid', model='test',
                                                          telemetry_sink=records.append))
    assert transport.call_count == 1
    assert records[0]['finish_reason'] == finish and records[0]['final_content_state'] == state
    assert records[0]['total_tokens'] == 40 and 'private reasoning' not in str(records)


@pytest.mark.parametrize('response', [{'choices': None}, {'choices': ['invalid']}, ['invalid']])
def test_malformed_provider_envelope_raises_a_controlled_error(response):
    with patch('runtime.local_inference.request.urlopen', return_value=_FakeResponse(response)):
        with pytest.raises(LocalInferenceError):
            call_json_chat([], config=LocalInferenceConfig(base_url='http://localhost', model='test',
                                                          telemetry_sink=lambda _: None))


def test_local_inference_openai_like_json_call():
    with patch("runtime.local_inference.request.urlopen", return_value=_FakeResponse()):
        result = call_json_chat(
            [{"role": "user", "content": "{}"}],
            config=LocalInferenceConfig(base_url="http://127.0.0.1:8000/v1", model="local-test"),
        )

    assert result == {"action": "STOP"}


def test_local_inference_extracts_json_from_text_response():
    assert _loads_json_object("```json\n{\"ok\": true}\n```") == {"ok": True}


def test_local_inference_skips_non_json_reasoning_braces():
    content = "Reasoning uses {not json} first.\n```json\n{\"ok\": true}\n```"

    assert _loads_json_object(content) == {"ok": True}


def test_local_inference_can_disable_response_format():
    with patch("runtime.local_inference.request.urlopen", return_value=_FakeResponse()) as mocked:
        call_json_chat(
            [{"role": "user", "content": "{}"}],
            config=LocalInferenceConfig(
                base_url="http://127.0.0.1:8000/v1",
                model="local-test",
                response_format=False,
            ),
        )

    body = json.loads(mocked.call_args.args[0].data.decode("utf-8"))
    assert "response_format" not in body


def test_local_inference_adds_bearer_token_when_configured():
    with patch("runtime.local_inference.request.urlopen", return_value=_FakeResponse()) as mocked:
        call_json_chat(
            [{"role": "user", "content": "{}"}],
            config=LocalInferenceConfig(
                base_url="https://provider.example/v1",
                model="cortex",
                api_key="secret-token",
                provider_label="external_l4",
            ),
        )

    assert mocked.call_args.args[0].headers["Authorization"] == "Bearer secret-token"


def test_local_inference_emits_usage_telemetry_without_prompt_content():
    records = []
    response = _FakeResponse(
        {
            "model": "deepseek/deepseek-chat",
            "choices": [{"message": {"content": '{"ok": true}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
        }
    )
    config = LocalInferenceConfig(
        base_url="http://127.0.0.1:8000/v1",
        model="deepseek/deepseek-chat",
        provider_label="external_l4",
        telemetry_sink=records.append,
    )

    with patch("runtime.local_inference.request.urlopen", return_value=response):
        assert call_json_chat([{"role": "user", "content": "secret prompt"}], config=config) == {"ok": True}

    assert records[0]["total_tokens"] == 14
    assert records[0]["model"] == "deepseek/deepseek-chat"
    assert "secret prompt" not in str(records)


def test_l45_inference_defaults_to_deepseek_profile(monkeypatch):
    monkeypatch.delenv("COGNITIVE_OS_L45_BASE_URL", raising=False)
    monkeypatch.delenv("COGNITIVE_OS_L45_MODEL", raising=False)
    monkeypatch.delenv("COGNITIVE_OS_L45_TIMEOUT", raising=False)
    monkeypatch.delenv("COGNITIVE_OS_L45_RESPONSE_FORMAT", raising=False)
    monkeypatch.delenv("COGNITIVE_OS_L45_API_KEY", raising=False)
    monkeypatch.delenv("COGNITIVE_OS_L45_API_KEY_ENV", raising=False)

    config = LocalInferenceConfig.from_l45_env()

    assert config.base_url == "http://127.0.0.1:8000/v1"
    assert config.model == "deepseek/deepseek-chat"
    assert config.timeout_seconds == 60
    assert config.response_format is True
    assert config.provider_label == "external_l45_intent_resolver"


def test_llm_profiles_config_declares_active_defaults():
    profiles = load_llm_profiles()["profiles"]

    assert profiles["local_l35"]["model"] == "local"
    assert profiles["external_l45_intent_resolver"]["model"] == "deepseek/deepseek-chat"


def test_l45_model_env_overrides_config_profile(monkeypatch):
    monkeypatch.setenv("COGNITIVE_OS_L45_MODEL", "provider/custom-model")

    assert LocalInferenceConfig.from_l45_env().model == "provider/custom-model"
