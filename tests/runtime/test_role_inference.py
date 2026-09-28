"""Exercise role consumers through the real JSON client, without a live model."""
import io
import json
from pathlib import Path

import pytest

from runtime.local_inference import LocalInferenceConfig, LocalInferenceError
from runtime.role_inference import role_model_config
from runtime.role_pipeline import run_role_pipeline
from runtime.spec_writer_candidate_arbiter import arbitrate_candidates

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def requests(monkeypatch):
    rows = []
    def respond(request, timeout):
        payload = json.loads(request.data)
        rows.append((payload, timeout))
        system = payload['messages'][0]['content']
        if 'ArchitectSkill' in system:
            user = json.loads(payload['messages'][1]['content'])
            answer = {'chosen_option_id': user.get('current_choice'), 'reason': '',
                      'additional_risks': [], 'summary': 'Retain the bounded option.'}
        elif 'Select the strongest' in system:
            user = json.loads(payload['messages'][1]['content'])
            answer = {'selected_source': user['candidates'][0]['source'], 'reason': 'Existing bounded contract.'}
        elif 'Level 4 cortex' in system:
            answer = {'executive_summary': 'A CLI transforms text.',
                      'capability_decomposition': [], 'refactor_plan': [],
                      'cognitive_loop': {}, 'open_questions': [], 'confidence': 'low'}
        else:
            answer = {'signals': [], 'confidence': 'low'}
        # The provider returns the role document; COS validates its schema.
        content = json.dumps(answer)
        return io.BytesIO(json.dumps({'model': 'deepseek/deepseek-chat', 'choices': [
            {'finish_reason': 'stop', 'message': {'content': content}}]}).encode())
    monkeypatch.setattr('runtime.local_inference.request.urlopen', respond)
    return rows


def test_operational_pipeline_routes_real_analyzer_and_architect_consumers(requests):
    result = run_role_pipeline(root=ROOT,
        project_dir=ROOT / 'benchmarks/project_analyzer/projects/simple_cli_tool',
        goal='Extract a bounded text normalization contract', use_role_llm=True)
    assert result['status'] == 'ok'
    assert len(requests) >= 3  # Analyzer signals + deliberation + Architect.
    assert all(row['model'] == 'deepseek/deepseek-chat' and row['response_format'] == {'type': 'json_object'}
               and row['max_tokens'] == 32768 and timeout == 180
               for row, timeout in requests)
    events = result['role_inference']['events']
    assert {'analyzer', 'architect'} <= {event['role'] for event in events}
    assert all(event['usage_reported'] is False and event['total_tokens'] is None for event in events)
    assert result['role_inference']['routes']['spec_writer']['model'] == 'deepseek/deepseek-chat'
    assert result['safety']['llm_invoked'] is True
    assert result['role_inference']['quality_evaluation'] == 'not_evaluated'


def test_eligible_spec_writer_uses_same_route_and_rejects_no_candidate_invention(requests):
    ranked = [{'source': 'policy.py:validate', 'score': 90, 'semantic_score': 85},
              {'source': 'app.py:run', 'score': 86, 'semantic_score': 82}]
    result, advisory = arbitrate_candidates(ranked, config=role_model_config('spec_writer'))
    assert result[0]['source'] == 'policy.py:validate'
    assert advisory['model'] == 'deepseek/deepseek-chat' and advisory['llm_invoked']
    assert len(requests) == 1 and requests[0][0]['response_format'] == {'type': 'json_object'}


def test_role_profiles_do_not_inherit_global_l45_model(monkeypatch):
    monkeypatch.setenv('COGNITIVE_OS_L45_MODEL', 'unrelated-model')
    assert role_model_config('analyzer').model == 'deepseek/deepseek-chat'
    monkeypatch.setenv('COGNITIVE_OS_ARCHITECT_MODEL', 'explicit-model')
    assert role_model_config('architect').model == 'explicit-model'
    assert [c.model for c in role_model_config('spec_writer').fallbacks] == []
    assert LocalInferenceConfig.from_l45_env().model == 'unrelated-model'


