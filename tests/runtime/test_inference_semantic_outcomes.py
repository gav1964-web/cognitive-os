"""Provider outcomes take precedence over HTTP success and parseable content."""
import io
import json
from urllib.error import HTTPError

import pytest

from runtime.inference_failure_evidence import completion_failure, failure_evidence
from runtime.local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat


@pytest.mark.parametrize('status', ['refusal', 'suspected_stub', 'service_error', 'empty', 'invalid_response_format'])
@pytest.mark.parametrize('http_status', [200, 422])
def test_declared_failure_cannot_become_json_success(monkeypatch, status, http_status):
    telemetry, calls = [], []
    payload = {'model': 'pro', 'choices': [{'message': {'content': '{"approved":true}'}}],
               'provider_diagnostics': {'response_status': status, 'browser_model': 'Pro',
                                        'run_id': 'semantic-test', 'resolved_model': 'pro'},
               'usage': {'prompt_tokens': 5, 'completion_tokens': 2, 'total_tokens': 7}}
    if http_status != 200:
        payload['error'] = {'code': status, 'provider': 'test'}
    def send(*args, **kwargs):
        calls.append(1)
        body = io.BytesIO(json.dumps(payload).encode())
        if http_status != 200:
            raise HTTPError('http://offline.invalid', http_status, 'semantic outcome', {}, body)
        return body
    monkeypatch.setattr('runtime.local_inference.request.urlopen', send)
    monkeypatch.setattr('runtime.local_inference._loads_json_object',
                        lambda *args: pytest.fail('Must stop before parsing response content'))
    config = LocalInferenceConfig('http://offline.invalid/v1', 'primary',
        telemetry_sink=telemetry.append, fallbacks=(LocalInferenceConfig('http://unused.invalid', 'backup'),))
    with pytest.raises(LocalInferenceError) as caught:
        call_json_chat([{'role': 'user', 'content': 'task'}], config=config)
    assert calls == [1]
    evidence = failure_evidence(caught.value)
    assert evidence['http_status'] == http_status
    assert evidence['quality_evaluation'] == 'not_evaluated'
    assert evidence['provider_failure']['code'] == status
    assert evidence['provider_failure']['diagnostics']['resolved_model'] == 'pro'
    assert telemetry[0]['quality_evaluation'] == 'not_evaluated'
    if http_status == 200:
        assert telemetry[0]['total_tokens'] == 7  # Usage survives semantic rejection.


@pytest.mark.parametrize('details', [None, {}, {'response_status': 'normal'},
                                    {'response_status': []}, {'response_status': 'refusal\nsecret'}])
def test_only_explicit_known_outcomes_are_interpreted(details):
    assert completion_failure({'provider_diagnostics': details}) == {}


def test_ordinary_response_may_discuss_rejection(monkeypatch):
    payload = {'choices': [{'message': {'content': '{"explanation":"refusal suspected_stub"}'}}],
               'provider_diagnostics': {'response_status': 'normal'}}
    monkeypatch.setattr('runtime.local_inference.request.urlopen',
                        lambda *a, **k: io.BytesIO(json.dumps(payload).encode()))
    assert call_json_chat([], config=LocalInferenceConfig('http://offline.invalid', 'model')) == {
        'explanation': 'refusal suspected_stub'}
