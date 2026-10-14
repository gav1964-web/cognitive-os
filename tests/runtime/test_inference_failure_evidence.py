import io
import json
from urllib.error import HTTPError

import pytest

from runtime.local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat
from runtime.development_regression_cycle import run_regression_cycle


def test_http_diagnostics_survive_without_raw_error_text(monkeypatch):
    payload = {'error': {'code': 'service_error', 'provider': 'geminivm', 'message': 'secret prompt'},
               'provider_diagnostics': {'run_id': 'run-123', 'retry_count': 0,
                   'transport_status': 'ok', 'browser_model': '3.1 Pro', 'secret': 'credential',
                   'requested_model': 'geminivm/gemini-web', 'resolved_model': 'pro'}}
    def send(*args, **kwargs):
        raise HTTPError('http://gateway', 502, 'error', {}, io.BytesIO(json.dumps(payload).encode()))
    monkeypatch.setattr('runtime.local_inference.request.urlopen', send)
    telemetry = []
    config = LocalInferenceConfig('http://gateway/v1', 'gemini-web', telemetry_sink=telemetry.append)
    with pytest.raises(LocalInferenceError) as caught:
        call_json_chat([{'role': 'user', 'content': 'task'}], config=config)
    assert caught.value.provider_failure['diagnostics']['run_id'] == 'run-123'
    assert caught.value.provider_failure['diagnostics']['requested_model'] == 'geminivm/gemini-web'
    assert caught.value.provider_failure['diagnostics']['resolved_model'] == 'pro'
    assert telemetry[0]['provider_failure'] == caught.value.provider_failure
    assert telemetry[0]['quality_evaluation'] == 'not_evaluated'
    assert not telemetry[0]['usage_reported']
    assert 'secret' not in str(telemetry) and 'credential' not in str(telemetry)


@pytest.mark.parametrize('invalid', [None, {}, [], 42, '', 'x' * 129,
                                    'pro\nsecret', 'pro secret', 'pro?key=secret'])
def test_untrusted_model_diagnostics_are_bounded(invalid):
    from runtime.inference_failure_evidence import safe_metadata
    result = safe_metadata({'error': {'code': 'service_error'},
        'provider_diagnostics': {'requested_model': invalid, 'resolved_model': invalid,
                                 'browser_model': 'Flash', 'prompt': 'secret'}})
    assert result == {'code': 'service_error', 'diagnostics': {'browser_model': 'Flash'}}


@pytest.mark.parametrize('http_status,code', [(502, 'service_error'), (422, 'refusal'),
                                             (422, 'suspected_stub'), (200, 'refusal'),
                                             (504, 'request_timeout')])
def test_provider_outage_preserves_task_and_does_not_retry_or_grade(tmp_path, monkeypatch, http_status, code):
    project = tmp_path/'project'
    project.mkdir()
    (project/'main.py').write_text('answer = 42\n')
    config = LocalInferenceConfig('http://gateway/v1', 'model')
    calls = []
    def chat(*args, **kwargs):
        calls.append(1)
        error = LocalInferenceError('provider failed')
        error.http_status = http_status
        error.provider_failure = {'code': code}
        raise error
    def run(**kwargs):
        try:
            kwargs['model_chat']([{'role': 'user', 'content': 'frozen request'}], config=config)
        except LocalInferenceError:
            return {'status': 'controlled_stop'}
    monkeypatch.setattr('runtime.development_regression_cycle.run_project_development', run)
    report = run_regression_cycle(root=tmp_path, project_dir=project, goal='repair',
        task_contract={'id': 'task-1'}, chain_case={}, policy={}, config=config, chat=chat,
        work_dir=tmp_path/'artifacts/cycle', max_attempts=3, authorized=True)
    assert calls == [1]
    assert report['reason'] == 'provider_unavailable'
    assert report['quality_evaluation'] == 'not_evaluated'
    assert report['provider_failure']['provider_failure']['code'] == code
    assert report['source_unchanged']
    pending = json.loads((tmp_path/'artifacts/cycle/pending-inference.json').read_text())
    assert pending['messages'][0]['content'] == 'frozen request'
    assert pending['source_inventory_digest'] == report['source_inventory_digest']
