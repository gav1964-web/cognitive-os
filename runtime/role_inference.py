"""Resolve operational role routes independently of the general L4.5 provider."""
from dataclasses import replace
import os

from .local_inference import LocalInferenceConfig, LlmProfileError, load_llm_profiles

UPSTREAM_ROLES = ('analyzer', 'architect', 'spec_writer')


def role_model_config(role: str) -> LocalInferenceConfig:
    payload = load_llm_profiles()
    name = payload.get('role_profiles', {}).get(role)
    profile = payload['profiles'].get(name)
    if role not in UPSTREAM_ROLES or not profile:
        raise LlmProfileError(f'missing or unsupported role profile: {role}')
    from .llm_failover import fallback_configs, fallback_codes
    prefix = 'COGNITIVE_OS_' + role.upper()
    key_env = os.environ.get(prefix + '_API_KEY_ENV', profile.get('api_key_env', ''))
    return LocalInferenceConfig(
        base_url=os.environ.get(prefix + '_BASE_URL', profile['base_url']).rstrip('/'),
        model=os.environ.get(prefix + '_MODEL', profile['model']),
        provider_label=f'{role}:{name}',
        api_key=os.environ.get(key_env) or None,
        timeout_seconds=float(os.environ.get(prefix + '_TIMEOUT', profile['timeout_seconds'])),
        response_format=profile.get('response_format', False),
        strict_json=True,
        max_output_tokens=profile.get('max_output_tokens'),
        fallbacks=fallback_configs(profile, LocalInferenceConfig),
        fallback_on_codes=fallback_codes(profile),
    )


def traced_role_config(role, config, events):
    """Preserve a caller's telemetry sink while attaching role identity."""
    latest = []
    def record(event):
        row = {'role': role, **event}
        latest[:] = [row]
        events.append(row)
        if config.telemetry_sink:
            config.telemetry_sink(event)
    def capture(evidence):
        if latest:
            latest[0]['response_evidence'] = evidence
        if config.raw_response_sink:
            config.raw_response_sink(evidence)
    return replace(config, telemetry_sink=record, strict_json=True, raw_response_sink=capture)


def role_llm_invoked(state):
    advisory = dict(state['adr'].get('architect_advisory') or {})
    events = state.get('role_inference', {}).get('events', [])
    return bool(advisory.get('llm_invoked')) or any(
        event.get('final_content_state') == 'present' and not event.get('provider_failure')
        for event in events)


def prepare_role_research(requests, configs, root):
    from .role_research import validate_request, research_question, persist_research
    if not isinstance(requests, list) or len(requests) > 3:
        raise ValueError('research_requires_at_most_three_requests')
    for request in requests:
        validate_request(request, root)
        if configs.get(request['role']) is None:
            raise ValueError('research_requires_enabled_role_model')
    if len({r['role'] for r in requests}) != len(requests):
        raise ValueError('research_requires_one_question_per_role')
    results = []
    for request in requests:
        role = request['role']
        config = configs[role]
        if config is None:
            raise ValueError('research_requires_enabled_role_model')
        result = research_question(request, config=config, root=root)
        result['receipt'] = persist_research(result, root)
        results.append(result)
        if result['checked_claims']:
            context = dict(config.advisory_context or {})
            context['external_research'] = {'owner': result['owner'],
                'claims': result['checked_claims'], 'receipt': result['receipt'],
                'admission': result['admission']}
            configs[role] = replace(config, advisory_context=context)
    return results
