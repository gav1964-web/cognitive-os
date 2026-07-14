from __future__ import annotations

import json
from unittest.mock import patch

from runtime.local_inference import LocalInferenceConfig, _loads_json_object, call_json_chat


class _FakeResponse:
    def __init__(self, payload=None):
        self.payload = payload or {"choices": [{"message": {"content": "{\"action\":\"STOP\"}"}}]}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_local_inference_openai_like_json_call():
    with patch("runtime.local_inference.request.urlopen", return_value=_FakeResponse()):
        result = call_json_chat(
            [{"role": "user", "content": "{}"}],
            config=LocalInferenceConfig(base_url="http://127.0.0.1:8000/v1", model="local-test"),
        )

    assert result == {"action": "STOP"}


def test_local_inference_extracts_json_from_text_response():
    assert _loads_json_object("```json\n{\"ok\": true}\n```") == {"ok": True}


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
            "model": "GigaChat-Pro",
            "choices": [{"message": {"content": '{"ok": true}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
        }
    )
    config = LocalInferenceConfig(
        base_url="http://127.0.0.1:8000/v1",
        model="GigaChat-Pro",
        provider_label="external_l4",
        telemetry_sink=records.append,
    )

    with patch("runtime.local_inference.request.urlopen", return_value=response):
        assert call_json_chat([{"role": "user", "content": "secret prompt"}], config=config) == {"ok": True}

    assert records[0]["total_tokens"] == 14
    assert records[0]["model"] == "GigaChat-Pro"
    assert "secret prompt" not in str(records)
