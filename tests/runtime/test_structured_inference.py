"""Reject damaged role documents without losing usage or original response evidence."""
from dataclasses import replace
import hashlib
import io
import json

import pytest

from runtime.local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat
from runtime.structured_inference import parse_document

SCHEMA = {'type': 'object', 'required': ['cases'], 'properties': {
    'cases': {'type': 'array', 'items': {'type': 'object', 'required': ['id'],
                                     'properties': {'id': {'type': 'string'}}}}}}
BROKEN = '{"cases":[{"input":None},{"id":"C2","input":1}]}'


def config(**kwargs):
    return LocalInferenceConfig(base_url='http://test.invalid/v1', model='test',
                                strict_json=True, **kwargs)


def response(text, **extra):
    return io.BytesIO(json.dumps({'model': 'test-v1', 'choices': [{'finish_reason': 'stop',
        'message': {'content': text, 'reasoning_content': 'DO NOT CAPTURE'}}],
        'usage': {'total_tokens': 25}, **extra}).encode())


@pytest.mark.parametrize('text', [BROKEN, '{"a":NaN}', '{"a":Infinity}',
    '{"a":1,"a":2}', '{"x":{"ok":true}', 'prefix {"ok":true}',
    '{"ok":true} trailing', '{"a":1}{"b":2}', '[{"ok":true}]'])
def test_whole_document_never_salvages_nested_objects(text):
    with pytest.raises(LocalInferenceError, match='complete JSON'):
        parse_document(text)


@pytest.mark.parametrize('text', ['{"cases":[]}', '```json\n{"cases":[]}\n```',
                                 '```\n{"cases":[]}\n```'])
def test_exact_document_or_single_fence(text):
    assert parse_document(text, SCHEMA) == {'cases': []}


@pytest.mark.parametrize('text', ['{"id":"C2"}', '{"cases":[{"id":1}]}'])
def test_schema_validates_nested_contract(text):
    with pytest.raises(LocalInferenceError, match='match schema'):
        parse_document(text, SCHEMA)


def test_raw_and_usage_survive_rejected_response_without_ordinary_metric_leak(monkeypatch):
    events, evidence = [], []
    monkeypatch.setattr('runtime.local_inference.request.urlopen', lambda *a, **k: response(BROKEN))
    with pytest.raises(LocalInferenceError) as error:
        call_json_chat([], config=config(telemetry_sink=events.append, raw_response_sink=evidence.append))
    assert evidence[0]['content'] == BROKEN
    assert evidence[0]['content_sha256'] == hashlib.sha256(BROKEN.encode()).hexdigest()
    assert error.value.response_evidence == evidence[0]
    assert events[0]['total_tokens'] == 25
    assert BROKEN not in str(events) and 'DO NOT CAPTURE' not in str(evidence)


def test_schema_implies_strict_even_without_flag_and_native_format_is_exact(monkeypatch):
    seen = []
    wire = {'type': 'json_schema', 'schema': SCHEMA}
    def send(req, **kwargs):
        seen.append(json.loads(req.data))
        return response('{"id":"C2"}')
    monkeypatch.setattr('runtime.local_inference.request.urlopen', send)
    with pytest.raises(LocalInferenceError, match='match schema'):
        call_json_chat([], config=replace(config(), strict_json=False, response_schema=SCHEMA, response_format=wire))
    assert seen[0]['response_format'] == wire


def test_capture_failure_cannot_deliver_success(monkeypatch):
    monkeypatch.setattr('runtime.local_inference.request.urlopen', lambda *a, **k: response('{"ok":true}'))
    def fail(record):
        raise OSError('disk unavailable')
    with pytest.raises(LocalInferenceError, match='could not be saved'):
        call_json_chat([], config=config(raw_response_sink=fail))


def test_oversize_evidence_is_bounded_and_not_accepted(monkeypatch):
    evidence = []
    content = '{"text":"абвгд"}'
    monkeypatch.setattr('runtime.local_inference.request.urlopen', lambda *a, **k: response(content))
    with pytest.raises(LocalInferenceError, match='evidence limit'):
        call_json_chat([], config=config(raw_response_sink=evidence.append, raw_response_limit_bytes=11))
    assert evidence[0]['truncated'] and len(evidence[0]['content'].encode()) <= 11
    assert evidence[0]['content_sha256'] == hashlib.sha256(content.encode()).hexdigest()


