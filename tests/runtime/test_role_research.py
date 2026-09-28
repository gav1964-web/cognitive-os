from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path

import pytest

from runtime.inference_web_evidence import checked_web_evidence
from runtime.local_inference import LocalInferenceConfig, call_json_chat
from runtime.role_inference import prepare_role_research
from runtime.role_research import research_question, validate_request, persist_research
from runtime.research_source_fetch import checked_url, public_address

ROOT = Path(__file__).resolve().parents[2]
URL = 'https://docs.python.org/3.13/library/tomllib.html'
QUOTE = 'The first argument should be a readable and binary file object.'


def request():
    return {'question': 'What input does tomllib.load accept?', 'role': 'analyzer',
            'owner': 'project_description', 'allowed_domains': ['docs.python.org'],
            'applicability': {'technology': 'Python', 'version': '3.13',
                              'url_prefix': 'https://docs.python.org/3.13/'}}


def config():
    return LocalInferenceConfig(base_url='http://example.invalid', model='fixture')


def answer(url=URL, quote=QUOTE):
    return {'claims': [{'statement': 'Use a binary file object.', 'url': url, 'quote': quote}], 'unknowns': []}


def source(url, domains):
    return {'url': url, 'final_url': url, 'text': QUOTE, 'sha256': 'a' * 64}


def test_source_is_fetched_quote_checked_and_not_automatically_admitted():
    result = research_question(request(), config=config(), root=ROOT,
                               chat=lambda *a, **k: answer(), fetch=source)
    assert result['status'] == 'evidence_checked'
    assert result['checked_claims'][0]['quote_verified']
    assert result['checked_claims'][0]['semantic_entailment'] == 'not_verified'
    assert result['admission'] == 'pending_owner_review' and result['search_usage'] == 'unknown'


@pytest.mark.parametrize('url,quote', [
    ('https://docs.python.org/3.12/library/tomllib.html', QUOTE),
    ('https://other.example/reference', QUOTE),
    (URL, 'The model invented this quotation completely.')])
def test_unverified_and_wrong_version_claims_are_not_handed_to_roles(url, quote):
    result = research_question(request(), config=config(), root=ROOT,
        chat=lambda *a, **k: answer(url, quote), fetch=source)
    assert result['status'] == 'unresolved' and not result['checked_claims']
    assert result['rejected_claims']


def test_redirect_cannot_silently_switch_documentation_version():
    def redirect(url, domains):
        return {**source(url, domains), 'final_url': url.replace('/3.13/', '/3.14/')}
    result = research_question(request(), config=config(), root=ROOT,
                               chat=lambda *a, **k: answer(), fetch=redirect)
    assert result['rejected_claims'][0]['reason'] == 'research_redirect_changed_version'


@pytest.mark.parametrize('url', ['http://docs.python.org/', 'https://127.0.0.1/',
    'https://docs.python.org@127.0.0.1/', 'https://docs.python.org.evil.example/',
    'https://docs.python.org:8002/', 'https://docs.python.org/3.13/%2e%2e/3.12/'])
def test_only_exact_public_https_domains_are_allowed(url):
    with pytest.raises(ValueError):
        checked_url(url, ['docs.python.org'])


def test_private_dns_target_is_rejected(monkeypatch):
    monkeypatch.setattr('runtime.research_source_fetch.socket.getaddrinfo',
        lambda *a, **k: [(2, 1, 6, '', ('127.0.0.1', 443))])
    with pytest.raises(ValueError, match='not_public'):
        public_address('docs.python.org')


def test_invalid_owner_is_rejected_before_model_call():
    data = request()
    data['owner'] = '../outside'
    with pytest.raises(ValueError, match='owner'):
        validate_request(data, ROOT)


def test_all_routes_are_checked_before_any_research_call(monkeypatch):
    other = request()
    other['role'] = 'architect'
    def forbidden(*args, **kwargs):
        pytest.fail('Invalid batch must not spend a model call')
    monkeypatch.setattr('runtime.role_research.research_question', forbidden)
    with pytest.raises(ValueError, match='enabled_role_model'):
        prepare_role_research([request(), other], {'analyzer': config(), 'architect': None}, ROOT)


def test_gateway_evidence_reaches_cos_without_changing_model_json(monkeypatch):
    text = json.dumps(answer())
    evidence = {'schema_version': 'web_evidence.v1', 'capture_status': 'captured',
        'response_sha256': hashlib.sha256(text.encode()).hexdigest(), 'search_usage': 'unknown',
        'sources': [{'url': URL, 'title': 'Python', 'origin': 'response_link'}]}
    payload = {'choices': [{'message': {'content': text}, 'finish_reason': 'stop'}],
               'provider_diagnostics': {'web_evidence': evidence, 'run_id': 'run-evidence', 'browser_model': 'Pro'}}
    monkeypatch.setattr('runtime.local_inference.request.urlopen',
        lambda *a, **k: io.BytesIO(json.dumps(payload).encode()))
    events = []
    from dataclasses import replace
    result = call_json_chat([], config=replace(config(), telemetry_sink=events.append))
    assert result == answer()
    assert events[0]['web_evidence']['sources'][0]['url'] == URL
    assert events[0]['total_tokens'] is None
    assert events[0]['provider_diagnostics']['run_id'] == 'run-evidence'
    assert checked_web_evidence(evidence, 'different answer') is None


def test_checked_context_is_scoped_to_the_requested_role(monkeypatch, tmp_path):
    result = research_question(request(), config=config(), root=ROOT,
                               chat=lambda *a, **k: answer(), fetch=source)
    monkeypatch.setattr('runtime.role_research.research_question', lambda *a, **k: deepcopy(result))
    monkeypatch.setattr('runtime.role_research.persist_research', lambda *a: 'artifacts/owner/receipt.json')
    configs = {role: config() for role in ('analyzer', 'architect', 'spec_writer')}
    results = prepare_role_research([request()], configs, ROOT)
    assert configs['analyzer'].advisory_context['external_research']['owner'] == 'project_description'
    assert configs['architect'].advisory_context is None
    assert configs['spec_writer'].advisory_context is None
    path = persist_research(results[0], tmp_path)
    assert path.startswith('artifacts/research/project_description/')
    assert json.loads((tmp_path / path).read_text())['admission'] == 'pending_owner_review'


def test_gap_plan_requires_explicit_matching_request(monkeypatch):
    from runtime.research_loop import build_knowledge_gap_packet, build_research_plan, execute_research_plan
    data = request()
    gap = build_knowledge_gap_packet(question=data['question'], needed_for='test', role='analyzer',
        reason='missing API fact', acceptable_sources=['model_web_research'])
    plan = build_research_plan(gap)
    assert plan['steps'][0]['execute_by_default'] is False
    assert execute_research_plan(gap, plan)['status'] == 'not_executed'
    result = research_question(data, config=config(), root=ROOT,
                               chat=lambda *a, **k: answer(), fetch=source)
    monkeypatch.setattr('runtime.role_research.research_question', lambda *a, **k: deepcopy(result))
    monkeypatch.setattr('runtime.role_research.persist_research', lambda *a: 'artifacts/receipt.json')
    assert execute_research_plan(gap, plan, model_research_request=data,
        model_config=config(), root=ROOT)['status'] == 'evidence_checked'
    invalid = {**data, 'question': 'unrelated question'}
    with pytest.raises(ValueError, match='does_not_match_gap'):
        execute_research_plan(gap, plan, model_research_request=invalid, model_config=config(), root=ROOT)