def test_browser_provider_is_only_explicitly_selectable():
    from runtime.local_inference import load_llm_profiles
    profiles = load_llm_profiles()['profiles']
    assert profiles['geminivm_pro']['model'] == 'geminivm/pro'
    for name, profile in profiles.items():
        if name != 'geminivm_pro':
            assert not profile['model'].startswith('geminivm/')
        assert 'geminivm_pro' not in profile.get('fallback_profiles', [])


def test_default_role_outage_does_not_launch_experimental_provider(monkeypatch):
    from urllib.error import HTTPError
    from runtime.local_inference import call_json_chat
    calls = []
    def fail(request, timeout):
        calls.append(json.loads(request.data)['model'])
        raise HTTPError(request.full_url, 503, 'unavailable', {}, io.BytesIO(b'{}'))
    monkeypatch.setattr('runtime.local_inference.request.urlopen', fail)
    with pytest.raises(LocalInferenceError):
        call_json_chat([], config=role_model_config('analyzer'))
    assert calls == ['deepseek/deepseek-chat']


@pytest.mark.parametrize('status,code', [(409, 'busy'), (502, 'service_error'),
    (422, 'refusal'), (504, 'response_timeout'), (None, None)])
def test_provider_failure_never_becomes_an_arbiter_format_retry(monkeypatch, status, code):
    failure = LocalInferenceError('provider unavailable')
    failure.http_status = status
    failure.provider_failure = {'code': code} if code else {}
    failure.transport_retryable = status is None
    calls = []
    def fail(*args, **kwargs):
        calls.append(kwargs)
        raise failure
    monkeypatch.setattr('runtime.spec_writer_candidate_arbiter.call_json_chat', fail)
    ranked = [{'source': 'a.py:a', 'score': 80}, {'source': 'b.py:b', 'score': 79}]
    result, advisory = arbitrate_candidates(ranked, config=role_model_config('spec_writer'))
    assert len(calls) == 1 and result == ranked
    assert advisory['source'] == 'deterministic_fallback'
    assert advisory['quality_evaluation'] == 'not_evaluated'


def test_stage_build_passes_spec_writer_configuration(monkeypatch):
    from runtime import role_pipeline_stages as stages
    cfg = role_model_config('spec_writer')
    calls = []
    monkeypatch.setattr(stages, 'run_configured_role_prefix', lambda **kw: calls.append(kw) or {})
    monkeypatch.setattr(stages, '_bind_build_artifacts', lambda *args: None)
    stages.stage_build({'goal': 'test', 'project_report': {},
                       'architect_advisory_config': None, 'spec_writer_advisory_config': cfg})
    assert calls[0]['spec_writer_advisory_config'] is cfg


def test_cli_enables_profiles_and_checks_gateway_before_running(monkeypatch, capsys):
    from tools import role_pipeline_run
    import sys
    calls = []
    monkeypatch.setattr(sys, 'argv', ['role_pipeline_run', '--project-dir', '.', '--goal', 'test'])
    monkeypatch.setattr('runtime.llm_gateway_bootstrap.ensure_llm_gateway_for_url',
                        lambda *args: calls.append('preflight') or {'status': 'already_running'})
    def pipeline(**kwargs):
        calls.append(kwargs)
        return {'status': 'ok'}
    monkeypatch.setattr('runtime.role_pipeline.run_role_pipeline', pipeline)
    assert role_pipeline_run.main() == 0
    assert calls[0] == 'preflight' and calls[1]['use_role_llm'] is True
    assert json.loads(capsys.readouterr().out)['status'] == 'ok'


def test_explicit_library_configuration_wins(monkeypatch):
    explicit = LocalInferenceConfig(base_url='http://example.invalid/v1', model='explicit')
    def workflow(*, state):
        assert state['analyzer_config'].model == 'explicit'
        assert state['architect_advisory_config'].model == 'deepseek/deepseek-chat'
        assert state['spec_writer_advisory_config'].model == 'deepseek/deepseek-chat'
        state['result'] = {'status': 'ok'}
    monkeypatch.setattr('runtime.role_pipeline.run_configured_workflow', workflow)
    assert run_role_pipeline(root=ROOT, project_dir=ROOT, goal='test',
        use_role_llm=True, analyzer_config=explicit)['status'] == 'ok'
