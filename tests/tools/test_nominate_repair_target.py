"""CLI persists bounded advisory model IO and does not grant patch authority."""
import json
import sys
from pathlib import Path

import pytest

from tools import nominate_repair_target as cli
from runtime.local_inference import LocalInferenceConfig, LocalInferenceError


def arguments(tmp_path, monkeypatch, *, request=False):
    project = tmp_path / 'project'
    project.mkdir()
    packet = tmp_path / 'packet.json'
    packet.write_text('{"packet_digest":"observation"}', encoding='utf-8')
    work = tmp_path / 'work'
    args = ['nominate', '--project', str(project), '--packet', str(packet), '--work-dir', str(work),
            '--authorize-native-trace']
    if request:
        args.append('--request-model')
    monkeypatch.setattr(sys, 'argv', args)
    monkeypatch.setattr(cli, 'trace_failure_methods', lambda **kw: {'status': 'observed_call_scope'})
    monkeypatch.setattr(cli, 'nomination_context', lambda **kw: {'context_digest': 'context'})
    return work


def test_default_is_context_only_without_model_call(tmp_path, monkeypatch):
    work = arguments(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, 'call_json_chat', lambda *a, **kw: pytest.fail('unexpected model call'))
    assert cli.main() == 0
    result = json.loads((work / 'result.json').read_text())
    assert result['status'] == 'context_ready'
    assert result['logical_model_calls'] == 0
    assert result['execution_authorized'] is False


def test_failed_trace_prevents_model_request(tmp_path, monkeypatch):
    work = arguments(tmp_path, monkeypatch, request=True)

    def blocked(**kw):
        raise ValueError('invalid_or_stale_trace')

    monkeypatch.setattr(cli, 'nomination_context', blocked)
    monkeypatch.setattr(cli, 'call_json_chat', lambda *a, **kw: pytest.fail('unexpected model call'))
    assert cli.main() == 1
    result = json.loads((work / 'result.json').read_text())
    assert result['logical_model_calls'] == 0
    assert result['reason'] == 'invalid_or_stale_trace'


@pytest.mark.parametrize('failure', ['provider', 'invalid_response', 'none'])
def test_one_model_call_preserved_without_retry(tmp_path, monkeypatch, failure):
    work = arguments(tmp_path, monkeypatch, request=True)
    config = LocalInferenceConfig(base_url='http://example.invalid', model='test')
    monkeypatch.setattr(cli.LocalInferenceConfig, 'from_l45_env', lambda: config)
    calls = []

    def call(messages, *, config):
        calls.append(messages)
        assert config.max_output_tokens == 1200
        if failure == 'provider':
            raise LocalInferenceError('provider_unavailable')
        return {'target': 'core.py:Worker.inner'}

    def validate(payload, **kw):
        if failure == 'invalid_response':
            raise ValueError('nomination_response_schema')
        return {'status': 'advisory_nomination', 'execution_authorized': False}

    monkeypatch.setattr(cli, 'call_json_chat', call)
    monkeypatch.setattr(cli, 'validate_nomination', validate)
    assert cli.main() == int(failure != 'none')
    assert len(calls) == 1
    result = json.loads((work / 'result.json').read_text())
    assert result['logical_model_calls'] == 1
    assert result['source_apply'] is result['execution_authorized'] is False
    assert (work / 'request.json').is_file()
    assert (work / 'response.json').is_file() == (failure != 'provider')


def test_existing_receipt_cannot_be_overwritten(tmp_path, monkeypatch):
    work = arguments(tmp_path, monkeypatch)
    work.mkdir()
    receipt = work / 'result.json'
    receipt.write_text('prior evidence', encoding='utf-8')
    with pytest.raises(FileExistsError):
        cli.main()
    assert receipt.read_text() == 'prior evidence'