def test_invalid_schema_fails_before_network(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail('network must not be reached')
    monkeypatch.setattr('runtime.local_inference.request.urlopen', unexpected)
    for schema in [{'type':'invalid'}, {'$ref':'https://invalid.test/schema'}]:
        with pytest.raises(LocalInferenceError, match='invalid response schema'):
            call_json_chat([], config=config(response_schema=schema))


def test_budget_persists_raw_before_parse_and_settles_known_usage(tmp_path, monkeypatch):
    from runtime.budgeted_chat import BudgetedChat
    from runtime.claim_suite_budget import create_budget, request_slot
    slot = request_slot('test', max_input_bytes=1000, max_output_tokens=100)
    path = tmp_path/'budget.json'
    create_budget(path, [slot])
    persisted = []
    monkeypatch.setattr('runtime.local_inference.request.urlopen', lambda *a, **k: response(BROKEN))
    chat = BudgetedChat(path, [slot], persist=persisted.append)
    with pytest.raises(LocalInferenceError):
        chat([], config=config(max_output_tokens=100))
    assert any(r[0]['status']=='started' and r[0].get('response_evidence') for r in persisted)
    assert chat.attempts[0]['response_evidence'][0]['content'] == BROKEN
    assert chat.attempts[0]['usage_known']
    assert json.loads(path.read_text())['jobs'][slot['digest']]['state'] == 'done'


def test_failover_retains_local_contract_and_evidence_but_uses_route_wire_format(monkeypatch):
    from urllib.error import HTTPError
    from runtime.llm_failover import _COOLDOWNS
    _COOLDOWNS.clear()
    seen, evidence = [], []
    def send(req, **kwargs):
        seen.append(json.loads(req.data))
        if len(seen) == 1:
            raise HTTPError(req.full_url, 503, 'Unavailable', {}, io.BytesIO(b'{}'))
        return response(BROKEN)
    monkeypatch.setattr('runtime.local_inference.request.urlopen', send)
    backup = LocalInferenceConfig(base_url='http://backup.invalid', model='backup', response_format=False)
    with pytest.raises(LocalInferenceError, match='complete JSON'):
        call_json_chat([], config=config(fallbacks=(backup,), raw_response_sink=evidence.append,
            response_schema=SCHEMA, response_format={'type':'json_schema','schema':SCHEMA}))
    assert len(seen) == 2 and 'response_format' not in seen[1]
    assert evidence[0]['requested_model'] == 'backup' and evidence[0]['content'] == BROKEN
    _COOLDOWNS.clear()


def test_role_trace_keeps_evidence_on_corresponding_usage_record(monkeypatch):
    from runtime.role_inference import traced_role_config
    events = []
    monkeypatch.setattr('runtime.local_inference.request.urlopen', lambda *a, **k: response(BROKEN))
    cfg = traced_role_config('spec_writer', replace(config(), strict_json=False), events)
    with pytest.raises(LocalInferenceError):
        call_json_chat([], config=cfg)
    assert len(events) == 1 and events[0]['response_evidence']['content'] == BROKEN


def test_native_schema_counts_against_input_reservation(tmp_path):
    from runtime.budgeted_chat import BudgetedChat
    from runtime.claim_suite_budget import create_budget, request_slot
    slot = request_slot('test', max_input_bytes=50, max_output_tokens=100)
    path = tmp_path/'budget.json'
    create_budget(path, [slot])
    chat = BudgetedChat(path, [slot], chat=lambda *a, **k: pytest.fail('must not call'))
    with pytest.raises(ValueError, match='bounds_exceeded'):
        chat([], config=config(max_output_tokens=100, response_format={'type':'json_schema','schema':SCHEMA}))
    assert json.loads(path.read_text())['jobs'][slot['digest']]['state'] == 'ready'


@pytest.mark.parametrize('consumer', ['architect', 'spec_writer'])
@pytest.mark.parametrize('text', [BROKEN, '{"id":"C2"}'])
def test_real_role_consumers_reject_bad_documents_without_format_retry(monkeypatch, consumer, text):
    calls = []
    def send(*args, **kwargs):
        calls.append(1)
        return response(text)
    monkeypatch.setattr('runtime.local_inference.request.urlopen', send)
    cfg = replace(config(), strict_json=False)
    if consumer == 'architect':
        from runtime.role_architect_llm import apply_architect_advisory
        result = apply_architect_advisory({}, config=cfg)['architect_advisory']
    else:
        from runtime.spec_writer_candidate_arbiter import arbitrate_candidates
        rows = [{'source':'a.py:f','score':90,'semantic_score':85},
                {'source':'b.py:g','score':86,'semantic_score':82}]
        _, result = arbitrate_candidates(rows, config=cfg)
    assert result['source'] == 'deterministic_fallback'
    assert 'structured response' in result['error']
    assert calls == [1]
